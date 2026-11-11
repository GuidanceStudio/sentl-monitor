"""The deck route: the material it needs, its blocks, its check and its pages."""

import copy
import json
import re
import os
import shutil
import unittest
from collections import Counter
from unittest import mock

from fixtures import CHOICE_Q, GEM, GPT, PRICE_Q, listing, models
from sentlmon import deck, livepage, pack
from sentlmon import pdf as report_pdf
from test_insights_period import CURRENT, OCT, OUTDATED, InsightCase, rows
from test_pdf import sandboxless

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
        patcher = mock.patch.object(deck, "MIN_ANSWERS", 1)  # the fixture's questions have two answers each
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ingest_market(9101, OCT[0], rows())
        self.build(DATE)
        self.made = self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        self.path = self.study / "reports" / f"{DATE}.deck.json"

    def model_args(self, doc):
        folder, day, study, period, _ = deck.load(self.study, DATE)
        return folder, study, period, doc

    def filled(self, **changes):
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        m = deck.build_model(*self.model_args({}))
        slide = {"title": "Chi sceglie una bevanda trova Avoria", "read": "Una frase sulle risposte.", "excerpts": [], "action": 1}
        keys = {b: [q["key"] for q in m["blocks"][b]["questions"]] for b in deck.present(m)}
        examples = {b: k[:1] for b, k in keys.items()}
        if "description" in keys and "facts" in keys:
            examples["description"] = ([k for k in keys["description"] if k not in keys["facts"]] or keys["description"])[:1]
        tops = {s["domain"] for b in ("reach", "description") if b in m["blocks"] for s in m["blocks"][b]["sources"]["third_domains"][:1]}
        doc.update({
            "opening": {"who": "chi cerca una bevanda all'avena",
                        "questions": {"reach": "Chi cerca una bevanda senza fare nomi trova Avenello?",
                                      "description": "Chi chiede di Avenello cosa si sente dire?",
                                      "facts": "Il prezzo di Avenello è riportato bene?"},
                        "examples": examples},
            "found": {"title": "Chi cerca una bevanda all'avena trova Avoria prima di Avenello",
                      "answers": {"reach": "Avoria compare in 1 risposta su 2, Avenello in 0 risposte su 2.",
                                  "description": "Le risposte su chi lavora da Avenello sono favorevoli.",
                                  "facts": "Una risposta su due riporta il prezzo di oggi."}},
            "actions_title": "La prima cosa da fare è pubblicare una pagina di confronto",
            "actions": [{"class": "not_named", "what": "Pubblicare una pagina di confronto su avenello.example",
                         "why": "Avenello compare in 0 risposte su 2 e Avoria in 1 risposta su 2",
                         "read_next": "Risposte che nominano Avenello: 0 su 2", "block": "reach"}],
            "blocks": {"reach": [{**slide, "excerpts": [{"text": OUTDATED[0], "question": PRICE_Q, "assistant": "Acme Chat"}]}],
                       "description": [{**slide, "action": None,
                                        "excerpts": [{"text": CURRENT[0], "question": PRICE_Q, "assistant": "Orbit Reason"},
                                                     {"text": OUTDATED[0], "question": PRICE_Q, "assistant": "Acme Chat"}]}],
                       "facts": [{**slide, "action": None}]},
            "sources": {"title": "Le pagine citate sono soprattutto di altri siti",
                        "read": f"Una frase sulle fonti: {', '.join(sorted(tops))}, senza azione perché parlano bene."},
            "method": {"limits": [], "ask": ["Quali pagine citano gli assistenti?"]},
        })
        doc.update(changes)
        return doc

    def save_doc(self, doc):
        self.path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    def problems(self, doc):
        self.save_doc(doc)
        return "\n".join(deck.check(self.study, self.path, DATE))


class OneFactTest(DeckCase, unittest.TestCase):
    """A fact row bundled a second claim no answer states: the row reads as one fact carried or missed."""

    def test_a_question_holding_two_facts_is_refused(self):
        study = self.read("study.json")
        for d in (d for p in study["projects"] for d in p["dimensions"]):
            for q in d["questions"]:
                if q.get("facts"):
                    q["facts"].append({**q["facts"][0], "fact": "Avenello ha 22 punti vendita", "current": ["22 punti vendita"],
                                       "outdated": []})
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertIn("holds 2 facts", self.problems(self.filled()))

    def test_a_question_holding_one_fact_passes(self):
        self.assertNotIn("holds 2 facts", self.problems(self.filled()))

    def test_the_facts_block_counts_its_questions(self):
        self.assertIn("facts (1 questions)", self.made.stdout)

    def test_the_figures_file_gives_no_sources_line_for_facts(self):
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertNotIn("Sources: of 0 answers", text)


class LaterRecordTest(DeckCase, unittest.TestCase):
    """A fact another project records later, with other terms, no longer says what is current."""

    def add_later_record(self, current):
        path = self.study / "study.json"
        study = json.loads(path.read_text(encoding="utf-8"))
        later = copy.deepcopy(study["projects"][0])
        later["key"], later["name"] = "market-2", "Mercato 2"
        for d in later["dimensions"]:
            for q in d["questions"]:
                for f in q.get("facts") or []:
                    f.update({"fact": "Il prezzo al litro non è più pubblicato", "date": "2027-02-01", "current": current})
        study["projects"].append(later)
        path.write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)

    def model(self):
        return deck.build_model(*self.model_args(self.filled()))

    def test_the_question_leaves_the_facts_block(self):
        self.add_later_record([])
        m = self.model()
        self.assertNotIn(PRICE_Q, [r["label"] for r in m["blocks"]["facts"]["questions"]])
        self.assertIn(PRICE_Q, [q["text"] for q in m["blocks"]["description"]["placed"]])

    def test_the_same_terms_in_a_later_project_change_nothing(self):
        self.add_later_record(["2,10 €"])
        self.assertIn(PRICE_Q, [r["label"] for r in self.model()["blocks"]["facts"]["questions"]])

    def test_the_figures_file_names_the_later_record(self):
        self.add_later_record([])
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertIn("## Facts a later record replaces", text)
        self.assertIn("Il prezzo al litro non è più pubblicato", text)

    def test_the_replaced_term_is_refused(self):
        self.add_later_record([])
        doc = self.filled()
        del doc["blocks"]["facts"]
        doc["actions"][0]["what"] = "Pubblicare su avenello.example il prezzo di «2,10 €» al litro"
        self.assertIn("a later record replaces", self.problems(doc))


class TitleFiguresTest(unittest.TestCase):
    """A figure in a title is what the reader looks for in the chart below it."""

    def row(self, dimension, label, high, low, judged):
        return {"project": "P", "dimension": dimension, "label": label, "judged": judged, "given": judged, "named": 0,
                "bands": {"4-5": high, "3": judged - high - low, "1-2": low}, "foils": []}

    def setUp(self):
        questions = [self.row("Confronti", "Q1", 1, 4, 6), self.row("Confronti", "Q2", 4, 1, 6), self.row("Confronti", "Q3", 4, 0, 6)]
        rows = [self.row("Confronti", "Confronti", 9, 5, 18), self.row("Startup", "Startup", 6, 3, 12),
                self.row("Prezzi", "Prezzi", 13, 2, 18)]
        questions += [self.row("Startup", "Q4", 3, 1, 6), self.row("Startup", "Q5", 3, 2, 6), self.row("Prezzi", "Q6", 7, 1, 9),
                      self.row("Prezzi", "Q7", 6, 1, 9)]
        self.m = {"subject": "Avenello", "answers_of": {},
                  "blocks": {"description": {"rows": rows, "questions": questions, "figures": [{"a": 28, "b": 48}]}}}

    def problems(self, title, **slide):
        return deck._undrawn({"blocks": {"description": [{"title": title, **slide}]}}, self.m)

    def test_a_question_figure_over_a_chart_of_dimensions_is_refused(self):
        self.assertIn("does not draw", self.problems("Nel confronto 1 risposta su 6 è favorevole")[0])

    def test_a_figure_in_the_read_is_held_to_the_chart_as_well(self):
        self.assertIn("read cites", self.problems("Un titolo", read="Una domanda arriva a 1 risposta su 6.")[0])

    def test_a_slide_naming_its_questions_draws_those_and_no_dimension(self):
        self.m["blocks"]["description"]["questions"][0]["key"] = "q1"
        self.assertEqual(self.problems("Nel confronto 1 risposta su 6 è favorevole", questions=["q1"]), [])
        self.assertTrue(self.problems("Confronti ha 9 risposte su 18", questions=["q1"]))

    def test_drawing_the_questions_lets_the_title_cite_them(self):
        self.assertEqual(self.problems("Nel confronto 1 risposta su 6 è favorevole", rows="questions"), [])

    def test_a_dimension_figure_stays_citable_when_its_questions_are_drawn(self):
        self.assertEqual(self.problems("Confronti ha 9 risposte su 18", dimensions=["Confronti"]), [])

    def test_a_figure_of_a_dimension_left_out_of_the_slide_is_refused(self):
        self.assertTrue(self.problems("Startup ha 6 risposte su 12", dimensions=["Confronti"]))

    def test_the_block_figure_on_the_tiles_may_be_cited(self):
        self.assertEqual(self.problems("In tutto 28 risposte su 48 sono favorevoli"), [])


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
        self.assertEqual([r["label"] for r in m["blocks"]["description"]["rows"]], ["Prezzo", "Lavoro"])
        self.assertEqual([r["label"] for r in m["blocks"]["facts"]["questions"]], [PRICE_Q])

    def test_a_question_with_facts_also_counts_in_its_topic(self):
        """A topic reading 9 of 9 beside a question of its own reading 3 of 9 is a figure that flatters."""
        block = self.model()["blocks"]["description"]
        self.assertIn(PRICE_Q, [q["text"] for q in block["placed"]])
        self.assertIn(PRICE_Q, [r["label"] for r in self.model()["blocks"]["facts"]["questions"]])

    def test_block_figures_come_from_the_period(self):
        m = self.model()
        reach, description, facts = (m["blocks"][b] for b in deck.BLOCKS)
        self.assertEqual((reach["rows"][0]["named"], reach["rows"][0]["given"]), (0, 2))
        self.assertEqual(reach["rows"][0]["foils"], [("Avoria", 1)])
        self.assertEqual(next(r for r in description["rows"] if r["label"] == "Lavoro")["bands"], {"1-2": 0, "3": 0, "4-5": 2})
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
        self.assertIn(CHOICE_Q, [r["label"] for r in m["blocks"]["facts"]["questions"]])

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
        sources = self.model()["blocks"]["description"]["sources"]
        self.assertEqual({k: sources[k] for k in ("owned", "foil", "third")}, {"owned": 1, "foil": 0, "third": 1})
        self.assertEqual(sources["domains"][0]["answers"], 1)
        self.assertEqual([d["domain"] for d in sources["third_domains"]], ["prezzi.example"])

    def test_a_site_says_how_many_answers_citing_it_name_the_subject(self):
        reader = mock.Mock(position=lambda text: 1 if "Avenello" in text else None, author=lambda d: "third")
        source = [{"domain": "guida.example", "url": "https://guida.example/a"}]
        answers = [{"answer": "Avenello e Avoria.", "sources": source}, {"answer": "Avoria.", "sources": source}]
        with mock.patch.object(deck, "_authors", lambda *_: {}), mock.patch.object(deck, "cited_page", lambda s: s["url"]):
            sources = deck._sources(answers, reader)
        self.assertEqual(sources["third_domains"][0]["naming"], 1)
        self.assertEqual(sources["third_naming"], {"guida.example": 1})

    def test_the_figures_file_tells_third_parties_from_competitors(self):
        self.ingest_market(9102, OCT[1], rows(choice=(("La migliore è Avoria.", 3, ["https://avoria.example/x", "https://guida.example/y"]),
                                                      ("Dipende.", 3, []))))
        self.build(DATE)
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertIn("other sites cited most: guida.example (1, of which 0 name the subject)", text)
        self.assertIn("competitors' domains cited most: avoria.example", text)

    def test_the_method_table_shows_what_ran_and_not_a_setting(self):
        row = self.model()["method"][0]
        self.assertEqual((row["name"], row["questions"], row["answers"], row["runs"]), ("Mercato", 3, 6, 1))

    def test_the_method_table_says_how_often_each_project_ran(self):
        m = {"method": [{"name": "Mercato", "questions": 3, "assistants": ["Acme Chat"], "answers": 6, "runs": 7, "schedule": "daily"},
                        {"name": "Marca", "questions": 2, "assistants": ["Acme Chat"], "answers": 4, "runs": 2, "schedule": None}],
             "fidelity": False, "subject": "Avenello", "monitored": []}
        it = deck._method({}, m, deck.DECK["it"])
        self.assertIn("<th>Rilevazioni nel periodo</th>", it)
        self.assertIn("<td>7, in programma ogni giorno</td>", it)
        self.assertIn("<td>2</td></tr>", it)
        self.assertNotIn("Frequenza prevista", it)
        en = deck._method({}, m, deck.DECK["en"])
        self.assertIn("<th>Times asked in the period</th>", en)
        self.assertIn("<td>7, scheduled every day</td>", en)


