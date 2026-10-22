"""The snapshot route's script: `validate`, `review`, `payload` and `bind` in snapshot mode, the report a
snapshot writes (`period`, `method`, `check`), `resume`, and `close`."""

import json
import re
import unittest

from fixtures import GEM, GPT, StudyCase, listing, models
from snapshot_study import (BOUND_AT, DATE, KEY, PROJECT_ID, RUN_ID, RUN_STARTED, SCORES, clean_snapshot,
                            extra_dimension, mutated, run_results, saved_project)

TOOLS = ("create-project-tool", "update-project-settings-tool", "save-project-questions-tool")
SNAPSHOT_ORDER = ["What we did and to what end", "The dimensions and how we reached them", "The questions",
                  "How the answers are scored", "What the assistants say", "What a single run cannot show"]


def dim(study, key):
    return next(d for d in study["projects"][0]["dimensions"] if d["key"] == key)


def q(study, key):
    return dim(study, key.rsplit("-", 1)[0])["questions"][0]


def replace_last(text, old, new):
    head, _, tail = text.rpartition(old)
    return head + new + tail


def sections(text):
    parts = re.split(r"^## \d+\. (.+)$", text, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


class SnapshotCase(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.design = clean_snapshot()
        self.put(self.design)
        self.models = self.save("models.json", models())

    def put(self, study):
        self.design = study
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")

    def validate(self, study):
        self.put(study)
        return self.cli("validate", "--study", self.study, "--models", self.models)

    def bind(self, saved, check=0, at=BOUND_AT):
        return self.cli("bind", "--study", self.study, "--project", KEY, "--saved",
                        self.save("project-now.json", saved), check=check, at=at)

    def bind_empty(self):
        return self.bind(saved_project(self.design, edit=lambda p: p.update(dimensions=[])))

    def bind_full(self, edit=None):
        saved = saved_project(self.design, edit=edit)
        self.bind_empty()
        self.bind(saved)
        return saved

    def no_runs(self):
        return listing([], PROJECT_ID)

    def payload(self, saved=None, runs=None, check=0):
        args = ["payload", "--study", self.study, "--project", KEY, "--models", self.models]
        if saved is not None:
            args += ["--saved", self.save("project-now.json", saved)]
        if runs is not None:
            args += ["--runs", self.save("runs-now.json", runs)]
        proc = self.cli(*args, check=check)
        return json.loads(proc.stdout) if proc.returncode == 0 else proc

    def ingest_run(self, scores=None, run_id=RUN_ID, started=RUN_STARTED):
        return self.cli("ingest", "--study", self.study, "--project", KEY, "--results",
                        self.save(f"run-{run_id}.json", run_results(self.design, run_id, scores=scores, started=started)),
                        check=0)

    def period(self, check=0):
        return self.cli("period", "--study", self.study, "--date", DATE, "--models", self.models, check=check)

    def method(self, check=0):
        return self.cli("method", "--study", self.study, "--date", DATE, "--models", self.models, check=check)

    def report_path(self):
        return self.study / "reports" / f"{DATE}.md"

    def report(self):
        return self.report_path().read_text(encoding="utf-8")

    def write_report(self, fill="the answers describe Avenello", edit=None):
        """period, method, every [[...]] marker filled, `edit` applied to the text; check is not run."""
        self.period()
        self.method()
        text = re.sub(r"\[\[[^\]]*\]\]", fill, self.report())
        self.report_path().write_text(edit(text) if edit else text, encoding="utf-8")

    def check(self, check=None):
        return self.cli("check", "--study", self.study, self.report_path(), check=check)

    def close(self, saved, check=0):
        return self.cli("close", "--study", self.study, "--saved", self.save("project-closed.json", saved),
                        check=check, at="2026-10-22T12:00:00Z")

    def saved_paused(self, active=False):
        return saved_project(self.design, edit=lambda p: p.update(is_active=active))

    def forget_run(self):
        (self.study / "history" / "runs" / KEY / f"{RUN_ID}.json.gz").unlink()

    def final_report(self):
        self.bind_full()
        self.ingest_run()
        self.write_report()
        self.check(check=0)


# --- validate and review --------------------------------------------------------

def set_(path, value):
    def change(study):
        target = study
        for step in path[:-1]:
            target = target[step]
        target[path[-1]] = value
    return change


def drop_dimensions(study, count):
    study["projects"][0]["dimensions"] = study["projects"][0]["dimensions"][:count]


def add_dimensions(study, count):
    for n in range(count):
        study["projects"][0]["dimensions"].append(extra_dimension(n))
        study["narrative"]["design_rationale"].append({"choice": f"Extra {n}", "reason": "it adds a reading"})


def add_question(study):
    first = dim(study, "reputation")
    twin = json.loads(json.dumps(first["questions"][0]))
    twin.update(key="reputation-2", text="Is Avenello oat milk any good?")
    first["questions"].append(twin)


REFUSALS = {
    "three dimensions": (lambda s: drop_dimensions(s, 3), "3 dimensions"),
    "six dimensions": (lambda s: add_dimensions(s, 2), "6 dimensions"),
    "a dimension with two questions": (add_question, "reputation has 2 questions"),
    "a dimension with no question": (lambda s: dim(s, "price").update(questions=[]), "price has 0 questions"),
    "a catalogue id that catalogue.md does not hold": (lambda s: dim(s, "price").update(catalogue="cost"),
                                                       "catalogue id cost"),
    "a dimension with no catalogue id": (lambda s: dim(s, "price").pop("catalogue"), "price has no catalogue id"),
    "rounds above one": (set_(["projects", 0, "rounds"], 2), "rounds must be 1"),
    "a schedule": (set_(["projects", 0, "schedule"], "weekly"), "a snapshot has no schedule"),
    "two projects": (lambda s: s["projects"].append(dict(s["projects"][0], key="other")), "one project"),
    "a question over 500 characters": (lambda s: q(s, "price-1").update(text="x" * 501), "price-1: text is 501"),
    "an alias in a question marked as naming no brand": (
        lambda s: q(s, "recommendation-1").update(text="Is Avenello the best oat milk in the US?"),
        "recommendation-1 is marked as naming no brand but contains the alias Avenello"),
    "a model Sentl no longer offers": (set_(["projects", 0, "models"], [GPT, "oldco/legacy-7b"]),
                                       "oldco/legacy-7b is not in list-ai-models"),
    "a narrative without a research question": (lambda s: s["narrative"].pop("research_question"),
                                                "narrative.research_question"),
    "a narrative without a purpose": (set_(["narrative", "purpose"], " "), "narrative.purpose"),
    "a dimension that says nothing about what it measures": (lambda s: dim(s, "price").pop("measures"),
                                                              "price: measures"),
    "a dimension with no reason for its choice": (
        lambda s: s["narrative"].update(design_rationale=s["narrative"]["design_rationale"][1:]),
        "Reputation has no entry in design_rationale"),
    "two dimensions with one name": (lambda s: dim(s, "price").update(name="Health"), "two dimensions named Health"),
}


class ValidateSnapshotTest(SnapshotCase):

    def test_the_clean_snapshot_validates_with_no_warning(self):
        proc = self.validate(clean_snapshot())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("validate passed", proc.stdout)
        self.assertNotIn("warning:", proc.stdout)

    def test_five_dimensions_are_accepted(self):
        self.assertEqual(self.validate(mutated(lambda s: add_dimensions(s, 1))).returncode, 0)

    def test_each_refusal_exits_1_and_names_the_problem(self):
        for name, (change, expected) in REFUSALS.items():
            with self.subTest(name):
                proc = self.validate(mutated(change))
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertIn(expected, proc.stdout)
                self.assertIn("validate failed", proc.stdout)

    def test_every_dimension_naming_the_subject_is_a_warning_not_a_refusal(self):
        proc = self.validate(mutated(lambda s: q(s, "recommendation-1").update(branded=True)))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("warning: every dimension names the subject", proc.stdout)

    def test_the_study_rules_on_themes_pairs_and_search_lean_do_not_apply(self):
        proc = self.validate(mutated(lambda s: dim(s, "health").update(search_lean="negative")))
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_a_kind_that_is_neither_study_nor_snapshot_is_refused(self):
        proc = self.validate(mutated(lambda s: s.update(kind="survey")))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("survey", proc.stderr)


class ReviewSnapshotTest(SnapshotCase):

    def review(self, study=None):
        self.put(study or clean_snapshot())
        return self.cli("review", "--study", self.study, "--models", self.models)

    def test_it_writes_study_review_and_prints_the_same_text(self):
        proc = self.review()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.study / "study-review.md").read_text(encoding="utf-8").strip(), proc.stdout.strip())

    def test_it_shows_every_question_with_its_rubric_and_the_judge_instructions(self):
        out = self.review().stdout
        for d in clean_snapshot()["projects"][0]["dimensions"]:
            self.assertIn(d["questions"][0]["text"], out)
        for part in ("## Questions", "5. Favourable, with grounds from a named source", "2.10 USD per litre",
                     "names the brand: no"):
            self.assertIn(part, out)

    def test_it_shows_the_cost_of_the_one_run_from_the_tariffs(self):
        out = self.review().stdout
        self.assertIn("20 credits per run", out)
        self.assertNotIn("per report period", out)

    def test_it_names_the_catalogue_entry_and_the_reason_of_each_dimension(self):
        out = self.review().stdout
        self.assertIn("catalogue: health-safety", out)
        self.assertIn("the reader decides on health pages", out)

    def test_a_snapshot_that_fails_validate_is_not_reviewed(self):
        proc = self.review(mutated(lambda s: drop_dimensions(s, 3)))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("3 dimensions", proc.stderr)


