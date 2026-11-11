"""The snapshot route's script: `validate`, `review`, `payload` and `bind` in snapshot mode, the period of its one run
and the deck that records it, `resume`, `close` and `promote`."""

import json
import re
import unittest

import socket
from unittest import mock
from urllib.parse import parse_qs, urlparse

from fixtures import GEM, GPT, StudyCase, listing, models
from snapshot_study import (ANSWERS as RUN_ANSWERS, ASKED_BY, BOUND_AT, DATE, KEY, PROJECT_ID, READER, RUN_ID, RUN_STARTED, SCORES, SEEDS,
                            SUGGESTIONS, clean_snapshot, extra_dimension, mutated, run_results, saved_project,
                            search_demand, seeds_file)

from sentlmon import deck, demand

TOOLS = ("create-project-tool", "create-snapshot-tool", "update-project-settings-tool", "save-project-questions-tool")


def dim(study, key):
    return next(d for d in study["projects"][0]["dimensions"] if d["key"] == key)


def q(study, key):
    return dim(study, key.rsplit("-", 1)[0])["questions"][0]


class SnapshotCase(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.design = clean_snapshot()
        self.put(self.design)
        self.models = self.save("models.json", models())
        self.searched(seeds_file(), search_demand())

    def put(self, study):
        self.design = study
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")

    def searched(self, seeds, demand_data):
        """The folder's seeds.json and search-demand.json; None removes the file."""
        for name, data in (("seeds.json", seeds), ("search-demand.json", demand_data)):
            path = self.study / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def validate(self, study):
        self.put(study)
        return self.cli("validate", "--study", self.study, "--models", self.models)

    def bind(self, saved, check=0, at=BOUND_AT):
        return self.cli("bind", "--study", self.study, "--project", KEY, "--saved",
                        self.save("project-now.json", saved), check=check, at=at)

    def bind_empty(self):
        return self.bind(saved_project(self.design, edit=lambda p: p.update(dimensions=[])))

    def bind_full(self, edit=None):
        saved = saved_project(self.design, edit=edit)
        self.bind_empty()
        self.bind(saved)
        return saved

    def no_runs(self):
        return listing([], PROJECT_ID)

    def payload(self, saved=None, runs=None, check=0):
        args = ["payload", "--study", self.study, "--project", KEY, "--models", self.models]
        if saved is not None:
            args += ["--saved", self.save("project-now.json", saved)]
        if runs is not None:
            args += ["--runs", self.save("runs-now.json", runs)]
        proc = self.cli(*args, check=check)
        return json.loads(proc.stdout) if proc.returncode == 0 else proc

    def ingest_run(self, scores=None, run_id=RUN_ID, started=RUN_STARTED):
        return self.cli("ingest", "--study", self.study, "--project", KEY, "--results",
                        self.save(f"run-{run_id}.json", run_results(self.design, run_id, scores=scores, started=started)),
                        check=0)

    def period(self, check=0):
        return self.cli("period", "--study", self.study, "--date", DATE, "--models", self.models, check=check)

    def close(self, saved, check=0):
        return self.cli("close", "--study", self.study, "--saved", self.save("project-closed.json", saved),
                        check=check, at="2026-10-22T12:00:00Z")

    def saved_paused(self, active=False):
        return saved_project(self.design, edit=lambda p: p.update(is_active=active))

    def forget_run(self):
        (self.study / "history" / "runs" / KEY / f"{RUN_ID}.json.gz").unlink()

    def earlier_report(self):
        """The one run ingested and its period recorded by a long report an earlier version wrote, with no deck."""
        self.bind_full()
        self.ingest_run()
        self.period()
        period = self.read(f"history/periods/{DATE}.json")
        (self.study / "reports").mkdir(exist_ok=True)
        (self.study / "reports" / f"{DATE}.md").write_text("# Report\n", encoding="utf-8")
        (self.study / "history" / "reports.json").write_text(json.dumps([
            {"date": DATE, "file": f"reports/{DATE}.md", "status": "final",
             "period": {"from": period["from"], "to": period["to"]}, "runs": period["runs"], "previous": None}]),
            encoding="utf-8")

    def final_deck(self, edit=None):
        """The one run ingested, its period built and its deck passed check, as SNAPSHOT.md step 9 ends. `edit` changes
        the project Sentl holds."""
        self.bind_full(edit=edit)
        self.ingest_run()
        self.period()
        with mock.patch.object(deck, "MIN_ANSWERS", 1), mock.patch.object(deck, "MIN_SITE_ANSWERS", 1):
            self.cli("deck", "--study", self.study, "--date", DATE, check=0)
            path = self.study / "reports" / f"{DATE}.deck.json"
            path.write_text(json.dumps(snapshot_deck(json.loads(path.read_text(encoding="utf-8")))), encoding="utf-8")
            self.cli("check", "--study", self.study, path, check=0)


# --- validate and review --------------------------------------------------------

def set_(path, value):
    def change(study):
        target = study
        for step in path[:-1]:
            target = target[step]
        target[path[-1]] = value
    return change


def drop_dimensions(study, count):
    study["projects"][0]["dimensions"] = study["projects"][0]["dimensions"][:count]


def add_dimensions(study, count):
    for n in range(count):
        study["projects"][0]["dimensions"].append(extra_dimension(n))
        study["narrative"]["design_rationale"].append({"choice": f"Extra {n}", "reason": "it adds a reading"})


def add_question(study):
    first = dim(study, "reputation")
    twin = json.loads(json.dumps(first["questions"][0]))
    twin.update(key="reputation-2", text="Is Avenello oat milk any good?")
    first["questions"].append(twin)


REFUSALS = {
    "three dimensions": (lambda s: drop_dimensions(s, 3), "3 dimensions"),
    "six dimensions": (lambda s: add_dimensions(s, 2), "6 dimensions"),
    "a dimension with two questions": (add_question, "reputation has 2 questions"),
    "a dimension with no question": (lambda s: dim(s, "price").update(questions=[]), "price has 0 questions"),
    "a catalogue id that catalogue.md does not hold": (lambda s: dim(s, "price").update(catalogue="cost"),
                                                       "catalogue id cost"),
    "a dimension with no catalogue id": (lambda s: dim(s, "price").pop("catalogue"), "price has no catalogue id"),
    "rounds above one": (set_(["projects", 0, "rounds"], 2), "rounds must be 1"),
    "a schedule": (set_(["projects", 0, "schedule"], "weekly"), "a snapshot has no schedule"),
    "two projects": (lambda s: s["projects"].append(dict(s["projects"][0], key="other")), "one project"),
    "a question over 500 characters": (lambda s: q(s, "price-1").update(text="x" * 501), "price-1: text is 501"),
    "a question with no judge instructions and no facts": (lambda s: q(s, "reputation-1").update(instructions=""),
                                                           "reputation-1: the judge has no instructions"),
    "an alias in a question marked as naming no brand": (
        lambda s: q(s, "recommendation-1").update(text="Is Avenello the best oat milk in the US?"),
        "recommendation-1 is marked as naming no brand but contains the alias Avenello"),
    "a model Sentl no longer offers": (set_(["projects", 0, "models"], [GPT, "oldco/legacy-7b"]),
                                       "oldco/legacy-7b is not in list-ai-models"),
    "a narrative without a research question": (lambda s: s["narrative"].pop("research_question"),
                                                "narrative.research_question"),
    "a narrative without a purpose": (set_(["narrative", "purpose"], " "), "narrative.purpose"),
    "a dimension that says nothing about what it measures": (lambda s: dim(s, "price").pop("measures"),
                                                              "price: measures"),
    "a dimension with no reason for its choice": (
        lambda s: s["narrative"].update(design_rationale=s["narrative"]["design_rationale"][1:]),
        "Reputation has no entry in design_rationale"),
    "two dimensions with one name": (lambda s: dim(s, "price").update(name="Health"), "two dimensions named Health"),
    "a question with no persona": (lambda s: q(s, "price-1").pop("persona"), "price-1: persona is missing"),
    "a question whose persona is blank": (lambda s: q(s, "health-1").update(persona=" "),
                                          "health-1: persona is missing"),
    "a suggestion that is not a text": (lambda s: q(s, "price-1").update(suggestion=""), "price-1: suggestion"),
    "a suggestion Google never gave": (lambda s: q(s, "price-1").update(suggestion="avenello oat milk free sample"),
                                       "price-1: suggestion «avenello oat milk free sample» is not in "
                                       "search-demand.json"),
    "a suggestion Google gave for another dimension": (
        lambda s: q(s, "price-1").update(suggestion=SUGGESTIONS["health"]),
        f"price-1: suggestion «{SUGGESTIONS['health']}» is not in search-demand.json"),
    "a question with no suggestion when its dimension has some": (lambda s: q(s, "health-1").pop("suggestion"),
                                                                  "health-1: suggestion is missing"),
}


class ValidateSnapshotTest(SnapshotCase):

    def test_the_clean_snapshot_validates_with_no_warning(self):
        proc = self.validate(clean_snapshot())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("validate passed", proc.stdout)
        self.assertNotIn("warning:", proc.stdout)

    def test_five_dimensions_are_accepted(self):
        self.assertEqual(self.validate(mutated(lambda s: add_dimensions(s, 1))).returncode, 0)

    def test_each_refusal_exits_1_and_names_the_problem(self):
        for name, (change, expected) in REFUSALS.items():
            with self.subTest(name):
                proc = self.validate(mutated(change))
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertIn(expected, proc.stdout)
                self.assertIn("validate failed", proc.stdout)

    def test_every_dimension_naming_the_subject_is_a_warning_not_a_refusal(self):
        proc = self.validate(mutated(lambda s: q(s, "recommendation-1").update(branded=True)))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("warning: every dimension names the subject", proc.stdout)

    def test_the_study_rules_on_themes_pairs_and_search_lean_do_not_apply(self):
        proc = self.validate(mutated(lambda s: dim(s, "health").update(search_lean="negative")))
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_a_suggestion_matches_the_recorded_one_after_folding(self):
        proc = self.validate(mutated(lambda s: q(s, "health-1").update(suggestion="Is Oat Milk Bad For You")))
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_a_suggestion_with_no_search_demand_in_the_folder_is_refused(self):
        self.searched(seeds_file(), None)
        proc = self.validate(clean_snapshot())
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn(f"health-1: suggestion «{SUGGESTIONS['health']}» is not in search-demand.json", proc.stdout)

    def test_with_no_network_the_questions_go_without_a_suggestion(self):
        self.searched(seeds_file(), search_demand(found=False))
        proc = self.validate(mutated(lambda s: [d["questions"][0].pop("suggestion", None)
                                                for d in s["projects"][0]["dimensions"]]))
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_a_snapshot_made_before_suggestions_validates(self):
        self.searched(None, None)
        proc = self.validate(mutated(lambda s: [d["questions"][0].pop("suggestion", None)
                                                for d in s["projects"][0]["dimensions"]]))
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_a_kind_that_is_neither_study_nor_snapshot_is_refused(self):
        proc = self.validate(mutated(lambda s: s.update(kind="survey")))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("survey", proc.stderr)


class ReviewSnapshotTest(SnapshotCase):

    def review(self, study=None):
        self.put(study or clean_snapshot())
        return self.cli("review", "--study", self.study, "--models", self.models)

    def test_it_writes_study_review_and_prints_the_same_text(self):
        proc = self.review()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.study / "study-review.md").read_text(encoding="utf-8").strip(), proc.stdout.strip())

    def test_it_shows_every_question_with_its_rubric_and_the_judge_instructions(self):
        out = self.review().stdout
        for d in clean_snapshot()["projects"][0]["dimensions"]:
            self.assertIn(d["questions"][0]["text"], out)
        for part in ("## Questions", "5. Favourable, with grounds from a named source", "2.10 USD per litre",
                     "names the brand: no"):
            self.assertIn(part, out)

    def test_it_shows_the_reader_and_each_question_with_its_persona_and_suggestion(self):
        out = self.review().stdout
        self.assertIn(f"- Reader: {READER}", out)
        for key in ("reputation", "recommendation", "price", "health"):
            self.assertIn(f"persona: {ASKED_BY[key]}", out)
            self.assertIn(f"- Google suggestion: {SUGGESTIONS[key]}", out)

    def test_it_shows_the_cost_of_the_one_run_from_the_tariffs(self):
        out = self.review().stdout
        self.assertIn("20 credits per run", out)
        self.assertNotIn("per report period", out)

    def test_it_names_the_catalogue_entry_and_the_reason_of_each_dimension(self):
        out = self.review().stdout
        self.assertIn("catalogue: health-safety", out)
        self.assertIn("the reader decides on health pages", out)

    def test_a_snapshot_that_fails_validate_is_not_reviewed(self):
        proc = self.review(mutated(lambda s: drop_dimensions(s, 3)))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("3 dimensions", proc.stderr)


