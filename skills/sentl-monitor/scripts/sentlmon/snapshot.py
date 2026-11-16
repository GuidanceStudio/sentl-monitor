"""`snapshot`: validate and review a one-off snapshot, say where an interrupted route resumes, and
record that its project is closed. Nothing here calls Sentl."""

import copy
import re
from pathlib import Path

from . import demand, design, schema
from .adopt import namesake_problems
from .common import (FINAL, Refused, Study, folded, load_json, match_key, now_iso, passed_deck, public_name,
                     write_json, write_text)

CATALOGUE = Path(__file__).resolve().parents[2] / "design" / "catalogue.md"
DIMENSIONS = (4, 5)


def is_snapshot(root):
    path = Study(root).path("study.json")
    return path.exists() and load_json(path).get("kind") == "snapshot"


def designed(study):
    """Whether a snapshot was designed as a study is, through `brief` and `design`: it lists its themes. One with no
    theme is of the earlier shape, one project of four or five dimensions of one question each, and keeps its rules."""
    return bool(study.get("themes"))


def catalogue_ids():
    try:
        text = CATALOGUE.read_text(encoding="utf-8")
    except OSError:
        raise Refused(f"the dimension catalogue {CATALOGUE.name} cannot be read: reinstall the skill") from None
    return re.findall(r"^### `([a-z0-9-]+)`\s*$", text, re.M)


def _load(root):
    path = Study(root).path("study.json")
    if not path.exists():
        raise Refused(f"study.json not found in {root}: the snapshot's design writes it")
    study = load_json(path)
    if study.get("kind") != "snapshot":
        raise Refused(f"study.json has kind {study.get('kind')!r}; a snapshot has kind 'snapshot'")
    return study


def _dimension_problems(d, rationale, ids, aliases, problems):
    key = d.get("key")
    if not design._text(d.get("catalogue")):
        problems.append(f"dimension {key} has no catalogue id")
    elif d["catalogue"] not in ids:
        problems.append(f"dimension {key}: catalogue id {d['catalogue']} is not in catalogue.md")
    if not design._text(d.get("measures")):
        problems.append(f"dimension {key}: measures must say what the dimension measures, as a non-empty text")
    if d.get("axis", "stance") not in design.AXES:
        problems.append(f"dimension {key}: axis must be one of {', '.join(design.AXES)}")
    if design._text(d.get("name")) and match_key(d["name"]) not in rationale:
        problems.append(f"dimension {d['name']} has no entry in design_rationale (the entry's choice is the "
                        "dimension's name)")
    questions = d.get("questions") or []
    if len(questions) != 1:
        problems.append(f"dimension {key} has {len(questions)} questions (a snapshot dimension has one)")
    for q in questions:
        design._check_question(q, d, None, aliases, problems)
        if not design._text(q.get("persona")):
            problems.append(f"{q.get('key')}: persona is missing (a snapshot names who asks each question)")


def _project_problems(project, model_ids, rationale, ids, aliases, problems):
    where = f"project {project.get('key')}"
    if not design._text(project.get("name")):
        problems.append(f"{where}: name must be a non-empty text")
    if project.get("rounds") != 1:
        problems.append(f"{where}: rounds must be 1 (a snapshot asks each question once)")
    if "schedule" in project:
        problems.append(f"{where}: a snapshot has no schedule")
    models = project.get("models")
    if not isinstance(models, list) or not models:
        problems.append(f"{where}: models must list at least one model id")
    else:
        problems += [f"{where}: model {m} is not in list-ai-models" for m in models if m not in model_ids]
    dims = project.get("dimensions") or []
    low, high = DIMENSIONS
    if not low <= len(dims) <= high:
        problems.append(f"{where} has {len(dims)} dimensions (a snapshot has {low} or {high})")
    names = set()
    for d in dims:
        if design._text(d.get("name")):
            if len(d["name"]) > design.DIMENSION_NAME:
                problems.append(f"dimension name of {d.get('key')} is {len(d['name'])} characters, over Sentl's "
                                f"limit of {design.DIMENSION_NAME}")
            if match_key(d["name"]) in names:
                problems.append(f"{where} has two dimensions named {d['name']}")
            names.add(match_key(d["name"]))
        else:
            problems.append(f"dimension {d.get('key')}: name must be a non-empty text")
        _dimension_problems(d, rationale, ids, aliases, problems)


