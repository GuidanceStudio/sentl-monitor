"""The deck says each thing once, in fewer words (DEVPLAN M37): the writer's text under a card does not restate its
figure, an excerpt points to its row of the table, slide 2 lists the assistants once, the sources slide keeps one count
beside each site, every text has a ceiling in words and a content slide one of 180."""

import unittest
from unittest import mock

from fixtures import CHOICE_Q, PRICE_Q
from sentlmon import deck, quick
from test_deck import DATE, DeckCase
from test_deck_sources import THIRD, model, source
from test_insights_period import CURRENT, OUTDATED
from test_quick import QuickCase


def words(n):
    return " ".join(["parola"] * n)


class Rendered(DeckCase):

    def section(self, doc, kind):
        self.save_doc(doc)
        text = deck.page_of(self.study, DATE)[0]
        at = text.index(f'<section class="slide {kind}')
        return text[at:text.index("</section>", at)]


class CardTest(Rendered, unittest.TestCase):

    def test_a_found_answer_restating_the_cards_figure_is_refused(self):
        doc = self.filled()
        doc["found"]["answers"]["description"] = "3 delle 4 risposte su Avenello sono favorevoli."
        self.assertIn("found answer description says 3 of 4, which the card beside it draws: say what lies behind it",
                      self.problems(doc))

    def test_a_found_answer_saying_what_lies_behind_the_figure_passes(self):
        self.assertNotIn("the card beside it draws", self.problems(self.filled()))

    def test_the_note_under_the_presence_card_is_one_line(self):
        figure = {"a": 3, "b": 9, "rivals": [("Avoria", 4), ("Brezza", 1)], "left_out": True, "rank": 2, "names": 3,
                  "project": ""}
        t = deck.DECK["it"]
        html = deck._versus(figure, "Avenello", t)
        self.assertIn("Avenello: posizione 2 su 3 nomi monitorati.", html)
        self.assertIn("Con Avoria (1 in più) e Brezza (2 in meno) l'ordine può invertirsi.", html)
        self.assertNotIn(t["left_out"], html)
        self.assertNotIn("qui i primi", html)
        en = deck._versus(figure, "Avenello", deck.DECK["en"])
        self.assertIn("Avenello: position 2 of 3 names monitored.", en)
        self.assertIn("With Avoria (1 more) and Brezza (2 fewer) the order can reverse.", en)

    def test_answers_left_out_of_a_competitors_count_are_said_on_the_method_slide(self):
        doc = self.filled()
        m = deck.build_model(*self.model_args(doc))
        t = deck.DECK["it"]
        self.assertNotIn(t["left_out"], deck._method(doc, m, t))
        m["blocks"]["reach"]["figures"][0]["left_out"] = True
        self.assertIn(t["left_out"], deck._method(doc, m, t))


