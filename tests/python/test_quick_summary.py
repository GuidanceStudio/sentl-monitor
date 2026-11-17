"""The quick deck opens with a summary and closes on suggested actions (DEVPLAN M38): slide 2 gives each project its
figure and one sentence; the slide before the sites gives one to three actions on the subject's own pages or checks of
pages the answers cite, each resting on a count a row of the deck draws."""

import json
import re
import unittest
from unittest import mock

import fixtures  # noqa: F401  (puts the skill's scripts on the path)
from sentlmon import deck, quick
from test_insights_period import OCT, rows
from test_quick import DATE, TODO, QuickCase


def words(n):
    return " ".join(["parola"] * n)


def text_of(html):
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


class SkeletonTest(QuickCase, unittest.TestCase):

    def test_the_skeleton_holds_the_summary_and_the_actions_to_fill(self):
        doc = self.skeleton()
        self.assertEqual(doc["schema"], "sentl-monitor/quick@2")
        self.assertEqual(doc["summary"], {"title": TODO, "projects": {"market": TODO}})
        self.assertEqual(doc["actions"], [{"what": TODO, "why": TODO}])
        self.assertEqual(list(doc), ["schema", "date", "summary", "slides", "actions"])

    def test_a_deck_of_the_first_schema_gets_the_summary_and_the_actions_and_keeps_its_slides(self):
        doc = self.filled()
        old = {"schema": "sentl-monitor/quick@1", "date": DATE, "slides": doc["slides"]}
        self.save_doc(old)
        self.assertIn("schema is not sentl-monitor/quick@2: run deck --quick again", self.problems(old))
        self.save_doc(old)
        said = self.cli("deck", "--quick", "--study", self.study, "--date", DATE, check=0).stdout
        new = self.skeleton()
        self.assertEqual((new["schema"], new["slides"]), ("sentl-monitor/quick@2", doc["slides"]))
        self.assertEqual(new["summary"], {"title": TODO, "projects": {"market": TODO}})
        self.assertEqual(new["actions"], [{"what": TODO, "why": TODO}])
        self.assertIn("4 texts left", said)

    def test_deck_quick_lists_the_summary_and_the_actions(self):
        said = self.made.stdout
        self.assertIn("2 summary", said)
        self.assertIn("4 suggested actions", said)
        self.assertIn("5 sites and method", said)
        self.assertIn("5 slides", said)

    def test_the_figures_file_gives_each_project_its_figure(self):
        figures = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        quick_part = figures.split("## Quick deck")[1]
        self.assertIn("### Slide 2: summary", quick_part)
        self.assertRegex(quick_part, r"- market \(Mercato\): Avenello named in 0 su 2; favourable \d+ su \d+")
        self.assertIn("### Slide 4: suggested actions", quick_part)


