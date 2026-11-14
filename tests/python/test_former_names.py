"""A former name of the subject, recorded in subject.former: the answers naming the subject by it alone and the pages they
cite, counted by `period`, listed in the figures file and drawn on the presence chart, so that a deck can ask a page still
carrying the old name to correct it and `check` accepts the count."""

import json
import unittest

from test_deck import DATE, DeckCase  # first: fixtures puts the scripts on the path
from fixtures import CHOICE_Q, GEM, GPT
from test_insights_period import CURRENT, OCT, rows

from sentlmon import check, deck
from sentlmon.adopt import namesake_problems
from sentlmon.period import Reader

OLD = "Latteria Valdese"
OLD_PAGE = "https://guida.example/latteria-valdese"


def subject(**changes):
    return {"label": "Avenello", "aliases": ["Avenello", OLD], "former": [OLD], **changes}


class FieldTest(unittest.TestCase):

    def test_a_former_name_is_one_of_the_aliases(self):
        self.assertEqual(namesake_problems(subject()), [])
        self.assertEqual(namesake_problems({"aliases": ["Avenello"]}), [])
        for former in (["Vecchio nome"], "Avenello", [""]):
            self.assertEqual([f for f, _ in namesake_problems({"aliases": ["Avenello"], "former": former})],
                             ["subject.former"], former)


class FormerOnlyTest(unittest.TestCase):

    def test_an_answer_naming_the_subject_by_its_former_name_alone(self):
        reader = Reader({"subject": subject()})
        self.assertTrue(reader.former_only("La Latteria Valdese vende latte d'avena."))
        self.assertFalse(reader.former_only("Avenello, ex Latteria Valdese, vende latte d'avena."))
        self.assertFalse(reader.former_only("Avoria vende latte d'avena."))
        self.assertFalse(reader.former_only(None))

    def test_a_study_without_former_names_has_no_such_answer(self):
        reader = Reader({"subject": {"label": "Avenello", "aliases": ["Avenello", OLD]}})
        self.assertFalse(reader.former_only("La Latteria Valdese vende latte d'avena."))


class AllowedTest(unittest.TestCase):

    def test_the_counts_of_the_former_name_may_be_cited(self):
        cell = {"figure": False, "mean": None, "coverage": None, "judged": 0, "expected": 0, "received": 0,
                "presence": {"named": 7, "given": 11, "rate": None, "position": None},
                "owned": {"citing": 0, "with_sources": 0}, "former": {"answers": 5, "pages": [["guida.example/x", 3]]}}
        pairs = check._allowed([{"total": cell, "by_model": {}}])[2]
        self.assertTrue({(5, 11), (5, 7), (3, 5)} <= pairs, pairs)


class FormerCase(DeckCase):
    """Runs 9102 and 9103 add, on the question naming no brand, three answers naming the subject by its former name
    alone, two of them citing a guide, and one naming it by both names: 3 of the 6 answers to it."""

    def setUp(self):
        super().setUp()
        study = self.read("study.json")
        study["subject"].update(aliases=[*study["subject"]["aliases"], OLD], former=[OLD])
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")
        old = ("La migliore è quella della Latteria Valdese.", 3, [OLD_PAGE])
        self.ingest_market(9102, OCT[1], rows(price=(CURRENT, CURRENT), choice=(old, ("Latteria Valdese, buona.", 3, []))))
        both = ("Avenello, ex Latteria Valdese, è buona.", 3, ["https://avenello.example/chi-siamo"])
        self.ingest_market(9103, OCT[2], rows(price=(CURRENT, CURRENT), choice=(old, both)))
        self.build(DATE)
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)


class PeriodTest(FormerCase, unittest.TestCase):

    def test_the_period_counts_the_answers_carrying_only_the_former_name_and_their_pages(self):
        choice = self.question(DATE, "scelta", CHOICE_Q)
        self.assertEqual(choice["total"]["former"], {"answers": 3, "pages": [["guida.example/latteria-valdese", 2]]})
        self.assertEqual((choice["by_model"][GPT]["former"]["answers"], choice["by_model"][GEM]["former"]["answers"]), (2, 1))

    def test_a_study_without_former_names_keeps_its_period_as_it_was(self):
        study = self.read("study.json")
        del study["subject"]["former"]
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")
        self.build(DATE)
        self.assertNotIn("former", self.question(DATE, "scelta", CHOICE_Q)["total"])


class DeckTest(FormerCase, unittest.TestCase):

    def test_the_presence_row_carries_the_count(self):
        row = deck.build_model(*self.model_args({}))["blocks"]["reach"]["rows"][0]
        self.assertEqual((row["former"], row["named"], row["given"]), (3, 4, 6))

    def test_the_figures_file_lists_the_answers_and_their_pages(self):
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertIn(f"only by a former name ({OLD}): 3 su 6; pages they cite: guida.example/latteria-valdese (2)", text)

    def test_the_presence_chart_draws_the_count(self):
        self.save_doc(self.filled())
        html = deck.page_of(self.study, DATE)[0]
        self.assertIn("Solo col nome di prima", html)
        self.assertIn('class="rows reach-rows former', html)

    def doc(self, why):
        doc = self.filled()
        doc["actions"].append({"class": "wrong_fact", "block": "reach",
                               "what": f"Chiedere a guida.example di scrivere Avenello al posto di {OLD}",
                               "why": why, "read_next": f"Risposte che nominano Avenello solo come {OLD}",
                               "pages": [{"url": "guida.example/latteria-valdese", "shows": [OLD]}]})
        return doc

    def test_check_accepts_a_correction_resting_on_the_former_name_count(self):
        accepted = self.problems(self.doc(f"3 delle 6 risposte nominano Avenello solo come {OLD}"))
        self.assertNotIn("3 delle 6", accepted)
        self.assertIn("3 delle 7", self.problems(self.doc(f"3 delle 7 risposte nominano Avenello solo come {OLD}")))