class SkeletonTest(DeckCase, unittest.TestCase):

    def test_the_figures_file_has_no_answer(self):
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertNotIn("~~~~", text)
        self.assertNotIn("La migliore è Avoria", text)
        self.assertIn("## Blocks", text)
        self.assertIn(f"«{CHOICE_Q}»", text)

    def test_the_figures_file_gives_each_question_its_own_figure(self):
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"«" + re.escape(CHOICE_Q) + r"»: 0 su 2")

    def test_a_second_run_keeps_what_the_writer_wrote(self):
        self.save_doc(self.filled())
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["found"]["answers"]["facts"],
                         "Una risposta su due riporta il prezzo di oggi.")

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
        doc["found"]["title"] = "Il dato compare in 7 risposte su 9"
        self.assertIn("count 7 su 9", self.problems(doc))

    def test_a_mean_missing_from_the_period_is_refused(self):
        doc = self.filled()
        doc["blocks"]["description"][0]["read"] = "La media è 3,3 su 5."
        self.assertIn("3,3", self.problems(doc))

    def test_a_figure_the_deck_draws_may_be_cited(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["read"] = "Avoria compare in 1 risposta su 2 e Avenello in 0 risposte su 2."
        self.assertEqual(self.problems(doc), "")

    def without_counts(self):
        """The deck's text after a second run has moved the counts its reasons cite."""
        doc = self.filled()
        figure = deck.build_model(*self.model_args(doc))["blocks"]["reach"]["figures"][0]
        doc["actions"][0]["why"] = f"Avenello compare in {figure['a']} risposte su {figure['b']}"
        doc["found"]["answers"]["reach"] = f"Avoria compare in {dict(figure['rivals'])['Avoria']} risposte su {figure['b']}, " \
                                           f"Avenello in {figure['a']} risposte su {figure['b']}."
        return doc

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
        self.assertEqual(self.problems(self.excerpt(self.without_counts(), f"[…] {cut}")), "")

    def test_an_excerpt_ending_inside_a_sentence_must_show_the_cut(self):
        self.ingest_market(9102, OCT[1], rows(price=((LONG, 2, []), CURRENT)))
        self.build(DATE)
        cut = "Avenello costa 2,10 € al litro"
        self.assertIn("ends inside a sentence", self.problems(self.excerpt(self.filled(), cut)))
        self.assertEqual(self.problems(self.excerpt(self.without_counts(), f"{cut} […]")), "")

    def test_text_longer_than_a_slide_holds_is_refused(self):
        doc = self.filled()
        doc["found"]["title"] = "parola " * 40
        self.assertIn("characters", self.problems(doc))

    def test_a_block_may_hold_three_slides_and_no_more(self):
        doc = self.filled()
        doc["blocks"]["reach"] = doc["blocks"]["reach"] * 4
        self.assertIn("at most 3", self.problems(doc))

    def test_a_slide_with_an_action_needs_an_excerpt(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["excerpts"] = []
        self.assertIn("shows no answer", self.problems(doc))

    def test_a_sentence_saying_all_or_nothing_is_refused(self):
        for text in ("Nessuna trova il prezzo.", "Avenello resta assente dalle risposte.", "Tutte citano il prezzo.",
                     "Non lo citano mai."):
            doc = self.filled()
            doc["blocks"]["facts"][0]["read"] = text
            self.assertIn("all or nothing", self.problems(doc), text)

    def test_a_count_of_zero_says_the_same_and_passes(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["read"] = "Avenello compare in 0 risposte su 2."
        self.assertEqual(self.problems(doc), "")

    def test_none_beside_the_count_that_says_so_passes(self):
        for text in ("Nessuna delle 2 risposte nomina Avenello.", "Avenello non compare mai: 0 risposte su 2."):
            doc = self.filled()
            doc["blocks"]["reach"][0]["read"] = text
            self.assertEqual(self.problems(doc), "", text)

    def test_none_of_a_count_the_figures_do_not_hold_is_refused(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["read"] = "Nessuna delle 7 risposte nomina Avenello."
        self.assertIn("all or nothing", self.problems(doc))

    def test_an_action_may_say_all_of_what_to_do(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Pubblicare su avenello.example tutte le condizioni del piano"
        self.assertEqual(self.problems(doc), "")

    def test_a_band_named_in_words_is_refused(self):
        doc = self.filled()
        doc["found"]["answers"]["facts"] = "Una risposta su 2 sta nella fascia alta."
        self.assertIn("word of the study", self.problems(doc))

    def test_a_page_no_answer_cites_is_refused(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Chiarire su avenello.example/listino il prezzo al litro"
        self.assertIn("avenello.example/listino", self.problems(doc))

    def test_a_page_the_answers_cite_passes(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Chiarire su avenello.example/prezzi e su https://www.avenello.example/prezzi/ il prezzo"
        self.assertEqual(self.problems(doc), "")

    def test_a_page_recorded_as_the_source_of_a_fact_passes(self):
        study = json.loads((self.study / "study.json").read_text(encoding="utf-8"))
        fact = next(f for p in study["projects"] for d in p["dimensions"] for q in d["questions"] for f in q.get("facts") or [])
        fact["source"] = "avenello.example/listino"
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        doc = self.filled()
        doc["actions"][0]["what"] = "Chiarire su avenello.example/listino il prezzo al litro"
        self.assertEqual(self.problems(doc), "")

    def test_saying_the_answers_are_correct_is_refused(self):
        for text in ("Il prezzo è corretto in 1 risposta su 2.", "The price is correct in 1 of 2 answers."):
            doc = self.filled()
            doc["blocks"]["facts"][0]["read"] = text
            self.assertIn("state it", self.problems(doc), text)

    def test_an_action_may_ask_to_correct_a_page(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Pubblicare su avenello.example il dato corretto e chiedere di correggerlo"
        self.assertEqual(self.problems(doc), "")

    def test_a_facts_row_carries_its_ratings_in_the_figures_file(self):
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^- .*not stated .*favourable \d+ su \d+, neutral \d+ su \d+, unfavourable \d+ su \d+")

    def test_a_rating_count_on_a_facts_question_may_be_cited(self):
        doc = self.filled()
        row = deck.build_model(*self.model_args(doc))["blocks"]["facts"]["rows"][0]
        doc["blocks"]["facts"][0]["read"] = f"Sono favorevoli {row['bands']['4-5']} risposte su {row['judged']}."
        self.assertEqual(self.problems(doc), "")

    def test_words_about_how_the_answers_were_scored_are_refused(self):
        doc = self.filled()
        doc["found"]["answers"]["facts"] = "Il giudice non è convinto."
        self.assertIn("giudice", self.problems(doc))

    def test_a_model_id_a_question_key_or_a_file_name_is_refused(self):
        doc = self.filled()
        doc["found"]["answers"]["facts"] = f"Vedi {GPT} e deck.json."
        found = self.problems(doc)
        self.assertIn(GPT, found)
        self.assertIn("deck.json", found)

    def test_the_deck_is_not_named_in_its_own_text(self):
        doc = self.filled()
        doc["method"]["limits"] = ["Il deck non mostra cambiamenti nel tempo."]
        self.assertIn("deck", self.problems(doc))

    def test_an_action_cannot_send_the_reader_to_a_competitor_s_site(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Farsi inserire nelle pagine citate: guida.example, www.avoria.example."
        found = self.problems(doc)
        self.assertIn("action 1", found)
        self.assertIn("avoria.example", found)

    def test_a_slide_cites_an_action_that_exists(self):
        doc = self.filled()
        doc["blocks"]["description"][0]["action"] = 7
        self.assertIn("action 7", self.problems(doc))

    def test_rows_of_a_slide_name_dimensions_of_the_block(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["dimensions"] = ["Lavoro"]
        self.assertIn("Lavoro", self.problems(doc))


class ReportsIndexTest(DeckCase, unittest.TestCase):
    """The deck's check wrote the deck's path over the report's in history/reports.json."""

    def deck_check(self):
        self.save_doc(self.filled())
        return self.cli("check", "--study", self.study, self.path, check=0)

    def test_a_deck_check_keeps_the_report_and_records_the_deck_beside_it(self):
        self.publish(DATE)
        report = self.read("history/reports.json")
        self.deck_check()
        self.assertEqual(self.read("history/reports.json"), [{**report[0], "deck": f"reports/{DATE}.deck.json"}])

    def test_a_report_check_after_the_deck_keeps_the_deck(self):
        self.deck_check()
        self.publish(DATE)
        entries = self.read("history/reports.json")
        self.assertEqual([(e["date"], e["status"], e["file"], e["deck"]) for e in entries],
                         [(DATE, "final", f"reports/{DATE}.md", f"reports/{DATE}.deck.json")])

    def test_a_report_redone_for_its_date_keeps_the_deck(self):
        self.publish(DATE)
        self.deck_check()
        self.publish(DATE, force=True)
        entries = self.read("history/reports.json")
        self.assertEqual([(e["date"], e["status"], e["file"], e["deck"]) for e in entries],
                         [(DATE, "final", f"reports/{DATE}.md", f"reports/{DATE}.deck.json")])

    def test_a_deck_checked_beside_a_draft_report_leaves_it_a_draft_and_is_found_later(self):
        self.cli("method", "--study", self.study, "--date", DATE, "--models", self.save("models.json", models()), check=0)
        self.cli("check", "--study", self.study, self.study / "reports" / f"{DATE}.md", "--unattended", check=1)
        said = self.deck_check().stdout
        entry = self.read("history/reports.json")[0]
        self.assertEqual((entry["status"], entry["file"], entry["deck"]),
                         ("draft", f"reports/{DATE}.draft.md", f"reports/{DATE}.deck.json"))
        self.assertNotIn("as final", said)
        self.assertIn("record of its period", said)
        self.assertEqual(self.read("history/last-report.json")["outcome"], "draft")
        folder = deck.load(self.study, DATE)[0]
        self.assertEqual(deck._earlier(folder, "2026-11-30")[0], DATE)
        self.assertIn(f"reports/{DATE}.deck.json", pack.select(folder, False))

    def test_a_deck_recorded_in_the_report_s_place_moves_beside_it(self):
        self.deck_check()
        entry = self.read("history/reports.json")[0]
        entry.pop("deck", None)
        entry["file"] = f"reports/{DATE}.deck.json"
        (self.study / "history" / "reports.json").write_text(json.dumps([entry]), encoding="utf-8")
        self.deck_check()
        entry = self.read("history/reports.json")[0]
        self.assertEqual((entry.get("file"), entry["deck"]), (None, f"reports/{DATE}.deck.json"))


class DeckRecordTest(DeckCase, unittest.TestCase):
    """The deck is the only report: its check records the period, and the next period starts after its runs."""

    NOV = "2026-11-30"
    LATER = "2026-11-02T06:00:00Z"

    def deck_check(self, *extra, doc=None, check=0):
        self.save_doc(doc or self.filled())
        return self.cli("check", "--study", self.study, self.path, *extra, check=check)

    def listing(self, *runs):
        return self.save("runs-601.json", listing([(run_id, "completed", started) for run_id, started in runs], 601))

    def test_a_period_recorded_by_its_deck_alone_bounds_the_next_period(self):
        said = self.deck_check().stdout
        self.assertIn("the next period starts after its runs", said)
        self.assertNotIn("draft report", said)
        self.assertEqual([(e["date"], e["status"], e["runs"]) for e in self.read("history/reports.json")],
                         [(DATE, "final", self.period_file(DATE)["runs"])])
        fetch = self.cli("runs", "--study", self.study, "--project", "market", "--date", self.NOV,
                         "--saved", self.listing((9101, OCT[0]), (9102, self.LATER)), check=0).stdout
        self.assertIn("Fetch: 9102\n", fetch + "\n")
        self.ingest_market(9102, self.LATER, rows())
        self.build(self.NOV)
        later = self.period_file(self.NOV)
        self.assertEqual((later["runs"], later["comparison"]["previous"]), ({"market": [9102]}, DATE))

    def test_no_run_is_new_after_a_period_recorded_by_its_deck(self):
        self.deck_check()
        self.listing((9101, OCT[0]))
        self.assertTrue(self.cli("pending", "--study", self.study, "--date", DATE, check=0).stdout.startswith("nothing_new"))

    def test_an_unattended_deck_that_passes_records_written(self):
        self.deck_check("--unattended")
        last = self.read("history/last-report.json")
        self.assertEqual(last["outcome"], "written")
        self.assertIn(DATE, last["detail"])

    def test_an_unattended_deck_that_fails_is_recorded_as_a_draft_and_ends_the_invocation(self):
        said = self.deck_check("--unattended", doc=self.filled(actions=[]), check=1).stdout
        self.assertIn("recorded as a draft", said)
        entries = self.read("history/reports.json")
        self.assertEqual([(e["date"], e["status"], e["runs"], "deck" in e) for e in entries],
                         [(DATE, "draft", self.period_file(DATE)["runs"], False)])
        last = self.read("history/last-report.json")
        self.assertEqual(last["outcome"], "draft")
        self.assertIn("problem", last["detail"])
        self.listing((9101, OCT[0]))
        self.assertTrue(self.cli("pending", "--study", self.study, "--date", DATE, check=0).stdout.startswith("nothing_new"))

    def test_a_failing_deck_with_the_operator_present_records_nothing(self):
        self.deck_check(doc=self.filled(actions=[]), check=1)
        self.assertFalse((self.study / "history" / "reports.json").exists())
        self.assertFalse((self.study / "history" / "last-report.json").exists())

    def test_a_draft_deck_fixed_and_checked_again_becomes_the_final_record(self):
        self.deck_check("--unattended", doc=self.filled(actions=[]), check=1)
        self.deck_check()
        entry = self.read("history/reports.json")[0]
        self.assertEqual((entry["status"], entry["deck"]), ("final", f"reports/{DATE}.deck.json"))
        self.assertEqual(self.read("history/last-report.json")["outcome"], "written")
        self.assertEqual(deck._earlier(deck.load(self.study, DATE)[0], self.NOV)[0], DATE)

    def test_an_unattended_failure_leaves_a_deck_that_passed_before_as_it_was(self):
        self.deck_check()
        before = self.read("history/reports.json")
        self.deck_check("--unattended", doc=self.filled(actions=[]), check=1)
        self.assertEqual(self.read("history/reports.json"), before)
        self.assertEqual(self.read("history/last-report.json")["outcome"], "draft")


class OpeningTest(DeckCase, unittest.TestCase):
    """The deck says what it shows before any figure."""

    def page(self, doc=None):
        self.save_doc(doc or self.filled())
        return deck.page_of(self.study, DATE)[0]

    def slide(self, kind):
        text = self.page()
        at = text.index(f'<section class="slide {kind}')
        return text[at:text.index("</section>", at)]

    def test_the_cover_says_what_was_done_and_who_asked(self):
        cover = self.slide("cover")
        self.assertIn("Abbiamo fatto 3 domande agli assistenti AI, come le farebbero chi cerca una bevanda all'avena", cover)
        self.assertIn("Prima rilevazione", cover)

    def test_the_second_slide_shows_what_the_report_answers_and_what_was_asked(self):
        opening = self.slide("opening")
        self.assertIn("Cosa mostra questo report", opening)
        self.assertIn("Sapere cosa dicono gli assistenti AI di Avenello", opening)
        self.assertIn("Chi cerca una bevanda senza fare nomi trova Avenello?", opening)
        self.assertIn(f"«{CHOICE_Q}»", opening)
        self.assertIn("1 domanda, 2 risposte", opening)

    def test_it_says_how_to_read_a_figure_and_where_the_questions_are(self):
        opening = self.slide("opening")
        self.assertIn("I numeri contano risposte", opening)
        self.assertIn("favorevole se è positiva per Avenello, sfavorevole se è negativa o non trova quello che il criterio chiede", opening)
        self.assertIn("È la prima rilevazione", opening)
        self.assertIn("Tutte le domande sono alla slide 10", opening)

    def test_the_opening_says_where_the_questions_come_from(self):
        t = deck.DECK["it"]
        line = deck._origins_line({"origins": {"search", "client_analysis"}, "subject": "Avenello"}, t, "it")
        self.assertIn("Le domande vengono dalle analisi su Avenello e dalle ricerche su Google", line)
        self.assertEqual(deck._origins_line({"origins": set(), "subject": "Avenello"}, t, "it"), "")

    def test_the_answers_a_question_gives_are_counted_as_they_are(self):
        t = deck.DECK["it"]
        self.assertEqual(deck._spread([(9, 33)], t), "Ogni domanda ha 9 risposte")
        self.assertEqual(deck._spread([(9, 33), (2, 5)], t), "33 domande hanno 9 risposte ciascuna, 5 ne hanno 2")
        self.assertEqual(deck._spread([(9, 30), (8, 1), (2, 5)], t), "30 domande hanno 9 risposte ciascuna, 1 ne ha 8, 5 ne hanno 2")
        self.assertEqual(deck._spread([(9, 4), (8, 3), (7, 2), (2, 1)], t), "Ogni domanda ha tra 2 e 9 risposte")

    def test_questions_all_repeated_say_so_without_some(self):
        t = deck.DECK["en"]
        self.assertEqual(deck._reading_key({"totals": {"assistants": 3}, "spread": [(10, 12), (75, 13)],
                                            "method": [{"assistants": ["a", "b", "c"]}]}), "reading_answers_always")
        self.assertIn("several times.", t["reading_answers_always"])
        self.assertEqual(deck._reading_key({"totals": {"assistants": 3}, "spread": [(2, 5), (9, 33)],
                                            "method": [{"assistants": ["a", "b", "c"]}]}), "reading_answers")
        self.assertEqual(deck._reading_key({"totals": {"assistants": 1}, "spread": [(9, 33)],
                                            "method": [{"assistants": ["a"]}]}), "reading_answers_one")

    def test_a_cover_with_repeated_questions_says_so(self):
        m = {"totals": {"questions": 38, "assistants": 4, "answers": 307}, "repeated": True}
        line = deck._cover_line(m, "giovani", deck.DECK["it"])
        self.assertIn("38 domande agli assistenti AI, più volte, come le farebbero giovani", line)
        one = deck._cover_line({"totals": {"questions": 3, "assistants": 1, "answers": 3}, "repeated": False}, "giovani", deck.DECK["it"])
        self.assertIn("3 domande a un assistente AI, come", one)

    def test_the_cover_total_names_its_parts(self):
        m = {"totals": {"questions": 38, "assistants": 4, "answers": 790, "by_block": {"reach": 270, "description": 520}},
             "repeated": True, "subject": "Avenello"}
        self.assertIn("le 790 risposte: 270 alle domande senza il nome di Avenello e 520 a quelle su Avenello.",
                      deck._cover_line(m, "giovani", deck.DECK["it"]))
        self.assertIn("the 790 answers: 270 to the questions without Avenello's name and 520 to those about Avenello.",
                      deck._cover_line(m, "young people", deck.DECK["en"]))
        one = {**m, "totals": {**m["totals"], "answers": 520, "by_block": {"reach": 0, "description": 520}}}
        self.assertTrue(deck._cover_line(one, "giovani", deck.DECK["it"]).endswith("le 520 risposte."))

    def test_the_cover_parts_add_up_to_its_total(self):
        m = deck.build_model(*self.model_args({}))
        self.assertEqual(sum(m["totals"]["by_block"].values()), m["totals"]["answers"])
        self.assertIn("le 6 risposte: 2 alle domande senza il nome di Avenello e 4 a quelle su Avenello", self.slide("cover"))

    def test_the_list_of_questions_on_two_slides_is_said_as_two(self):
        m = deck.build_model(*self.model_args({}))
        html_page = deck._opening_slide(self.filled(), m, deck.DECK["it"], "it", (12, 13))
        self.assertIn("Tutte le domande sono alle slide 12-13", html_page)

    def test_the_reader_can_add_the_answers_up(self):
        """The cover, the cards and the method rest on one count: 1093 beside 120 + 965 reads as an error."""
        m = deck.build_model(*self.model_args({}))
        cards = sum(deck._measure(b, r)[1] for b in ("reach", "description") for r in m["blocks"][b]["rows"])
        self.assertEqual(m["totals"]["answers"], cards)
        self.assertEqual(sum(r["answers"] for r in m["method"]), cards)
        self.assertEqual(sum(n * q for n, q in m["spread"]), cards)

    def test_the_chart_says_when_one_assistant_answers(self):
        t = deck.DECK["it"]
        f = {"a": 72, "b": 120, "rivals": [("Avoria", 75)], "rank": 2, "names": 10, "left_out": False, "project": None}
        self.assertIn("A queste domande risponde solo Perplexity Sonar", deck._versus(f, "Avenello", t, "Perplexity Sonar"))
        self.assertNotIn("risponde solo", deck._versus(f, "Avenello", t))

    def test_the_chart_says_how_many_names_it_shows(self):
        t = deck.DECK["it"]
        f = {"a": 14, "b": 90, "rivals": [(f"R{i}", 40 - i) for i in range(8)], "rank": 9, "names": 11, "left_out": False, "project": None}
        self.assertIn("posizione 9 su 11 nomi monitorati; qui i primi 4 e Avenello", deck._versus(f, "Avenello", t))
        f = {**f, "a": 39, "rank": 2}
        self.assertIn("posizione 2 su 11 nomi monitorati; qui i primi 5", deck._versus(f, "Avenello", t))

    def test_names_a_few_answers_apart_are_said_to_be_close(self):
        t = deck.DECK["it"]
        f = {"a": 39, "b": 180, "rivals": [("Avoria", 62), ("Oatfield", 37), ("Nordic", 36), ("Altro", 25)], "rank": 2,
             "names": 5, "left_out": False, "project": None}
        self.assertIn("Nel confronto con Avenello, Oatfield ha 2 risposte in meno e Nordic 3 in meno: il prossimo report "
                      "può invertire l'ordine.", deck._versus(f, "Avenello", t))
        far = {**f, "rivals": [("Avoria", 62), ("Altro", 25)]}
        self.assertNotIn("Nel confronto con", deck._versus(far, "Avenello", t))

    def test_each_close_name_says_whether_it_has_more_answers_or_fewer(self):
        f = {"a": 39, "b": 180, "rivals": [("Avoria", 41), ("Oatfield", 38), ("Nordic", 39)], "rank": 2,
             "names": 4, "left_out": False, "project": None}
        self.assertIn("Nel confronto con Avenello, Avoria ha 2 risposte in più, Oatfield 1 in meno e Nordic lo stesso numero:",
                      deck._versus(f, "Avenello", deck.DECK["it"]))
        self.assertIn("Compared with Avenello, Avoria has 2 more answers, Oatfield 1 fewer and Nordic the same number:",
                      deck._versus(f, "Avenello", deck.DECK["en"]))
        one = {**f, "rivals": [("Oatfield", 38), ("Altro", 5)]}
        self.assertIn("Nel confronto con Avenello, Oatfield ha 1 risposta in meno:", deck._versus(one, "Avenello", deck.DECK["it"]))
        self.assertIn("Compared with Avenello, Oatfield has 1 fewer answer:", deck._versus(one, "Avenello", deck.DECK["en"]))

    def test_a_subject_named_in_no_answer_has_nobody_close_to_report(self):
        t = deck.DECK["it"]
        f = {"a": 0, "b": 90, "rivals": [("Avoria", 1)], "rank": 2, "names": 2, "left_out": False, "project": None}
        self.assertNotIn("Nel confronto con", deck._versus(f, "Avenello", t))

    def test_every_count_stands_beside_its_bar(self):
        """A thin part of a bar has no room for its number: 12, 5 and 1 must all be readable."""
        t = deck.DECK["it"]
        m = {"subject": "Avenello", "fidelity": False}
        row = {"project": "P", "label": "Costo", "judged": 18, "bands": {"4-5": 12, "3": 5, "1-2": 1}}
        html_page = deck._rows("description", [row], t, "it", m, False, 0)
        self.assertIn('<div class="fig">12 su 18</div><div class="fig">5</div><div class="fig">1</div>', html_page)
        self.assertIn('<i class="mid"></i>Neutre', html_page)

    def test_the_method_says_the_assistants_are_not_the_app(self):
        self.assertIn("senza account né cronologia", self.slide("method"))

    def test_the_method_keeps_the_rating_scale_out_and_names_the_competitors(self):
        method = self.slide("method")
        self.assertNotIn("scala da 1 a 5", method)
        self.assertNotIn("4 o 5", method)
        self.assertIn("Concorrenti monitorati", method)

    def test_each_card_says_which_assistants_answered(self):
        self.assertIn("Assistenti: ", self.slide("opening"))

    def test_the_sources_show_the_subjects_pages_and_every_site_an_action_names(self):
        t = deck.DECK["it"]
        source = {"with_sources": 3, "answers": 9, "owned": 2, "foil": 0, "third": 3,
                  "third_domains": [{"domain": "a.example", "answers": 5}],
                  "third_all": {"a.example": 5, "b.example": 2, "c.example": 1},
                  "owned_pages": [("avenello.example/prezzi", 4)]}
        m = {"blocks": {"reach": {"rows": [1], "sources": source}, "description": {"rows": [], "sources": source},
                        "facts": {"rows": [], "sources": source}}}
        page = deck._sources_table({"actions": [{"what": "Scrivere a b.example"}]}, m, t, "Avenello")
        self.assertIn("a.example (5), b.example (2)", page)
        self.assertNotIn("c.example", page)
        self.assertIn("Pagine di Avenello più citate (risposte): avenello.example/prezzi (4)", page)

    def test_on_the_questions_without_the_name_a_site_shows_how_many_answers_name_the_subject(self):
        t = deck.DECK["it"]
        source = {"with_sources": 3, "answers": 9, "owned": 2, "foil": 0, "third": 3,
                  "third_domains": [{"domain": "a.example", "answers": 5, "naming": 2}],
                  "third_all": {"a.example": 5}, "third_naming": {"a.example": 2}, "owned_pages": []}
        m = {"blocks": {"reach": {"rows": [1], "sources": source}, "description": {"rows": [1], "sources": source},
                        "facts": {"rows": [], "sources": source}}}
        page = deck._sources_table({"actions": []}, m, t, "Avenello")
        self.assertEqual(page.count("a.example (5 risposte, 2 con Avenello)"), 1)
        self.assertIn("a.example (5)", page)
        self.assertIn("quante nominano Avenello", page)

    def test_a_stray_line_on_a_last_page_of_questions_is_drawn_tighter(self):
        placed = [{"text": "Una domanda abbastanza corta?", "dimension": "Tema"} for _ in range(56)]
        m = {"subject": "Avenello", "blocks": {b: {"rows": [1] if b == "reach" else [], "placed": placed if b == "reach" else []}
                                               for b in deck.BLOCKS}}
        pages = deck._question_pages(m, deck.DECK["it"])
        self.assertEqual(len(pages), 1)
        self.assertIn(" tight", deck._questions_slide(pages[0], 1, 1, m, deck.DECK["it"]))

    def test_the_finding_answers_the_same_questions_in_the_same_order(self):
        found = self.slide("found")
        self.assertLess(found.index("trova Avenello?"), found.index("cosa si sente dire?"))
        self.assertIn("Avoria compare in 1 risposta su 2", found)

    def test_an_evidence_slide_carries_the_question_it_belongs_to(self):
        self.assertIn('<div class="kicker">Chi cerca una bevanda senza fare nomi trova Avenello?</div>', self.slide("reach"))

    def test_the_list_of_questions_closes_the_deck(self):
        questions = self.slide("questions")
        for text in (CHOICE_Q, PRICE_Q):
            self.assertIn(text, questions)
        self.assertIn("Le 3 domande", questions)

    def test_a_long_list_of_questions_takes_several_slides(self):
        m = {"subject": "A", "blocks": {b: {"rows": [], "placed": []} for b in deck.BLOCKS}}
        m["blocks"]["description"] = {"rows": [{}], "placed": [{"text": "Una domanda", "dimension": f"Tema {n // 4}"} for n in range(120)]}
        pages = deck._question_pages(m, deck.DECK["it"])
        self.assertGreater(len(pages), 1)
        self.assertTrue(all(len(p) <= 2 for p in pages))

    def test_an_opening_question_must_be_a_question(self):
        doc = self.filled()
        doc["opening"]["questions"]["reach"] = "La presenza di Avenello"
        self.assertIn("end it with ?", self.problems(doc))

    def test_each_block_needs_a_real_question_as_example(self):
        doc = self.filled()
        doc["opening"]["examples"]["reach"] = []
        self.assertIn("opening example of reach", self.problems(doc))
        doc["opening"]["examples"]["reach"] = ["nowhere"]
        self.assertIn("not a question of block reach", self.problems(doc))

    def test_each_block_needs_its_answer(self):
        doc = self.filled()
        del doc["found"]["answers"]["description"]
        self.assertIn("found answer description is missing", self.problems(doc))

    def test_an_excerpt_names_the_assistant_with_its_maker(self):
        self.assertEqual(deck._public("Sonar", {"perplexity/sonar": "Perplexity: Sonar"}), "Perplexity Sonar")

    def test_the_assistants_are_shown_by_maker(self):
        names = {"a/one": "Anthropic: Claude One", "a/two": "Anthropic: Claude Two", "p/s": "Perplexity: Sonar"}
        self.assertEqual(deck._makers(["p/s", "a/one", "a/two"], names), "Anthropic (Claude One, Claude Two), Perplexity (Sonar)")


class FavourableShowsTest(DeckCase, unittest.TestCase):

    def test_a_description_slide_without_an_answer_is_refused(self):
        doc = self.filled()
        doc["blocks"]["description"][0]["excerpts"] = []
        doc["blocks"]["description"][0]["action"] = None
        self.assertIn("what a favourable answer says", " ".join(deck._structure(doc, deck.build_model(*self.model_args(doc)))))


class ActionEvidenceTest(DeckCase, unittest.TestCase):

    def test_a_reason_its_slide_does_not_draw_is_refused(self):
        doc = self.filled()
        doc["actions"][0]["why"] = "Avenello compare in 7 risposte su 9"
        problems = deck._why_drawn(doc, deck.build_model(*self.model_args(doc)))
        self.assertIn("its slide does not draw it", " ".join(problems))

    def test_entering_a_listing_on_a_site_the_answers_cite_is_refused(self):
        doc = self.filled()
        m = deck.build_model(*self.model_args(doc))
        m["blocks"]["description"]["sources"]["third_all"] = {"guida.example": 2}
        doc["actions"][0]["what"] = "Inserire Avenello nelle pagine di guida.example"
        self.assertTrue(deck._listed_already(doc, m))

    def test_an_action_with_no_site_is_refused(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Chiedere a Docsity di riportare il prezzo"
        self.assertIn("names no site", self.problems(doc))

    def test_an_action_on_a_site_no_answer_cites_is_refused(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Scrivere a mai-citato.example il prezzo"
        self.assertIn("which no answer cites", self.problems(doc))

    def test_a_third_party_page_is_asked_for_never_edited(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Aggiornare la guida di prezzi.example con il prezzo"
        self.assertIn("the reader does not own", self.problems(doc))
        doc["actions"][0]["what"] = "Add the price to prezzi.example"
        self.assertIn("the reader does not own", self.problems(doc))
        doc["actions"][0]["what"] = "Chiedere a prezzi.example di riportare il prezzo"
        self.assertNotIn("the reader does not own", self.problems(doc))

    def test_the_subjects_own_page_can_be_edited(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Aggiornare la pagina prezzi di avenello.example"
        self.assertNotIn("the reader does not own", self.problems(doc))


class TooFewTest(DeckCase, unittest.TestCase):
    """One answer of two is no finding: the question counts in its topic and in the list, nowhere else."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(deck, "MIN_ANSWERS", 3)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_row_of_a_question_with_too_few_answers_is_refused(self):
        doc = self.filled()
        m = deck.build_model(*self.model_args(doc))
        key = m["blocks"]["description"]["questions"][0]["key"]
        doc["blocks"]["description"][0]["questions"] = [key]
        self.assertIn("too few", " ".join(deck._too_few(doc, m)))

    def test_an_excerpt_of_such_a_question_is_refused(self):
        doc = self.filled()
        m = deck.build_model(*self.model_args(doc))
        self.assertIn("too few", " ".join(deck._too_few(doc, m)))

    def test_a_topic_of_such_questions_draws_its_row_instead(self):
        m = deck.build_model(*self.model_args({}))
        block = m["blocks"]["description"]
        rows = deck.rows_of("description", block, {"dimensions": [], "questions": [], "rows": "dimensions"})
        self.assertFalse(any(r.get("key") for r in rows))


class SiteOnItsQuestionsTest(DeckCase, unittest.TestCase):
    """The reader goes to the action's slide to see why that site: it is read on those questions."""

    def test_a_site_cited_on_other_questions_is_refused(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Chiedere a prezzi.example di riportare il prezzo"
        self.assertIn("on the questions of its slide", self.problems(doc))

    def test_a_site_cited_on_the_slides_questions_passes(self):
        doc = self.filled()
        doc["actions"][0].update({"what": "Chiedere a prezzi.example di riportare il prezzo", "block": "description"})
        doc["blocks"]["reach"][0]["action"] = None
        doc["blocks"]["description"][0]["action"] = 1
        self.assertNotIn("on the questions of its slide", self.problems(doc))


class QuoteRatingTest(DeckCase, unittest.TestCase):
    """A reader of an excerpt asks how that answer was rated."""

    def test_an_excerpt_says_how_its_answer_was_rated(self):
        m = deck.build_model(*self.model_args({}))
        excerpt = {"text": CURRENT[0], "question": PRICE_Q, "assistant": "Orbit Reason"}
        self.assertEqual(deck._rating(excerpt, m, "description"), "4-5")
        low = {"text": OUTDATED[0], "question": PRICE_Q, "assistant": "Acme Chat"}
        self.assertEqual(deck._rating(low, m, "description"), "1-2")

    def test_a_reach_excerpt_shows_no_rating(self):
        m = deck.build_model(*self.model_args({}))
        self.assertIsNone(deck._rating({"text": CURRENT[0]}, m, "reach"))

    def test_the_rating_is_on_the_caption(self):
        t = deck.DECK["it"]
        excerpt = {"text": "Testo", "question": "Domanda?", "assistant": "Acme Chat"}
        html = deck._quotes([excerpt], t, {"m": "Acme Chat"}, ["4-5"])
        self.assertIn("Risposta favorevole", html)
        self.assertNotIn("Risposta", deck._quotes([excerpt], t, {"m": "Acme Chat"}))


class OpeningExamplesTest(DeckCase, unittest.TestCase):
    """The first slide promises the questions the deck then answers."""

    def test_a_question_with_too_few_answers_is_no_example(self):
        doc = self.filled()
        with mock.patch.object(deck, "MIN_ANSWERS", 3):
            self.assertIn("opening example", self.problems(doc))

    def test_a_question_with_enough_answers_passes(self):
        self.assertNotIn("too few answers for a finding: pick", self.problems(self.filled()))

    def test_two_cards_never_show_the_same_question(self):
        m = {"blocks": {"description": {"questions": [{"key": "a", "answers": 9}, {"key": "b", "answers": 9}]},
                        "facts": {"questions": [{"key": "a", "answers": 9}]}}}
        doc = {"opening": {"examples": {"description": ["a"], "facts": ["a"]}}}
        with mock.patch.object(deck, "present", lambda _: ["description", "facts"]), mock.patch.object(deck, "_thin", lambda *_: False):
            self.assertTrue(deck._same_examples(doc, m))
            doc["opening"]["examples"]["description"] = ["b"]
            self.assertEqual(deck._same_examples(doc, m), [])

    def test_a_card_with_no_other_question_may_repeat(self):
        m = {"blocks": {"description": {"questions": [{"key": "a", "answers": 9}]},
                        "facts": {"questions": [{"key": "a", "answers": 9}]}}}
        doc = {"opening": {"examples": {"description": ["a"], "facts": ["a"]}}}
        with mock.patch.object(deck, "present", lambda _: ["description", "facts"]), mock.patch.object(deck, "_thin", lambda *_: False):
            self.assertEqual(deck._same_examples(doc, m), [])


class DoubtQuotedTest(unittest.TestCase):
    """A doubt printed beside "favourable answer" reads as a contradiction."""

    doc = {"blocks": {"facts": [{"excerpts": [{"text": "Non ho trovato nelle fonti la descrizione delle tutele."}]}]}}

    def test_a_doubt_from_a_favourable_answer_is_refused(self):
        with mock.patch.object(deck, "_rating", lambda *_: "4-5"):
            self.assertTrue(deck._doubts(self.doc, {}))

    def test_an_answer_that_cannot_judge_is_a_doubt_too(self):
        doc = {"blocks": {"description": [{"excerpts": [{"text": "Avenello non compare nei risultati e quindi non posso valutarlo."}]}]}}
        with mock.patch.object(deck, "_rating", lambda *_: "4-5"):
            self.assertTrue(deck._doubts(doc, {}))

    def test_a_doubt_from_an_unfavourable_answer_passes(self):
        with mock.patch.object(deck, "_rating", lambda *_: "1-2"):
            self.assertEqual(deck._doubts(self.doc, {}), [])

    def test_a_favourable_sentence_passes(self):
        doc = {"blocks": {"facts": [{"excerpts": [{"text": "I fondi sono tenuti separati."}]}]}}
        with mock.patch.object(deck, "_rating", lambda *_: "4-5"):
            self.assertEqual(deck._doubts(doc, {}), [])


class SiteComparisonTest(DeckCase, unittest.TestCase):
    """Two sites level at 44 were written as one overtaking the other: the table holds the counts."""

    def test_a_site_said_to_overtake_another_is_refused(self):
        doc = self.filled(sources={"title": "Trustpilot supera Rivistatech sulle domande col nome", "read": "Una frase sulle fonti."})
        self.assertIn("compares sites in words", self.problems(doc))

    def test_the_plain_sentence_passes(self):
        self.assertNotIn("compares sites in words", self.problems(self.filled()))

    def test_the_site_cited_most_says_among_which(self):
        doc = self.filled(sources={"title": "Rivistatech è il sito più citato", "read": "Una frase sulle fonti."})
        self.assertIn("says the site cited most", self.problems(doc))
        doc = self.filled(sources={"title": "Rivistatech è il sito più citato di terzi", "read": "Una frase sulle fonti."})
        self.assertNotIn("says the site cited most", self.problems(doc))


class AmountShownTest(DeckCase, unittest.TestCase):
    """An amount no slide shows has no proof: it is a recorded fact or it stands in an excerpt on its slide."""

    def test_an_amount_with_no_proof_on_the_slide_is_refused(self):
        doc = self.filled()
        doc["actions"][0]["why"] = "Avenello compare in 0 risposte su 2, con prezzi fino a 6.000 euro"
        self.assertIn("an amount", self.problems(doc))

    def test_a_title_is_held_to_the_same_rule(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["title"] = "Il prezzo arriva a 6.000 euro"
        self.assertIn("an amount", self.problems(doc))

    def test_an_amount_in_an_excerpt_of_its_slide_passes(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["excerpts"][0]["text"] = "Il corso costa 6.000 euro."
        doc["actions"][0]["why"] = "Avenello compare in 0 risposte su 2, con prezzi fino a 6.000 €"
        self.assertEqual(deck._amounts(doc, {"projects": []}), [])

    def test_a_recorded_amount_passes(self):
        doc = {"actions": [{"why": "Le risposte riportano 69 €"}], "blocks": {}}
        with mock.patch.object(deck, "_quotable", lambda _: {"69 €"}):
            self.assertEqual(deck._amounts(doc, {}), [])


class ActionOrderTest(DeckCase, unittest.TestCase):
    """The writer ranks the actions by the answers and the part of the reader's purpose each moves, and the deck keeps
    that order: sorting the subject's own pages first put the largest gap of one study third. Each action says who acts."""

    def doc(self):
        doc = self.filled()
        first = {**doc["actions"][0], "what": "Chiedere a prezzi.example di riportare il prezzo", "block": "description"}
        doc["actions"] = [first, doc["actions"][0]]
        doc["blocks"]["reach"][0]["action"] = 2
        doc["blocks"]["description"][0]["action"] = 1
        return doc

    def rows(self):
        self.save_doc(self.doc())
        text = deck.page_of(self.study, DATE)[0]
        table = text.split('<section class="slide actions')[1].split("<tbody>")[1].split("</tbody>")[0]
        return text, table.split("</tr>")[:2]

    def test_the_table_keeps_the_writers_order_and_says_who_acts(self):
        _, (first, second) = self.rows()
        self.assertIn('<td class="num">1</td>', first)
        self.assertIn("Chiedere a prezzi.example", first)
        self.assertIn("Richiesta a un sito di terzi", first)
        self.assertIn("Pubblicare una pagina di confronto su avenello.example", second)
        self.assertIn("Sulle pagine di Avenello", second)

    def test_a_slide_prints_the_number_the_table_does(self):
        text, _ = self.rows()
        self.assertIn("<b>Azione 1:</b> Chiedere a prezzi.example", text)
        self.assertIn("<b>Azione 2:</b> Pubblicare una pagina di confronto", text)

    def test_no_note_states_an_order_the_writer_did_not_give(self):
        text, _ = self.rows()
        self.assertNotIn("Prima le azioni", text)

    def test_english_says_who_acts(self):
        study = self.read("study.json")
        study["report_language"] = "en"
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        _, (first, second) = self.rows()
        self.assertIn("A request to a third-party site", first)
        self.assertIn("On Avenello's own pages", second)

    def test_one_action_on_the_subjects_own_pages_is_still_required(self):
        doc = self.doc()
        doc["actions"] = doc["actions"][:1]
        doc["blocks"]["reach"][0]["action"] = None
        self.assertIn("every action asks a third party", self.problems(doc))

    def test_a_text_never_names_an_action_by_number(self):
        doc = self.filled(sources={"title": "Le pagine citate sono soprattutto di altri siti", "read": "L'azione 2 riguarda queste fonti."})
        self.assertIn("by its number", self.problems(doc))


def _sources(owned, foil, third, with_sources, third_domains=()):
    return {"with_sources": with_sources, "answers": 6, "owned": owned, "foil": foil, "third": third,
            "third_domains": [{"domain": d, "answers": n} for d, n in third_domains], "third_all": dict(third_domains),
            "third_naming": {}, "owned_pages": []}


def _model(sources):
    return {"subject": "Avenello", "fidelity": False,
            "blocks": {"reach": {"rows": [{}], "sources": sources}, "description": {"rows": []}, "facts": {"rows": []}}}


class DrawnLabelsTest(unittest.TestCase):
    """A label the code draws says what its numbers count: the writer cannot change it."""

    def test_the_sources_slide_says_its_numbers_count_answers_citing(self):
        self.assertEqual(deck.DECK["it"]["sources_kicker"], "Quante risposte citano ogni fonte")
        self.assertEqual(deck.DECK["en"]["sources_kicker"], "How many answers cite each source")

    def test_a_count_of_answers_with_nothing_to_count_is_0(self):
        row = {"project": "P", "label": "Chi vende bevande all'avena?", "foils": [], "named": 0, "given": 2}
        for lang, word in (("it", "nessuno"), ("en", "none")):
            with self.subTest(lang):
                t = deck.DECK[lang]
                drawn = deck._rows("reach", [row], t, lang, _model({}), False, 0)
                self.assertIn('<div class="foils">0</div>', drawn)
                table = deck._sources_table({"actions": []}, _model(_sources(1, 0, 0, 1)), t, "Avenello")
                self.assertIn("<td>0</td></tr>", table)
                self.assertNotIn(word, drawn + table)

    def test_columns_that_overlap_carry_a_note(self):
        for lang, note in (("it", "Una risposta può citare più tipi di fonte"),
                           ("en", "An answer can cite more than one kind of source")):
            with self.subTest(lang):
                t = deck.DECK[lang]
                overlapping = _model(_sources(2, 1, 2, 3, [("guida.example", 2)]))
                self.assertIn(note, deck._sources_table({"actions": []}, overlapping, t, "Avenello"))
                apart = _model(_sources(1, 0, 2, 3, [("guida.example", 2)]))
                self.assertNotIn(note, deck._sources_table({"actions": []}, apart, t, "Avenello"))


class NamesakeTest(unittest.TestCase):
    """A site sharing the subject's name, which the subject does not own, read as the subject's own."""

    def test_a_site_named_like_the_subject_is_labelled_as_another_organisation(self):
        m = {**_model(_sources(0, 0, 2, 2, [("avenello.it", 2), ("guida.example", 1)])), "aliases": ["Avenello", "Avenello Spa"]}
        it = deck._sources_table({"actions": []}, m, deck.DECK["it"], "Avenello")
        self.assertIn("avenello.it (2, un'altra organizzazione di nome Avenello)", it)
        self.assertIn("guida.example (1)", it)
        en = deck._sources_table({"actions": []}, m, deck.DECK["en"], "Avenello")
        self.assertIn("avenello.it (2, another organisation named Avenello)", en)

    def test_an_alias_names_the_namesake_too(self):
        m = {**_model(_sources(0, 0, 1, 1, [("oat-co.example", 1)])), "subject": "Avenello", "aliases": ["Oat Co"]}
        self.assertIn("oat-co.example (1, un'altra organizzazione di nome Oat-co)",
                      deck._sources_table({"actions": []}, m, deck.DECK["it"], "Avenello"))


class FigureBesideTest(unittest.TestCase):
    """A count in the text and the chart beside it: "tutte le 14" stood beside a row drawn at 8 of 14."""

    ROW = {"project": "P", "dimension": "Contatti", "dimensions": ["Contatti"], "label": "Il numero verde è 800 123 456",
           "given": 14, "current": 8, "outdated": 0, "both": 0, "silent": 6, "judged": 14,
           "bands": {"1-2": 2, "3": 4, "4-5": 8}, "asked": 1}

    def model(self):
        return {"subject": "Avenello", "monitored": ["Avoria"], "answers_of": {}, "author": lambda d: "third",
                "blocks": {"reach": {"rows": [], "questions": [], "figures": []},
                           "description": {"rows": [], "questions": [], "figures": []},
                           "facts": {"rows": [self.ROW], "questions": [self.ROW],
                                     "figures": [{"a": 8, "b": 14, "parts": [(8, "good"), (0, "low"), (6, "mid")],
                                                  "rivals": [], "project": None}]}}}

    def problems(self, title, found=None):
        doc = {"blocks": {"facts": [{"title": title, "read": "Una frase."}]},
               "found": {"answers": {"facts": found or "Una frase."}}}
        return "\n".join(deck._beside_figure(doc, self.model()))

    def test_a_count_the_chart_beside_it_does_not_draw_is_refused(self):
        self.assertIn("14 of 14", self.problems("Il numero verde è riportato in tutte le 14 risposte"))
        self.assertIn("10 of 14", self.problems("Il numero verde è riportato in 10 delle 14 risposte"))

    def test_the_count_the_chart_draws_passes(self):
        self.assertEqual(self.problems("Il numero verde è riportato in 8 delle 14 risposte"), "")
        self.assertEqual(self.problems("Il numero verde manca in 6 delle 14 risposte"), "")

    def test_a_count_of_another_base_is_left_to_the_other_rules(self):
        self.assertEqual(self.problems("Il numero verde è riportato in 20 delle 30 risposte"), "")

    def test_a_count_beside_a_competitor_is_left_to_its_own_rule(self):
        self.assertEqual(self.problems("Avoria compare in 3 delle 14 risposte"), "")

    def test_the_found_slide_is_held_to_the_block_figure(self):
        self.assertIn("14 of 14", self.problems("Il numero verde è riportato in 8 delle 14 risposte",
                                                found="Il numero verde è riportato in tutte le 14 risposte."))


class LivePageTest(unittest.TestCase):
    """A rate in a tooltip and an answer in a closed FAQ were written as missing: a web tool had not seen them."""

    html = ('<html><head><title>Prezzi da 39 euro</title><meta name="description" content="Il conto per le PMI">'
            '<style>p{color:red}</style><script>var hidden = 1;</script></head><body>'
            '<p>Tre utenti <span data-tooltip="Utente in più: 9 euro" title="Aiuto">inclusi</span></p>'
            '<details><summary>I miei soldi sono al sicuro?</summary><div>I fondi sono separati.</div></details>'
            '<p>Tre utenti <span data-tooltip="Utente in più: 9 euro" title="Aiuto">inclusi</span></p></body></html>')

    def test_the_text_holds_what_a_reader_finds_by_hovering_or_opening(self):
        text = livepage.text_of(self.html)
        self.assertIn("Title: Prezzi da 39 euro", text)
        self.assertIn("Description: Il conto per le PMI", text)
        self.assertIn("[Utente in più: 9 euro]", text)
        self.assertIn("I fondi sono separati.", text)

    def test_scripts_stay_out_and_a_line_comes_once(self):
        text = livepage.text_of(self.html)
        self.assertNotIn("hidden", text)
        self.assertNotIn("color:red", text)
        self.assertEqual(text.count("Tre utenti"), 1)

    def opener(self, html, seen=None):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.headers.get_content_charset.return_value = "utf-8"
        response.read.return_value = html.encode("utf-8")

        def open_url(request, timeout):
            (seen if seen is not None else []).append(request.full_url)
            return response
        return open_url

    def test_an_address_with_no_scheme_is_read_over_https(self):
        seen = []
        html = self.html.replace("</body>", "<p>" + "parola " * 50 + "</p></body>")
        self.assertIn("I fondi sono separati.", livepage.read("avenello.example/prezzi", self.opener(html, seen)))
        self.assertEqual(seen, ["https://avenello.example/prezzi"])

    def test_only_web_addresses_are_read(self):
        with self.assertRaisesRegex(deck.Refused, "not a web address"):
            livepage.read("file:///etc/passwd", self.opener(self.html))

    def test_a_page_built_by_scripts_says_to_use_the_web_tool(self):
        with self.assertRaisesRegex(deck.Refused, "web tool"):
            livepage.read("https://a.example", self.opener("<html><body><div id=app></div></body></html>"))

    def test_a_refused_page_says_to_use_the_web_tool(self):
        def refuse(request, timeout):
            raise OSError("403")
        with self.assertRaisesRegex(deck.Refused, "web tool"):
            livepage.read("https://a.example", refuse)


class BothFiguresTest(DeckCase, unittest.TestCase):
    """An answer giving today's price beside the old one reads as today's on the chart: the text must be able to say so."""

    def test_the_figures_file_says_how_many_give_both(self):
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"of which beside an old figure 0 su \d")


class OneAnswerActionTest(unittest.TestCase):
    """An action built on one answer of 127 sent a client to fix what a single old contract said."""

    def test_a_reason_resting_on_one_answer_is_refused(self):
        for why in ("Sette risposte su nove sono favorevoli, ma una descrive una penale.",
                    "Una risposta avverte di una penale.", "One answer says the fee is wrong."):
            self.assertTrue(deck._one_answer({"actions": [{"why": why}]}), why)

    def test_another_organisation_is_not_one_answer(self):
        for why in ("Le risposte confondono Avenello con un'altra azienda.", "Su avenello.it scrive un’altra organizzazione."):
            self.assertEqual(deck._one_answer({"actions": [{"why": why}]}), [], why)
        for why in ("Una risposta su tre è sfavorevole e un'altra risposta riporta il prezzo vecchio.",
                    "Un'altra descrive una penale."):
            self.assertTrue(deck._one_answer({"actions": [{"why": why}]}), why)

    def test_a_ratio_and_a_count_pass(self):
        for why in ("Una risposta su due riporta il prezzo vecchio.", "Sei risposte su nove rimandano alla call.",
                    "One answer in three gives the old price."):
            self.assertEqual(deck._one_answer({"actions": [{"why": why}]}), [], why)


class AskerJudgesTest(DeckCase, unittest.TestCase):
    """The assistants answer and the people ask: a judgement belongs to the answers."""

    def test_a_judgement_given_to_who_asks_is_refused(self):
        doc = self.filled(found={**self.filled()["found"], "title": "Il giudizio di chi chiede di Avenello è positivo"})
        self.assertIn("gives the judgement to who asks", self.problems(doc))

    def test_the_plain_sentence_passes(self):
        self.assertNotIn("gives the judgement to who asks", self.problems(self.filled()))


class TopSiteTest(unittest.TestCase):
    """A reader sees the most cited site with no action and asks why."""

    m = {"blocks": {"reach": {"sources": {"third_domains": [{"domain": "it.guida.example", "answers": 27}]}}}}

    def doc(self, read, what="Pubblicare il prezzo su avenello.example"):
        return {"actions": [{"what": what}], "sources": {"read": read}}

    def test_a_top_site_with_no_action_and_no_reason_is_refused(self):
        self.assertTrue(deck._top_site(self.doc("Guida è il sito più citato."), self.m))

    def test_a_reason_in_the_read_passes(self):
        doc = self.doc("Guida è il sito più citato, senza azione perché parla bene di Avenello.")
        self.assertEqual(deck._top_site(doc, self.m), [])

    def test_an_action_on_that_site_passes(self):
        doc = self.doc("Una frase sulle fonti.", "Chiedere a guida.example di aggiungere il corso")
        self.assertEqual(deck._top_site(doc, self.m), [])


class ThirdPageTest(DeckCase, unittest.TestCase):
    """A writer reading only the answers asked a shop to list a rival: a site an action asks has been opened."""

    def doc(self, pages=None, what="Chiedere a prezzi.example di aggiungere Avenello alla sua guida", kind="not_named"):
        doc = self.filled()
        doc["actions"].append({**doc["actions"][0], "class": kind, "what": what, "block": "description"})
        doc["blocks"]["description"][0]["action"] = 2
        if pages is not None:
            doc["actions"][1]["pages"] = pages
        return doc

    def test_an_action_on_a_site_with_no_record_of_its_page_is_refused(self):
        self.assertIn("says nothing of its page", self.problems(self.doc()))

    def test_a_page_the_answers_do_not_cite_is_refused(self):
        doc = self.doc([{"url": "prezzi.example/altra", "shows": ["Avoria", "Oatwell"]}])
        self.assertIn("not a page the answers cite", self.problems(doc))

    def test_a_page_listing_others_passes(self):
        doc = self.doc([{"url": "https://prezzi.example/avena", "shows": ["Avoria", "Oatwell"]}])
        self.assertNotIn("page of prezzi.example", self.problems(doc))
        self.assertNotIn("not a page the answers cite", self.problems(doc))

    def test_a_shop_of_its_own_goods_is_refused(self):
        doc = self.doc([{"url": "prezzi.example/avena", "shows": ["Prezzi Base", "Prezzi Plus"]}])
        self.assertIn("lists fewer than two others", self.problems(doc))

    def test_a_page_that_lists_the_subject_needs_no_adding(self):
        doc = self.doc([{"url": "prezzi.example/avena", "shows": ["Avoria", "Oatwell", "Avenello"]}])
        self.assertIn("its page lists it", self.problems(doc))

    def test_a_page_read_settles_whether_the_subject_is_listed(self):
        m = {"blocks": {"description": {"sources": {"third_all": {"prezzi.example": 3}}}}}
        doc = {"actions": [{"what": "Chiedere a prezzi.example di inserire la scheda di Avenello"}]}
        self.assertTrue(deck._listed_already(doc, m))
        doc["actions"][0]["pages"] = [{"url": "prezzi.example/avena", "shows": ["Avoria", "Oatwell"]}]
        self.assertEqual(deck._listed_already(doc, m), [])

    def test_a_page_not_read_is_one_the_reader_checks(self):
        doc = self.doc([{"url": "prezzi.example/avena", "shows": []}])
        self.assertIn("its page was not read", self.problems(doc))
        doc = self.doc([{"url": "prezzi.example/avena", "shows": []}], what="Controllare su prezzi.example se Avenello compare")
        self.assertNotIn("its page was not read", self.problems(doc))

    def test_a_wrong_figure_needs_one_term(self):
        doc = self.doc([{"url": "prezzi.example/avena", "shows": ["1,90 €"]}], what="Chiedere a prezzi.example di correggere il prezzo",
                       kind="wrong_fact")
        self.assertNotIn("lists fewer", self.problems(doc))

    def test_a_figure_on_the_subjects_own_page_needs_the_page_read_too(self):
        doc = self.doc(what="Sostituire 1,90 € con 2,10 € su avenello.example", kind="wrong_fact")
        self.assertIn("no page was read to show", self.problems(doc))
        doc = self.doc([{"url": "avenello.example/prezzi", "shows": ["1,90 €"]}], what="Sostituire 1,90 € con 2,10 € su avenello.example",
                       kind="wrong_fact")
        self.assertNotIn("no page was read to show", self.problems(doc))

    def test_a_correction_resting_on_unread_pages_alone_is_refused(self):
        doc = self.doc([{"url": "prezzi.example/avena", "shows": []}], what="Controllare il prezzo su prezzi.example", kind="wrong_fact")
        self.assertIn("no page was read to show", self.problems(doc))

    def test_the_slide_shows_what_the_page_lists(self):
        doc = self.doc([{"url": "prezzi.example/avena", "shows": ["Avoria", "Oatwell"]}])
        self.save_doc(doc)
        self.assertIn("prezzi.example/avena elenca Avoria, Oatwell, non Avenello", deck.page_of(self.study, DATE)[0])

    def test_the_slide_shows_every_wrong_figure_of_a_page(self):
        doc = self.doc([{"url": "prezzi.example/avena", "shows": ["1,90 €", "2,40 €"]}], what="Chiedere a prezzi.example di correggere il prezzo",
                       kind="wrong_fact")
        self.save_doc(doc)
        self.assertIn("prezzi.example/avena riporta «1,90\u00a0€», «2,40\u00a0€».", deck.page_of(self.study, DATE)[0])

    def test_the_slide_shows_the_wrong_figure(self):
        doc = self.doc([{"url": "prezzi.example/avena", "shows": ["1,90 €"]}], what="Chiedere a prezzi.example di correggere il prezzo",
                       kind="wrong_fact")
        self.save_doc(doc)
        self.assertIn("prezzi.example/avena riporta «1,90\u00a0€».", deck.page_of(self.study, DATE)[0])


class FavourableBaseTest(DeckCase, unittest.TestCase):
    """The favourable figure counts the answers to questions on the subject, and other answers name it too."""

    def test_favourable_answers_are_not_those_naming_the_subject(self):
        doc = self.filled()
        doc["found"]["answers"]["description"] = "1 su 2 risposte che nominano Avenello sono favorevoli."
        self.assertIn("favourable answers name the subject", self.problems(doc))

    def test_the_answers_to_questions_on_the_subject_pass(self):
        doc = self.filled()
        doc["found"]["answers"]["description"] = "Quando la domanda nomina Avenello, 1 risposta su 2 è favorevole."
        self.assertNotIn("favourable answers name the subject", self.problems(doc))


class UnitsTest(unittest.TestCase):

    def test_a_figure_keeps_its_unit_on_the_line(self):
        self.assertEqual(deck._tight_units("i valori «69 €» e 12 %"), "i valori «69\u00a0€» e 12\u00a0%")


class WhoActsTest(DeckCase, unittest.TestCase):
    """The reader controls the subject's pages and does the checking: a third party only adds or corrects."""

    def test_a_deck_whose_actions_all_ask_third_parties_is_refused(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Chiedere a prezzi.example di riportare il prezzo"
        self.assertIn("every action asks a third party", self.problems(doc))

    def test_an_action_on_the_subjects_pages_passes(self):
        self.assertNotIn("every action asks a third party", self.problems(self.filled()))

    def test_a_third_party_is_never_asked_to_check(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Chiedere a prezzi.example di verificare se Avenello compare"
        self.assertIn("the reader does the checking", self.problems(doc))
        doc["actions"][0]["what"] = "Chiedere a prezzi.example e altro.example se la guida cita Avenello"
        self.assertIn("the reader does the checking", self.problems(doc))
        doc["actions"][0]["what"] = "Verificare se prezzi.example riporta Avenello e chiedere di aggiungerla"
        self.assertNotIn("the reader does the checking", self.problems(doc))

    def test_a_question_of_the_opening_holds_no_count(self):
        doc = self.filled()
        doc["opening"]["questions"]["facts"] = "Le 18 risposte sul prezzo cosa riportano?"
        self.assertIn("holds a count", self.problems(doc))


class SameRowsTest(unittest.TestCase):
    """A second slide of the rows of another tells the reader nothing new."""

    block = {"questions": [], "rows": [{"label": "A", "dimension": "A"}, {"label": "B", "dimension": "B"},
                                       {"label": "C", "dimension": "C"}, {"label": "D", "dimension": "D"}]}

    def test_a_slide_of_rows_another_draws_is_refused(self):
        doc = {"blocks": {"description": [{"dimensions": []}, {"dimensions": ["A", "B", "C"]}]}}
        self.assertTrue(deck._same_rows(doc, {"blocks": {"description": self.block}}))

    def test_slides_of_different_rows_pass(self):
        doc = {"blocks": {"description": [{"dimensions": ["A", "B", "C"]}, {"dimensions": ["D", "B", "C"]}]}}
        self.assertEqual(deck._same_rows(doc, {"blocks": {"description": self.block}}), [])


class WhyThatSiteTest(DeckCase, unittest.TestCase):
    """A reader told to ask a site asks why that one: the code says how many answers cite it."""

    def doc(self):
        doc = self.filled()
        doc["actions"][0].update({"what": "Chiedere a prezzi.example di riportare il prezzo", "block": "description"})
        doc["blocks"]["reach"][0]["action"] = None
        doc["blocks"]["description"][0]["action"] = 1
        return doc

    def test_the_answers_citing_a_third_party_are_counted_on_the_action(self):
        doc = self.doc()
        m = deck.build_model(*self.model_args(doc))
        line = deck._why_site(doc["actions"][0], 1, doc, m, deck.DECK["it"])
        self.assertIn("prezzi.example: citato da 1 delle", line)

    def test_a_site_count_takes_the_base_of_the_reason_beside_it(self):
        doc = self.doc()
        doc["actions"][0]["why"] = "prezzi.example è citato da 1 delle 2 risposte sul prezzo."
        m = deck.build_model(*self.model_args(doc))
        line = deck._why_site(doc["actions"][0], 1, doc, m, deck.DECK["it"])
        self.assertIn("prezzi.example: citato da 1 delle 2 risposte su «Quanto costa un litro di latte d'avena Avenello?».", line)
        en = deck._why_site(doc["actions"][0], 1, doc, m, deck.DECK["en"])
        self.assertIn("prezzi.example: cited by 1 of the 2 answers on «Quanto costa un litro di latte d'avena Avenello?».", en)

    def test_a_reason_with_another_base_keeps_the_slide_count(self):
        doc = self.doc()
        doc["actions"][0]["why"] = "prezzi.example è citato da 1 delle 4 risposte."
        m = deck.build_model(*self.model_args(doc))
        self.assertIn("prezzi.example: citato da 1 delle 4 risposte alle domande di questa slide.",
                      deck._why_site(doc["actions"][0], 1, doc, m, deck.DECK["it"]))

    def test_the_slide_names_the_page_most_cited(self):
        doc = self.doc()
        m = deck.build_model(*self.model_args(doc))
        line = deck._why_site(doc["actions"][0], 1, doc, m, deck.DECK["it"], page=True)
        self.assertIn("Pagina più citata: prezzi.example/avena (1).", line)
        self.assertNotIn("Pagina più citata", deck._why_site(doc["actions"][0], 1, doc, m, deck.DECK["it"]))

    def test_the_line_says_which_questions_it_counts(self):
        doc = self.doc()
        m = deck.build_model(*self.model_args(doc))
        self.assertIn("alle domande della slide 7", deck._why_site(doc["actions"][0], 1, doc, m, deck.DECK["it"], slide=7))
        self.assertIn("alle domande di questa slide", deck._why_site(doc["actions"][0], 1, doc, m, deck.DECK["it"]))

    def test_the_figures_file_lists_the_pages_of_other_sites(self):
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertIn("other pages cited most: prezzi.example/avena", text)

    def test_the_subjects_own_site_needs_no_such_line(self):
        doc = self.filled()
        m = deck.build_model(*self.model_args(doc))
        self.assertEqual(deck._why_site(doc["actions"][0], 1, doc, m, deck.DECK["it"]), "")

    def test_the_actions_slide_shows_the_line(self):
        self.save_doc(self.doc())
        self.assertIn("prezzi.example: citato da", deck.page_of(self.study, DATE)[0])


class WorstShownTest(DeckCase, unittest.TestCase):
    """A reader told of unfavourable answers looks for one."""

    def test_unfavourable_answers_with_no_excerpt_of_one_are_refused(self):
        doc = self.filled()
        doc["blocks"]["description"][0]["excerpts"].pop()
        self.assertIn("no excerpt shows one", self.problems(doc))

    def test_an_unfavourable_excerpt_passes(self):
        self.assertNotIn("no excerpt shows one", self.problems(self.filled()))


class WeakSiteTest(unittest.TestCase):
    """An action on a site few answers read earns "why that one?"."""

    def model(self, citing, total):
        answers = [{"answer": "x", "sources": [{"domain": "guida.example", "url": "https://guida.example/p"}] if i < citing else []}
                   for i in range(total)]
        block = {"questions": [{"key": "q", "label": "Q", "dimension": "D"}], "rows": []}
        return {"blocks": {"reach": block}, "answers_of": {"q": answers}, "author": lambda d: "third"}

    def doc(self):
        return {"actions": [{"what": "Chiedere a guida.example di aggiungere il corso", "block": "reach"}],
                "blocks": {"reach": [{"action": 1, "questions": ["q"], "dimensions": [], "rows": "dimensions"}]}}

    def test_a_site_few_answers_cite_is_refused(self):
        with mock.patch.object(deck, "MIN_ANSWERS", 1):
            self.assertTrue(deck._weak_sites(self.doc(), self.model(3, 63)))

    def test_three_answers_are_too_few_whatever_the_share(self):
        with mock.patch.object(deck, "MIN_ANSWERS", 1):
            self.assertTrue(deck._weak_sites(self.doc(), self.model(3, 18)))

    def test_a_site_many_answers_cite_passes(self):
        with mock.patch.object(deck, "MIN_ANSWERS", 1):
            self.assertEqual(deck._weak_sites(self.doc(), self.model(25, 90)), [])


class AssertedTest(DeckCase, unittest.TestCase):
    """The content of a page is the subject's: an action never dictates a fact the study does not record."""

    def test_a_fact_the_study_does_not_record_is_refused(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Completare la risposta su avenello.example: i fondi sono detenuti altrove"
        self.assertIn("the study does not record", self.problems(doc))
        doc["actions"][0]["what"] = "Scrivere su avenello.example, dicendo che i fondi sono al sicuro"
        self.assertIn("the study does not record", self.problems(doc))

    def test_what_the_page_must_answer_passes(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Completare la risposta su avenello.example dicendo cosa succede ai fondi"
        self.assertNotIn("the study does not record", self.problems(doc))

    def test_an_identity_or_a_recorded_fact_can_be_stated(self):
        doc = self.filled()
        doc["actions"][0].update({"class": "confused", "what": "Chiarire su avenello.example: Avenello è un'azienda italiana"})
        self.assertNotIn("the study does not record", self.problems(doc))


class ReactionTest(DeckCase, unittest.TestCase):
    """The answers show what assistants say, never what people think of them."""

    def test_a_reaction_in_a_title_is_refused(self):
        doc = self.filled()
        doc["found"]["title"] = "Avenello convince chi la cerca per nome"
        self.assertIn("what people think", self.problems(doc))


class LeftOutTest(DeckCase, unittest.TestCase):
    """"Left out" says nothing named it: it holds only beside the count that says so."""

    def test_left_out_beside_answers_that_name_it_is_refused(self):
        doc = self.filled()
        doc["found"]["title"] = "Avenello resta fuori dalle risposte di chi cerca una bevanda"
        self.assertIn("says all or nothing", self.problems(doc))


class VoicesTest(unittest.TestCase):
    """Every excerpt from one assistant reads as a study of that assistant."""

    def model(self, assistants):
        return {"blocks": {"description": {"questions": [{"project": "P"}]}, "reach": {"questions": [{"project": "Q"}]}},
                "method": [{"name": "P", "assistants": assistants}, {"name": "Q", "assistants": ["One"]}]}

    def doc(self, *voices):
        return {"blocks": {"description": [{"excerpts": [{"assistant": v}]} for v in voices]}}

    def test_one_assistant_across_a_block_many_answer_is_refused(self):
        self.assertTrue(deck._voices(self.doc("One", "One"), self.model(["One", "Two"])))

    def test_two_assistants_pass(self):
        self.assertEqual(deck._voices(self.doc("One", "Two"), self.model(["One", "Two"])), [])

    def test_a_block_only_one_assistant_answers_has_no_choice(self):
        doc = {"blocks": {"reach": [{"excerpts": [{"assistant": "One"}]}, {"excerpts": [{"assistant": "One"}]}]}}
        self.assertEqual(deck._voices(doc, self.model(["One", "Two"])), [])

    def test_a_single_excerpt_has_nothing_to_vary(self):
        self.assertEqual(deck._voices(self.doc("One"), self.model(["One", "Two"])), [])


class WholeBlockTest(DeckCase, unittest.TestCase):
    """A block's figure over a chart of part of the block is a figure the reader cannot find."""

    def test_the_block_figure_is_drawn_only_on_a_slide_of_the_whole_block(self):
        m = deck.build_model(*self.model_args({}))
        block = m["blocks"]["description"]
        figure = (block["figures"][0]["a"], block["figures"][0]["b"])
        whole = {"dimensions": [], "questions": [], "rows": "dimensions"}
        self.assertIn(figure, deck._drawn("description", block, whole))
        part = {"dimensions": ["Lavoro"], "questions": [], "rows": "dimensions"}
        self.assertNotIn(figure, deck._drawn("description", block, part))


class ComparisonTest(DeckCase, unittest.TestCase):
    """Presence read alone misleads: the same answers name the competitors."""

    def model(self, **doc):
        return deck.build_model(*self.model_args(doc))

    def test_the_figure_carries_the_competitors_and_the_position(self):
        figure = self.model()["blocks"]["reach"]["figures"][0]
        self.assertEqual((figure["a"], figure["b"], figure["rivals"], figure["rank"]), (0, 2, [("Avoria", 1)], 2))

    def test_the_figures_file_gives_the_comparison(self):
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        text = (self.study / "history" / "deck" / f"{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertIn("Compared on the same answers", text)
        self.assertIn("Avoria 1 su 2", text)
        self.assertIn("Position: 2 su", text)

    def test_a_competitor_named_by_the_question_does_not_count_for_it(self):
        class Named:
            def foils_named(self, text):
                return ["Avoria"] if "Avoria" in text else []
        items = [({"text": "Cerco un'alternativa a Avoria"}, {"total": {"foils": {"Avoria": 6, "Oatly": 2}}}),
                 ({"text": "Qual è la migliore?"}, {"total": {"foils": {"Avoria": 1}}})]
        counts, left_out = deck._rivals(items, Named())
        self.assertEqual(dict(counts), {"Oatly": 2, "Avoria": 1})
        self.assertTrue(left_out)

    def test_the_found_slide_draws_the_subject_beside_the_competitors(self):
        self.save_doc(self.filled())
        text = deck.page_of(self.study, DATE)[0]
        versus = text[text.index('class="versus"'):]
        self.assertIn("Avoria", versus)
        self.assertIn('<div class="me">Avenello</div>', versus)

    def test_the_answer_on_presence_must_name_a_competitor(self):
        doc = self.filled()
        doc["found"]["answers"]["reach"] = "Avenello compare in 0 risposte su 2."
        self.assertIn("gives no comparison", self.problems(doc))

    def test_a_title_citing_presence_must_name_a_competitor(self):
        doc = self.filled()
        doc["found"]["title"] = "Avenello è nominata in 0 risposte su 2"
        self.assertIn("no comparison", self.problems(doc))

    def test_a_subject_among_the_first_is_not_played_down(self):
        doc = self.filled()
        doc["found"]["answers"]["reach"] = "Avenello compare solo in 0 risposte su 2, Avoria in 1 risposta su 2."
        self.assertIn("say where it stands", self.problems(doc))

    def test_a_subject_among_the_first_is_not_set_against_what_holds(self):
        doc = self.filled()
        doc["found"]["title"] = "Avenello piace, ma è nominata in 0 risposte su 2 da Avoria"
        self.assertIn("no weakness", self.problems(doc))


class FactsRowsTest(unittest.TestCase):

    def question(self, key, fact, current):
        return {"key": key, "text": f"Domanda {key}?", "facts": [{"fact": fact, "source": "https://www.acme.example/prezzi/",
                                                                 "date": "2026-10-01", "current": current, "outdated": ["5 €"]}]}

    def row(self, key, fact, current, given, carried):
        scope = {"facts": {"total": {"given": given, "current_only": carried, "both": 0, "outdated_only": given - carried,
                                     "stating": given}},
                 "total": {"judged": given, "bands": {"1-2": 0, "3": 0, "4-5": given}}}
        return deck._fact_row("P", "Prezzi", self.question(key, fact, current), scope)

    def test_a_fact_shows_its_terms_once(self):
        self.assertEqual(deck._fact_name(self.question("a", "Prezzo di partenza", ["69 €", "69€", "69 euro", "129 €"])),
                         "Prezzo di partenza: 69 €, 129 €")

    def test_a_term_the_fact_already_states_is_not_repeated(self):
        self.assertEqual(deck._fact_name(self.question("a", "Il piano costa £27 al mese.", ["£27"])), "Il piano costa £27 al mese")

    def test_questions_bringing_out_one_fact_make_one_row(self):
        rows = deck._by_fact([self.row("a", "Prezzo", ["7 €"], 10, 4), self.row("b", "Prezzo", ["7 €"], 10, 6)], True)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["label"], rows[0]["current"], rows[0]["given"]), ("Prezzo: 7 €", 10, 20))

    def test_a_row_knows_which_pages_the_old_and_the_new_term_come_from(self):
        question = self.question("a", "Prezzo", ["7 €"])
        answers = [{"answer": "Costa 5 €", "sources": [{"url": "https://www.vecchio.example/prezzi?x=1", "domain": "vecchio.example"}]},
                   {"answer": "Costa 7 €", "sources": [{"url": "https://nuovo.example/", "domain": "nuovo.example"}]},
                   {"answer": "Non lo so", "sources": [{"url": "https://muto.example/", "domain": "muto.example"}]},
                   {"answer": None, "sources": []}]
        sites = deck._sites_by_term(question, answers)
        self.assertEqual(sites["old"], {"vecchio.example/prezzi": 1})
        self.assertEqual(sites["new"], {"nuovo.example": 1})

    def telling(self, old, new, outdated=100, current=50):
        row = {"outdated": outdated, "current": current, "sites": {"old": Counter(old), "new": Counter(new)}}
        return deck._telling(row, lambda d: {"own.example": "owned", "rival.example": "foil"}.get(d, "third"))

    def test_a_page_cited_alike_by_both_kinds_of_answers_says_nothing(self):
        found = self.telling({"both.example/p": 60}, {"both.example/p": 30})
        self.assertEqual(found, {"owned": [], "third": [], "foil": []})

    def test_a_page_the_old_answers_cite_and_todays_do_not_tells(self):
        found = self.telling({"third.example/p": 24, "rival.example/blog": 53, "own.example/old": 6}, {"third.example/p": 1})
        self.assertEqual(found, {"owned": [("own.example/old", 6)], "third": [("third.example/p", 24)],
                                 "foil": [("rival.example/blog", 53)]})

    def test_a_page_a_couple_of_answers_cite_tells_nothing(self):
        self.assertEqual(self.telling({"third.example/p": 2}, {})["third"], [])

    def test_the_facts_chart_shows_those_pages_by_who_wrote_them(self):
        t = deck.DECK["it"]
        row = {"project": "P", "label": "Prezzo", "given": 9, "current": 2, "outdated": 5, "silent": 2, "judged": 9,
               "bands": {"4-5": 2, "3": 7, "1-2": 0},
               "telling": {"owned": [], "third": [("vecchio.example/p", 4)], "foil": [("rivale.example/blog", 3)]}}
        page = deck._rows("facts", [row], t, "it", {"subject": "Avenello", "fidelity": False}, False, 0)
        self.assertIn("Pagine che le 5 risposte col solo dato vecchio citano e quelle col dato di oggi quasi mai", page)
        self.assertIn("Di terzi: vecchio.example/p (4). Dei concorrenti: rivale.example/blog (3).", page)

    def test_no_page_that_tells_draws_no_note(self):
        row = {"project": "P", "label": "Prezzo", "given": 9, "current": 2, "outdated": 5, "silent": 2, "judged": 9,
               "bands": {"4-5": 2, "3": 7, "1-2": 0}, "telling": {"owned": [], "third": [], "foil": []}}
        page = deck._rows("facts", [row], deck.DECK["it"], "it", {"subject": "Avenello", "fidelity": False}, False, 0)
        self.assertNotIn("Pagine citate", page)

    def test_the_row_says_how_many_questions_bring_it_out(self):
        rows = deck._by_fact([self.row("a", "Prezzo", ["7 €"], 10, 4), self.row("b", "Prezzo", ["7 €"], 10, 6)], True)
        self.assertIn("Da 2 domande", deck._fact_label(rows[0], deck.DECK["it"], "it"))

    def test_the_row_says_where_the_fact_comes_from(self):
        row = deck._by_fact([self.row("a", "Prezzo", ["7 €"], 10, 4)], True)[0]
        self.assertIn("Fonte: acme.example/prezzi, 1° ottobre 2026", deck._fact_label(row, deck.DECK["it"], "it"))


class ReaderWordsTest(DeckCase, unittest.TestCase):
    """The reader has the words of the market, not those of the study."""

    def test_the_words_of_the_study_are_refused(self):
        for word in ("punteggio", "blocco", "dimensione", "domande di categoria", "dato corrente", "score", "dimension"):
            doc = self.filled()
            doc["blocks"]["facts"][0]["read"] = f"Una frase con {word} dentro."
            self.assertIn("word of the study", self.problems(doc), word)

    def test_the_chart_word_for_neutral_answers_is_kept(self):
        doc = self.filled()
        doc["blocks"]["description"][0]["read"] = "Sono 3 neutrali e 3 sfavorevoli."
        self.assertIn("the chart says neutre", self.problems(doc))

    def test_a_topic_is_not_favourable_the_answers_are(self):
        doc = self.filled()
        doc["blocks"]["description"][0]["read"] = "The app is favourable in 35 of 75 answers."
        self.assertIn("answers on the app are favourable", self.problems(doc))

    def test_the_deck_is_written_about_the_subject(self):
        for text in ("Chi cerca senza nominarci trova Avoria.", "Le risposte citano le nostre pagine.", "Do buyers find us?"):
            doc = self.filled()
            doc["blocks"]["reach"][0]["read"] = text
            self.assertIn("name the subject", self.problems(doc), text)
        doc = self.filled()
        doc["blocks"]["reach"][0]["read"] = "Le risposte citano molti siti US."
        self.assertNotIn("name the subject", self.problems(doc))

    def test_a_quoted_label_is_not_the_writer_speaking(self):
        for text in ("Le risposte rimandano alla pagina «Lavora con noi» di Avenello.",
                     "Le risposte rimandano alla pagina “Chi siamo e i nostri valori” di Avenello.",
                     'The answers point to the "About us" page of Avenello.'):
            doc = self.filled()
            doc["blocks"]["reach"][0]["read"] = text
            self.assertNotIn("name the subject", self.problems(doc), text)

    def test_a_listing_on_a_site_already_cited_on_the_subject_is_refused(self):
        m = {"blocks": {"description": {"sources": {"third_all": {"capterra.com": 3}}}}}
        doc = {"actions": [{"what": "Chiedere la scheda a capterra.com"}]}
        self.assertIn("already cite", deck._listed_already(doc, m)[0])
        self.assertEqual(deck._listed_already({"actions": [{"what": "Completare la scheda su altro.example"}]}, m), [])
        self.assertEqual(deck._listed_already({"actions": [{"what": "Scrivere su capterra.com il prezzo di oggi"}]}, m), [])

    def test_an_action_says_what_to_write(self):
        doc = self.filled()
        doc["actions"][0]["what"] = "Rafforzare la pagina dei prezzi su avenello.example"
        self.assertIn("say what to write and on which page", self.problems(doc))

    def test_a_project_name_is_refused(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["read"] = "Nel progetto Mercato le risposte sono due."
        self.assertIn("names the project Mercato", self.problems(doc))

    def test_a_topic_is_not_the_subject_of_a_sentence(self):
        for text in ("Scelta la nomina in 0 risposte su 2.", "Lavoro è a 2 su 2."):
            doc = self.filled()
            doc["blocks"]["reach"][0]["read"] = text
            self.assertIn("subject of a sentence", self.problems(doc), text)

    def test_a_title_stringing_figures_is_refused(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["title"] = "Avenello in 0 risposte su 2, Avoria in 1 risposta su 2, e 2 risposte su 2 altrove"
        self.assertIn("at most 2", self.problems(doc))

    def test_a_figure_repeated_on_the_first_slides_is_refused(self):
        doc = self.filled()
        doc["actions_title"] = "La prima cosa da fare riguarda 0 risposte su 2"
        doc["actions"][0]["what"] = "Pubblicare una pagina su avenello.example per le 0 risposte su 2"
        self.assertIn("appears 4 times", self.problems(doc))


def fullest(doc):
    """Every text of the deck at the length its slide holds."""
    longest = "parola " * 22
    doc["found"] = {"title": ("parola " * 16).strip(), "answers": {b: longest.strip() for b in deck.BLOCKS}}
    doc["actions"] = [{"class": "named_with_warning", "what": ("parola " * 24).strip(),
                       "why": ("parola " * 24).strip() + " 2", "read_next": ("parola " * 9).strip() + " 2",
                       "block": "reach"}] * 5
    for slides in doc["blocks"].values():
        slides[0].update(title=("parola " * 16).strip(), read=("parola " * 29).strip())
    return doc


class OverflowTest(DeckCase, unittest.TestCase):
    """A slide running over its page was found only by pdf --deck, after check had passed."""

    def crowded(self):
        """The reach slide with its title and read at their limits, two excerpts of forty long words and its action."""
        doc = self.filled()
        excerpt = {"text": ("precipitevolissimevolmente " * 40).strip(), "question": PRICE_Q, "assistant": "Acme Chat"}
        doc["blocks"]["reach"][0].update(title=("parola " * 16).strip(), read=("parola " * 29).strip(),
                                         excerpts=[excerpt, {**excerpt, "assistant": "Orbit Reason"}])
        doc["actions"][0]["what"] = ("parola " * 24).strip()
        return doc

    def overflows(self, doc):
        return [p for p in self.problems(doc).splitlines() if "runs over its page" in p]

    def test_a_slide_running_over_its_page_is_refused_before_the_pdf(self):
        found = self.overflows(self.crowded())
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0].startswith("slide 5 runs over its page by about "), found[0])

    def test_the_refusal_names_the_texts_of_that_slide(self):
        found = self.overflows(self.crowded())[0]
        self.assertIn("title, read or excerpts of reach slide 1", found)
        self.assertIn("what of action 1", found)

    def test_the_fullest_texts_a_slide_holds_pass(self):
        # Five actions on one evidence slide fail check on their structure, which leaves the slides unmeasured there.
        doc = fullest(self.filled())
        folder, study, period, _ = self.model_args(doc)
        self.assertEqual(deck._overflowing(folder, study, period, doc, deck.build_model(folder, study, period, doc)), [])

    def test_the_print_runs_over_where_check_refuses(self):
        browser = report_pdf.sandboxed_browser()
        if not browser:
            self.skipTest("no browser prints with its sandbox on this machine")
        self.save_doc(self.crowded())
        # The slide is named from the pages' feet, read with pdftotext where it is installed.
        named = r" \(slide 5 runs over\)" if shutil.which("pdftotext") else ""
        with self.assertRaisesRegex(deck.Refused, r"11 pages for 10 slides" + named + ":"):
            deck.render(self.study, DATE, skip_check=True,
                        printer=lambda target, pdf, engines: report_pdf.print_pdf(target, pdf, [e for e in engines if e[0] == browser]))

    def test_pdf_deck_leaves_the_height_to_its_page_count(self):
        self.save_doc(self.filled())
        with mock.patch.object(deck.fit, "heights", lambda page, css: [900.0] * page.count("<section")):
            self.assertTrue(self.overflows(self.filled()))
            self.assertIn("10 slides", deck.render(self.study, DATE, printer=fake_pdf(10)))


class RenderTest(DeckCase, unittest.TestCase):

    def page(self, doc=None):
        self.save_doc(doc or self.filled())
        return deck.page_of(self.study, DATE)[0]

    def test_one_section_per_slide_in_the_reader_s_order(self):
        text = self.page()
        self.assertEqual(text.count('<section class="slide'), 10)
        kinds = re.findall(r'<section class="slide (\w+)', text)
        self.assertEqual(kinds, ["cover", "opening", "found", "actions", "reach", "description", "facts", "sources", "method",
                                 "questions"])

    def test_the_page_is_16_by_9_and_holds_no_script(self):
        text = self.page()
        self.assertIn("size: 13.333in 7.5in", text)
        self.assertNotIn("<script", text)

    def test_the_page_draws_the_figures_with_the_report_language(self):
        text = self.page()
        self.assertIn("0 su 2", text)
        self.assertIn("Avoria 1", text)
        self.assertIn('class="bar"', text)

    def test_a_slide_lists_the_third_parties_the_reader_can_ask(self):
        self.assertIn("prezzi.example (1)", self.page())
        self.assertIn("Altri siti più citati", self.page())

    def test_the_sources_slide_says_what_its_numbers_count(self):
        text = self.page()
        self.assertIn('<div class="kicker">Quante risposte citano ogni fonte</div>', text)
        self.assertNotIn("Dove leggono", text)

    def test_a_slide_on_one_or_two_dimensions_draws_their_questions(self):
        doc = self.filled()
        doc["blocks"]["reach"][0]["dimensions"] = ["Scelta"]
        self.assertIn(CHOICE_Q, self.page(doc))

    def test_a_slide_may_draw_the_questions_it_names(self):
        doc = self.filled()
        m = deck.build_model(*self.model_args(doc))
        doc["blocks"]["reach"][0]["questions"] = [m["blocks"]["reach"]["questions"][0]["key"]]
        self.assertIn(CHOICE_Q, self.page(doc).split('class="rows reach-rows')[1])

    def test_few_actions_are_set_larger(self):
        self.assertIn('<section class="slide actions few-actions"', self.page())

    def test_the_labels_are_in_the_report_s_language(self):
        text = self.page()
        self.assertIn("Cosa fare", text)
        self.assertNotIn("Figura", text)

    def test_evidence_slides_are_numbered_from_the_block(self):
        self.assertIn('<td class="num">5</td>', self.page())

    def test_the_facts_chart_shows_the_favourable_answers(self):
        self.save_doc(self.filled())
        chart = deck.page_of(self.study, DATE)[0].split('class="rows facts-rows')[1]
        row = deck.build_model(*self.model_args(self.filled()))["blocks"]["facts"]["rows"][0]
        self.assertIn('<div class="head">Risposte favorevoli</div>', chart)
        self.assertIn('<div class="head"><i class="low"></i>Solo un dato vecchio</div>', chart)
        self.assertIn(f'<div class="fig">{row["bands"]["4-5"]} su {row["judged"]}</div>', chart)

    def test_a_slide_shows_its_action_in_words(self):
        self.assertIn("Azione 1: Pubblicare una pagina di confronto", re.sub(r"<[^>]+>", "", self.page()))

    def test_the_method_slide_shows_answers_not_rounds(self):
        text = self.page()
        method = text[text.index('<section class="slide method'):text.index('<section class="slide questions')]
        self.assertIn("Progetto su Sentl", method)
        self.assertNotIn("ripetizion", method.lower())
        self.assertIn("Quali pagine citano gli assistenti?", method)

    def test_english_labels(self):
        study = self.read("study.json")
        study["report_language"] = "en"
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.assertIn("What to do", self.page())

    def test_a_deck_failing_check_is_not_rendered(self):
        self.save_doc(self.filled(actions=[]))
        proc = self.cli("pdf", "--study", self.study, "--deck", "--date", DATE, check=2)
        self.assertIn("check", proc.stderr)

    def test_a_browser_without_its_sandbox_stops_the_deck_with_exit_1(self):
        self.save_doc(self.filled())
        browsers = self.study.parent / "bin"
        browsers.mkdir()
        sandboxless(browsers, "chromium")
        with mock.patch.dict(os.environ, {"PATH": str(browsers)}):
            proc = self.cli("pdf", "--study", self.study, "--deck", "--date", DATE, check=1)
        self.assertIn("chromium cannot start its sandbox", proc.stderr)
        self.assertFalse((self.study / "reports" / f"{DATE}.deck.pdf").exists())

    def test_pages_that_are_not_the_slides_are_refused(self):
        self.save_doc(self.filled())
        with self.assertRaisesRegex(deck.Refused, "11 pages for 10 slides"):
            deck.render(self.study, DATE, printer=fake_pdf(11))

    def test_the_copy_to_send_has_a_descriptive_name(self):
        self.save_doc(self.filled())
        self.cli("check", "--study", self.study, self.path, check=0)
        message = deck.render(self.study, DATE, printer=fake_pdf(10))
        shared = list((self.study / "reports" / "share").glob("*.pdf"))
        self.assertEqual(len(shared), 1)
        self.assertIn("Avenello + Sentl.ai - monitoring deck", shared[0].name)
        self.assertIn(str(shared[0]), message)

    def test_the_fullest_slides_stay_on_one_page_each(self):
        browser = report_pdf.sandboxed_browser()
        if not browser:
            self.skipTest("no browser prints with its sandbox on this machine")
        self.save_doc(fullest(self.filled()))
        deck.render(self.study, DATE, skip_check=True,
                    printer=lambda target, pdf, engines: report_pdf.print_pdf(target, pdf, [e for e in engines if e[0] == browser]))
        self.assertTrue((self.study / "reports" / f"{DATE}.deck.pdf").exists())


if __name__ == "__main__":
    unittest.main()
