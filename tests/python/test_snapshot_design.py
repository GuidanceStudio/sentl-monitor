"""A snapshot designed as a study: `validate` runs the study's checks plus the absence of a schedule and of a report
cadence, `review` prints it, and `payload` sends each project's rounds to Sentl as one snapshot."""

import json
import re
import unittest

from design_study import READER, as_snapshot, clean_snapshot_study, clean_study, mutated, one_snapshot, run_of
from fixtures import StudyCase, listing, models

from sentlmon import check, deck, snapcompare
from sentlmon.common import Refused, Study
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

    def bind(self, saved, key="brand", at="2026-11-16T09:00:00Z"):
        return self.cli("bind", "--study", self.study, "--project", key, "--saved",
                        self.save("project-now.json", saved), check=0, at=at)

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


class CostTest(SnapshotDesignCase):

    def review(self, *extra):
        return self.cli("review", "--study", self.study, "--models", self.models, *extra, check=0).stdout

    def test_each_snapshot_costs_its_one_run_at_its_rounds_and_at_one_round(self):
        out = self.review()
        # 10 questions x 3 rounds x (2 + 3) credits, and x 1 round.
        self.assertIn("- snapshot brand: 150 credits per run (10 questions x 3 rounds x 5 credits across 2 models); "
                      "50 credits per run at 1 round", out)
        self.assertIn("- snapshot category: 150 credits per run", out)
        self.assertIn("- all snapshots: 300 credits at the rounds proposed; 100 credits at 1 round", out)
        self.assertNotIn("per 30 days", out)
        self.assertNotIn("per report period", out)

    def test_the_cost_is_set_against_the_credits_available_at_both_rounds(self):
        self.assertIn("- available now: 250 credits, enough for every snapshot at 1 round (100 credits), not at the "
                      "rounds proposed (300 credits)", self.review("--credits-available", "250"))
        self.assertIn("- available now: 300 credits, enough for every snapshot at the rounds proposed (300 credits)",
                      self.review("--credits-available", "300"))
        self.assertIn("- available now: 90 credits, not enough for every snapshot even at 1 round (100 credits)",
                      self.review("--credits-available", "90"))

    def test_a_snapshot_has_no_monthly_budget_to_set_against_the_plan(self):
        out = self.review("--monthly-credits", "1000", "--credits-available", "500")
        self.assertNotIn("the plan gives", out)

    def test_a_snapshot_of_one_round_shows_one_figure(self):
        self.put(as_snapshot(mutated(lambda s: None), rounds=1))
        out = self.review()
        self.assertIn("- snapshot brand: 50 credits per run (10 questions x 1 round x 5 credits across 2 models)\n", out)
        self.assertIn("- all snapshots: 100 credits at the rounds proposed\n", out)


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


# --- several snapshots in one folder --------------------------------------------

IDS = {"brand": 900, "category": 901}
DATE = "2026-11-16"


class SeveralSnapshotsCase(SnapshotDesignCase):

    def create(self, key):
        """Snapshot `key` created, bound while empty, its questions saved and bound again."""
        self.bind(empty_project(self.design, key, IDS[key]), key)
        self.bind(sentl_project(self.design, key, IDS[key]), key)

    def runs(self, key, *rows):
        return self.save(f"runs-{key}.json", listing(list(rows), IDS[key]))

    def resume(self, *listings, check=0):
        args = ["resume", "--study", self.study]
        if listings:
            args += ["--runs", *listings]
        return self.cli(*args, check=check)

    def step(self, *listings):
        return re.search(r"^Next step: (\w+)", self.resume(*listings).stdout, re.M).group(1)

    def ingest(self, key, run_id, started):
        self.cli("ingest", "--study", self.study, "--project", key, "--results",
                 self.save(f"run-{run_id}.json", run_of(self.design, key, run_id, IDS[key], started)), check=0)

    def reported(self, runs):
        """The period's deck recorded as passed, as `check` records it, with the runs it read."""
        (self.study / "history").mkdir(exist_ok=True)
        (self.study / "history" / "reports.json").write_text(json.dumps([
            {"date": DATE, "status": "final", "deck": f"reports/{DATE}.deck.json", "runs": runs,
             "previous": None, "period": {"from": "2026-11-16T00:00:00Z", "to": "2026-11-16T23:00:00Z"}}]),
            encoding="utf-8")


