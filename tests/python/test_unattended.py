"""The unattended report: `pending` decides whether any completed run is new, `period` and
`check` record why a report was not written, and history/last-report.json holds the outcome
of the latest invocation (ARCHITECTURE.md §`report`, §Scheduling, §Coverage)."""

import re
import unittest

from fixtures import GEM, StudyCase, listing, run, weekly
from test_detect import ADOPTED

OCT = weekly("2026-10-05", 4)
NOV = weekly("2026-11-02", 4)
OUTCOMES = {"written", "draft", "nothing_new", "below_floor"}


class UnattendedCase(StudyCase):

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)
        self.answer_operator()

    def last(self):
        return self.read("history/last-report.json")

    def has_last(self):
        return (self.study / "history/last-report.json").exists()

    def save_listing(self, rows):
        self.save("runs-501.json", listing(rows))

    def pending(self, date, check=0):
        return self.cli("pending", "--study", self.study, "--date", date, check=check)

    def fill(self, date):
        """method run, every [[...]] marker replaced by plain text."""
        self.cli("method", "--study", self.study, "--date", date, "--models", self.save("models.json", self.models()),
                 check=0)
        path = self.study / "reports" / f"{date}.md"
        path.write_text(re.sub(r"\[\[[^\]]*\]\]", "le risposte descrivono Avenello",
                               path.read_text(encoding="utf-8")), encoding="utf-8")
        return path

    @staticmethod
    def models():
        from fixtures import models
        return models()

    def invocation(self, date, rows, runs, unattended=True):
        """What the scheduled assistant does: save the listing, ask `pending`, and only when a
        run is new ingest, build the period and check the report. Returns the check result, or
        None when pending stopped it."""
        self.save_listing(rows)
        if self.pending(date).stdout.startswith("nothing_new"):
            return None
        self.ingest_all([r for r in runs if not (self.study / "history/runs/brand" / f"{r['run']['id']}.json.gz").exists()])
        self.build(date)
        path = self.fill(date)
        return self.cli("check", "--study", self.study, path, *(["--unattended"] if unattended else []))


def october():
    return [run(run_id=9101 + n, started=s) for n, s in enumerate(OCT)]


def october_rows():
    return [(9101 + n, "completed", s) for n, s in enumerate(OCT)]


class OutcomeTest(UnattendedCase, unittest.TestCase):

    def test_a_report_that_passes_check_records_written(self):
        self.ingest_all(october())
        self.publish("2026-10-31")
        self.assertEqual(self.last()["outcome"], "written")
        self.assertIn("2026-10-31", self.last()["detail"])

    def test_the_record_holds_the_time_the_outcome_and_a_detail(self):
        self.ingest_all(october())
        self.build("2026-10-31", check=0)
        self.cli("method", "--study", self.study, "--date", "2026-10-31", "--models",
                 self.save("models.json", self.models()), check=0)
        self.cli("check", "--study", self.study, self.study / "reports/2026-10-31.md", "--unattended", check=1,
                 at="2026-11-01T05:00:00Z")
        record = self.last()
        self.assertEqual(sorted(record), ["at", "detail", "outcome"])
        self.assertEqual(record["at"], "2026-11-01T05:00:00Z")
        self.assertIn(record["outcome"], OUTCOMES)

    def test_a_report_that_fails_check_unattended_is_saved_as_a_draft(self):
        self.ingest_all(october())
        self.build("2026-10-31")
        self.cli("method", "--study", self.study, "--date", "2026-10-31", "--models",
                 self.save("models.json", self.models()), check=0)
        proc = self.cli("check", "--study", self.study, self.study / "reports/2026-10-31.md", "--unattended", check=1)
        self.assertIn("reports/2026-10-31.draft.md", proc.stdout)
        self.assertTrue((self.study / "reports/2026-10-31.draft.md").is_file())
        self.assertFalse((self.study / "reports/2026-10-31.md").exists())
        entry = self.read("history/reports.json")[0]
        self.assertEqual((entry["status"], entry["file"]), ("draft", "reports/2026-10-31.draft.md"))
        self.assertEqual(entry["runs"], {"brand": [9101, 9102, 9103, 9104]})
        self.assertEqual(self.last()["outcome"], "draft")
        self.assertIn("left to write", self.last()["detail"])

    def test_a_report_that_fails_check_with_the_operator_present_stays_where_it_is(self):
        self.ingest_all(october())
        self.build("2026-10-31")
        self.cli("method", "--study", self.study, "--date", "2026-10-31", "--models",
                 self.save("models.json", self.models()), check=0)
        self.cli("check", "--study", self.study, self.study / "reports/2026-10-31.md", check=1)
        self.assertTrue((self.study / "reports/2026-10-31.md").is_file())
        self.assertFalse((self.study / "reports/2026-10-31.draft.md").exists())
        self.assertFalse((self.study / "history/reports.json").exists())
        self.assertFalse(self.has_last())

    def test_a_draft_that_is_fixed_and_checked_again_becomes_the_final_report(self):
        self.ingest_all(october())
        self.build("2026-10-31")
        self.cli("method", "--study", self.study, "--date", "2026-10-31", "--models",
                 self.save("models.json", self.models()), check=0)
        self.cli("check", "--study", self.study, self.study / "reports/2026-10-31.md", "--unattended", check=1)
        draft = self.study / "reports/2026-10-31.draft.md"
        fixed = self.study / "reports/2026-10-31.md"
        fixed.write_text(re.sub(r"\[\[[^\]]*\]\]", "le risposte descrivono Avenello",
                                draft.read_text(encoding="utf-8")), encoding="utf-8")
        self.cli("check", "--study", self.study, fixed, check=0)
        self.assertEqual([(e["date"], e["status"]) for e in self.read("history/reports.json")],
                         [("2026-10-31", "final")])
        self.assertEqual(self.last()["outcome"], "written")

    def test_runs_under_ninety_percent_judged_record_below_floor(self):
        self.ingest(run(overrides={("salute-2", GEM): ("Dipende.", None, "neutral", [])}))
        proc = self.build("2026-10-31", check=4)
        self.assertEqual(self.last()["outcome"], "below_floor")
        self.assertIn("83%", self.last()["detail"])
        self.assertIn("83%", proc.stdout + proc.stderr)
        self.assertFalse((self.study / "reports").exists() and list((self.study / "reports").glob("*.md")))

    def test_a_period_with_no_run_records_below_floor(self):
        self.build("2026-10-31", check=4)
        self.assertEqual(self.last()["outcome"], "below_floor")

    def test_a_run_started_after_the_last_report_is_new(self):
        self.ingest_all(october())
        self.publish("2026-10-31")
        self.save_listing(october_rows() + [(9201, "completed", NOV[0])])
        proc = self.pending("2026-11-30")
        self.assertNotIn("nothing_new", proc.stdout)
        self.assertIn("1 run to fetch", proc.stdout)
        self.assertEqual(self.last()["outcome"], "written")

    def test_no_completed_run_since_the_last_report_records_nothing_new(self):
        self.ingest_all(october())
        self.publish("2026-10-31")
        self.save_listing(october_rows())
        proc = self.pending("2026-11-30")
        self.assertTrue(proc.stdout.startswith("nothing_new"), proc.stdout)
        self.assertEqual(self.last()["outcome"], "nothing_new")
        self.assertEqual(len(self.read("history/reports.json")), 1)

    def test_a_run_not_final_yet_is_not_new(self):
        self.ingest_all(october())
        self.publish("2026-10-31")
        self.save_listing(october_rows() + [(9201, "running", NOV[0])])
        self.assertTrue(self.pending("2026-11-30").stdout.startswith("nothing_new"))

    def test_a_run_ingested_but_not_reported_is_new(self):
        self.ingest_all(october())
        self.save_listing(october_rows())
        proc = self.pending("2026-10-31")
        self.assertFalse(proc.stdout.startswith("nothing_new"), proc.stdout)
        self.assertFalse(self.has_last())

    def test_a_run_not_fetched_yet_is_new_on_a_first_report(self):
        self.save_listing(october_rows())
        self.assertFalse(self.pending("2026-10-31").stdout.startswith("nothing_new"))

    def test_pending_refuses_a_listing_that_is_missing(self):
        proc = self.pending("2026-10-31", check=2)
        self.assertIn("runs-501.json", proc.stderr)

    def test_pending_refuses_a_listing_of_another_project(self):
        self.save("runs-501.json", listing(october_rows(), project_id=777))
        self.pending("2026-10-31", check=2)


