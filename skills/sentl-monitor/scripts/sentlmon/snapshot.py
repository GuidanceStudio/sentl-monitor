"""`snapshot`: validate and review a one-off snapshot, say where an interrupted route resumes, and
record that its project is closed. Nothing here calls Sentl."""

import copy
import re
from pathlib import Path

from . import design, schema
from .common import FINAL, Refused, Study, load_json, match_key, now_iso, public_name, write_json, write_text

CATALOGUE = Path(__file__).resolve().parents[2] / "design" / "catalogue.md"
DIMENSIONS = (4, 5)


def is_snapshot(root):
    path = Study(root).path("study.json")
    return path.exists() and load_json(path).get("kind") == "snapshot"


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


def problems_of(study, model_ids, ids=None):
    """(refusals, warnings) of a snapshot study."""
    ids = catalogue_ids() if ids is None else ids
    problems, warnings = [], []
    narrative = study.get("narrative") or {}
    for field in ("research_question", "purpose"):
        if not design._text(narrative.get(field)):
            problems.append(f"narrative.{field} is missing")
    rationale = {match_key(c.get("choice")) for c in narrative.get("design_rationale") or [] if isinstance(c, dict)}
    subject = study.get("subject") or {}
    aliases = list(subject.get("aliases") or [])
    for foil in study.get("foils") or []:
        aliases += foil.get("aliases") or []
    projects = study.get("projects") or []
    if len(projects) != 1:
        problems.append(f"a snapshot has one project; study.json lists {len(projects)}")
    for project in projects[:1]:
        _project_problems(project, model_ids, rationale, ids, aliases, problems)
        dims = project.get("dimensions") or []
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
    problems, warnings = problems_of(study, set(schema.models(models_file)))
    lines = [f"validate failed: {len(problems)} problem(s)"] if problems else [
        f"validate passed: {design._count(len(warnings), 'warning', 'warnings')}"]
    lines += [f"  - {p}" for p in problems] + [f"  warning: {w}" for w in warnings]
    return "\n".join(lines), not problems


def review_text(study, models_file):
    names = schema.models(models_file)
    narrative, project = study["narrative"], study["projects"][0]
    out = [f"# Snapshot review: {study['subject']['label']}", "", "## Narrative", "",
           f"- Research question: {narrative['research_question']}", f"- Purpose: {narrative['purpose']}"]
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
    return out + design.question_lines(study) + design._credits(study, models_file)


def review(root, models_file):
    study = _load(root)
    problems, _ = problems_of(study, set(schema.models(models_file)))
    if problems:
        raise Refused("study.json fails validate, so there is nothing to review yet:\n  - " + "\n  - ".join(problems))
    text = "\n".join(review_text(study, models_file)).rstrip() + "\n"
    write_text(Study(root).path("study-review.md"), text)
    return text.rstrip()


# --- resume and close ---------------------------------------------------------

def _step(name, *lines):
    return "\n".join([f"Next step: {name}", *lines])


def resume(root, runs_file=None):
    """Which step of SNAPSHOT.md the folder is at, from its files and the run listing read now."""
    folder = Study(root)
    if not folder.path("study.json").exists():
        return _step("design", "No study.json: design the snapshot (SNAPSHOT.md steps 2 to 5).")
    study = _load(root)
    key = study["projects"][0]["key"]
    binding = load_json(folder.path("sentl.json")) if folder.path("sentl.json").exists() else {"projects": {}}
    bound = binding["projects"].get(key)
    if bound is None or not bound.get("questions"):
        return _step("project", "The project is not created in Sentl, or holds no question yet: create it, save its "
                                "questions and bind it (step 6).")
    if runs_file is None:
        raise Refused(f"project {key} is bound: pass --runs, the list-runs-tool response read now")
    listing = schema.run_listing(runs_file)
    if listing["project_id"] != bound["project_id"]:
        raise Refused(f"the saved run listing is of project {listing['project_id']}, but {key} is bound to project "
                      f"{bound['project_id']}: save list-runs-tool's response for the right project")
    rows = listing["runs"]
    ingested = {int(p.name.split(".")[0]) for p in folder.path("history", "runs", key).glob("*.json.gz")}
    reported = any(e["status"] == "final" for e in folder.reports())
    opened = [r for r in rows if r["status"] in schema.OPEN]
    pending = [r for r in rows if r["status"] in FINAL and r["id"] not in ingested]
    unseen = [r for r in rows if r["status"] not in schema.STATUSES]
    if opened:
        return _step("run", "A run is open: follow it with list-runs-tool until its status is final (step 8). A run "
                            "is already started, so do not call trigger-run-tool.")
    if pending:
        ids = ", ".join(f"run {r['id']}" for r in pending)
        return _step("report", f"A completed run is not in history/runs: {ids}. Fetch its results, ingest them and "
                               "write the report (step 9).")
    if unseen and not ingested:
        shown = ", ".join(f"run {r['id']} ({r['status']})" for r in unseen)
        return _step("run", f"Status never seen: {shown}. Tell the operator and do not call trigger-run-tool "
                            "again without a new go.")
    if not rows and not ingested:
        return _step("cost", "The project has no run: show estimate-run-tool and wait for the operator's go "
                             "(step 7).")
    if not reported:
        return _step("report", "The run is ingested and no report has passed check: write the report (step 9).")
    if "closed" not in bound:
        return _step("archive", "The report is final and the project is not closed: ask the operator whether to follow "
                                "the subject over time (promote) or pause the project and give the panel link to "
                                "archive it (step 10).")
    return _step("done", "The snapshot is finished: the report is final and the project is closed.")


