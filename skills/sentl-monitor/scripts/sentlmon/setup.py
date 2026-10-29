"""`payload` and `bind`: the arguments the setup route sends to Sentl's tools that write, and the
record of what Sentl then holds. Nothing here calls Sentl: `payload` prints JSON for the assistant
to pass to the tools, and `bind` reads a saved get-project-tool response."""

import json

from . import design, schema, snapshot
from .adopt import criteria_hash
from .common import FINAL, Refused, Study, load_json, match_key, norm, now_iso, slug, write_json
from .detect import _compare, _describe


def _project_of(study, key):
    for project in study["projects"]:
        if project["key"] == key:
            return project
    raise Refused(f"no project {key!r} in study.json; projects: " + ", ".join(p["key"] for p in study["projects"]))


def _binding(folder, study):
    path = folder.path("sentl.json")
    if path.exists():
        return load_json(path)
    return {"schema": "sentl-monitor/binding@1", "organization": study.get("organization"), "projects": {}}


def _judge_text(q):
    return design.compose_instructions(q.get("instructions"), q.get("facts"))


def _check_saved(saved, bound, key):
    if saved.get("archived"):
        raise Refused(f"project {saved['id']} is archived in Sentl: restore it first, or leave it as a history to "
                      "read; nothing is saved to an archived project")
    if saved["id"] != bound["project_id"]:
        raise Refused(f"the saved project is {saved['id']}, but {key} is bound to project {bound['project_id']}: "
                      "save get-project-tool's response for the right project")


def _pending(folder, key, bound, runs_file):
    """(lines to refuse with, notes): completed runs neither ingested nor recorded as unavailable,
    and runs still open."""
    listing = schema.run_listing(runs_file)
    if listing["project_id"] != bound["project_id"]:
        raise Refused(f"the saved run listing is of project {listing['project_id']}, but {key} is bound to project "
                      f"{bound['project_id']}: save list-runs-tool's response for the right project")
    ingested = {int(p.name.split(".")[0]) for p in folder.path("history", "runs", key).glob("*.json.gz")}
    path = folder.path("history", "unavailable.json")
    unavailable = {e["run_id"] for e in (load_json(path)["runs"] if path.exists() else []) if e["project"] == key}
    rows = listing["runs"]
    pending = sorted(r["id"] for r in rows if r["status"] in FINAL and r["id"] not in ingested | unavailable)
    notes = [f"run {r['id']} is {r['status']}: its answers are read once it completes, and a save now is "
             "matched against the version in force when it started" for r in rows if r["status"] in schema.OPEN]
    return pending, notes


def _unrecorded_edits(folder, key, study, bound, saved):
    """Refuse a saved project that differs from the latest recorded version: saving would overwrite
    an edit made in Sentl's panel, and the runs it touched would be matched to the wrong wording."""
    versions = folder.versions(key)
    if not versions:
        raise Refused(f"no recorded version for project {key!r}: run bind on a saved get-project-tool response first")
    latest = versions[-1]
    entry = _project_of(study, key)
    taken = set(bound["dimensions"]) | {t["id"] for t in study["themes"]} | {d["key"] for d in entry["dimensions"]}
    _, dims, changes = _compare(saved, latest, versions, bound, taken, set())
    if changes:
        raise Refused("the project in Sentl differs from the latest recorded version, so saving would overwrite an "
                      "edit made there. Run detect on this saved response, then payload again:\n"
                      + "\n".join(_describe(changes, latest, dims)))


def _create(project, binding, study):
    organization = binding.get("organization") or study.get("organization")
    if not organization:
        raise Refused("study.json and sentl.json name no organization: set `organization` in study.json to the "
                      "slug list-organizations gives")
    out = {"organization": organization, "name": project["name"], "researcher_model_ids": list(project["models"])}
    if study.get("kind") == "snapshot":
        return out
    out["rounds"] = project["rounds"]
    if project.get("schedule"):
        out["schedule_frequency"] = project["schedule"]
    return out