# --- payload and bind -----------------------------------------------------------

def values(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from values(v)
    elif isinstance(node, list):
        for v in node:
            yield from values(v)


class PayloadSnapshotTest(SnapshotCase):

    def test_an_unbound_snapshot_gets_the_arguments_of_create_snapshot_tool_and_no_project_call(self):
        out = self.payload()
        self.assertEqual(sorted(k for k in out if k in TOOLS), ["create-snapshot-tool"])
        self.assertEqual(out["create-snapshot-tool"], {
            "organization": "example-org", "name": f"Snapshot · Avenello · {DATE}",
            "researcher_model_ids": [GPT, GEM]})

    def test_the_create_arguments_carry_no_rounds_no_schedule_and_no_activation(self):
        args = self.payload()["create-snapshot-tool"]
        for field in ("rounds", "schedule_frequency", "is_active"):
            self.assertNotIn(field, args)

    def test_a_bound_snapshot_saves_one_project_with_its_four_dimensions_and_asks_for_no_settings_change(self):
        saved = self.bind_full()
        out = self.payload(saved, self.no_runs())
        self.assertNotIn("update-project-settings-tool", out)
        sent = out["save-project-questions-tool"]
        self.assertEqual(sent["project_id"], PROJECT_ID)
        self.assertEqual([len(d["questions"]) for d in sent["dimensions"]], [1, 1, 1, 1])

    def test_no_output_sets_is_active_to_true(self):
        saved = self.bind_full()
        for state in (False, True):
            out = self.payload(saved_project(self.design, edit=lambda p: p.update(is_active=state)), self.no_runs())
            self.assertNotIn(("is_active", True), list(values(out)))

    def test_an_active_snapshot_project_is_paused_by_the_settings_call(self):
        self.bind_full()
        out = self.payload(saved_project(self.design, edit=lambda p: p.update(is_active=True)), self.no_runs())
        self.assertEqual(out["update-project-settings-tool"]["is_active"], False)
        self.assertEqual(out["update-project-settings-tool"]["project_id"], PROJECT_ID)
        self.assertNotIn("schedule_frequency", out["update-project-settings-tool"])

    def test_a_schedule_found_in_sentl_is_told_to_the_operator_and_not_sent(self):
        self.bind_full()
        out = self.payload(saved_project(self.design, edit=lambda p: p.update(schedule_frequency="weekly")),
                           self.no_runs())
        self.assertNotIn("schedule_frequency", json.dumps(out["save-project-questions-tool"]))
        self.assertTrue(any("schedule" in n for n in out["notes"]), out["notes"])

    def test_a_snapshot_that_fails_validate_is_refused(self):
        self.put(mutated(lambda s: drop_dimensions(s, 3)))
        self.assertIn("3 dimensions", self.payload(check=2).stderr)

    def test_bind_records_a_snapshot_project_that_has_no_schedule(self):
        self.bind_full()
        bound = self.read("sentl.json")["projects"][KEY]
        self.assertEqual(bound["project_id"], PROJECT_ID)
        self.assertEqual(len(bound["questions"]), 4)
        self.assertIsNone(self.read(f"history/versions/{KEY}-002.json")["settings"]["schedule"])


# --- the period ---------------------------------------------------------------

class SnapshotPeriodTest(SnapshotCase):
    """The period of the snapshot's one run: no cadence, nothing to compare with, one run only."""

    def setUp(self):
        super().setUp()
        self.bind_full()
        self.ingest_run()

    def test_the_period_needs_no_report_cadence_and_has_no_comparison(self):
        self.assertNotIn("report_every", self.design)
        self.period()
        comparison = self.read(f"history/periods/{DATE}.json")["comparison"]
        self.assertIsNone(comparison["previous"])
        self.assertFalse(comparison.get("halves"))

    def test_a_run_under_the_judged_floor_is_still_the_snapshot(self):
        self.forget_run()
        self.ingest_run(scores={("reputation", GPT): 4, ("reputation", GEM): 4})
        self.period(check=0)
        self.assertEqual(self.read(f"history/periods/{DATE}.json")["runs"], {KEY: [RUN_ID]})

    def test_a_snapshot_holding_two_runs_is_refused(self):
        self.ingest_run(run_id=7002, started="2026-10-22T10:00:00Z")
        proc = self.cli("period", "--study", self.study, "--date", DATE, "--models", self.models, check=2)
        self.assertIn("one run", proc.stderr)

    def test_a_dimension_under_80_percent_judged_is_shown_without_a_figure(self):
        self.forget_run()
        self.ingest_run(scores={k: v for k, v in SCORES.items() if k != ("price", GEM)})
        self.assertIn("1 of 2 answers judged, under 80%", self.period().stdout)


# --- the deck of a snapshot ---------------------------------------------------

def snapshot_deck(doc):
    """The deck's text of the fixture's one run, written as DECK.md asks: every figure is the period's."""
    slide = {"rows": "dimensions", "dimensions": [], "questions": []}

    def excerpt(dimension, model, name):
        return [{"text": RUN_ANSWERS[(dimension, model)], "question": q(clean_snapshot(), f"{dimension}-1")["text"],
                 "assistant": name}]
    return {**doc,
            "opening": {"who": "shoppers who ask an AI assistant about oat milk",
                        "questions": {"reach": "Do shoppers who ask for an oat milk without naming a brand find Avenello?",
                                      "description": "What do shoppers who ask about Avenello hear?",
                                      "facts": "Do the answers give the price of Avenello right?"},
                        "examples": {"reach": ["recommendation-1"], "description": ["reputation-1"], "facts": ["price-1"]}},
            "found": {"title": "Shoppers who ask for an oat milk hear of Avoria before Avenello",
                      "answers": {"reach": "Avenello is named in 1 of the 2 answers, Avoria in 2 of 2.",
                                  "description": "3 of the 6 answers about Avenello are favourable.",
                                  "facts": "1 of the 2 answers gives the price of today."}},
            "actions_title": "The first thing to do is to get Avenello into the guide the answers cite",
            "actions": [{"class": "not_named", "what": "Ask guide.example to add Avenello to its oat milk guide",
                         "why": "Avoria is named in 2 of the 2 answers, Avenello in fewer",
                         "read_next": "Answers naming Avenello: 1 of 2", "block": "reach",
                         "pages": [{"url": "guide.example/oat", "shows": ["Avoria", "Brand B", "Brand C"]}]}],
            "blocks": {"reach": [{**slide, "title": "Shoppers who ask for an oat milk find Avoria",
                                  "read": "One answer leaves Avenello out.",
                                  "excerpts": excerpt("recommendation", GEM, "Orbit Reason"), "action": 1}],
                       "description": [{**slide, "title": "Shoppers who ask about Avenello hear about its taste",
                                        "read": "The answers describe the taste.",
                                        "excerpts": excerpt("reputation", GPT, "Acme Chat"), "action": None}],
                       "facts": [{**slide, "title": "The price of today comes up in one answer",
                                  "read": "The other answer rounds the price.",
                                  "excerpts": excerpt("price", GPT, "Acme Chat"), "action": None}]},
            "sources": {"title": "The answers cite guide.example",
                        "read": "The answers cite guide.example, where the action asks for Avenello."},
            "method": {"limits": [], "ask": ["Which pages do the assistants cite?"]}}


class SnapshotDeckCase(SnapshotCase):
    """The deck of the fixture's one run, written as DECK.md asks."""

    def setUp(self):
        super().setUp()
        for name in ("MIN_ANSWERS", "MIN_SITE_ANSWERS"):  # the fixture's questions have two answers each
            patcher = mock.patch.object(deck, name, 1)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.bind_full()
        self.ingest_run()
        self.period()
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        self.path = self.study / "reports" / f"{DATE}.deck.json"
        self.path.write_text(json.dumps(snapshot_deck(json.loads(self.path.read_text(encoding="utf-8")))),
                             encoding="utf-8")


class SnapshotDeckTest(SnapshotDeckCase):
    """A snapshot ends with a deck: the period of its one run, compared with nothing, is what the deck draws."""

    def test_the_deck_of_the_one_run_passes_check_and_records_the_period(self):
        self.cli("check", "--study", self.study, self.path, check=0)
        self.assertEqual([(e["date"], e["status"], e["runs"], e["previous"], e["deck"])
                          for e in self.read("history/reports.json")],
                         [(DATE, "final", {KEY: [RUN_ID]}, None, f"reports/{DATE}.deck.json")])

    def test_the_deck_of_the_one_run_prints_with_a_slide_per_page(self):
        def printer(target, pdf, engines):
            pdf.write_bytes(b"%PDF-1.4\n" + b"<< /Type /Page >>\n" * deck.page_of(self.study, DATE)[1])
            return "fake", []
        said = deck.render(self.study, DATE, printer=printer)
        self.assertIn("To send:", said)
        self.assertTrue(list((self.study / "reports" / "share").glob("*monitoring deck*.pdf")))


class SnapshotDeckSlidesTest(SnapshotDeckCase):
    """What the deck of a snapshot says of how it ran, and how its slides look with one block."""

    def model(self, blocks=None):
        folder, _, study, period, doc = deck.load(self.study, DATE)
        m = deck.build_model(folder, study, period, doc)
        for key in set(deck.BLOCKS) - set(blocks or deck.BLOCKS):
            m["blocks"][key]["rows"] = []
        return doc, m

    def test_the_method_slide_says_it_ran_once_with_no_schedule(self):
        doc, m = self.model()
        method = deck._method(doc, m, deck.DECK["en"])
        self.assertIn("<td>1, no schedule</td>", method)
        self.assertNotIn("scheduled every", method)

    def test_slide_two_says_each_question_was_asked_once(self):
        doc, m = self.model()
        self.assertEqual(deck._reading_key(m), "reading_answers_once")
        opening = deck._opening_slide(doc, m, deck.DECK["en"], "en", (9, 9))
        self.assertIn("each question was asked once, to 2 of these assistants", opening)
        self.assertNotIn("repeated", opening)

    def test_the_rating_scale_is_explained_only_when_a_slide_uses_it(self):
        t = deck.DECK["en"]
        for blocks, used in ((["reach"], False), (["reach", "description"], True), (["reach", "facts"], True)):
            with self.subTest(blocks):
                doc, m = self.model(blocks)
                opening, method = deck._opening_slide(doc, m, t, "en", (9, 9)), deck._method(doc, m, t)
                self.assertEqual(t["reading_scores"].split(":")[0] in opening, used)
                self.assertEqual(t["scores_title"] in method, used)

    def test_the_found_slide_of_one_block_keeps_its_card_as_tall_as_its_content(self):
        from sentlmon import fit
        for blocks, grows in ((["reach"], False), (["reach", "description"], True), (list(deck.BLOCKS), True)):
            with self.subTest(blocks):
                doc, m = self.model(blocks)
                tree = fit._Tree()
                tree.feed(f'<section class="slide found">{deck._found_slide(doc, m, deck.DECK["en"])}</section>')
                cards = next(n for n in _nodes(tree.root) if "cards" in n.classes)
                layout = fit.Layout(deck.STYLE)
                self.assertEqual(fit._flex(layout.style(cards).props)[0] > 0, grows)
                section = tree.root.elements()[0]
                self.assertLessEqual(layout.box(section, fit.PAGE_WIDTH), fit.PAGE_HEIGHT)


def _nodes(node):
    for kid in node.elements():
        yield kid
        yield from _nodes(kid)


# --- the questions start from Google's suggestions ------------------------------

class SuggestionStepTest(SnapshotCase):
    """SNAPSHOT.md step 4: one seed per dimension goes to `demand autocomplete`, and each question starts
    from its dimension's top suggestion. No test reaches Google."""

    def setUp(self):
        super().setUp()
        for patch in (mock.patch.object(socket, "getaddrinfo", side_effect=AssertionError("a hostname was resolved")),
                      mock.patch.object(demand, "DELAY", 0)):
            patch.start()
            self.addCleanup(patch.stop)
        self.searched(seeds_file(), None)

    @staticmethod
    def google(url):
        """The seed itself gets its dimension's suggestion first; a seed followed by a stem gets an echo."""
        prefix = parse_qs(urlparse(url).query)["q"][0]
        first = {seed: SUGGESTIONS[key] for key, seed in SEEDS.items()}.get(prefix)
        return json.dumps([prefix, [first, prefix + " near me"] if first else [prefix + " near me"]])

    def test_each_dimension_gets_one_seed_and_its_question_starts_from_the_top_suggestion(self):
        with mock.patch.object(demand, "_get", side_effect=self.google) as get:
            self.cli("demand", "autocomplete", "--study", self.study, "--hl", "en", "--gl", "US", check=0)
        self.assertEqual(get.call_count, len(SEEDS) * 8)
        out = self.cli("demand", "summary", "--study", self.study, check=0).stdout
        tops = dict(re.findall(r"^(\S+): .*\n.*\n  top queries: ([^;\n]+)", out, flags=re.M))
        for d in clean_snapshot()["projects"][0]["dimensions"]:
            item = d["questions"][0]
            self.assertEqual(item["suggestion"], tops[d["key"]], d["key"])
            self.assertTrue(item["persona"].strip(), d["key"])
        self.assertEqual(self.validate(clean_snapshot()).returncode, 0)

    def test_without_network_every_prefix_is_listed_and_nothing_is_suggested(self):
        with mock.patch.object(demand, "_get", side_effect=OSError("network is unreachable")):
            proc = self.cli("demand", "autocomplete", "--study", self.study, "--hl", "en", "--gl", "US", check=1)
        self.assertIn(f"{len(SEEDS) * 8} prefixes could not be fetched", proc.stdout)
        self.assertTrue(all(not b["autocomplete"] for b in self.read("search-demand.json")["themes"].values()))


# --- resume and close -----------------------------------------------------------

class ResumeTest(SnapshotCase):

    def resume(self, runs=None, check=0):
        args = ["resume", "--study", self.study]
        if runs is not None:
            args += ["--runs", self.save("runs-now.json", runs)]
        return self.cli(*args, check=check)

    def step(self, runs=None):
        match = re.search(r"^Next step: (\w+)", self.resume(runs).stdout, re.M)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_a_folder_without_study_json_resumes_at_design(self):
        (self.study / "study.json").unlink()
        self.assertEqual(self.step(), "design")

    def test_a_designed_snapshot_that_is_not_bound_resumes_at_the_project(self):
        self.assertEqual(self.step(), "project")

    def test_a_project_bound_while_empty_resumes_at_the_project_to_save_its_questions(self):
        self.bind_empty()
        self.assertEqual(self.step(self.no_runs()), "project")

    def test_a_bound_project_with_no_run_resumes_at_cost_and_go(self):
        self.bind_full()
        self.assertEqual(self.step(self.no_runs()), "cost")

    def test_a_bound_project_asks_for_the_run_listing(self):
        self.bind_full()
        proc = self.resume(check=2)
        self.assertIn("--runs", proc.stderr)

    def test_an_open_run_resumes_at_following_it_and_starts_nothing(self):
        self.bind_full()
        for status in ("pending", "queued", "running"):
            with self.subTest(status):
                proc = self.resume(listing([(RUN_ID, status, RUN_STARTED)], PROJECT_ID))
                self.assertIn("Next step: run", proc.stdout)
                self.assertIn("trigger-run-tool", proc.stdout)
                self.assertIn("do not call", proc.stdout)

    def test_a_run_in_researching_or_judging_is_followed_and_starts_nothing(self):
        self.bind_full()
        for status in ("researching", "judging"):
            with self.subTest(status):
                proc = self.resume(listing([(RUN_ID, status, RUN_STARTED)], PROJECT_ID))
                self.assertIn("Next step: run", proc.stdout)
                self.assertIn("do not call trigger-run-tool", proc.stdout)

    def test_a_run_that_ended_with_no_results_is_told_and_starts_nothing_without_a_go(self):
        self.bind_full()
        for status in ("failed", "stalled"):
            with self.subTest(status):
                proc = self.resume(listing([(RUN_ID, status, RUN_STARTED)], PROJECT_ID))
                self.assertIn("Next step: run", proc.stdout)
                self.assertIn(status, proc.stdout)
                self.assertIn("operator", proc.stdout)
                self.assertNotIn("never seen", proc.stdout)

    def test_a_completed_run_not_in_history_resumes_at_the_deck(self):
        self.bind_full()
        proc = self.resume(listing([(RUN_ID, "completed", RUN_STARTED)], PROJECT_ID))
        self.assertIn("Next step: deck", proc.stdout)
        self.assertIn(f"run {RUN_ID}", proc.stdout)
        self.assertIn("period", proc.stdout)

    def test_a_run_ingested_without_a_passing_deck_resumes_at_the_deck(self):
        self.bind_full()
        self.ingest_run()
        self.assertEqual(self.step(listing([(RUN_ID, "completed", RUN_STARTED)], PROJECT_ID)), "deck")

    def test_a_deck_left_as_a_draft_resumes_at_the_deck(self):
        self.bind_full()
        self.ingest_run()
        self.period()
        with mock.patch.object(deck, "MIN_ANSWERS", 1), mock.patch.object(deck, "MIN_SITE_ANSWERS", 1):
            self.cli("deck", "--study", self.study, "--date", DATE, check=0)
            self.cli("check", "--study", self.study, self.study / "reports" / f"{DATE}.deck.json", check=1)
        self.assertEqual(self.step(listing([(RUN_ID, "completed", RUN_STARTED)], PROJECT_ID)), "deck")

    def test_a_folder_whose_only_record_is_an_earlier_versions_report_resumes_at_the_deck(self):
        self.earlier_report()
        self.assertEqual(self.step(listing([(RUN_ID, "completed", RUN_STARTED)], PROJECT_ID)), "deck")

    def test_a_finished_deck_on_a_snapshot_not_closed_resumes_at_the_end_choice(self):
        self.final_deck()
        self.assertEqual(self.step(listing([(RUN_ID, "completed", RUN_STARTED)], PROJECT_ID)), "end")

    def test_a_closed_snapshot_has_nothing_left(self):
        self.final_deck()
        self.close(self.saved_paused())
        self.assertEqual(self.step(listing([(RUN_ID, "completed", RUN_STARTED)], PROJECT_ID)), "done")

    def test_a_study_that_is_not_a_snapshot_is_refused(self):
        self.put(mutated(lambda s: s.update(kind="study")))
        self.assertIn("snapshot", self.resume(check=2).stderr)

    def test_a_listing_of_another_project_is_refused(self):
        self.bind_full()
        self.resume(listing([], 111), check=2)


class CloseTest(SnapshotCase):

    def close_deleted(self, check=0):
        return self.cli("close", "--study", self.study, "--deleted", check=check, at="2026-10-22T12:00:00Z")

    def saved_archived(self):
        return saved_project(self.design, edit=lambda p: p.update(archived=True))

    def closed(self):
        return self.read("sentl.json")["projects"][KEY]["closed"]

    def test_a_snapshot_left_in_sentl_is_closed_as_kept(self):
        self.final_deck()
        self.close(self.saved_paused())
        self.assertEqual(self.closed(), {"closed_at": "2026-10-22T12:00:00Z", "how": "kept"})

    def test_an_archived_project_is_closed_as_archived(self):
        self.final_deck()
        self.close(self.saved_archived())
        self.assertEqual(self.closed()["how"], "archived")

    def test_a_deleted_snapshot_is_closed_without_reading_it(self):
        self.final_deck()
        self.close_deleted()
        self.assertEqual(self.closed(), {"closed_at": "2026-10-22T12:00:00Z", "how": "deleted"})

    def test_close_says_the_run_and_the_report_stay_in_the_folder_and_names_no_panel(self):
        self.final_deck()
        out = self.close(self.saved_paused()).stdout
        self.assertIn("stay in this folder", out)
        self.assertNotIn("web panel", out)

    def test_a_project_still_active_is_not_closed(self):
        self.final_deck()
        proc = self.close(self.saved_paused(active=True), check=2)
        self.assertIn("is_active", proc.stderr)
        self.assertNotIn("closed", self.read("sentl.json")["projects"][KEY])

    def test_closing_twice_keeps_the_first_time(self):
        self.final_deck()
        self.close(self.saved_paused())
        again = self.cli("close", "--study", self.study, "--saved", self.save("p.json", self.saved_paused()),
                         check=0, at="2026-10-23T12:00:00Z")
        self.assertIn("already closed", again.stdout)
        self.assertEqual(self.closed()["closed_at"], "2026-10-22T12:00:00Z")

    def test_neither_saved_nor_deleted_is_refused(self):
        self.final_deck()
        self.cli("close", "--study", self.study, check=2)

    def test_a_project_that_is_not_bound_is_refused(self):
        self.close(self.saved_paused(), check=2)

    def test_the_saved_project_must_be_the_bound_one(self):
        self.final_deck()
        self.close(saved_project(self.design, project_id=1), check=2)

    def test_a_study_that_is_not_a_snapshot_is_not_closed(self):
        self.final_deck()
        self.put(mutated(lambda s: s.update(kind="study")))
        self.close(self.saved_paused(), check=2)

    def test_the_binding_keeps_its_ids_after_closing(self):
        self.final_deck()
        before = self.read("sentl.json")["projects"][KEY]
        self.close(self.saved_paused())
        after = self.read("sentl.json")["projects"][KEY]
        self.assertEqual({k: v for k, v in after.items() if k != "closed"}, before)


if __name__ == "__main__":
    unittest.main()


ANSWERS = {"schedule": "weekly", "report_every": "monthly",
           "audience": {"choice": "generic_consumer", "reason": "the snapshot asked as a consumer would"},
           "project": {"question": "What do assistants tell a buyer of Avenello oat milk?",
                       "decision": "Which dimension to work on first"}}


class PromoteTest(SnapshotCase):
    """`promote`: a snapshot whose project is kept becomes a monitored study; its run is the baseline."""

    def promote(self, answers=None, check=0):
        return self.cli("promote", "--study", self.study, "--answers",
                        self.save("promote.json", ANSWERS if answers is None else answers),
                        "--models", self.models, check=check)

    def changed(self, **edit):
        answers = json.loads(json.dumps(ANSWERS))
        answers.update(edit)
        return answers

    def test_a_finished_snapshot_becomes_a_study_with_the_schedule_and_the_cadence(self):
        self.final_deck()
        self.promote()
        study = self.read("study.json")
        self.assertEqual(study["kind"], "study")
        self.assertEqual(study["report_every"], "monthly")
        project = study["projects"][0]
        self.assertEqual((project["schedule"], project["rounds"]), ("weekly", 1))
        self.assertEqual(project["question"], ANSWERS["project"]["question"])
        self.assertEqual(study["narrative"]["audience"]["choice"], "generic_consumer")

    def test_each_dimension_gets_a_theme_whose_origin_is_the_snapshot_probe(self):
        self.final_deck()
        self.promote()
        study = self.read("study.json")
        keys = {d["key"] for d in study["projects"][0]["dimensions"]}
        self.assertEqual({t["dimension"] for t in study["themes"]}, keys)
        self.assertTrue(all(t["origins"][0]["kind"] == "probe" and DATE in t["origins"][0]["detail"]
                            for t in study["themes"]))

    def test_the_questions_and_rubrics_are_left_as_they_were(self):
        self.final_deck()
        before = [q for d in self.read("study.json")["projects"][0]["dimensions"] for q in d["questions"]]
        self.promote()
        after = [q for d in self.read("study.json")["projects"][0]["dimensions"] for q in d["questions"]]
        self.assertEqual(before, after)

    def test_the_project_stays_bound_and_is_not_closed(self):
        self.final_deck()
        self.promote()
        bound = self.read("sentl.json")["projects"][KEY]
        self.assertEqual(bound["project_id"], PROJECT_ID)
        self.assertNotIn("closed", bound)

    def test_it_sends_nothing_and_activates_nothing(self):
        self.final_deck()
        out = self.promote().stdout
        self.assertIn("payload", out)
        self.assertIn("go", out)
        self.assertNotIn('"is_active": true', out)

    def test_a_project_that_ran_nothing_is_refused(self):
        self.bind_full()
        self.assertIn("run", self.promote(check=2).stderr)
        self.assertEqual(self.read("study.json")["kind"], "snapshot")

    def test_a_snapshot_without_a_passing_deck_is_refused(self):
        self.bind_full()
        self.ingest_run()
        self.assertIn("deck", self.promote(check=2).stderr)

    def test_a_snapshot_whose_only_record_is_an_earlier_versions_report_is_refused(self):
        self.earlier_report()
        self.assertIn("deck", self.promote(check=2).stderr)
        self.assertEqual(self.read("study.json")["kind"], "snapshot")

    def test_a_project_already_closed_is_refused(self):
        self.final_deck()
        self.close(self.saved_paused())
        self.assertIn("closed", self.promote(check=2).stderr)

    def test_a_study_that_is_not_a_snapshot_is_refused(self):
        self.final_deck()
        self.promote()
        self.assertIn("snapshot", self.promote(check=2).stderr)

    def test_missing_answers_are_named_and_nothing_is_written(self):
        self.final_deck()
        answers = self.changed(schedule="hourly", report_every="yearly")
        del answers["audience"]
        stderr = self.promote(answers, check=2).stderr
        for word in ("schedule", "report_every", "audience"):
            self.assertIn(word, stderr)
        self.assertEqual(self.read("study.json")["kind"], "snapshot")

    def test_the_first_report_after_promotion_compares_with_the_snapshot(self):
        self.final_deck()
        self.promote()
        self.ingest_run(run_id=RUN_ID + 1, started="2026-11-22T09:00:00Z",
                        scores={k: 5 for k in SCORES})
        proc = self.cli("period", "--study", self.study, "--date", "2026-11-22", "--models", self.models, check=0)
        self.assertIn(f"Compared with the period of {DATE}", proc.stdout)

    def test_a_native_snapshot_cannot_be_followed_and_the_message_names_brief_and_design(self):
        self.final_deck(edit=lambda p: p.update(kind="snapshot"))
        self.assertEqual(self.read("sentl.json")["projects"][KEY]["kind"], "snapshot")
        err = self.promote(check=2).stderr
        self.assertIn("no schedule", err)
        self.assertIn("brief", err)
