"""A Sentl response whose shape differs from what the skill reads is refused with exit 5,
naming the tool and the field; extra fields are accepted. Any other unexpected error exits 6
with one line and no traceback, unless --debug asks for it."""

import os
import unittest
from unittest import mock

from fixtures import GPT, StudyCase, listing, models, monitor, project, run


def responses(data):
    return data["run"]["responses"]


def renamed(items, old, new):
    for item in items:
        item[new] = item.pop(old)


class RunResultsShapeTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt()

    def refused(self, data, *fields):
        proc = self.ingest(data, check=5)
        message = proc.stderr
        self.assertIn("get-run-results-tool", message)
        for field in fields:
            self.assertIn(field, message)
        self.assertNotIn("Traceback", message)
        self.assertFalse((self.study / "history" / "runs" / "brand" / "9001.json.gz").exists())
        return message

    def test_scores_on_a_0_to_100_scale_are_refused(self):
        data = run(score=74.9)
        for r in responses(data):
            r["judge_score"] = r["judge_score"] * 20 - 6
        message = self.refused(data, "run.reputation_score", "run.responses[0].judge_score", "1 to 5")
        self.assertIn("74", message)

    def test_renamed_sources_are_refused(self):
        data = run()
        renamed(responses(data), "sources", "citations")
        self.refused(data, "run.responses[0].sources", "missing")

    def test_a_renamed_source_url_is_refused(self):
        data = run()
        renamed([s for r in responses(data) for s in r["sources"]], "url", "link")
        self.refused(data, ".sources[0].url", "missing")

    def test_a_renamed_question_is_refused(self):
        data = run()
        renamed(responses(data), "question", "prompt")
        self.refused(data, "run.responses[0].question")

    def test_a_score_sent_as_a_string_is_refused(self):
        data = run()
        responses(data)[2]["judge_score"] = "4"
        self.refused(data, "run.responses[2].judge_score", "integer", "'4'")

    def test_a_missing_start_time_is_refused(self):
        data = run()
        del data["run"]["started_at"]
        self.refused(data, "run.started_at", "missing")

    def test_a_renamed_model_id_is_refused(self):
        data = run()
        renamed(responses(data), "model_id", "model")
        self.refused(data, "run.responses[0].model_id")

    def test_a_status_never_seen_is_refused_naming_the_known_ones(self):
        message = self.refused(run(status="partially_scored"), "run.status", "partially_scored", "completed_with_warnings")
        self.assertIn("running", message)

    def test_a_status_not_final_yet_is_still_read_again_later(self):
        self.ingest(run(status="running"), check=3)

    def test_the_same_change_in_every_response_is_reported_once_with_its_count(self):
        data = run()
        renamed(responses(data), "model_id", "model")
        message = self.refused(data)
        self.assertEqual(message.count("model_id"), 1)
        self.assertIn("6 responses", message)

    def test_extra_fields_are_accepted(self):
        data = run()
        data["run"]["credits_used"] = 40
        for n, r in enumerate(responses(data)):
            r["round"] = 1
            r["latency_ms"] = 900 + n
            for s in r["sources"]:
                s["position"] = 1
        self.ingest(data, check=0)

    def test_null_score_null_answer_and_untitled_source_are_accepted(self):
        data = run(overrides={("prezzo-1", GPT): (None, None, "neutral", [])})
        responses(data)[0]["sources"][0]["title"] = None
        self.ingest(data, check=0)

    def test_fields_the_skill_only_copies_take_any_value(self):
        data = run()
        data["run"].update(error={"code": 500, "detail": "judge timeout"}, trigger=1, finished_at="soon")
        responses(data)[0]["sentiment"] = 0.8
        del responses(data)[0]["sources"][0]["title"]
        responses(data)[1]["sources"] = None
        self.ingest(data, check=0)
        snap = self.read_run("brand", 9001)
        self.assertEqual(snap["error"], {"code": 500, "detail": "judge timeout"})
        self.assertEqual(snap["responses"][1]["sources"], [])
        self.assertEqual(snap["responses"][0]["sources"][0]["domain"], "avenello.example")

    def test_a_source_title_that_is_not_text_is_refused(self):
        data = run()
        responses(data)[0]["sources"][0]["title"] = 7
        self.refused(data, "run.responses[0].sources[0].title")

    def test_a_start_time_without_a_time_zone_is_read_as_utc(self):
        self.answer_operator()
        self.ingest(run(started="2026-10-01T06:00:00"), check=0)
        self.cli("period", "--study", self.study, "--date", "2026-10-31", check=0)
        self.assertEqual(self.read("history/periods/2026-10-31.json")["runs"], {"brand": [9001]})


