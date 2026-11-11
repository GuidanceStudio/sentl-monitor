"""The unattended report: `pending` decides whether any completed run is new, `period` and the
deck's `check` record why a report was not written, and history/last-report.json holds the
outcome of the latest invocation (ARCHITECTURE.md §`report`, §Scheduling, §Coverage)."""

import unittest

from fixtures import GEM, StudyCase, clock, listing, run, weekly
from test_detect import ADOPTED

OCT = weekly("2026-10-05", 4)
NOV = weekly("2026-11-02", 4)
OUTCOMES = {"written", "draft", "nothing_new", "below_floor"}
PROBLEM = "found title cites a figure the period does not hold"


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

    def entries(self):
        return [(e["date"], e["status"]) for e in self.read("history/reports.json")]

    def invocation(self, date, rows, runs):
        """What the scheduled assistant does: save the listing, ask `pending`, and only when a
        run is new ingest, build the period and check its deck. Returns the check result, or
        None when pending stopped it."""
        self.save_listing(rows)
        if self.pending(date).stdout.startswith("nothing_new"):
            return None
        self.ingest_all([r for r in runs if not (self.study / "history/runs/brand" / f"{r['run']['id']}.json.gz").exists()])
        return self.publish(date, unattended=True)


def october():
    return [run(run_id=9101 + n, started=s) for n, s in enumerate(OCT)]


def october_rows():
    return [(9101 + n, "completed", s) for n, s in enumerate(OCT)]


class OutcomeTest(UnattendedCase, unittest.TestCase):

    def test_a_deck_that_passes_check_records_written(self):
        self.ingest_all(october())
        self.publish("2026-10-31")
        self.assertEqual(self.last()["outcome"], "written")
        self.assertIn("2026-10-31", self.last()["detail"])

    def test_the_record_holds_the_time_the_outcome_and_a_detail(self):
        self.ingest_all(october())
        with clock("2026-11-01T05:00:00Z"):
            self.publish("2026-10-31", problems=[PROBLEM], unattended=True)
        record = self.last()
        self.assertEqual(sorted(record), ["at", "detail", "outcome"])
        self.assertEqual(record["at"], "2026-11-01T05:00:00Z")
        self.assertIn(record["outcome"], OUTCOMES)

    def test_a_deck_that_fails_check_unattended_records_its_period_as_a_draft(self):
        self.ingest_all(october())
        proc = self.publish("2026-10-31", problems=[PROBLEM], unattended=True)
        self.assertIn("recorded as a draft", proc.stdout)
        self.assertTrue((self.study / "reports/2026-10-31.deck.json").is_file())
        self.assertEqual(sorted(p.name for p in (self.study / "reports").iterdir()), ["2026-10-31.deck.json"])
        [entry] = self.read("history/reports.json")
        self.assertEqual(entry["status"], "draft")
        self.assertNotIn("file", entry)
        self.assertEqual(entry["runs"], {"brand": [9101, 9102, 9103, 9104]})
        self.assertEqual(self.last()["outcome"], "draft")
        self.assertIn(PROBLEM, self.last()["detail"])

    def test_a_deck_that_fails_check_with_the_operator_present_records_nothing(self):
        self.ingest_all(october())
        self.publish("2026-10-31", problems=[PROBLEM])
        self.assertTrue((self.study / "reports/2026-10-31.deck.json").is_file())
        self.assertFalse((self.study / "history/reports.json").exists())
        self.assertFalse(self.has_last())

    def test_a_draft_that_is_fixed_and_checked_again_becomes_final(self):
        self.ingest_all(october())
        self.publish("2026-10-31", problems=[PROBLEM], unattended=True)
        self.publish("2026-10-31")
        self.assertEqual(self.entries(), [("2026-10-31", "final")])
        self.assertEqual(self.last()["outcome"], "written")

    def test_runs_under_ninety_percent_judged_record_below_floor(self):
        self.ingest(run(overrides={("salute-2", GEM): ("Dipende.", None, "neutral", [])}))
        proc = self.build("2026-10-31", check=4)
        self.assertEqual(self.last()["outcome"], "below_floor")
        self.assertIn("83%", self.last()["detail"])
        self.assertIn("83%", proc.stdout + proc.stderr)
        self.assertFalse((self.study / "reports").exists())

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

    def test_two_invocations_on_the_same_runs_record_one_period(self):
        first = self.invocation("2026-10-31", october_rows(), october())
        self.assertEqual(first.returncode, 0, first.stdout)
        deck = self.study / "reports/2026-10-31.deck.json"
        before = deck.read_bytes()
        again = self.invocation("2026-10-31", october_rows(), october())
        self.assertIsNone(again)
        self.assertEqual(self.entries(), [("2026-10-31", "final")])
        self.assertEqual(deck.read_bytes(), before)
        self.assertEqual(self.last()["outcome"], "nothing_new")

    def test_a_later_day_with_the_same_runs_still_records_nothing(self):
        self.invocation("2026-10-31", october_rows(), october())
        self.assertIsNone(self.invocation("2026-11-03", october_rows(), october()))
        self.assertEqual(self.entries(), [("2026-10-31", "final")])

    def test_a_draft_is_not_written_again_by_the_next_invocation(self):
        self.save_listing(october_rows())
        self.ingest_all(october())
        self.publish("2026-10-31", problems=[PROBLEM], unattended=True)
        self.assertIsNone(self.invocation("2026-11-02", october_rows(), october()))
        self.assertEqual(self.entries(), [("2026-10-31", "draft")])
        self.assertEqual(self.last()["outcome"], "nothing_new")

    def test_a_new_run_after_a_report_records_the_next_period(self):
        self.invocation("2026-10-31", october_rows(), october())
        november = [run(run_id=9201 + n, started=s) for n, s in enumerate(NOV)]
        rows = october_rows() + [(9201 + n, "completed", s) for n, s in enumerate(NOV)]
        later = self.invocation("2026-11-30", rows, october() + november)
        self.assertEqual(later.returncode, 0, later.stdout)
        self.assertEqual(self.entries(), [("2026-10-31", "final"), ("2026-11-30", "final")])
        self.assertEqual(self.last()["outcome"], "written")


if __name__ == "__main__":
    unittest.main()
