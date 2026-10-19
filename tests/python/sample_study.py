"""The fictional study behind the sample report in examples/ (README, "A sample report").

`build(folder)` runs the steps a reader's assistant runs: `adopt` on the project and its latest
run, the operator's answers written into study.json, `ingest` of fourteen daily runs, then
`period` and `method` for the report date. The findings, the changes and the summary of the
sample report were written from the material this leaves in `history/material/`, as
`report/REPORT.md` says, and `check` passes on it.

To rewrite the sample after a change to the pipeline, build the study in an empty folder:

    python3 tests/python/sample_study.py <folder>

Every name, text and domain is invented; the models are the fixtures' fictional ones.
"""

import contextlib
import copy
import datetime as dt
import io
import json
import sys
from pathlib import Path

from fixtures import GEM, GPT, clock, models, monitor

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"
DATE = "2026-10-14"
REPORT = EXAMPLES / f"avenello-report-{DATE}.md"
CHARTS = EXAMPLES / f"avenello-report-{DATE}.charts.md"
ADOPTED = f"{DATE}T09:00:00Z"
PROJECT_ID = 701
FIRST_RUN = 9401

SUGAR_Q = "How much sugar is in Avenello oat milk?"
BEST_Q = "What is the best oat milk to buy?"
GREEN_Q = "Is Avenello oat milk good for the environment?"

DIMENSIONS = [
    (41, "Nutrition", 811, SUGAR_Q, {
        "1": "States a sugar content that is wrong and presents it as current",
        "2": "States the sugar content of the old recipe",
        "3": "Gives no figure, or a figure without saying which product",
        "4": "States the current sugar content",
        "5": "States the current sugar content and cites Avenello's nutrition page",
    }, "Fact: Avenello Original has 3 g of sugar per 100 ml since the March 2026 recipe; it had 5 g before "
       "(avenello.example/nutrition, 2026-09-15)."),
    (42, "Choice", 812, BEST_Q, {
        "1": "Advises against Avenello",
        "2": "Does not mention Avenello",
        "3": "Mentions Avenello without recommending it",
        "4": "Recommends Avenello among others",
        "5": "Recommends Avenello first, with a reason",
    }, ""),
    (43, "Sustainability", 813, GREEN_Q, {
        "1": "Says Avenello harms the environment, without a source",
        "2": "Doubts Avenello's environmental claims",
        "3": "Speaks of oat milk in general, not of Avenello",
        "4": "Says Avenello's footprint is lower than dairy's",
        "5": "Says so and cites Avenello's published figures",
    }, ""),
]
DIMENSION_OF = {question: name for _, name, _, question, _, _ in DIMENSIONS}


def project():
    """The get-project-tool response: one project, three dimensions of one question each,
    two assistants, three rounds, a run every day."""
    return {"project": {
        "id": PROJECT_ID, "name": "Avenello · US market", "organization": "example-org",
        "schedule_frequency": "daily", "rounds": 3, "is_active": True,
        "researcher_model_ids": [GPT, GEM],
        "latest_run": {"id": FIRST_RUN + 13, "status": "completed"},
        "dimensions": [
            {"id": did, "name": name, "color": "#2f6f4f", "sort": n, "archived": False,
             "questions": [{"id": qid, "label": text[:40], "question": text, "grading_rubric": rubric,
                            "additional_instructions": instructions}]}
            for n, (did, name, qid, text, rubric, instructions) in enumerate(DIMENSIONS, 1)],
    }}


# Answers as (text, judge score, cited urls). Acme Chat quotes the old sugar figure until
# 9 October and the current one from 10 October; Orbit Reason names Avenello for the best oat
# milk from 9 October, cites no Avenello page on sugar on 4 and 6 October, and cites Avenello's
# own footprint figures on even days.
OLD_SUGAR = ("Avenello Original contains about 5 g of sugar per 100 ml, mostly from the oats themselves. "
             "That is less than most sweetened oat milks but more than the unsweetened ones.",
             2, ["https://nutrition.example/oat-milks-compared", "https://reviews.example/avenello-original"])