class ResumeAcrossSnapshotsTest(SeveralSnapshotsCase):

    def test_a_snapshot_not_created_yet_is_named_and_the_folder_resumes_at_the_project(self):
        self.create("brand")
        out = self.resume().stdout
        self.assertIn("Next step: project", out)
        self.assertIn("category", out)
        self.assertNotIn("brand", out.split("\n", 1)[1])

    def test_each_bound_snapshot_needs_its_run_listing(self):
        self.create("brand")
        self.create("category")
        proc = self.resume(self.runs("brand"), check=2)
        self.assertIn("--runs", proc.stderr)
        self.assertIn("category", proc.stderr)

    def test_a_listing_of_a_project_no_snapshot_is_bound_to_is_refused(self):
        self.create("brand")
        self.create("category")
        other = self.save("runs-other.json", listing([], 111))
        self.resume(self.runs("brand"), other, check=2)

    def test_the_first_snapshot_with_no_run_is_at_cost(self):
        self.create("brand")
        self.create("category")
        out = self.resume(self.runs("brand"), self.runs("category")).stdout
        self.assertIn("Next step: cost", out)
        self.assertIn("brand", out)

    def test_an_open_run_of_one_snapshot_is_followed_and_no_other_run_starts(self):
        self.create("brand")
        self.create("category")
        out = self.resume(self.runs("brand", (7001, "researching", "2026-11-16T09:00:00Z")),
                          self.runs("category")).stdout
        self.assertIn("Next step: run", out)
        self.assertIn("run 7001 of brand", out)
        self.assertIn("do not call trigger-run-tool", out)

    def test_once_a_run_is_final_the_next_snapshot_is_at_cost(self):
        self.create("brand")
        self.create("category")
        out = self.resume(self.runs("brand", (7001, "completed", "2026-11-16T09:00:00Z")),
                          self.runs("category")).stdout
        self.assertIn("Next step: cost", out)
        self.assertIn("category", out)

    def test_a_run_that_ended_with_no_results_is_told_before_the_next_snapshot(self):
        self.create("brand")
        self.create("category")
        out = self.resume(self.runs("brand", (7001, "failed", "2026-11-16T09:00:00Z")), self.runs("category")).stdout
        self.assertIn("Next step: run", out)
        self.assertIn("run 7001 (failed)", out)

    def test_with_a_run_of_every_snapshot_the_runs_not_ingested_go_to_the_deck(self):
        self.create("brand")
        self.create("category")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        out = self.resume(self.runs("brand", (7001, "completed", "2026-11-16T09:00:00Z")),
                          self.runs("category", (7002, "completed", "2026-11-16T10:00:00Z"))).stdout
        self.assertIn("Next step: deck", out)
        self.assertIn("run 7002 of category", out)
        self.assertNotIn("run 7001", out)

    def test_a_run_started_again_by_hand_is_read_like_the_first(self):
        self.create("brand")
        self.create("category")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        self.ingest("category", 7002, "2026-11-16T10:00:00Z")
        out = self.resume(self.runs("brand", (7003, "completed", "2026-11-16T11:00:00Z"),
                                    (7001, "completed", "2026-11-16T09:00:00Z")),
                          self.runs("category", (7002, "completed", "2026-11-16T10:00:00Z"))).stdout
        self.assertIn("Next step: deck", out)
        self.assertIn("run 7003 of brand", out)

    def test_the_folder_ends_once_every_snapshot_is_closed(self):
        self.create("brand")
        self.create("category")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        self.ingest("category", 7002, "2026-11-16T10:00:00Z")
        self.reported({"brand": [7001], "category": [7002]})
        listings = (self.runs("brand", (7001, "completed", "2026-11-16T09:00:00Z")),
                    self.runs("category", (7002, "completed", "2026-11-16T10:00:00Z")))
        self.assertEqual(self.step(*listings), "end")
        self.cli("close", "--study", self.study, "--project", "brand", "--deleted", check=0)
        out = self.resume(*listings).stdout
        self.assertIn("Next step: end", out)
        self.assertIn("category", out)
        self.cli("close", "--study", self.study, "--project", "category", "--deleted", check=0)
        self.assertEqual(self.step(*listings), "done")

    def test_a_closed_snapshots_listing_is_ignored(self):
        self.create("brand")
        self.create("category")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        self.cli("close", "--study", self.study, "--project", "category", "--deleted", check=0)
        out = self.resume(self.runs("brand", (7001, "completed", "2026-11-16T09:00:00Z")),
                          self.runs("category", (7002, "failed", "2026-11-16T10:00:00Z"))).stdout
        self.assertIn("Next step: deck", out)
        self.assertNotIn("7002", out)

    def test_a_folder_whose_snapshots_were_all_deleted_before_a_run_says_so(self):
        self.put(one_snapshot(rounds=1))
        self.create("brand")
        self.cli("close", "--study", self.study, "--project", "brand", "--deleted", check=0)
        out = self.resume().stdout
        self.assertIn("Next step: done", out)
        self.assertIn("closed before a run of it was ingested", out)
        self.assertNotIn("write the deck", out)


