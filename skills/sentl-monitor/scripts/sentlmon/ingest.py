"""`ingest`: turn a saved get-run-results-tool response into a run snapshot."""

from collections import Counter, defaultdict

from . import schema
from .common import (FINAL, Refused, Study, domain_of, load_json, match_key, mean, now_iso, parse_time,
                     write_gz, write_json)


class NotFinal(Exception):
    """A run whose status is not final; exit code 3."""


def candidates(versions, started_at):
    """The versions a run is matched against, the one in force first. A detected version
    is in force from the end of its window; a run started inside the window is matched
    against it and the version before it, since the edit happened somewhere in between.
    Empty when the run predates every recorded version (an adopted project's history)."""
    start = parse_time(started_at)
    for i in range(len(versions) - 1, -1, -1):
        v = versions[i]
        if parse_time(v["recorded_at"]) <= start:
            return [v]
        if v.get("window") and i and parse_time(v["window"]["from"]) <= start:
            return [v, versions[i - 1]]
    return []


def _question_map(version):
    out = {}
    for d in version["dimensions"]:
        for q in d["questions"]:
            out[(match_key(d["name"]), match_key(q["text"]))] = (d["key"], q["key"])
    return out


def _id_map(version):
    return {q["id"]: (d["key"], q["key"]) for d in version["dimensions"] for q in d["questions"]}


def _asked(r):
    return match_key(r.get("dimension")), match_key(r.get("question"))


def _rounds(pairs):
    return max(Counter(pairs).values(), default=1)


def _fit(version, responses):
    """How well a version explains a run: its models, its rounds, then how few questions one
    of them asks and the other does not. A question the version holds and the run never
    asked counts against the version, so a run made before a question was added keeps the
    earlier version."""
    measured = {(match_key(d["name"]), match_key(q["text"]))
                for d in version["dimensions"] if not d["archived"] for q in d["questions"]}
    settings = version["settings"]
    return (set(settings["models"]) == {r.get("model_id") for r in responses},
            settings["rounds"] == _rounds((_asked(r), r.get("model_id")) for r in responses),
            -len(measured ^ {_asked(r) for r in responses}))


def _criteria(version):
    return {q["key"]: q["criteria_hash"] for d in version["dimensions"] for q in d["questions"]}


def _unavailable(folder):
    path = folder.path("history", "unavailable.json")
    data = load_json(path) if path.exists() else {"schema": "sentl-monitor/unavailable@1", "runs": []}
    return path, data


def record_unavailable(root, key, run_id, reason):
    folder = Study(root)
    folder.project(key)
    path, data = _unavailable(folder)
    when = now_iso()
    for entry in data["runs"]:
        if entry["project"] == key and entry["run_id"] == run_id:
            entry.update(reason=reason, last_tried=when, attempts=entry["attempts"] + 1)
            break
    else:
        data["runs"].append({"project": key, "run_id": run_id, "reason": reason,
                             "first_tried": when, "last_tried": when, "attempts": 1})
    write_json(path, data)
    return (f"Run {run_id} of {key} recorded as unavailable ({reason}). "
            "It is requested again at the next invocation and blocks nothing.")


def _clear_unavailable(folder, key, run_id):
    path, data = _unavailable(folder)
    kept = [e for e in data["runs"] if not (e["project"] == key and e["run_id"] == run_id)]
    if path.exists() and len(kept) != len(data["runs"]):
        data["runs"] = kept
        write_json(path, data)


def run_score(responses):
    """Mean of the dimension means of the judged, matched answers: Sentl's definition."""
    by_dim = defaultdict(list)
    for r in responses:
        if r["match"] != "unmatched" and r["score"] is not None:
            by_dim[r["dimension"]].append(r["score"])
    return mean([mean(v) for v in by_dim.values()])


