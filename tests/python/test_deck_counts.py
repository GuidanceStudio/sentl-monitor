"""`check` on a deck: every count is read, and a count beside a name is that name's."""

import unittest
from collections import Counter
from unittest import mock

from test_deck import DeckCase  # first: fixtures puts the scripts on the path
from sentlmon import deck
from sentlmon.common import domain_of

ACME, ORBIT = "acme/chat", "orbit/reason"
HIDDEN = ("https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc", "guida.example")
LIST = "https://guida.example/lista"
SUB = "https://it.guida.example/altra"
PIECE = "https://rivista.example/pezzo"
OWN = "https://avenello.example/prezzi"
RIVAL = "https://avoria.example/confronto"


def answer(model, *urls):
    pairs = [u if isinstance(u, tuple) else (u, None) for u in urls]
    return {"model": model, "answer": "Una risposta.", "score": 3,
            "sources": [{"url": u, "title": t, "domain": domain_of(u, t)} for u, t in pairs]}


def question(key, dimension, given, rivals=None):
    return {"key": key, "label": f"Domanda {key}", "project": "Mercato", "dimension": dimension, "given": given, "judged": given,
            "named": 0, "rivals": Counter(rivals or {}), "foils": [], "bands": {"1-2": 0, "3": given, "4-5": 0}}


def topic(dimension, given, rivals=None):
    return {**question(None, dimension, given, rivals), "label": dimension}


def model():
    """Six answers without the name on two topics, three on the subject: nine in the period."""
    on_account = [answer(ACME, LIST, PIECE), answer(ACME, LIST), answer(ORBIT, HIDDEN), answer(ORBIT, SUB)]
    on_invoices = [answer(ACME, PIECE), answer(ORBIT)]
    on_subject = [answer(ACME, OWN, PIECE), answer(ORBIT, OWN), answer(ORBIT, RIVAL)]
    author = {"avenello.example": "owned", "avoria.example": "Avoria"}
    return {"subject": "Avenello", "names": {ACME: "Acme: Acme Chat", ORBIT: "Orbit: Orbit Reason"}, "monitored": ["Avoria"],
            "author": lambda d: author.get(d, "third"),
            "answers_of": {"q1": on_account, "q2": on_invoices, "q3": on_subject},
            "blocks": {"reach": {"rows": [topic("Conto", 4, {"Avoria": 3}), topic("Fatture", 2, {"Avoria": 1})],
                                 "questions": [question("q1", "Conto", 4, {"Avoria": 3}), question("q2", "Fatture", 2, {"Avoria": 1})],
                                 "figures": [{"a": 1, "b": 6, "rivals": [("Avoria", 4)], "rank": 2, "names": 2}],
                                 "responses": on_account + on_invoices},
                       "description": {"rows": [topic("Prezzo", 3)], "questions": [question("q3", "Prezzo", 3)],
                                       "figures": [], "responses": on_subject},
                       "facts": {"rows": [], "questions": [], "figures": [], "responses": []}}}


class TiedCase:

    def tied(self, text, m=None):
        """What `check` says of a sentence, and the counts it judged beside a name."""
        return deck._tied_counts({"sources": {"read": text}}, m or model())

    def passes(self, *texts):
        for text in texts:
            self.assertEqual(self.tied(text)[0], [], text)

    def refused(self, text, *words):
        found = "\n".join(self.tied(text)[0])
        self.assertTrue(found, text)
        for word in words:
            self.assertIn(word, found)


class SiteCountTest(TiedCase, unittest.TestCase):

    def test_the_true_count_of_a_site_passes(self):
        self.passes("guida.example è citato in 4 delle 6 risposte.", "4 delle 6 risposte citano guida.example.",
                    "On accounts guida.example is cited by 4 of the 6 answers.")

    def test_a_count_a_site_does_not_have_is_refused_with_the_real_one(self):
        self.refused("guida.example è citato in 5 delle 6 risposte.", "guida.example", "4 of 6")
        self.refused("5 delle 6 risposte citano guida.example.", "4 of 6")

    def test_a_site_counts_with_its_subdomains_or_alone(self):
        self.passes("guida.example è citato in 3 delle 6 risposte.", "it.guida.example è citato in 1 delle 6 risposte.")

    def test_a_count_on_a_topic_a_question_or_the_period_passes(self):
        self.passes("Sul conto guida.example è citato in 4 delle 4 risposte.", "rivista.example è citato in 3 delle 9 risposte.")

    def test_a_count_on_the_answers_of_one_project_passes(self):
        m = model()
        m["blocks"]["reach"]["questions"][1]["project"] = m["blocks"]["reach"]["rows"][1]["project"] = "Altro"
        self.assertEqual(self.tied("guida.example è citato in 4 delle 4 risposte.", m)[0], [])

    def test_a_count_on_the_answers_scored_or_on_all_given_passes(self):
        m = model()
        m["answers_of"]["q3"][0]["score"] = None
        self.assertEqual(self.tied("avenello.example è citato in 2 delle 3 risposte.", m)[0], [])
        self.assertEqual(self.tied("avenello.example è citato in 1 delle 2 risposte.", m)[0], [])

    def test_a_site_may_go_by_its_name_in_parentheses(self):
        self.passes("Guida (4 su 6) resta senza azione.")
        self.refused("Guida (2 su 6) resta senza azione.", "4 of 6")

    def test_a_name_the_answers_may_only_mention_is_no_site(self):
        self.passes("Guida è citata in 5 delle 6 risposte.", "Tutte le 9 risposte citano Guida.")

    def test_a_count_of_something_else_beside_a_site_is_not_the_site_s(self):
        self.passes("Su guida.example 3 risposte su 9 sono favorevoli.")

    def test_a_count_with_no_site_beside_it_is_left_to_the_figures(self):
        self.passes("3 delle 9 risposte sul prezzo citano anche 99 €.")

    def test_the_counts_judged_beside_a_site_do_not_go_through_the_period_s_figures(self):
        self.assertEqual(self.tied("guida.example è citato in 4 delle 6 risposte.")[1], {(4, 6)})


