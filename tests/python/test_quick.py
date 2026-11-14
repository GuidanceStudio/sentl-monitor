"""The quick deck (DEVPLAN M33): one slide per project of the period, one row per topic with the code's figure, a sentence
and an excerpt the writer fills, and a last slide with the sites cited most and how the answers were read."""

import json
import re
import unittest
import zipfile
from unittest import mock

from fixtures import CHOICE_Q, PRICE_Q, WORK_Q
from sentlmon import deck, pack, quick
from sentlmon import pdf as report_pdf
from test_deck import fake_pdf
from test_insights_period import CURRENT, OCT, InsightCase, rows

DATE = "2026-10-31"
NOV = "2026-11-30"
LATER = "2026-11-02T06:00:00Z"
TODO = "[[...]]"


def excerpt(text, question, assistant):
    return {"text": text, "question": question, "assistant": assistant}


class QuickCase(InsightCase):
    """The market project's period of October, with its quick deck's skeleton written."""

    def setUp(self):
        super().setUp()
        self.ingest_market(9101, OCT[0], rows())
        self.build(DATE)
        self.made = self.cli("deck", "--quick", "--study", self.study, "--date", DATE, check=0)
        self.path = self.study / "reports" / f"{DATE}.quick.json"

    def skeleton(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def filled(self):
        doc = self.skeleton()
        slide = doc["slides"][0]
        slide.update(question="Cosa sentono dagli assistenti AI i consumatori di bevande all'avena?",
                     title="Chi chiede una bevanda all'avena senza fare nomi trova Avoria e non Avenello")
        texts = {
            "prezzo": ("Una risposta riporta il prezzo di oggi, l'altra un prezzo vecchio.",
                       excerpt(CURRENT[0], PRICE_Q, "Orbit Reason")),
            "scelta": ("Avoria compare in 1 risposta su 2, Avenello in nessuna delle 2.",
                       excerpt("La migliore è Avoria.", CHOICE_Q, "Acme Chat")),
            "lavoro": ("Entrambe le risposte descrivono Avenello come un buon posto dove lavorare.",
                       excerpt("Si lavora bene da Avenello.", WORK_Q, "Orbit Reason")),
        }
        for row in slide["rows"]:
            row["says"], row["excerpt"] = texts[row["dimension"]]
        return doc

    def row(self, doc, dimension):
        return next(r for r in doc["slides"][0]["rows"] if r["dimension"] == dimension)

    def save_doc(self, doc):
        self.path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    def problems(self, doc):
        self.save_doc(doc)
        return "\n".join(quick.check(self.study, self.path, DATE))

    def passed(self):
        self.save_doc(self.filled())
        return self.cli("check", "--study", self.study, self.path, check=0)


class SkeletonTest(QuickCase, unittest.TestCase):

    def test_one_slide_per_project_and_one_row_per_topic_in_the_study_s_order(self):
        doc = self.skeleton()
        self.assertEqual((doc["schema"], doc["date"]), ("sentl-monitor/quick@1", DATE))
        self.assertEqual([(s["project"], [r["dimension"] for r in s["rows"]]) for s in doc["slides"]],
                         [("market", ["prezzo", "scelta", "lavoro"])])
        slide = doc["slides"][0]
        self.assertEqual((slide["question"], slide["title"]), (TODO, TODO))
        self.assertEqual(slide["rows"][0], {"dimension": "prezzo", "says": TODO,
                                            "excerpt": {"text": TODO, "question": TODO, "assistant": TODO}})

    def test_deck_quick_writes_the_figures_and_no_full_deck(self):
        self.assertFalse((self.study / "reports" / f"{DATE}.deck.json").exists())
        figures = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertIn("## Blocks", figures)
        self.assertIn("## Quick deck", figures)
        self.assertIn(f"«{CHOICE_Q}»", figures.split("## Quick deck")[1])
        self.assertNotIn("~~~~", figures)

    def test_deck_quick_prints_the_slides_the_rows_and_the_texts_left(self):
        said = self.made.stdout
        self.assertIn("3 slides", said)
        self.assertIn("3 rows", said)
        self.assertIn("14 texts left", said)
        self.assertIn(f"{DATE}.quick.json", said)

    def test_a_second_run_keeps_what_is_written(self):
        doc = self.filled()
        self.save_doc(doc)
        self.cli("deck", "--quick", "--study", self.study, "--date", DATE, check=0)
        self.assertEqual(self.skeleton(), doc)

    def test_a_project_with_more_than_six_topics_takes_a_second_slide(self):
        layout = [{"key": "market", "rows": [{"key": f"d{n}"} for n in range(7)]}]
        doc = quick._skeleton(DATE, layout)
        self.assertEqual([(s["project"], [r["dimension"] for r in s["rows"]]) for s in doc["slides"]],
                         [("market", ["d0", "d1", "d2", "d3"]), ("market", ["d4", "d5", "d6"])])
        self.assertEqual([len(part) for part in quick._split(list(range(13)))], [5, 4, 4])
        self.assertEqual([len(part) for part in quick._split(list(range(6)))], [6])


class PassTest(QuickCase, unittest.TestCase):

    def test_a_filled_deck_passes_and_records_its_period(self):
        said = self.passed().stdout
        self.assertIn("check passed", said)
        entry = self.read("history/reports.json")[-1]
        self.assertEqual((entry["date"], entry["status"], entry["deck"], entry["runs"]),
                         (DATE, "final", f"reports/{DATE}.quick.json", self.period_file(DATE)["runs"]))
        last = self.read("history/last-report.json")
        self.assertEqual(last["outcome"], "written")
        self.assertIn(DATE, last["detail"])

    def test_the_next_period_starts_after_the_runs_of_the_quick_deck(self):
        self.passed()
        self.ingest_market(9102, LATER, rows())
        self.build(NOV)
        later = self.period_file(NOV)
        self.assertEqual((later["runs"], later["comparison"]["previous"]), ({"market": [9102]}, DATE))

    def test_an_unattended_deck_that_passes_records_written(self):
        self.save_doc(self.filled())
        self.cli("check", "--study", self.study, self.path, "--unattended", check=0)
        self.assertEqual(self.read("history/last-report.json")["outcome"], "written")

    def test_an_unattended_deck_that_fails_is_recorded_as_a_draft(self):
        said = self.cli("check", "--study", self.study, self.path, "--unattended", check=1).stdout
        self.assertIn("recorded as a draft", said)
        entry = self.read("history/reports.json")[-1]
        self.assertEqual((entry["date"], entry["status"], "deck" in entry), (DATE, "draft", False))
        self.assertEqual(self.read("history/last-report.json")["outcome"], "draft")

    def test_a_failing_deck_with_the_operator_present_records_nothing(self):
        self.cli("check", "--study", self.study, self.path, check=1)
        self.assertFalse((self.study / "history" / "reports.json").exists())


class RefusalTest(QuickCase, unittest.TestCase):

    def test_a_marker_left_is_refused(self):
        self.assertIn("left to write", self.problems(self.skeleton()))

    def test_a_slide_of_another_project_is_refused(self):
        doc = self.filled()
        doc["slides"][0]["project"] = "elsewhere"
        self.assertIn("elsewhere", self.problems(doc))

    def test_a_row_left_out_is_refused(self):
        doc = self.filled()
        doc["slides"][0]["rows"] = [r for r in doc["slides"][0]["rows"] if r["dimension"] != "scelta"]
        found = self.problems(doc)
        self.assertIn("slide 2", found)
        self.assertIn("prezzo, scelta, lavoro", found)

    def test_a_slide_the_period_does_not_give_is_refused(self):
        doc = self.filled()
        doc["slides"].append(doc["slides"][0])
        self.assertIn("slide 3", self.problems(doc))

    def test_texts_over_their_length_are_refused(self):
        doc = self.filled()
        doc["slides"][0]["question"] = "Chi " + "a" * 117
        doc["slides"][0]["title"] = "Chi " + "a" * 157
        self.row(doc, "lavoro")["says"] = "Chi " + "a" * 167
        found = self.problems(doc)
        self.assertIn("question holds 121 characters, at most 120", found)
        self.assertIn("title holds 161 characters, at most 160", found)
        self.assertIn("says holds 171 characters, at most 170", found)

    def test_an_excerpt_over_forty_words_is_refused(self):
        doc = self.filled()
        self.row(doc, "lavoro")["excerpt"]["text"] = ("parola " * 41).strip()
        self.assertIn("over 40 words", self.problems(doc))

    def test_an_excerpt_of_a_question_of_another_topic_is_refused(self):
        doc = self.filled()
        self.row(doc, "prezzo")["excerpt"] = excerpt("Si lavora bene da Avenello.", WORK_Q, "Orbit Reason")
        self.assertIn("is not a question of the topic Prezzo", self.problems(doc))

    def test_an_assistant_not_of_the_period_is_refused(self):
        doc = self.filled()
        self.row(doc, "lavoro")["excerpt"]["assistant"] = "Zenith Answer"
        self.assertIn("is not an assistant of the period", self.problems(doc))

    def test_an_excerpt_not_in_the_answers_is_refused(self):
        doc = self.filled()
        self.row(doc, "prezzo")["excerpt"]["text"] = "Avenello costa 3,00 € al litro."
        self.assertIn("not found verbatim in the answers of Orbit Reason", self.problems(doc))

    def test_an_excerpt_of_another_assistant_s_answer_is_refused(self):
        doc = self.filled()
        self.row(doc, "prezzo")["excerpt"]["assistant"] = "Acme Chat"
        self.assertIn("not found verbatim in the answers of Acme Chat", self.problems(doc))

    def test_an_excerpt_cut_inside_a_sentence_is_refused_and_a_marked_cut_passes(self):
        doc = self.filled()
        self.row(doc, "prezzo")["excerpt"]["text"] = "costa 2,10 € al litro."
        self.assertIn("starts inside a sentence", self.problems(doc))
        self.row(doc, "prezzo")["excerpt"]["text"] = "[…] costa 2,10 € al litro."
        self.assertNotIn("inside a sentence", self.problems(doc))

    def test_a_figure_the_period_does_not_hold_is_refused(self):
        doc = self.filled()
        self.row(doc, "lavoro")["says"] = "Avenello compare in 3 risposte su 7."
        self.assertIn("count 3 su 7 is not in the period's figures", self.problems(doc))

    def test_a_count_beside_a_competitor_that_is_not_its_count_is_refused(self):
        doc = self.filled()
        self.row(doc, "scelta")["says"] = "Avoria compare in 2 risposte su 2."
        self.assertIn("beside Avoria", self.problems(doc))

    def test_none_the_figures_do_not_bear_out_is_refused(self):
        doc = self.filled()
        self.row(doc, "lavoro")["says"] = "Nessuna risposta è sfavorevole ad Avenello."
        self.assertIn("all or nothing", self.problems(doc))

    def test_a_word_about_the_machine_is_refused(self):
        doc = self.filled()
        doc["slides"][0]["title"] = "Il deck mostra cosa rispondono gli assistenti su Avenello"
        self.assertIn("how the deck was built", self.problems(doc))

    def test_a_word_of_the_study_is_refused(self):
        doc = self.filled()
        self.row(doc, "lavoro")["says"] = "Il punteggio delle risposte è alto."
        self.assertIn("a word of the study", self.problems(doc))

    def test_the_first_person_is_refused(self):
        doc = self.filled()
        self.row(doc, "lavoro")["says"] = "Gli assistenti ci consigliano come datore di lavoro."
        self.assertIn("name the subject", self.problems(doc))

    def test_a_model_id_is_refused(self):
        doc = self.filled()
        self.row(doc, "lavoro")["says"] = "Lo dice acme/chat-large."
        self.assertIn("model id acme/chat-large appears", self.problems(doc))

    def test_a_slide_taller_than_its_page_is_refused(self):
        doc = self.filled()
        with mock.patch.object(quick.fit, "heights", lambda page, css: [900.0] * page.count("<section")):
            found = self.problems(doc)
        self.assertIn("slide 2 runs over its page", found)
        self.assertIn("slide 2", found)

    def test_the_filled_deck_fits_its_pages(self):
        self.assertEqual(self.problems(self.filled()), "")


class PageTest(QuickCase, unittest.TestCase):

    def page(self):
        self.save_doc(self.filled())
        return quick.page_of(self.study, DATE)

    def test_the_names_counted_are_listed_with_one_or(self):
        path = self.study / "study.json"
        study = json.loads(path.read_text(encoding="utf-8"))
        study["subject"]["aliases"] = ["Avenello Drink", "Aven"]
        path.write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        text, _ = self.page()
        self.assertIn("Avenello, Avenello Drink o Aven", text)

    def test_one_section_per_slide_the_cover_the_projects_and_the_sites(self):
        text, count = self.page()
        self.assertEqual(count, 3)
        self.assertEqual(text.count('<section class="slide'), 3)
        self.assertIn("3 / 3", text)
        self.assertNotIn("<script", text)

    def test_the_cover_says_it_is_a_summary_of_the_period(self):
        cover = self.page()[0].split("</section>")[0]
        self.assertIn("Sintesi", cover)
        self.assertIn("Avenello", cover)
        self.assertRegex(re.sub(r"<[^>]+>", "", cover), r"\d+ domande")

    def test_each_row_draws_its_figure(self):
        text = " ".join(re.sub(r"<[^>]+>", " ", self.page()[0]).split())
        self.assertIn("0 su 2", text)
        self.assertIn("Avoria 1", text)
        self.assertIn("1 su 2", text)
        self.assertIn("2 su 2", text)
        self.assertIn("Si lavora bene da Avenello.", text)

    def test_a_topic_with_questions_of_both_kinds_draws_both_figures(self):
        from sentlmon.i18n import DECK, QUICK
        row = {"reach": {"named": 3, "given": 8, "foils": [("Avoria", 5)]},
               "description": {"judged": 6, "bands": {"4-5": 4, "3": 1, "1-2": 1}}}
        drawn = quick._figures_html(row, {"subject": "Avenello", "fidelity": False}, DECK["it"], QUICK["it"])
        self.assertIn('class="meter"', drawn)
        self.assertIn('class="bar"', drawn)
        self.assertIn("Avoria 5", drawn)
        self.assertIn("neutre 1", drawn)

    def test_the_last_slide_lists_the_sites_cited_most_with_the_subject_s_own_marked(self):
        last = self.page()[0].split('<section class="slide')[-1]
        self.assertIn("avoria.example", last)
        self.assertIn("prezzi.example", last)
        self.assertRegex(last, r"avenello\.example.{0,80}sito di Avenello")
        self.assertIn("Acme Chat", last)
        self.assertIn("favorevole 4 o 5", last)
        self.assertNotRegex(last.lower(), r"giudic|judge")

    def test_english_labels(self):
        study = self.read("study.json")
        study["report_language"] = "en"
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        text = self.page()[0]
        self.assertIn("Summary", text)
        self.assertIn("naming Avenello", text)


class PrintTest(QuickCase, unittest.TestCase):

    def test_pdf_quick_writes_the_page_the_pdf_and_the_copy_to_send(self):
        self.passed()
        with mock.patch.object(report_pdf, "print_pdf", fake_pdf(3)):
            said = self.cli("pdf", "--quick", "--study", self.study, "--date", DATE, check=0).stdout
        reports = self.study / "reports"
        self.assertTrue((reports / f"{DATE}.quick.html").exists())
        self.assertTrue((reports / f"{DATE}.quick.pdf").exists())
        self.assertFalse((reports / f"{DATE}.deck.html").exists())
        shared = [p.name for p in (reports / "share").glob("*.pdf")]
        self.assertEqual(shared, [f"Avenello + Sentl.ai - sintesi ({OCT[0][:10]}).pdf"])
        self.assertIn(shared[0], said)

    def test_pages_that_are_not_the_slides_are_refused(self):
        self.passed()
        with self.assertRaisesRegex(quick.Refused, "4 pages for 3 slides"):
            quick.render(self.study, DATE, printer=fake_pdf(4))

    def test_a_deck_failing_check_is_not_printed(self):
        with mock.patch.object(report_pdf, "print_pdf", fake_pdf(3)):
            proc = self.cli("pdf", "--quick", "--study", self.study, "--date", DATE, check=2)
        self.assertIn("check", proc.stderr)
        self.assertFalse((self.study / "reports" / f"{DATE}.quick.pdf").exists())


class LaterDeckTest(QuickCase, unittest.TestCase):
    """A quick deck has no actions: a full deck after it has no earlier edition to compare them with."""

    def test_a_later_full_deck_has_no_earlier_edition_from_a_quick_one(self):
        self.passed()
        # A full deck's text on file for the same date, written but never the one check recorded, changes nothing.
        full = self.study / "reports" / f"{DATE}.deck.json"
        full.write_text(json.dumps({"schema": deck.SCHEMA, "date": DATE, "actions": []}), encoding="utf-8")
        self.ingest_market(9102, LATER, rows())
        self.build(NOV)
        folder = deck.load(self.study, NOV)[0]
        self.assertIsNone(deck._earlier(folder, NOV))
        self.cli("deck", "--study", self.study, "--date", NOV, check=0)
        self.assertNotIn("earlier", self.read(f"reports/{NOV}.deck.json"))

    def test_a_quick_deck_leaves_a_full_deck_of_its_date_as_the_record(self):
        folder, _, _, period, _ = deck.load(self.study, DATE)
        folder.record_period(DATE, period, deck=f"reports/{DATE}.deck.json")
        self.passed()
        entry = next(e for e in folder.reports() if e["date"] == DATE)
        self.assertEqual(entry["deck"], f"reports/{DATE}.deck.json")
        self.assertEqual(entry["status"], "final")

    def test_a_full_deck_recorded_before_a_quick_one_is_still_an_earlier_edition(self):
        entry = {"date": DATE, "status": "final", "deck": f"reports/{DATE}.deck.json"}
        self.assertTrue(deck._full_deck(entry))
        self.assertFalse(deck._full_deck({**entry, "deck": f"reports/{DATE}.quick.json"}))
        self.assertTrue(deck._full_deck({"date": DATE, "status": "final", "file": f"reports/{DATE}.deck.json"}))


class PackTest(QuickCase, unittest.TestCase):

    def test_pack_carries_the_quick_deck_the_entry_names_and_unpack_takes_it(self):
        self.passed()
        folder = deck.load(self.study, DATE)[0]
        held = pack.select(folder, False)
        self.assertIn(f"reports/{DATE}.quick.json", held)
        self.assertNotIn(f"reports/{DATE}.deck.json", held)
        out = self.study.parent / "carried.zip"
        self.cli("pack", "--study", self.study, "--out", out, check=0)
        with zipfile.ZipFile(out) as zf:
            self.assertIn(f"reports/{DATE}.quick.json", zf.namelist())
        restored = self.study.parent / "restored"
        self.cli("unpack", "--study", restored, out, check=0)
        self.assertEqual((restored / "reports" / f"{DATE}.quick.json").read_bytes(), self.path.read_bytes())

    def test_a_draft_quick_deck_travels_with_its_material(self):
        self.cli("check", "--study", self.study, self.path, "--unattended", check=1)
        held = pack.select(deck.load(self.study, DATE)[0], False)
        self.assertIn(f"reports/{DATE}.quick.json", held)
        self.assertIn(f"history/material/{DATE}.md", held)


if __name__ == "__main__":
    unittest.main()
