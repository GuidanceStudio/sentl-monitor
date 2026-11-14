"""Presence as the reader can weigh it: one position per market, never a rank pooled over a market where the subject leads
and one where it is absent; and, on few answers per question, which assistants name the subject rather than how often."""

import json
import unittest
from collections import Counter
from unittest import mock

from fixtures import GEM, GPT
from sentlmon import deck
from test_deck import DATE, DeckCase


def reach_row(label, named, given, rivals, by_model=None):
    return {"project": "Mercato", "dimension": label, "label": label, "named": named, "given": given,
            "rivals": Counter(rivals), "left_out": False, "by_model": by_model or {}}


HOME = reach_row("Valdoria", 9, 10, {"Avoria": 8, "Brezza": 2})
AWAY = reach_row("Altrove", 1, 10, {"Avoria": 9, "Brezza": 7})


def card_model(figures, few=False, names=None):
    return {"blocks": {"reach": {"figures": figures, "questions": []}}, "method": [], "subject": "Avenello",
            "names": names or {}, "few": few}


class ByMarketTest(unittest.TestCase):

    def test_by_default_the_block_has_one_position_over_all_its_topics(self):
        f, = deck._block_figures("reach", [HOME, AWAY], True, 3)
        self.assertEqual((f["a"], f["b"], f["rank"]), (10, 20, 2))

    def test_by_market_each_topic_has_its_own_position(self):
        figures = deck._block_figures("reach", [HOME, AWAY], True, 3, by_market=True)
        self.assertEqual([(f["market"], f["a"], f["b"], f["rank"], f["names"]) for f in figures],
                         [("Valdoria", 9, 10, 1, 3), ("Altrove", 1, 10, 3, 3)])

    def test_the_card_draws_one_position_per_market(self):
        figures = deck._block_figures("reach", [HOME, AWAY], True, 3, by_market=True)
        html = deck._visual("reach", card_model(figures), deck.DECK["it"])
        self.assertIn('class="markets"', html)
        self.assertNotIn('class="versus"', html)
        self.assertIn("Posizione tra i 3 nomi monitorati", html)
        self.assertIn("Risposte che nominano Avenello", html)
        cells = html[html.index('class="markets"'):]
        self.assertLess(cells.index("Valdoria"), cells.index("Altrove"))
        self.assertIn("9 su 10", cells)
        en = deck._visual("reach", card_model(figures), deck.DECK["en"])
        self.assertIn("Position among the 3 names monitored", en)


class ByMarketDeckTest(DeckCase, unittest.TestCase):

    def test_the_skeleton_leaves_the_markets_pooled(self):
        self.assertIs(json.loads(self.path.read_text(encoding="utf-8"))["by_market"], False)

    def test_the_figures_file_gives_each_topic_its_position(self):
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"- [^\n]*/ Scelta: 0 su 2; competitors named: Avoria 1 su 2; position 2 su 2\n")

    def test_a_deck_by_market_draws_the_markets_and_passes(self):
        doc = self.filled(by_market=True)
        with mock.patch.object(deck, "FEW_ANSWERS", 1):
            self.assertEqual(self.problems(doc), "")
            html = deck.page_of(self.study, DATE)[0]
        self.assertIn('class="markets"', html)
        self.assertIn("Scelta", html[html.index('class="markets"'):])


class FewAnswersTest(unittest.TestCase):

    NAMES = {GPT: "Acme: Acme Chat", GEM: "Orbit: Orbit Reason", "z/one": "Zenith: Zenith Answer"}

    def figure(self):
        row = reach_row("Valdoria", 2, 6, {"Avoria": 1}, by_model={GPT: [2, 2], GEM: [0, 2], "z/one": [0, 2]})
        return deck._block_figures("reach", [row], True, 2)

    def test_the_card_names_the_assistants_that_name_the_subject(self):
        html = deck._visual("reach", card_model(self.figure(), few=True, names=self.NAMES), deck.DECK["it"])
        self.assertNotIn("meter", html)
        self.assertIn("Assistenti che nominano Avenello in almeno una risposta", html)
        named = html[html.index("in almeno una risposta"):html.index("in nessuna risposta")]
        self.assertIn("Acme Chat", named)
        self.assertNotIn("Orbit Reason", named)
        self.assertIn("Orbit Reason, Zenith Answer", html[html.index("in nessuna risposta"):])

    def test_a_card_on_enough_answers_keeps_the_chart(self):
        html = deck._visual("reach", card_model(self.figure(), few=False, names=self.NAMES), deck.DECK["it"])
        self.assertIn('class="versus"', html)


