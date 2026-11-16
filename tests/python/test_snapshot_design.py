"""A snapshot designed as a study: `validate` runs the study's checks plus the absence of a schedule and of a report
cadence, `review` prints it, and `payload` sends each project's rounds to Sentl as one snapshot."""

import json
import unittest

from design_study import READER, as_snapshot, clean_snapshot_study, mutated
from fixtures import StudyCase, listing, models
from test_design import REFUSALS, WARNINGS
from test_setup import empty_project, sentl_project

PROJECT_ID = 900
# What only a schedule or a report cadence brings: the refusal of a schedule Sentl does not offer, and the warning on
# the answers a report period pools.
SCHEDULE_ONLY = {"a schedule Sentl does not offer"}
CADENCE_ONLY = {"fewer than three answers per question and model in a report period"}


def lines(stdout, prefix):
    return sorted(line for line in stdout.splitlines() if line.startswith(prefix))


class SnapshotDesignCase(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.models = self.save("models.json", models())
        self.put(clean_snapshot_study())

    def put(self, study):
        self.design = study
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")

    def validate(self, study):
        self.put(study)
        return self.cli("validate", "--study", self.study, "--models", self.models)

    def bind(self, saved, key="brand"):
        return self.cli("bind", "--study", self.study, "--project", key, "--saved",
                        self.save("project-now.json", saved), check=0, at="2026-11-16T09:00:00Z")

    def payload(self, key="brand", saved=None, runs=None, check=0):
        args = ["payload", "--study", self.study, "--project", key, "--models", self.models]
        if saved is not None:
            args += ["--saved", self.save("project-now.json", saved),
                     "--runs", self.save("runs-now.json", runs or listing([], PROJECT_ID))]
        proc = self.cli(*args, check=check)
        return json.loads(proc.stdout) if proc.returncode == 0 else proc


class ValidateTest(SnapshotDesignCase):

    def test_a_snapshot_designed_as_a_study_validates_with_no_warning(self):
        study = clean_snapshot_study()
        self.assertEqual(len(study["projects"]), 2)
        self.assertEqual([len(d["questions"]) for d in study["projects"][0]["dimensions"]], [2] * 5)
        proc = self.validate(study)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("  warning:", proc.stdout)

    def test_each_refusal_of_a_study_is_the_same_refusal_of_the_study_as_a_snapshot(self):
        for name, (change, _) in REFUSALS.items():
            if name in SCHEDULE_ONLY:
                continue
            with self.subTest(name):
                study = self.validate(mutated(change))
                snapshot = self.validate(as_snapshot(mutated(change)))
                self.assertEqual(snapshot.returncode, study.returncode, snapshot.stdout + snapshot.stderr)
                self.assertEqual(lines(snapshot.stdout, "  - "), lines(study.stdout, "  - "))

    def test_each_warning_of_a_study_is_the_same_warning_of_the_study_as_a_snapshot(self):
        for name, (change, _) in WARNINGS.items():
            if name in CADENCE_ONLY:
                continue
            with self.subTest(name):
                study = self.validate(mutated(change))
                snapshot = self.validate(as_snapshot(mutated(change), rounds=3))
                self.assertEqual(snapshot.returncode, 0, snapshot.stdout + snapshot.stderr)
                self.assertEqual(lines(snapshot.stdout, "  warning:"), lines(study.stdout, "  warning:"))

    def test_a_schedule_is_refused(self):
        study = clean_snapshot_study()
        study["projects"][0]["schedule"] = "weekly"
        proc = self.validate(study)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("project brand: a snapshot has no schedule", proc.stdout)

    def test_a_report_cadence_is_refused(self):
        proc = self.validate({**clean_snapshot_study(), "report_every": "monthly"})
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("a snapshot has no report cadence: report_every is left out", proc.stdout)

    def test_one_round_warns_that_its_run_gives_one_answer_per_question_and_model(self):
        proc = self.validate(as_snapshot(mutated(lambda s: None), rounds=1))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("warning: project brand gives 1 answer per question and model in its run (3 or more are "
                      "expected)", proc.stdout)

    def test_a_snapshot_with_no_themes_is_checked_under_the_earlier_rules_and_the_output_says_so(self):
        proc = self.validate({**clean_snapshot_study(), "themes": []})
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("a snapshot has one project; study.json lists 2", proc.stdout)
        self.assertIn("its themes are empty", proc.stdout)


class ReviewTest(SnapshotDesignCase):

    def test_review_names_the_snapshot_its_reader_and_its_rounds_with_no_schedule(self):
        out = self.cli("review", "--study", self.study, "--models", self.models, check=0).stdout
        self.assertIn("# Snapshot review: Avenello", out)
        self.assertIn(f"- Reader: {READER}", out)
        self.assertIn("- Rounds: 3; no schedule: the snapshot is created paused", out)
        self.assertIn("## Theme inventory", out)
        self.assertNotIn("per report period", out)
        self.assertEqual((self.study / "study-review.md").read_text(encoding="utf-8").rstrip(), out.rstrip())


class PayloadTest(SnapshotDesignCase):

    def test_create_snapshot_tool_carries_the_rounds_and_no_schedule(self):
        out = self.payload()
        self.assertNotIn("create-project-tool", out)
        self.assertEqual(out["create-snapshot-tool"], {
            "organization": "example-org", "name": self.design["projects"][0]["name"],
            "researcher_model_ids": self.design["projects"][0]["models"], "rounds": 3})

    def test_at_one_round_the_create_call_leaves_the_rounds_out(self):
        self.put(as_snapshot(mutated(lambda s: None), rounds=1))
        self.assertNotIn("rounds", self.payload()["create-snapshot-tool"])

    def test_every_project_of_the_study_is_created_as_a_snapshot(self):
        out = self.payload("category")
        self.assertEqual(out["create-snapshot-tool"]["name"], self.design["projects"][1]["name"])

    def test_rounds_that_differ_from_sentls_are_sent_by_the_settings_call_without_a_schedule(self):
        self.bind(empty_project(self.design, project_id=PROJECT_ID))
        saved = sentl_project(self.design, project_id=PROJECT_ID, edit=lambda p: p.update(rounds=1))
        self.bind(saved)
        update = self.payload(saved=saved)["update-project-settings-tool"]
        self.assertEqual(update["rounds"], 3)
        self.assertEqual(update["project_id"], PROJECT_ID)
        self.assertNotIn("schedule_frequency", update)
        self.assertNotIn("is_active", update)

    def test_rounds_sentl_already_holds_ask_for_no_settings_call(self):
        self.bind(empty_project(self.design, project_id=PROJECT_ID))
        saved = sentl_project(self.design, project_id=PROJECT_ID)
        self.bind(saved)
        self.assertNotIn("update-project-settings-tool", self.payload(saved=saved))


if __name__ == "__main__":
    unittest.main()