NEW_SUGAR_ACME = ("Since its 2026 recipe change, Avenello Original has 3 g of sugar per 100 ml, "
                  "according to the brand's nutrition page.",
                  5, ["https://www.avenello.example/nutrition", "https://nutrition.example/oat-milks-compared"])
NEW_SUGAR_ORBIT = ("Avenello Original has 3 g of sugar per 100 ml. The sugar comes from the enzymatic "
                   "breakdown of the oats; none is added.",
                   5, ["https://www.avenello.example/nutrition"])
UNCITED_SUGAR_ORBIT = ("Avenello Original has around 3 g of sugar per 100 ml, less than most sweetened oat milks.",
                       4, ["https://nutrition.example/oat-milks-compared"])
BEST_WITHOUT = ("Avoria Barista is the oat milk most often recommended in comparisons: it froths well and is "
                "easy to find. Unsweetened store brands are the cheaper choice.",
                2, ["https://avoria.example/barista", "https://ranking.example/oat-milk-2026"])
BEST_ORBIT_WITHOUT = ("Avoria Barista and Avoria Original lead most rankings of oat milks for taste and for "
                      "coffee. Check the label for added sugar and oils.",
                      2, ["https://avoria.example/compare", "https://ranking.example/oat-milk-2026"])
BEST_WITH = ("Avoria Barista and Avenello Original are the two oat milks most often recommended. "
             "Avenello has less sugar; Avoria froths better for coffee.",
             4, ["https://ranking.example/oat-milk-2026", "https://www.avenello.example/nutrition"])
GREEN_ACME = ("Avenello reports that a litre of its oat milk emits about a third of the CO2 of a litre of "
              "cow's milk, in its 2025 sustainability report. Oat drinks also need less land and water than dairy.",
              4, ["https://www.avenello.example/sustainability", "https://climate.example/oat-vs-dairy"])
GREEN_ORBIT = ("Oat milks generally have a lower footprint than dairy milk: less land, less water and fewer "
               "emissions per litre. Avenello's own figures are published by the company and not "
               "independently verified.",
               3, ["https://climate.example/oat-vs-dairy"])
GREEN_ORBIT_FIGURES = ("According to its 2025 sustainability report, Avenello's oat milk emits about a third of the "
                       "CO2 of cow's milk per litre. Oat milks in general need less land and water than dairy.",
                       4, ["https://www.avenello.example/sustainability", "https://climate.example/oat-vs-dairy"])


def answers_of(day):
    """Day `day`'s answer per question and assistant (1 = 1 October 2026)."""
    return {
        (SUGAR_Q, GPT): NEW_SUGAR_ACME if day >= 10 else OLD_SUGAR,
        (SUGAR_Q, GEM): UNCITED_SUGAR_ORBIT if day in (4, 6) else NEW_SUGAR_ORBIT,
        (BEST_Q, GPT): BEST_WITHOUT,
        (BEST_Q, GEM): BEST_WITH if day >= 9 else BEST_ORBIT_WITHOUT,
        (GREEN_Q, GPT): GREEN_ACME,
        (GREEN_Q, GEM): GREEN_ORBIT_FIGURES if day % 2 == 0 else GREEN_ORBIT,
    }


def started(day):
    return f"{dt.date(2026, 10, 1) + dt.timedelta(days=day - 1)}T06:00:00Z"


def run(day):
    """The get-run-results-tool response of day `day`'s run: three rounds, each the same answer."""
    run_id = FIRST_RUN + day - 1
    responses = []
    for _ in range(3):
        for (question, model), (answer, score, urls) in answers_of(day).items():
            responses.append({
                "id": run_id * 100 + len(responses) + 1, "model_id": model, "question": question,
                "dimension": DIMENSION_OF[question], "answer": answer, "judge_score": score,
                "sentiment": "positive" if score >= 4 else "negative" if score <= 2 else "neutral",
                "sources": [{"url": u, "title": u.rsplit("/", 1)[-1]} for u in urls],
            })
    when = started(day)
    return {"run": {
        "id": run_id, "project_id": PROJECT_ID, "organization": "example-org", "status": "completed",
        "trigger": "scheduled", "reputation_score": None, "error": None,
        "started_at": when, "finished_at": when.replace("T06", "T07"), "responses": responses,
    }}


