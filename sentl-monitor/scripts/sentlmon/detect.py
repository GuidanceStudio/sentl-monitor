"""`detect`: compare a saved get-project-tool response with the latest recorded version,
and record a `detected` version when the project in Sentl differs from it."""

from .adopt import _unique, criteria_hash
from .common import Refused, Study, load_mcp, norm, now_iso, slug, write_json


def _settings(proj):
    return {"models": list(proj.get("researcher_model_ids") or []), "rounds": proj.get("rounds") or 1,
            "schedule": proj.get("schedule_frequency"), "active": bool(proj.get("is_active"))}


def _compare(proj, latest, versions, bound, taken_dims, new_intent):
    """The version Sentl's project amounts to, and its changes from `latest`. A question or
    a dimension keeps its key through its Sentl id; a new one gets the next free key."""
    dim_of = {v: k for k, v in bound["dimensions"].items()}
    q_of = {v: k for k, v in bound["questions"].items()}
    before_d = {d["key"]: d for d in latest["dimensions"]}
    before_q = {q["key"]: q for d in latest["dimensions"] for q in d["questions"]}
    taken_q = {q["key"] for v in versions for d in v["dimensions"] for q in d["questions"]}

    def new_key(dkey):
        n = 1
        while f"{dkey}-{n}" in taken_q:
            n += 1
        taken_q.add(f"{dkey}-{n}")
        return f"{dkey}-{n}"

    changes, dims = [], []
    for d in proj["dimensions"]:
        dkey = dim_of.get(d["id"]) or _unique(slug(d["name"]), taken_dims)
        archived, old = bool(d.get("archived")), before_d.get(dkey)
        if old is None or (old["archived"] and not archived):
            changes.append({"dimension": dkey, "change": "dimension_added"})
        elif archived and not old["archived"]:
            changes.append({"dimension": dkey, "change": "dimension_archived"})
        elif norm(old["name"]) != norm(d["name"]):
            changes.append({"dimension": dkey, "change": "dimension_renamed"})
        questions = []
        for q in d["questions"]:
            qkey, h = q_of.get(q["id"]), criteria_hash(q.get("grading_rubric"), q.get("additional_instructions"))
            was = before_q.get(qkey)
            # A difference of quotes or spacing is a transcription, not an edit.
            text = was["text"] if was and norm(was["text"]) == norm(q["question"]) else q["question"]
            if was is None:
                qkey = new_key(dkey)
                changes.append({"question": qkey, "change": "created"})
            elif text != was["text"] and qkey in new_intent:
                old_key, qkey = qkey, new_key(dkey)
                changes += [{"question": qkey, "change": "new_intent", "replaces": old_key},
                            {"question": old_key, "change": "retired"}]
            else:
                if text != was["text"]:
                    changes.append({"question": qkey, "change": "reworded"})
                if was["criteria_hash"] != h:
                    changes.append({"question": qkey, "change": "criteria"})
            questions.append({"key": qkey, "id": q["id"], "text": text, "criteria_hash": h, "sentl": q})
        dims.append({"key": dkey, "id": d["id"], "name": d["name"], "archived": archived, "questions": questions})

    present_q = {q["id"] for d in proj["dimensions"] for q in d["questions"]}
    present_d = {d["id"] for d in proj["dimensions"]}
    changes += [{"question": k, "change": "retired"} for k, q in before_q.items() if q["id"] not in present_q]
    changes += [{"dimension": k, "change": "dimension_archived"} for k, d in before_d.items()
                if d["id"] not in present_d and not d["archived"]]
    settings = _settings(proj)
    was_models, models = latest["settings"]["models"], settings["models"]
    if set(was_models) != set(models):
        changes.append({"change": "models", "added": [m for m in models if m not in was_models],
                        "removed": [m for m in was_models if m not in models]})
    if latest["settings"]["rounds"] != settings["rounds"]:
        changes.append({"change": "rounds", "from": latest["settings"]["rounds"], "to": settings["rounds"]})
    return settings, dims, changes


def _mirror(study, entry, dims, settings, changes, number):
    """Make an adopted project's entry in study.json follow Sentl's project."""
    old_questions = {q["key"]: q for d in entry["dimensions"] for q in d["questions"]}
    old_dims = {d["key"]: d for d in entry["dimensions"]}
    lineage = {}
    for c in changes:
        if "question" in c and c["change"] != "retired":
            lineage.setdefault(c["question"], []).append(
                {"version": number, **{k: v for k, v in c.items() if k != "question"}})
    themes = {t["id"] for t in study["themes"]}
    out = []
    for d in dims:
        questions = []
        for q in d["questions"]:
            sentl = q["sentl"]
            item = dict(old_questions.get(q["key"]) or {"key": q["key"]})
            item.update(label=sentl.get("label", ""), text=q["text"], rubric=sentl.get("grading_rubric") or {},
                        instructions=sentl.get("additional_instructions") or "")
            item["lineage"] = list(item.get("lineage") or []) + lineage.get(q["key"], [])
            questions.append(item)
        out.append({**old_dims.get(d["key"], {}), "key": d["key"], "name": d["name"], "archived": d["archived"],
                    "questions": questions})
        if d["key"] not in themes and not d["archived"]:
            study["themes"].append({"id": d["key"], "label": d["name"], "origins": [], "dimension": d["key"]})
    entry.update(models=settings["models"], rounds=settings["rounds"], schedule=settings["schedule"], dimensions=out)