def _settings_update(project, bound, saved, is_snapshot=False):
    """The update call when the study's name, models, rounds or schedule differ from the project in Sentl,
    and, for a snapshot, when the project is active. Activation is never part of it: the study route sets
    it only on the operator's go, and a snapshot's call can only pause."""
    differs = (norm(saved["name"]) != norm(project["name"])
               or set(saved.get("researcher_model_ids") or []) != set(project["models"])
               or (not is_snapshot and (saved["rounds"] != project["rounds"]
                                        or saved.get("schedule_frequency") != project["schedule"])))
    pause = is_snapshot and bool(saved.get("is_active"))
    if not (differs or pause):
        return None
    out = {"project_id": bound["project_id"], "name": project["name"],
           "researcher_model_ids": list(project["models"])}
    if not is_snapshot:
        out["rounds"] = project["rounds"]
        out["schedule_frequency"] = project["schedule"]
    if pause:
        out["is_active"] = False
    return out


def _questions(project, bound, saved):
    """The save-project-questions-tool arguments. Every item the study holds keeps its Sentl id; a
    text that differs from Sentl's only by its normalization is sent as Sentl has it; a dimension
    the study dropped is sent archived, since one left out would be deleted."""
    by_dim = {d["id"]: d for d in saved["dimensions"]}
    out, notes = [], []
    for d in project["dimensions"]:
        did = bound["dimensions"].get(d["key"])
        sentl = by_dim.get(did)
        item = {}
        if did is not None:
            item["id"] = did
        item["name"] = sentl["name"] if sentl and norm(sentl["name"]) == norm(d["name"]) else d["name"]
        if sentl and sentl.get("archived"):
            item["archived"] = False
        held = {q["id"]: q for q in sentl["questions"]} if sentl else {}
        questions = []
        for q in d["questions"]:
            qid = bound["questions"].get(q["key"])
            was = held.get(qid)
            text = was["question"] if was and norm(was["question"]) == norm(q["text"]) else q["text"]
            entry = {"label": q["label"], "question": text, "grading_rubric": dict(q["rubric"]),
                     "additional_instructions": _judge_text(q)}
            questions.append({"id": qid, **entry} if qid is not None else entry)
        item["questions"] = questions
        out.append(item)
        kept = {bound["questions"].get(q["key"]) for q in d["questions"]}
        notes += [f"question {key} ({sq['question']!r}) is not in study.json: Sentl deletes it only when the call "
                  "carries delete_missing: true, which the operator approves from the dry run's list"
                  for key, qid in bound["questions"].items() if qid in held and qid not in kept
                  for sq in [held[qid]]]
    kept_dims = {d["key"] for d in project["dimensions"]}
    out += [{"id": did, "archived": True} for key, did in bound["dimensions"].items() if key not in kept_dims]
    return {"project_id": bound["project_id"], "dimensions": out}, notes


def payload(root, key, models_file, saved_file=None, runs_file=None):
    """The arguments of the Sentl tools that write, as JSON; nothing is written or sent."""
    folder = Study(root)
    study = folder.study
    project = _project_of(study, key)
    is_snapshot = study.get("kind") == "snapshot"
    problems, _ = (snapshot if is_snapshot else design).problems_of(study, set(schema.models(models_file)))
    if problems:
        raise Refused("study.json fails validate, so it is not set up in Sentl:\n  - " + "\n  - ".join(problems))
    binding = _binding(folder, study)
    bound = binding["projects"].get(key)
    out = {"project": key}
    if bound is None:
        tool = "create-snapshot-tool" if is_snapshot else "create-project-tool"
        out[tool] = _create(project, binding, study)
        out["notes"] = [f"the {'snapshot' if is_snapshot else 'project'} does not exist in Sentl yet: call {tool}, "
                        "save its project to inbox/, run bind, then run payload again for the questions"]
        return json.dumps(out, ensure_ascii=False, indent=2)

    if not saved_file or not runs_file:
        raise Refused(f"project {key} is bound to project {bound['project_id']}: pass --saved (the get-project-tool "
                      "response read now) and --runs (the list-runs-tool response read now)")
    saved = schema.project(saved_file)
    _check_saved(saved, bound, key)
    pending, notes = _pending(folder, key, bound, runs_file)
    if pending:
        raise Refused("completed runs are not ingested yet: " + ", ".join(f"run {i}" for i in pending)
                      + ". Fetch each with get-run-results-tool and ingest it, or record it as unavailable "
                        "with ingest --unavailable, before any save")
    _unrecorded_edits(folder, key, study, bound, saved)
    update = _settings_update(project, bound, saved, is_snapshot)
    if update:
        out["update-project-settings-tool"] = update
    arguments, left_out = _questions(project, bound, saved)
    out["save-project-questions-tool"] = arguments
    out["notes"] = notes + left_out
    if is_snapshot and saved.get("schedule_frequency"):
        out["notes"].append(f"the project has the schedule {saved['schedule_frequency']} in Sentl and a snapshot has "
                            "none: tell the operator")
    return json.dumps(out, ensure_ascii=False, indent=2)


