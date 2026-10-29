"""`design`: validate a designed study.json against Sentl's limits and the design rules, compose
the judge instructions Sentl receives, print the review the operator approves, and record the
lineage of a revised study. Nothing here calls Sentl."""

import copy
import json

from . import demand, schema
from .adopt import AUDIENCES, ORIGIN_KINDS, criteria_hash, _terms
from .common import Refused, Study, fold, first_mention, match_key, public_name, write_json, write_text

DIMENSION_NAME, LABEL, QUESTION, ANCHOR, INSTRUCTIONS = 100, 100, 500, 300, 500
SCHEDULES = ("daily", "weekly", "monthly")
FRAMINGS = ("positive", "negative", "neutral")
LEANS = ("positive", "negative", "none")
AXES = ("stance", "fidelity")
OPPOSITE = {"positive": "negative", "negative": "positive"}
DIMENSIONS_PER_PROJECT = (5, 7)
ANSWERS_PER_PERIOD = 3

# Runs of a project that fall in one report period, by schedule and report cadence.
RUNS_PER_PERIOD = {("daily", "weekly"): 7, ("daily", "monthly"): 30, ("weekly", "weekly"): 1,
                   ("weekly", "monthly"): 4, ("monthly", "weekly"): 0.25, ("monthly", "monthly"): 1}


def compose_instructions(instructions, facts):
    """The text Sentl receives as additional_instructions: the instructions, then the dated facts
    with the terms that mark an answer current or outdated. It is never cut; `validate` refuses
    one over Sentl's limit."""
    parts = [(instructions or "").strip()]
    lines = []
    for f in facts or []:
        line = (f.get("fact") or "").strip().rstrip(".")
        origin = ", ".join(x for x in (f"source {f['source']}" if f.get("source") else "",
                                       f"read {f['date']}" if f.get("date") else "") if x)
        line += f" ({origin})." if origin else "."
        for kind in ("current", "outdated"):
            if f.get(kind):
                line += f" {kind.capitalize()}: {'; '.join(f[kind])}."
        lines.append(line)
    if lines:
        parts.append("Facts: " + " ".join(lines))
    return " ".join(p for p in parts if p)


def runs_per_period(project, report_every):
    return RUNS_PER_PERIOD.get((project.get("schedule"), report_every))


def _count(n, one, many):
    return f"{n:g} {one if n == 1 else many}"


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _load(root):
    path = Study(root).path("study.json")
    if not path.exists():
        raise Refused(f"study.json not found in {root}: the design writes it")
    study = json.loads(path.read_text(encoding="utf-8"))
    if study.get("kind") != "study":
        if study.get("kind") == "snapshot":
            raise Refused("study.json is a snapshot: the snapshot checks apply to it, not the study's")
        raise Refused(f"study.json has kind {study.get('kind')!r}; a designed study has kind 'study'")
    return study


def _questions(project):
    return [(d, q) for d in project.get("dimensions") or [] for q in d.get("questions") or []]


def _check_question(q, dim, audience, subject_aliases, problems):
    qid = q.get("key") or "a question of dimension " + str(dim.get("key"))
    for field in ("key", "text", "label"):
        if not _text(q.get(field)):
            problems.append(f"{qid}: {field} must be a non-empty text")
    if not isinstance(q.get("branded"), bool):
        problems.append(f"{qid}: branded must be true or false")
    if q.get("framing") not in FRAMINGS:
        problems.append(f"{qid}: framing must be one of {', '.join(FRAMINGS)}")
    if audience in ("personas", "stakeholders") and not _text(q.get("persona")):
        problems.append(f"{qid}: persona is missing (the audience is {audience})")
    for field, limit in (("label", LABEL), ("text", QUESTION)):
        if _text(q.get(field)) and len(q[field]) > limit:
            problems.append(f"{qid}: {field} is {len(q[field])} characters, over Sentl's limit of {limit}")
    rubric = q.get("rubric")
    if not isinstance(rubric, dict) or set(rubric) != set("12345") or not all(_text(v) for v in rubric.values()):
        problems.append(f"{qid}: rubric needs five anchors, 1 to 5, each a non-empty text")
    else:
        for anchor, text in sorted(rubric.items()):
            if len(text) > ANCHOR:
                problems.append(f"{qid}: rubric anchor {anchor} is {len(text)} characters, over Sentl's limit of {ANCHOR}")
    facts = q.get("facts") or []
    for n, f in enumerate(facts):
        if not isinstance(f, dict) or not _text(f.get("fact")) or not all(_terms(f.get(k, [])) for k in ("current", "outdated")):
            problems.append(f"{qid}: facts[{n}] needs a fact text, and current and outdated as lists of terms")
    if not isinstance(q.get("instructions", ""), str):
        problems.append(f"{qid}: instructions must be a text")
    elif all(isinstance(f, dict) for f in facts):
        size = len(compose_instructions(q.get("instructions", ""), facts))
        if size > INSTRUCTIONS:
            problems.append(f"{qid}: judge instructions are {size} characters with their facts, over Sentl's limit "
                            f"of {INSTRUCTIONS}")
    if q.get("branded") is False and _text(q.get("text")):
        text = fold(q["text"])
        alias = next((a for a in subject_aliases if first_mention(text, [a]) is not None), None)
        if alias:
            problems.append(f"{qid} is marked as naming no brand but contains the alias {alias}")