def _describe(changes, latest, dims):
    texts = {q["key"]: q["text"] for d in dims for q in d["questions"]}
    texts.update({q["key"]: q["text"] for d in latest["dimensions"] for q in d["questions"] if q["key"] not in texts})
    before = {q["key"]: q["text"] for d in latest["dimensions"] for q in d["questions"]}
    lines = []
    for c in changes:
        kind, q, d = c["change"], c.get("question"), c.get("dimension")
        if kind == "reworded":
            lines.append(f"  {q} reworded: «{before[q]}» → «{texts[q]}»")
        elif kind == "new_intent":
            lines.append(f"  {q} replaces {c['replaces']} as a new question: «{texts[q]}»")
        elif kind == "criteria":
            lines.append(f"  {q}: rubric or judge instructions changed («{texts[q]}»)")
        elif kind in ("created", "retired"):
            lines.append(f"  {q} {kind}: «{texts[q]}»")
        elif kind == "models":
            lines.append(f"  models added: {', '.join(c['added']) or 'none'}; removed: {', '.join(c['removed']) or 'none'}")
        elif kind == "rounds":
            lines.append(f"  rounds {c['from']} → {c['to']}")
        else:
            lines.append(f"  dimension {d}: {kind.removeprefix('dimension_')}")
    return lines


def detect(root, key, saved_file, new_intent=(), dry_run=False):
    folder = Study(root)
    study, binding = folder.study, folder.binding
    folder.project(key)
    entry = next(p for p in study["projects"] if p["key"] == key)
    bound = binding["projects"][key]
    proj = load_mcp(saved_file, "project")
    if "dimensions" not in proj or "id" not in proj:
        raise Refused(f"{saved_file} is not a get-project-tool response")
    if proj["id"] != bound["project_id"]:
        raise Refused(f"the saved project is {proj['id']}, but {key} is bound to project {bound['project_id']}: "
                      "save get-project-tool's response for the right project")
    versions = folder.versions(key)
    latest, now = versions[-1], now_iso()
    taken_dims = set(bound["dimensions"]) | {t["id"] for t in study["themes"]} | {d["key"] for d in entry["dimensions"]}
    settings, dims, changes = _compare(proj, latest, versions, bound, taken_dims, set(new_intent))

    notes = [f"--new-intent {k} ignored: the saved project does not reword {k}."
             for k in sorted(set(new_intent) - {c.get("replaces") for c in changes})]
    if not changes:
        if not dry_run:
            latest["seen_at"] = now
            write_json(folder.path("history", "versions", f"{key}-{latest['version']:03d}.json"), latest)
        return "\n".join([f"Project {key} unchanged since version {latest['version']}."] + notes)

    number = latest["version"] + 1
    window = {"from": latest.get("seen_at") or latest["recorded_at"], "to": now}
    lines = [f"Project {key} differs from version {latest['version']}: the edit was made in Sentl between "
             f"{window['from']} and {now}. Changes (tell the operator):"] + _describe(changes, latest, dims) + notes
    if any(c["change"] == "reworded" for c in changes):
        lines.append("A reworded question keeps its key and is compared with its earlier wording. If it now asks "
                     "something else, the operator says so: run with --dry-run, then with --new-intent <key>.")
    if dry_run:
        return "\n".join(lines + ["Dry run: nothing written."])

    write_json(folder.path("history", "versions", f"{key}-{number:03d}.json"), {
        "schema": "sentl-monitor/version@1", "project": key, "version": number, "source": "detected",
        "recorded_at": now, "seen_at": now, "window": window, "settings": settings,
        "dimensions": [{**d, "questions": [{k: v for k, v in q.items() if k != "sentl"} for q in d["questions"]]}
                       for d in dims],
        "changes": changes})
    bound.update(version=number, dimensions={d["key"]: d["id"] for d in dims},
                 questions={q["key"]: q["id"] for d in dims for q in d["questions"]})
    write_json(folder.path("sentl.json"), binding)
    lines.append(f"Version {number} recorded as detected. Runs started between {window['from']} and {now} "
                 "are matched against both versions.")
    if versions[0]["source"] == "adopt":
        _mirror(study, entry, dims, settings, changes, number)
        write_json(folder.path("study.json"), study)
        lines.append("study.json now follows Sentl's project, as for every adopted project.")
    else:
        lines.append("study.json is left as it is: the operator chooses whether the design or Sentl's project holds.")
    return "\n".join(lines)