# --- bind ---------------------------------------------------------------------

def _pair(dim_name, text):
    return match_key(dim_name), match_key(text)


def _check_latest_run(saved, run, project, latest):
    """Refuse a saved project that lacks a text the latest run asked, unless the study rewords or
    drops that question on purpose."""
    now = {q["key"]: _pair(d["name"], q["text"]) for d in project["dimensions"] for q in d["questions"]}
    changed = set()
    for d in (latest or {}).get("dimensions", []):
        for q in d["questions"]:
            pair = _pair(d["name"], q["text"])
            if now.get(q["key"]) != pair:
                changed.add(pair)
    held = {_pair(d["name"], q["question"]) for d in saved["dimensions"] for q in d["questions"]}
    names = {match_key(d["name"]) for d in saved["dimensions"]}
    lost = []
    for r in run.get("responses", []):
        pair = _pair(r.get("dimension"), r.get("question"))
        if pair in changed:
            continue
        if pair[0] not in names:
            lost.append(f"dimension {r.get('dimension')!r}")
        elif pair not in held:
            lost.append(f"{r.get('dimension')}: {r.get('question')}")
    if lost:
        raise Refused("the saved project lacks texts the latest run asked, so it was not saved exactly:\n  "
                      + "\n  ".join(dict.fromkeys(lost)) + "\nSave get-project-tool's response again and rerun bind.")


def _match(project, bound, saved):
    """(dimension key -> saved dimension, question key -> saved question, problems): the study's
    items found in the saved project, by the id bound before and otherwise by name or text."""
    by_id = {d["id"]: d for d in saved["dimensions"]}
    claimed, dims, questions, problems = set(), {}, {}, []
    for d in project["dimensions"]:
        found = by_id.get(bound["dimensions"].get(d["key"]))
        if found is None:
            found = next((s for s in saved["dimensions"] if s["id"] not in claimed and norm(s["name"]) == norm(d["name"])), None)
        if found is None:
            problems.append(f"dimension {d['name']} ({d['key']}) is not in the saved project")
            continue
        if norm(found["name"]) != norm(d["name"]):
            problems.append(f"dimension {d['key']} is named {found['name']!r} in the saved project, "
                            f"{d['name']!r} in study.json")
        claimed.add(found["id"])
        dims[d["key"]] = found
        by_qid = {q["id"]: q for q in found["questions"]}
        taken = set()
        for q in d["questions"]:
            sq = by_qid.get(bound["questions"].get(q["key"]))
            if sq is None:
                sq = next((s for s in found["questions"] if s["id"] not in taken and norm(s["question"]) == norm(q["text"])), None)
            if sq is None:
                problems.append(f"question {q['key']} is not in the saved project")
                continue
            taken.add(sq["id"])
            questions[q["key"]] = sq
            if norm(sq["question"]) != norm(q["text"]):
                problems.append(f"question {q['key']} still has its earlier text in the saved project: the save "
                                "did not apply")
            elif criteria_hash(sq.get("grading_rubric"), sq.get("additional_instructions")) != \
                    criteria_hash(q["rubric"], _judge_text(q)):
                problems.append(f"question {q['key']} has another rubric or judge instructions in the saved "
                                "project than in study.json: the save did not apply")
    return dims, questions, problems


