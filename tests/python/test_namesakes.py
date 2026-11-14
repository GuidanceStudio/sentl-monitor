"""Answers about a namesake: another organisation sharing the subject's name, recorded under subject.namesakes. The rule
that tells one apart, the counts the period keeps, the deck's part of the bar, the rubric sentence and the candidates
the brief proposes."""

import copy
import json
import unittest
from unittest import mock

from test_deck import DeckCase  # first: fixtures puts the scripts on the path
from design_study import clean_study
from fixtures import CHOICE_Q, GEM, GPT, HOME, NAMESAKE, WORK_Q, StudyCase, project, run
from test_insights_period import CURRENT, OCT, OUTDATED, InsightCase, rows
from test_setup import KEY, SetupCase, sentl_project

from sentlmon import deck, design, quick
from sentlmon.adopt import missing_answers
from sentlmon.common import domain_of
from sentlmon.i18n import DECK, QUICK
from sentlmon.period import Reader

DATE = "2026-10-31"
LISTED = "https://lavoro.example/azienda/avenello-arredi/recensioni"
OTHER = {"label": "Avenello Tessuti", "places": ["Montefiume"], "products": ["tende"]}


def subject(**changes):
    return {"subject": {"label": "Avenello", "aliases": ["Avenello", "Avenello Bevande"], "owned_domains": ["avenello.example"],
                        "places": list(HOME), "namesakes": [copy.deepcopy(NAMESAKE)], **changes}}


def sources(*urls):
    return [{"url": u, "title": None, "domain": domain_of(u)} for u in urls]


class RuleTest(unittest.TestCase):
    """An answer is about a namesake when its markers outweigh the subject's in the answer's text and the addresses it
    cites inline; on a tie, the pages it cites decide."""

    def about(self, answer, urls=(), study=None):
        return Reader(study or subject()).namesake(answer, sources(*urls))

    def test_an_answer_describing_the_namesake_by_its_town_and_products_is_about_it(self):
        self.assertEqual(self.about("Avenello è un'azienda di Borgoverde che produce divani e arredamento."), "Avenello Arredi")

    def test_an_answer_telling_the_namesake_apart_is_about_the_subject(self):
        text = ("Avenello Bevande produce a Valdoria la sua bevanda d'avena, venduta su avenello.example; non va confusa "
                "con l'azienda di divani di Borgoverde.")
        self.assertIsNone(self.about(text))

    def test_the_shared_name_alone_counts_for_neither(self):
        self.assertIsNone(self.about("Avenello è un buon marchio.", [LISTED]))

    def test_a_tie_goes_to_the_namesake_when_more_of_the_cited_pages_are_its_own(self):
        text = "Da Avenello i dipendenti di Borgoverde scrivono recensioni positive; la sede di Valdoria non ne ha."
        self.assertEqual(self.about(text, [LISTED, "https://avenelloarredi.example/chi-siamo"]), "Avenello Arredi")

    def test_a_tie_stays_with_the_subject_when_its_own_pages_are_as_many(self):
        text = "Da Avenello i dipendenti di Borgoverde scrivono recensioni positive; la sede di Valdoria non ne ha."
        self.assertIsNone(self.about(text, [LISTED, "https://avenello.example/lavora-con-noi"]))
        self.assertIsNone(self.about(text))

    def test_a_numbered_citation_counts_as_the_source_it_points_to(self):
        self.assertEqual(self.about("Avenello è un'ottima azienda [1].", ["https://www.avenelloarredi.example/azienda"]),
                         "Avenello Arredi")
        self.assertIsNone(self.about("Avenello è un'ottima azienda [2].", ["https://www.avenelloarredi.example/azienda",
                                                                           "https://avenello.example/chi-siamo"]))

    def test_a_link_to_the_namesake_s_site_or_listing_counts(self):
        self.assertEqual(self.about("[Avenello](https://avenelloarredi.example/x) ha buone recensioni."), "Avenello Arredi")
        self.assertEqual(self.about(f"Le recensioni sono buone ({LISTED})."), "Avenello Arredi")

    def test_a_distinctive_alias_counts_for_the_subject(self):
        self.assertIsNone(self.about("Avenello Bevande non produce divani."))
        self.assertEqual(self.about("Avenello non produce bevande ma divani a Borgoverde."), "Avenello Arredi")

    def test_the_namesake_with_the_most_markers_is_the_one(self):
        study = subject(namesakes=[copy.deepcopy(NAMESAKE), OTHER])
        self.assertEqual(self.about("Avenello vende tende a Montefiume e a Borgoverde, tende su misura.", study=study),
                         "Avenello Tessuti")

    def test_the_sentence_shown_is_the_one_marking_the_namesake_in_its_words_or_its_citations(self):
        reader = Reader(subject())
        text = "Avenello ha opinioni divise. Su un sito di lavoro il voto è 2 su 5 [2]. Altro."
        urls = sources("https://avenello.example/chi-siamo", LISTED)
        self.assertEqual(reader.namesake_sentence(text, "Avenello Arredi", urls), "Su un sito di lavoro il voto è 2 su 5 [2].")
        self.assertEqual(reader.namesake_sentence("Avenello ha sede a Valdoria. I divani sono buoni.", "Avenello Arredi"),
                         "I divani sono buoni.")
        self.assertEqual(reader.namesake_sentence("Avenello ha opinioni divise.", "Avenello Arredi"), "Avenello ha opinioni divise.")

    def test_a_study_without_namesakes_has_none(self):
        study = subject()
        del study["subject"]["namesakes"]
        self.assertIsNone(self.about("Avenello è un'azienda di Borgoverde che produce divani.", study=study))


