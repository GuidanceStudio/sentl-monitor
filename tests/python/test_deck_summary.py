"""The deck opens with a summary and closes on the suggested actions (DEVPLAN M38): slide 3 gives, per group of
questions, one figure and one sentence, then the first action; the presence ranking stands on the first slide of
presence; the actions come after the evidence and the sources, and the method and the questions form an appendix."""

import re
import unittest
from unittest import mock

import fixtures  # noqa: F401  (puts the skill's scripts on the path)
from sentlmon import deck, fit
from sentlmon import theme as sentl_theme
from test_deck import DATE
from test_deck_brief import Rendered, words
from test_deck_presence import AWAY, HOME, reach_row
from test_insights_period import OCT, rows


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
        self.assertRegex(found, r"slide 3 holds \d+ words of the writer's texts, at most 40 on the summary: shorten found "
                                r"title \(15 words\)")
        with mock.patch.object(deck, "SLIDE_WORDS", 40):
            self.assertNotIn("slide 3 holds", self.problems(doc))

    def test_the_first_action_counts_among_the_summary_s_texts(self):
        doc = self.filled()
        doc["actions"][0]["what"] = " ".join(["parola"] * 17) + " su avenello.example"
        with mock.patch.object(deck, "SUMMARY_WORDS", 40):
            self.assertRegex(self.problems(doc), r"slide 3 holds \d+ words of the writer's texts, at most 40 on the summary: "
                                                 r"shorten action 1 what \(19 words\)")