def _check_project(project, study, model_ids, audience, aliases, problems, warnings):
    key = project.get("key")
    where = f"project {key}"
    for field in ("question", "decision"):
        if not _text(project.get(field)):
            problems.append(f"{where} has no {field}")
    if not _text(project.get("name")):
        problems.append(f"{where}: name must be a non-empty text")
    rounds = project.get("rounds")
    if not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 1:
        problems.append(f"{where}: rounds must be an integer of 1 or more")
    if project.get("schedule") not in SCHEDULES:
        problems.append(f"{where}: schedule must be {', '.join(SCHEDULES[:-1])} or {SCHEDULES[-1]}")
    models = project.get("models")
    if not isinstance(models, list) or not models:
        problems.append(f"{where}: models must list at least one model id")
    else:
        problems += [f"{where}: model {m} is not in list-ai-models" for m in models if m not in model_ids]
    dims = project.get("dimensions") or []
    low, high = DIMENSIONS_PER_PROJECT
    if not low <= len(dims) <= high:
        warnings.append(f"{where} has {len(dims)} dimensions ({low} to {high} are expected)")
    names = {}
    for d in dims:
        dkey = d.get("key")
        if not _text(d.get("name")):
            problems.append(f"dimension {dkey}: name must be a non-empty text")
            continue
        if len(d["name"]) > DIMENSION_NAME:
            problems.append(f"dimension name of {dkey} is {len(d['name'])} characters, over Sentl's limit of "
                            f"{DIMENSION_NAME}")
        if match_key(d["name"]) in names:
            problems.append(f"{where} has two dimensions named {d['name']}")
        names[match_key(d["name"])] = dkey
    for d in dims:
        dkey, questions = d.get("key"), d.get("questions") or []
        if d.get("search_lean", "none") not in LEANS:
            problems.append(f"dimension {dkey}: search_lean must be one of {', '.join(LEANS)}")
        if d.get("axis", "stance") not in AXES:
            problems.append(f"dimension {dkey}: axis must be one of {', '.join(AXES)}")
        if not questions:
            problems.append(f"dimension {dkey} has no question")
        elif len(questions) < 2:
            warnings.append(f"dimension {dkey} has 1 question (two or more are expected)")
        lean = d.get("search_lean", "none")
        if lean in OPPOSITE and not any(q.get("framing") == OPPOSITE[lean] for q in questions):
            problems.append(f"dimension {dkey} leans {lean} but has no question with {OPPOSITE[lean]} framing")
        seen = set()
        for q in questions:
            _check_question(q, d, audience, aliases, problems)
            if _text(q.get("text")):
                if match_key(q["text"]) in seen:
                    problems.append(f"dimension {dkey} has two questions with the same text: {q['text']}")
                seen.add(match_key(q["text"]))
    branded = {q.get("branded") for _, q in _questions(project)} & {True, False}
    if branded == {True, False}:
        warnings.append(f"{where} mixes questions that name the brand with questions that name none: Sentl's "
                        "score for it would blend two readings")
    runs = runs_per_period(project, study.get("report_every"))
    if runs is not None and isinstance(rounds, int) and rounds * runs < ANSWERS_PER_PERIOD:
        warnings.append(f"{where} gives {_count(rounds * runs, 'answer', 'answers')} per question and model in a "
                        f"report period ({ANSWERS_PER_PERIOD} or more are expected)")


