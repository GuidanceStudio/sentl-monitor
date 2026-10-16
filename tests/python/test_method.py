import json
import re
import unittest

from fixtures import GEM, GPT, StudyCase, models, run

IT_ORDER = ["Cosa abbiamo fatto e a che scopo", "Da dove vengono i temi",
            "Le dimensioni e come ci siamo arrivati", "Le domande",
            "Come vengono valutate le risposte", "Cosa dicono gli assistenti", "Cosa è cambiato"]
EN_ORDER = ["What we did and to what end", "Where the themes came from",
            "The dimensions and how we reached them", "The questions",
            "How the answers are scored", "What the assistants say", "What changed"]


def sections(text):
    """Map each `## N. Title` heading to the text under it."""
    parts = re.split(r"^## \d+\. (.+)$", text, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


class MethodTest(StudyCase, unittest.TestCase):

    def method(self, check=0, models_data=None, *extra):
        return self.cli("method", "--study", self.study, "--date", "2026-10-31",
                        "--models", self.save("models.json", models_data or models()), *extra, check=check)

    def report(self):
        return (self.study / "reports" / "2026-10-31.md").read_text(encoding="utf-8")

    def test_first_report_lays_out_the_sections_in_the_first_report_order(self):
        self.ready()
        self.method()
        headings = re.findall(r"^## (\d+)\. (.+)$", self.report(), flags=re.M)
        self.assertEqual([t for _, t in headings], IT_ORDER)
        self.assertEqual([int(n) for n, _ in headings], list(range(1, 8)))

    def test_title_is_the_research_question_with_subject_period_and_date(self):
        self.ready()
        self.method()
        lines = self.report().splitlines()
        self.assertEqual(lines[0], "# Cosa viene detto a chi chiede a un assistente AI di Avenello?")
        head = "\n".join(lines[1:4])
        self.assertIn("Avenello", head)
        self.assertIn("1 ottobre 2026", head)
        self.assertIn("31 ottobre 2026", head)

    def test_purpose_names_the_assistants_and_counts_the_answers(self):
        self.ready()
        self.method()
        purpose = sections(self.report())[IT_ORDER[0]]
        self.assertIn("Sapere cosa dicono gli assistenti AI di Avenello", purpose)
        self.assertIn("Acme Chat", purpose)
        self.assertIn("Orbit Reason", purpose)
        self.assertRegex(purpose, r"\b6 risposte\b")
        self.assertIn("fonti", purpose)

    def test_themes_are_grouped_by_origin_with_the_no_search_data_line(self):
        self.ready()
        self.method()
        themes = sections(self.report())[IT_ORDER[1]]
        self.assertIn("Domande al servizio clienti, 2026", themes)
        self.assertIn("Listino 2026", themes)
        self.assertIn("Nessun dato di ricerca", themes)

    def test_dimensions_leave_out_archived_ones_and_say_who_asks(self):
        self.ready()
        self.method()
        dims = sections(self.report())[IT_ORDER[2]]
        self.assertIn("Salute", dims)
        self.assertIn("Prezzo", dims)
        self.assertNotIn("Confezione", self.report())
        self.assertIn("Le domande sono quelle di un consumatore qualsiasi.", dims)

    def test_questions_are_verbatim(self):
        self.ready()
        self.method()
        qs = sections(self.report())[IT_ORDER[3]]
        self.assertIn("Il latte d’avena Avenello fa male?", qs)
        self.assertIn("Quanto costa il latte d'avena Avenello rispetto al latte vaccino?", qs)

    def test_scoring_gives_five_three_and_one_and_who_wrote_the_criteria(self):
        self.ready()
        self.method()
        scoring = sections(self.report())[IT_ORDER[4]]
        for anchor in ("Dice che non fa male con fonti", "Risposta neutra", "Dice che fa male senza fonti"):
            self.assertIn(anchor, scoring)
        self.assertNotIn("Riporta rischi non verificati", scoring)
        self.assertIn("il team marketing di Avenello", scoring)
        self.assertIn("15 settembre 2026", scoring)

    def test_findings_hold_one_entry_to_write_per_dimension(self):
        self.ready()
        self.method()
        findings = sections(self.report())[IT_ORDER[5]]
        self.assertEqual(re.findall(r"^### (\w+)", findings, flags=re.M), ["Salute", "Prezzo"])
        self.assertIn("[[", findings)

    def test_changes_on_a_first_report_says_it_is_the_first_measurement(self):
        self.ready()
        self.method()
        self.assertIn("prima misurazione", sections(self.report())[IT_ORDER[6]])

    def test_the_report_carries_no_id_key_or_model_id(self):
        self.ready()
        self.method()
        text = self.report()
        for banned in (GPT, GEM, "salute-1", "prezzo-1", "9001", "501", "credit", "crediti"):
            self.assertNotIn(banned, text)

    def test_a_model_missing_from_the_list_is_named_from_its_id(self):
        self.ready()
        only_one = models()
        del only_one["researcher_models"][GEM]
        self.method(models_data=only_one)
        self.assertIn("reason-pro", sections(self.report())[IT_ORDER[0]])

    def test_personas_without_a_persona_per_question_claim_none_beside_the_questions(self):
        self.adopt()
        self.answer_operator()
        study = self.read("study.json")
        study["narrative"]["audience"] = {"choice": "personas", "reason": "Genitori e sportivi chiedono cose diverse."}
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.ingest(run())
        self.cli("period", "--study", self.study, "--date", "2026-10-31", check=0)
        self.method()
        self.assertNotIn("accanto a ogni domanda", self.report())

    def test_english_headings_follow_the_report_language(self):
        self.adopt()
        self.answer_operator(report_language="en")
        self.ingest(run())
        self.cli("period", "--study", self.study, "--date", "2026-10-31", check=0)
        self.method()
        self.assertEqual(re.findall(r"^## \d+\. (.+)$", self.report(), flags=re.M), EN_ORDER)

    def test_missing_operator_answers_are_listed_and_no_report_is_written(self):
        self.adopt()
        self.ingest(run())
        proc = self.method(check=2)
        for field in ("research_question", "purpose", "report_every", "origins"):
            self.assertIn(field, proc.stdout + proc.stderr)
        self.assertFalse((self.study / "reports" / "2026-10-31.md").exists())

    def test_without_a_period_file_nothing_is_written(self):
        self.adopt()
        self.answer_operator()
        self.method(check=2)

    def test_an_existing_report_is_not_overwritten(self):
        self.ready()
        self.method()
        path = self.study / "reports" / "2026-10-31.md"
        path.write_text("written by hand", encoding="utf-8")
        self.method(check=2)
        self.assertEqual(path.read_text(encoding="utf-8"), "written by hand")


if __name__ == "__main__":
    unittest.main()
