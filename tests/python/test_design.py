"""The design route's script: `validate` (every refusal and warning), the judge instructions composed
from instructions and dated facts, `review`, and the lineage `revise` records."""

import json
import re
import unittest

from design_study import LONG, PRICE_FACT, clean_study, mutated, search_demand
from fixtures import GEM, GPT, NEW, REPO, StudyCase, models

from sentlmon import design


def dim(study, project, key):
    return next(d for d in study["projects"][0 if project == "brand" else 1]["dimensions"] if d["key"] == key)


def q(study, key):
    return next(x for p in study["projects"] for d in p["dimensions"] for x in d["questions"] if x["key"] == key)


class DesignCase(StudyCase):

    def put(self, study):
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.models = self.save("models.json", models())

    def validate(self, study, models_data=None):
        self.put(study)
        if models_data is not None:
            self.models = self.save("models.json", models_data)
        return self.cli("validate", "--study", self.study, "--models", self.models)


def drop_theme(study, key):
    study["themes"] = [t for t in study["themes"] if t["id"] != key]


def drop_dimension(study, key):
    study["projects"][0]["dimensions"] = [d for d in study["projects"][0]["dimensions"] if d["key"] != key]
    drop_theme(study, key)


def set_(path, value):
    def change(study):
        target = study
        for step in path[:-1]:
            target = target[step]
        target[path[-1]] = value
    return change


def twin_neutral(study):
    twin = q(study, "health-2")
    twin["framing"] = "neutral"
    twin.pop("pair")
    q(study, "health-1").pop("pair")


REFUSALS = {
    "a question without its text": (lambda s: q(s, "health-1").pop("text"), "health-1: text"),
    "rounds below one": (set_(["projects", 0, "rounds"], 0), "rounds"),
    "a schedule Sentl does not offer": (set_(["projects", 0, "schedule"], "hourly"), "schedule"),
    "a dimension name over 100 characters": (set_(["projects", 0, "dimensions", 0, "name"], LONG[:101]),
                                             "dimension name"),
    "a question label over 100 characters": (set_(["projects", 0, "dimensions", 0, "questions", 0, "label"], LONG[:101]),
                                             "health-1: label is 101 characters"),
    "a question over 500 characters": (lambda s: q(s, "health-1").update(text=LONG[:501]),
                                       "health-1: text is 501 characters"),
    "a rubric anchor over 300 characters": (lambda s: q(s, "health-1")["rubric"].update({"3": LONG[:301]}),
                                            "health-1: rubric anchor 3 is 301 characters"),
    "judge instructions over 500 characters": (lambda s: q(s, "health-1").update(instructions=LONG[:501]),
                                               "health-1: judge instructions"),
    "instructions that overflow only with their facts": (lambda s: q(s, "price-1").update(instructions=LONG[:470]),
                                                         "price-1: judge instructions"),
    "a dimension with no question": (lambda s: dim(s, "brand", "taste").update(questions=[]), "taste has no question"),
    "a dimension fed by no theme": (lambda s: drop_theme(s, "price"), "no theme feeds dimension price"),
    "a theme with no origin": (lambda s: next(t for t in s["themes"] if t["id"] == "price").update(origins=[]),
                               "theme price has no origin"),
    "an origin of an unknown kind": (lambda s: next(t for t in s["themes"] if t["id"] == "price")
                                     .update(origins=[{"kind": "rumour", "detail": "x"}]), "theme price has no origin"),
    "an alias of the subject in a question marked as naming no brand": (
        lambda s: q(s, "c-price-1").update(text="How much does Avenello cost per carton?"),
        "c-price-1 is marked as naming no brand but contains the alias Avenello"),
    "an alias of a foil in a question marked as naming no brand": (
        lambda s: q(s, "c-price-2").update(text="Is oat milk cheaper than dairy milk?"),
        "c-price-2 is marked as naming no brand but contains the alias dairy milk"),
    "search_lean negative without a positive question": (twin_neutral, "health leans negative but has no question"),
    "search_lean positive without a negative question": (
        lambda s: dim(s, "brand", "price").update(search_lean="positive"), "price leans positive but has no question"),
    "a pair across two dimensions": (lambda s: q(s, "price-1").update(pair="health-a", framing="neutral"),
                                     "pair health-a"),
    "a pair whose questions share a framing": (lambda s: q(s, "health-2").update(framing="negative"),
                                               "pair health-a: the two questions share a framing"),
    "a pair with one question": (lambda s: q(s, "health-2").pop("pair"), "pair health-a has 1 question"),
    "a duplicate question key": (lambda s: q(s, "taste-2").update(key="taste-1"), "duplicate key taste-1"),
    "a duplicate dimension key": (lambda s: dim(s, "brand", "taste").update(key="price"), "duplicate key price"),
    "a duplicate project key": (lambda s: s["projects"][1].update(key="brand"), "duplicate key brand"),
    "a key retired earlier and used again": (
        lambda s: dim(s, "brand", "taste").update(retired=[{"key": "taste-2", "text": "Old", "version": 2}]),
        "duplicate key taste-2"),
    "two questions with one text in a dimension": (
        lambda s: q(s, "taste-2").update(text="what does  Avenello oat milk taste like?"),
        "taste has two questions with the same text"),
    "two dimensions with one name in a project": (lambda s: dim(s, "brand", "taste").update(name="price"),
                                                  "two dimensions named price"),
    "a model Sentl no longer offers": (set_(["projects", 0, "models"], [GPT, "oldco/legacy-7b"]),
                                       "oldco/legacy-7b is not in list-ai-models"),
    "a narrative without a research question": (lambda s: s["narrative"].pop("research_question"),
                                                "narrative.research_question"),
    "a narrative without a purpose": (set_(["narrative", "purpose"], " "), "narrative.purpose"),
    "an audience without its reason": (set_(["narrative", "audience"], {"choice": "personas", "reason": ""}),
                                       "narrative.audience"),
    "an audience that is not one of the four": (set_(["narrative", "audience", "choice"], "everyone"),
                                                "narrative.audience"),
    "a persona missing when personas ask": (lambda s: q(s, "price-1").pop("persona"), "price-1: persona"),
    "a project without its question": (lambda s: s["projects"][0].pop("question"), "project brand has no question"),
    "a project without its decision": (set_(["projects", 1, "decision"], ""), "project category has no decision"),
}