def problems_of(study, model_ids):
    """(refusals, warnings) of a designed study."""
    problems, warnings = [], []
    narrative = study.get("narrative") or {}
    for field in ("research_question", "purpose"):
        if not _text(narrative.get(field)):
            problems.append(f"narrative.{field} is missing")
    audience = narrative.get("audience") or {}
    if audience.get("choice") not in AUDIENCES or not _text(audience.get("reason")):
        problems.append(f"narrative.audience needs a choice ({', '.join(AUDIENCES)}) and a reason")
    subject = study.get("subject") or {}
    aliases = list(subject.get("aliases") or [])
    for foil in study.get("foils") or []:
        aliases += foil.get("aliases") or []
    projects = study.get("projects") or []
    if not projects:
        problems.append("the study has no project")
    for project in projects:
        _check_project(project, study, model_ids, audience.get("choice"), aliases, problems, warnings)

    keys = {"project": [], "dimension": [], "question": [], "theme": []}
    for p in projects:
        keys["project"].append(p.get("key"))
        for d in p.get("dimensions") or []:
            keys["dimension"].append(d.get("key"))
            keys["question"] += [q.get("key") for q in d.get("questions") or []]
            keys["question"] += [r.get("key") for r in d.get("retired") or []]
    keys["theme"] = [t.get("id") for t in study.get("themes") or []]
    for kind, found in keys.items():
        for k in sorted({k for k in found if found.count(k) > 1}, key=str):
            problems.append(f"duplicate key {k} among the {kind}s")

    dimension_keys = {d.get("key") for p in projects for d in p.get("dimensions") or []}
    fed = set()
    for t in study.get("themes") or []:
        target = t.get("dimension")
        for dkey in target if isinstance(target, list) else [target]:
            fed.add(dkey)
            if dkey not in dimension_keys:
                problems.append(f"theme {t.get('id')} feeds dimension {dkey}, which no project has")
        origins = t.get("origins") or []
        if not origins or any(o.get("kind") not in ORIGIN_KINDS or not _text(o.get("detail")) for o in origins):
            problems.append(f"theme {t.get('id')} has no origin of a known kind and a detail "
                            f"(kinds: {', '.join(ORIGIN_KINDS)})")
    problems += [f"no theme feeds dimension {k}" for k in sorted(dimension_keys - fed, key=str)]

    pairs = {}
    for p in projects:
        for d, q in _questions(p):
            if q.get("pair"):
                pairs.setdefault(q["pair"], []).append((d.get("key"), q.get("framing")))
    for pair, members in sorted(pairs.items()):
        framings = [f for _, f in members]
        if len(members) != 2:
            problems.append(f"pair {pair} has {_count(len(members), 'question', 'questions')}; a pair has two")
        elif members[0][0] != members[1][0]:
            problems.append(f"pair {pair} spans two dimensions: {members[0][0]} and {members[1][0]}")
        elif framings[0] == framings[1]:
            problems.append(f"pair {pair}: the two questions share a framing")
        elif set(framings) != {"positive", "negative"}:
            problems.append(f"pair {pair}: the two questions must lean opposite ways, positive and negative")
    return problems, warnings


def _model_ids(models_file):
    return schema.models(models_file)


def validate(root, models_file):
    """(text, ok): every refusal, then every warning."""
    study = _load(root)
    problems, warnings = problems_of(study, set(_model_ids(models_file)))
    lines = [f"validate failed: {len(problems)} problem(s)"] if problems else [
        f"validate passed: {_count(len(warnings), 'warning', 'warnings')}"]
    lines += [f"  - {p}" for p in problems] + [f"  warning: {w}" for w in warnings]
    return "\n".join(lines), not problems


# --- review -------------------------------------------------------------------

def _origin(o):
    return f"{o['kind'].replace('_', ' ')}, {o['detail']}"