class StudyFieldsTest(unittest.TestCase):

    def missing(self, **changes):
        study = {"subject": {"label": "Avenello", "aliases": ["Avenello"], **changes}}
        return [m for m in missing_answers(study) if m.startswith("subject.")]

    def test_well_formed_namesakes_and_places_pass(self):
        self.assertEqual(self.missing(namesakes=[NAMESAKE, OTHER], places=HOME), [])
        self.assertEqual(self.missing(), [])

    def test_each_malformed_field_is_named(self):
        self.assertEqual(self.missing(namesakes={"label": "x"}), ["subject.namesakes"])
        self.assertEqual(self.missing(namesakes=[{"places": ["Borgoverde"]}]), ["subject.namesakes[0].label"])
        self.assertEqual(self.missing(namesakes=[{"label": "Avenello Arredi"}]), ["subject.namesakes[0].markers"])
        self.assertEqual(self.missing(namesakes=[{"label": "Avenello Arredi", "products": ["divani", ""]}]),
                         ["subject.namesakes[0].products"])
        self.assertEqual(self.missing(namesakes=[NAMESAKE, dict(NAMESAKE)]), ["subject.namesakes[1].label"])
        self.assertEqual(self.missing(places="Valdoria"), ["subject.places"])

    def test_validate_refuses_a_malformed_namesake(self):
        study = clean_study()
        study["subject"]["namesakes"] = [{"label": "Avenello Furniture"}]
        problems, _ = design.problems_of(study, {GPT, GEM}, ({}, {}))
        self.assertIn("subject.namesakes[0].markers: a namesake needs at least one place, domain, product or listing",
                      problems)



class AdoptPromptTest(StudyCase, unittest.TestCase):

    def test_adopt_asks_for_namesakes_and_the_subject_s_places(self):
        proc = self.cli("adopt", "--study", self.study, "--project", self.save("p.json", project()),
                        "--run", self.save("r.json", run()), "--key", "brand", check=0)
        self.assertIn("subject.places", proc.stdout)
        self.assertIn("subject.namesakes", proc.stdout)
        self.assertIn("demand namesakes", proc.stdout)


def namesake_rows(work):
    return rows(price=(OUTDATED, CURRENT), choice=(("I divani di Avenello a Borgoverde.", 3, [LISTED]),
                                                   ("Dipende dai gusti.", 3, [])), work=work)


