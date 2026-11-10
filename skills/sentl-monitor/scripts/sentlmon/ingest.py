"""`ingest`: turn a saved get-run-results-tool response into a run snapshot."""

from collections import Counter, defaultdict

from . import schema
from .adopt import criteria_hash
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


def _dimension_map(version):
    return {(d["id"], match_key(q["text"])): (d["key"], q["key"])
            for d in version["dimensions"] if d.get("id") is not None for q in d["questions"]}


def _asked(r):
    return match_key(r.get("dimension")), match_key(r.get("question"))


def _rounds(responses):
    """The rounds of a run: Sentl's `round`, or the answers of a question and model where it is absent."""
    marked = [r["round"] for r in responses if r.get("round")]
    return max(marked) if marked else max(Counter((_asked(r), r.get("model_id")) for r in responses).values(), default=1)


def _find(r, maps):
    """The keys of the question a response answers and how they were found. Sentl's question_id names the
    question whatever its text says now; then the text, under the dimension's name or, once it was renamed,
    under its id."""
    for _, _, ids, _ in maps:
        if r.get("question_id") in ids:
            return ids[r["question_id"]], "id"
    for qmap, how, _, _ in maps:
        if _asked(r) in qmap:
            return qmap[_asked(r)], how
    for _, _, _, dims in maps:
        if (r.get("dimension_id"), match_key(r.get("question"))) in dims:
            return dims[(r["dimension_id"], match_key(r["question"]))], "dimension"
    return None, "unmatched"


def _deleted(r):
    """What Sentl says it deleted: a null id, on a response that carries the ids."""
    return [name for name in ("question", "dimension") if f"{name}_id" in r and r[f"{name}_id"] is None]


def _fit(version, responses):
    """How well a version explains a run: its models, its rounds, then how few questions one
    of them asks and the other does not. A question the version holds and the run never
    asked counts against the version, so a run made before a question was added keeps the
    earlier version."""
    measured = {(match_key(d["name"]), match_key(q["text"]))
                for d in version["dimensions"] if not d["archived"] for q in d["questions"]}
    settings = version["settings"]
    return (set(settings["models"]) == {r.get("model_id") for r in responses},
            settings["rounds"] == _rounds(responses),
            -len(measured ^ {_asked(r) for r in responses}))


def _criteria(version):
    return {q["key"]: q["criteria_hash"] for d in version["dimensions"] for q in d["questions"]}


def _project_read(folder, key):
    """{question id: question} of the project read saved in the inbox (`project-<Sentl id>.json`, else
    `project-<key>.json`), or {} when none of this project is there or it cannot be read."""
    project_id = ((folder.binding.get("projects") or {}).get(key) or {}).get("project_id")
    for name in (f"project-{project_id}.json", f"project-{key}.json"):
        path = folder.path("inbox", name)
        if not path.exists():
            continue
        try:
            read = schema.project(path)
        except (Refused, schema.Mismatch):
            continue
        if read["id"] == project_id:
            return {q["id"]: q for d in read["dimensions"] for q in d["questions"]}
    return {}


def settle(folder, key, started_at, unknown, tried, answers):
    """{question: {"version": n, "by": how}} for the questions of `unknown` whose criteria are known after all. `tried` is
    the later version, then the earlier; `answers` is (question key, response as Sentl returned it) of the run.
    By "rubric": every answer to the question carries the rubric and instructions it was judged under, and they are one
    version's. By "updated_at": the project read says the question was last edited before the run started, with the
    later version's criteria, so the run was judged under them. Nothing else settles a question."""
    hashes = {v["version"]: _criteria(v) for v in tried}
    later = tried[0]
    ids = {q["key"]: q.get("id") for d in later["dimensions"] for q in d["questions"]}
    read, out = None, {}
    for q in unknown:
        mine = [r for k, r in answers if k == q]
        if mine and all("grading_rubric" in r for r in mine):
            judged = {criteria_hash(r.get("grading_rubric"), r.get("additional_instructions")) for r in mine}
            match = [n for n, h in hashes.items() if judged == {h.get(q)}]
            if len(match) == 1:
                out[q] = {"version": match[0], "by": "rubric"}
                continue
        read = _project_read(folder, key) if read is None else read
        asked = read.get(ids.get(q))
        if (asked and asked.get("updated_at") and parse_time(asked["updated_at"]) < parse_time(started_at)
                and criteria_hash(asked.get("grading_rubric"), asked.get("additional_instructions")) == hashes[later["version"]].get(q)):
            out[q] = {"version": later["version"], "by": "updated_at"}
    return out