def _inventory(study, root):
    path = Study(root).path("search-demand.json")
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    summary = demand.summarize(data) if data else {}
    lines = ["## Theme inventory", ""]
    if not data:
        lines += ["No search demand was collected.", ""]
    for t in study["themes"]:
        lines.append(f"- {t['label']} (dimension {t['dimension']}): " + "; ".join(_origin(o) for o in t["origins"]))
        s = summary.get(t["id"])
        if s:
            volume = "; ".join(f"{c} {v}" for c, v in s["volume"].items()) if s["volume"] else "no volume"
            top = "; ".join(q if v is None else f"{q} ({v})" for q, v in s["top"])
            lines.append(f"  - search: {_count(s['suggestions'], 'distinct suggestion', 'distinct suggestions')}, "
                         f"{volume} a month; top queries: {top}")
        elif data:
            lines.append("  - search: nothing collected for this theme")
    return lines + [""]


def _credits(study, models_file):
    tariffs = schema.models(models_file)
    lines = ["## Credit estimate", ""]
    total, total_period = 0, 0
    period_known = True
    for p in study["projects"]:
        missing = [m for m in p["models"] if tariffs[m].get("credits") is None]
        if missing:
            raise Refused(f"list-ai-models gives no credits for {', '.join(missing)}: save the response again")
        per_call = sum(tariffs[m]["credits"] for m in p["models"])
        count = len(_questions(p))
        run = count * p["rounds"] * per_call
        runs = runs_per_period(p, study.get("report_every"))
        line = (f"- project {p['key']}: {run:g} credits per run ({_count(count, 'question', 'questions')} x "
                f"{_count(p['rounds'], 'round', 'rounds')} x {per_call:g} credits across {len(p['models'])} models)")
        if runs is not None:
            line += f"; {run * runs:g} credits per report period ({_count(runs, 'run', 'runs')})"
            total_period += run * runs
        else:
            period_known = False
        total += run
        lines.append(line)
    lines.append(f"- all projects: {total:g} credits per run" + (f"; {total_period:g} credits per report period"
                                                                  if period_known else ""))
    lines += ["", "Judging costs no credits; estimate-run-tool gives the total before a run starts.", ""]
    return lines


def question_lines(study):
    """The review's Questions section: every question with its persona, framing, rubric and the
    judge instructions as Sentl receives them."""
    out = ["## Questions", ""]
    for p in study["projects"]:
        for d in p["dimensions"]:
            out += [f"### {p['name']}: {d['name']}", ""]
            for q in d["questions"]:
                out += [f"**{q['key']}** {q['text']}", "",
                        f"- persona: {q.get('persona') or 'none'}; framing: {q['framing']}; names the brand: "
                        f"{'yes' if q['branded'] else 'no'}" + (f"; pair: {q['pair']}" if q.get("pair") else ""),
                        "- rubric:"]
                out += [f"  {a}. {q['rubric'][a]}" for a in "12345"]
                text = compose_instructions(q.get("instructions"), q.get("facts"))
                out += [f"- judge instructions as Sentl receives them: {text or 'none'}", ""]
    return out


def review_text(study, root, models_file):
    names = schema.models(models_file)
    audience = study["narrative"]["audience"]
    narrative = study["narrative"]
    out = [f"# Study review: {study['subject']['label']}", "", "## Narrative", "",
           f"- Research question: {narrative['research_question']}", f"- Purpose: {narrative['purpose']}",
           f"- Audience: {audience['choice']}. {audience['reason']}"]
    if narrative.get("criteria"):
        out.append(f"- Rubrics written by: {narrative['criteria'].get('by')} ({narrative['criteria'].get('date')})")
    if narrative.get("score_axis"):
        out.append(f"- Score axis: {narrative['score_axis']}")
    out += [f"- Design choice: {c['choice']}. {c['reason']}" for c in narrative.get("design_rationale") or []]
    out.append("")
    out += _inventory(study, root)
    out += ["## Projects and dimensions", ""]
    for p in study["projects"]:
        out += [f"### {p['name']} ({p['key']})", "", f"- Question: {p['question']}", f"- Decision: {p['decision']}",
                f"- Models: {', '.join(public_name(m, names) for m in p['models'])}",
                f"- Rounds: {p['rounds']}; schedule: {p['schedule']}", "- Dimensions:"]
        for d in p["dimensions"]:
            out.append(f"  - {d['name']}: {_count(len(d['questions']), 'question', 'questions')} "
                       f"(search leans {d.get('search_lean', 'none')}; axis {d.get('axis', 'stance')})")
        out.append("")
    out += question_lines(study)
    out += _credits(study, models_file)
    return "\n".join(out).rstrip() + "\n"