class IngestSeveralTest(SeveralSnapshotsCase):

    def test_a_run_of_one_snapshot_under_the_key_of_another_is_refused(self):
        self.create("brand")
        self.create("category")
        proc = self.cli("ingest", "--study", self.study, "--project", "brand", "--results",
                        self.save("run-7002.json", run_of(self.design, "category", 7002, IDS["category"],
                                                          "2026-11-16T10:00:00Z")), check=2)
        for said in ("run 7002", "project 901", "brand is bound to project 900", "--project category"):
            self.assertIn(said, proc.stderr)
        self.assertFalse((self.study / "history" / "runs" / "brand" / "7002.json.gz").exists())


class CloseSeveralTest(SeveralSnapshotsCase):

    def test_close_needs_the_snapshot_when_the_folder_holds_several(self):
        self.create("brand")
        self.create("category")
        proc = self.cli("close", "--study", self.study, "--deleted", check=2)
        self.assertIn("--project", proc.stderr)

    def test_close_records_the_snapshot_it_names_and_no_other(self):
        self.create("brand")
        self.create("category")
        saved = sentl_project(self.design, "category", IDS["category"])
        self.cli("close", "--study", self.study, "--project", "category", "--saved",
                 self.save("closed.json", saved), check=0)
        bound = self.read("sentl.json")["projects"]
        self.assertEqual(bound["category"]["closed"]["how"], "kept")
        self.assertNotIn("closed", bound["brand"])