def _saved_results(folder, run_id):
    """{response id: response} of the run's results saved in the inbox, or {} when they are not there."""
    path = folder.path("inbox", f"run-{run_id}.json")
    if not path.exists():
        return {}
    try:
        run = schema.run_results(path)
    except (Refused, schema.Mismatch):
        return {}
    return {r["id"]: r for r in run.get("responses") or []} if run.get("id") == run_id else {}


def resettle(folder, key, snapshot, versions):
    """A run snapshot whose questions of unknown criteria are settled again with what the inbox holds now: the run's
    saved results, whose answers may carry their rubric, and the latest project read. The file on disk is not changed."""
    unknown = snapshot.get("criteria_unknown") or []
    tried = candidates(versions, snapshot["started_at"]) if unknown else []
    if len(tried) != 2:
        return snapshot
    raw = _saved_results(folder, snapshot["run_id"])
    answers = [(e["question"], raw[e["response_id"]]) for e in snapshot["responses"] if e.get("response_id") in raw]
    found = settle(folder, key, snapshot["started_at"], unknown, tried, answers)
    if not found:
        return snapshot
    return {**snapshot, "criteria_unknown": [q for q in unknown if q not in found],
            "criteria_settled": {**(snapshot.get("criteria_settled") or {}), **found}}


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
    if status in schema.ENDED:
        detail = f" ({run['error']})" if run.get("error") else ""
        raise Refused(f"run {run_id} ended {status} with no results{detail}: nothing to ingest, it stays out of the period")
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
    maps = [(_question_map(v), "version" if version is not None and v is not version else "exact", _id_map(v),
             _dimension_map(v)) for v in (tried or versions[:1])]

    # Sentl orders the answers by id: a run read in another order gives the same snapshot.
    given = run["responses"]
    answers = sorted(given, key=lambda r: r["id"]) if any("round" in r for r in given) else given
    responses, unmatched, asked = [], [], []
    for r in answers:
        found, how = _find(r, maps)
        if found:
            asked.append((found[1], r))
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
        if "round" in r:
            entry["round"] = r["round"]
        if not found:
            entry["asked"] = {"dimension": r.get("dimension"), "question": r.get("question")}
            if _deleted(r):
                entry["asked"]["deleted"] = _deleted(r)
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
                "rounds": _rounds(run["responses"])}
        expected = len(asked) * len(plan["models"]) * plan["rounds"]
    judged = sum(1 for r in matched if r["score"] is not None)
    settled = settle(folder, key, run["started_at"], unknown, tried, asked) if unknown else {}
    unknown = [q for q in unknown if q not in settled]

    snapshot = {
        "schema": "sentl-monitor/run@1", "run_id": run_id, "project": key, "status": status,
        "trigger": run.get("trigger"), "started_at": run.get("started_at"), "finished_at": run.get("finished_at"),
        "sentl_score": run.get("reputation_score"), "error": run.get("error"),
        "version": version["version"] if version else None, "ingested_at": now_iso(),
        "plan": plan, "expected": expected, "received": len(responses), "judged": judged,
        "criteria_unknown": unknown, **({"criteria_settled": settled} if settled else {}), "responses": responses,
    }
    write_gz(target, snapshot)
    _clear_unavailable(folder, key, run_id)

    lines = [f"Ingested run {run_id} of {key} ({status}, started {run.get('started_at')}): "
             f"{len(responses)} received, {judged} judged of {expected} expected, {len(unmatched)} unmatched."]
    if unmatched:
        lines.append("Unmatched responses, kept and excluded from every figure (tell the operator):")
        lines += [f"  {u['asked']['dimension']}: {u['asked']['question']} ({u['model']})"
                  + (f", {' and '.join(u['asked']['deleted'])} deleted in Sentl" if u["asked"].get("deleted") else "")
                  for u in unmatched]
    own, sentl = run_score(responses), run.get("reputation_score")
    if own is not None and sentl is not None and abs(own - sentl) > 0.05:
        lines.append(f"Sentl's run score {sentl} differs from the mean of dimension means computed here, "
                     f"{own:.2f}: tell the operator.")
    return "\n".join(lines)
