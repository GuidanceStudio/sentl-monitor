"""The sources slide says what each site does for the subject: its own pages the assistants read, the sites the actions
are about, and the review sites grouped on one line with the answers citing them. Nobody has to explain why a site has
no action."""

import unittest

from fixtures import CHOICE_Q, GEM, GPT
from sentlmon import deck
from test_deck import DATE, DeckCase
from test_insights_period import OCT, rows


def source(third, reviews=None, naming=None):
    third = dict(third)
    return {"with_sources": 9, "answers": 12, "owned": 2, "foil": 0, "third": 9,
            "third_domains": [{"domain": d, "answers": n} for d, n in third.items()][:5], "third_all": third,
            "third_naming": naming or {}, "owned_pages": [("avenello.example/prezzi", 4)],
            "reviews": reviews or {"answers": 0, "naming": 0, "domains": []}}


def model(block_source, key="description"):
    empty = {"rows": [], "sources": source({})}
    blocks = {"reach": dict(empty), "description": dict(empty), "facts": dict(empty)}
    blocks[key] = {"rows": [1], "sources": block_source}
    return {"blocks": blocks, "subject": "Avenello", "aliases": [], "namesakes": []}


REVIEWS = {"answers": 8, "naming": 2, "domains": ["it.trustpilot.com", "it.indeed.com"]}
THIRD = [("it.trustpilot.com", 6), ("a.example", 5), ("it.indeed.com", 3)]


class SourcesSlideTest(unittest.TestCase):

    def test_review_sites_are_grouped_on_one_line_with_the_answers_citing_them(self):
        page = deck._sources_table({"actions": []}, model(source(THIRD, REVIEWS)), deck.DECK["it"], "Avenello")
        self.assertIn("siti di recensioni: it.trustpilot.com, it.indeed.com (8), a.example (5)", page)
        self.assertNotIn("it.trustpilot.com (6)", page)
        en = deck._sources_table({"actions": []}, model(source(THIRD, REVIEWS)), deck.DECK["en"], "Avenello")
        self.assertIn("review sites: it.trustpilot.com, it.indeed.com (8)", en)

    def test_a_review_site_on_several_domains_is_listed_once(self):
        reviews = {"answers": 8, "naming": 2, "domains": ["it.trustpilot.com", "trustpilot.com", "it.indeed.com"]}
        page = deck._sources_table({"actions": []}, model(source(THIRD, reviews)), deck.DECK["it"], "Avenello")
        self.assertIn("siti di recensioni: it.trustpilot.com, it.indeed.com (8)", page)

    def test_the_review_line_gives_only_the_answers_citing_it(self):
        m = model(source(THIRD, REVIEWS, naming={"a.example": 1}), key="reach")
        page = deck._sources_table({"actions": []}, m, deck.DECK["it"], "Avenello")
        self.assertIn("siti di recensioni: it.trustpilot.com, it.indeed.com (8)", page)
        self.assertNotIn("con Avenello", page)

    def test_the_slide_says_which_sites_the_actions_are_about(self):
        doc = {"actions": [{"what": "Pubblicare su avenello.example una pagina sui prezzi"},
                           {"what": "Chiedere a a.example di aggiungere Avenello"}]}
        page = deck._sources_table(doc, model(source(THIRD)), deck.DECK["it"], "Avenello")
        self.assertIn("Le azioni riguardano avenello.example (azione 1) e a.example (azione 2).", page)
        en = deck._sources_table(doc, model(source(THIRD)), deck.DECK["en"], "Avenello")
        self.assertIn("The actions are about avenello.example (action 1) and a.example (action 2).", en)

    def test_a_deck_without_actions_on_sites_says_nothing_of_them(self):
        page = deck._sources_table({"actions": [{"what": "Scrivere il prezzo nella scheda"}]}, model(source(THIRD)),
                                   deck.DECK["it"], "Avenello")
        self.assertNotIn("Le azioni riguardano", page)

    def test_the_subjects_own_pages_are_listed(self):
        page = deck._sources_table({"actions": []}, model(source(THIRD)), deck.DECK["it"], "Avenello")
        self.assertIn("Pagine di Avenello più citate (risposte): avenello.example/prezzi (4)", page)


class ReviewSitesTest(DeckCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        cited = ["https://it.trustpilot.com/review/avoria.example", "https://guida.example/x"]
        choice = (("La migliore è Avoria.", 3, cited), ("Avenello è buona.", 3, ["https://it.trustpilot.com/review/avenello"]))
        self.ingest_market(9102, OCT[1], rows(choice=choice))
        self.build(DATE)
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)

    def test_the_period_counts_the_answers_citing_a_review_site(self):
        m = deck.build_model(*self.model_args({}))
        self.assertEqual(m["blocks"]["reach"]["sources"]["reviews"], {"answers": 2, "naming": 1, "domains": ["it.trustpilot.com"]})

    def test_the_figures_file_lists_the_review_sites(self):
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertIn("review sites: it.trustpilot.com (2 answers cite at least one, 1 of which name the subject)", text)

    def test_the_most_cited_site_needs_no_reason_for_having_no_action(self):
        doc = self.filled()
        doc["sources"]["read"] = "Le risposte citano soprattutto guide e siti di recensioni."
        self.assertNotIn("has no action", self.problems(doc))
