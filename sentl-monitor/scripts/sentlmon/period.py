"""`period`: the runs of one report period pooled, compared with the periods before it,
and the material the report is written from."""

import calendar
import datetime as dt
from collections import Counter, defaultdict

from .common import (FIGURE_FLOOR, RUN_FLOOR, Refused, Study, fmt_decimal, fmt_percent, fold, first_mention,
                     is_owned, load_json, load_mcp, mean, parse_time, public_name, write_json, write_text)
from .compare import K, compare


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

    def position(self, answer):
        """None when the subject is not named; else 1 + the foils named before it."""
        if answer is None:
            return None
        text = fold(answer)
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
    }


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
              "starts": {}, "dropped": {}, "asked": {}, "projects": {}}
    starts = []
    for proj in study["projects"]:
        key = proj["key"]
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
        responses = [r for run in runs for r in run["responses"] if r["match"] != "unmatched"]
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
            block["dimensions"][d["key"]] = entry
            asked.append({"key": d["key"], "name": d["name"],
                          "questions": [{"key": q["key"], "text": q["text"]} for q in questions]})
        period["asked"][key] = asked
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


def _left_out(period, where):
    return [f"Left out of {k}{where}: run {e['run_id']}, {e['reason']} (tell the operator)."
            for k, ex in period["excluded"].items() for e in ex]


def build(root, date, models_file=None):
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


def _fmt(value, lang):
    """A figure as the report writes it and `check` reads it: one decimal, the report
    language's separator."""
    return "none" if value is None else fmt_decimal(value, lang)


def _cell_line(c, lang):
    p = c["presence"]
    rate = f" ({fmt_percent(p['rate'])})" if p["rate"] is not None else ""
    return (f"mean {_fmt(c['mean'], lang)} | figure {'yes' if c['figure'] else 'no'} | judged {c['judged']} of "
            f"{c['expected']} | bands 1-2:{c['bands']['1-2']} 3:{c['bands']['3']} 4-5:{c['bands']['4-5']} | "
            f"subject named in {p['named']} of {p['given']} answers{rate}, mean position {_fmt(p['position'], lang)}")


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
        if e["total"]["unstable_pairs"]:
            out.append("Unstable pairs: " + ", ".join(f"{u['question']} / {name(u['model'])}"
                                                      for u in e["total"]["unstable_pairs"]))
        for q in d["questions"]:
            names_subject = "yes" if reader.position(q["text"]) else "no"
            out += ["", f"#### Question: {q['text']}", f"names the subject: {names_subject}",
                    f"{_cell_line(e['questions'][q['key']]['total'], lang)}"]
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