def _suggestion_problems(dims, given):
    """A question's suggestion must be one its dimension's seed gave (`given`: the folded suggestions per
    dimension key), and a dimension whose seed gave some needs one on its question."""
    out = []
    for d in dims:
        found = given.get(d.get("key"), set())
        for q in d.get("questions") or []:
            if design._text(q.get("suggestion")) and folded(q["suggestion"]) not in found:
                out.append(design.unrecorded(q))
            elif "suggestion" not in q and found:
                out.append(f"{q.get('key')}: suggestion is missing: search-demand.json holds Google's suggestions "
                           f"for dimension {d.get('key')}, and the question starts from one of them")
    return out


def problems_of(study, model_ids, recorded, ids=None):
    """(refusals, warnings) of a snapshot study. `recorded` is what `demand.recorded` reads from the folder. A
    snapshot designed as a study is checked as one; one of the earlier shape, under its own rules."""
    if designed(study):
        return design.problems_of(study, model_ids, recorded)
    ids = catalogue_ids() if ids is None else ids
    problems, warnings = [], []
    narrative = study.get("narrative") or {}
    for field in ("research_question", "purpose"):
        if not design._text(narrative.get(field)):
            problems.append(f"narrative.{field} is missing")
    rationale = {match_key(c.get("choice")) for c in narrative.get("design_rationale") or [] if isinstance(c, dict)}
    subject = study.get("subject") or {}
    problems += [f"{field}: {what}" for field, what in namesake_problems(subject)]
    aliases = list(subject.get("aliases") or [])
    for foil in study.get("foils") or []:
        aliases += foil.get("aliases") or []
    projects = study.get("projects") or []
    problems += design.namesake_anchor_problems(study)
    if len(projects) != 1:
        problems.append(f"a snapshot has one project; study.json lists {len(projects)}")
    for project in projects[:1]:
        _project_problems(project, model_ids, rationale, ids, aliases, problems)
        dims = project.get("dimensions") or []
        problems += _suggestion_problems(dims, recorded[0])
        keys = [d.get("key") for d in dims] + [q.get("key") for d in dims for q in d.get("questions") or []]
        problems += [f"duplicate key {k}" for k in sorted({k for k in keys if keys.count(k) > 1}, key=str)]
        asked = [q for d in dims for q in d.get("questions") or []]
        if asked and all(q.get("branded") is True for q in asked):
            warnings.append("every dimension names the subject: no dimension shows whether the assistants name "
                            "the subject when nobody asks for it")
    return problems, warnings


def validate(root, models_file):
    """(text, ok): every refusal, then every warning."""
    study = _load(root)
    problems, warnings = problems_of(study, set(schema.models(models_file)), demand.recorded(root))
    text, ok = design.verdict(problems, warnings)
    if problems and not designed(study):
        text += ("\n  note: its themes are empty, so it is checked as a snapshot of the earlier shape (one project of "
                 "four or five dimensions of one question each); a snapshot designed through `brief` and `design` "
                 "lists its themes")
    return text, ok


def review_text(study, models_file, available=None):
    names = schema.models(models_file)
    narrative, project = study["narrative"], study["projects"][0]
    out = [f"# Snapshot review: {study['subject']['label']}", "", "## Narrative", "",
           f"- Research question: {narrative['research_question']}", f"- Purpose: {narrative['purpose']}"]
    if narrative.get("reader"):
        out.append(f"- Reader: {narrative['reader']}")
    if narrative.get("criteria"):
        out.append(f"- Rubrics written by: {narrative['criteria'].get('by')} ({narrative['criteria'].get('date')})")
    out += ["", "## Project", "", f"- {project['name']}",
            f"- Models: {', '.join(public_name(m, names) for m in project['models'])}",
            "- One round, no schedule: the project is created paused", "", "## Dimensions", ""]
    reasons = {match_key(c["choice"]): c["reason"] for c in narrative.get("design_rationale") or []}
    for d in project["dimensions"]:
        out.append(f"- {d['name']} (catalogue: {d['catalogue']}; axis {d.get('axis', 'stance')}): {d['measures']}. "
                   f"Chosen because {reasons.get(match_key(d['name']), 'no reason given')}")
    out.append("")
    return out + design.question_lines(study) + design._credits(study, models_file, available=available)


