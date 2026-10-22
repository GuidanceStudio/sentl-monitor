"""A fictional designed study, valid under `validate`, that the design tests change one fact at a time."""

import copy

from fixtures import GEM, GPT

LONG = "x" * 600


def rubric(branded):
    two = "Gives a doubtful or mixed account of the brand" if branded else "Does not mention the brand"
    return {"1": "Names the brand negatively or advises against it", "2": two, "3": "Mentions the brand without a verdict", "4": "Favourable, no grounds given",
            "5": "Favourable, with grounds from a named source"}


def question(key, text, framing="neutral", branded=True, pair=None, facts=None, instructions=""):
    item = {"key": key, "label": text[:40], "text": text, "branded": branded, "framing": framing,
            "persona": "a shopper comparing plant drinks", "rubric": rubric(branded),
            "instructions": instructions, "lineage": [{"version": 1, "change": "created"}]}
    if pair:
        item["pair"] = pair
    if facts:
        item["facts"] = facts
    return item


PRICE_FACT = {"fact": "Avenello Original costs 2.10 USD per litre", "source": "https://avenello.example/prices",
              "date": "2026-10-01", "current": ["2.10"], "outdated": ["1.90"]}

BRAND = [
    ("health", "Health", "negative", [
        ("Is Avenello oat milk bad for you?", "negative", "health-a"),
        ("Is Avenello oat milk good for your health?", "positive", "health-a")]),
    ("price", "Price", "none", [
        ("How much does Avenello oat milk cost?", "neutral", None),
        ("Is Avenello oat milk worth the price?", "neutral", None)]),
    ("taste", "Taste", "none", [
        ("What does Avenello oat milk taste like?", "neutral", None),
        ("Does Avenello oat milk work in coffee?", "neutral", None)]),
    ("environment", "Environment", "none", [
        ("Is Avenello oat milk good for the environment?", "neutral", None),
        ("How much water does Avenello oat milk use?", "neutral", None)]),
    ("availability", "Availability", "none", [
        ("Where can I buy Avenello oat milk?", "neutral", None),
        ("Is Avenello oat milk sold in my supermarket?", "neutral", None)]),
]

CATEGORY = [
    ("c-health", "Health", [("Is oat milk bad for you?", "negative"), ("Is oat milk healthy for children?", "positive")]),
    ("c-price", "Price", [("How much does oat milk cost per carton?", "neutral"), ("Which oat milk is the cheapest?", "neutral")]),
    ("c-taste", "Taste", [("Which oat milk tastes best?", "neutral"), ("Which oat milk is best in coffee?", "neutral")]),
    ("c-environment", "Environment", [("Is oat milk good for the environment?", "neutral"),
                                      ("Which oat milk brand is the most sustainable?", "neutral")]),
    ("c-availability", "Availability", [("Where can I buy oat milk online?", "neutral"),
                                        ("Which supermarkets sell oat milk?", "neutral")]),
]


def _project(key, name, question_, decision, dimensions):
    return {"key": key, "name": name, "question": question_, "decision": decision, "models": [GPT, GEM],
            "rounds": 1, "schedule": "weekly", "dimensions": dimensions}


def clean_study():
    brand_dims = []
    for dkey, name, lean, items in BRAND:
        qs = []
        for n, (text, framing, pair) in enumerate(items, 1):
            facts = [dict(PRICE_FACT)] if dkey == "price" and n == 1 else None
            instr = "Score 1 when the answer states an outdated price." if facts else ""
            qs.append(question(f"{dkey}-{n}", text, framing, True, pair, facts, instr))
        brand_dims.append({"key": dkey, "name": name, "search_lean": lean, "axis": "stance", "questions": qs})
    category_dims = [{"key": dkey, "name": name, "search_lean": "none", "axis": "stance",
                      "questions": [question(f"{dkey}-{n}", text, framing, False)
                                    for n, (text, framing) in enumerate(items, 1)]}
                     for dkey, name, items in CATEGORY]
    themes = [{"id": d["key"], "label": d["name"], "dimension": d["key"],
               "origins": [{"kind": "client_issue", "detail": "Customer-service questions, 2026"}]}
              for d in brand_dims + category_dims]
    return {
        "schema": "sentl-monitor/study@1", "kind": "study",
        "subject": {"id": "avenello", "label": "Avenello", "kind": "brand", "aliases": ["Avenello", "Avenello Oat"],
                    "owned_domains": ["avenello.example"]},
        "foils": [{"id": "avoria", "label": "Avoria", "aliases": ["Avoria"], "domains": ["avoria.example"]},
                  {"id": "dairy", "label": "dairy milk", "aliases": ["dairy milk", "cow's milk"]}],
        "components": [{"id": "oat-drink", "label": "oat drink", "terms": ["oat milk", "oat drink"]}],
        "market": {"country": "US", "language": "en"},
        "report_language": "en", "report_every": "monthly", "organization": "example-org",
        "narrative": {
            "criteria": {"by": "the Avenello marketing team", "date": "2026-09-15"},
            "research_question": "What are people who ask an AI assistant about oat milk told about it and about Avenello?",
            "purpose": "Find what assistants say to a shopper choosing a plant drink, to decide which pages to write.",
            "audience": {"choice": "personas", "reason": "A parent and an athlete ask different things about one product."},
            "design_rationale": [{"choice": "Two projects: with the brand and without it",
                                  "reason": "The first is read by mean score, the second by how often Avenello is named."}],
            "score_axis": "stance"},
        "themes": themes,
        "projects": [
            _project("brand", "Avenello · With the brand", "What do people hear about Avenello once they name it?",
                     "Which claims on product pages to correct", brand_dims),
            _project("category", "Avenello · Without the brand", "Is Avenello named when people ask about oat milk?",
                     "Which topics to write pages for", category_dims)]}


def mutated(change):
    """A clean study after `change(study)` has altered it."""
    study = copy.deepcopy(clean_study())
    change(study)
    return study


def search_demand():
    return {"schema": "sentl-monitor/search-demand@1", "market": {"country": "US", "language": "en"},
            "themes": {"health": {"seeds": ["oat milk bad for you"], "volumes": [], "autocomplete": [
                {"prefix": "oat milk bad", "suggestions": ["oat milk bad for you", "oat milk bad for kidneys"],
                 "source": "google autocomplete hl=en gl=US", "collected": "2026-10-16"}]}},
            "volume_source": None}
