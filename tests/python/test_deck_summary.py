"""The deck opens with a summary and closes on the suggested actions (DEVPLAN M38): slide 3 gives, per group of
questions, one figure and one sentence, then the first action; the presence ranking stands on the first slide of
presence; the actions come after the evidence and the sources, and the method and the questions form an appendix."""

import re
import unittest
from unittest import mock

import fixtures  # noqa: F401  (puts the skill's scripts on the path)
from sentlmon import deck
from test_deck import DATE
from test_deck_brief import Rendered
from test_deck_presence import AWAY, HOME, reach_row


def text_of(section):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", section))


class SummarySlideTest(Rendered, unittest.TestCase):

    def test_slide_three_is_the_summary(self):
        page = self.section(self.filled(), "found")
        self.assertIn('<div class="kicker">In sintesi</div>', page)
        self.assertIn("<h1>Chi cerca una bevanda all'avena trova Avoria</h1>", page)

    def test_each_group_has_its_label_its_figure_and_its_sentence(self):
        doc = self.filled()
        m = deck.build_model(*self.model_args(doc))
        page = self.section(doc, "found")
        t = deck.DECK["it"]
        for key in deck.present(m):
            with self.subTest(key):
                self.assertIn(f'<div class="sum-group">{t["groups"][key].format(subject="Avenello")}</div>', page)
                (_, a, b), = deck._headlines(m["blocks"][key]["figures"])
                self.assertIn(f"{a} <small>su {b}</small>", page)
                self.assertIn(deck.esc(doc["found"]["answers"][key]), page)

    def test_the_summary_ends_on_the_first_action_and_the_slide_of_all_of_them(self):
        doc = self.filled()
        page = text_of(self.section(doc, "found"))
        order = deck._order(doc, deck.build_model(*self.model_args(doc)), deck.DECK["it"])
        n = [kind for kind, _, _ in order].index("actions") + 1
        self.assertIn(f"Prima azione suggerita: {doc['actions'][0]['what']}", page)
        self.assertIn(f"Tutte le azioni: slide {n}", page)

    def test_the_summary_draws_no_chart(self):
        with mock.patch.object(deck, "FEW_ANSWERS", 1):
            page = self.section(self.filled(), "found")
        for chart in ('class="versus"', 'class="markets', 'class="bar"', 'class="legend"', 'class="named-by"'):
            self.assertNotIn(chart, page)

    def test_english_labels(self):
        study = self.read("study.json")
        study["report_language"] = "en"
        (self.study / "study.json").write_text(deck.json.dumps(study, ensure_ascii=False), encoding="utf-8")
        page = text_of(self.section(self.filled(), "found"))
        self.assertIn("In short", page)
        self.assertIn("First suggested action:", page)
        self.assertIn("All the actions: slide", page)


class HeadlineTest(unittest.TestCase):

    def test_the_markets_of_one_project_add_up_to_one_figure(self):
        figures = deck._block_figures("reach", [HOME, AWAY], True, 3, by_market=True)
        self.assertEqual(deck._headlines(figures), [(None, 10, 20)])

    def test_projects_of_different_audiences_keep_a_figure_each(self):
        other = {**reach_row("Valdoria", 2, 8, {}), "project": "Altro"}
        figures = deck._block_figures("reach", [HOME, other], False, 3)
        self.assertEqual(deck._headlines(figures), [("Mercato", 9, 10), ("Altro", 2, 8)])

    def test_the_summary_labels_each_project_figure(self):
        m = {"subject": "Avenello", "fidelity": False,
             "blocks": {"reach": {"figures": [{"project": "Mercato", "a": 9, "b": 10}, {"project": "Altro", "a": 2, "b": 8}]}}}
        html = deck._headline_html("reach", m, deck.DECK["it"])
        self.assertIn("Mercato", html)
        self.assertIn("2 <small>su 8</small>", html)


EMPTY = {key: {"rows": [], "questions": [], "figures": []} for key in deck.BLOCKS}


