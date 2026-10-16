"""`ingest`: turn a saved get-run-results-tool response into a run snapshot."""

from collections import defaultdict

from .common import (FINAL, Refused, Study, domain_of, load_json, load_mcp, match_key, mean, now_iso,
                     parse_time, write_gz, write_json)


class NotFinal(Exception):
    """A run whose status is not final; exit code 3."""


def version_in_force(versions, started_at):
    """The latest version recorded before the run started, or None when the run
    predates every recorded version (a run read from an adopted project's history)."""
    start = parse_time(started_at)
    current = None
    for v in versions:
        if parse_time(v["recorded_at"]) <= start:
            current = v
    return current


def _question_map(version):
    out = {}
    for d in version["dimensions"]:
        for q in d["questions"]:
            out[(match_key(d["name"]), match_key(q["text"]))] = (d["key"], q["key"])
    return out


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
    run = load_mcp(results_file, "run")
    if "responses" not in run or "id" not in run:
        raise Refused(f"{results_file} is not a get-run-results-tool response")
    run_id, status = run["id"], run.get("status")
    if status not in FINAL:
        raise NotFinal(f"run {run_id} has status {status!r}, not final: it is read again at the next invocation")

    target = folder.path("history", "runs", key, f"{run_id}.json.gz")
    if target.exists():
        _clear_unavailable(folder, key, run_id)
        return f"Run {run_id} already ingested; nothing changed."

    versions = folder.versions(key)
    if not versions:
        raise Refused(f"no recorded version for project {key}: run adopt first")
    version = version_in_force(versions, run["started_at"])
    qmap = _question_map(version or versions[0])

    responses, unmatched = [], []
    for r in run["responses"]:
        found = qmap.get((match_key(r.get("dimension")), match_key(r.get("question"))))
        score = r.get("judge_score")
        entry = {
            "response_id": r.get("id"), "question": found[1] if found else None,
            "dimension": found[0] if found else None, "model": r.get("model_id"),
            "score": score, "sentiment": r.get("sentiment") if score is not None else None,
            "answer": r.get("answer"),
            "sources": [{"url": s.get("url"), "title": s.get("title"), "domain": domain_of(s.get("url"), s.get("title"))}
                        for s in r.get("sources") or []],
            "match": "exact" if found else "unmatched",
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
    else:
        pairs = defaultdict(int)
        for r in matched:
            pairs[(r["question"], r["model"])] += 1
        plan = {"questions": sorted({r["question"] for r in matched}),
                "models": sorted({r["model"] for r in matched}),
                "rounds": max(pairs.values(), default=1)}
    expected = len(plan["questions"]) * len(plan["models"]) * plan["rounds"]
    judged = sum(1 for r in matched if r["score"] is not None)

    snapshot = {
        "schema": "sentl-monitor/run@1", "run_id": run_id, "project": key, "status": status,
        "trigger": run.get("trigger"), "started_at": run.get("started_at"), "finished_at": run.get("finished_at"),
        "sentl_score": run.get("reputation_score"), "error": run.get("error"),
        "version": version["version"] if version else None, "ingested_at": now_iso(),
        "plan": plan, "expected": expected, "received": len(responses), "judged": judged,
        "responses": responses,
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
