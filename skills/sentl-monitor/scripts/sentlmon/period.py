"""`period`: the runs of one report period pooled, compared with the periods before it,
and the material the report is written from."""

import calendar
import datetime as dt
from collections import Counter, defaultdict

from .common import (FIGURE_FLOOR, RUN_FLOOR, Refused, Study, fmt_decimal, fmt_percent, first_mention, folded,
                     is_owned, load_json, mean, parse_time, public_name, require_language, write_json,
                     write_text)
from . import schema
from .compare import K, compare, dimension_entries
from .insights import (EPS, TOP_SOURCES, classify, episodes, fact_cell, fact_terms, page_of, readings, reset,
                       says_missing, top_sources)


HALVES_DAYS = 14


class BelowFloor(Exception):
    """No run left in the period once runs under the judged floor are left out; exit code 4."""


def _back(day, every):
    if every == "weekly":
        return day - dt.timedelta(days=7)
    year, month = (day.year, day.month - 1) if day.month > 1 else (day.year - 1, 12)
    return day.replace(year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1]))


def intervals(date, every, count=K):
    """[start, end) of the `report_every` interval that ends with the day `date`, then of the
    `count` intervals before it, as UTC times."""
    end = dt.date.fromisoformat(date) + dt.timedelta(days=1)
    out = []
    for _ in range(count + 1):
        start = _back(end, every)
        out.append(tuple(dt.datetime.combine(d, dt.time(), dt.timezone.utc) for d in (start, end)))
        end = start
    return out


def cadence(study):
    """`report_every`, which every period needs."""
    if study.get("kind") == "snapshot":
        raise Refused("a snapshot has no report cadence: `resume` names its next step")
    every = study.get("report_every")
    if every not in ("weekly", "monthly"):
        raise Refused("report_every is not set in study.json: ask the operator whether a report covers a week or a "
                      "month, write it, and run the command again")
    return every


def previous_cut(last, key, started):
    """The start of the last run of project `key` in the report `last`: a later report's runs
    start after it. `started` maps the project's ingested run ids to their start times."""
    return max((started[i] for i in last["runs"].get(key, []) if i in started),
               default=parse_time(last["period"]["to"]))


def select_runs(runs, start=None, end=None, after=None, floor=RUN_FLOOR):
    """The runs started in [start, end) and after `after`, by start time, and those left out
    under the judged floor, with the reason."""
    chosen, excluded = [], []
    for r in sorted(runs, key=lambda r: parse_time(r["started_at"])):
        at = parse_time(r["started_at"])
        if (start and at < start) or (end and at >= end) or (after and at <= after):
            continue
        share = r["judged"] / r["expected"] if r["expected"] else 0.0
        if share < floor:
            excluded.append({"run_id": r["run_id"],
                             "reason": f"{fmt_percent(share)} of expected answers judged "
                                       f"({r['judged']} of {r['expected']}), under the 90% floor"})
        else:
            chosen.append(r)
    return chosen, excluded


def latest_criteria(runs, versions):
    """A period that holds two versions of a question whose criteria changed uses the runs
    of the latest version only: the earlier runs lose that question. A run with no version
    was matched against the first recorded version and is read as judged under it; a run
    inside a detection window whose rubric is unknown loses the questions it lists in
    `criteria_unknown`. Returns the runs and {run id: questions dropped}."""
    numbers = [r["version"] for r in runs if r["version"] is not None]
    hashes = {v["version"]: {q["key"]: q["criteria_hash"] for d in v["dimensions"] for q in d["questions"]}
              for v in versions}
    latest = hashes[max(numbers)] if numbers else {}
    out, dropped = [], {}
    for r in runs:
        mine = hashes.get(r["version"] if r["version"] is not None else versions[0]["version"], {})
        gone = {q for q in r["plan"]["questions"] if q in mine and q in latest and mine[q] != latest[q]}
        gone |= set(r.get("criteria_unknown") or ()) & set(r["plan"]["questions"])
        if gone:
            dropped[str(r["run_id"])] = sorted(gone)
            r = {**r, "plan": {**r["plan"], "questions": [q for q in r["plan"]["questions"] if q not in gone]},
                 "responses": [x for x in r["responses"] if x["question"] not in gone]}
        out.append(r)
    return out, dropped


class Reader:
    """Subject and foil lookup over answers, from the study as it stands now."""

    def __init__(self, study):
        subject = study.get("subject") or {}
        self.aliases = subject.get("aliases") or []
        self.owned = subject.get("owned_domains") or []
        self.foils = [f.get("aliases") or [] for f in study.get("foils") or []]
        self.foil_domains = [(f.get("label") or f.get("id"), f["domains"]) for f in study.get("foils") or []
                             if isinstance(f.get("domains"), list) and f["domains"]]

    def author(self, domain):
        """`owned`, a foil's label, or `third` (a third party), subdomains included."""
        if is_owned(domain, self.owned):
            return "owned"
        return next((label for label, domains in self.foil_domains if is_owned(domain, domains)), "third")

    def position(self, answer):
        """None when the subject is not named; else 1 + the foils named before it."""
        if answer is None:
            return None
        text = folded(answer)
        at = first_mention(text, self.aliases)
        if at is None:
            return None
        before = 0
        for aliases in self.foils:
            other = first_mention(text, aliases)
            if other is not None and other < at:
                before += 1
        return 1 + before


def cell(responses, expected, reader):
    judged = [r["score"] for r in responses if r["score"] is not None]
    given = [r for r in responses if r["answer"] is not None]
    positions = [p for p in (reader.position(r["answer"]) for r in given) if p is not None]
    pairs = defaultdict(list)
    for r in responses:
        if r["score"] is not None:
            pairs[(r["question"], r["model"])].append(r["score"])
    domains, citing, with_sources = Counter(), 0, 0
    for r in responses:
        found = {s["domain"] for s in r["sources"] if s["domain"]}
        domains.update(found)
        if found:
            with_sources += 1
            citing += any(is_owned(d, reader.owned) for d in found)
    coverage = len(judged) / expected if expected else None
    return {
        "mean": mean(judged),
        "figure": coverage is not None and coverage >= FIGURE_FLOOR and bool(judged),
        "received": len(responses), "judged": len(judged), "expected": expected, "coverage": coverage,
        "bands": {"1-2": sum(s <= 2 for s in judged), "3": sum(s == 3 for s in judged),
                  "4-5": sum(s >= 4 for s in judged)},
        "presence": {"named": len(positions), "given": len(given),
                     "rate": len(positions) / len(given) if given else None,
                     "position": mean(positions)},
        "unstable_pairs": [{"question": q, "model": m} for (q, m), s in sorted(pairs.items())
                           if max(s) - min(s) >= 2],
        "domains": dict(sorted(domains.items(), key=lambda kv: (-kv[1], kv[0]))),
        "owned": {"citing": citing, "with_sources": with_sources},
        "readings": readings(responses),
        "authors": _authors(responses, reader),
    }


