import json
import unittest

from fixtures import GEM, GPT, StudyCase, run


class IngestTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt()

    def test_writes_a_normalized_run_snapshot(self):
        self.ingest(run())
        snap = self.read_run("brand", 9001)
        self.assertEqual(snap["schema"], "sentl-monitor/run@1")
        self.assertEqual((snap["run_id"], snap["project"], snap["status"], snap["trigger"]),
                         (9001, "brand", "completed", "scheduled"))
        self.assertEqual(snap["sentl_score"], 3.1)
        self.assertEqual((snap["received"], snap["judged"]), (6, 6))
        by = {(r["question"], r["model"]): r for r in snap["responses"]}
        self.assertEqual(len(by), 6)
        r = by[("salute-1", GPT)]
        self.assertEqual((r["dimension"], r["score"], r["sentiment"], r["match"]), ("salute", 4, "positive", "exact"))
        self.assertTrue(r["answer"].startswith("Il latte d'avena Avenello non fa male"))
        self.assertEqual([s["domain"] for s in r["sources"]], ["avenello.example", "salute.example"])
        self.assertEqual(r["sources"][0]["url"], "https://www.avenello.example/prodotti")

    def test_matches_across_typographic_quotes_and_spacing(self):
        self.ingest(run())
        snap = self.read_run("brand", 9001)
        self.assertEqual(sum(1 for r in snap["responses"] if r["question"] == "salute-1"), 2)

    def test_a_run_before_the_first_version_takes_its_expected_count_from_its_responses(self):
        self.ingest(run(started="2026-10-01T06:00:00Z"))
        snap = self.read_run("brand", 9001)
        self.assertIsNone(snap["version"])
        self.assertEqual(snap["expected"], 6)

    def test_a_run_after_the_version_takes_its_expected_count_from_it(self):
        dropped = run(run_id=9100, started="2999-01-01T06:00:00Z", score=3.0,
                      overrides={})
        dropped["run"]["responses"] = [r for r in dropped["run"]["responses"] if r["model_id"] == GPT]
        self.ingest(dropped)
        snap = self.read_run("brand", 9100)
        self.assertEqual(snap["version"], 1)
        self.assertEqual((snap["expected"], snap["received"]), (6, 3))

    def test_unscored_answer_gets_null_sentiment(self):
        self.ingest(run(overrides={("salute-2", GEM): ("Dipende.", None, "neutral", [])}))
        r = next(r for r in self.read_run("brand", 9001)["responses"] if (r["question"], r["model"]) == ("salute-2", GEM))
        self.assertIsNone(r["score"])
        self.assertIsNone(r["sentiment"])
        self.assertEqual(self.read_run("brand", 9001)["judged"], 5)

    def test_an_empty_answer_is_kept_and_not_judged(self):
        self.ingest(run(overrides={("prezzo-1", GEM): (None, None, "neutral", [])}))
        snap = self.read_run("brand", 9001)
        r = next(r for r in snap["responses"] if (r["question"], r["model"]) == ("prezzo-1", GEM))
        self.assertIsNone(r["answer"])
        self.assertIsNone(r["score"])
        self.assertEqual((snap["received"], snap["judged"]), (6, 5))

    def test_a_response_matching_no_question_is_kept_unmatched_and_listed(self):
        stray = {"id": 1, "model_id": GPT, "question": "Avenello è vegano?", "dimension": "Salute",
                 "answer": "Sì.", "judge_score": 5, "sentiment": "positive", "sources": []}
        proc = self.ingest(run(extra=[stray]))
        snap = self.read_run("brand", 9001)
        [u] = [r for r in snap["responses"] if r["match"] == "unmatched"]
        self.assertIsNone(u["question"])
        self.assertIn("Avenello è vegano?", proc.stdout)
        self.assertIn("1 unmatched", proc.stdout)

    def test_a_status_not_final_is_not_ingested(self):
        proc = self.ingest(run(status="running"), check=3)
        self.assertIn("running", proc.stdout + proc.stderr)
        self.assertFalse((self.study / "history" / "runs" / "brand" / "9001.json.gz").exists())

    def test_a_truncated_response_is_refused(self):
        text = json.dumps(run())[:-200]
        path = self.study / "inbox" / "cut.json"
        path.write_text(text, encoding="utf-8")
        proc = self.cli("ingest", "--study", self.study, "--project", "brand", "--results", path, check=2)
        self.assertIn("complete JSON", proc.stdout + proc.stderr)
        self.assertFalse((self.study / "history" / "runs" / "brand" / "9001.json.gz").exists())

    def test_ingesting_a_run_twice_changes_nothing(self):
        self.ingest(run())
        first = (self.study / "history/runs/brand/9001.json.gz").read_bytes()
        proc = self.ingest(run(score=1.0))
        self.assertIn("already ingested", proc.stdout)
        self.assertEqual((self.study / "history/runs/brand/9001.json.gz").read_bytes(), first)

    def test_a_server_error_is_recorded_as_unavailable_and_cleared_once_read(self):
        self.cli("ingest", "--study", self.study, "--project", "brand", "--unavailable", 9002,
                 "--reason", "An internal server error occurred.", check=0)
        self.cli("ingest", "--study", self.study, "--project", "brand", "--unavailable", 9002,
                 "--reason", "An internal server error occurred.", check=0)
        [entry] = self.read("history/unavailable.json")["runs"]
        self.assertEqual((entry["project"], entry["run_id"], entry["attempts"]), ("brand", 9002, 2))
        self.ingest(run(run_id=9002))
        self.assertEqual(self.read("history/unavailable.json")["runs"], [])

    def test_the_operator_is_told_when_sentl_score_differs_from_the_mean_of_dimension_means(self):
        quiet = self.ingest(run(score=3.1))
        self.assertNotIn("differs", quiet.stdout)
        loud = self.ingest(run(run_id=9003, score=3.3))
        self.assertIn("differs", loud.stdout)
        self.assertIn("3.1", loud.stdout)
        self.assertIn("3.3", loud.stdout)

    def test_a_grounding_redirect_takes_its_domain_from_the_title(self):
        redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AbC123"
        data = run()
        data["run"]["responses"][0]["sources"] = [{"title": "salute.example", "url": redirect},
                                                  {"title": "Una pagina", "url": redirect}]
        self.ingest(data)
        r = self.read_run("brand", 9001)["responses"][0]
        self.assertEqual([s["domain"] for s in r["sources"]], ["salute.example", "vertexaisearch.cloud.google.com"])

    def test_unknown_project_key_is_refused(self):
        self.cli("ingest", "--study", self.study, "--project", "nope",
                 "--results", self.save("r.json", run()), check=2)


if __name__ == "__main__":
    unittest.main()