class OneAnswerApartTest(unittest.TestCase):
    """A comparison resting on one answer reverses with the next reading: 7 of 15 against 6 of 15 is no order."""

    def model(self, a=7, rivals=(("Avoria", 6), ("Brezza", 4))):
        row = reach_row("Valdoria", a, 15, dict(rivals))
        figures = deck._block_figures("reach", [row], True, 3)
        return {"subject": "Gruppo Avenello", "aliases": ["Avenello"], "monitored": ["Avoria", "Brezza"],
                "blocks": {"reach": {"figures": figures, "rows": [row], "questions": [{**row, "key": "q1"}]}}}

    def problems(self, m, **fields):
        doc = {"found": {"title": fields.get("title", ""), "answers": {"reach": fields.get("answer", "")}},
               "blocks": {"reach": [{"title": "", "read": fields.get("read", "")}]}}
        return "\n".join(deck._one_answer_apart(doc, m))

    def test_ahead_of_a_name_one_answer_away_is_refused(self):
        for title in ("Chi cerca una bevanda trova Avenello davanti ad Avoria",
                      "Chi cerca una bevanda trova più spesso Avenello e Avoria, a una risposta di distanza",
                      "Shoppers find Avoria behind Avenello"):
            self.assertIn("one answer", self.problems(self.model(), title=title), title)

    def test_a_position_resting_on_one_answer_is_refused(self):
        for answer in ("Avenello è prima dei tre nomi monitorati, con 7 risposte su 15.",
                       "Avenello è in posizione 1 su 3.", "Avenello is first of the three names monitored."):
            self.assertIn("one answer", self.problems(self.model(), answer=answer), answer)

    def test_the_counts_of_the_sentence_are_what_it_compares(self):
        read = "Sul prezzo Avenello è nominata in 5 risposte su 9, più di Avoria, nominata in 4 su 9."
        self.assertIn("one answer", self.problems(self.model(a=7, rivals=(("Avoria", 2),)), read=read))
        far = "Sul prezzo Avenello è nominata in 6 risposte su 9, più di Avoria, nominata in 4 su 9."
        self.assertEqual(self.problems(self.model(), read=far), "")

    def test_a_comparison_two_answers_apart_or_level_passes(self):
        m = self.model(a=8)
        self.assertEqual(self.problems(m, title="Chi cerca una bevanda trova Avenello davanti ad Avoria",
                                       answer="Avenello è prima dei tre nomi monitorati."), "")
        self.assertEqual(self.problems(self.model(), title="Chi cerca una bevanda trova Avenello alla pari con Avoria"), "")

    def test_rivals_compared_with_each_other_count_when_the_subject_is_not_named(self):
        self.assertIn("one answer", self.problems(self.model(a=1, rivals=(("Avoria", 6), ("Brezza", 5))),
                                                  read="Avoria è davanti a Brezza."))
        self.assertEqual(self.problems(self.model(a=1, rivals=(("Avoria", 6), ("Brezza", 5))),
                                       read="Avoria compare più spesso."), "")


class FewAnswersDeckTest(DeckCase, unittest.TestCase):
    """The fixture asks each question of two assistants once: two answers a question."""

    def test_the_reading_slide_says_the_deck_reads_who_names_the_subject(self):
        self.save_doc(self.filled())
        html = deck.page_of(self.study, DATE)[0]
        self.assertIn("Ogni domanda ha al massimo 2 risposte", html)
        with mock.patch.object(deck, "FEW_ANSWERS", 1):
            self.assertNotIn("Ogni domanda ha al massimo", deck.page_of(self.study, DATE)[0])

    def test_the_check_refuses_a_title_ordering_names_one_answer_apart(self):
        doc = self.filled()
        doc["found"]["title"] = "Chi cerca una bevanda all'avena trova Avoria prima di Avenello"
        self.assertIn("one answer", self.problems(doc))