class SummaryTest(QuickCase, unittest.TestCase):

    def page(self, doc=None):
        self.save_doc(doc or self.filled())
        return quick.page_of(self.study, DATE)[0]

    def summary(self, doc=None):
        return self.page(doc).split("<section ")[2]

    def test_slide_two_is_the_summary(self):
        summary = self.summary()
        self.assertTrue(summary.startswith('class="slide found"'))
        self.assertIn('<div class="kicker">In sintesi</div>', summary)
        self.assertIn(f"<h1>{self.filled()['summary']['title']}</h1>", summary)

    def test_each_project_has_its_name_its_figures_and_its_sentence(self):
        summary = self.summary()
        self.assertIn('<div class="sum-group">Mercato</div>', summary)
        self.assertIn("0 <small>su 2</small>", summary)
        self.assertIn("risposte che nominano Avenello", summary)
        self.assertIn("risposte favorevoli a Avenello", summary)
        self.assertIn(self.filled()["summary"]["projects"]["market"], summary)

    def test_the_project_figure_adds_up_its_rows(self):
        reach = {"named": 1, "given": 4, "foils": []}
        rated = {"judged": 6, "bands": {"4-5": 4, "3": 1, "1-2": 1}}
        project = {"rows": [{"reach": reach, "description": None}, {"reach": {**reach, "named": 2}, "description": rated},
                            {"reach": None, "description": {**rated, "bands": {"4-5": 1, "3": 2, "1-2": 3}}}]}
        self.assertEqual(quick._headlines(project), [("reach", 3, 8), ("description", 5, 12)])

    def test_a_sentence_restating_the_project_figure_is_refused(self):
        doc = self.filled()
        doc["summary"]["projects"]["market"] = "Avenello compare in 0 risposte su 2; sul lavoro le risposte sono favorevoli."
        self.assertIn("slide 2 summary of market says 0 of 2, which the summary draws beside it: say what lies behind it",
                      self.problems(doc))

    def test_a_sentence_repeating_the_title_of_the_project_s_slide_is_refused(self):
        doc = self.filled()
        doc["summary"]["projects"]["market"] = doc["slides"][0]["title"] + "."
        self.assertIn("slide 2 summary of market repeats the title of slide 3: say what the project's slides add up to",
                      self.problems(doc))

    def test_the_title_and_the_sentences_have_the_full_deck_s_ceilings(self):
        doc = self.filled()
        doc["summary"]["title"] = words(21) + "."
        doc["summary"]["projects"]["market"] = words(26) + "."
        found = self.problems(doc)
        self.assertIn("summary title holds 21 words, at most 20", found)
        self.assertIn("summary of market holds 26 words, at most 25", found)

    def test_the_summary_slide_has_its_ceiling_in_words(self):
        doc = self.filled()
        with mock.patch.object(deck, "SUMMARY_WORDS", 30):
            self.assertRegex(self.problems(doc), r"slide 2 holds \d+ words of the writer's texts, at most 30 on the summary: "
                                                 r"shorten summary of market \(\d+ words\), summary title \(\d+ words\)")

    def test_a_figure_the_period_does_not_hold_is_refused(self):
        doc = self.filled()
        doc["summary"]["projects"]["market"] = "Sul lavoro 3 risposte su 7 sono favorevoli."
        self.assertIn("count 3 su 7 is not in the period's figures", self.problems(doc))

    def test_english_labels(self):
        study = self.read("study.json")
        study["report_language"] = "en"
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        summary = self.summary()
        self.assertIn("In short", summary)
        self.assertIn("answers naming Avenello", summary)


