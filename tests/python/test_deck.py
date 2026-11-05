"""The deck route: the material it needs, its blocks, its check and its pages."""

import json
import re
import shutil
import unittest

from fixtures import CHOICE_Q, GEM, GPT, PRICE_Q
from sentlmon import deck
from test_insights_period import CURRENT, OCT, OUTDATED, InsightCase, rows

DATE = "2026-10-31"
LONG = "Avenello costa 2,10 € al litro, mentre Avoria è la scelta più lineare se vuoi un prezzo semplice. Il resto dipende."


def fake_pdf(pages):
    """A PDF engine writing `pages` page objects, for a test with no browser."""
    def write(target, pdf, engines):
        pdf.write_bytes(b"%PDF-1.4\n" + b"<< /Type /Page >>\n" * pages)
        return "fake", []
    return write


class DeckCase(InsightCase):

    def setUp(self):
        super().setUp()
        self.ingest_market(9101, OCT[0], rows())
        self.build(DATE)
        self.made = self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        self.path = self.study / "reports" / f"{DATE}.deck.json"

    def filled(self, **changes):
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        slide = {"title": "Il blocco dice una cosa precisa", "read": "Una frase sul blocco.", "excerpts": [], "action": 1}
        doc.update({
            "found": {"title": "Avenello non è nominata in 2 risposte su 2", "points": ["Una risposta su due riporta il prezzo."]},
            "actions_title": "La prima azione è pubblicare una pagina di confronto",
            "actions": [{"class": "not_named", "what": "Pubblicare una pagina di confronto su avenello.example",
                         "rests_on": "0 risposte su 2 nominano Avenello", "read_next": "Risposte che nominano Avenello: 0 su 2",
                         "block": "reach"}],
            "blocks": {"reach": [dict(slide)], "description": [{**slide, "action": None}], "facts": [{**slide, "action": None}]},
            "sources": {"title": "Le pagine citate sono soprattutto di terzi", "read": "Una frase sulle fonti."},
            "method": {"limits": [], "ask": ["Quali pagine citano gli assistenti?"]},
        })
        doc.update(changes)
        return doc

    def save_doc(self, doc):
        self.path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    def problems(self, doc):
        self.save_doc(doc)
        return "\n".join(deck.check(self.study, self.path, DATE))


class MaterialTest(InsightCase, unittest.TestCase):

    def text(self):
        self.build(DATE)
        return self.material()

    def test_who_wrote_the_sources_is_shown_on_a_dimension_with_no_foil_page(self):
        self.ingest_market(9101, OCT[0], rows(choice=(("Dipende dai gusti.", 3, []), ("Dipende.", 3, []))))
        material = self.text()
        prezzo = material[material.index("### Dimension Prezzo"):material.index("#### Question")]
        self.assertIn("##### Who wrote the sources", prezzo)
        self.assertIn("owned pages in 1 of 2 (50%), a foil's pages in 0 of 2 (0%), third-party pages in 1 of 2 (50%)", prezzo)

    def test_a_dimension_citing_nothing_has_no_section(self):
        self.ingest_market(9101, OCT[0], rows())
        material = self.text()
        lavoro = material[material.index("### Dimension Lavoro"):]
        self.assertNotIn("##### Who wrote the sources", lavoro)

    def test_the_answers_naming_each_competitor_are_counted(self):
        self.ingest_market(9101, OCT[0], rows())
        self.build(DATE)
        scelta = self.period_file(DATE)["projects"]["market"]["dimensions"]["scelta"]
        self.assertEqual(scelta["total"]["foils"], {"Avoria": 1})
        self.assertEqual(scelta["by_model"][GPT]["foils"], {"Avoria": 1})
        self.assertEqual(scelta["by_model"][GEM]["foils"], {})
        self.assertIn("Competitors named: Avoria in 1 of 2 answers", self.material())


