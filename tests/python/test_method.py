import json
import re
import unittest

from fixtures import GEM, GPT, StudyCase, models, project, run

PURPOSE, THEMES, DIMENSIONS, QUESTIONS, SCORING = ("Cosa abbiamo fatto e a che scopo", "Da dove vengono i temi",
                                                  "Le dimensioni e come ci siamo arrivati", "Le domande",
                                                  "Come vengono valutate le risposte")
SUMMARY, FINDINGS, CHANGES = "In sintesi", "Cosa dicono gli assistenti", "Cosa è cambiato"
IT_ORDER = [PURPOSE, THEMES, DIMENSIONS, QUESTIONS, SCORING, SUMMARY, FINDINGS, CHANGES]
EN_ORDER = ["What we did and to what end", "Where the themes came from",
            "The dimensions and how we reached them", "The questions",
            "How the answers are scored", "In short", "What the assistants say", "What changed"]


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
        self.assertEqual([int(n) for n, _ in headings], list(range(1, 9)))

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
        findings = sections(self.report())[FINDINGS]
        self.assertEqual(re.findall(r"^### (\w+)", findings, flags=re.M), ["Salute", "Prezzo"])
        self.assertIn("[[", findings)

    def test_the_summary_is_left_to_the_writer_after_the_method_sections(self):
        self.ready()
        self.method()
        self.assertEqual(sections(self.report())[SUMMARY].strip(), "[[summary]]")

    def test_changes_on_a_first_report_says_it_is_the_first_measurement(self):
        self.ready()
        self.method()
        self.assertIn("prima misurazione", sections(self.report())[CHANGES])

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


class TwinProjectsTest(StudyCase, unittest.TestCase):
    """The same questions, with the same rubrics, in two projects."""

    def test_a_rubric_used_by_one_question_text_in_two_projects_is_not_shared(self):
        self.adopt()
        twin = project()
        twin["project"].update(id=502, name="Avenello · Gemello")
        for n, d in enumerate(twin["project"]["dimensions"]):
            d["id"] = 21 + n
            for m, q in enumerate(d["questions"]):
                q["id"] = 201 + 10 * n + m
        data = run(run_id=9002)
        data["run"]["project_id"] = 502
        self.cli("adopt", "--study", self.study, "--project", self.save("p2.json", twin),
                 "--run", self.save("r2.json", data), "--key", "twin", check=0)
        self.answer_operator()
        study = self.read("study.json")
        for theme in study["themes"]:
            theme["origins"] = [{"kind": "client_issue", "detail": "Domande al servizio clienti, 2026"}]
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.ingest(run())
        self.cli("ingest", "--study", self.study, "--project", "twin", "--results", self.save("r2b.json", data), check=0)
        self.cli("period", "--study", self.study, "--date", "2026-10-31", check=0)
        self.cli("method", "--study", self.study, "--date", "2026-10-31",
                 "--models", self.save("models.json", models()), check=0)
        scoring = sections((self.study / "reports/2026-10-31.md").read_text(encoding="utf-8"))[SCORING]
        self.assertNotIn("Criteri comuni", scoring)
        self.assertNotIn("» e «Il latte d’avena Avenello fa male?»", scoring)
        self.assertEqual(scoring.count("«Il latte d’avena Avenello fa male?» 5: Dice che non fa male con fonti"), 2)


class ScheduleTest(unittest.TestCase):
    """How often a project runs, read from the start times of runs without a version."""

    def test_runs_on_the_same_day_are_one_day(self):
        from sentlmon.period import _schedule_of
        self.assertIsNone(_schedule_of(["2026-10-01T06:00:00Z", "2026-10-01T09:00:00Z"]))
        reruns = ["2026-10-01T06:00:00Z", "2026-10-01T08:00:00Z", "2026-10-01T10:00:00Z",
                  "2026-10-08T06:00:00Z", "2026-10-08T08:00:00Z"]
        self.assertEqual(_schedule_of(reruns), "weekly")
        self.assertEqual(_schedule_of([f"2026-10-0{d}T06:00:00Z" for d in range(1, 6)]), "daily")


