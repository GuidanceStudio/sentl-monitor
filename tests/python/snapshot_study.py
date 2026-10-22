"""A fictional snapshot study, valid under `validate`, with the Sentl responses of its project and its run."""

import copy

from design_study import PRICE_FACT, question
from fixtures import GEM, GPT

from sentlmon.design import compose_instructions

PROJECT_ID = 900
RUN_ID = 7001
KEY = "snapshot"
DATE = "2026-10-22"
RUN_STARTED = "2026-10-22T09:00:00Z"
BOUND_AT = "2026-10-22T08:00:00Z"

# (key, name, catalogue id, question, names the brand, axis, what it measures)
DIMENSIONS = [
    ("reputation", "Reputation", "reputation", "What do people say about Avenello oat milk?", True, "stance",
     "how the assistants describe Avenello to someone who names it"),
    ("recommendation", "Recommendation", "recommendation", "What is the best oat milk to buy in the US?", False,
     "stance", "whether and where the assistants name Avenello when nobody asks for it"),
    ("price", "Price", "price", "How much does Avenello oat milk cost?", True, "fidelity",
     "whether the assistants give the price the brand's page states"),
    ("health", "Health", "health-safety", "Is Avenello oat milk bad for you?", True, "stance",
     "whether the assistants raise a health concern about Avenello"),
]

# (dimension key, model) -> score; the project mean, 3.375, is not the mean of any dimension.
SCORES = {("reputation", GPT): 4, ("reputation", GEM): 4, ("recommendation", GPT): 3, ("recommendation", GEM): 2,
          ("price", GPT): 5, ("price", GEM): 3, ("health", GPT): 3, ("health", GEM): 3}

ANSWERS = {
    ("reputation", GPT): "Avenello oat milk is well regarded for its mild taste and smooth texture.",
    ("reputation", GEM): "Avenello oat milk gets favourable reviews, mostly for its use in coffee.",
    ("recommendation", GPT): "Avoria is a common pick, and Avenello is another option worth trying.",
    ("recommendation", GEM): "Several brands sell good oat milk, such as Avoria and store brands.",
    ("price", GPT): "Avenello oat milk costs about 2.10 USD per litre in most US supermarkets.",
    ("price", GEM): "Avenello oat milk usually costs around two dollars a litre.",
    ("health", GPT): "Avenello oat milk is not bad for you when drunk in moderation.",
    ("health", GEM): "Avenello oat milk has added sugar in some versions, so check the label.",
}


def dimension(key, name, catalogue, text, branded=True, axis="stance", measures="what it measures"):
    facts = [dict(PRICE_FACT)] if catalogue == "price" else None
    instructions = "Score 1 when the answer states an outdated price." if facts else ""
    item = question(f"{key}-1", text, "neutral", branded, None, facts, instructions)
    return {"key": key, "catalogue": catalogue, "name": name, "axis": axis, "measures": measures, "questions": [item]}


def clean_snapshot():
    dims = [dimension(k, n, c, t, b, a, m) for k, n, c, t, b, a, m in DIMENSIONS]
    return {
        "schema": "sentl-monitor/study@1", "kind": "snapshot",
        "subject": {"id": "avenello", "label": "Avenello", "kind": "brand", "aliases": ["Avenello", "Avenello Oat"],
                    "owned_domains": ["avenello.example"]},
        "foils": [{"id": "avoria", "label": "Avoria", "aliases": ["Avoria"], "domains": ["avoria.example"]}],
        "components": [{"id": "oat-drink", "label": "oat drink", "terms": ["oat milk", "oat drink"]}],
        "market": {"country": "US", "language": "en"},
        "report_language": "en", "organization": "example-org",
        "narrative": {
            "criteria": {"by": "the Avenello marketing team", "date": "2026-10-22"},
            "research_question": "What does an AI assistant tell a shopper about Avenello oat milk?",
            "purpose": "A first look at what assistants say about Avenello, before deciding on a monitoring study.",
            "design_rationale": [{"choice": d["name"], "reason": f"the reader decides on {d['name'].lower()} pages"}
                                 for d in dims]},
        "themes": [],
        "projects": [{"key": KEY, "name": f"Snapshot · Avenello · {DATE}",
                      "question": "What do assistants say about Avenello today?",
                      "decision": "Whether a monitoring study is worth setting up",
                      "models": [GPT, GEM], "rounds": 1, "dimensions": dims}]}


def mutated(change):
    """A clean snapshot after `change(study)` has altered it."""
    study = copy.deepcopy(clean_snapshot())
    change(study)
    return study


def extra_dimension(n):
    return dimension(f"extra-{n}", f"Extra {n}", "reputation", f"What do shoppers think of Avenello oat milk, take {n}?")


def saved_project(study, project_id=PROJECT_ID, edit=None, first_id=1000):
    """The get-project-tool response of the snapshot project once its questions are saved."""
    project = study["projects"][0]
    next_id, dimensions = first_id, []
    for d in project["dimensions"]:
        did, next_id = next_id, next_id + 1
        questions = []
        for q in d["questions"]:
            qid, next_id = next_id, next_id + 1
            questions.append({"id": qid, "label": q["label"], "question": q["text"], "grading_rubric": dict(q["rubric"]),
                              "additional_instructions": compose_instructions(q.get("instructions"), q.get("facts"))})
        dimensions.append({"id": did, "name": d["name"], "archived": False, "questions": questions})
    data = {"project": {"id": project_id, "name": project["name"], "organization": "example-org",
                        "schedule_frequency": None, "rounds": project["rounds"], "is_active": False,
                        "researcher_model_ids": list(project["models"]), "dimensions": dimensions}}
    if edit:
        edit(data["project"])
    return data


def run_results(study, run_id=RUN_ID, project_id=PROJECT_ID, started=RUN_STARTED, scores=None, status="completed"):
    """The get-run-results-tool response of the one run: every question answered by both models."""
    scores = SCORES if scores is None else scores
    responses, n = [], run_id * 100
    for d in study["projects"][0]["dimensions"]:
        q = d["questions"][0]
        for model in (GPT, GEM):
            n += 1
            responses.append({"id": n, "model_id": model, "question": q["text"], "dimension": d["name"],
                              "answer": ANSWERS[(d["key"], model)], "judge_score": scores.get((d["key"], model)),
                              "sentiment": "neutral", "sources": [{"url": "https://guide.example/oat", "title": "guide"}]})
    return {"run": {"id": run_id, "project_id": project_id, "organization": "example-org", "status": status,
                    "trigger": "manual", "reputation_score": 3.4, "error": None, "started_at": started,
                    "finished_at": started, "responses": responses}}