class BlocksTest(DeckCase, unittest.TestCase):

    def model(self, **doc):
        folder, _, study, period, _ = deck.load(self.study, DATE)
        return deck.build_model(folder, study, period, doc)

    def test_each_question_goes_to_the_block_of_its_type(self):
        m = self.model()
        self.assertEqual([r["label"] for r in m["blocks"]["reach"]["rows"]], ["Scelta"])
        self.assertEqual([r["label"] for r in m["blocks"]["description"]["rows"]], ["Lavoro"])
        self.assertEqual([r["label"] for r in m["blocks"]["facts"]["rows"]], [PRICE_Q])

    def test_block_figures_come_from_the_period(self):
        m = self.model()
        reach, description, facts = (m["blocks"][b] for b in deck.BLOCKS)
        self.assertEqual((reach["rows"][0]["named"], reach["rows"][0]["given"]), (0, 2))
        self.assertEqual(reach["rows"][0]["foils"], [("Avoria", 1)])
        self.assertEqual(description["rows"][0]["bands"], {"1-2": 0, "3": 0, "4-5": 2})
        self.assertAlmostEqual(description["rows"][0]["mean"], 4.0)
        self.assertEqual((facts["rows"][0]["current"], facts["rows"][0]["outdated"], facts["rows"][0]["silent"]), (1, 1, 0))
        self.assertEqual([(f["a"], f["b"]) for f in reach["figures"]], [(0, 2)])

    def test_a_question_naming_no_subject_with_facts_stays_in_reach_and_shows_its_fact(self):
        study = self.read("study.json")
        question = study["projects"][0]["dimensions"][1]["questions"][0]
        question["facts"] = [{"fact": "Avoria costa 3 €", "source": "https://avoria.example", "date": "2026-09-01",
                              "current": ["Avoria"], "outdated": []}]
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.build(DATE)
        m = self.model()
        self.assertEqual([r["label"] for r in m["blocks"]["reach"]["rows"]], ["Scelta"])
        self.assertIn(CHOICE_Q, [r["label"] for r in m["blocks"]["facts"]["rows"]])

    def test_a_category_as_subject_has_no_reach(self):
        study = self.read("study.json")
        study["subject"]["kind"] = "category"
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        m = self.model()
        self.assertEqual(m["blocks"]["reach"]["rows"], [])
        self.assertIn("Scelta", [r["label"] for r in m["blocks"]["description"]["rows"]])

    def test_the_writer_may_move_a_question_scoring_a_position(self):
        period = self.period_file(DATE)
        key = next(q["key"] for d in period["asked"]["market"] for q in d["questions"] if q["text"] == CHOICE_Q)
        m = self.model(moved={key: "description"})
        self.assertEqual(m["blocks"]["reach"]["rows"], [])
        self.assertIn("Scelta", [r["label"] for r in m["blocks"]["description"]["rows"]])

    def test_projects_stay_apart_unless_the_deck_says_they_share_an_audience(self):
        m = self.model(same_audience=True)
        self.assertEqual(m["blocks"]["reach"]["figures"][0]["project"], None)
        self.assertEqual(self.model()["blocks"]["reach"]["figures"][0]["project"], "Mercato")

    def test_sources_are_counted_by_block(self):
        sources = self.model()["blocks"]["facts"]["sources"]
        self.assertEqual({k: sources[k] for k in ("owned", "foil", "third", "with_sources")},
                         {"owned": 1, "foil": 0, "third": 1, "with_sources": 2})
        self.assertEqual(sources["domains"][0]["answers"], 1)

    def test_the_method_table_shows_what_ran_and_not_a_setting(self):
        row = self.model()["method"][0]
        self.assertEqual((row["name"], row["questions"], row["answers"]), ("Mercato", 3, 6))


class SkeletonTest(DeckCase, unittest.TestCase):

    def test_the_figures_file_has_no_answer(self):
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertNotIn("~~~~", text)
        self.assertNotIn("La migliore è Avoria", text)
        self.assertIn("## Blocks", text)
        self.assertIn(f"«{CHOICE_Q}»", text)

    def test_a_second_run_keeps_what_the_writer_wrote(self):
        self.save_doc(self.filled())
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["found"]["points"],
                         ["Una risposta su due riporta il prezzo."])

    def test_the_skeleton_is_refused_until_it_is_written(self):
        self.assertIn("left to write", "\n".join(deck.check(self.study, self.path, DATE)))

    def test_a_period_built_before_the_competitor_counts_is_refused(self):
        path = self.study / "history" / "periods" / f"{DATE}.json"
        period = json.loads(path.read_text(encoding="utf-8"))
        for block in period["projects"].values():
            for d in block["dimensions"].values():
                for q in d["questions"].values():
                    q["total"].pop("foils")
        path.write_text(json.dumps(period), encoding="utf-8")
        proc = self.cli("deck", "--study", self.study, "--date", DATE, check=2)
        self.assertIn("run period", proc.stderr)


