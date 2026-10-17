"""`period`: the runs of one report period pooled, compared with the periods before it,
and the material the report is written from."""

import calendar
import datetime as dt
from collections import Counter, defaultdict

from .common import (FIGURE_FLOOR, RUN_FLOOR, Refused, Study, fmt_decimal, fmt_percent, first_mention, folded,
                     is_owned, load_json, load_mcp, mean, parse_time, public_name, write_json, write_text)
from .compare import K, compare
from .insights import classify, episodes, fact_cell, fact_terms, page_of, readings, reset, says_missing, top_sources


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


def select_runs(runs, start=None, end=None, after=None):
    """The runs started in [start, end) and after `after`, by start time, and those left out
    under the judged floor, with the reason."""
    chosen, excluded = [], []
    for r in sorted(runs, key=lambda r: parse_time(r["started_at"])):
        at = parse_time(r["started_at"])
        if (start and at < start) or (end and at >= end) or (after and at <= after):
            continue
        share = r["judged"] / r["expected"] if r["expected"] else 0.0
        if share < RUN_FLOOR:
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
    period = {"schema": "sentl-monitor/period@1", "date": date, "runs": {}, "excluded": {}, "versions": {},
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


def _left_out(period, where):
    return [f"Left out of {k}{where}: run {e['run_id']}, {e['reason']} (tell the operator)."
            for k, ex in period["excluded"].items() for e in ex]


def build(root, date, models_file=None):
    reset()
    folder = Study(root)
    study = folder.study
    every = study.get("report_every")
    if every not in ("weekly", "monthly"):
        raise Refused("report_every is not set in study.json: ask the operator whether a report covers a week or a "
                      "month, write it, and run period again")
    reader = Reader(study)
    names = load_mcp(models_file, "researcher_models") if models_file else {}
    keys = [p["key"] for p in study["projects"]]
    runs = {k: folder.runs(k) for k in keys}
    versions = {k: folder.versions(k) for k in keys}
    reports = [e for e in folder.reports() if e["date"] < date]
    bounds = intervals(date, every)
    periods_dir = folder.path("history", "periods")

    def pick(window):
        out = {}
        for k in keys:
            chosen, excluded = select_runs(runs[k], **window(k))
            kept, dropped = latest_criteria(chosen, versions[k])
            out[k] = (kept, excluded, dropped)
        return out

    if reports:
        last = reports[-1]
        started = {k: {r["run_id"]: parse_time(r["started_at"]) for r in runs[k]} for k in keys}
        cut = {k: max((started[k][i] for i in last["runs"].get(k, []) if i in started[k]),
                      default=parse_time(last["period"]["to"])) for k in keys}
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

    if not reports:
        # The periods before a first report are rebuilt each time it is built, so none is left over.
        for path in periods_dir.glob("*.json"):
            if path.stem < date and load_json(path).get("rebuilt"):
                path.unlink()
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
            lines.append(f"There is no earlier period: no completed run started before {bounds[0][0].date()} was ingested, "
                         "so this report is the first measurement (tell the operator).")

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

    current["comparison"] = compare(study, current, prevs, versions, answers, reader.owned)
    earlier = {k: _runs_of(prevs[0], k, run_of) if prevs else [] for k in keys}
    now = {k: [(run, ()) for run in chosen[k][0]] for k in keys}
    _add_episodes(study, current, earlier, now, versions)
    current["comparison"]["presence_sources"] = _presence_sources(current, earlier, now, reader)
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
    if c["previous"]:
        called = sum(bool((e.get(m) or {}).get("changed")) for e in c["dimensions"].values() for m in ("mean", "presence"))
        lines.append(f"Compared with the period of {c['previous']}: {called} dimension change(s) called, "
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
                        out.append((run["started_at"][:10], (mean([r["score"] for r in rs]), share)))
                    return out
                past, current = values(before), values(now[key])
                found = [{"measure": measure, **e} for i, measure in enumerate(("mean", "current_share"))
                         for e in episodes([v[i] for _, v in past], [(d, v[i]) for d, v in current])]
                if found:
                    scope["episodes"] = found


def _presence_sources(period, earlier, now, reader):
    """For each question whose presence changed, the domains cited by the answers naming the
    subject in one period and by no answer to the question in the other."""
    out = []
    for dkey, e in period["comparison"]["dimensions"].items():
        for q, qe in (e.get("questions") or {}).items():
            if qe.get("status") != "compared" or not (qe.get("presence") or {}).get("changed"):
                continue
            key, models = e["project"], set(e["models"])
            this = [r for r in _answers_to(now[key], q, models) if r["answer"] is not None]
            last = [r for r in _answers_to(earlier[key], q, models) if r["answer"] is not None]

            def moved(here, there):
                cited = {d for r in there for d in _domains(r)}
                naming = Counter(d for r in here if reader.position(r["answer"]) is not None for d in _domains(r))
                return [{"domain": d, "answers": n} for d, n in sorted(naming.items(), key=lambda kv: (-kv[1], kv[0]))
                        if d not in cited]
            new, lost = moved(this, last), moved(last, this)
            if new or lost:
                out.append({"project": key, "dimension": dkey, "question": q, "new": new, "lost": lost})
    return out


def _share(n, m, noun=""):
    return f"{n} of {m}" + (f" {noun}" if noun else "") + (f" ({fmt_percent(n / m)})" if m else "")


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
        out += [f"- {r['date']}: subject named in {_share(r['named'], r['given'], 'answers')}"
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
            if mean_score and not figure:
                out.append(f"- {label}, {e['runs']} runs {e['side']} the range of the {e['earlier']} runs before, "
                           f"from {e['first']} to {e['last']}; {ending}")
                continue
            out.append(f"- {label}, {e['runs']} runs {e['side']} the range {shown(e['range'][0])} to "
                       f"{shown(e['range'][1])} of the {e['earlier']} runs before, from {e['first']} to {e['last']}: "
                       + "; ".join(shown(v) for v in e["values"]) + f"; {ending}")
    if scope.get("missing"):
        out += ["", "##### Missing evidence", ""]
        out += [f"- {name(m)}: {_share(x['answers'], x['given'], 'answers')} say no source of the kind asked for was "
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
            f"{p['page']} ({p['foil']}, {p['answers']} answer{'s' if p['answers'] != 1 else ''})"
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
            f"subject named in {p['named']} of {p['given']} answers{rate}, mean position {_fmt(p['position'], lang)}"
            + (f", resting on {c['readings']} readings of {p['given']} answers" if c["readings"] < p["given"] else ""))


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


def _metric_line(kind, m, lang):
    if m is None:
        return f"{kind}: not compared"
    sign = "-" if m["delta"] < 0 else "+"
    if kind == "presence":
        shown = {k: fmt_percent(m[k]) for k in ("now", "previous")}
        lo, hi = fmt_percent(m["range"][0]), fmt_percent(m["range"][1])
        delta = f"{sign}{fmt_percent(abs(m['delta']))[:-1]} points"
    else:
        shown = {k: _fmt(m[k], lang) for k in ("now", "previous")}
        lo, hi, delta = _fmt(m["range"][0], lang), _fmt(m["range"][1], lang), sign + _fmt(abs(m["delta"]), lang)
    return (f"{kind}: now {shown['now']}, previous {shown['previous']}, delta {delta}, range {lo} to {hi} over "
            f"{m['periods']} earlier period(s): " + ("CHANGE CALLED" if m["changed"] else "unchanged"))


def _changes_material(study, period, versions, names, answer_of):
    def name(model):
        return public_name(model, names)

    lang = study.get("report_language") or "en"
    c = period["comparison"]
    out = ["## Changes since the previous period", ""]
    if c["previous"] is None:
        return out + ["There is no earlier period: the report's changes section says this is the first measurement.", ""]
    pp = c["previous_period"]
    out += [f"Compared with the period of {c['previous']}, runs started {pp['from']} to {pp['to']}"
            + (", rebuilt from the project's earlier runs" if pp["rebuilt"] else "")
            + f". The range is made of the earlier periods {', '.join(c['range_of'])}.",
            "A change is called when the value lies outside the range and moves at least 0.3 points from the previous "
            "period (presence: 10 points); 0.5 and 20 points with a single earlier period. Write the changes called, "
            "the verdict changes with their two answers, and the domains new or lost; the rest is unchanged. "
            "The report's design lines below the marker are written by method: keep them.", ""]
    # Names and wordings as the period asked them; an earlier period's from the versions.
    dims = {d["key"]: d for asked in period["asked"].values() for d in asked}
    texts = {q["key"]: q["text"] for d in dims.values() for q in d["questions"]}
    for v in (v for vs in versions.values() for v in reversed(vs)):
        for d in v["dimensions"]:
            dims.setdefault(d["key"], d)
            texts.update({q["key"]: q["text"] for q in d["questions"] if q["key"] not in texts})
    for dkey, e in c["dimensions"].items():
        status = {"compared": "compared", "new": "new: no earlier figure", "no_figure": "not compared: no figure",
                  "new_baseline": "not compared: no question comparable with the previous period"}[e["status"]]
        out += [f"### Dimension {dims[dkey]['name']}: {status}", ""]
        if e["status"] == "compared":
            out += [f"Compared on the answers of {', '.join(name(m) for m in e['models'])} to "
                    + "; ".join(f"«{texts[q]}»" for q in e["compared_questions"]),
                    _metric_line("mean", e["mean"], lang), _metric_line("presence", e["presence"], lang)]
        for q, qe in e.get("questions", {}).items():
            if qe["status"] == "compared":
                out.append(f"- «{texts[q]}»: {_metric_line('mean', qe['mean'], lang)}; "
                           f"{_metric_line('presence', qe['presence'], lang)}")
            else:
                out.append(f"- «{texts[q]}»: {qe['status'].replace('_', ' ')}" + (f" ({qe['reason']})" if qe.get("reason") else ""))
        out.append("")
    out += ["### Verdict changes", ""]
    for v in c["verdict_changes"] or []:
        out.append(f"- {dims[v['dimension']]['name']}, «{texts[v['question']]}», {name(v['model'])}: "
                   f"{v['from']} (mean {_fmt(v['previous_mean'], lang)}) in the previous period, {v['to']} "
                   f"(mean {_fmt(v['mean'], lang)}) in this one.")
        for label, ref in (("Previous period", v["previous_answer"]), ("This period", v["answer"])):
            r = answer_of(v["project"], ref)
            out += ["", f"{label}, score {r['score']}, sources: " + (", ".join(s["domain"] for s in r["sources"]) or "none"),
                    "", "~~~~", r["answer"], "~~~~"]
        out.append("")
    if not c["verdict_changes"]:
        out += ["None.", ""]
    out += ["### Domains", ""]
    for kind, label in (("new", "New"), ("lost", "Lost")):
        items = [f"{d['domain']} in {dims[d['dimension']]['name']} ({d['answers']} answers"
                 + (" in the previous period" if kind == "lost" else "") + (", owned" if d["owned"] else "") + ")"
                 for d in c["domains"][kind]]
        out.append(f"{label}: " + ("; ".join(items) or "none"))
    if c.get("presence_sources"):
        out += ["### Presence changes", ""]
        for entry in c["presence_sources"]:
            parts = []
            if entry["new"]:
                parts.append("cited by the answers naming the subject now and by no answer before: " + ", ".join(
                    f"{d['domain']} ({d['answers']} answers)" for d in entry["new"]))
            if entry["lost"]:
                parts.append("cited by the answers naming the subject before and by no answer now: " + ", ".join(
                    f"{d['domain']} ({d['answers']} answers in the previous period)" for d in entry["lost"]))
            out.append(f"- «{texts[entry['question']]}» ({dims[entry['dimension']]['name']}): " + "; ".join(parts))
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
