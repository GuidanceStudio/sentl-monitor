import json
import unittest

from fixtures import GEM, GPT, StudyCase, project, run


class AdoptTest(StudyCase, unittest.TestCase):

    def test_study_json_holds_the_project_as_sentl_has_it(self):
        self.adopt()
        study = self.read("study.json")
        self.assertEqual(study["schema"], "sentl-monitor/study@1")
        self.assertEqual(study["kind"], "study")
        self.assertEqual(study["organization"], "example-org")
        self.assertIsNone(study["report_every"])
        [proj] = study["projects"]
        self.assertEqual(proj["key"], "brand")
        self.assertEqual(proj["name"], "Avenello · Con il marchio")
        self.assertEqual(proj["models"], [GPT, GEM])
        self.assertEqual((proj["rounds"], proj["schedule"]), (1, "weekly"))
        self.assertEqual([d["key"] for d in proj["dimensions"]], ["salute", "prezzo", "confezione"])
        self.assertEqual([d.get("archived", False) for d in proj["dimensions"]], [False, False, True])
        salute = proj["dimensions"][0]
        self.assertEqual([q["key"] for q in salute["questions"]], ["salute-1", "salute-2"])
        q1 = salute["questions"][0]
        self.assertEqual(q1["text"], "Il latte d’avena Avenello fa male?")
        self.assertEqual(q1["label"], "Avenello fa male")
        self.assertEqual(q1["rubric"]["5"], "Dice che non fa male con fonti")
        self.assertIn("3 g di zuccheri", q1["instructions"])
        self.assertEqual(q1["lineage"], [{"version": 1, "change": "adopted"}])

    def test_each_measured_dimension_gets_a_theme_waiting_for_its_origins(self):
        self.adopt()
        themes = self.read("study.json")["themes"]
        self.assertEqual([(t["id"], t["label"], t["dimension"], t["origins"]) for t in themes],
                         [("salute", "Salute", "salute", []), ("prezzo", "Prezzo", "prezzo", [])])

    def test_binding_records_every_sentl_id(self):
        self.adopt()
        binding = self.read("sentl.json")
        self.assertEqual(binding["schema"], "sentl-monitor/binding@1")
        self.assertEqual(binding["organization"], "example-org")
        self.assertEqual(binding["projects"]["brand"], {
            "project_id": 501, "version": 1,
            "dimensions": {"salute": 11, "prezzo": 12, "confezione": 13},
            "questions": {"salute-1": 101, "salute-2": 102, "prezzo-1": 103, "confezione-1": 104},
        })

    def test_an_adopt_version_records_the_configuration_in_force(self):
        self.adopt()
        version = self.read("history/versions/brand-001.json")
        self.assertEqual(version["schema"], "sentl-monitor/version@1")
        self.assertEqual((version["project"], version["version"], version["source"]), ("brand", 1, "adopt"))
        self.assertEqual(version["settings"], {"models": [GPT, GEM], "rounds": 1, "schedule": "weekly", "active": True})
        dims = {d["key"]: d for d in version["dimensions"]}
        self.assertEqual(dims["salute"]["name"], "Salute")
        self.assertTrue(dims["confezione"]["archived"])
        q = dims["salute"]["questions"][0]
        self.assertEqual((q["key"], q["id"], q["text"]), ("salute-1", 101, "Il latte d’avena Avenello fa male?"))
        self.assertRegex(q["criteria_hash"], r"^[0-9a-f]{64}$")
        self.assertNotEqual(q["criteria_hash"], dims["salute"]["questions"][1]["criteria_hash"])

    def test_output_lists_what_the_operator_must_answer(self):
        self.save("project.json", project())
        proc = self.cli("adopt", "--study", self.study, "--project", self.study / "inbox/project.json",
                        "--run", self.save("run.json", run()), "--key", "brand", check=0)
        for field in ("research_question", "purpose", "audience", "aliases", "market",
                      "report_language", "report_every", "criteria", "origins"):
            self.assertIn(field, proc.stdout)

    def test_project_key_defaults_to_a_slug_of_the_project_name(self):
        self.cli("adopt", "--study", self.study, "--project", self.save("p.json", project()),
                 "--run", self.save("r.json", run()), check=0)
        self.assertEqual(list(self.read("sentl.json")["projects"]), ["avenello-con-il-marchio"])

    def test_refuses_a_saved_project_missing_a_question_of_the_latest_run(self):
        damaged = project()
        damaged["project"]["dimensions"][1]["questions"][0]["question"] = "Quanto costa Avenello?"
        proc = self.cli("adopt", "--study", self.study, "--project", self.save("p.json", damaged),
                        "--run", self.save("r.json", run()), "--key", "brand", check=2)
        self.assertIn("Quanto costa il latte d'avena Avenello rispetto al latte vaccino?", proc.stdout + proc.stderr)
        self.assertFalse((self.study / "study.json").exists())
        self.assertFalse((self.study / "sentl.json").exists())

    def test_refuses_a_saved_project_missing_a_dimension_of_the_latest_run(self):
        damaged = project()
        damaged["project"]["dimensions"][1]["name"] = "Prezzi"
        proc = self.cli("adopt", "--study", self.study, "--project", self.save("p.json", damaged),
                        "--run", self.save("r.json", run()), "--key", "brand", check=2)
        self.assertIn("Prezzo", proc.stdout + proc.stderr)

    def test_without_a_run_the_check_is_skipped_and_said(self):
        proc = self.cli("adopt", "--study", self.study, "--project", self.save("p.json", project()),
                        "--key", "brand", check=0)
        self.assertIn("no completed run", proc.stdout.lower())
        self.assertTrue((self.study / "study.json").exists())

    def test_accepts_the_mcp_content_wrapper_a_host_may_save(self):
        wrapped = [{"type": "text", "text": json.dumps(project(), ensure_ascii=False)}]
        self.cli("adopt", "--study", self.study, "--project", self.save("p.json", wrapped),
                 "--run", self.save("r.json", run()), "--key", "brand", check=0)
        self.assertEqual(self.read("sentl.json")["projects"]["brand"]["project_id"], 501)

    def test_refuses_to_adopt_the_same_key_twice(self):
        self.adopt()
        self.cli("adopt", "--study", self.study, "--project", self.save("p.json", project()),
                 "--key", "brand", check=2)


if __name__ == "__main__":
    unittest.main()