WARNINGS = {
    "fewer than five dimensions in a project": (lambda s: drop_dimension(s, "taste"),
                                                "project brand has 4 dimensions"),
    "fewer than two questions in a dimension": (lambda s: dim(s, "brand", "taste")["questions"].pop(),
                                                "dimension taste has 1 question"),
    "a project that mixes branded and unbranded questions": (lambda s: q(s, "c-price-1").update(branded=True),
                                                             "project category mixes"),
    "fewer than three answers per question and model in a report period": (
        set_(["projects", 0, "schedule"], "monthly"), "project brand gives 1 answer per question and model"),
}


class ValidateTest(DesignCase, unittest.TestCase):

    def test_the_clean_study_validates_with_no_warning(self):
        proc = self.validate(clean_study())
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn("  warning:", proc.stdout)
        self.assertIn("validate passed", proc.stdout)

    def test_each_refusal_has_a_fixture_that_exits_1_and_names_the_problem(self):
        for name, (change, expected) in REFUSALS.items():
            with self.subTest(name):
                proc = self.validate(mutated(change))
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertIn(expected, proc.stdout)
                self.assertIn("validate failed", proc.stdout)

    def test_each_warning_has_a_fixture_that_exits_0_and_names_the_warning(self):
        for name, (change, expected) in WARNINGS.items():
            with self.subTest(name):
                proc = self.validate(mutated(change))
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertIn(f"warning: {expected}", proc.stdout)

    def test_every_problem_is_listed_not_only_the_first(self):
        def change(study):
            q(study, "health-1").pop("text")
            drop_theme(study, "price")
        proc = self.validate(mutated(change))
        self.assertIn("health-1: text", proc.stdout)
        self.assertIn("no theme feeds dimension price", proc.stdout)

    def test_a_question_over_the_limit_by_one_character_is_accepted_at_the_limit(self):
        proc = self.validate(mutated(lambda s: q(s, "health-1").update(text=LONG[:500])))
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_a_kind_that_is_neither_study_nor_snapshot_is_refused(self):
        proc = self.validate(mutated(lambda s: s.update(kind="survey")))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("survey", proc.stderr)

    def test_a_missing_study_is_refused_with_exit_2(self):
        self.models = self.save("models.json", models())
        self.cli("validate", "--study", self.study, "--models", self.models, check=2)

    def test_a_models_file_that_is_not_list_ai_models_is_refused_with_exit_5(self):
        proc = self.validate(clean_study(), {"researcher_models": {GPT: {"credits": 2}}})
        self.assertEqual(proc.returncode, 5, proc.stderr)