class SummaryRoomTest(QuickCase, unittest.TestCase):
    """The summary's ceiling counts the writer's texts only (M39 T15): beside the six figures of three projects, the
    writer has the full deck's room."""

    def setUp(self):
        super().setUp()
        self.adopt_audience("trade", 602, "Avenello · Chi lavora nel settore", 9201, OCT[0], rows())
        self.adopt_audience("online", 603, "Avenello · Chi compra la spesa online", 9301, OCT[0], rows())
        self.build(DATE)
        self.path.unlink()
        self.cli("deck", "--quick", "--study", self.study, "--date", DATE, check=0)

    def at(self, n):
        """The deck with the summary's texts, its title and the three projects' sentences, holding n words."""
        doc = self.filled()
        first = {r["dimension"]: r for r in doc["slides"][0]["rows"]}
        for slide in doc["slides"][1:]:
            slide.update(question=doc["slides"][0]["question"], title=doc["slides"][0]["title"])
            for row in slide["rows"]:
                # Each project's topic keys are the market's with a number: prezzo-2 is the market's prezzo.
                same = first[row["dimension"].split("-")[0]]
                row.update(says=same["says"], excerpt=same["excerpt"])
        title, *sentences = (n // 4 + (i < n % 4) for i in range(4))
        doc["summary"] = {"title": words(title), "projects": {s["project"]: words(k) for s, k in zip(doc["slides"], sentences)}}
        return doc

    def test_the_writer_has_the_full_deck_s_room_whatever_the_figures_beside_them(self):
        doc = self.at(deck.SUMMARY_WORDS)
        self.save_doc(doc)
        summary = quick.page_of(self.study, DATE)[0].split("<section ")[2]
        self.assertEqual(summary.count('class="sum-fig"'), 6)
        self.assertEqual(self.problems(doc), "")

    def test_one_word_over_is_refused(self):
        self.assertIn(f"slide 2 holds {deck.SUMMARY_WORDS + 1} words of the writer's texts, at most {deck.SUMMARY_WORDS} "
                      "on the summary: shorten", self.problems(self.at(deck.SUMMARY_WORDS + 1)))


class OneProjectSummaryTest(QuickCase, unittest.TestCase):
    """A quick summary of one project is drawn as before M39 T17, its captions naming the subject."""

    def test_it_is_drawn_as_before(self):
        doc = self.filled()
        self.save_doc(doc)
        summary = quick.page_of(self.study, DATE)[0].split("<section ")[2]
        self.assertEqual(
            summary[:summary.index("<footer")],
            f'class="slide found"><div class="kicker">In sintesi</div><h1>{doc["summary"]["title"]}</h1>'
            '<div class="summary one"><div class="sum-row"><div class="sum-group">Mercato</div>'
            '<div class="sum-figs many"><div class="sum-fig">0 <small>su 2</small></div>'
            '<div class="sum-cap">risposte che nominano Avenello</div><div class="sum-fig">3 <small>su 4</small></div>'
            '<div class="sum-cap">risposte favorevoli a Avenello</div></div>'
            f'<p class="sum-a">{doc["summary"]["projects"]["market"]}</p></div></div>')


class SeveralProjectsSummaryTest(QuickCase, unittest.TestCase):
    """On a quick summary of several projects, each named after a part of the subject, a caption under a project's
    figure leaves out the subject where it read as the whole subject's figure; presence still counts the answers naming
    it (M39 T17, as T16 on the full deck's summary)."""

    REACH = {"named": 1, "given": 4, "foils": []}
    RATED = {"judged": 6, "bands": {"4-5": 4, "3": 1, "1-2": 1}}

    def plan(self, *names):
        return [{"key": f"p{n}", "name": name, "rows": [{"reach": self.REACH, "description": self.RATED}]}
                for n, name in enumerate(names)]

    def captions(self, plan, lang="it", fidelity=False):
        page = quick._summary_html({}, {"subject": "Avenello", "fidelity": fidelity}, deck.DECK[lang], plan)
        return re.findall(r'<div class="sum-cap">([^<]*)</div>', page)

    def test_the_captions_of_two_projects_leave_out_the_subject_except_on_presence(self):
        self.adopt_audience("trade", 602, "Avenello · Chi lavora nel settore", 9201, OCT[0], rows())
        self.build(DATE)
        self.path.unlink()
        self.cli("deck", "--quick", "--study", self.study, "--date", DATE, check=0)
        self.save_doc(self.filled())
        summary = quick.page_of(self.study, DATE)[0].split("<section ")[2]
        self.assertEqual(summary.count('<div class="sum-group">'), 2)
        self.assertEqual(summary.count('<div class="sum-cap">risposte che nominano Avenello</div>'), 2)
        self.assertEqual(summary.count('<div class="sum-cap">risposte favorevoli</div>'), 2)
        self.assertNotIn("favorevoli a Avenello", summary)

    def test_only_presence_names_the_subject_in_either_language_and_score(self):
        for lang in ("it", "en"):
            for fidelity in (False, True):
                with self.subTest(lang=lang, fidelity=fidelity):
                    reach, description = self.captions(self.plan("Mercato", "Chi lavora nel settore"), lang, fidelity)[:2]
                    self.assertIn("Avenello", reach)
                    self.assertNotIn("Avenello", description)
        self.assertEqual(self.captions(self.plan("Mercato", "Chi lavora nel settore"), "en")[:2],
                         ["answers naming Avenello", "favourable answers"])

    def test_the_facts_caption_names_no_subject_either(self):
        for lang in ("it", "en"):
            self.assertNotIn("{subject}", deck.DECK[lang]["summary_caption_several"]["facts"])

    def test_one_project_keeps_the_subject_in_its_captions(self):
        self.assertEqual(self.captions(self.plan("Mercato")), ["risposte che nominano Avenello", "risposte favorevoli a Avenello"])


class SnapshotNameTest(QuickCase, unittest.TestCase):
    """A project named as SNAPSHOT.md names a snapshot is shown by its project part (M39 T15)."""

    def test_the_quick_deck_shows_the_project_part_alone(self):
        study = self.read("study.json")
        study["projects"][0]["name"] = "Snapshot · Gruppo Avenello · Mercato · 2026-10-04"
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.cli("deck", "--quick", "--study", self.study, "--date", DATE, check=0)
        self.save_doc(self.filled())
        text = quick.page_of(self.study, DATE)[0]
        self.assertIn('<div class="sum-group">Mercato</div>', text)
        for part in ("Snapshot", "Gruppo Avenello", "2026-10-04"):
            self.assertNotIn(part, text)


class ActionsTest(QuickCase, unittest.TestCase):

    def with_action(self, what=None, why=None):
        doc = self.filled()
        action = doc["actions"][0]
        action.update({k: v for k, v in (("what", what), ("why", why)) if v is not None})
        return doc

    def test_the_actions_stand_before_the_sites_and_method(self):
        self.save_doc(self.filled())
        text, count = quick.page_of(self.study, DATE)
        kinds = re.findall(r'<section class="slide ([\w-]+)', text)
        self.assertEqual((count, kinds), (5, ["cover", "found", "q-slide", "actions", "q-sites"]))
        actions = text_of(text.split("<section ")[4])
        self.assertIn("Azioni suggerite", actions)
        self.assertIn("Sulle pagine di Avenello " + self.filled()["actions"][0]["what"], actions)
        self.assertIn(self.filled()["actions"][0]["why"], actions)
        self.assertIn("4 / 5", actions)

    def test_a_check_of_a_page_the_answers_cite_is_marked_as_such_and_passes(self):
        doc = self.with_action(what="Verificare che prezzi.example riporti il prezzo di oggi di Avenello")
        self.assertEqual(self.problems(doc), "")
        self.assertIn("Da verificare Verificare che prezzi.example", text_of(quick.page_of(self.study, DATE)[0]))

    def test_one_to_three_actions(self):
        doc = self.filled()
        doc["actions"] = []
        self.assertIn("the quick deck has no action", self.problems(doc))
        doc["actions"] = self.filled()["actions"] * 4
        self.assertIn("4 actions: a quick deck holds at most 3", self.problems(doc))

    def test_what_and_why_hold_at_most_20_words(self):
        doc = self.with_action(what=words(19) + " su avenello.example", why="Avoria compare in 1 risposta su 2 " + words(14))
        found = self.problems(doc)
        self.assertIn("action 1 what holds 21 words, at most 20", found)
        self.assertIn("action 1 why holds 21 words, at most 20", found)

    def test_a_request_to_a_third_party_is_refused(self):
        doc = self.with_action(what="Chiedere a prezzi.example di aggiornare il prezzo di Avenello")
        self.assertIn("action 1 asks a third party for a change", self.problems(doc))

    def test_work_on_a_page_the_subject_does_not_own_is_refused(self):
        doc = self.with_action(what="Aggiornare il prezzo di Avenello su prezzi.example")
        self.assertIn("action 1 works on prezzi.example, a page Avenello does not own", self.problems(doc))

    def test_a_check_of_a_page_no_answer_cites_is_refused(self):
        doc = self.with_action(what="Verificare che altrove.example riporti il prezzo di oggi di Avenello")
        self.assertIn("action 1 checks altrove.example, which no answer cites", self.problems(doc))

    def test_an_action_naming_no_site_is_refused(self):
        doc = self.with_action(what="Pubblicare una pagina che confronta Avenello con le altre bevande all'avena")
        self.assertIn("action 1 names no site", self.problems(doc))

    def test_a_competitor_s_site_is_refused(self):
        doc = self.with_action(what="Verificare che avoria.example confronti Avoria con Avenello")
        self.assertIn("a competitor's site", self.problems(doc))

    def test_a_why_without_a_count_a_row_draws_is_refused(self):
        doc = self.with_action(why="Chi chiede la bevanda migliore si sente indicare Avoria")
        self.assertIn("action 1 why gives no count a row of the deck draws", self.problems(doc))

    def test_a_why_on_a_row_s_count_passes(self):
        self.assertEqual(self.problems(self.with_action(why="Avenello compare in 0 risposte su 2 sulla bevanda migliore")), "")

    def test_english_labels(self):
        study = self.read("study.json")
        study["report_language"] = "en"
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.save_doc(self.filled())
        text = text_of(quick.page_of(self.study, DATE)[0])
        self.assertIn("Suggested actions", text)
        self.assertIn("On Avenello's own pages", text)


if __name__ == "__main__":
    unittest.main()