class SummaryFiguresTest(unittest.TestCase):
    """The sentence beside a figure says what lies behind it; the parts of the figure are drawn on the evidence slides."""

    ROW = {"project": "P", "dimension": "Contatti", "dimensions": ["Contatti"], "label": "Il numero verde è 800 123 456",
           "given": 14, "current": 8, "outdated": 0, "both": 0, "silent": 6, "judged": 14,
           "bands": {"1-2": 2, "3": 4, "4-5": 8}, "asked": 1}

    def problems(self, found):
        m = {"subject": "Avenello", "monitored": ["Avoria"], "answers_of": {}, "author": lambda d: "third",
             "blocks": {**EMPTY, "facts": {"rows": [self.ROW], "questions": [self.ROW],
                                  "figures": [{"a": 8, "b": 14, "parts": [(8, "good"), (0, "low"), (6, "mid")],
                                               "rivals": [], "project": None}]}}}
        doc = {"blocks": {"facts": []}, "found": {"answers": {"facts": found}}}
        return "\n".join(deck._beside_figure(doc, m))

    def test_a_sentence_restating_the_figure_is_refused(self):
        self.assertIn("found answer facts says 8 of 14, which the summary draws beside it: say what lies behind it",
                      self.problems("Il numero verde è riportato in 8 delle 14 risposte."))
        self.assertIn("6 of 14, which the summary draws", self.problems("Il numero verde manca in 6 delle 14 risposte."))

    def test_a_part_of_the_figure_may_be_said(self):
        figure = {"a": 8, "b": 14, "parts": [(5, "good"), (3, "low"), (6, "mid")], "rivals": [], "project": None}
        m = {"subject": "Avenello", "monitored": [], "answers_of": {}, "author": lambda d: "third",
             "blocks": {**EMPTY, "description": {"rows": [self.ROW], "questions": [], "figures": [figure]}}}
        doc = {"blocks": {"description": []}, "found": {"answers": {"description": "Le sfavorevoli, 3 delle 14, parlano dei prezzi."}}}
        self.assertEqual(deck._beside_figure(doc, m), [])
        doc["found"]["answers"]["description"] = "Le favorevoli, 8 delle 14, parlano dei prezzi."
        self.assertIn("which the summary draws", "\n".join(deck._beside_figure(doc, m)))

    def test_a_count_the_block_never_draws_is_refused(self):
        self.assertIn("14 of 14", self.problems("Il numero verde è riportato in tutte le 14 risposte."))


class RankingTest(Rendered, unittest.TestCase):

    def test_the_ranking_stands_on_the_first_slide_of_presence(self):
        doc = self.filled()
        doc["blocks"]["reach"].append({**doc["blocks"]["reach"][0], "action": None, "title": "Un altro titolo"})
        with mock.patch.object(deck, "FEW_ANSWERS", 1):
            self.save_doc(doc)
            text = deck.page_of(self.study, DATE)[0]
        reach = [s for s in text.split("<section ") if s.startswith('class="slide reach')]
        self.assertEqual(len(reach), 2)
        self.assertIn('class="ranking"', reach[0])
        self.assertIn('<b class="me">Avenello 0</b>', reach[0])
        self.assertNotIn('class="ranking"', reach[1])

    def test_the_first_slide_of_presence_may_cite_the_ranking(self):
        rows = [{**r, "bands": {}, "judged": 0} for r in (HOME, AWAY)]
        block = {"rows": rows, "questions": rows, "figures": deck._block_figures("reach", rows, True, 3)}
        part = {"dimensions": ["Valdoria"]}
        self.assertNotIn((10, 20), deck._drawn("reach", block, part))
        self.assertIn((10, 20), deck._drawn("reach", block, part, ranking=True))
        self.assertIn((17, 20), deck._drawn("reach", block, part, ranking=True))


class SummaryWordsTest(Rendered, unittest.TestCase):

    def test_the_summary_has_a_ceiling_of_its_own_naming_its_longest_texts(self):
        doc = self.filled()
        doc["found"]["title"] = " ".join(["parola"] * 15) + "."
        with mock.patch.object(deck, "SUMMARY_WORDS", 40):
            found = self.problems(doc)
        self.assertRegex(found, r"slide 3 holds \d+ words, at most 40: shorten found title \(15 words\)")
        with mock.patch.object(deck, "SLIDE_WORDS", 40):
            self.assertNotIn("slide 3 holds", self.problems(doc))

    def test_the_first_action_counts_among_the_summary_s_texts(self):
        doc = self.filled()
        doc["actions"][0]["what"] = " ".join(["parola"] * 17) + " su avenello.example"
        with mock.patch.object(deck, "SUMMARY_WORDS", 40):
            self.assertRegex(self.problems(doc), r"slide 3 holds \d+ words, at most 40: shorten action 1 what \(19 words\)")


class LimitTest(Rendered, unittest.TestCase):

    def test_the_method_says_the_questions_about_the_subject_were_not_asked_about_competitors(self):
        doc = self.filled()
        m = deck.build_model(*self.model_args(doc))
        t = deck.DECK["it"]
        self.assertIn(t["limit_unasked"].format(subject="Avenello"), deck._method(doc, m, t))
        m["blocks"]["description"]["rows"] = []
        self.assertNotIn(t["limit_unasked"].format(subject="Avenello"), deck._method(doc, m, t))


if __name__ == "__main__":
    unittest.main()