class CheckTest(DeckCase, unittest.TestCase):

    def test_a_complete_deck_passes_and_is_recorded(self):
        proc = self.save_doc(self.filled()) or self.cli("check", "--study", self.study, self.path, check=0)
        self.assertIn("deck", proc.stdout)
        entry = self.read("history/reports.json")[-1]
        self.assertEqual((entry["date"], entry["status"]), (DATE, "final"))

    def test_a_deck_with_no_action_is_refused(self):
        self.assertIn("no action", self.problems(self.filled(actions=[])))

    def test_more_than_five_actions_are_refused(self):
        self.assertIn("at most 5", self.problems(self.filled(actions=self.filled()["actions"] * 6)))

    def test_an_action_with_no_evidence_slide_is_refused(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["action"] = None
        self.assertIn("action 1 has no evidence slide", self.problems(doc))

    def test_an_action_pointing_at_a_block_the_study_lacks_is_refused(self):
        doc = self.filled()
        doc["actions"][0]["block"] = "elsewhere"
        self.assertIn("elsewhere", self.problems(doc))

    def test_an_action_needs_a_known_class_and_figures(self):
        doc = self.filled()
        doc["actions"][0].update({"class": "bad_press", "read_next": "Risposte che nominano Avenello"})
        found = self.problems(doc)
        self.assertIn("bad_press", found)
        self.assertIn("read_next", found)

    def test_a_block_left_out_is_refused(self):
        doc = self.filled()
        del doc["blocks"]["description"]
        self.assertIn("block description has no slide", self.problems(doc))

    def test_a_figure_missing_from_the_period_is_refused(self):
        doc = self.filled()
        doc["found"]["title"] = "Avenello è nominata in 7 risposte su 9"
        self.assertIn("count 7 su 9", self.problems(doc))

    def test_a_mean_missing_from_the_period_is_refused(self):
        doc = self.filled()
        doc["blocks"]["description"][0]["read"] = "La media è 3,3 su 5."
        self.assertIn("3,3", self.problems(doc))

    def test_a_figure_the_deck_draws_may_be_cited(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["read"] = "Avoria compare in 1 risposta su 2 e Avenello in 0 risposte su 2."
        self.assertEqual(self.problems(doc), "")

    def excerpt(self, doc, text, question=PRICE_Q, assistant="Acme Chat"):
        doc["blocks"]["facts"][0]["excerpts"] = [{"text": text, "question": question, "assistant": assistant}]
        return doc

    def test_an_excerpt_must_be_verbatim(self):
        self.assertIn("not found verbatim", self.problems(self.excerpt(self.filled(), "Avenello costa 5 € al litro.")))

    def test_a_verbatim_excerpt_passes(self):
        self.assertEqual(self.problems(self.excerpt(self.filled(), OUTDATED[0])), "")

    def test_an_excerpt_must_come_from_its_question_and_its_assistant(self):
        found = self.problems(self.excerpt(self.filled(), CURRENT[0]))
        self.assertIn("not found verbatim", found)
        self.assertIn("Acme Chat", found)

    def test_an_excerpt_names_a_question_of_the_study(self):
        self.assertIn("is not a question", self.problems(self.excerpt(self.filled(), OUTDATED[0], question="Quanto costa?")))

    def test_an_excerpt_names_an_assistant_of_the_period(self):
        self.assertIn("is not an assistant", self.problems(self.excerpt(self.filled(), OUTDATED[0], assistant="Nessuno")))

    def test_an_excerpt_over_forty_words_is_refused(self):
        self.assertIn("40 words", self.problems(self.excerpt(self.filled(), "parola " * 41)))

    def test_an_excerpt_cut_inside_a_sentence_must_show_the_cut(self):
        self.ingest_market(9102, OCT[1], rows(price=((LONG, 2, []), CURRENT)))
        self.build(DATE)
        cut = "Avoria è la scelta più lineare se vuoi un prezzo semplice."
        self.assertIn("starts inside a sentence", self.problems(self.excerpt(self.filled(), cut)))
        self.assertEqual(self.problems(self.excerpt(self.filled(), f"[…] {cut}")), "")

    def test_an_excerpt_ending_inside_a_sentence_must_show_the_cut(self):
        self.ingest_market(9102, OCT[1], rows(price=((LONG, 2, []), CURRENT)))
        self.build(DATE)
        cut = "Avenello costa 2,10 € al litro"
        self.assertIn("ends inside a sentence", self.problems(self.excerpt(self.filled(), cut)))
        self.assertEqual(self.problems(self.excerpt(self.filled(), f"{cut} […]")), "")

    def test_text_longer_than_a_slide_holds_is_refused(self):
        doc = self.filled()
        doc["found"]["title"] = "parola " * 40
        self.assertIn("characters", self.problems(doc))

    def test_more_than_four_points_are_refused(self):
        doc = self.filled()
        doc["found"]["points"] = ["Una frase."] * 5
        self.assertIn("at most 4", self.problems(doc))

    def test_a_block_may_hold_two_slides_and_no_more(self):
        doc = self.filled()
        doc["blocks"]["reach"] = doc["blocks"]["reach"] * 3
        self.assertIn("at most 2", self.problems(doc))

    def test_words_about_how_the_answers_were_scored_are_refused(self):
        doc = self.filled()
        doc["found"]["points"] = ["Il giudice ha dato un punteggio basso."]
        self.assertIn("giudice", self.problems(doc))

    def test_a_model_id_a_question_key_or_a_file_name_is_refused(self):
        doc = self.filled()
        doc["found"]["points"] = [f"Vedi {GPT} e deck.json."]
        found = self.problems(doc)
        self.assertIn(GPT, found)
        self.assertIn("deck.json", found)

    def test_a_slide_cites_an_action_that_exists(self):
        doc = self.filled()
        doc["blocks"]["description"][0]["action"] = 7
        self.assertIn("action 7", self.problems(doc))

    def test_rows_of_a_slide_name_dimensions_of_the_block(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["dimensions"] = ["Lavoro"]
        self.assertIn("Lavoro", self.problems(doc))


class RenderTest(DeckCase, unittest.TestCase):

    def page(self, doc=None):
        self.save_doc(doc or self.filled())
        return deck.page_of(self.study, DATE)[0]

    def test_one_section_per_slide_in_the_reader_s_order(self):
        text = self.page()
        self.assertEqual(text.count('<section class="slide'), 8)
        kinds = re.findall(r'<section class="slide (\w+)', text)
        self.assertEqual(kinds, ["cover", "found", "actions", "reach", "description", "facts", "sources", "method"])

    def test_the_page_is_16_by_9_and_holds_no_script(self):
        text = self.page()
        self.assertIn("size: 13.333in 7.5in", text)
        self.assertNotIn("<script", text)

    def test_the_page_draws_the_figures_with_the_report_language(self):
        text = self.page()
        self.assertIn("0 su 2", text)
        self.assertIn("4,0", text)
        self.assertIn("Avoria 1", text)
        self.assertIn('class="bar"', text)

    def test_the_labels_are_in_the_report_s_language(self):
        text = self.page()
        self.assertIn("Dato su cui si basa", text)
        self.assertNotIn("Figura", text)

    def test_evidence_slides_are_numbered_from_the_block(self):
        self.assertIn('<td class="num">4</td>', self.page())

    def test_a_slide_shows_its_action_in_words(self):
        self.assertIn("Azione 1: Pubblicare una pagina di confronto", re.sub(r"<[^>]+>", "", self.page()))

    def test_the_method_slide_is_last_and_shows_answers_not_rounds(self):
        text = self.page()
        method = text[text.index('<section class="slide method'):]
        self.assertIn("Risposte nel periodo", method)
        self.assertNotIn("ripetizion", method.lower())
        self.assertIn("Quali pagine citano gli assistenti?", method)

    def test_english_labels(self):
        study = self.read("study.json")
        study["report_language"] = "en"
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.assertIn("Figure it rests on", self.page())

    def test_a_deck_failing_check_is_not_rendered(self):
        self.save_doc(self.filled(actions=[]))
        proc = self.cli("pdf", "--study", self.study, "--deck", "--date", DATE, check=2)
        self.assertIn("check", proc.stderr)

    def test_pages_that_are_not_the_slides_are_refused(self):
        self.save_doc(self.filled())
        with self.assertRaisesRegex(deck.Refused, "9 pages for 8 slides"):
            deck.render(self.study, DATE, printer=fake_pdf(9))

    def test_the_copy_to_send_has_a_descriptive_name(self):
        self.save_doc(self.filled())
        self.cli("check", "--study", self.study, self.path, check=0)
        message = deck.render(self.study, DATE, printer=fake_pdf(8))
        shared = list((self.study / "reports" / "share").glob("*.pdf"))
        self.assertEqual(len(shared), 1)
        self.assertIn("Avenello + Sentl.ai - monitoring deck", shared[0].name)
        self.assertIn(str(shared[0]), message)

    @unittest.skipUnless(shutil.which("chromium"), "no chromium on this machine")
    def test_the_fullest_slides_stay_on_one_page_each(self):
        longest = "parola " * 22
        doc = self.filled()
        doc["found"] = {"title": ("parola " * 16).strip(), "points": [longest.strip()] * 4}
        doc["actions"] = [{"class": "named_with_warning", "what": ("parola " * 24).strip(),
                           "rests_on": ("parola " * 9).strip() + " 2", "read_next": ("parola " * 9).strip() + " 2",
                           "block": "reach"}] * 5
        for slides in doc["blocks"].values():
            slides[0].update(title=("parola " * 16).strip(), read=("parola " * 29).strip())
        self.save_doc(doc)
        deck.render(self.study, DATE, skip_check=True)
        self.assertTrue((self.study / "reports" / f"{DATE}.deck.pdf").exists())


if __name__ == "__main__":
    unittest.main()