TELLS_APART = ("Avenello produce a Valdoria e vende su avenello.example; non è l'azienda di divani di Borgoverde. "
               "Si lavora bene a Valdoria.", 4, [])
DESCRIBES = ("Avenello è un'azienda di Borgoverde che produce divani; i dipendenti ne parlano bene.", 5, [LISTED])


class NamesakeCase(InsightCase):
    """The market project with the namesake recorded: in the first run the work question has an answer telling the
    namesake apart and one about the subject, in the second one telling it apart and one describing the namesake."""

    def setUp(self):
        super().setUp()
        self.record()
        self.ingest_market(9101, OCT[0], namesake_rows((TELLS_APART, ("Si lavora bene da Avenello.", 4, []))))
        self.ingest_market(9102, OCT[1], namesake_rows((TELLS_APART, DESCRIBES)))
        self.build(DATE)

    def record(self, namesakes=(NAMESAKE,)):
        study = self.read("study.json")
        study["subject"].update(places=list(HOME), namesakes=copy.deepcopy(list(namesakes)))
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")


class PeriodTest(NamesakeCase, unittest.TestCase):

    def test_the_answers_about_the_namesake_are_counted_per_question_dimension_project_and_model(self):
        work = self.question(DATE, "lavoro", WORK_Q)
        self.assertEqual(work["total"]["namesakes"],
                         {"given": 1, "judged": 1, "bands": {"1-2": 0, "3": 0, "4-5": 1}, "labels": {"Avenello Arredi": 1}})
        self.assertEqual(work["by_model"][GEM]["namesakes"]["judged"], 1)
        self.assertEqual(work["by_model"][GPT]["namesakes"]["judged"], 0)
        self.assertEqual(work["namesake_answers"], [{"run_id": 9102, "response_id": 910206, "namesake": "Avenello Arredi"}])
        period = self.period_file(DATE)
        block = period["projects"]["market"]
        self.assertEqual(block["dimensions"]["lavoro"]["total"]["namesakes"]["judged"], 1)
        self.assertEqual(block["total"]["namesakes"]["judged"], 1)
        self.assertEqual(period["namesakes"], [NAMESAKE])

    def test_the_mean_and_the_bands_still_count_every_answer(self):
        work = self.question(DATE, "lavoro", WORK_Q)["total"]
        self.assertEqual((work["judged"], work["bands"]["4-5"]), (4, 4))

    def test_a_question_naming_no_subject_has_no_answer_about_a_namesake(self):
        choice = self.question(DATE, "scelta", CHOICE_Q)
        self.assertEqual(choice["total"]["namesakes"]["judged"], 0)
        self.assertEqual(choice["namesake_answers"], [])

    def test_the_material_marks_each_answer_and_counts_them_per_question(self):
        material = self.material(DATE)
        self.assertIn("Namesakes recorded: Avenello Arredi", material)
        self.assertIn("answers about a namesake: 1 (Avenello Arredi 1)", material)
        self.assertIn("about a namesake: Avenello Arredi, sources:", material)
        self.assertEqual(material.count("about a namesake: Avenello Arredi, sources:"), 1)

    def test_a_study_without_namesakes_writes_no_namesake_field(self):
        self.record(())
        study = self.read("study.json")
        del study["subject"]["namesakes"]
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")
        self.build(DATE)
        text = (self.study / f"history/periods/{DATE}.json").read_text(encoding="utf-8")
        self.assertNotIn("namesake", text)
        self.assertNotIn("namesake", self.material(DATE))


class NamesakeDeckCase(NamesakeCase, DeckCase):

    def setUp(self):
        NamesakeCase.setUp(self)
        patcher = mock.patch.object(deck, "MIN_ANSWERS", 1)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.made = self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        self.path = self.study / "reports" / f"{DATE}.deck.json"

    def model(self, doc=None):
        return deck.build_model(*self.model_args(doc or {}))