def review(root, models_file, monthly=None, available=None):
    """The review of a snapshot; `monthly` is not read, since a snapshot has no monthly budget."""
    study = _load(root)
    problems, _ = problems_of(study, set(schema.models(models_file)), demand.recorded(root))
    if problems:
        raise Refused("study.json fails validate, so there is nothing to review yet:\n  - " + "\n  - ".join(problems))
    if designed(study):
        text = design.review_text(study, root, models_file, available=available)
    else:
        text = "\n".join(review_text(study, models_file, available)).rstrip() + "\n"
    write_text(Study(root).path("study-review.md"), text)
    return text.rstrip()


# --- resume and close ---------------------------------------------------------

def _step(name, *lines):
    return "\n".join([f"Next step: {name}", *lines])


def _listings(binding, keys, runs_files):
    """{key: rows of its run listing}, one listing per snapshot not closed; the listing of a closed snapshot is not read,
    and a listing of a project no snapshot of the folder is bound to is refused."""
    by_id = {binding["projects"][k]["project_id"]: k for k in keys}
    rows_of = {}
    for path in runs_files or []:
        listing = schema.run_listing(path)
        key = by_id.get(listing["project_id"])
        if key is None:
            if len(keys) == 1:
                raise Refused(f"the saved run listing is of project {listing['project_id']}, but {keys[0]} is bound "
                              f"to project {binding['projects'][keys[0]]['project_id']}: save list-runs-tool's "
                              "response for the right project")
            bound = ", ".join(f"{k} {binding['projects'][k]['project_id']}" for k in keys)
            raise Refused(f"the run listing of project {listing['project_id']} is of no snapshot bound in this folder "
                          f"({bound}): save list-runs-tool's response for each snapshot")
        if "closed" not in binding["projects"][key]:
            rows_of[key] = listing["runs"]
    absent = [k for k in keys if k not in rows_of and "closed" not in binding["projects"][k]]
    if absent:
        raise Refused(f"project {', '.join(absent)} is bound: pass --runs, the list-runs-tool response read now, one "
                      "for each snapshot not closed")
    return rows_of


def _ingested(folder, keys):
    """{key: run ids in history/runs}."""
    return {k: {int(p.name.split(".")[0]) for p in folder.path("history", "runs", k).glob("*.json.gz")} for k in keys}


def _latest_deck(folder):
    """The reports.json entry of the latest deck that passed check, or None."""
    passed = [e for e in folder.reports() if passed_deck(e)]
    return max(passed, key=lambda e: e["date"]) if passed else None


def _unread(entry, ingested):
    """[(key, run id)] of the runs ingested that the deck of `entry` did not read. An entry with no `runs` names none."""
    if "runs" not in entry:
        return []
    read = entry["runs"] or {}
    return [(k, i) for k, ids in ingested.items() for i in sorted(ids) if i not in read.get(k, [])]