def ingest(root, key, results_file):
    folder = Study(root)
    folder.project(key)
    run = schema.run_results(results_file)
    run_id, status = run["id"], run["status"]
    if status not in FINAL:
        raise NotFinal(f"run {run_id} has status {status!r}, not final: it is read again at the next invocation")

    target = folder.path("history", "runs", key, f"{run_id}.json.gz")
    if target.exists():
        _clear_unavailable(folder, key, run_id)
        return f"Run {run_id} already ingested; nothing changed."

    versions = folder.versions(key)
    if not versions:
        raise Refused(f"no recorded version for project {key!r}: run adopt first")
    tried = candidates(versions, run["started_at"])
    unknown = []
    if len(tried) == 2:
        later, earlier = (_fit(v, run["responses"]) for v in tried)
        if later == earlier:
            # Nothing in the run tells the two versions apart, so the rubric its answers were
            # judged under is unknown for every question whose criteria changed between them.
            before, after = _criteria(tried[1]), _criteria(tried[0])
            unknown = sorted(k for k in after if k in before and before[k] != after[k])
        elif earlier > later:
            tried.reverse()
    version = tried[0] if tried else None
    maps = [(_question_map(v), "version" if version is not None and v is not version else "exact", _id_map(v))
            for v in (tried or versions[:1])]

    responses, unmatched = [], []
    for r in run["responses"]:
        # Sentl's question_id names the question whatever its text says now; the text is the fallback.
        found, how = next(((ids[r["question_id"]], "id") for _, _, ids in maps if r.get("question_id") in ids),
                          next(((qmap[_asked(r)], how) for qmap, how, _ in maps if _asked(r) in qmap), (None, "unmatched")))
        score = r.get("judge_score")
        entry = {
            "response_id": r.get("id"), "question": found[1] if found else None,
            "dimension": found[0] if found else None, "model": r.get("model_id"),
            "score": score, "sentiment": r.get("sentiment") if score is not None else None,
            "answer": r.get("answer"),
            "sources": [{"url": s.get("url"), "title": s.get("title"), "domain": domain_of(s.get("url"), s.get("title"))}
                        for s in r.get("sources") or []],
            "match": how,
        }
        if not found:
            entry["asked"] = {"dimension": r.get("dimension"), "question": r.get("question")}
            unmatched.append(entry)
        responses.append(entry)

    matched = [r for r in responses if r["match"] != "unmatched"]
    if version is not None:
        measured = [d for d in version["dimensions"] if not d["archived"]]
        plan = {"questions": [q["key"] for d in measured for q in d["questions"]],
                "models": list(version["settings"]["models"]), "rounds": version["settings"]["rounds"]}
        expected = len(plan["questions"]) * len(plan["models"]) * plan["rounds"]
    else:
        # No configuration is known for the run (gap G2): what it asked is what it answered,
        # and a question asked in a wording no version holds still counts as asked.
        asked = {_asked(r) for r in run["responses"]}
        plan = {"questions": sorted({r["question"] for r in matched}),
                "models": sorted({r["model"] for r in responses}),
                "rounds": _rounds((_asked(r), r.get("model_id")) for r in run["responses"])}
        expected = len(asked) * len(plan["models"]) * plan["rounds"]
    judged = sum(1 for r in matched if r["score"] is not None)

    snapshot = {
        "schema": "sentl-monitor/run@1", "run_id": run_id, "project": key, "status": status,
        "trigger": run.get("trigger"), "started_at": run.get("started_at"), "finished_at": run.get("finished_at"),
        "sentl_score": run.get("reputation_score"), "error": run.get("error"),
        "version": version["version"] if version else None, "ingested_at": now_iso(),
        "plan": plan, "expected": expected, "received": len(responses), "judged": judged,
        "criteria_unknown": unknown, "responses": responses,
    }
    write_gz(target, snapshot)
    _clear_unavailable(folder, key, run_id)

    lines = [f"Ingested run {run_id} of {key} ({status}, started {run.get('started_at')}): "
             f"{len(responses)} received, {judged} judged of {expected} expected, {len(unmatched)} unmatched."]
    if unmatched:
        lines.append("Unmatched responses, kept and excluded from every figure (tell the operator):")
        lines += [f"  {u['asked']['dimension']}: {u['asked']['question']} ({u['model']})" for u in unmatched]
    own, sentl = run_score(responses), run.get("reputation_score")
    if own is not None and sentl is not None and abs(own - sentl) > 0.05:
        lines.append(f"Sentl's run score {sentl} differs from the mean of dimension means computed here, "
                     f"{own:.2f}: tell the operator.")
    return "\n".join(lines)
