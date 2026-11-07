"""The second edition of the deck: what changed since the deck before it, and what became of its actions."""

import json
import re
import unittest

from fixtures import GEM, GPT
from sentlmon import deck
from test_deck import DATE, DeckCase, fake_pdf
from test_insights_period import CURRENT, rows

LATER = "2026-11-30"
LATER_RUN = "2026-11-09T06:00:00Z"
THEN = "Risposte che nominano Avenello: 0 su 2"
WHAT = "Pubblicare una pagina di confronto su avenello.example"


class SecondCase(DeckCase, unittest.TestCase):

    answers = None

    def setUp(self):
        super().setUp()
        self.first = self.filled()
        self.save_doc(self.first)
        self.cli("check", "--study", self.study, self.path, check=0)
        self.ingest_market(9102, LATER_RUN, self.answers or rows())
        self.build(LATER)
        self.made = self.cli("deck", "--study", self.study, "--date", LATER, check=0)
        self.later = self.study / "reports" / f"{LATER}.deck.json"

    def model(self, doc=None):
        folder, _, study, period, _ = deck.load(self.study, LATER)
        return deck.build_model(folder, study, period, doc or {})

    def second(self, **earlier):
        doc = {**json.loads(json.dumps(self.first)), "date": LATER,
               "earlier": {"date": DATE, "title": "Dal 31 ottobre i dati sono rimasti uguali",
                           "read": "Una frase su cosa è rimasto uguale.", "actions_title": "Cosa è successo alle azioni proposte",
                           "now": ["Risposte che nominano Avenello: 0 su 2"]}}
        doc["earlier"].update(earlier)
        return doc

    def problems(self, doc):
        self.later.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return "\n".join(deck.check(self.study, self.later, LATER))


class SkeletonTest(SecondCase):

    def test_the_text_to_fill_carries_the_earlier_deck(self):
        written = json.loads(self.later.read_text(encoding="utf-8"))["earlier"]
        self.assertEqual(written["date"], DATE)
        self.assertEqual(written["now"], [deck.TODO])
        self.assertEqual((written["title"], written["read"], written["actions_title"]), (deck.TODO,) * 3)

    def test_a_first_edition_has_none(self):
        self.assertNotIn("earlier", json.loads(self.path.read_text(encoding="utf-8")))

    def test_the_figures_file_lists_the_earlier_actions_and_both_dates(self):
        text = (self.study / "history" / "deck" / f"{LATER}.figures.md").read_text(encoding="utf-8")
        self.assertIn(f"Compared with the deck of {DATE}", text)
        self.assertIn(WHAT, text)
        self.assertIn(THEN, text)

    def test_a_deck_written_before_the_earlier_one_was_final_gains_the_field_and_keeps_its_text(self):
        doc = self.second()
        del doc["earlier"]
        self.later.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.cli("deck", "--study", self.study, "--date", LATER, check=0)
        kept = json.loads(self.later.read_text(encoding="utf-8"))
        self.assertEqual(kept["found"], doc["found"])
        self.assertEqual(kept["earlier"]["now"], [deck.TODO])


class ProgressTest(DeckCase, unittest.TestCase):
    """A session the host compacts starts again: `deck` tells it where the text stands."""

    def said(self):
        return self.cli("deck", "--study", self.study, "--date", DATE, check=0).stdout

    def test_deck_counts_the_texts_left_to_write(self):
        self.assertRegex(self.said(), r"\d+ texts left")
        self.save_doc(self.filled())
        self.assertIn("0 texts left", self.said())

    def test_check_names_the_fields_left_to_write(self):
        doc = self.filled()
        doc["found"]["title"], doc["actions"][0]["why"] = deck.TODO, deck.TODO
        found = self.problems(doc)
        self.assertIn("found.title", found)
        self.assertIn("actions[1].why", found)

    def test_deck_names_the_notes_of_an_earlier_session(self):
        self.assertNotIn("notes", self.said())
        (self.study / "history" / "deck" / f"{DATE}.notes.md").write_text("Risultati letti.", encoding="utf-8")
        self.assertIn(f"{DATE}.notes.md", self.said())


class FiguresTest(SecondCase):

    def test_the_rows_are_the_figures_of_both_dates(self):
        second = self.model()["second"]
        self.assertEqual(second["date"], DATE)
        row = next(r for r in second["rows"] if r["block"] == "facts")
        self.assertEqual((row["before"], row["now"], row["change"]), ((1, 2), (1, 2), None))

    def test_the_actions_come_from_the_earlier_deck(self):
        self.assertEqual(self.model()["second"]["actions"], [{"what": WHAT, "then": THEN}])