def resume(root, runs_files=None):
    """Which step of SNAPSHOT.md the folder is at, from its files and the run listing of each snapshot read now. The
    folder may hold several snapshots, run one after the other and pooled in one deck."""
    folder = Study(root)
    if not folder.path("study.json").exists():
        return _step("design", "No study.json: design the snapshot (SNAPSHOT.md steps 2 to 5).")
    study = _load(root)
    keys = [p["key"] for p in study["projects"]]
    binding = load_json(folder.path("sentl.json")) if folder.path("sentl.json").exists() else {"projects": {}}
    missing = [k for k in keys if not (binding["projects"].get(k) or {}).get("questions")]
    if missing:
        if len(keys) == 1:
            return _step("project", "The project is not created in Sentl, or holds no question yet: create it, save "
                                    "its questions and bind it (step 6).")
        return _step("project", f"Not created in Sentl, or holding no question yet: {', '.join(missing)}. Create each, "
                                "save its questions and bind it (step 6).")
    if isinstance(runs_files, (str, Path)):
        runs_files = [runs_files]
    rows_of = _listings(binding, keys, runs_files)
    ingested = _ingested(folder, keys)
    open_ = [(k, r) for k in rows_of for r in rows_of[k] if r["status"] in schema.OPEN]
    if open_:
        shown = ", ".join(f"run {r['id']} of {k}" for k, r in open_)
        return _step("run", f"A run is open: {shown}. Follow it with list-runs-tool until its status is final "
                            "(step 8). A run is already started, so do not call trigger-run-tool.")
    for k in keys:
        rows = rows_of.get(k)
        if rows is None or ingested[k] or any(r["status"] in FINAL for r in rows):
            continue
        ended = [r for r in rows if r["status"] in schema.ENDED]
        unseen = [r for r in rows if r["status"] not in schema.STATUSES]
        if ended:
            shown = ", ".join(f"run {r['id']} ({r['status']})" for r in ended)
            return _step("run", f"The run of {k} ended with no results: {shown}. Tell the operator, with Sentl's "
                                "error; a stalled run was not charged. Call trigger-run-tool again only on a new go.")
        if unseen:
            shown = ", ".join(f"run {r['id']} ({r['status']})" for r in unseen)
            return _step("run", f"Status never seen: {shown}. Tell the operator and do not call trigger-run-tool "
                                "again without a new go.")
        return _step("cost", f"Snapshot {k} has no run: show estimate-run-tool for it and wait for the operator's go "
                             "(step 7).")
    pending = [(k, r) for k in rows_of for r in rows_of[k] if r["status"] in FINAL and r["id"] not in ingested[k]]
    if pending:
        shown = ", ".join(f"run {r['id']} of {k}" for k, r in pending)
        return _step("deck", f"A completed run is not in history/runs: {shown}. Fetch its results, ingest them, "
                             "build the period, which pools every run of every snapshot, and write the deck (step 9).")
    if not any(ingested.values()):
        # Every snapshot is closed, since one that is not has a run or stopped at its cost or run step above.
        return _step("done", "Every snapshot was closed before a run of it was ingested: there is no run to pool, so no "
                             "deck is written. A new look at the subject starts in a new folder.")
    latest = _latest_deck(folder)
    if latest is None:
        return _step("deck", "Every run is ingested and no deck has passed check: build the period and write the deck "
                             "(step 9).")
    later = _unread(latest, ingested)
    if later:
        shown = ", ".join(f"run {i} of {k}" for k, i in later)
        return _step("deck", f"Ingested after the deck of {latest['date']} passed: {shown}. Build the period again, which "
                             "pools every run of every snapshot, and write its deck (step 9); the new deck replaces the "
                             f"deck of {latest['date']}.")
    open_ends = [k for k in keys if "closed" not in binding["projects"][k]]
    if open_ends:
        return _step("end", f"The deck is final and {', '.join(open_ends)} is not closed: ask the operator whether to "
                            "keep each snapshot, delete it, or follow the subject over time (step 10).")
    return _step("done", "The snapshot is finished: the deck is final and every project is closed.")


def _key_to_close(study, project):
    keys = [p["key"] for p in study["projects"]]
    if project is None:
        if len(keys) > 1:
            raise Refused(f"this folder holds {len(keys)} snapshots ({', '.join(keys)}): pass --project, the one "
                          "to close")
        return keys[0]
    if project not in keys:
        raise Refused(f"no snapshot {project!r} in study.json: one of {', '.join(keys)}")
    return project


def close(root, saved_file=None, deleted=False, project=None):
    """Record in sentl.json how one snapshot ended: kept in Sentl, archived, or deleted."""
    folder = Study(root)
    study = _load(root)
    key = _key_to_close(study, project)
    if not folder.path("sentl.json").exists():
        raise Refused(f"sentl.json not found in {root}: the snapshot is created and bound first (SNAPSHOT.md step 6)")
    binding = load_json(folder.path("sentl.json"))
    bound = binding["projects"].get(key)
    if bound is None:
        raise Refused(f"project {key!r} has no binding in sentl.json")
    if "closed" in bound:
        return f"Project {key} was already closed at {bound['closed']['closed_at']}; nothing changed."
    if deleted:
        how = "deleted"
    else:
        if not saved_file:
            raise Refused("pass --saved (the get-project-tool response read now), or --deleted when the snapshot was "
                          "deleted")
        saved = schema.project(saved_file)
        if saved["id"] != bound["project_id"]:
            raise Refused(f"the saved project is {saved['id']}, but {key} is bound to project {bound['project_id']}: "
                          "save get-project-tool's response for the right project")
        if saved.get("is_active"):
            raise Refused("the project is still is_active in Sentl: archive it, or call update-project-settings-tool "
                          "with is_active false, save get-project-tool again and run close again")
        how = "archived" if saved.get("archived") else "kept"
    bound["closed"] = {"closed_at": now_iso(), "how": how}
    write_json(folder.path("sentl.json"), binding)
    return (f"Project {key} is recorded as closed in sentl.json ({how}). The run, its period and the deck stay in this "
            "folder, so nothing the deck needs is lost if the snapshot is deleted or the project archived.")