def _free(base, taken):
    n = 1
    while f"{base}-{n}" in taken:
        n += 1
    taken.add(f"{base}-{n}")
    return f"{base}-{n}"


def _layout(project, bound, saved, dims, questions, versions):
    """The saved project as version dimensions, every item under its study key; an item the study
    does not hold (an archived dimension, a question left in Sentl) keeps the key it was bound under."""
    key_of_dim = {s["id"]: k for k, s in dims.items()}
    key_of_q = {s["id"]: k for k, s in questions.items()}
    dim_by_id = {v: k for k, v in bound["dimensions"].items()}
    q_by_id = {v: k for k, v in bound["questions"].items()}
    taken_d = set(bound["dimensions"]) | {d["key"] for d in project["dimensions"]}
    taken_q = set(bound["questions"]) | {q["key"] for d in project["dimensions"] for q in d["questions"]} | {
        q["key"] for v in versions for d in v["dimensions"] for q in d["questions"]}
    out = []
    for s in saved["dimensions"]:
        dkey = key_of_dim.get(s["id"]) or dim_by_id.get(s["id"])
        if dkey is None:
            base = slug(s["name"])
            dkey, n = base, 2
            while dkey in taken_d:
                dkey, n = f"{base}-{n}", n + 1
            taken_d.add(dkey)
        qs = []
        for sq in s["questions"]:
            qkey = key_of_q.get(sq["id"]) or q_by_id.get(sq["id"]) or _free(dkey, taken_q)
            qs.append({"key": qkey, "id": sq["id"], "text": sq["question"],
                       "criteria_hash": criteria_hash(sq.get("grading_rubric"), sq.get("additional_instructions"))})
        out.append({"key": dkey, "id": s["id"], "name": s["name"], "archived": bool(s.get("archived")), "questions": qs})
    return out


def _changes(project, latest, dims, settings):
    if latest is None:
        return []
    before_d = {d["key"]: d for d in latest["dimensions"]}
    before_q = {q["key"]: q for d in latest["dimensions"] for q in d["questions"]}
    now_q = {q["key"] for d in dims for q in d["questions"]}
    replaced = {}
    for d in project["dimensions"]:
        for q in d["questions"]:
            for e in q.get("lineage") or []:
                if e.get("change") == "new_intent" and e.get("replaces"):
                    replaced[q["key"]] = e["replaces"]
    changes = []
    for d in dims:
        old = before_d.get(d["key"])
        if old is None or (old["archived"] and not d["archived"]):
            changes.append({"dimension": d["key"], "change": "dimension_added"})
        elif d["archived"] and not old["archived"]:
            changes.append({"dimension": d["key"], "change": "dimension_archived"})
        elif norm(old["name"]) != norm(d["name"]):
            changes.append({"dimension": d["key"], "change": "dimension_renamed"})
        for q in d["questions"]:
            was = before_q.get(q["key"])
            if was is None:
                old_key = replaced.get(q["key"])
                if old_key in before_q:
                    changes.append({"question": q["key"], "change": "new_intent", "replaces": old_key})
                else:
                    changes.append({"question": q["key"], "change": "created"})
                continue
            if norm(was["text"]) != norm(q["text"]):
                changes.append({"question": q["key"], "change": "reworded"})
            if was["criteria_hash"] != q["criteria_hash"]:
                changes.append({"question": q["key"], "change": "criteria"})
    changes += [{"question": k, "change": "retired"} for k in before_q if k not in now_q]
    was_models, models = latest["settings"]["models"], settings["models"]
    if set(was_models) != set(models):
        changes.append({"change": "models", "added": [m for m in models if m not in was_models],
                        "removed": [m for m in was_models if m not in models]})
    if latest["settings"]["rounds"] != settings["rounds"]:
        changes.append({"change": "rounds", "from": latest["settings"]["rounds"], "to": settings["rounds"]})
    return changes