# What the operator answers when `adopt` asks for what Sentl does not hold (ADOPT.md step 6).
ANSWERS = {
    "narrative": {
        "research_question": "What are people who ask an AI assistant about oat milk told about it and about Avenello?",
        "purpose": "Find the facts about Avenello that assistants state wrongly and the pages they take them from, "
                   "to decide which pages to update.",
        "audience": {"choice": "generic_consumer",
                     "reason": "The questions are the ones any shopper types; no persona changes them."},
        "criteria": {"by": "Avenello's marketing team", "date": "2026-09-15"},
    },
    "subject": {"label": "Avenello", "kind": "brand", "aliases": ["Avenello"], "owned_domains": ["avenello.example"]},
    "foils": [{"id": "avoria", "label": "Avoria", "aliases": ["Avoria"], "domains": ["avoria.example"]}],
    "market": {"country": "US", "language": "en"},
    "report_language": "en",
    "report_every": "weekly",
}
ORIGINS = {
    "nutrition": [{"kind": "client_issue", "detail": "Customer-service questions about the new recipe, 2026"}],
    "choice": [{"kind": "search", "detail": "Google autocomplete, United States, September 2026"}],
    "sustainability": [{"kind": "client_material", "detail": "Avenello sustainability report 2025"}],
}
FACTS = {
    "nutrition-1": [{"fact": "Avenello Original has 3 g of sugar per 100 ml since the March 2026 recipe; it had 5 g before.",
                     "source": "https://www.avenello.example/nutrition", "date": "2026-09-15",
                     "current": ["3 g"], "outdated": ["5 g"]}],
}


def cli(*args, at=None):
    """monitor.py's main() in-process; returns (exit code, output)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), \
            (clock(at) if at else contextlib.nullcontext()):
        try:
            code = monitor.main([str(a) for a in args])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue()


def must(*args, at=None):
    code, out = cli(*args, at=at)
    if code != 0:
        raise RuntimeError(f"monitor.py {args[0]} exited {code}:\n{out}")
    return out


def answer(study):
    """Writes the operator's answers into study.json, changing only those fields."""
    path = study / "study.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for field, value in ANSWERS.items():
        if field == "narrative":
            data["narrative"].update(copy.deepcopy(value))
        else:
            data[field] = copy.deepcopy(value)
    for theme in data["themes"]:
        theme["origins"] = copy.deepcopy(ORIGINS[theme["id"]])
    for proj in data["projects"]:
        for dim in proj["dimensions"]:
            for question in dim["questions"]:
                if question["key"] in FACTS:
                    question["facts"] = copy.deepcopy(FACTS[question["key"]])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save(study, name, data):
    path = study / "inbox" / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def build(study):
    """The sample study in the folder `study`, up to `method` for the report date: reports/<DATE>.md
    holds the outline with its markers, history/material/<DATE>.md the material."""
    study = Path(study)
    (study / "inbox").mkdir(parents=True, exist_ok=True)
    latest = save(study, f"run-{FIRST_RUN + 13}.json", run(14))
    must("adopt", "--study", study, "--project", save(study, f"project-{PROJECT_ID}.json", project()),
         "--run", latest, "--key", "market", at=ADOPTED)
    answer(study)
    for day in range(1, 15):
        path = latest if day == 14 else save(study, f"run-{FIRST_RUN + day - 1}.json", run(day))
        must("ingest", "--study", study, "--project", "market", "--results", path, at=ADOPTED)
    names = save(study, "models.json", models())
    must("period", "--study", study, "--date", DATE, "--models", names, at=ADOPTED)
    must("method", "--study", study, "--date", DATE, "--models", names, at=ADOPTED)
    return study


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 tests/python/sample_study.py <empty folder>")
    folder = Path(sys.argv[1])
    if folder.exists() and any(folder.iterdir()):
        sys.exit(f"{folder} is not empty")
    build(folder)
    print(f"Built the sample study in {folder}: the outline is reports/{DATE}.md, "
          f"the material history/material/{DATE}.md.")