def _authors(responses, reader):
    """Answers citing owned pages, a foil's pages and third-party pages, out of those citing
    any; and the foil pages most cited, each counted once per answer."""
    counts, pages = Counter(), Counter()
    for r in responses:
        cited = [(s, reader.author(s["domain"])) for s in r["sources"] if s["domain"]]
        if not cited:
            continue
        counts["with_sources"] += 1
        kinds = {"owned" if a == "owned" else "third" if a == "third" else "foil" for _, a in cited}
        counts.update(kinds)
        pages.update({(page_of(s), a) for s, a in cited if a not in ("owned", "third")})
    return {"owned": counts["owned"], "foil": counts["foil"], "third": counts["third"],
            "with_sources": counts["with_sources"],
            "foil_pages": [{"page": page, "foil": foil, "answers": n}
                           for (page, foil), n in sorted(pages.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]}


def _domains(r):
    return {s["domain"] for s in r["sources"] if s["domain"]}


def _question_insights(scope, rs, runs, models, study_question, text, reader, lang):
    """Fact currency, the sources behind a fact or a score, presence by run on a question
    naming no brand, and the answers that found no evidence, added to a question's scope."""
    given = [r for r in rs if r["answer"] is not None]
    terms = fact_terms(study_question or {})
    by_run = [(run, [r for r in rs if r["run"] == run["run_id"]]) for run in runs]
    by_run = [(run, mine) for run, mine in by_run if mine]
    groups = {}
    if terms:
        scope["facts"] = {
            "terms": terms, "total": fact_cell(rs, terms),
            "by_model": {m: fact_cell([r for r in rs if r["model"] == m], terms) for m in models},
            "runs": [{"run_id": run["run_id"], "date": run["started_at"][:10], "total": fact_cell(mine, terms),
                      "by_model": {m: fact_cell([r for r in mine if r["model"] == m], terms) for m in models}}
                     for run, mine in by_run]}
        kinds = [(classify(r["answer"], terms), r) for r in given]
        groups["outdated"] = [_domains(r) for k, r in kinds if k == "outdated_only"]
        groups["current"] = [_domains(r) for k, r in kinds if k in ("current_only", "both")]
    groups["low"] = [_domains(r) for r in given if r["score"] is not None and r["score"] <= 2]
    groups["high"] = [_domains(r) for r in given if r["score"] is not None and r["score"] >= 4]
    # A pair of groups is read for its contrast, so it is listed only when both groups have an
    # answer citing a source.
    sources = {}
    for pair in (("outdated", "current"), ("low", "high")):
        if all(any(groups.get(group, ())) for group in pair):
            for group in pair:
                sources[group] = top_sources(groups[group], groups[OPPOSITE[group]])
    if sources:
        scope["group_sources"] = sources
    if reader.position(text) is None:
        scope["presence_runs"] = []
        for run, mine in by_run:
            answered = [r for r in mine if r["answer"] is not None]
            named = sum(1 for r in answered if reader.position(r["answer"]) is not None)
            scope["presence_runs"].append({"run_id": run["run_id"], "date": run["started_at"][:10], "named": named,
                                           "given": len(answered),
                                           "rate": named / len(answered) if answered else None})
    missing = {}
    for m in models:
        mine = [r for r in given if r["model"] == m]
        flagged = [says_missing(r["answer"], lang) for r in mine]
        if any(flagged):
            missing[m] = {"answers": sum(flagged), "given": len(mine),
                          "judged": sum(1 for r in mine if r["score"] is not None),
                          "mean": mean([r["score"] for r in mine]),
                          "mean_without": mean([r["score"] for r, f in zip(mine, flagged) if not f])}
    if missing:
        scope["missing"] = missing


def _expected(runs, questions, model=None):
    total = 0
    for run in runs:
        plan = run["plan"]
        qs = sum(1 for q in plan["questions"] if q in questions)
        ms = len(plan["models"]) if model is None else int(model in plan["models"])
        total += qs * ms * plan["rounds"]
    return total


def _scope(responses, runs, questions, models, reader):
    rs = [r for r in responses if r["question"] in questions]
    return {"total": cell(rs, _expected(runs, questions), reader),
            "by_model": {m: cell([r for r in rs if r["model"] == m], _expected(runs, questions, m), reader)
                         for m in models}}


def _period(study, date, chosen, reader, versions):
    """A period's body from `chosen`: {project key: (runs, runs left out, questions dropped)}.
    Its dimensions and questions are those of its runs' latest version, named and worded as
    then (an edit made after its last run belongs to the next period), less any with no
    answer expected; a period of runs older than every version takes the first one."""
    period = {"schema": "sentl-monitor/period@2", "date": date, "runs": {}, "excluded": {}, "versions": {},
              "starts": {}, "dropped": {}, "asked": {}, "settings": {}, "projects": {}}
    starts = []
    lang = (study.get("market") or {}).get("language")
    for proj in study["projects"]:
        key = proj["key"]
        studied = {q["key"]: q for d in proj["dimensions"] for q in d["questions"]}
        runs, excluded, dropped = chosen[key]
        if excluded:
            period["excluded"][key] = excluded
        if dropped:
            period["dropped"][key] = dropped
        if not runs:
            continue
        period["runs"][key] = [r["run_id"] for r in runs]
        period["versions"][key] = [r["version"] for r in runs]
        period["starts"][key] = [r["started_at"] for r in runs]
        starts += period["starts"][key]
        responses = [{**r, "run": run["run_id"]} for run in runs for r in run["responses"] if r["match"] != "unmatched"]
        models = sorted({m for run in runs for m in run["plan"]["models"]})
        numbers = [r["version"] for r in runs if r["version"] is not None]
        layout = next((v for v in versions[key] if v["version"] == max(numbers, default=0)), versions[key][0])
        block, asked = {"dimensions": {}}, []
        for d in (d for d in layout["dimensions"] if not d["archived"]):
            questions = [q for q in d["questions"] if _expected(runs, {q["key"]})]
            if not questions:
                continue
            qkeys = [q["key"] for q in questions]
            entry = _scope(responses, runs, set(qkeys), models, reader)
            entry["questions"] = {q: _scope(responses, runs, {q}, models, reader) for q in qkeys}
            for q in questions:
                _question_insights(entry["questions"][q["key"]], [r for r in responses if r["question"] == q["key"]],
                                   runs, models, studied.get(q["key"]), q["text"], reader, lang)
            block["dimensions"][d["key"]] = entry
            asked.append({"key": d["key"], "name": d["name"],
                          "questions": [{"key": q["key"], "text": q["text"]} for q in questions]})
        period["asked"][key] = asked
        if numbers:
            rounds, schedule = layout["settings"]["rounds"], layout["settings"]["schedule"]
        else:
            rounds = max(r["plan"]["rounds"] for r in runs)
            schedule = _schedule_of([r["started_at"] for r in runs]) or layout["settings"].get("schedule")
        period["settings"][key] = {"models": models, "rounds": rounds, "schedule": schedule}
        all_q = {q for e in block["dimensions"].values() for q in e["questions"]}
        block.update(_scope(responses, runs, all_q, models, reader))
        # A project's figure is the mean of its dimension figures, as Sentl scores a run.
        block["total"]["mean"] = mean([e["total"]["mean"] for e in block["dimensions"].values()])
        for m in models:
            block["by_model"][m]["mean"] = mean([e["by_model"][m]["mean"] for e in block["dimensions"].values()])
        period["projects"][key] = block
    if starts:
        period["from"], period["to"] = min(starts, key=parse_time), max(starts, key=parse_time)
    return period


def _schedule_of(starts):
    """How often runs started, from the median gap between the distinct days they started on
    (a manual run and a rerun on the same day are one day); None for a single day."""
    days = sorted({parse_time(s).date() for s in starts})
    gaps = sorted((b - a).days for a, b in zip(days, days[1:]))
    if not gaps:
        return None
    median = gaps[len(gaps) // 2]
    return "daily" if median < 1.5 else "weekly" if median < 10 else "monthly"


def _halves(study, date, current, chosen, end, reader, versions, names):
    """The two halves of a first period that has no earlier one: the period's kept runs (`chosen`,
    after `latest_criteria`) split at the midpoint between its first run and the end of the
    report's date (`end`), when they span at least 14 days. A project with runs in one half only
    is not compared, and with no project in both halves there are no halves. Returns
    ([first, second], split time, the projects in both halves, lines for the operator), or
    (None, None, [], lines)."""
    start, span = parse_time(current["from"]), parse_time(current["to"]) - parse_time(current["from"])
    if span < dt.timedelta(days=HALVES_DAYS):
        return None, None, [], [f"The runs span {span.days} days, under the {HALVES_DAYS} needed to compare the two "
                                "halves of the period, so this report is the first measurement (tell the operator)."]
    split = start + (end - start) / 2
    halves = []
    for half, inside in (("first", lambda at: at < split), ("second", lambda at: at >= split)):
        part = {}
        for k, (kept, _, dropped) in chosen.items():
            runs = [r for r in kept if inside(parse_time(r["started_at"]))]
            ids = {str(r["run_id"]) for r in runs}
            part[k] = (runs, [], {i: qs for i, qs in dropped.items() if i in ids})
        built = _period(study, date, part, reader, versions)
        built.update(half=half, names={m: public_name(m, names) for b in built["projects"].values() for m in b["by_model"]})
        halves.append(built)
    first, second = halves
    both = [k for k in chosen if first["runs"].get(k) and second["runs"].get(k)]
    if not both:
        return None, None, [], ["No project has runs in both halves of the period, so this report is the first "
                                "measurement (tell the operator)."]
    lines = [f"The runs span {span.days} days: the second half of the period, runs started {second['from'][:10]} to "
             f"{second['to'][:10]}, is compared with the first half, runs started {first['from'][:10]} to "
             f"{first['to'][:10]}; the halves are written with no report of their own (tell the operator)."]
    lines += [f"{k} has runs in the {h['half']} half only and is not compared (tell the operator)."
              for k in chosen if k not in both for h in halves if h["runs"].get(k)]
    return halves, split, both, lines


def _left_out(period, where):
    return [f"Left out of {k}{where}: run {e['run_id']}, {e['reason']} (tell the operator)."
            for k, ex in period["excluded"].items() for e in ex]


def build(root, date, models_file=None):
    reset()
    folder = Study(root)
    study = folder.study
    require_language(study)
    snapshot = study.get("kind") == "snapshot"
    every = None if snapshot else cadence(study)
    reader = Reader(study)
    names = schema.models(models_file) if models_file else {}
    keys = [p["key"] for p in study["projects"]]
    runs = {k: folder.runs(k) for k in keys}
    versions = {k: folder.versions(k) for k in keys}
    reports = [] if snapshot else [e for e in folder.reports() if e["date"] < date]
    bounds = None if snapshot else intervals(date, every)
    periods_dir = folder.path("history", "periods")

    def pick(window):
        out = {}
        for k in keys:
            chosen, excluded = select_runs(runs[k], floor=0.0 if snapshot else RUN_FLOOR, **window(k))
            kept, dropped = latest_criteria(chosen, versions[k])
            out[k] = (kept, excluded, dropped)
        return out

    if snapshot:
        held = sum(len(r) for r in runs.values())
        if held > 1:
            raise Refused(f"a snapshot holds one run, and this folder holds {held}: the run to report is the "
                          "operator's choice, and the others are removed from history/runs first")
        chosen = pick(lambda k: {})
        lines = ["Snapshot: the period is the project's one run, compared with nothing."]
    elif reports:
        last = reports[-1]
        cut = {k: previous_cut(last, k, {r["run_id"]: parse_time(r["started_at"]) for r in runs[k]}) for k in keys}
        chosen = pick(lambda k: {"end": bounds[0][1], "after": cut[k]})
        lines = [f"The period covers the runs started after the last run of the report of {last['date']}."]
    else:
        chosen = pick(lambda k: {"start": bounds[0][0], "end": bounds[0][1]})
        lines = [f"First report: the period covers the runs started from {bounds[0][0].date()} to {date}."]
    current = _period(study, date, chosen, reader, versions)
    if not current["runs"]:
        reasons = [f"{k}: run {e['run_id']} left out, {e['reason']}" for k, ex in current["excluded"].items() for e in ex]
        raise BelowFloor("no run in the period" + (":\n  " + "\n  ".join(reasons) if reasons else
                                                   ": ingest the completed runs started in it first"))
    lines += _left_out(current, "")

    halves, split, both = None, None, []
    if not reports and not snapshot:
        # The periods before a first report, and the halves of its period, are built again each
        # time it is built, so none is left over. The halves of other dates belong to their own
        # reports and stay. The runs of the rebuilt periods must all be here, or they would be
        # built again from fewer runs.
        folder.require_runs([load_json(p) for p in periods_dir.glob("*.json")
                             if p.stem < date and load_json(p).get("rebuilt")], date)
        for path in periods_dir.glob("*.json"):
            if path.stem < date and load_json(path).get("rebuilt"):
                path.unlink()
        for half in ("first", "second"):
            periods_dir.joinpath(f"{date}.{half}.json").unlink(missing_ok=True)
        rebuilt = []
        for start, stop in bounds[1:]:
            day = (stop - dt.timedelta(days=1)).date().isoformat()
            earlier = _period(study, day, pick(lambda k: {"start": start, "end": stop}), reader, versions)
            lines += _left_out(earlier, f" (rebuilt period {day})")
            if earlier["runs"]:
                earlier.update(rebuilt=True, names={m: public_name(m, names)
                                                    for b in earlier["projects"].values() for m in b["by_model"]})
                write_json(periods_dir / f"{day}.json", earlier)
                rebuilt.append(day)
        if rebuilt:
            lines.append(f"Rebuilt {len(rebuilt)} earlier period(s) from the project's runs, with no report of their own: "
                         f"{', '.join(sorted(rebuilt))}. The first report compares with them (tell the operator).")
        else:
            halves, split, both, found = _halves(study, date, current, chosen, bounds[0][1], reader, versions, names)
            lines += [f"There is no earlier period: no completed run started before {bounds[0][0].date()} was "
                      "ingested.", *found]
            for half in halves or ():
                write_json(periods_dir / f"{date}.{half['half']}.json", half)

    unavailable = folder.path("history", "unavailable.json")
    for e in (load_json(unavailable)["runs"] if unavailable.exists() else []):
        lines.append(f"Unavailable, left out until Sentl returns its results: run {e['run_id']} of {e['project']} "
                     f"({e['reason']}) (tell the operator).")
    for k, dropped in current["dropped"].items():
        lines += [f"The criteria of {', '.join(qs)} changed in the period: run {run_id} of {k} is left out for them, "
                  "and the runs of the latest version are used (tell the operator)." for run_id, qs in dropped.items()]

    dates = {e["date"] for e in reports}
    dates |= {p.stem for p in periods_dir.glob("*.json") if p.stem < date and load_json(p).get("rebuilt")}
    prevs = [load_json(periods_dir / f"{d}.json") for d in sorted(dates, reverse=True)[:K]
             if (periods_dir / f"{d}.json").exists()]
    # The answers of the previous period are read.
    folder.require_runs(prevs[:1], date)
    cache = {}

    def run_of(key, run_id):
        if (key, run_id) not in cache:
            cache[(key, run_id)] = folder.run(key, run_id)
        return cache[(key, run_id)]

    def answers(period, key, q, m):
        out = []
        for run_id in period["runs"].get(key, []):
            if q in period.get("dropped", {}).get(key, {}).get(str(run_id), ()):
                continue
            run = run_of(key, run_id)
            out += [(run["started_at"], run_id, r) for r in run["responses"]
                    if (r["question"], r["model"]) == (q, m) and r["match"] != "unmatched" and r["score"] is not None]
        return out

    earlier = {k: _runs_of(prevs[0], k, run_of) if prevs else [] for k in keys}
    now = {k: [(run, ()) for run in chosen[k][0]] for k in keys}
    if halves:
        # No earlier period: the second half is compared with the first, as with one previous period.
        first, second = halves

        def compared(h):
            return {**h, "projects": {k: b for k, b in h["projects"].items() if k in both}}
        # The design changes are those made inside the whole period, between its first run and its last.
        current["comparison"] = compare(study, compared(second), [compared(first)], versions, answers, reader.owned,
                                        {"period": current})
        current["comparison"].update(previous=None, previous_period=None, range_of=[], halves={
            **{h["half"]: {"from": h["from"], "to": h["to"],
                           "projects": {k: {"runs": len(ids), "answers": h["projects"][k]["total"]["received"]}
                                        for k, ids in h["runs"].items()}} for h in halves},
            "split": split.replace(microsecond=0).isoformat().replace("+00:00", "Z")})
        before, after = ({k: _runs_of(h, k, run_of) for k in keys} for h in halves)
    else:
        current["comparison"] = compare(study, current, prevs, versions, answers, reader.owned)
        before, after = earlier, now
    # The insights the findings are written from read the whole period.
    _add_episodes(study, current, earlier, now, versions)
    current["comparison"]["presence_sources"] = _presence_sources(current, before, after, reader)
    seen = {m for p in [current, *prevs] for b in p["projects"].values() for m in b["by_model"]}
    current["names"] = {m: public_name(m, names) for m in sorted(seen)}
    write_json(periods_dir / f"{date}.json", current)

    material = [f"# Material for the report of {date}", ""]
    for proj in study["projects"]:
        kept = chosen[proj["key"]][0]
        if kept:
            responses = [r for run in kept for r in run["responses"] if r["match"] != "unmatched"]
            material += _material(proj, current["asked"][proj["key"]], current["projects"][proj["key"]],
                                  responses, kept, names, reader, study.get("report_language") or "en")
    material += _changes_material(study, current, versions, names, lambda key, ref: next(
        r for r in run_of(key, ref["run_id"])["responses"] if r["response_id"] == ref["response_id"]))
    write_text(folder.path("history", "material", f"{date}.md"), "\n".join(material) + "\n")

    c = current["comparison"]
    head = [f"Period {date}: " + "; ".join(f"{k} runs {v}" for k, v in current["runs"].items()) + "."]
    if c["previous"] or halves:
        called = sum(bool((e.get(m) or {}).get("changed")) for e in dimension_entries(c).values()
                     for m in ("mean", "presence"))
        against = f"the period of {c['previous']}" if c["previous"] else "the first half of the period"
        lines.append(f"Compared with {against}: {called} dimension change(s) called, "
                     f"{len(c['verdict_changes'])} verdict change(s), "
                     f"{len(c['domains']['new']) + len(c['domains']['lost'])} domain(s) new or lost, "
                     f"{len(c['design_changes'])} design change(s).")
    for k, block in current["projects"].items():
        for dkey, e in block["dimensions"].items():
            if not e["total"]["figure"]:
                t = e["total"]
                lines.append(f"Dimension {dkey} of {k}: {t['judged']} of {t['expected']} answers judged, "
                             "under 80%: shown without a figure (tell the operator).")
    return "\n".join(head + lines)


def _runs_of(period, key, run_of):
    """A period's runs of a project, each with the questions it lost in that period."""
    dropped = period.get("dropped", {}).get(key, {})
    return [(run_of(key, i), tuple(dropped.get(str(i), ()))) for i in period["runs"].get(key, [])]


def _answers_to(runs, question, models=None):
    return [r for run, gone in runs if question not in gone for r in run["responses"]
            if r["question"] == question and r["match"] != "unmatched" and (models is None or r["model"] in models)]


def _add_episodes(study, period, earlier, now, versions):
    """Episodes of each question's mean and of its facts' current share, run by run, on the
    assistants every run of the series has, and leaving out the earlier runs judged under
    other criteria for the question."""
    for proj in study["projects"]:
        key = proj["key"]
        block = period["projects"].get(key)
        if not block:
            continue
        studied = {q["key"]: q for d in proj["dimensions"] for q in d["questions"]}
        hashes = {v["version"]: {q["key"]: q["criteria_hash"] for d in v["dimensions"] for q in d["questions"]}
                  for v in versions[key]}
        first = versions[key][0]["version"]
        latest = max((v for v in period["versions"].get(key, []) if v is not None), default=first)

        def criteria(run, q):
            return hashes.get(run["version"] if run["version"] is not None else first, {}).get(q)
        for dim in block["dimensions"].values():
            for q, scope in dim["questions"].items():
                terms = fact_terms(studied.get(q) or {})
                now_hash = hashes.get(latest, {}).get(q)
                before = [(run, gone) for run, gone in earlier[key] if criteria(run, q) == now_hash]
                series = before + now[key]
                models = set.intersection(*(set(run["plan"]["models"]) for run, _ in series)) if series else set()

                def values(runs):
                    out = []
                    for run, gone in runs:
                        rs = [] if q in gone else _answers_to([(run, ())], q, models)
                        share = fact_cell(rs, terms)["current_share"] if terms else None
                        out.append((run["started_at"], (mean([r["score"] for r in rs]), share)))
                    return out
                past, current = values(before), values(now[key])
                found = [_dated({"measure": measure, **e}) for i, measure in enumerate(("mean", "current_share"))
                         for e in episodes([v[i] for _, v in past], [(d, v[i]) for d, v in current])]
                for e in (e for e in found if e["closed"]):
                    e["later"] = _later(e, [(d, v[0 if e["measure"] == "mean" else 1]) for d, v in current])
                if found:
                    scope["episodes"] = found


def _later(episode, series):
    """The runs after a closed episode whose value lies on its side of the range it was measured
    against: the close date is the first run back inside the range and says nothing about the runs
    after it."""
    lo, hi = episode["range"]
    end = parse_time(episode["last_at"])
    return [{"date": at[:10], "value": v} for at, v in series if v is not None and parse_time(at) > end
            and (v > hi + EPS if episode["side"] == "above" else v < lo - EPS)]


def _dated(episode):
    """An episode found on run start times: its dates as days, and the start times of its first
    and last run, which place it on either side of a split."""
    episode.update(first_at=episode["first"], last_at=episode["last"])
    for k in ("first", "last", "closed", "switched"):
        if episode.get(k):
            episode[k] = episode[k][:10]
    return episode


def _presence_sources(period, earlier, now, reader):
    """For each question whose presence changed, the domains cited by the answers naming the
    subject in one period and by no answer to the question in the other."""
    out = []
    for (key, dkey), e in dimension_entries(period["comparison"]).items():
        for q, qe in (e.get("questions") or {}).items():
            if qe.get("status") != "compared" or not (qe.get("presence") or {}).get("changed"):
                continue
            models = set(e["models"])
            this = [r for r in _answers_to(now[key], q, models) if r["answer"] is not None]
            last = [r for r in _answers_to(earlier[key], q, models) if r["answer"] is not None]

            def moved(here, there):
                cited = {d for r in there for d in _domains(r)}
                naming = Counter(d for r in here if reader.position(r["answer"]) is not None for d in _domains(r))
                return [{"domain": d, "answers": n} for d, n in sorted(naming.items(), key=lambda kv: (-kv[1], kv[0]))
                        if d not in cited][:TOP_SOURCES]
            new, lost = moved(this, last), moved(last, this)
            if new or lost:
                out.append({"project": key, "dimension": dkey, "question": q, "new": new, "lost": lost})
    return out


def _n_runs(n):
    return f"{n} run" + ("" if n == 1 else "s")


def _n_answers(n):
    return f"{n} answer" + ("" if n == 1 else "s")


def _share(n, m, answers=False):
    return f"{n} of " + (_n_answers(m) if answers else str(m)) + (f" ({fmt_percent(n / m)})" if m else "")


def _fact_line(c):
    s = c["stating"]
    return (f"answers stating a term {_share(s, c['given'])}; current only {_share(c['current_only'], s)}; "
            f"outdated only {_share(c['outdated_only'], s)}; both {_share(c['both'], s)}; "
            f"a current term {_share(c['current_only'] + c['both'], s)}")


GROUPS = {"outdated": "answers stating only an outdated term", "current": "answers stating a current term",
          "low": "answers scored 1-2", "high": "answers scored 4-5"}
OPPOSITE = {"outdated": "current", "current": "outdated", "low": "high", "high": "low"}


def _question_lines(scope, name, lang):
    """The insight sections of a question in the material, each only when it has content. A
    question without a figure has no mean to cite, so none is printed."""
    out = []
    figure = scope.get("total", {}).get("figure")
    facts = scope.get("facts")
    if facts and facts["total"]["stating"]:
        terms = facts["terms"]
        out += ["", "##### Fact currency", "",
                "Current terms: " + (", ".join(f"«{t}»" for t in terms["current"]) or "none")
                + "; outdated terms: " + (", ".join(f"«{t}»" for t in terms["outdated"]) or "none") + ".",
                f"All assistants: {_fact_line(facts['total'])}"]
        out += [f"- {name(m)}: {_fact_line(c)}" for m, c in facts["by_model"].items() if c["given"]]
        out.append("By run, all assistants then each:")

        def short(c):
            s = c["stating"]
            return (f"a current term {_share(c['current_only'] + c['both'], s)}, outdated only "
                    f"{_share(c['outdated_only'], s)}, both {_share(c['both'], s)}")
        for run in facts["runs"]:
            out.append(f"- {run['date']}: {short(run['total'])} | "
                       + " | ".join(f"{name(m)}: {short(c)}" for m, c in run["by_model"].items() if c["given"]))
    listed = scope.get("group_sources") or {}
    for title, pair in (("Sources behind the fact", ("outdated", "current")),
                        ("Sources behind the score", ("low", "high"))):
        if not any(group in listed for group in pair):
            continue
        out += ["", f"##### {title}", ""]
        for group in (g for g in pair if g in listed):
            entries = listed[group]
            out.append(f"Cited by most of the {GROUPS[group]} ({entries[0]['answers']} citing a source):")
            for e in entries:
                other = e["other"]
                out.append(f"- {e['domain']}: {_share(e['citing'], e['answers'])}; in the {GROUPS[OPPOSITE[group]]}: "
                           + _share(other["citing"], other["answers"]))
    if scope.get("presence_runs"):
        out += ["", "##### Presence by run", ""]
        out += [f"- {r['date']}: subject named in {_share(r['named'], r['given'], True)}"
                for r in scope["presence_runs"]]
    if scope.get("episodes"):
        out += ["", "##### Episodes", ""]
        for e in scope["episodes"]:
            mean_score = e["measure"] == "mean"
            shown = (lambda v: _fmt(v, lang)) if mean_score else fmt_percent
            label = "mean score" if mean_score else "share of the answers stating a current term"
            ending = (f"back inside on {e['closed']}" if e["closed"] else
                      f"jumped to the other side of the range on {e['switched']}" if e.get("switched") else
                      "still outside when the period ends")
            valued = not (mean_score and not figure)
            if valued:
                out.append(f"- {label}, {e['runs']} runs {e['side']} the range {shown(e['range'][0])} to "
                           f"{shown(e['range'][1])} of the {e['earlier']} runs before, from {e['first']} to "
                           f"{e['last']}: " + "; ".join(shown(v) for v in e["values"]) + f"; {ending}")
            else:
                out.append(f"- {label}, {e['runs']} runs {e['side']} the range of the {e['earlier']} runs before, "
                           f"from {e['first']} to {e['last']}; {ending}")
            if e.get("later"):
                out.append(f"  - still {e['side']} that range after the close: "
                           + "; ".join(x["date"] + (f" ({shown(x['value'])})" if valued else "") for x in e["later"])
                           + f"; the close date is the first run back inside the range; it says nothing about the "
                             f"runs after it, so do not write that the {label} was {e['side']} the range only during "
                             "the episode")
    if scope.get("missing"):
        out += ["", "##### Missing evidence", ""]
        out += [f"- {name(m)}: {_share(x['answers'], x['given'], True)} say no source of the kind asked for was "
                "found" + (f"; mean {_fmt(x['mean'], lang)} with them, {_fmt(x['mean_without'], lang)} without"
                           if figure else "")
                for m, x in scope["missing"].items()]
    return out


def _author_lines(authors):
    """Who wrote the cited pages, when a foil's pages are among them."""
    if not authors["foil"]:
        return []
    n = authors["with_sources"]
    out = ["", "##### Who wrote the sources", "",
           f"Of the answers citing sources: owned pages in {_share(authors['owned'], n)}, a foil's pages in "
           f"{_share(authors['foil'], n)}, third-party pages in {_share(authors['third'], n)}."]
    if authors["foil_pages"]:
        out.append("Foil pages cited most: " + "; ".join(
            f"{p['page']} ({p['foil']}, {_n_answers(p['answers'])})"
            for p in authors["foil_pages"]))
    return out


def _fmt(value, lang):
    """A figure as the report writes it and `check` reads it: one decimal, the report
    language's separator."""
    return "none" if value is None else fmt_decimal(value, lang)


def _cell_line(c, lang):
    p = c["presence"]
    rate = f" ({fmt_percent(p['rate'])})" if p["rate"] is not None else ""
    return (f"mean {_fmt(c['mean'], lang)} | figure {'yes' if c['figure'] else 'no'} | judged {c['judged']} of "
            f"{c['expected']} | bands 1-2:{c['bands']['1-2']} 3:{c['bands']['3']} 4-5:{c['bands']['4-5']} | "
            f"subject named in {p['named']} of {_n_answers(p['given'])}{rate}, mean position {_fmt(p['position'], lang)}"
            + (f", resting on {c['readings']} readings of {_n_answers(p['given'])}" if c["readings"] < p["given"] else ""))


def _material(proj, dims, block, responses, runs, names, reader, lang):
    def name(model):
        info = names.get(model)
        return f"{info['name']} ({model})" if info else model

    out = [f"## Project {proj['name']}", "",
           "Each answer is between ~~~~ lines, exactly as Sentl returned it.",
           f"Runs: {', '.join(str(r['run_id']) for r in runs)}",
           f"Project: {_cell_line(block['total'], lang)}", ""]
    for m, c in block["by_model"].items():
        out.append(f"- {name(m)}: {_cell_line(c, lang)}")
    for d in dims:
        e = block["dimensions"][d["key"]]
        out += ["", f"### Dimension {d['name']}", "", f"Total: {_cell_line(e['total'], lang)}"]
        out += [f"- {name(m)}: {_cell_line(c, lang)}" for m, c in e["by_model"].items()]
        doms = e["total"]["domains"]
        out.append("Domains: " + (", ".join(f"{k} ({v})" for k, v in doms.items()) or "none"))
        out += _author_lines(e["total"]["authors"])
        if e["total"]["unstable_pairs"]:
            out.append("Unstable pairs: " + ", ".join(f"{u['question']} / {name(u['model'])}"
                                                      for u in e["total"]["unstable_pairs"]))
        for q in d["questions"]:
            names_subject = "yes" if reader.position(q["text"]) else "no"
            out += ["", f"#### Question: {q['text']}", f"names the subject: {names_subject}",
                    f"{_cell_line(e['questions'][q['key']]['total'], lang)}"]
            out += _question_lines(e["questions"][q["key"]], name, lang)
            for r in responses:
                if r["question"] != q["key"]:
                    continue
                score = "not judged" if r["score"] is None else f"score {r['score']}"
                out += ["", f"**{name(r['model'])}**, {score}, sources: "
                        + (", ".join(s["domain"] for s in r["sources"]) or "none"), "",
                        "~~~~", r["answer"] if r["answer"] is not None else "(no answer)", "~~~~"]
    return out + [""]


def _metric_line(kind, m, lang, halves=False):
    label = "share stating a current term" if kind == "current_share" else kind
    if m is None:
        return f"{label}: not compared"
    sign = "-" if m["delta"] < 0 else "+"
    if kind in ("presence", "current_share"):
        shown = {k: fmt_percent(m[k]) for k in ("now", "previous")}
        lo, hi = fmt_percent(m["range"][0]), fmt_percent(m["range"][1])
        delta = f"{sign}{fmt_percent(abs(m['delta']))[:-1]} points"
    else:
        shown = {k: _fmt(m[k], lang) for k in ("now", "previous")}
        lo, hi, delta = _fmt(m["range"][0], lang), _fmt(m["range"][1], lang), sign + _fmt(abs(m["delta"]), lang)
    called = "CHANGE CALLED" if m["changed"] else "unchanged"
    if halves:
        return f"{label}: second half {shown['now']}, first half {shown['previous']}, delta {delta}: {called}"
    return (f"{label}: now {shown['now']}, previous {shown['previous']}, delta {delta}, range {lo} to {hi} over "
            f"{m['periods']} earlier period(s): " + ("CHANGE CALLED" if m["changed"] else "unchanged"))


def episodes_behind(episodes, measure, delta, later_from):
    """The episodes of a measure that can explain a move of `delta`: on the side of the range
    the move goes to, and running in the later side of the comparison, which starts at the time
    `later_from` (an episode whose last run started before it belongs to the earlier side)."""
    side = "above" if delta > 0 else "below"
    start = parse_time(later_from)
    return [e for e in episodes or [] if e["measure"] == measure and e["side"] == side
            and parse_time(e["last_at"]) >= start]


def _episode_notes(scope, measure, text, delta, later_from):
    """The episodes of a question's measure in the whole period, beside a change they explain."""
    label = "mean score" if measure == "mean" else "share of the answers stating a current term"
    return [f"  - episode behind this change, «{text}»: {label} {e['side']} the range from {e['first']} to {e['last']}, "
            f"{e['runs']} runs; state its first date beside the change"
            for e in episodes_behind(scope.get("episodes"), measure, delta, later_from)]


def _changes_material(study, period, versions, names, answer_of):
    def name(model):
        return public_name(model, names)

    lang = study.get("report_language") or "en"
    c = period["comparison"]
    halves = c.get("halves")
    write = ("Write the changes called, the verdict changes with their two answers, and the domains new or lost; the "
             "rest is unchanged. Where an episode is listed beside a change called, state its first date in the same "
             "sentence.")
    before, after = ("in the first half", "in the second half") if halves else ("in the previous period", "in this one")
    earlier_side = "the first half" if halves else "the previous period"
    later_from = halves["split"] if halves else period["from"]

    def metric(kind, m):
        return _metric_line(kind, m, lang, bool(halves))
    if halves:
        first, second = halves["first"], halves["second"]
        counts = " ".join(
            f"{p['name']}: {_n_runs(first['projects'].get(p['key'], {}).get('runs', 0))} and "
            f"{_n_answers(first['projects'].get(p['key'], {}).get('answers', 0))} in the first half, "
            f"{_n_runs(second['projects'].get(p['key'], {}).get('runs', 0))} and "
            f"{second['projects'].get(p['key'], {}).get('answers', 0)} in the second."
            for p in study["projects"] if p["key"] in first["projects"] or p["key"] in second["projects"])
        out = ["## Changes between the two halves of the period", "",
               f"There is no earlier period, so the second half of the period, runs started {second['from'][:10]} to "
               f"{second['to'][:10]}, is compared with the first half, runs started {first['from'][:10]} to "
               f"{first['to'][:10]}; the halves are split at {halves['split'][:16].replace('T', ' ')} UTC. " + counts,
               "A change is called as with a single earlier period: when the value moves at least 0.5 points "
               "(presence and the share stating a current term: 20 points). " + write + " The report's line naming "
               "the two halves and the design lines below the marker are written by method: keep them.", ""]
    else:
        out = ["## Changes since the previous period", ""]
        if c["previous"] is None:
            return out + ["There is no earlier period: the report's changes section says this is the first "
                          "measurement.", ""]
        pp = c["previous_period"]
        out += [f"Compared with the period of {c['previous']}, runs started {pp['from']} to {pp['to']}"
                + (", rebuilt from the project's earlier runs" if pp["rebuilt"] else "")
                + f". The range is made of the earlier periods {', '.join(c['range_of'])}.",
                "A change is called when the value lies outside the range and moves at least 0.3 points from the "
                "previous period (presence and the share stating a current term: 10 points); 0.5 and 20 points with a "
                "single earlier period. " + write + " The report's design lines below the marker are written by "
                "method: keep them.", ""]
    # Names and wordings as the period asked them; an earlier period's from the versions. Two
    # projects may share a dimension key, and so a question key: both are read with the project.
    dims = {(key, d["key"]): d for key, asked in period["asked"].items() for d in asked}
    texts = {(key, q["key"]): q["text"] for (key, _), d in dims.items() for q in d["questions"]}
    for key, vs in versions.items():
        for d in (d for v in reversed(vs) for d in v["dimensions"]):
            dims.setdefault((key, d["key"]), d)
            texts.update({(key, q["key"]): q["text"] for q in d["questions"] if (key, q["key"]) not in texts})
    projects = {p["key"]: p["name"] for p in study["projects"]}
    entries = dimension_entries(c)
    shared_keys = Counter(dkey for _, dkey in entries)
    shared_names = Counter(dims[e]["name"] for e in entries)

    def dim_name(key, dkey):
        """The dimension's name, with its project's when another project's dimension shares the key or the name."""
        found = dims[(key, dkey)]["name"]
        return f"{found} ({projects.get(key, key)})" if shared_keys[dkey] > 1 or shared_names[found] > 1 else found
    for key, pe in c.get("projects", {}).items():
        out += [f"### Project {projects.get(key, key)}: compared on the dimensions "
                + ", ".join(dims[(key, d)]["name"] for d in pe["dimensions"]), metric("mean", pe["mean"]), ""]
    for (key, dkey), e in entries.items():
        status = {"compared": "compared", "new": "new: no earlier figure", "no_figure": "not compared: no figure",
                  "new_baseline": f"not compared: no question comparable with {earlier_side}"}[e["status"]]
        out += [f"### Dimension {dim_name(key, dkey)}: {status}", ""]
        scopes = period["projects"].get(key, {}).get("dimensions", {}).get(dkey, {}).get("questions", {})
        if e["status"] == "compared":
            out += [f"Compared on the answers of {', '.join(name(m) for m in e['models'])} to "
                    + "; ".join(f"«{texts[(key, q)]}»" for q in e["compared_questions"]),
                    metric("mean", e["mean"]), metric("presence", e["presence"])]
        dimension_moved = (e.get("mean") or {}).get("changed") and e["mean"]["delta"]
        for q, qe in e.get("questions", {}).items():
            if qe["status"] == "compared":
                out.append(f"- «{texts[(key, q)]}»: {metric('mean', qe['mean'])}; {metric('presence', qe['presence'])}"
                           + (f"; {metric('current_share', qe['current_share'])}" if qe.get("current_share") else ""))
                # An episode is noted once, under its question, for the question's change or its dimension's.
                for measure in ("mean", "current_share"):
                    own = qe.get(measure) or {}
                    delta = own["delta"] if own.get("changed") else \
                        dimension_moved if measure == "mean" and q in e["compared_questions"] else None
                    if delta:
                        out += _episode_notes(scopes.get(q, {}), measure, texts[(key, q)], delta, later_from)
            else:
                out.append(f"- «{texts[(key, q)]}»: {qe['status'].replace('_', ' ')}"
                           + (f" ({qe['reason']})" if qe.get("reason") else ""))
        out.append("")
    out += ["### Verdict changes", ""]
    for v in c["verdict_changes"] or []:
        out.append(f"- {dim_name(v['project'], v['dimension'])}, «{texts[(v['project'], v['question'])]}», "
                   f"{name(v['model'])}: "
                   f"{v['from']} (mean {_fmt(v['previous_mean'], lang)}) {before}, {v['to']} "
                   f"(mean {_fmt(v['mean'], lang)}) {after}.")
        labels = ("First half", "Second half") if halves else ("Previous period", "This period")
        for label, ref in zip(labels, (v["previous_answer"], v["answer"])):
            r = answer_of(v["project"], ref)
            out += ["", f"{label}, score {r['score']}, sources: " + (", ".join(s["domain"] for s in r["sources"]) or "none"),
                    "", "~~~~", r["answer"], "~~~~"]
        out.append("")
    if not c["verdict_changes"]:
        out += ["None.", ""]
    out += ["### Domains", ""]
    for kind, label in (("new", "New"), ("lost", "Lost")):
        items = [f"{d['domain']} in {dim_name(d['project'], d['dimension'])} ({_n_answers(d['answers'])}"
                 + (f" {before}" if kind == "lost" else "") + (", owned" if d["owned"] else "") + ")"
                 for d in c["domains"][kind]]
        out.append(f"{label}: " + ("; ".join(items) or "none"))
    if c.get("presence_sources"):
        out += ["### Presence changes", ""]
        for entry in c["presence_sources"]:
            parts = []
            if entry["new"]:
                parts.append("cited by the answers naming the subject now and by no answer before: " + ", ".join(
                    f"{d['domain']} ({_n_answers(d['answers'])})" for d in entry["new"]))
            if entry["lost"]:
                parts.append("cited by the answers naming the subject before and by no answer now: " + ", ".join(
                    f"{d['domain']} ({_n_answers(d['answers'])} {before})" for d in entry["lost"]))
            key = entry["project"]
            out.append(f"- «{texts[(key, entry['question'])]}» ({dim_name(key, entry['dimension'])}): " + "; ".join(parts))
        out.append("")
    out += ["", "### Design changes", ""]
    for d in c["design_changes"]:
        kind = d["change"].replace("_", " ")
        if d["change"] == "models":
            listed = {k: ", ".join(name(m) for m in d[k]) or "none" for k in ("added", "removed", "basis")}
            out.append(f"- models: added {listed['added']}; removed {listed['removed']}; "
                       f"compared on {listed['basis']}")
        elif "name" in d:
            out.append(f"- {kind}: {d['name']}")
        else:
            out.append(f"- {kind}: «{d.get('text') or d['previous_text']}»"
                       + (f", earlier wording «{d['previous_text']}»" if d.get("text") and d.get("previous_text") else "")
                       + (f", from {d['since']}" if d.get("since") else ""))
    if not c["design_changes"]:
        out.append("None.")
    return out + [""]