class EvidenceTest(Rendered, unittest.TestCase):

    def test_an_excerpt_whose_question_is_in_the_table_points_to_its_row(self):
        page = self.section(self.filled(), "description")
        self.assertEqual(page.count(deck.esc(PRICE_Q)), 1)
        self.assertIn('<span class="row-n">1</span>', page)
        self.assertIn("<b>Domanda 1</b> · ", page)

    def test_excerpts_on_one_question_outside_the_table_print_it_once(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["excerpts"] = [{"text": OUTDATED[0], "question": PRICE_Q, "assistant": "Acme Chat"},
                                                 {"text": CURRENT[0], "question": PRICE_Q, "assistant": "Orbit Reason"}]
        page = self.section(doc, "reach")
        self.assertEqual(page.count(deck.esc(PRICE_Q)), 1)
        self.assertNotIn(deck.esc(CHOICE_Q) + "</div>", page[page.index('class="quotes"'):])

    def test_an_excerpt_holds_at_most_30_words(self):
        self.assertEqual(deck.MAX_WORDS, 30)
        doc = self.filled()
        doc["blocks"]["description"][0]["excerpts"][0]["text"] = words(31)
        self.assertIn("an excerpt holds over 30 words", self.problems(doc))

    def test_the_evidence_slide_does_not_repeat_the_sites_count_the_actions_slide_gives(self):
        doc = self.filled()
        doc["actions"][0].update(what="Chiedere a prezzi.example di correggere il prezzo di Avenello", block="description",
                                 **{"class": "wrong_fact"})
        doc["blocks"]["reach"][0]["action"] = None
        doc["blocks"]["description"][0]["action"] = 1
        strip = self.section(doc, "description")
        strip = strip[strip.index('class="strip"'):]
        self.assertIn("Chiedere a prezzi.example", strip)
        self.assertNotIn("citato da", strip)

    def test_the_actions_slide_gives_a_sites_count_once(self):
        doc = self.filled()
        doc["actions"][0].update(what="Chiedere a prezzi.example di correggere il prezzo di Avenello", block="description")
        doc["blocks"]["reach"][0]["action"] = None
        doc["blocks"]["description"][0]["action"] = 1
        m = deck.build_model(*self.model_args(doc))
        t, order = deck.DECK["it"], deck._order(doc, m, deck.DECK["it"])
        n, total = next((c[1], c[2]) for c in deck._site_counts(doc["actions"][0], 1, doc, m))
        doc["actions"][0]["why"] = "Avenello costa 2,10 € al litro, e le risposte riportano un prezzo diverso."
        self.assertIn(f"prezzi.example: citato da {n} delle {total}", deck._actions_table(doc, order, m, t))
        doc["actions"][0]["why"] = f"prezzi.example è citato da {n} delle {total} risposte e riporta un prezzo vecchio."
        self.assertNotIn("prezzi.example: citato da", deck._actions_table(doc, order, m, t))


class OpeningTest(Rendered, unittest.TestCase):

    def test_each_column_gives_one_example_question(self):
        self.assertEqual(deck.MAX_EXAMPLES, 1)
        doc = self.filled()
        m = deck.build_model(*self.model_args(doc))
        doc["opening"]["examples"]["description"] = [q["key"] for q in m["blocks"]["description"]["questions"]][:2]
        self.assertIn("opening example of description: give one question key, 2 given", self.problems(doc))

    def test_slide_two_lists_the_assistants_once(self):
        page = self.section(self.filled(), "opening")
        self.assertEqual(page.count("Orbit Reason"), 1)
        self.assertNotIn("Assistenti: ", page)

    def test_slide_two_says_how_questions_are_asked_and_rated_and_no_more(self):
        page = self.section(self.filled(), "opening")
        self.assertIn("I numeri contano risposte, non domande: ogni domanda è stata posta una volta, a 2 di questi "
                      "assistenti: Acme Chat e Orbit Reason.", page)
        self.assertIn("Ogni risposta è valutata con un criterio scritto per la sua domanda prima di leggere le risposte:", page)
        self.assertNotIn("primo report", page)
        self.assertNotIn("Ogni domanda ha 2 risposte", page)

    def test_the_method_slide_leaves_how_an_answer_is_rated_to_slide_two(self):
        page = self.section(self.filled(), "method")
        self.assertNotIn("Come è valutata ogni risposta", page)
        self.assertNotIn("favorevole se", page)


class RepeatTest(Rendered, unittest.TestCase):
    """Slide 2 asks each group's question; the slides after it name the group in a few words."""

    def test_an_evidence_slide_opens_with_its_group_not_the_question_of_slide_two(self):
        page = self.section(self.filled(), "reach")
        self.assertIn('<div class="kicker">Domande senza il nome di Avenello</div>', page)
        self.assertNotIn("Chi cerca una bevanda senza fare nomi trova Avenello?", page)

    def test_the_found_slide_names_each_group_without_the_question_of_slide_two(self):
        page = self.section(self.filled(), "found")
        for key in ("reach", "description", "facts"):
            self.assertIn(f'<div class="card-q">{deck.DECK["it"]["groups"][key].format(subject="Avenello")}</div>', page)
        for asked in self.filled()["opening"]["questions"].values():
            self.assertNotIn(asked, page)
        self.assertEqual(self.section(self.filled(), "opening").count("Chi cerca una bevanda senza fare nomi trova Avenello?"), 1)


class SourcesTest(unittest.TestCase):

    def test_no_note_says_how_the_columns_add_up(self):
        page = deck._sources_table({"actions": []}, model(source(THIRD)), deck.DECK["it"], "Avenello")
        self.assertNotIn("sommando le colonne", page)

    def test_beside_each_site_only_the_answers_citing_it(self):
        m = model(source(THIRD, naming={"a.example": 1}), key="reach")
        page = deck._sources_table({"actions": []}, m, deck.DECK["it"], "Avenello")
        self.assertIn("a.example (5)", page)
        self.assertNotIn("con Avenello", page)
        self.assertNotIn("accanto a ogni sito", page)

    def test_a_site_an_action_names_says_how_many_of_its_answers_name_the_subject(self):
        m = model(source(THIRD, naming={"a.example": 1}), key="reach")
        doc = {"actions": [{"what": "Chiedere a a.example di aggiungere Avenello"}]}
        page = deck._sources_table(doc, m, deck.DECK["it"], "Avenello")
        self.assertIn("a.example (5 risposte, 1 con Avenello)", page)


class WordLimitTest(Rendered, unittest.TestCase):

    def test_each_text_has_a_ceiling_in_words(self):
        why = "Avenello compare in 0 risposte su 2 e {}."
        cases = (("found title", 20, lambda d, n: d["found"].update(title=words(n) + ".")),
                 ("found answer description", 25, lambda d, n: d["found"]["answers"].update(description=words(n) + ".")),
                 ("reach read", 25, lambda d, n: d["blocks"]["reach"][0].update(read=words(n) + ".")),
                 ("reach title", 20, lambda d, n: d["blocks"]["reach"][0].update(title=words(n) + ".")),
                 ("action 1 what", 20, lambda d, n: d["actions"][0].update(what=words(n - 2) + " su avenello.example")),
                 ("action 1 why", 20, lambda d, n: d["actions"][0].update(why=why.format(words(n - 8)))))
        for field, limit, put in cases:
            with self.subTest(field):
                doc = self.filled()
                put(doc, limit + 1)
                self.assertRegex(self.problems(doc), rf"{field} holds {limit + 1} words, at most {limit}")
                doc = self.filled()
                put(doc, limit)
                self.assertNotRegex(self.problems(doc), rf"{field} holds \d+ words")

    def test_a_content_slide_over_its_ceiling_is_refused_naming_its_longest_texts(self):
        self.assertEqual(deck.SLIDE_WORDS, 230)
        doc = self.filled()
        doc["found"]["title"] = words(15) + "."
        with mock.patch.object(deck, "SLIDE_WORDS", 60):
            found = self.problems(doc)
        self.assertRegex(found, r"slide 3 holds \d+ words, at most 60: shorten found title \(15 words\)")

    def test_the_cover_and_the_list_of_questions_are_not_counted(self):
        doc = self.filled()
        with mock.patch.object(deck, "SLIDE_WORDS", 30):
            found = self.problems(doc)
        order = deck._order(doc, deck.build_model(*self.model_args(doc)), deck.DECK["it"])
        for n, (kind, _, _) in enumerate(order, 1):
            if kind in ("cover", "questions"):
                self.assertNotIn(f"slide {n} holds", found)
        self.assertIn("slide 2 holds", found)

    def test_a_word_is_what_the_reader_reads_as_one(self):
        self.assertEqual(deck.words("Avenello costa 2,10 € al litro: vedi avenello.example/prezzi — dell'avena."), 8)


class QuickTest(QuickCase, unittest.TestCase):

    def test_a_row_sentence_holds_at_most_25_words(self):
        doc = self.filled()
        self.row(doc, "lavoro")["says"] = words(26) + "."
        self.assertRegex(self.problems(doc), r"slide 2 lavoro.says holds 26 words, at most 25")

    def test_a_row_sentence_restating_its_figure_is_refused(self):
        doc = self.filled()
        self.row(doc, "scelta")["says"] = "Avenello compare in 0 risposte su 2."
        self.assertIn("slide 2 scelta.says says 0 of 2, which its row draws: say what lies behind it", self.problems(doc))

    def test_the_filled_quick_deck_passes(self):
        self.assertEqual(self.problems(self.filled()), "")


if __name__ == "__main__":
    unittest.main()