class PooledPeriodTest(SeveralSnapshotsCase):

    def period(self):
        return self.cli("period", "--study", self.study, "--date", DATE, "--models", self.models, check=0)

    def test_one_snapshot_with_three_runs_of_one_round_gives_three_answers_per_question_and_model(self):
        self.put(one_snapshot(rounds=1))
        self.create("brand")
        for n, hour in enumerate(("09", "11", "13")):
            self.ingest("brand", 7001 + n, f"2026-11-16T{hour}:00:00Z")
        self.assertIn("3 runs", self.period().stdout)
        period = self.read(f"history/periods/{DATE}.json")
        self.assertEqual(period["runs"], {"brand": [7001, 7002, 7003]})
        folder, _, study, period, doc = deck.load(self.study, DATE)
        m = deck.build_model(folder, study, period, doc)
        questions = sum(len(d["questions"]) for d in study["projects"][0]["dimensions"])
        self.assertEqual(m["method"][0]["runs"], 3)
        self.assertEqual(m["method"][0]["answers"], questions * 2 * 3)
        self.assertEqual([n for n, _ in m["spread"]], [6])
        self.assertNotEqual(deck._reading_key(m), "reading_answers_once")

    def test_the_period_pools_every_completed_run_of_every_snapshot(self):
        self.create("brand")
        self.create("category")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        self.ingest("category", 7002, "2026-11-16T10:00:00Z")
        self.ingest("category", 7003, "2026-11-16T12:00:00Z")
        self.period()
        period = self.read(f"history/periods/{DATE}.json")
        self.assertEqual(period["runs"], {"brand": [7001], "category": [7002, 7003]})
        # Each run answers every question at the design's 3 rounds, so every dimension is judged in full.
        self.assertEqual({d: e["total"]["figure"] for b in period["projects"].values() for d, e in b["dimensions"].items()},
                         {d["key"]: True for p in self.design["projects"] for d in p["dimensions"]})

    def test_a_snapshot_never_created_is_left_out_of_the_period_and_named(self):
        self.create("brand")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        out = self.period().stdout
        self.assertIn("Snapshot category is left out of the period and the deck: it is not created in Sentl", out)
        self.assertEqual(self.read(f"history/periods/{DATE}.json")["runs"], {"brand": [7001]})
        folder, _, study, period, doc = deck.load(self.study, DATE)
        self.assertEqual(len(deck.build_model(folder, study, period, doc)["method"]), 1)

    def test_a_snapshot_never_run_is_left_out_of_the_period_and_named(self):
        self.create("brand")
        self.create("category")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        out = self.period().stdout
        self.assertIn("Snapshot category is left out of the period and the deck: no run of it is ingested", out)
        self.assertNotIn("Snapshot brand", out)


LATER = "2026-11-17"


class AfterTheDeckTest(SeveralSnapshotsCase):
    """One snapshot of 1 round whose deck passed after its first run, then run twice more by hand."""

    def setUp(self):
        super().setUp()
        self.put(one_snapshot(rounds=1))
        self.create("brand")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        self.decked(DATE)
        self.ingest("brand", 7002, "2026-11-17T09:00:00Z")
        self.ingest("brand", 7003, "2026-11-17T11:00:00Z")

    def decked(self, date):
        """The period of `date` built and its deck, with one action, recorded by `check` as passed."""
        (self.study / "reports").mkdir(exist_ok=True)
        (self.study / "reports" / f"{date}.deck.json").write_text(json.dumps(
            {"schema": deck.SCHEMA, "date": date, "actions": [{"what": "Fix the price page", "read_next": "price"}]}),
            encoding="utf-8")
        self.publish(date)

    def listing(self):
        return self.runs("brand", (7003, "completed", "2026-11-17T11:00:00Z"),
                         (7002, "completed", "2026-11-17T09:00:00Z"), (7001, "completed", "2026-11-16T09:00:00Z"))

    def test_runs_ingested_after_the_deck_passed_send_the_folder_back_to_the_deck(self):
        out = self.resume(self.listing()).stdout
        self.assertIn("Next step: deck", out)
        for said in ("run 7002 of brand", "run 7003 of brand", f"the deck of {DATE}"):
            self.assertIn(said, out)
        self.assertNotIn("run 7001", out)
        self.decked(LATER)
        self.assertEqual(self.step(self.listing()), "end")

    def test_the_deck_built_again_replaces_the_snapshots_deck_and_is_no_second_edition(self):
        self.cli("period", "--study", self.study, "--date", LATER, "--models", self.models, check=0)
        folder, _, study, period, doc = deck.load(self.study, LATER)
        self.assertEqual(period["runs"], {"brand": [7001, 7002, 7003]})
        m = deck.build_model(folder, study, period, doc)
        self.assertIsNone(m["second"])
        self.assertTrue(m["first"])
        self.decked(LATER)
        self.assertEqual([e["date"] for e in self.read("history/reports.json")], [LATER])

    def test_promote_refuses_runs_the_snapshots_deck_did_not_read(self):
        proc = self.cli("promote", "--study", self.study, "--answers", self.save("follow.json", FOLLOW),
                        "--models", self.models, check=2)
        self.assertIn("run 7002 of brand, run 7003 of brand were ingested after the deck of", proc.stderr)
        self.assertIn("step 9", proc.stderr)
        self.assertEqual(self.read("study.json")["kind"], "snapshot")
        self.decked(LATER)
        self.cli("promote", "--study", self.study, "--answers", self.save("follow.json", FOLLOW),
                 "--models", self.models, check=0)