class ComposeTest(unittest.TestCase):

    def test_instructions_and_dated_facts_are_joined_in_one_text(self):
        text = design.compose_instructions("Score 1 when the answer states an outdated price.", [PRICE_FACT])
        self.assertTrue(text.startswith("Score 1 when the answer states an outdated price."))
        for part in ("Avenello Original costs 2.10 USD per litre", "avenello.example/prices", "2026-10-01",
                     "2.10", "1.90"):
            self.assertIn(part, text)

    def test_the_composed_text_of_the_clean_study_is_within_500_characters(self):
        for p in clean_study()["projects"]:
            for d in p["dimensions"]:
                for item in d["questions"]:
                    text = design.compose_instructions(item["instructions"], item.get("facts"))
                    self.assertLessEqual(len(text), 500, item["key"])

    def test_a_question_without_facts_sends_its_instructions_as_written(self):
        self.assertEqual(design.compose_instructions("Judge on grounds.", None), "Judge on grounds.")
        self.assertEqual(design.compose_instructions("Judge on grounds.", []), "Judge on grounds.")

    def test_facts_without_instructions_start_with_the_facts(self):
        text = design.compose_instructions("", [PRICE_FACT])
        self.assertTrue(text.startswith("Facts"), text)

    def test_composition_is_not_cut_to_fit_so_validate_can_refuse_it(self):
        text = design.compose_instructions("y" * 480, [PRICE_FACT])
        self.assertGreater(len(text), 500)