class TwoProjectMethodTest(StudyCase, unittest.TestCase):
    """A study of two projects with different settings: the branded fixture project (three
    questions, two assistants, one round, weekly) and the market project (three questions
    sharing one rubric, one assistant, three rounds, daily)."""

    MARKET = "Avenello · Mercato"

    def setUp(self):
        super().setUp()
        from fixtures import market_project
        self.adopt(at="2026-09-30T12:00:00Z")
        market = market_project(rounds=3)
        market["project"]["researcher_model_ids"] = [GEM]
        self.cli("adopt", "--study", self.study, "--project", self.save("market.json", market),
                 "--run", self.save("market-run.json", self.market_run(9000, "2026-09-29T06:00:00Z")),
                 "--key", "market", check=0, at="2026-09-30T12:00:00Z")
        self.answer_operator()
        study = self.read("study.json")
        for theme in study["themes"]:
            theme["origins"] = [{"kind": "client_issue", "detail": "Domande al servizio clienti, 2026"}]
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def market_run(run_id, started, rounds=3):
        from fixtures import CHOICE_Q, PRICE_Q, WORK_Q, results
        rows = [(q, GEM, "Avenello costa 2,10 € al litro.", 4, []) for q in (PRICE_Q, CHOICE_Q, WORK_Q)]
        return results(run_id, started, rows * rounds)

    def report(self, date="2026-10-31"):
        self.cli("period", "--study", self.study, "--date", date, "--models", self.save("models.json", models()), check=0)
        self.cli("method", "--study", self.study, "--date", date, "--models", self.save("models.json", models()), check=0)
        return (self.study / "reports" / f"{date}.md").read_text(encoding="utf-8")

    def ingest_both(self, starts=("2026-10-05T06:00:00Z", "2026-10-12T06:00:00Z")):
        for n, start in enumerate(starts):
            self.ingest(run(run_id=9101 + n, started=start), name=f"b-{n}.json")
            self.cli("ingest", "--study", self.study, "--project", "market",
                     "--results", self.save(f"m-{n}.json", self.market_run(9201 + n, start)), check=0)

    def test_projects_with_different_settings_are_stated_one_per_line(self):
        self.ingest_both()
        purpose = sections(self.report())[IT_ORDER[0]]
        self.assertIn("- **Avenello · Con il marchio**: 3 domande a 2 assistenti AI (Acme Chat e Orbit Reason), "
                      "ciascuna posta una volta per rilevazione, con una rilevazione a settimana.", purpose)
        self.assertIn(f"- **{self.MARKET}**: 3 domande a un assistente AI (Orbit Reason), ciascuna posta 3 volte per "
                      "rilevazione, con una rilevazione al giorno.", purpose)
        self.assertNotIn("Abbiamo posto 6 domande", purpose)

    def test_projects_with_the_same_settings_keep_one_sentence(self):
        study = self.read("study.json")
        for version in sorted((self.study / "history/versions").glob("market-*.json")):
            data = json.loads(version.read_text(encoding="utf-8"))
            data["settings"].update(models=[GPT, GEM], rounds=1, schedule="weekly")
            version.write_text(json.dumps(data), encoding="utf-8")
        from fixtures import CHOICE_Q, PRICE_Q, WORK_Q, results
        for n, start in enumerate(("2026-10-05T06:00:00Z", "2026-10-12T06:00:00Z")):
            self.ingest(run(run_id=9101 + n, started=start), name=f"b-{n}.json")
            rows = [(q, m, "Avenello costa 2,10 € al litro.", 4, []) for q in (PRICE_Q, CHOICE_Q, WORK_Q) for m in (GPT, GEM)]
            self.cli("ingest", "--study", self.study, "--project", "market",
                     "--results", self.save(f"m-{n}.json", results(9201 + n, start, rows)), check=0)
        purpose = sections(self.report())[IT_ORDER[0]]
        self.assertIn("Abbiamo posto 6 domande a 2 assistenti AI: Acme Chat e Orbit Reason.", purpose)
        self.assertNotIn(f"**{self.MARKET}**", purpose)
        self.assertEqual(study["projects"][1]["key"], "market")

    def test_runs_without_a_version_give_their_rounds_and_schedule(self):
        self._tmp.cleanup()
        StudyCase.setUp(self)
        from fixtures import market_project
        self.adopt(at="2026-11-01T00:00:00Z")
        market = market_project(rounds=1)
        market["project"]["researcher_model_ids"] = [GEM]
        self.cli("adopt", "--study", self.study, "--project", self.save("market.json", market),
                 "--run", self.save("market-run.json", self.market_run(9000, "2026-09-29T06:00:00Z")),
                 "--key", "market", check=0, at="2026-11-01T00:00:00Z")
        self.answer_operator()
        study = self.read("study.json")
        for theme in study["themes"]:
            theme["origins"] = [{"kind": "client_issue", "detail": "Domande al servizio clienti, 2026"}]
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.ingest_both(("2026-10-05T06:00:00Z", "2026-10-12T06:00:00Z", "2026-10-19T06:00:00Z"))
        purpose = sections(self.report())[IT_ORDER[0]]
        self.assertIn(f"- **{self.MARKET}**: 3 domande a un assistente AI (Orbit Reason), ciascuna posta 3 volte per "
                      "rilevazione, con una rilevazione a settimana.", purpose)

    def test_dimensions_that_share_an_origin_are_listed_together(self):
        self.ingest_both()
        study = self.read("study.json")
        study["themes"][0]["origins"].append({"kind": "client_material", "detail": "Listino 2026"})
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        themes = sections(self.report())[IT_ORDER[1]]
        self.assertIn("- Salute, Prezzo, Scelta e Lavoro: Domande al servizio clienti, 2026", themes)
        self.assertEqual(themes.count("Domande al servizio clienti, 2026"), 1)
        self.assertIn("- Salute: Listino 2026", themes)

    def test_a_rubric_shared_by_several_questions_is_stated_once_with_all_five_anchors(self):
        from fixtures import CHOICE_Q, PRICE_Q, WORK_Q
        self.ingest_both()
        scoring = sections(self.report())[IT_ORDER[4]]
        self.assertIn(f"- «{PRICE_Q}», «{CHOICE_Q}» e «{WORK_Q}»: 5: e · 4: d · 3: c · 2: b · 1: a", scoring)
        self.assertEqual(scoring.count("2: b"), 1)
        self.assertIn("I criteri comuni a più domande sono riportati una volta per tutte, con i cinque punteggi.", scoring)
        self.assertIn("«Il latte d’avena Avenello fa male?» 5: Dice che non fa male con fonti · 3: Risposta neutra · "
                      "1: Dice che fa male senza fonti", scoring)

    def test_check_accepts_the_regenerated_method_sections(self):
        self.ingest_both()
        self.report()
        path = self.study / "reports/2026-10-31.md"
        path.write_text(re.sub(r"\[\[[^\]]*\]\]", "le risposte descrivono Avenello", path.read_text(encoding="utf-8")),
                        encoding="utf-8")
        proc = self.cli("check", "--study", self.study, path)
        self.assertEqual(proc.returncode, 0, proc.stdout)
