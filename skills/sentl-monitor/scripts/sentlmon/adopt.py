"""`adopt`: take a project that already exists in Sentl into a study folder."""

import hashlib
import json

from . import schema
from .i18n import SECTIONS
from .common import Refused, Study, load_json, match_key, norm, now_iso, require_language, slug, write_json

ORIGIN_KINDS = ("client_material", "client_issue", "client_analysis", "search", "probe")
AUDIENCES = ("generic_consumer", "personas", "stakeholders", "mixed")

QUESTIONS_FOR_THE_OPERATOR = [
    ("narrative.research_question", "the neutral question the study answers"),
    ("narrative.purpose", "what the client will decide with the reports"),
    ("narrative.audience", '{"choice": one of ' + ", ".join(AUDIENCES) + ', "reason": "..."}'),
    ("narrative.criteria", '{"by": who wrote the rubrics, "date": "YYYY-MM-DD"}'),
    ("subject.label, subject.aliases, subject.owned_domains", "the subject as answers name it, and its websites"),
    ("foils", '[{"id": "...", "label": "...", "aliases": ["..."], "domains": ["..."]}], competitors or alternatives '
              "and the websites they own (optional)"),
    ("market", '{"country": ISO 3166 code such as "IT" or "GB", "language": ISO 639 code such as "it" or "en"}'),
    ("report_language", " or ".join(sorted(SECTIONS))),
    ("report_every", "weekly or monthly"),
    ("themes[].origins", "for each theme: [{\"kind\": one of " + ", ".join(ORIGIN_KINDS) + ', "detail": "..."}]'),
]


def criteria_hash(rubric, instructions):
    payload = {"rubric": {k: norm(v) for k, v in sorted((rubric or {}).items())},
               "instructions": norm(instructions)}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _terms(value):
    """A list of non-empty strings, as foil domains and fact terms must be."""
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def missing_answers(study):
    """Fields the operator must supply before a report can be written."""
    missing = []
    narrative = study.get("narrative") or {}
    for field in ("research_question", "purpose"):
        if not (narrative.get(field) or "").strip():
            missing.append(f"narrative.{field}")
    snapshot = study.get("kind") == "snapshot"
    audience = narrative.get("audience") or {}
    if not snapshot and (audience.get("choice") not in AUDIENCES or not (audience.get("reason") or "").strip()):
        missing.append("narrative.audience")
    criteria = narrative.get("criteria") or {}
    if not (criteria.get("by") or "").strip() or not criteria.get("date"):
        missing.append("narrative.criteria")
    subject = study.get("subject") or {}
    if not (subject.get("label") or "").strip():
        missing.append("subject.label")
    if not subject.get("aliases"):
        missing.append("subject.aliases")
    market = study.get("market") or {}
    if not market.get("country") or not market.get("language"):
        missing.append("market")
    if study.get("report_language") not in SECTIONS:
        missing.append("report_language")
    if not snapshot and study.get("report_every") not in ("weekly", "monthly"):
        missing.append("report_every")
    for n, foil in enumerate(study.get("foils") or []):
        if "domains" in foil and not _terms(foil["domains"]):
            missing.append(f"foils[{foil.get('id') or n}].domains")
    for proj in study.get("projects", []):
        for q in (q for d in proj["dimensions"] for q in d["questions"]):
            for n, fact in enumerate(q.get("facts") or []):
                missing += [f"questions[{q['key']}].facts[{n}].{kind}" for kind in ("current", "outdated")
                            if kind in fact and not _terms(fact[kind])]
    measured = {d["key"] for p in study.get("projects", []) for d in p["dimensions"] if not d.get("archived")}
    for theme in study.get("themes", []):
        if theme.get("dimension") not in measured:
            continue
        origins = theme.get("origins") or []
        if not origins or any(o.get("kind") not in ORIGIN_KINDS or not (o.get("detail") or "").strip() for o in origins):
            missing.append(f"themes[{theme['id']}].origins")
    return missing


def _unique(base, taken):
    key, n = base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    taken.add(key)
    return key


def _check_against_run(proj, run):
    if run.get("project_id") not in (None, proj["id"]):
        raise Refused(f"the saved run belongs to project {run.get('project_id')}, not {proj['id']}")
    dims = {match_key(d["name"]) for d in proj["dimensions"]}
    pairs = {(match_key(d["name"]), match_key(q["question"])) for d in proj["dimensions"] for q in d["questions"]}
    lost = []
    for r in run.get("responses", []):
        dim, text = match_key(r.get("dimension")), match_key(r.get("question"))
        if dim not in dims:
            lost.append(f"dimension {r.get('dimension')!r}")
        elif (dim, text) not in pairs:
            lost.append(f"{r.get('dimension')}: {r.get('question')}")
    if lost:
        listing = "\n  ".join(dict.fromkeys(lost))
        raise Refused("the saved project lacks texts the latest run asked, so it was not saved exactly:\n  "
                      + listing + "\nSave get-project-tool's response again and rerun adopt.")