# --- promote ------------------------------------------------------------------

def _promote_gaps(answers):
    """What the operator's answers still lack for a monitored study."""
    gaps = []
    if answers.get("schedule") not in design.SCHEDULES:
        gaps.append(f"schedule: one of {', '.join(design.SCHEDULES)}")
    if answers.get("report_every") not in ("weekly", "monthly"):
        gaps.append("report_every: weekly or monthly")
    audience = answers.get("audience") or {}
    if audience.get("choice") not in design.AUDIENCES or not design._text(audience.get("reason")):
        gaps.append(f"audience: {{choice: one of {', '.join(design.AUDIENCES)}, reason}}")
    project = answers.get("project") or {}
    for field in ("question", "decision"):
        if not design._text(project.get(field)):
            gaps.append(f"project.{field}: a non-empty text")
    return gaps


def _per_project(answers, field, keys, allowed, gaps, required=True):
    """{key: value} from an answer given once for every project or as a map by project key."""
    value = answers.get(field)
    if value is None and not required:
        return {}
    given = value if isinstance(value, dict) else {k: value for k in keys}
    wrong = [k for k in keys if (k in given or required) and not allowed(given.get(k))]
    extra = sorted(set(given) - set(keys))
    if wrong or extra:
        detail = ([f"wrong or missing for {', '.join(wrong)}"] if wrong else []) + (
            [f"no project {', '.join(extra)}"] if extra else [])
        gaps.append(f"{field}: one value for every project, or one for each of {', '.join(keys)} "
                    f"({'; '.join(detail)})")
    return {k: v for k, v in given.items() if k in keys}


def _study_name(name):
    """`<subject> · <project>` from a snapshot named `Snapshot · <subject> · <project> · <D>`."""
    parts = name.split(" · ")
    if len(parts) >= 3 and parts[0] == "Snapshot" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[-1]):
        return " · ".join(parts[1:-1])
    return name


def _follow(root, study, answers_file, models_file):
    """A snapshot designed as a study becomes that study: the same study.json with a schedule, rounds and a report
    cadence. The snapshots' bindings move to `snapshots` in sentl.json, so `payload` creates each project; their runs,
    period and deck stay as the first look."""
    folder = Study(root)
    keys = [p["key"] for p in study["projects"]]
    binding = load_json(folder.path("sentl.json")) if folder.path("sentl.json").exists() else {"projects": {}}
    unbound = [k for k in keys if not (binding["projects"].get(k) or {}).get("questions")]
    if unbound:
        raise Refused(f"snapshot {', '.join(unbound)} is not created in Sentl: a snapshot is followed after its run")
    unrun = [k for k in keys if not any(folder.path("history", "runs", k).glob("*.json.gz"))]
    if unrun:
        raise Refused(f"snapshot {', '.join(unrun)} has no run in history/runs: the snapshots' runs are the first "
                      "look, so they are ingested first")
    latest = _latest_deck(folder)
    if latest is None:
        raise Refused("the snapshots have no deck that passed check: write their deck (SNAPSHOT.md step 9) before "
                      "following the subject")
    later = _unread(latest, _ingested(folder, keys))
    if later:
        shown = ", ".join(f"run {i} of {k}" for k, i in later)
        raise Refused(f"{shown} {'were' if len(later) > 1 else 'was'} ingested after the deck of {latest['date']} "
                      "passed: build the period again and "
                      "write its deck (SNAPSHOT.md step 9), so the snapshots' deck reads every run, before following the "
                      "subject")
    answers = load_json(answers_file)
    gaps = []
    schedules = _per_project(answers, "schedule", keys, lambda v: v in design.SCHEDULES, gaps)
    rounds = _per_project(answers, "rounds", keys, lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 1,
                          gaps, required=False)
    if answers.get("report_every") not in ("weekly", "monthly"):
        gaps.append("report_every: weekly or monthly")
    if gaps:
        raise Refused("answers missing for a monitored study:\n  - " + "\n  - ".join(gaps))
    followed = copy.deepcopy(study)
    followed["kind"] = "study"
    followed["report_every"] = answers["report_every"]
    for p in followed["projects"]:
        p.update(name=_study_name(p["name"]), schedule=schedules[p["key"]], rounds=rounds.get(p["key"], p["rounds"]))
    problems, _ = design.problems_of(followed, set(schema.models(models_file)), demand.recorded(root))
    if problems:
        raise Refused("the study fails validate:\n  - " + "\n  - ".join(problems))
    for k in keys:
        binding.setdefault("snapshots", {})[k] = binding["projects"].pop(k)
    when = latest["date"]
    write_json(folder.path("study.json"), followed)
    write_json(folder.path("sentl.json"), binding)
    shown = ", ".join(f"{p['key']} ({p['schedule']}, {p['rounds']} round{'s' * (p['rounds'] != 1)})"
                      for p in followed["projects"])
    return (f"Following: study.json is a study with {shown}, reporting {answers['report_every']}. The snapshots' "
            "bindings are kept under `snapshots` in sentl.json; their runs, period and deck stay as the first look. "
            "Nothing was sent to Sentl. Next: SETUP.md from `payload`, which creates each project on the operator's "
            f"go; activation only on a further go. `report` compares the first period with the snapshots of {when}.")