class OneSubjectBothWaysTest(SnapshotDesignCase):
    """The fixture of one fictional subject written as a study and as a snapshot."""

    def test_the_study_and_the_snapshot_carry_the_same_themes_personas_and_models(self):
        study, snap = clean_study(), clean_snapshot_study()
        for field in ("subject", "foils", "components", "market", "themes", "personas"):
            self.assertEqual(snap[field], study[field], field)
        self.assertEqual([(p["key"], p["models"], p["dimensions"]) for p in snap["projects"]],
                         [(p["key"], p["models"], p["dimensions"]) for p in study["projects"]])

    def test_they_differ_only_in_kind_schedule_report_cadence_reader_name_and_rounds(self):
        study, snap = clean_study(), clean_snapshot_study()
        self.assertEqual({k for k in study.keys() | snap.keys() if study.get(k) != snap.get(k)},
                         {"kind", "report_every", "narrative", "projects"})
        self.assertEqual({k for k in study["narrative"].keys() | snap["narrative"].keys()
                          if study["narrative"].get(k) != snap["narrative"].get(k)}, {"reader"})
        for a, b in zip(study["projects"], snap["projects"]):
            self.assertEqual({k for k in a.keys() | b.keys() if a.get(k) != b.get(k)} - {"rounds"},
                             {"schedule", "name"})

    def test_a_snapshot_cut_to_a_budget_records_what_it_left_out(self):
        snap = one_snapshot(rounds=3)
        snap["narrative"]["design_rationale"].append(
            {"choice": "The snapshot without the brand is left out",
             "reason": "The budget of 200 credits covers one snapshot at 3 rounds."})
        self.put(snap)
        self.cli("validate", "--study", self.study, "--models", self.models, check=0)
        out = self.cli("review", "--study", self.study, "--models", self.models, check=0).stdout
        self.assertIn("- Design choice: The snapshot without the brand is left out. The budget of 200 credits covers "
                      "one snapshot at 3 rounds.", out)


class CompareSeveralTest(SeveralSnapshotsCase):

    def test_compare_refuses_a_folder_of_several_snapshots_and_says_why(self):
        self.create("brand")
        self.create("category")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        self.ingest("category", 7002, "2026-11-16T10:00:00Z")
        self.cli("period", "--study", self.study, "--date", DATE, "--models", self.models, check=0)
        with self.assertRaises(Refused) as caught:
            snapcompare._Side(self.study)
        self.assertIn("brand, category", str(caught.exception))
        self.assertIn("one snapshot", str(caught.exception))

    def test_compare_reads_a_folder_of_one_snapshot_designed_as_a_study(self):
        self.put(one_snapshot(rounds=1))
        self.create("brand")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        self.cli("period", "--study", self.study, "--date", DATE, "--models", self.models, check=0)
        self.assertEqual(snapcompare._Side(self.study).project["key"], "brand")


# --- following the subject ------------------------------------------------------

FOLLOW = {"schedule": "weekly", "report_every": "monthly"}
FOLLOWED_IDS = {"brand": 950, "category": 951}
FOLLOWED_AT = "2026-11-20T09:00:00Z"