def adopt(root, project_file, run_file=None, key=None):
    folder = Study(root)
    proj = schema.project(project_file)
    run = schema.run_results(run_file) if run_file else None
    if run is not None:
        _check_against_run(proj, run)

    study_path, binding_path = folder.path("study.json"), folder.path("sentl.json")
    study = load_json(study_path) if study_path.exists() else None
    binding = load_json(binding_path) if binding_path.exists() else None
    if study:
        require_language(study)
    key = key or slug(proj["name"])
    if binding and key in binding["projects"]:
        raise Refused(f"project key {key!r} is already in this study")

    recorded_at = now_iso()
    dim_keys = set(t["id"] for t in (study or {}).get("themes", []))
    dims, ver_dims, ids_dims, ids_questions, themes = [], [], {}, {}, []
    for d in proj["dimensions"]:
        dkey = _unique(slug(d["name"]), dim_keys)
        ids_dims[dkey] = d["id"]
        questions, ver_questions = [], []
        for n, q in enumerate(d["questions"], 1):
            qkey = f"{dkey}-{n}"
            ids_questions[qkey] = q["id"]
            questions.append({"key": qkey, "label": q.get("label") or "", "text": q["question"],
                              "rubric": q.get("grading_rubric") or {}, "instructions": q.get("additional_instructions") or "",
                              "lineage": [{"version": 1, "change": "adopted"}]})
            ver_questions.append({"key": qkey, "id": q["id"], "text": q["question"],
                                  "criteria_hash": criteria_hash(q.get("grading_rubric"), q.get("additional_instructions"))})
        archived = bool(d.get("archived"))
        dims.append({"key": dkey, "name": d["name"], "archived": archived, "questions": questions})
        ver_dims.append({"key": dkey, "id": d["id"], "name": d["name"], "archived": archived, "questions": ver_questions})
        if not archived:
            themes.append({"id": dkey, "label": d["name"], "origins": [], "dimension": dkey})

    settings = {"models": list(proj.get("researcher_model_ids") or []), "rounds": proj.get("rounds") or 1,
                "schedule": proj.get("schedule_frequency"), "active": bool(proj.get("is_active"))}
    entry = {"key": key, "name": proj["name"], "question": None, "decision": None,
             "models": settings["models"], "rounds": settings["rounds"], "schedule": settings["schedule"],
             "dimensions": dims}

    if study is None:
        study = {
            "schema": "sentl-monitor/study@1", "kind": "study",
            "subject": {"id": None, "label": None, "kind": None, "aliases": [], "owned_domains": []},
            "foils": [], "components": [], "market": None, "report_language": None, "report_every": None,
            "organization": proj.get("organization"),
            "narrative": {"research_question": None, "purpose": None, "audience": None, "criteria": None,
                          "design_rationale": [], "score_axis": None},
            "themes": [], "projects": [],
        }
        binding = {"schema": "sentl-monitor/binding@1", "organization": proj.get("organization"), "projects": {}}
    study["themes"].extend(themes)
    study["projects"].append(entry)
    binding["projects"][key] = {"project_id": proj["id"], "version": 1,
                                "dimensions": ids_dims, "questions": ids_questions}
    version = {"schema": "sentl-monitor/version@1", "project": key, "version": 1, "source": "adopt",
               "recorded_at": recorded_at, "seen_at": recorded_at, "window": None, "settings": settings,
               "dimensions": ver_dims, "changes": []}

    write_json(folder.path("history", "versions", f"{key}-001.json"), version)
    write_json(study_path, study)
    write_json(binding_path, binding)

    measured = [d for d in dims if not d["archived"]]
    lines = [f"Adopted {proj['name']!r} as project {key}: {len(measured)} dimensions measured"
             f" ({len(dims) - len(measured)} archived), {sum(len(d['questions']) for d in measured)} questions."]
    if run is not None:
        lines.append(f"Latest run {run.get('id')}: every question and dimension it asked is in the saved project.")
    else:
        lines.append("No completed run given: the check of the saved project against a run was skipped; "
                     "tell the operator.")
    lines.append("Ask the operator for these and write them into study.json; the texts appear in the report as "
                 "written, so write them in the report's language:")
    lines += [f"  {field}: {hint}" for field, hint in QUESTIONS_FOR_THE_OPERATOR]
    lines.append("Optional: narrative.score_axis (stance or fidelity), projects[].question and projects[].decision.")
    lines.append("Optional, for the insights: foils[].domains (the sites each competitor owns), and for each question "
                 'whose facts carry a figure or a name (a price, a fee, a person in charge) a "facts" list under the '
                 'question: [{"fact": "...", "source": "...", "date": "YYYY-MM-DD", "current": ["term"], '
                 '"outdated": ["term"]}], the terms written as answers state them. Do not change the question texts.')
    return "\n".join(lines)