def promote(root, answers_file, models_file):
    """Turn a finished snapshot into a monitored study. A snapshot designed as a study keeps its study.json, with a
    schedule, rounds and a report cadence added, and is set up as projects. A snapshot of the earlier shape, created
    as a project before Sentl had snapshots, keeps its project: the questions, the rounds and the run stay, so the run
    is the baseline of the first report. Writes study.json, and sentl.json for the first."""
    folder = Study(root)
    study = _load(root)
    if designed(study):
        return _follow(root, study, answers_file, models_file)
    project = study["projects"][0]
    key = project["key"]
    binding = load_json(folder.path("sentl.json")) if folder.path("sentl.json").exists() else {"projects": {}}
    bound = binding["projects"].get(key)
    if bound is None or not bound.get("questions"):
        raise Refused(f"project {key} is not created in Sentl: a snapshot is promoted after its run")
    if bound.get("kind") == "snapshot":
        raise Refused("a snapshot takes no schedule, so it cannot be followed: design a study for the subject "
                      "(`brief`, `design`) and keep this snapshot's deck as the first look")
    if "closed" in bound:
        raise Refused("the snapshot's project is closed: nothing is left to follow. Design a study for the "
                      "subject (`brief`, `design`) and keep this snapshot's deck as the first look")
    if not any(folder.path("history", "runs", key).glob("*.json.gz")):
        raise Refused("the snapshot has no run in history/runs: its run is the baseline, so it is ingested first")
    if not any(passed_deck(e) for e in folder.reports()):
        raise Refused("the snapshot has no deck that passed check: write its deck (SNAPSHOT.md step 9) before "
                      "promoting it")
    answers = load_json(answers_file)
    gaps = _promote_gaps(answers)
    if gaps:
        raise Refused("answers missing for a monitored study:\n  - " + "\n  - ".join(gaps))
    promoted = copy.deepcopy(study)
    promoted["kind"] = "study"
    promoted["report_every"] = answers["report_every"]
    promoted.setdefault("narrative", {})["audience"] = answers["audience"]
    promoted["projects"][0].update(schedule=answers["schedule"], question=answers["project"]["question"],
                                   decision=answers["project"]["decision"])
    when = min(e["date"] for e in folder.reports() if passed_deck(e))
    promoted["themes"] = [{"id": d["key"], "label": d["name"], "dimension": d["key"],
                           "origins": [{"kind": "probe", "detail": f"the snapshot of {when} asked this dimension "
                                                                   f"({d['catalogue']} in the catalogue)"}]}
                          for d in promoted["projects"][0]["dimensions"]]
    problems, _ = design.problems_of(promoted, set(schema.models(models_file)), demand.recorded(root))
    if problems:
        raise Refused("the promoted study fails validate:\n  - " + "\n  - ".join(problems))
    write_json(folder.path("study.json"), promoted)
    return (f"Promoted: study.json is a study with project {key} on a {answers['schedule']} schedule and reports "
            f"{answers['report_every']}; the snapshot's run and period stay as the baseline. Nothing was sent to "
            "Sentl and the project is still paused. Next: `payload` (saves the schedule), then, on the operator's "
            f"go, activation; `report` compares each period with the snapshot of {when}.")