class FollowTest(SeveralSnapshotsCase):
    """`promote` on a snapshot designed as a study: the same study.json with a schedule, rounds and a report cadence,
    set up as projects; the snapshots' period is the first look the first report compares with."""

    def finished(self):
        self.create("brand")
        self.create("category")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        self.ingest("category", 7002, "2026-11-16T10:00:00Z")
        self.cli("period", "--study", self.study, "--date", DATE, "--models", self.models, check=0)
        self.reported({"brand": [7001], "category": [7002]})

    def follow(self, answers=None, check=0):
        return self.cli("promote", "--study", self.study, "--answers",
                        self.save("follow.json", FOLLOW if answers is None else answers),
                        "--models", self.models, check=check)

    def set_up_project(self, key):
        """SETUP.md on the followed study: the project created, bound while empty, its questions saved, bound again."""
        study = self.read("study.json")
        self.bind(empty_project(study, key, FOLLOWED_IDS[key]), key, at=FOLLOWED_AT)
        self.bind(sentl_project(study, key, FOLLOWED_IDS[key], first_id=3000), key, at=FOLLOWED_AT)

    def test_the_snapshot_becomes_the_same_study_with_a_schedule_and_a_report_cadence(self):
        self.finished()
        before = self.read("study.json")
        self.follow()
        after = self.read("study.json")
        self.assertEqual(after["kind"], "study")
        self.assertEqual(after["report_every"], "monthly")
        self.assertEqual([p["schedule"] for p in after["projects"]], ["weekly", "weekly"])
        self.assertEqual([p["rounds"] for p in after["projects"]], [p["rounds"] for p in before["projects"]])
        for field in ("themes", "personas", "subject", "foils"):
            self.assertEqual(after.get(field), before.get(field), field)
        self.assertEqual([[d for d in p["dimensions"]] for p in after["projects"]],
                         [[d for d in p["dimensions"]] for p in before["projects"]])
        self.assertEqual([p["models"] for p in after["projects"]], [p["models"] for p in before["projects"]])

    def test_each_project_drops_the_snapshot_from_its_name(self):
        self.finished()
        self.follow()
        names = [p["name"] for p in self.read("study.json")["projects"]]
        self.assertTrue(all(not n.startswith("Snapshot") and DATE not in n for n in names), names)

    def test_rounds_and_a_schedule_may_be_set_per_project(self):
        self.finished()
        self.follow({**FOLLOW, "schedule": {"brand": "weekly", "category": "monthly"}, "rounds": {"brand": 2}})
        projects = {p["key"]: p for p in self.read("study.json")["projects"]}
        self.assertEqual((projects["brand"]["schedule"], projects["category"]["schedule"]), ("weekly", "monthly"))
        self.assertEqual(projects["brand"]["rounds"], 2)

    def test_the_followed_study_validates(self):
        self.finished()
        self.follow()
        self.cli("validate", "--study", self.study, "--models", self.models, check=0)

    def test_the_snapshots_are_kept_aside_so_payload_creates_projects(self):
        self.finished()
        out = self.follow().stdout
        binding = self.read("sentl.json")
        self.assertEqual(binding["projects"], {})
        self.assertEqual({k: v["project_id"] for k, v in binding["snapshots"].items()}, IDS)
        created = self.payload("brand")
        self.assertIn("create-project-tool", created)
        self.assertEqual(created["create-project-tool"]["schedule_frequency"], "weekly")
        self.assertIn("payload", out)
        self.assertNotIn('"is_active": true', out)

    def test_check_still_finds_a_snapshots_id_in_the_deck(self):
        self.finished()
        self.follow()
        folder = Study(self.study)
        period = self.read(f"history/periods/{DATE}.json")
        problems = check.leaks(folder, folder.study, period, "The first look came from project 900.",
                               self.read("sentl.json"))
        self.assertIn("an id appears: 'project 900'", problems)

    def test_a_run_of_a_snapshot_set_aside_is_refused_by_the_study(self):
        self.finished()
        self.follow()
        late = self.save("run-7003.json", run_of(self.design, "brand", 7003, IDS["brand"], "2026-11-17T09:00:00Z"))
        before = self.cli("ingest", "--study", self.study, "--project", "brand", "--results", late, check=2).stderr
        self.assertIn("brand is bound to no project yet", before)
        self.set_up_project("brand")
        stderr = self.cli("ingest", "--study", self.study, "--project", "brand", "--results", late, check=2).stderr
        for said in ("run 7003", "project 900", "the snapshot brand set aside under `snapshots`",
                     "brand is bound to project 950"):
            self.assertIn(said, stderr)
        self.assertFalse((self.study / "history" / "runs" / "brand" / "7003.json.gz").exists())

    def test_a_snapshot_with_no_run_is_refused_and_nothing_is_written(self):
        self.create("brand")
        self.create("category")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        self.reported({"brand": [7001]})
        self.assertIn("category", self.follow(check=2).stderr)
        self.assertEqual(self.read("study.json")["kind"], "snapshot")
        self.assertIn("brand", self.read("sentl.json")["projects"])

    def test_a_snapshot_without_a_passing_deck_is_refused(self):
        self.create("brand")
        self.create("category")
        self.ingest("brand", 7001, "2026-11-16T09:00:00Z")
        self.ingest("category", 7002, "2026-11-16T10:00:00Z")
        self.assertIn("deck", self.follow(check=2).stderr)
        self.assertEqual(self.read("study.json")["kind"], "snapshot")

    def test_missing_or_wrong_answers_are_named_and_nothing_is_written(self):
        self.finished()
        stderr = self.follow({"schedule": "hourly", "report_every": "yearly"}, check=2).stderr
        for word in ("schedule", "report_every"):
            self.assertIn(word, stderr)
        stderr = self.follow({**FOLLOW, "schedule": {"brand": "weekly"}}, check=2).stderr
        self.assertIn("category", stderr)
        self.assertEqual(self.read("study.json")["kind"], "snapshot")

    def test_a_project_created_again_for_a_snapshot_records_no_question_as_new_or_retired(self):
        self.finished()
        self.follow()
        self.set_up_project("brand")
        versions = [json.loads(v.read_text(encoding="utf-8"))
                    for v in sorted((self.study / "history" / "versions").glob("brand-*.json"))]
        followed = [v for v in versions if v["recorded_at"] == FOLLOWED_AT]
        self.assertEqual([len(v["dimensions"]) for v in followed], [0, 5])
        changes = [c for v in followed for c in v["changes"]]
        self.assertFalse([c for c in changes if c.get("change") in ("created", "retired", "new_intent")], changes)
        self.assertEqual(self.read("sentl.json")["projects"]["brand"]["project_id"], FOLLOWED_IDS["brand"])

    def test_the_first_report_after_following_compares_with_the_snapshot(self):
        self.finished()
        self.follow()
        study = self.read("study.json")
        for key in ("brand", "category"):
            self.set_up_project(key)
        self.cli("ingest", "--study", self.study, "--project", "brand", "--results",
                 self.save("run-8001.json", run_of(study, "brand", 8001, 950, "2026-11-23T09:00:00Z", score=5,
                                                   rounds=3)),
                 check=0)
        self.cli("ingest", "--study", self.study, "--project", "category", "--results",
                 self.save("run-8002.json", run_of(study, "category", 8002, 951, "2026-11-23T10:00:00Z", score=5,
                                                   rounds=3)),
                 check=0)
        out = self.cli("period", "--study", self.study, "--date", "2026-11-23", "--models", self.models,
                       check=0).stdout
        self.assertIn(f"Compared with the period of {DATE}", out)
        period = self.read("history/periods/2026-11-23.json")
        self.assertEqual(period["runs"], {"brand": [8001], "category": [8002]})
        compared = [e for dims in period["comparison"]["dimensions"].values() for e in dims.values()]
        self.assertEqual(len(compared), 10)
        # The snapshots' answers scored 4 and the projects' 5: every dimension is compared on figures, and moved.
        self.assertEqual({e["status"] for e in compared}, {"compared"})
        self.assertTrue(all(e["mean"]["changed"] for e in compared), compared)


if __name__ == "__main__":
    unittest.main()