class DeckTest(NamesakeDeckCase, unittest.TestCase):

    def test_the_rated_parts_count_the_subject_s_answers_and_the_namesake_s_have_their_own(self):
        m = self.model()
        row = next(r for r in m["blocks"]["description"]["rows"] if r["dimension"] == "Lavoro")
        self.assertEqual((row["judged"], row["bands"], row["namesake"]), (4, {"1-2": 0, "3": 0, "4-5": 3}, 1))
        figure = m["blocks"]["description"]["figures"][0]
        self.assertEqual((figure["a"], figure["b"]), (5, 8))
        self.assertEqual(figure["parts"], [(5, "good"), (0, "mid"), (2, "low"), (1, "namesake")])

    def test_the_card_draws_the_namesake_count_and_check_refuses_another(self):
        """The card's legend carries the namesake's part: the text under it says what lies behind it, not the count."""
        said = "Le favorevoli lodano il lavoro; 1 delle 8 descrive Avenello Arredi."
        doc = self.filled()
        doc["found"]["answers"]["description"] = said
        self.assertIn("found answer description says 1 of 8, which the card beside it draws", self.problems(doc))
        doc["found"]["answers"]["description"] = said.replace("1 delle 8", "4 delle 8")
        self.assertIn("found answer description says 4 of 8, and the chart beside it draws", self.problems(doc))

    def test_the_chart_and_the_card_draw_the_namesake_part_with_its_label(self):
        self.save_doc(self.filled())
        text = deck.page_of(self.study, DATE)[0]
        self.assertIn('class="seg namesake"', text)
        self.assertIn(f'{DECK["it"]["namesake_part"]}: 1', text)
        self.assertIn("Avenello Arredi", text)

    def test_an_excerpt_from_an_answer_about_the_namesake_is_marked_as_such(self):
        m = self.model()
        excerpt = {"text": "Avenello è un'azienda di Borgoverde che produce divani", "question": WORK_Q, "assistant": "Orbit Reason"}
        self.assertEqual(deck._rating(excerpt, m, "description"), "namesake")
        self.assertIn("namesake", DECK["it"]["rated"])

    def test_the_figures_file_counts_them_and_quotes_them(self):
        figures = (self.study / f"history/deck/{DATE}.figures.md").read_text(encoding="utf-8")
        self.assertIn("about a namesake 1 su 4", figures)
        self.assertIn("## Answers about a namesake", figures)
        self.assertIn("Avenello è un'azienda di Borgoverde che produce divani", figures)

    def test_a_cited_site_of_a_recorded_namesake_is_named_by_its_label(self):
        m = self.model()
        self.assertEqual(deck._namesake("avenelloarredi.example", m), "Avenello Arredi")
        self.assertIsNone(deck._namesake("guida.example", m))

    def test_the_quick_deck_draws_the_same_part(self):
        m = self.model()
        folder, _, study, period, _ = deck.load(self.study, DATE)
        row = next(r for p in quick._layout(m, study, period) for r in p["rows"] if r["key"] == "lavoro")
        html = quick._figures_html(row, m, DECK["it"], QUICK["it"])
        self.assertIn('class="seg namesake"', html)
        self.assertIn("1", html)
        self.assertIn(QUICK["it"]["bands_namesake"].format(n=1), html)