class InputFileTest(StudyCase, unittest.TestCase):
    """A file that is another tool's response, or no readable file at all, is input to save
    again (exit 2), not a change in Sentl (exit 5)."""

    def setUp(self):
        super().setUp()
        self.adopt()

    def test_run_results_given_as_the_project_are_refused_naming_both_tools(self):
        proc = self.cli("detect", "--study", self.study, "--project", "brand",
                        "--saved", self.save("wrong.json", run()), check=2)
        self.assertIn("get-run-results-tool", proc.stderr)
        self.assertIn("get-project-tool", proc.stderr)

    def test_a_project_given_as_run_results_is_refused(self):
        proc = self.cli("ingest", "--study", self.study, "--project", "brand",
                        "--results", self.save("wrong.json", project()), check=2)
        self.assertIn("get-project-tool", proc.stderr)

    def test_a_run_listing_given_as_the_models_is_refused(self):
        self.answer_operator()
        self.ingest(run())
        proc = self.cli("period", "--study", self.study, "--date", "2026-10-31",
                        "--models", self.save("wrong.json", listing([(9001, "completed", "2026-10-01T06:00:00Z")])),
                        check=2)
        self.assertIn("list-runs-tool", proc.stderr)
        self.assertIn("list-ai-models", proc.stderr)

    def test_models_given_as_the_run_listing_are_refused(self):
        self.answer_operator()
        proc = self.cli("runs", "--study", self.study, "--project", "brand",
                        "--saved", self.save("wrong.json", models()), check=2)
        self.assertIn("list-ai-models", proc.stderr)

    def test_a_missing_file_is_refused(self):
        proc = self.cli("ingest", "--study", self.study, "--project", "brand",
                        "--results", self.study / "inbox" / "run-404.json", check=2)
        self.assertIn("run-404.json", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_a_folder_given_as_a_file_is_refused(self):
        self.cli("ingest", "--study", self.study, "--project", "brand", "--results", self.study / "inbox", check=2)


class ProjectShapeTest(StudyCase, unittest.TestCase):

    def adopt_refused(self, data, *fields, run_data=None):
        proc = self.cli("adopt", "--study", self.study, "--project", self.save("p.json", data),
                        "--run", self.save("r.json", run_data or run()), "--key", "brand", check=5)
        for field in fields:
            self.assertIn(field, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertFalse((self.study / "study.json").exists())
        return proc.stderr

    def test_a_renamed_grading_rubric_is_refused(self):
        data = project()
        for d in data["project"]["dimensions"]:
            renamed(d["questions"], "grading_rubric", "rubric")
        message = self.adopt_refused(data, "get-project-tool", "project.dimensions[0].questions[0].grading_rubric")
        self.assertIn("4 questions", message)

    def test_a_rubric_sent_as_a_list_is_refused(self):
        data = project()
        q = data["project"]["dimensions"][0]["questions"][0]
        q["grading_rubric"] = [q["grading_rubric"][k] for k in "12345"]
        self.adopt_refused(data, "get-project-tool", "grading_rubric", "1 to 5")

    def test_a_partial_or_missing_rubric_is_accepted_and_never_printed_as_none(self):
        data = project()
        salute, prezzo = data["project"]["dimensions"][0], data["project"]["dimensions"][1]
        salute["questions"][0]["grading_rubric"] = None
        salute["questions"][1]["grading_rubric"] = {}
        prezzo["questions"][0]["grading_rubric"] = {"1": "Prezzo sbagliato", "3": None, "5": "Prezzo corretto"}
        prezzo["questions"][0]["label"] = None
        del prezzo["questions"][0]["additional_instructions"]
        self.cli("adopt", "--study", self.study, "--project", self.save("p.json", data),
                 "--run", self.save("r.json", run()), "--key", "brand", check=0)
        self.answer_operator()
        self.ingest(run())
        self.build("2026-10-31")
        self.cli("method", "--study", self.study, "--date", "2026-10-31",
                 "--models", self.save("models.json", models()), check=0)
        report = (self.study / "reports" / "2026-10-31.md").read_text(encoding="utf-8")
        self.assertIn("Prezzo corretto", report)
        self.assertNotIn("None", report)

    def test_a_rubric_with_an_anchor_outside_1_to_5_is_refused(self):
        data = project()
        data["project"]["dimensions"][1]["questions"][0]["grading_rubric"]["6"] = "Oltre la scala"
        self.adopt_refused(data, "project.dimensions[1].questions[0].grading_rubric", "1 to 5")

    def test_a_rubric_anchor_that_is_not_text_is_refused(self):
        data = project()
        data["project"]["dimensions"][1]["questions"][0]["grading_rubric"]["3"] = 3
        self.adopt_refused(data, "project.dimensions[1].questions[0].grading_rubric")

    def test_a_renamed_question_text_is_refused(self):
        data = project()
        for d in data["project"]["dimensions"]:
            renamed(d["questions"], "question", "text")
        self.adopt_refused(data, "get-project-tool", "project.dimensions[0].questions[0].question")

    def test_a_run_with_a_renamed_field_is_refused_by_adopt(self):
        data = run()
        renamed(responses(data), "model_id", "model")
        self.adopt_refused(project(), "get-run-results-tool", "model_id", run_data=data)

    def test_detect_refuses_a_renamed_rubric_and_records_no_version(self):
        self.adopt()
        data = project()
        for d in data["project"]["dimensions"]:
            renamed(d["questions"], "grading_rubric", "rubric")
        proc = self.detect(data, "2026-11-30T12:00:00Z", check=5)
        self.assertIn("grading_rubric", proc.stderr)
        self.assertFalse((self.study / "history/versions/brand-002.json").exists())

    def test_extra_fields_are_accepted(self):
        data = project()
        data["project"]["general_rule"] = "Valuta con le fonti."
        data["project"]["organization"] = {"id": 1, "slug": "example-org", "name": "Example"}
        data["project"]["dimensions"][0]["questions"][0]["position"] = 1
        self.cli("adopt", "--study", self.study, "--project", self.save("p.json", data),
                 "--run", self.save("r.json", run()), "--key", "brand", check=0)


class ModelsShapeTest(StudyCase, unittest.TestCase):

    def test_a_models_listing_without_public_names_is_refused(self):
        self.ready()
        data = models()
        for info in data["researcher_models"].values():
            info["label"] = info.pop("name")
        proc = self.cli("period", "--study", self.study, "--date", "2026-10-31",
                        "--models", self.save("models.json", data), check=5)
        self.assertIn("list-ai-models", proc.stderr)
        self.assertIn(f"researcher_models[{GPT!r}].name", proc.stderr)


class UnexpectedErrorTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.ready()

    def period(self, *extra):
        with mock.patch.object(monitor.period, "build", side_effect=KeyError("model")):
            return self.cli("period", "--study", self.study, "--date", "2026-10-31", *extra, check=6)

    def test_an_unexpected_error_exits_6_with_one_line_and_no_traceback(self):
        proc = self.period()
        message = proc.stderr.strip()
        self.assertNotIn("Traceback", message)
        self.assertEqual(message.count("\n"), 0, message)
        self.assertIn("KeyError", message)
        self.assertIn("--debug", message)

    def test_debug_shows_the_traceback(self):
        self.assertIn("Traceback", self.period("--debug").stderr)

    def test_debug_before_the_command_shows_the_traceback(self):
        with mock.patch.object(monitor.period, "build", side_effect=KeyError("model")):
            proc = self.cli("--debug", "period", "--study", self.study, "--date", "2026-10-31", check=6)
        self.assertIn("Traceback", proc.stderr)

    def test_without_debug_no_position_turns_it_on(self):
        self.assertNotIn("Traceback", self.period().stderr)

    def test_ctrl_c_exits_130_with_one_line(self):
        with mock.patch.object(monitor.period, "build", side_effect=KeyboardInterrupt()):
            proc = self.cli("period", "--study", self.study, "--date", "2026-10-31", check=130)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.stderr.strip().count("\n"), 0, proc.stderr)
        self.assertIn("interrupted", proc.stderr)

    def test_the_environment_variable_shows_the_traceback(self):
        with mock.patch.dict(os.environ, {"SENTL_MONITOR_DEBUG": "1"}):
            self.assertIn("Traceback", self.period().stderr)

    def test_a_refusal_keeps_exit_2(self):
        self.cli("ingest", "--study", self.study, "--project", "nope",
                 "--results", self.save("r.json", run()), check=2)


if __name__ == "__main__":
    unittest.main()