def close(root, saved_file):
    """Record in sentl.json that the snapshot's project is paused and left for the operator to archive."""
    folder = Study(root)
    study = _load(root)
    key = study["projects"][0]["key"]
    if not folder.path("sentl.json").exists():
        raise Refused(f"sentl.json not found in {root}: the project is created and bound first (SNAPSHOT.md step 6)")
    binding = load_json(folder.path("sentl.json"))
    bound = binding["projects"].get(key)
    if bound is None:
        raise Refused(f"project {key!r} has no binding in sentl.json")
    saved = schema.project(saved_file)
    if saved["id"] != bound["project_id"]:
        raise Refused(f"the saved project is {saved['id']}, but {key} is bound to project {bound['project_id']}: "
                      "save get-project-tool's response for the right project")
    if saved.get("is_active"):
        raise Refused("the project is still is_active in Sentl: call update-project-settings-tool with is_active "
                      "false, save get-project-tool again and run close again")
    if "closed" in bound:
        return f"Project {key} was already closed at {bound['closed']['paused_at']}; nothing changed."
    bound["closed"] = {"paused_at": now_iso(), "archive": "operator"}
    write_json(folder.path("sentl.json"), binding)
    return (f"Project {key} is paused and recorded as closed in sentl.json. The Sentl MCP cannot archive or delete a "
            "project: give the operator the link from project-edit-link-tool, to archive or delete it in the Sentl "
            "web panel. Deleting loses nothing the report needs, since the run is saved in this folder.")


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


def promote(root, answers_file, models_file):
    """Turn a finished snapshot whose project is still open into a monitored study: the questions, the
    rounds and the run stay, so the run is the baseline of the first report. Writes study.json only."""
    folder = Study(root)
    study = _load(root)
    project = study["projects"][0]
    key = project["key"]
    binding = load_json(folder.path("sentl.json")) if folder.path("sentl.json").exists() else {"projects": {}}
    bound = binding["projects"].get(key)
    if bound is None or not bound.get("questions"):
        raise Refused(f"project {key} is not created in Sentl: a snapshot is promoted after its run")
    if "closed" in bound:
        raise Refused("the snapshot's project is closed: nothing is left to follow. Design a study for the "
                      "subject (`brief`, `design`) and keep this report as the first look")
    if not any(folder.path("history", "runs", key).glob("*.json.gz")):
        raise Refused("the snapshot has no run in history/runs: its run is the baseline, so it is ingested first")
    if not any(e["status"] == "final" for e in folder.reports()):
        raise Refused("the snapshot has no report that passed check: write the report (SNAPSHOT.md step 9) before "
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
    when = min(e["date"] for e in folder.reports() if e["status"] == "final")
    promoted["themes"] = [{"id": d["key"], "label": d["name"], "dimension": d["key"],
                           "origins": [{"kind": "probe", "detail": f"the snapshot of {when} asked this dimension "
                                                                   f"({d['catalogue']} in the catalogue)"}]}
                          for d in promoted["projects"][0]["dimensions"]]
    problems, _ = design.problems_of(promoted, set(schema.models(models_file)))
    if problems:
        raise Refused("the promoted study fails validate:\n  - " + "\n  - ".join(problems))
    write_json(folder.path("study.json"), promoted)
    return (f"Promoted: study.json is a study with project {key} on a {answers['schedule']} schedule and reports "
            f"{answers['report_every']}; the snapshot's run and report stay as the baseline. Nothing was sent to "
            "Sentl and the project is still paused. Next: `payload` (saves the schedule), then, on the operator's "
            f"go, activation; `report` compares each period with the snapshot of {when}.")
