import unittest

from fixtures import GEM, GPT, StudyCase, run


class PeriodTest(StudyCase, unittest.TestCase):

    def period(self, date="2026-10-31", check=0):
        proc = self.cli("period", "--study", self.study, "--date", date, check=check)
        return proc

    def test_dimension_mean_is_the_mean_of_its_judged_answers(self):
        self.ready()
        p = self.read("history/periods/2026-10-31.json")
        dims = p["projects"]["brand"]["dimensions"]
        self.assertAlmostEqual(dims["salute"]["total"]["mean"], 3.75)
        self.assertAlmostEqual(dims["prezzo"]["total"]["mean"], 2.5)
        self.assertAlmostEqual(dims["salute"]["questions"]["salute-1"]["total"]["mean"], 3.0)
        self.assertAlmostEqual(dims["salute"]["by_model"][GPT]["mean"], 4.5)

    def test_project_mean_is_the_mean_of_its_dimension_means(self):
        self.ready()
        proj = self.read("history/periods/2026-10-31.json")["projects"]["brand"]
        self.assertAlmostEqual(proj["total"]["mean"], 3.125)
        self.assertAlmostEqual(proj["by_model"][GPT]["mean"], 3.75)
        self.assertAlmostEqual(proj["by_model"][GEM]["mean"], 2.5)

    def test_period_file_names_its_runs_and_has_no_previous_period(self):
        self.ready()
        p = self.read("history/periods/2026-10-31.json")
        self.assertEqual(p["schema"], "sentl-monitor/period@2")
        self.assertEqual(p["runs"], {"brand": [9001]})
        self.assertEqual(p["comparison"]["previous"], None)
        self.assertEqual(p["from"], "2026-10-01T06:00:00Z")

    def test_coverage_and_bands(self):
        self.ready()
        salute = self.read("history/periods/2026-10-31.json")["projects"]["brand"]["dimensions"]["salute"]["total"]
        self.assertEqual((salute["judged"], salute["expected"]), (4, 4))
        self.assertAlmostEqual(salute["coverage"], 1.0)
        self.assertEqual(salute["bands"], {"1-2": 1, "3": 0, "4-5": 3})
        self.assertTrue(salute["figure"])

    def test_presence_counts_answers_naming_the_subject_among_answers_given(self):
        data = run(rounds=2)
        blank = next(r for r in data["run"]["responses"] if r["dimension"] == "Prezzo" and r["model_id"] == GEM)
        blank.update(answer=None, judge_score=None)
        self.ready(data)
        dims = self.read("history/periods/2026-10-31.json")["projects"]["brand"]["dimensions"]
        salute = dims["salute"]["total"]["presence"]
        self.assertEqual((salute["named"], salute["given"]), (6, 8))
        self.assertAlmostEqual(salute["rate"], 0.75)
        self.assertAlmostEqual(salute["position"], 4 / 3)
        prezzo = dims["prezzo"]["total"]["presence"]
        self.assertEqual((prezzo["named"], prezzo["given"]), (2, 3))

    def test_presence_uses_the_aliases_in_force_when_the_period_is_built(self):
        self.adopt()
        self.ingest(run())
        self.answer_operator()
        self.period()
        proj = self.read("history/periods/2026-10-31.json")["projects"]["brand"]["total"]
        self.assertEqual(proj["presence"]["named"], 4)

    def test_domains_are_counted_once_per_answer_and_owned_ones_split_out(self):
        self.ready()
        dims = self.read("history/periods/2026-10-31.json")["projects"]["brand"]["dimensions"]
        self.assertEqual(dims["salute"]["total"]["domains"],
                         {"salute.example": 2, "avenello.example": 1, "shop.avenello.example": 1})
        self.assertEqual(dims["salute"]["total"]["owned"], {"citing": 2, "with_sources": 3})
        self.assertEqual(dims["prezzo"]["total"]["domains"], {"prezzi.example": 2})

    def test_unmatched_responses_count_in_no_figure(self):
        stray = {"id": 1, "model_id": GPT, "question": "Avenello è vegano?", "dimension": "Salute",
                 "answer": "No.", "judge_score": 1, "sentiment": "negative", "sources": []}
        self.adopt(at="2026-09-30T12:00:00Z")
        self.answer_operator()
        self.ingest(run(extra=[stray]))
        self.period()
        salute = self.read("history/periods/2026-10-31.json")["projects"]["brand"]["dimensions"]["salute"]["total"]
        self.assertAlmostEqual(salute["mean"], 3.75)
        self.assertEqual(salute["judged"], 4)

    def test_the_runs_of_the_interval_are_pooled_in_start_order(self):
        self.adopt()
        self.answer_operator()
        self.ingest(run(run_id=9005, started="2026-10-05T06:00:00Z"), name="b.json")
        self.ingest(run(run_id=9001, started="2026-10-01T06:00:00Z"), name="a.json")
        self.period()
        self.assertEqual(self.read("history/periods/2026-10-31.json")["runs"], {"brand": [9001, 9005]})

    def test_a_run_under_ninety_percent_judged_leaves_no_period(self):
        self.adopt()
        self.answer_operator()
        self.ingest(run(overrides={("salute-2", GEM): ("Dipende.", None, "neutral", [])}))
        proc = self.period(check=4)
        self.assertIn("83%", proc.stdout + proc.stderr)
        self.assertFalse((self.study / "history/periods/2026-10-31.json").exists())

    def test_a_dimension_under_eighty_percent_judged_has_no_figure(self):
        data = run(rounds=2)
        pick = next(r for r in data["run"]["responses"] if r["dimension"] == "Prezzo")
        pick["judge_score"] = None
        self.ready(data)
        dims = self.read("history/periods/2026-10-31.json")["projects"]["brand"]["dimensions"]
        self.assertFalse(dims["prezzo"]["total"]["figure"])
        self.assertTrue(dims["salute"]["total"]["figure"])

    def test_a_pair_whose_answers_differ_by_two_points_is_unstable(self):
        data = run(rounds=2)
        second = [r for r in data["run"]["responses"]
                  if r["model_id"] == GEM and r["question"].endswith("fa male?")][1]
        second["judge_score"] = 5
        self.ready(data)
        salute = self.read("history/periods/2026-10-31.json")["projects"]["brand"]["dimensions"]["salute"]
        self.assertEqual(salute["total"]["unstable_pairs"], [{"question": "salute-1", "model": GEM}])
        self.assertEqual(salute["questions"]["salute-2"]["total"]["unstable_pairs"], [])

    def test_material_says_which_questions_name_the_subject_and_fences_each_answer(self):
        heading_inside = "Ecco i fatti.\n\n### Zuccheri\n\nAvenello ne contiene pochi."
        self.ready(run(overrides={("salute-2", GPT): (heading_inside, 5, "positive", [])}))
        material = (self.study / "history/material/2026-10-31.md").read_text(encoding="utf-8")
        self.assertIn("names the subject: yes", material)
        self.assertIn("~~~~\n" + heading_inside + "\n~~~~", material)

    def test_material_holds_figures_and_every_answer_for_the_writer(self):
        self.ready()
        material = (self.study / "history/material/2026-10-31.md").read_text(encoding="utf-8")
        self.assertIn("Salute", material)
        self.assertIn("Prezzo", material)
        self.assertIn("Sì, Avenello fa bene alla salute se consumato con moderazione.", material)
        self.assertIn("3,8", material)

    def test_the_material_writes_each_figure_as_the_report_cites_it(self):
        self.ready()
        material = (self.study / "history/material/2026-10-31.md").read_text(encoding="utf-8")
        salute = material[material.index("### Dimension Salute"):material.index("#### Question")]
        self.assertIn("mean 3,8 |", salute)
        self.assertIn("(75%)", salute)
        self.assertNotIn("3.75", material)


if __name__ == "__main__":
    unittest.main()