class RubricTest(SetupCase):

    def with_namesake(self):
        study = copy.deepcopy(self.design)
        study["subject"]["namesakes"] = [{"label": "Avenello Furniture", "products": ["sofas"]}]
        return study

    def test_a_question_on_the_subject_rates_an_answer_about_a_namesake_1(self):
        study = self.with_namesake()
        brand = next(q for d in study["projects"][0]["dimensions"] for q in d["questions"])
        category = next(q for d in study["projects"][1]["dimensions"] for q in d["questions"])
        self.assertTrue(design.compose_rubric(brand, study)["1"].endswith(
            "An answer that describes Avenello Furniture instead of Avenello also rates 1."))
        self.assertEqual(design.compose_rubric(category, study), category["rubric"])
        self.assertEqual(design.compose_rubric(brand, self.design), brand["rubric"])
        composed = design.compose_rubric(brand, study)
        self.assertEqual(design.compose_rubric({**brand, "rubric": composed}, study), composed)

    def test_setup_sends_the_composed_rubric_and_bind_accepts_it(self):
        saved = self.create_and_save()
        study = self.with_namesake()
        self.write_study(study)
        args = self.question_args(saved)
        sent = next(q for d in args["dimensions"] for q in d["questions"] if q["question"].startswith("Is Avenello oat milk bad"))
        self.assertIn("Avenello Furniture", sent["grading_rubric"]["1"])

        def saved_as_sent(project):
            for d in project["dimensions"]:
                for q in d["questions"]:
                    match = next(x for dd in args["dimensions"] for x in dd["questions"] if x.get("id") == q["id"])
                    q["grading_rubric"] = match["grading_rubric"]
        self.bind(sentl_project(study, edit=saved_as_sent))
        refused = self.bind(sentl_project(study), check=2)
        self.assertIn("another rubric", refused.stdout + refused.stderr)

    def test_validate_counts_the_sentence_in_the_anchor_s_length(self):
        study = self.with_namesake()
        q = study["projects"][0]["dimensions"][0]["questions"][0]
        q["rubric"]["1"] = "x" * (design.ANCHOR - 20)
        problems, _ = design.problems_of(study, {GPT, GEM}, ({}, {}))
        self.assertTrue(any(f"{q['key']}: rubric anchor 1 is" in p for p in problems), problems)

    def test_recording_a_namesake_is_a_change_of_criteria_for_the_questions_on_the_subject(self):
        study, changes, _ = design.revise(self.design, self.with_namesake())
        self.assertIn("health-1: rubric, judge instructions or facts changed", changes)
        self.assertFalse(any(c.startswith("c-health-1:") for c in changes))


class CandidatesTest(InsightCase, unittest.TestCase):

    def test_the_brief_proposes_namesakes_from_suggestions_and_answers(self):
        self.ingest_market(9101, OCT[0], namesake_rows((TELLS_APART, (
            "Avenello, con sede a Borgoverde, produce divani.", 5,
            [LISTED, "https://www.avenelloarredi.example/chi-siamo", "https://avenello.example/lavoro"]))))
        demand = {"schema": "sentl-monitor/search-demand@1", "market": {"country": "IT", "language": "it"},
                  "themes": {"lavoro": {"seeds": ["lavorare da avenello"], "volumes": [], "autocomplete": [
                      {"prefix": "avenello", "suggestions": ["avenello divani", "avenello divani letto", "avenello latte"],
                       "source": "google autocomplete hl=it gl=IT", "collected": "2026-10-16"}]}},
                  "volume_source": None}
        (self.study / "search-demand.json").write_text(json.dumps(demand), encoding="utf-8")
        out = self.cli("demand", "namesakes", "--study", self.study, check=0).stdout
        self.assertIn("divani: 2 suggestions", out)
        self.assertNotIn("latte:", out)
        self.assertIn("avenelloarredi.example: cited by 1 answer", out)
        self.assertNotIn("avenello.example:", out)
        self.assertIn("lavoro.example/azienda/avenello-arredi: cited by 2 answers", out)
        self.assertIn("Borgoverde: 1 answer", out)
        self.assertFalse((self.study / "study.json").read_text(encoding="utf-8").count("namesakes"))

    def test_a_recorded_namesake_is_not_proposed_again(self):
        self.ingest_market(9101, OCT[0], namesake_rows((TELLS_APART, DESCRIBES)))
        study = self.read("study.json")
        study["subject"]["namesakes"] = [copy.deepcopy(NAMESAKE)]
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        out = self.cli("demand", "namesakes", "--study", self.study, check=0).stdout
        self.assertNotIn("lavoro.example/azienda/avenello-arredi", out)


if __name__ == "__main__":
    unittest.main()