class PageCountTest(TiedCase, unittest.TestCase):

    def test_the_count_of_a_page_named_by_its_address_passes(self):
        self.passes("guida.example/lista è citata in 2 delle 6 risposte.")

    def test_a_page_written_in_words_passes_on_its_own_count(self):
        self.passes("La lista di guida.example, citata in 2 delle 6 risposte, non nomina Avenello.")

    def test_the_site_s_count_beside_a_page_is_refused(self):
        self.refused("guida.example/lista è citata in 4 delle 6 risposte.", "guida.example/lista")
        self.refused("La lista di guida.example, citata in 4 delle 6 risposte, non nomina Avenello.", "page")

    def test_the_page_s_count_beside_its_site_is_refused(self):
        self.refused("guida.example è citato in 2 delle 6 risposte.", "4 of 6")

    def test_answers_citing_the_site_through_a_redirect_may_have_read_the_page(self):
        self.passes("guida.example/lista è citata in 3 delle 6 risposte.")
        self.refused("guida.example/lista è citata in 1 delle 6 risposte.", "2 to 3 of 6")


class AssistantCountTest(TiedCase, unittest.TestCase):

    def test_a_count_of_one_assistant_is_that_assistant_s(self):
        self.passes("2 delle 3 risposte di Acme Chat citano guida.example.")
        self.refused("3 delle 3 risposte di Acme Chat citano guida.example.", "2 of 3")

    def test_the_refusal_says_the_base_is_that_assistant_s_answers(self):
        self.refused("3 delle 3 risposte di Acme Chat citano guida.example.", "2 of 3", "answers of Acme Chat only")

    def test_an_assistant_may_go_by_its_maker(self):
        self.refused("3 delle 3 risposte di Acme citano guida.example.", "2 of 3")

    def test_a_count_of_one_assistant_on_a_page_is_that_assistant_s(self):
        self.passes("2 delle 3 risposte di Acme Chat citano guida.example/lista.")
        self.refused("2 delle 3 risposte di Orbit Reason citano guida.example/lista.", "0 to 1 of 3")


class CompetitorCountTest(TiedCase, unittest.TestCase):

    def test_the_true_count_of_a_competitor_passes(self):
        self.passes("Avoria è nominata in 4 risposte su 6.", "Avoria in 3 su 4 sul conto.", "Avoria (4 su 6) è la prima.")

    def test_a_count_a_competitor_does_not_have_is_refused_with_the_real_one(self):
        self.refused("Avoria è nominata in 5 risposte su 6.", "Avoria", "4 of 6")
        self.refused("Avoria in 2 su 4 sul conto.", "3 of 4")

    def test_a_count_with_no_base_beside_a_competitor_must_be_one_of_its_counts(self):
        self.passes("Avoria è in 3.", "Avoria (4) è la prima.")
        self.refused("Avoria è in 7.", "Avoria")

    def test_a_topic_named_after_a_competitor_is_no_count_of_it(self):
        self.passes("Su Avoria 2 su 3 sono favorevoli.", "Nel confronto con Avoria 1 risposta su 3 è favorevole.")


class BaseTest(TiedCase, unittest.TestCase):

    def test_a_count_beside_a_site_gives_its_base(self):
        for text in ("Guida (4) resta senza azione.", "guida.example è citato da 4 risposte.", "4 risposte citano guida.example.",
                     "4 citano guida.example.", "guida.example is cited by 4 answers."):
            self.refused(text, "base", "4 of 6")

    def test_a_count_after_by_beside_the_site_cited_most_is_that_site_s(self):
        self.passes("guida.example è il sito più citato su queste domande, da 4 risposte.",
                    "guida.example is the site cited most on these questions, by 4 answers.",
                    "guida.example, the most cited site, by 4 answers.")
        self.refused("guida.example is the site cited most on these questions, by 5 answers.", "guida.example", "4 of 6")
        self.refused("guida.example, the most cited site, by 5 answers.", "4 of 6")

    def test_all_and_none_of_a_count_are_a_base(self):
        self.passes("Tutte le 4 risposte citano guida.example.", "Nessuna delle 6 risposte cita altro.example.")

    def test_a_count_beside_a_page_in_words_gives_its_base(self):
        self.refused("La guida di rivista.example è il sito, e 2 risposte citano questa guida.", "base", "page")

    def test_a_count_after_the_site_said_to_be_cited_most_is_of_the_page_it_cites(self):
        self.refused("Guida è il sito esterno più citato senza il nome, e 2 risposte citano questa guida.", "a page of Guida", "2 to 3 of 6")