class IdempotenceTest(UnattendedCase, unittest.TestCase):

    def reports(self):
        return sorted(p.name for p in (self.study / "reports").glob("*.md"))

    def test_two_invocations_on_the_same_runs_write_one_report(self):
        first = self.invocation("2026-10-31", october_rows(), october())
        self.assertEqual(first.returncode, 0, first.stdout)
        before = (self.study / "reports/2026-10-31.md").read_bytes()
        again = self.invocation("2026-10-31", october_rows(), october())
        self.assertIsNone(again)
        self.assertEqual(self.reports(), ["2026-10-31.md"])
        self.assertEqual((self.study / "reports/2026-10-31.md").read_bytes(), before)
        self.assertEqual(len(self.read("history/reports.json")), 1)
        self.assertEqual(self.last()["outcome"], "nothing_new")

    def test_a_later_day_with_the_same_runs_still_writes_nothing(self):
        self.invocation("2026-10-31", october_rows(), october())
        self.assertIsNone(self.invocation("2026-11-03", october_rows(), october()))
        self.assertEqual(self.reports(), ["2026-10-31.md"])

    def test_a_draft_is_not_written_again_by_the_next_invocation(self):
        self.save_listing(october_rows())
        self.ingest_all(october())
        self.build("2026-10-31")
        self.cli("method", "--study", self.study, "--date", "2026-10-31", "--models",
                 self.save("models.json", self.models()), check=0)
        self.cli("check", "--study", self.study, self.study / "reports/2026-10-31.md", "--unattended", check=1)
        self.assertIsNone(self.invocation("2026-11-02", october_rows(), october()))
        self.assertEqual(self.reports(), ["2026-10-31.draft.md"])
        self.assertEqual(self.last()["outcome"], "nothing_new")

    def test_a_new_run_after_a_report_writes_the_next_one(self):
        self.invocation("2026-10-31", october_rows(), october())
        november = [run(run_id=9201 + n, started=s) for n, s in enumerate(NOV)]
        rows = october_rows() + [(9201 + n, "completed", s) for n, s in enumerate(NOV)]
        later = self.invocation("2026-11-30", rows, october() + november)
        self.assertEqual(later.returncode, 0, later.stdout)
        self.assertEqual(self.reports(), ["2026-10-31.md", "2026-11-30.md"])
        self.assertEqual(self.last()["outcome"], "written")


if __name__ == "__main__":
    unittest.main()