class ReviewTest(DesignCase, unittest.TestCase):

    def review(self, study=None, demand=True, models_data=None):
        self.put(study or clean_study())
        if models_data is not None:
            self.models = self.save("models.json", models_data)
        if demand:
            (self.study / "search-demand.json").write_text(json.dumps(search_demand()), encoding="utf-8")
        return self.cli("review", "--study", self.study, "--models", self.models)

    def test_it_writes_study_review_and_prints_the_same_text(self):
        proc = self.review()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.study / "study-review.md").read_text(encoding="utf-8").strip(), proc.stdout.strip())

    def test_it_prints_the_narrative(self):
        out = self.review().stdout
        for part in ("## Narrative", "What are people who ask an AI assistant about oat milk",
                     "to decide which pages to write", "personas", "A parent and an athlete",
                     "Two projects: with the brand and without it", "stance"):
            self.assertIn(part, out)

    def test_it_prints_the_theme_inventory_with_origins_and_search_demand(self):
        out = self.review().stdout
        self.assertIn("## Theme inventory", out)
        self.assertIn("Customer-service questions, 2026", out)
        self.assertIn("2 distinct suggestions", out)
        self.assertIn("oat milk bad for you", out)

    def test_it_says_when_no_search_demand_was_collected(self):
        out = self.review(demand=False).stdout
        self.assertIn("No search demand was collected", out)

    def test_it_prints_projects_and_dimensions_with_their_question_counts(self):
        out = self.review().stdout
        self.assertIn("## Projects and dimensions", out)
        self.assertIn("Avenello · With the brand", out)
        self.assertIn("Which claims on product pages to correct", out)
        self.assertIn("Acme Chat", out)
        self.assertIn("Health: 2 questions", out)

    def test_it_prints_every_question_with_persona_framing_and_rubric(self):
        out = self.review().stdout
        self.assertIn("## Questions", out)
        for project in clean_study()["projects"]:
            for d in project["dimensions"]:
                for item in d["questions"]:
                    self.assertIn(item["text"], out)
        for part in ("a shopper comparing plant drinks", "framing: negative", "names the brand: no",
                     "5. Favourable, with grounds from a named source", "Gives a doubtful or mixed account",
                     "Avenello Original costs 2.10 USD per litre", "Score 1 when the answer states an outdated price."):
            self.assertIn(part, out)

    def test_the_credit_estimate_comes_from_the_models_tariffs(self):
        out = self.review().stdout
        self.assertIn("## Credit estimate", out)
        # 10 questions x 1 round x (2 + 3 credits) in each project.
        self.assertIn("project brand: 50 credits per run", out)
        self.assertIn("project category: 50 credits per run", out)
        self.assertIn("100 credits per run", out)
        # a weekly schedule read monthly is four runs.
        self.assertIn("200 credits per report period", out)
        self.assertIn("Judging is not in this figure", out)

    def test_the_estimate_follows_the_tariff_and_the_rounds(self):
        study = mutated(lambda s: s["projects"][0].update(rounds=2, models=[GPT, NEW]))
        out = self.review(study).stdout
        # 10 questions x 2 rounds x (2 + 1) credits.
        self.assertIn("project brand: 60 credits per run", out)

    def test_a_model_with_no_tariff_is_refused(self):
        proc = self.review(models_data={"researcher_models": {GPT: {"name": "Acme Chat"}, GEM: {"name": "Orbit Reason", "credits": 3}}})
        self.assertEqual(proc.returncode, 2)
        self.assertIn("credits", proc.stderr)

    def test_a_study_that_fails_validation_is_not_reviewed(self):
        proc = self.review(mutated(lambda s: drop_theme(s, "price")))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("no theme feeds dimension price", proc.stderr)
        self.assertFalse((self.study / "study-review.md").exists())