# --- payload and bind -----------------------------------------------------------

def values(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from values(v)
    elif isinstance(node, list):
        for v in node:
            yield from values(v)


class PayloadSnapshotTest(SnapshotCase):

    def test_an_unbound_snapshot_gets_create_arguments_with_one_round_and_no_schedule(self):
        out = self.payload()
        self.assertEqual(sorted(k for k in out if k in TOOLS), ["create-project-tool"])
        self.assertEqual(out["create-project-tool"], {
            "organization": "example-org", "name": f"Snapshot · Avenello · {DATE}",
            "researcher_model_ids": [GPT, GEM], "rounds": 1})

    def test_the_create_arguments_do_not_activate_the_project(self):
        self.assertNotIn("is_active", self.payload()["create-project-tool"])

    def test_a_bound_snapshot_saves_one_project_with_its_four_dimensions_and_asks_for_no_settings_change(self):
        saved = self.bind_full()
        out = self.payload(saved, self.no_runs())
        self.assertNotIn("update-project-settings-tool", out)
        sent = out["save-project-questions-tool"]
        self.assertEqual(sent["project_id"], PROJECT_ID)
        self.assertEqual([len(d["questions"]) for d in sent["dimensions"]], [1, 1, 1, 1])

    def test_no_output_sets_is_active_to_true(self):
        saved = self.bind_full()
        for state in (False, True):
            out = self.payload(saved_project(self.design, edit=lambda p: p.update(is_active=state)), self.no_runs())
            self.assertNotIn(("is_active", True), list(values(out)))

    def test_an_active_snapshot_project_is_paused_by_the_settings_call(self):
        self.bind_full()
        out = self.payload(saved_project(self.design, edit=lambda p: p.update(is_active=True)), self.no_runs())
        self.assertEqual(out["update-project-settings-tool"]["is_active"], False)
        self.assertEqual(out["update-project-settings-tool"]["project_id"], PROJECT_ID)
        self.assertNotIn("schedule_frequency", out["update-project-settings-tool"])

    def test_a_schedule_found_in_sentl_is_told_to_the_operator_and_not_sent(self):
        self.bind_full()
        out = self.payload(saved_project(self.design, edit=lambda p: p.update(schedule_frequency="weekly")),
                           self.no_runs())
        self.assertNotIn("schedule_frequency", json.dumps(out["save-project-questions-tool"]))
        self.assertTrue(any("schedule" in n for n in out["notes"]), out["notes"])

    def test_a_snapshot_that_fails_validate_is_refused(self):
        self.put(mutated(lambda s: drop_dimensions(s, 3)))
        self.assertIn("3 dimensions", self.payload(check=2).stderr)

    def test_bind_records_a_snapshot_project_that_has_no_schedule(self):
        self.bind_full()
        bound = self.read("sentl.json")["projects"][KEY]
        self.assertEqual(bound["project_id"], PROJECT_ID)
        self.assertEqual(len(bound["questions"]), 4)
        self.assertIsNone(self.read(f"history/versions/{KEY}-002.json")["settings"]["schedule"])


# --- the report -----------------------------------------------------------------

class SnapshotReportTest(SnapshotCase):

    def setUp(self):
        super().setUp()
        self.bind_full()
        self.ingest_run()

    def test_method_lays_out_the_snapshot_order_with_limits_last(self):
        self.period()
        self.method()
        headings = re.findall(r"^## (\d+)\. (.+)$", self.report(), flags=re.M)
        self.assertEqual([t for _, t in headings], SNAPSHOT_ORDER)
        self.assertEqual([int(n) for n, _ in headings], list(range(1, 7)))

    def test_the_period_needs_no_report_cadence_and_has_no_comparison(self):
        self.assertNotIn("report_every", self.design)
        self.period()
        comparison = self.read(f"history/periods/{DATE}.json")["comparison"]
        self.assertIsNone(comparison["previous"])
        self.assertFalse(comparison.get("halves"))

    def test_a_run_under_the_judged_floor_is_still_the_snapshot(self):
        self.forget_run()
        self.ingest_run(scores={("reputation", GPT): 4, ("reputation", GEM): 4})
        self.period(check=0)
        self.assertEqual(self.read(f"history/periods/{DATE}.json")["runs"], {KEY: [RUN_ID]})

    def test_a_snapshot_holding_two_runs_is_refused(self):
        self.ingest_run(run_id=7002, started="2026-10-22T10:00:00Z")
        proc = self.cli("period", "--study", self.study, "--date", DATE, "--models", self.models, check=2)
        self.assertIn("one run", proc.stderr)

    def test_the_dimensions_section_says_what_each_dimension_measures_and_why_it_was_chosen(self):
        self.period()
        self.method()
        body = sections(self.report())["The dimensions and how we reached them"]
        self.assertIn("**Price**", body)
        self.assertIn("whether the assistants give the price the brand's page states", body)
        self.assertIn("the reader decides on price pages", body)

    def test_the_scoring_section_gives_no_overall_score_and_no_rule_for_changes_between_periods(self):
        self.period()
        self.method()
        body = sections(self.report())["How the answers are scored"]
        self.assertNotIn("mean of the dimensions", body)
        self.assertNotIn("Between periods", body)
        self.assertIn("names no brand", body)

    def test_the_limits_section_says_what_one_run_cannot_show(self):
        self.period()
        self.method()
        body = sections(self.report())["What a single run cannot show"]
        self.assertIn("rests on one question", body)
        self.assertIn("one answer from each assistant", body)
        self.assertIn("monitoring study", body)

    def test_method_asks_for_no_audience_and_no_cadence(self):
        study = self.read("study.json")
        self.assertNotIn("audience", study["narrative"])
        self.period()
        self.method(check=0)

    def test_a_filled_snapshot_report_passes_check(self):
        self.write_report()
        proc = self.check(check=0)
        self.assertIn("check passed", proc.stdout)
        self.assertEqual([e["status"] for e in self.read("history/reports.json")], ["final"])

    def test_check_refuses_a_changes_section(self):
        self.write_report(edit=lambda t: t + "\n## 7. What changed\n\nNothing has changed.\n")
        proc = self.check(check=1)
        self.assertIn("a snapshot report has no section What changed", proc.stdout)

    def test_check_refuses_a_summary_or_a_themes_section_too(self):
        self.write_report(edit=lambda t: t + "\n## 7. In short\n\nThe answers are favourable.\n")
        self.assertIn("a snapshot report has no section In short", self.check(check=1).stdout)

    def test_check_refuses_a_figure_for_the_whole_project(self):
        self.write_report(edit=lambda t: replace_last(t, "the answers describe Avenello", "the overall score is 3.4"))
        proc = self.check(check=1)
        self.assertIn("figure 3.4 is not in the period's figures", proc.stdout)

    def test_check_refuses_a_figure_for_the_whole_project_written_before_the_first_dimension(self):
        self.write_report(edit=lambda t: t.replace("## 5. What the assistants say\n\n",
                                                   "## 5. What the assistants say\n\nThe overall score is 3.4.\n\n"))
        self.assertIn("figure 3.4 is not in the period's figures", self.check(check=1).stdout)

    def test_check_accepts_the_figure_of_a_dimension(self):
        self.write_report(edit=lambda t: replace_last(t, "the answers describe Avenello", "the dimension scores 3.0"))
        self.check(check=0)

    def test_check_refuses_a_credit_figure(self):
        self.write_report(edit=lambda t: replace_last(t, "the answers describe Avenello", "the run cost 20 credits"))
        proc = self.check(check=1)
        self.assertIn("a credit figure appears", proc.stdout)

    def test_check_refuses_a_marker_left_to_write(self):
        self.period()
        self.method()
        self.assertIn("[[...]]", self.check(check=1).stdout)

    def test_a_dimension_under_80_percent_judged_is_shown_without_a_figure(self):
        self.forget_run()
        self.ingest_run(scores={k: v for k, v in SCORES.items() if k != ("price", GEM)})
        self.assertIn("1 of 2 answers judged, under 80%", self.period().stdout)


# --- resume and close -----------------------------------------------------------

class ResumeTest(SnapshotCase):

    def resume(self, runs=None, check=0):
        args = ["resume", "--study", self.study]
        if runs is not None:
            args += ["--runs", self.save("runs-now.json", runs)]
        return self.cli(*args, check=check)

    def step(self, runs=None):
        match = re.search(r"^Next step: (\w+)", self.resume(runs).stdout, re.M)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_a_folder_without_study_json_resumes_at_design(self):
        (self.study / "study.json").unlink()
        self.assertEqual(self.step(), "design")

    def test_a_designed_snapshot_that_is_not_bound_resumes_at_the_project(self):
        self.assertEqual(self.step(), "project")

    def test_a_project_bound_while_empty_resumes_at_the_project_to_save_its_questions(self):
        self.bind_empty()
        self.assertEqual(self.step(self.no_runs()), "project")

    def test_a_bound_project_with_no_run_resumes_at_cost_and_go(self):
        self.bind_full()
        self.assertEqual(self.step(self.no_runs()), "cost")

    def test_a_bound_project_asks_for_the_run_listing(self):
        self.bind_full()
        proc = self.resume(check=2)
        self.assertIn("--runs", proc.stderr)

    def test_an_open_run_resumes_at_following_it_and_starts_nothing(self):
        self.bind_full()
        for status in ("pending", "queued", "running"):
            with self.subTest(status):
                proc = self.resume(listing([(RUN_ID, status, RUN_STARTED)], PROJECT_ID))
                self.assertIn("Next step: run", proc.stdout)
                self.assertIn("trigger-run-tool", proc.stdout)
                self.assertIn("do not call", proc.stdout)

    def test_a_completed_run_not_in_history_resumes_at_the_report(self):
        self.bind_full()
        proc = self.resume(listing([(RUN_ID, "completed", RUN_STARTED)], PROJECT_ID))
        self.assertIn("Next step: report", proc.stdout)
        self.assertIn(f"run {RUN_ID}", proc.stdout)

    def test_a_run_ingested_without_a_final_report_resumes_at_the_report(self):
        self.bind_full()
        self.ingest_run()
        self.assertEqual(self.step(listing([(RUN_ID, "completed", RUN_STARTED)], PROJECT_ID)), "report")

    def test_a_finished_report_on_a_project_not_closed_resumes_at_the_archive(self):
        self.final_report()
        self.assertEqual(self.step(listing([(RUN_ID, "completed", RUN_STARTED)], PROJECT_ID)), "archive")

    def test_a_closed_snapshot_has_nothing_left(self):
        self.final_report()
        self.close(self.saved_paused())
        self.assertEqual(self.step(listing([(RUN_ID, "completed", RUN_STARTED)], PROJECT_ID)), "done")

    def test_a_study_that_is_not_a_snapshot_is_refused(self):
        self.put(mutated(lambda s: s.update(kind="study")))
        self.assertIn("snapshot", self.resume(check=2).stderr)

    def test_a_listing_of_another_project_is_refused(self):
        self.bind_full()
        self.resume(listing([], 111), check=2)


class CloseTest(SnapshotCase):

    def test_the_archive_step_writes_closed_with_archive_operator(self):
        self.final_report()
        self.close(self.saved_paused())
        closed = self.read("sentl.json")["projects"][KEY]["closed"]
        self.assertEqual(closed, {"paused_at": "2026-10-22T12:00:00Z", "archive": "operator"})

    def test_it_tells_the_operator_to_archive_the_project_in_the_panel(self):
        self.final_report()
        out = self.close(self.saved_paused()).stdout
        self.assertIn("web panel", out)
        self.assertIn("project-edit-link-tool", out)

    def test_a_project_still_active_is_not_closed(self):
        self.final_report()
        proc = self.close(self.saved_paused(active=True), check=2)
        self.assertIn("is_active", proc.stderr)
        self.assertNotIn("closed", self.read("sentl.json")["projects"][KEY])

    def test_closing_twice_keeps_the_first_time(self):
        self.final_report()
        self.close(self.saved_paused())
        again = self.cli("close", "--study", self.study, "--saved", self.save("p.json", self.saved_paused()),
                         check=0, at="2026-10-23T12:00:00Z")
        self.assertIn("already closed", again.stdout)
        self.assertEqual(self.read("sentl.json")["projects"][KEY]["closed"]["paused_at"], "2026-10-22T12:00:00Z")

    def test_a_project_that_is_not_bound_is_refused(self):
        self.close(self.saved_paused(), check=2)

    def test_the_saved_project_must_be_the_bound_one(self):
        self.final_report()
        self.close(saved_project(self.design, project_id=1), check=2)

    def test_a_study_that_is_not_a_snapshot_is_not_closed(self):
        self.final_report()
        self.put(mutated(lambda s: s.update(kind="study")))
        self.close(self.saved_paused(), check=2)

    def test_the_binding_keeps_its_ids_after_closing(self):
        self.final_report()
        before = self.read("sentl.json")["projects"][KEY]
        self.close(self.saved_paused())
        after = self.read("sentl.json")["projects"][KEY]
        self.assertEqual({k: v for k, v in after.items() if k != "closed"}, before)


if __name__ == "__main__":
    unittest.main()
