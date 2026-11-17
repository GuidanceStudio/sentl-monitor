"""The sources slide says what each site does for the subject: its own pages the assistants read, the sites the actions
are about, and the review sites grouped on one line with the answers citing them. Nobody has to explain why a site has
no action."""

import json
import unittest

from fixtures import CHOICE_Q, GEM, GPT
from sentlmon import deck, fit
from sentlmon import theme as sentl_theme
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


class ActionSitesTest(unittest.TestCase):
    """A site several actions name lists every one of their numbers: keeping its first action's alone, a site named by
    actions 1 and 3 read as concerning action 1 (M39 T17)."""

    DOC = {"actions": [{"what": "Pubblicare su avenello.example una pagina sui prezzi"},
                       {"what": "Chiedere a a.example di aggiungere Avenello"},
                       {"what": "Aggiornare su avenello.example la pagina dei punti vendita"}]}

    def note(self, doc, lang):
        return deck._sources_table(doc, model(source(THIRD)), deck.DECK[lang], "Avenello")

    def test_a_site_named_by_two_actions_lists_both_numbers(self):
        self.assertIn("Le azioni riguardano avenello.example (azioni 1 e 3) e a.example (azione 2).", self.note(self.DOC, "it"))
        self.assertIn("The actions are about avenello.example (actions 1 and 3) and a.example (action 2).",
                      self.note(self.DOC, "en"))

    def test_a_site_named_by_three_actions_lists_them_in_a_list(self):
        doc = {"actions": [{"what": f"Pubblicare su avenello.example la pagina {n}"} for n in range(3)]}
        self.assertIn("Le azioni riguardano avenello.example (azioni 1, 2 e 3).", self.note(doc, "it"))
        self.assertIn("The actions are about avenello.example (actions 1, 2 and 3).", self.note(doc, "en"))

    def test_a_site_named_twice_in_one_action_counts_that_action_once(self):
        doc = {"actions": [{"what": "Scrivere su avenello.example/prezzi e su avenello.example/negozi il prezzo di oggi"}]}
        self.assertIn("Le azioni riguardano avenello.example (azione 1).", self.note(doc, "it"))


class CompetitorColumnTest(DeckCase, unittest.TestCase):
    """The column of the answers citing competitors' pages is drawn when a foil carries its domains. Without them no
    cited site is told a competitor's, and the column printed 0 beside a competitor's site listed among the other sites;
    `deck` names the foils without domains, whose sites count among the third parties (M39 T17)."""

    HEAD = "<th>Citano pagine dei concorrenti</th>"
    LINE = "Foils with no domains in study.json: {names}. Their sites are counted among the third parties"
    NO_COLUMN = ", and the sources slide draws no column of competitors' pages"

    def section(self, doc, kind):
        self.save_doc(doc)
        text = deck.page_of(self.study, DATE)[0]
        at = text.index(f'<section class="slide {kind}')
        return text[at:text.index("</section>", at)]

    def foils(self, foils):
        study = self.read("study.json")
        study["foils"] = foils
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.cli("deck", "--study", self.study, "--date", DATE, check=0).stdout

    def figures(self):
        return (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")

    def test_foils_with_domains_draw_the_column_as_before(self):
        page = self.section(self.filled(), "sources")
        self.assertIn(self.HEAD, page)
        self.assertEqual(page.count("<th>"), 5)
        # The choice question's answer citing avoria.example counts as a competitor's page, not among the other sites.
        self.assertIn('<td class="class">Domande senza il nome di Avenello</td><td><span class="fig">0 su 2</span>', page)
        self.assertIn('<td><span class="fig">1 su 2</span>', page)
        self.assertNotIn("avoria.example", page)
        self.assertNotIn("Foils with no domains", self.made.stdout)
        self.assertIn("competitors' pages", self.figures())

    def test_without_foil_domains_the_column_is_left_out_and_the_operator_told(self):
        said = self.foils([{"id": "avoria", "label": "Avoria", "aliases": ["Avoria"]}])
        self.assertIn(self.LINE.format(names="Avoria") + self.NO_COLUMN + ".", said)
        page = self.section(self.filled(), "sources")
        self.assertNotIn(self.HEAD, page)
        self.assertEqual(page.count("<th>"), 4)
        self.assertIn("avoria.example (1)", page)
        en = self.study / "study.json"
        study = json.loads(en.read_text(encoding="utf-8"))
        study["report_language"] = "en"
        en.write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertNotIn("<th>Cite competitors' pages</th>", self.section(self.filled(), "sources"))
        figures = self.figures()
        self.assertNotIn("competitors' pages", figures)
        self.assertNotIn("competitors' domains cited most", figures)

    def test_a_foil_without_domains_beside_one_with_them_keeps_the_column_and_is_named(self):
        said = self.foils([{"id": "avoria", "label": "Avoria", "aliases": ["Avoria"], "domains": ["avoria.example"]},
                           {"id": "brezza", "label": "Brezza", "aliases": ["Brezza"]}])
        self.assertIn(self.LINE.format(names="Brezza") + ".", said)
        self.assertNotIn(self.NO_COLUMN, said)
        self.assertIn(self.HEAD, self.section(self.filled(), "sources"))

    def test_check_and_the_estimates_read_a_slide_without_the_column(self):
        self.foils([{"id": "avoria", "label": "Avoria", "aliases": ["Avoria"]}])
        doc = self.filled()
        self.save_doc(doc)
        folder, study, period, _ = self.model_args(doc)
        m = deck.build_model(folder, study, period, doc)
        self.assertEqual(deck._overflowing(folder, study, period, doc, m), [])
        self.assertEqual(deck._wordy(folder, study, period, doc, m), [])
        order, slides = deck._slides(study, period, doc, m, sentl_theme.resolve(folder)[0])
        height = fit.heights(slides[[kind for kind, _, _ in order].index("sources")], deck.STYLE)[0]
        self.assertLess(height, fit.PAGE_HEIGHT)
        self.assertEqual(self.problems(doc), "")


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