def bind(root, key, saved_file, run_file=None):
    """Record the ids of a saved get-project-tool response in sentl.json and a `setup` version."""
    folder = Study(root)
    study = folder.study
    project = _project_of(study, key)
    saved = schema.project(saved_file)
    run = schema.run_results(run_file) if run_file else None
    if run is not None and run.get("project_id") not in (None, saved["id"]):
        raise Refused(f"the saved run belongs to project {run.get('project_id')}, not {saved['id']}")
    binding = _binding(folder, study)
    bound = binding["projects"].get(key) or {"project_id": saved["id"], "version": 0, "dimensions": {}, "questions": {}}
    _check_saved(saved, bound, key)
    versions = folder.versions(key)
    latest = versions[-1] if versions else None

    # A project just created holds no dimension: its ids are bound and its questions follow with the save.
    empty = not saved["dimensions"] and not bound["dimensions"]
    dims, questions, problems = ({}, {}, []) if empty else _match(project, bound, saved)
    if problems:
        raise Refused("the saved project does not hold study.json:\n  - " + "\n  - ".join(problems)
                      + "\nSave the project again if it was changed after, or run the save that failed.")
    if run is not None:
        _check_latest_run(saved, run, project, latest)

    settings = {"models": list(saved.get("researcher_model_ids") or []), "rounds": saved.get("rounds") or 1,
                "schedule": saved.get("schedule_frequency"), "active": bool(saved.get("is_active"))}
    layout = _layout(project, bound, saved, dims, questions, versions)
    changes = _changes(project, latest, layout, settings)
    now = now_iso()
    notes = []
    wanted = {"models": project["models"], "rounds": project["rounds"], "schedule": project.get("schedule")}
    notes += [f"settings: {k} is {settings[k]!r} in Sentl and {v!r} in study.json (recorded as Sentl has it)"
              for k, v in wanted.items() if (set(settings[k]) != set(v) if k == "models" else settings[k] != v)]
    kept = {d["key"] for d in project["dimensions"]}
    notes += [f"dimension {d['key']} is in Sentl and not in study.json" + ("" if d["archived"] else " and is not archived")
              for d in layout if d["key"] not in kept]

    unchanged = latest is not None and not changes and latest["settings"] == settings
    if unchanged:
        latest["seen_at"] = now
        write_json(folder.path("history", "versions", f"{key}-{latest['version']:03d}.json"), latest)
        number = latest["version"]
        head = f"Project {key} (Sentl project {saved['id']}) unchanged since version {number}."
    else:
        number = (latest["version"] if latest else 0) + 1
        write_json(folder.path("history", "versions", f"{key}-{number:03d}.json"), {
            "schema": "sentl-monitor/version@1", "project": key, "version": number, "source": "setup",
            "recorded_at": now, "seen_at": now, "window": None, "settings": settings, "dimensions": layout,
            "changes": changes})
        head = f"Project {key} bound to Sentl project {saved['id']}: version {number} recorded as setup."
    binding["projects"][key] = {"project_id": saved["id"], "version": number,
                                "dimensions": {d["key"]: d["id"] for d in layout},
                                "questions": {q["key"]: q["id"] for d in layout for q in d["questions"]}}
    if saved.get("kind"):
        binding["projects"][key]["kind"] = saved["kind"]
    write_json(folder.path("sentl.json"), binding)
    lines = [head, f"{len(layout)} dimensions and {sum(len(d['questions']) for d in layout)} questions have their ids "
                   "in sentl.json."]
    if empty:
        lines.append("The project holds no question yet: save its questions, then bind again.")
    if run is None:
        lines.append("No run was given: the saved project was not checked against a run's texts.")
    return "\n".join(lines + [f"Note (tell the operator): {n}" for n in notes])