class MostCitedTest(unittest.TestCase):

    def most(self, text, m=None):
        return deck._most_cited({"sources": {"title": text}}, m or model())

    def test_the_site_cited_most_passes(self):
        self.assertEqual(self.most("Senza il nome le risposte citano soprattutto guida.example."), [])
        self.assertEqual(self.most("Il sito più citato è avenello.example."), [])

    def test_a_site_that_comes_first_on_no_scope_is_refused_with_the_one_that_does(self):
        found = "\n".join(self.most("Le risposte citano soprattutto rivista.example."))
        self.assertIn("rivista.example", found)
        self.assertIn("guida.example", found)

    def test_on_the_sources_slide_a_site_comes_first_on_a_whole_block(self):
        m = model()
        m["blocks"]["reach"]["rows"][1]["project"] = m["blocks"]["reach"]["questions"][1]["project"] = "Altro"
        self.assertTrue(self.most("Le risposte citano soprattutto rivista.example.", m))
        self.assertEqual(deck._most_cited({"actions": [{"why": "Sulle fatture le risposte citano soprattutto rivista.example."}]}, m), [])

    def test_a_sentence_on_third_parties_leaves_the_subject_s_site_out(self):
        self.assertEqual(self.most("Tra i siti di terzi le risposte citano soprattutto rivista.example."), [])

    def test_a_site_level_with_another_is_no_most(self):
        m = model()
        for key in ("q1", "q2", "q3"):
            m["answers_of"][key] = []
        tied = [answer(ACME, "https://uno.example/a"), answer(ORBIT, "https://due.example/b")]
        m["answers_of"]["q1"] = m["blocks"]["reach"]["responses"] = tied
        m["blocks"]["description"]["responses"] = []
        self.assertIn("level", "\n".join(self.most("Le risposte citano soprattutto uno.example.", m)))

    def test_the_title_of_the_sources_slide_ranks_the_site_it_says_the_answers_cite(self):
        self.assertIn("rivista.example", "\n".join(self.most("Le risposte citano rivista.example.")))
        self.assertEqual(self.most("Le risposte citano guida.example."), [])
        self.assertEqual(deck._most_cited({"sources": {"read": "Le risposte citano rivista.example."}}, model()), [])

    def test_a_sentence_on_something_else_is_left_alone(self):
        self.assertEqual(self.most("Le pagine citate sono soprattutto di altri siti."), [])
        self.assertEqual(self.most("Avenello costa soprattutto meno, dice guida.example."), [])


class EveryCountIsReadTest(DeckCase, unittest.TestCase):

    def said(self, text):
        """What `check` says of a sentence on the sources slide, which has no chart to hold it to."""
        doc = self.filled()
        doc["sources"]["read"] += " " + text
        return self.problems(doc)

    def test_a_count_written_as_delle_is_read(self):
        self.assertIn("count 7 delle 9", self.said("Il dato compare in 7 delle 9 risposte."))

    def test_a_count_written_as_of_the_is_read(self):
        self.assertIn("count 7 of the 9", self.said("The figure is in 7 of the 9 answers."))

    def test_a_count_with_no_word_for_answers_near_it_is_read(self):
        self.assertIn("count 7 su 9", self.said("Sul prezzo il dato compare in 7 su 9."))

    def test_a_count_of_questions_or_assistants_is_no_count_of_answers(self):
        self.assertEqual(self.said("Il dato compare in 2 domande su 3 e in 1 assistente su 2."), "")
        self.assertEqual(self.said("Il dato compare in 2 su 3 domande."), "")

    def test_a_true_site_count_the_figures_do_not_hold_passes(self):
        with mock.patch.object(deck, "_allowed_figures", return_value=(set(), set(), set())):
            self.assertNotIn("count 1 delle 6", self.said("prezzi.example è citato in 1 delle 6 risposte."))

    def test_a_site_count_stands_in_a_reason_and_over_a_chart_that_do_not_draw_it(self):
        doc = self.filled()
        doc["actions"][0]["why"] += "; prezzi.example è citato in 1 delle 6 risposte"
        doc["blocks"]["reach"][0]["read"] = "prezzi.example è citato in 1 su 6 risposte."
        self.assertEqual(self.problems(doc), "")

    def test_a_false_site_count_is_refused_once(self):
        found = self.said("prezzi.example è citato in 5 delle 6 risposte.")
        self.assertIn("prezzi.example", found)
        self.assertNotIn("count 5 delle 6", found)


if __name__ == "__main__":
    unittest.main()