def review(root, models_file):
    study = _load(root)
    problems, _ = problems_of(study, set(_model_ids(models_file)))
    if problems:
        raise Refused("study.json fails validate, so there is nothing to review yet:\n  - " + "\n  - ".join(problems))
    text = review_text(study, root, models_file)
    write_text(Study(root).path("study-review.md"), text)
    return text.rstrip()


# --- revision -----------------------------------------------------------------

def _criteria(q):
    return (criteria_hash(q.get("rubric"), q.get("instructions")), json.dumps(q.get("facts") or [], sort_keys=True))


def _index(study):
    return {q["key"]: q for p in study["projects"] for d in p["dimensions"] for q in d["questions"]}


def revise(old, new, new_intent=()):
    """(study, changes, notes): `new` with the lineage of each question set from `old`. A reworded
    question keeps its key; one in `new_intent` gets the next free key and its old key is retired
    in the dimension; a question missing from `new` is retired."""
    study = copy.deepcopy(new)
    before = _index(old)
    versions = [e.get("version", 1) for q in before.values() for e in q.get("lineage") or []]
    number = max(versions, default=1) + 1
    taken = {q["key"] for q in _index(study).values()} | set(before) | {
        r["key"] for p in old["projects"] for d in p["dimensions"] for r in d.get("retired") or []}
    changes, notes, replaced = [], [], set()

    def free(dkey):
        n = 1
        while f"{dkey}-{n}" in taken:
            n += 1
        taken.add(f"{dkey}-{n}")
        return f"{dkey}-{n}"

    for p in study["projects"]:
        for d in p["dimensions"]:
            retired = list(d.get("retired") or [])
            for n, q in enumerate(d["questions"]):
                was = before.get(q["key"])
                if was is None:
                    q["lineage"] = [{"version": number, "change": "created"}]
                    changes.append(f"{q['key']} created: «{q['text']}»")
                    continue
                lineage = list(was.get("lineage") or [])
                if match_key(q["text"]) != match_key(was["text"]) and q["key"] in new_intent:
                    key = free(d["key"])
                    retired.append({"key": was["key"], "text": was["text"], "version": number})
                    replaced.add(was["key"])
                    d["questions"][n] = {**q, "key": key,
                                         "lineage": [{"version": number, "change": "new_intent", "replaces": was["key"]}]}
                    changes.append(f"{key} replaces {was['key']} as a new question: «{q['text']}»")
                    continue
                if match_key(q["text"]) != match_key(was["text"]):
                    lineage.append({"version": number, "change": "reworded"})
                    changes.append(f"{q['key']} reworded: «{was['text']}» → «{q['text']}»")
                if _criteria(q) != _criteria(was):
                    lineage.append({"version": number, "change": "criteria"})
                    changes.append(f"{q['key']}: rubric, judge instructions or facts changed")
                q["lineage"] = lineage
            kept = {q["key"] for q in d["questions"]} | {r["key"] for r in retired}
            previous = {q["key"]: q for pp in old["projects"] if pp["key"] == p["key"]
                        for dd in pp["dimensions"] if dd["key"] == d["key"] for q in dd["questions"]}
            for key, was in previous.items():
                if key not in kept:
                    retired.append({"key": key, "text": was["text"], "version": number})
                    changes.append(f"{key} retired: «{was['text']}»")
            if retired:
                d["retired"] = retired
    notes = [f"--new-intent {k} ignored: {k} was not reworded." for k in sorted(set(new_intent) - replaced)]
    return study, changes, notes


def revise_files(root, previous_file, new_intent=(), dry_run=False):
    path = Study(root).path("study.json")
    new = _load(root)
    old = json.loads(open(previous_file, encoding="utf-8").read())
    study, changes, notes = revise(old, new, set(new_intent))
    if not changes:
        return "\n".join(["Study unchanged since the previous design."] + notes)
    versions = [e["version"] for q in _index(study).values() for e in q["lineage"]]
    lines = [f"Design version {max(versions)}. Changes (the operator confirms each classification):"]
    lines += [f"  {c}" for c in changes] + notes
    if dry_run:
        return "\n".join(lines + ["Dry run: nothing written."])
    write_json(path, study)
    return "\n".join(lines + ["The lineage is recorded in study.json."])