class ReviseTest(DesignCase, unittest.TestCase):

    def revise(self, new, *extra):
        previous = self.save("previous.json", clean_study())
        self.put(new)
        return self.cli("revise", "--study", self.study, "--previous", previous, *extra)

    def test_a_reworded_question_keeps_its_key_and_records_reworded(self):
        proc = self.revise(mutated(lambda s: q(s, "price-1").update(text="What does Avenello oat milk cost per litre?")))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        item = q(self.read("study.json"), "price-1")
        self.assertEqual(item["text"], "What does Avenello oat milk cost per litre?")
        self.assertEqual(item["lineage"][-1], {"version": 2, "change": "reworded"})
        self.assertIn("price-1 reworded", proc.stdout)

    def test_a_question_with_a_new_intent_gets_a_new_key_and_the_old_key_is_retired(self):
        new = mutated(lambda s: q(s, "price-1").update(text="Is Avenello oat milk cheaper than Avoria?"))
        proc = self.revise(new, "--new-intent", "price-1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("ignored", proc.stdout)
        study = self.read("study.json")
        price = dim(study, "brand", "price")
        self.assertEqual([x["key"] for x in price["questions"]], ["price-3", "price-2"])
        self.assertEqual(price["questions"][0]["lineage"], [{"version": 2, "change": "new_intent", "replaces": "price-1"}])
        self.assertEqual(price["retired"], [{"key": "price-1", "text": "How much does Avenello oat milk cost?", "version": 2}])
        self.assertEqual(self.validate(study).returncode, 0)

    def test_a_retired_key_is_never_given_again(self):
        first = mutated(lambda s: q(s, "price-1").update(text="Is Avenello oat milk cheaper than Avoria?"))
        self.revise(first, "--new-intent", "price-1")
        revised = self.read("study.json")
        previous = self.save("previous.json", revised)
        q(revised, "price-3")["text"] = "Which is cheaper, Avenello oat milk or Avoria?"
        self.put(revised)
        self.cli("revise", "--study", self.study, "--previous", previous, "--new-intent", "price-3", check=0)
        keys = [x["key"] for x in dim(self.read("study.json"), "brand", "price")["questions"]]
        self.assertEqual(keys, ["price-4", "price-2"])

    def test_a_changed_rubric_or_fact_is_criteria_and_keeps_the_key(self):
        proc = self.revise(mutated(lambda s: q(s, "price-1")["facts"][0].update(current=["2.20"])))
        self.assertEqual(q(self.read("study.json"), "price-1")["lineage"][-1], {"version": 2, "change": "criteria"})
        self.assertIn("price-1: rubric, judge instructions or facts changed", proc.stdout)

    def test_a_reworded_question_whose_rubric_also_changed_records_both(self):
        def change(s):
            q(s, "taste-1").update(text="How does Avenello oat milk taste?")
            q(s, "taste-1")["rubric"]["5"] = "Favourable, with a named source"
        self.revise(mutated(change))
        self.assertEqual([e["change"] for e in q(self.read("study.json"), "taste-1")["lineage"][1:]],
                         ["reworded", "criteria"])

    def test_a_question_removed_from_the_study_is_retired(self):
        self.revise(mutated(lambda s: dim(s, "brand", "taste")["questions"].pop()))
        taste = dim(self.read("study.json"), "brand", "taste")
        self.assertEqual([r["key"] for r in taste["retired"]], ["taste-2"])

    def test_nothing_changed_writes_nothing(self):
        proc = self.revise(clean_study())
        self.assertIn("unchanged", proc.stdout)
        self.assertEqual(self.read("study.json"), clean_study())

    def test_new_intent_on_a_question_that_was_not_reworded_is_ignored_and_said(self):
        proc = self.revise(clean_study(), "--new-intent", "price-1")
        self.assertIn("--new-intent price-1 ignored", proc.stdout)
        self.assertEqual(self.read("study.json"), clean_study())

    def test_a_dry_run_lists_the_changes_and_writes_nothing(self):
        new = mutated(lambda s: q(s, "price-1").update(text="What does Avenello oat milk cost per litre?"))
        proc = self.revise(new, "--dry-run")
        self.assertIn("Dry run", proc.stdout)
        self.assertEqual(self.read("study.json"), new)

    def test_a_new_question_is_recorded_as_created_in_the_new_version(self):
        def change(s):
            dim(s, "brand", "taste")["questions"].append(
                {**q(s, "taste-1"), "key": "taste-3", "text": "Is Avenello oat milk sweet?",
                 "lineage": [{"version": 1, "change": "created"}]})
        self.revise(mutated(change))
        self.assertEqual(q(self.read("study.json"), "taste-3")["lineage"], [{"version": 2, "change": "created"}])


class CatalogueTest(unittest.TestCase):

    TEXT = (REPO / "skills" / "sentl-monitor" / "design" / "catalogue.md").read_text(encoding="utf-8")

    def entries(self):
        parts = re.split(r"(?m)^### `([a-z-]+)`\n", self.TEXT)
        return dict(zip(parts[1::2], parts[2::2]))

    def test_every_entry_gives_its_axis_patterns_anchors_and_facts(self):
        entries = self.entries()
        self.assertGreaterEqual(len(entries), 8)
        for entry_id, body in entries.items():
            for field in ("- Axis:", "- Patterns:", "- Anchors:", "- Facts:"):
                self.assertIn(field, body, entry_id)

    def test_it_defines_the_stance_and_fidelity_axes_with_five_anchors_each(self):
        for axis in ("stance", "fidelity"):
            table = self.TEXT.split(f"**{axis}.**")[1].split("\n\n")[1]
            self.assertEqual(len(re.findall(r"(?m)^\| [1-5] \|", table)), 5, axis)

    def test_the_catalogue_names_a_recommendation_entry_that_names_no_brand(self):
        self.assertIn("Names the subject: no", self.entries()["recommendation"])


if __name__ == "__main__":
    unittest.main()