class SummaryRoomTest(Rendered, unittest.TestCase):
    """The summary's ceiling counts the writer's texts only (M39 T15): beside the five figures of two projects in two
    blocks, the writer has the room three figures left when the code's words counted."""

    def setUp(self):
        super().setUp()
        self.adopt_audience("trade", 602, "Avenello · Chi lavora nel settore", 9201, OCT[0], rows())
        self.build(DATE)
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)

    def at(self, n):
        """The deck with the summary's texts, its title, the three answers and the first action's what, holding n words."""
        doc = self.filled()
        found = doc["found"]
        texts = [(found, "title"), *((found["answers"], k) for k in ("reach", "description", "facts")), (doc["actions"][0], "what")]
        for (parent, field), size in zip(texts, (n // 5 + (i < n % 5) for i in range(5))):
            parent[field] = f"{parent[field]} {words(size - deck.words(parent[field]))}"
        # Two projects make the price question the description's most unfavourable: it is drawn as a row of its own.
        doc["blocks"]["description"][0]["rows"] = "questions"
        return doc

    def test_the_writer_has_70_words_whatever_the_figures_beside_them(self):
        self.assertEqual(deck.SUMMARY_WORDS, 70)
        doc = self.at(deck.SUMMARY_WORDS)
        self.assertEqual(self.section(doc, "found").count('class="sum-fig"'), 5)
        self.assertEqual(self.problems(doc), "")

    def test_one_word_over_is_refused(self):
        self.assertIn(f"slide 3 holds {deck.SUMMARY_WORDS + 1} words of the writer's texts, at most {deck.SUMMARY_WORDS} "
                      "on the summary: shorten found title", self.problems(self.at(deck.SUMMARY_WORDS + 1)))


def found_height(case, doc):
    """The estimated height of the summary slide of `doc`."""
    folder, study, period, _ = case.model_args(doc)
    m = deck.build_model(folder, study, period, doc)
    order, slides = deck._slides(study, period, doc, m, sentl_theme.resolve(folder)[0])
    return fit.heights(slides[[kind for kind, _, _ in order].index("found")], deck.STYLE)[0]


def lines(markup, line, text):
    """The lines `text` takes in `markup`, where {} stands for it, on a summary slide: read from the estimate against a
    text of one word, `line` px a line."""
    height = lambda t: fit.heights(f'<section class="slide found">{markup.format(t)}</section>', deck.STYLE)[0]
    return 1 + round((height(text) - height("parola")) / line)


class SeveralFiguresTest(unittest.TestCase):
    """A block of several figures puts each project's name on a line of its own above its figure, under a caption
    without the subject, which the names give (M39 T16)."""

    TWO = [{"project": "Mercato", "a": 9, "b": 10}, {"project": "Chi lavora nel settore", "a": 2, "b": 8}]

    def html(self, key, lang="it", fidelity=False):
        m = {"subject": "Avenello", "fidelity": fidelity, "blocks": {key: {"figures": self.TWO}}}
        return deck._headline_html(key, m, deck.DECK[lang])

    def test_each_project_s_name_stands_on_its_own_line_above_its_figure(self):
        self.assertIn('<div class="sum-name">Mercato</div><div class="sum-fig">9 <small>su 10</small></div>'
                      '<div class="sum-name">Chi lavora nel settore</div><div class="sum-fig">2 <small>su 8</small></div>',
                      self.html("description"))
        self.assertNotIn("<span>", self.html("description"))

    def test_the_caption_leaves_out_the_subject_except_on_presence(self):
        self.assertIn('<div class="sum-cap">risposte favorevoli</div>', self.html("description"))
        self.assertIn('<div class="sum-cap">favourable answers</div>', self.html("description", "en"))
        self.assertIn('<div class="sum-cap">risposte che nominano Avenello</div>', self.html("reach"))
        for key in set(deck.BLOCKS) - {"reach"}:
            for lang in ("it", "en"):
                for fidelity in (False, True):
                    with self.subTest(key=key, lang=lang, fidelity=fidelity):
                        self.assertNotIn("Avenello", self.html(key, lang, fidelity))


class OneFigureSummaryTest(Rendered, unittest.TestCase):
    """A summary of one figure a block, the common case, is drawn as before M39 T16."""

    def test_its_figures_and_captions_are_drawn_as_before(self):
        page = self.section(self.filled(), "found")
        self.assertIn('<div class="summary"><div class="sum-row">', page)
        for a, b, caption in ((0, 2, "risposte che nominano Avenello"), (3, 4, "risposte favorevoli a Avenello"),
                              (1, 2, "risposte che riportano il dato di oggi")):
            self.assertIn(f'<div class="sum-figs"><div class="sum-fig">{a} <small>su {b}</small></div>'
                          f'<div class="sum-cap">{caption}</div></div>', page)
        self.assertNotIn("sum-name", page)

    def test_its_height_is_the_one_estimated_before(self):
        doc = self.filled()
        self.save_doc(doc)
        self.assertAlmostEqual(found_height(self, doc), 564.35, delta=0.01)


def hundreds(headlines):
    """`deck._headlines` with three digits in each count, as a study of a hundred answers a block draws them: the
    fixture's counts of one digit leave a project's name room beside its figure."""
    return lambda figures: [(project, 100 + a, 130 + b) for project, a, b in headlines(figures)]


class SeveralFiguresFitTest(Rendered, unittest.TestCase):
    """Two figures in two of the three blocks, of three digits beside project names of four words: with a one-line
    title, three found answers of two lines and a first action of two lines, the summary fits its page (M39 T16)."""

    ANSWERS = {"reach": "Chi chiede la bevanda migliore per colazione sente indicare Avoria o una marca del discount.",
               "description": "Le risposte sfavorevoli riguardano il prezzo al litro, che i clienti trovano alto.",
               "facts": "Le risposte con il prezzo sbagliato riportano quello vecchio della pagina dei punti vendita."}
    WHAT = "Pubblicare su avenello.example una pagina che confronti la bevanda con Avoria per prezzo al litro, ingredienti e punti vendita"

    def setUp(self):
        super().setUp()
        self.adopt_audience("trade", 602, "Avenello · Chi lavora nel settore", 9201, OCT[0], rows())
        study = self.read("study.json")
        study["projects"][0]["name"] = "Avenello · Chi compra al supermercato"
        (self.study / "study.json").write_text(deck.json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.build(DATE)
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        patcher = mock.patch.object(deck, "_headlines", hundreds(deck._headlines))
        patcher.start()
        self.addCleanup(patcher.stop)

    def doc(self):
        doc = self.filled()
        doc["found"]["answers"] = dict(self.ANSWERS)
        doc["actions"][0]["what"] = self.WHAT
        doc["blocks"]["description"][0]["rows"] = "questions"
        return doc

    def test_the_texts_have_the_shape_measured(self):
        doc = self.doc()
        page = self.section(doc, "found")
        self.assertEqual(page.count('class="sum-name"'), 4)
        self.assertIn('<div class="sum-name">Chi compra al supermercato</div><div class="sum-fig">100 <small>su 132</small>', page)
        self.assertEqual(lines("<h1>{}</h1>", 36, doc["found"]["title"]), 1)
        for key, text in self.ANSWERS.items():
            with self.subTest(key):
                self.assertEqual(lines('<div class="summary several"><div class="sum-row"><div class="sum-group"></div>'
                                       '<div class="sum-figs"></div><p class="sum-a">{}</p></div></div>', 28.6, text), 2)
        self.assertEqual(lines('<p class="sum-action"><b>Prima azione suggerita:</b> {} <span>Tutte le azioni: slide 8</span></p>',
                               26, self.WHAT), 2)
        self.assertLessEqual(sum(deck.words(t) for t in (doc["found"]["title"], *self.ANSWERS.values(), self.WHAT)),
                             deck.SUMMARY_WORDS)

    def test_the_summary_fits_its_page(self):
        doc = self.doc()
        self.save_doc(doc)
        self.assertLessEqual(found_height(self, doc), fit.PAGE_HEIGHT)
        folder, study, period, _ = self.model_args(doc)
        self.assertEqual(deck._overflowing(folder, study, period, doc, deck.build_model(folder, study, period, doc)), [])


class DrawnOverTest(Rendered, unittest.TestCase):
    """What the code draws on the summary can run over its page whatever the writer cuts: `check` says so and asks
    nobody to shorten (M39 T16)."""

    def test_the_figures_running_over_by_themselves_are_reported(self):
        doc = self.filled()
        self.save_doc(doc)
        with mock.patch.object(fit, "PAGE_HEIGHT", found_height(self, {**doc, "found": {}, "actions": []}) - 40):
            found = self.problems(doc)
        self.assertIn("the figures the code draws on slide 3 run over the page by themselves: report it", found)
        self.assertNotIn("slide 3 runs over its page", found)

    def test_texts_the_writer_can_shorten_are_named_as_before(self):
        doc = self.filled()
        self.save_doc(doc)
        doc["found"]["title"] = " ".join(["Chi cerca una bevanda all'avena trova Avoria"] * 3)
        with mock.patch.object(fit, "PAGE_HEIGHT", found_height(self, doc) - 20):
            found = self.problems(doc)
        self.assertIn("slide 3 runs over its page by about 1 line of text: shorten the found title or answers", found)
        self.assertNotIn("the figures the code draws", found)


class SnapshotNameTest(Rendered, unittest.TestCase):
    """A project named as SNAPSHOT.md names a snapshot is shown by its project part (M39 T15)."""

    NAME = "Snapshot · Gruppo Avenello · Mercato · 2026-10-04"

    def test_a_snapshot_s_short_name_is_its_project(self):
        self.assertEqual(deck._short(self.NAME, "Avenello"), "Mercato")
        self.assertEqual(deck._short("Snapshot · Avenello · Con il marchio · 2026-10-04", "Avenello"), "Con il marchio")

    def test_any_other_name_reads_as_before(self):
        self.assertEqual(deck._short("Avenello · Mercato", "Avenello"), "Mercato")
        self.assertEqual(deck._short("Snapshot · Avenello · 2026-10-22", "Avenello"), "Snapshot · Avenello · 2026-10-22")
        self.assertEqual(deck._short("Snapshot · Gruppo Avenello · Mercato", "Avenello"), "Snapshot · Gruppo Avenello · Mercato")

    def test_the_deck_shows_the_project_part_alone(self):
        study = self.read("study.json")
        study["projects"][0]["name"] = self.NAME
        (self.study / "study.json").write_text(deck.json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        self.save_doc(self.filled())
        text = deck.page_of(self.study, DATE)[0]
        self.assertIn('<td class="class">Mercato</td>', text)
        for part in ("Snapshot", "Gruppo Avenello", "2026-10-04"):
            self.assertNotIn(part, text)


class LimitTest(Rendered, unittest.TestCase):

    def test_the_method_says_the_questions_about_the_subject_were_not_asked_about_competitors(self):
        doc = self.filled()
        m = deck.build_model(*self.model_args(doc))
        t = deck.DECK["it"]
        self.assertIn(t["limit_unasked"].format(subject="Avenello"), deck._method(doc, m, t))
        m["blocks"]["description"]["rows"] = []
        self.assertNotIn(t["limit_unasked"].format(subject="Avenello"), deck._method(doc, m, t))



class OrderTest(Rendered, unittest.TestCase):

    def page(self, doc=None):
        self.save_doc(doc or self.filled())
        return deck.page_of(self.study, DATE)[0]

    def test_the_suggested_actions_close_the_deck_before_the_appendix(self):
        kinds = re.findall(r'<section class="slide (\w+)', self.page())
        self.assertEqual(kinds, ["cover", "opening", "found", "reach", "description", "facts", "sources", "actions", "method",
                                 "questions"])

    def test_the_actions_slide_is_named_suggested_actions(self):
        self.assertIn('<div class="kicker">Azioni suggerite</div>', self.section(self.filled(), "actions"))

    def test_each_page_of_the_appendix_says_so(self):
        text = self.page()
        for kind in ("method", "questions"):
            with self.subTest(kind):
                at = text.index(f'<section class="slide {kind}')
                self.assertIn('<div class="kicker">Appendice</div>', text[at:text.index("</section>", at)])
        for kind in ("found", "reach", "sources", "actions"):
            at = text.index(f'<section class="slide {kind}')
            self.assertNotIn("Appendice", text[at:text.index("</section>", at)])

    def test_the_actions_point_to_their_evidence_and_the_summary_to_the_actions(self):
        text = self.page()
        actions = text[text.index('<section class="slide actions'):]
        self.assertIn('<td class="num">4</td>', actions[:actions.index("</section>")])
        self.assertIn("Tutte le azioni: slide 8", text_of(text[text.index('<section class="slide found'):]))

    def test_english_labels(self):
        study = self.read("study.json")
        study["report_language"] = "en"
        (self.study / "study.json").write_text(deck.json.dumps(study, ensure_ascii=False), encoding="utf-8")
        text = self.page()
        self.assertIn('<div class="kicker">Suggested actions</div>', text)
        self.assertIn('<div class="kicker">Appendix</div>', text)


class RepeatedTest(Rendered, unittest.TestCase):
    """The figures said again and again are those of the slide that decides whether the reader goes on: the summary."""

    def test_a_figure_repeated_on_the_summary_is_refused(self):
        doc = self.filled()
        doc["found"]["title"] = "Chi cerca una bevanda trova Avoria in 1 risposta su 2"
        doc["actions"][0]["what"] = "Pubblicare su avenello.example un confronto con Avoria, in 1 risposta su 2"
        with mock.patch.object(deck, "MAX_REPEATS", 1):
            self.assertIn("1 of 2 appears 2 times on the summary", self.problems(doc))

    def test_the_actions_slide_at_the_end_is_not_counted(self):
        doc = self.filled()
        doc["found"]["title"] = "Chi cerca una bevanda trova Avoria in 1 risposta su 2"
        doc["actions_title"] = "La prima cosa da fare riguarda Avoria, in 1 risposta su 2"
        with mock.patch.object(deck, "MAX_REPEATS", 1):
            self.assertNotIn("appears 2 times", self.problems(doc))


if __name__ == "__main__":
    unittest.main()
