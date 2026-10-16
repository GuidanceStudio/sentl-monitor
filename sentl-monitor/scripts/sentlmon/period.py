"""`period`: the metrics of one report period, and the material the findings are written from."""

from collections import Counter, defaultdict

from .common import (FIGURE_FLOOR, RUN_FLOOR, Study, fmt_percent, fold, first_mention, is_owned, load_mcp, mean,
                     public_name, write_json, write_text)


class BelowFloor(Exception):
    """No run left in the period once runs under the judged floor are left out; exit code 4."""


def select_runs(runs):
    """The runs of the period and the ones left out, with the reason.

    The period of a first report is the project's latest completed run.
    """
    if not runs:
        return [], []
    latest = max(runs, key=lambda r: r["started_at"])
    share = latest["judged"] / latest["expected"] if latest["expected"] else 0.0
    if share < RUN_FLOOR:
        return [], [{"run_id": latest["run_id"],
                     "reason": f"{fmt_percent(share)} of expected answers judged "
                               f"({latest['judged']} of {latest['expected']}), under the 90% floor"}]
    return [latest], []


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


def build(root, date, models_file=None):
    folder = Study(root)
    study = folder.study
    reader = Reader(study)
    names = (load_mcp(models_file, "researcher_models") if models_file else {})
    period = {"schema": "sentl-monitor/period@1", "date": date, "runs": {}, "excluded": {},
              "versions": {}, "projects": {},
              "comparison": {"previous": None, "range_of": [], "dimensions": {}, "verdict_changes": [],
                             "domains": {"new": [], "lost": []}, "design_changes": []}}
    material = [f"# Material for the report of {date}", ""]
    starts = []
    for proj in study["projects"]:
        key = proj["key"]
        chosen, excluded = select_runs(folder.runs(key))
        if excluded:
            period["excluded"][key] = excluded
        if not chosen:
            continue
        period["runs"][key] = [r["run_id"] for r in chosen]
        period["versions"][key] = [r["version"] for r in chosen]
        starts += [r["started_at"] for r in chosen]
        responses = [r for run in chosen for r in run["responses"] if r["match"] != "unmatched"]
        models = sorted({m for run in chosen for m in run["plan"]["models"]})
        dims = [d for d in proj["dimensions"] if not d.get("archived")]
        block = {"dimensions": {}}
        for d in dims:
            qkeys = [q["key"] for q in d["questions"]]
            entry = _scope(responses, chosen, set(qkeys), models, reader)
            entry["questions"] = {q: _scope(responses, chosen, {q}, models, reader) for q in qkeys}
            block["dimensions"][d["key"]] = entry
        all_q = {q["key"] for d in dims for q in d["questions"]}
        block.update(_scope(responses, chosen, all_q, models, reader))
        # A project's figure is the mean of its dimension figures, as Sentl scores a run.
        block["total"]["mean"] = mean([e["total"]["mean"] for e in block["dimensions"].values()])
        for m in models:
            block["by_model"][m]["mean"] = mean([e["by_model"][m]["mean"] for e in block["dimensions"].values()])
        period["projects"][key] = block
        material += _material(proj, dims, block, responses, chosen, names, reader)

    if not period["runs"]:
        reasons = [f"{k}: run {e['run_id']} left out, {e['reason']}" for k, ex in period["excluded"].items() for e in ex]
        raise BelowFloor("no run in the period" + (":\n  " + "\n  ".join(reasons) if reasons else
                                                   ": ingest a completed run first"))
    period["from"], period["to"] = min(starts), max(starts)
    period["names"] = {m: public_name(m, names) for b in period["projects"].values() for m in b["by_model"]}
    write_json(folder.path("history", "periods", f"{date}.json"), period)
    write_text(folder.path("history", "material", f"{date}.md"), "\n".join(material) + "\n")

    lines = [f"Period {date}: " + "; ".join(f"{k} runs {v}" for k, v in period["runs"].items()) + "."]
    for k, ex in period["excluded"].items():
        lines += [f"Left out of {k}: run {e['run_id']}, {e['reason']} (tell the operator)." for e in ex]
    for k, block in period["projects"].items():
        for dkey, e in block["dimensions"].items():
            if not e["total"]["figure"]:
                t = e["total"]
                lines.append(f"Dimension {dkey} of {k}: {t['judged']} of {t['expected']} answers judged, "
                             "under 80%: shown without a figure (tell the operator).")
    return "\n".join(lines)


def _fmt(value, places=2):
    return "none" if value is None else f"{value:.{places}f}"


def _cell_line(c):
    p = c["presence"]
    return (f"mean {_fmt(c['mean'])} | figure {'yes' if c['figure'] else 'no'} | judged {c['judged']} of "
            f"{c['expected']} | bands 1-2:{c['bands']['1-2']} 3:{c['bands']['3']} 4-5:{c['bands']['4-5']} | "
            f"subject named in {p['named']} of {p['given']} answers, mean position {_fmt(p['position'])}")


def _material(proj, dims, block, responses, runs, names, reader):
    def name(model):
        info = names.get(model)
        return f"{info['name']} ({model})" if info else model

    out = [f"## Project {proj['name']}", "",
           "Each answer is between ~~~~ lines, exactly as Sentl returned it.",
           f"Runs: {', '.join(str(r['run_id']) for r in runs)}",
           f"Project: {_cell_line(block['total'])}", ""]
    for m, c in block["by_model"].items():
        out.append(f"- {name(m)}: {_cell_line(c)}")
    for d in dims:
        e = block["dimensions"][d["key"]]
        out += ["", f"### Dimension {d['name']}", "", f"Total: {_cell_line(e['total'])}"]
        out += [f"- {name(m)}: {_cell_line(c)}" for m, c in e["by_model"].items()]
        doms = e["total"]["domains"]
        out.append("Domains: " + (", ".join(f"{k} ({v})" for k, v in doms.items()) or "none"))
        if e["total"]["unstable_pairs"]:
            out.append("Unstable pairs: " + ", ".join(f"{u['question']} / {name(u['model'])}"
                                                      for u in e["total"]["unstable_pairs"]))
        for q in d["questions"]:
            names_subject = "yes" if reader.position(q["text"]) else "no"
            out += ["", f"#### Question: {q['text']}", f"names the subject: {names_subject}",
                    f"{_cell_line(e['questions'][q['key']]['total'])}"]
            for r in responses:
                if r["question"] != q["key"]:
                    continue
                score = "not judged" if r["score"] is None else f"score {r['score']}"
                out += ["", f"**{name(r['model'])}**, {score}, sources: "
                        + (", ".join(s["domain"] for s in r["sources"]) or "none"), "",
                        "~~~~", r["answer"] if r["answer"] is not None else "(no answer)", "~~~~"]
    return out + [""]