class ChangedFactTest(SecondCase):

    answers = rows(price=(CURRENT, CURRENT))

    def test_a_block_moved_by_the_step_is_marked(self):
        row = next(r for r in self.model()["second"]["rows"] if r["block"] == "facts")
        self.assertEqual((row["before"], row["now"], row["change"]), ((1, 2), (2, 2), "up"))


class NothingComparableTest(SecondCase):

    def setUp(self):
        super().setUp()
        path = self.study / "history" / "periods" / f"{LATER}.json"
        period = json.loads(path.read_text(encoding="utf-8"))
        for settings in period["settings"].values():
            settings["models"] = [GPT]
        path.write_text(json.dumps(period), encoding="utf-8")

    def test_questions_asked_of_other_assistants_are_not_compared(self):
        self.assertEqual(self.model()["second"]["rows"], [])

    def test_only_the_actions_slide_stays(self):
        order = [kind for kind, _, _ in deck._order(self.second(), self.model(), deck.DECK["it"])]
        self.assertNotIn("changed", order)
        self.assertIn("earlier", order)


class CheckTest(SecondCase):

    def test_a_complete_second_edition_passes(self):
        self.assertEqual(self.problems(self.second()), "")

    def test_a_deck_with_no_earlier_part_is_refused(self):
        doc = self.second()
        del doc["earlier"]
        self.assertIn(f"the deck of {DATE} comes before", self.problems(doc))

    def test_a_first_edition_cannot_claim_one(self):
        doc = self.filled(earlier={"date": "2026-01-31", "now": []})
        self.save_doc(doc)
        self.assertIn("no deck comes before", "\n".join(deck.check(self.study, self.path, DATE)))

    def test_every_earlier_action_needs_its_figure_today(self):
        self.assertIn("1 earlier action", self.problems(self.second(now=[])))

    def test_a_figure_today_needs_a_figure(self):
        self.assertIn("carries no figure", self.problems(self.second(now=["Il dato è migliorato"])))

    def test_a_figure_the_period_does_not_hold_is_refused(self):
        self.assertIn("7", self.problems(self.second(now=["Risposte che nominano Avenello: 7 su 9"])))

    def test_a_cause_is_refused(self):
        for text in ("Il dato sale grazie alla pagina pubblicata", "The figure rose thanks to the new page"):
            with self.subTest(text):
                self.assertIn("cause", self.problems(self.second(read=text)))


class PackTest(SecondCase):

    def test_a_slim_pack_carries_what_the_second_edition_reads(self):
        pack, target = self.study.parent / "study.zip", self.study.parent / "carried"
        self.cli("pack", "--study", self.study, "--out", pack, check=0)
        self.cli("unpack", "--study", target, pack, check=0)
        self.study = target
        (target / "inbox").mkdir()
        self.build(LATER)
        (target / "history" / "runs" / "market" / "9101.json.gz").unlink()  # a later report leaves this deck's runs out
        self.assertEqual(self.model()["second"]["date"], DATE)


class SlidesTest(SecondCase):

    def page(self):
        self.later.write_text(json.dumps(self.second(), ensure_ascii=False), encoding="utf-8")
        return deck.page_of(self.study, LATER)[0]

    def test_the_two_slides_follow_what_was_found(self):
        kinds = re.findall(r'<section class="slide (\w+)', self.page())
        self.assertEqual(kinds[:6], ["cover", "opening", "found", "changed", "earlier", "actions"])

    def test_the_actions_slide_shows_the_action_and_both_figures(self):
        slide = re.search(r'<section class="slide earlier.*?</section>', self.page(), re.S).group(0)
        for text in (WHAT, THEN, "31 ottobre 2026"):
            self.assertIn(text, slide)

    def test_the_changed_slide_shows_both_dates_and_the_note(self):
        slide = re.search(r'<section class="slide changed.*?</section>', self.page(), re.S).group(0)
        self.assertIn("31 ottobre 2026", slide)
        self.assertIn("stessi assistenti", slide)

    def test_a_first_edition_shows_neither(self):
        self.save_doc(self.first)
        kinds = re.findall(r'<section class="slide (\w+)', deck.page_of(self.study, DATE)[0])
        self.assertNotIn("changed", kinds)
        self.assertNotIn("earlier", kinds)

    def test_the_second_edition_renders_with_its_two_slides(self):
        self.later.write_text(json.dumps(self.second(), ensure_ascii=False), encoding="utf-8")
        count = deck.page_of(self.study, LATER)[1]
        deck.render(self.study, LATER, printer=fake_pdf(count))
        self.assertTrue((self.study / "reports" / f"{LATER}.deck.pdf").exists())


if __name__ == "__main__":
    unittest.main()
