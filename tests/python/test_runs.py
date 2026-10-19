"""`runs`: from a saved list-runs-tool response, the completed runs a report needs, by start
time, the runs not final yet, statuses never seen, and a warning when the listing does not
reach back to the start of the window (Sentl's listing has no paging)."""

import re
import unittest

from fixtures import StudyCase, listing, run, weekly
from test_detect import ADOPTED

OCT = weekly("2026-10-05", 4)
NOV = weekly("2026-11-02", 5)


def fetched(proc):
    m = re.search(r"^Fetch: (.*)$", proc.stdout, re.M)
    return [int(x) for x in m.group(1).split()] if m and m.group(1) != "none" else []


def line(proc, start):
    return next((ln for ln in proc.stdout.splitlines() if ln.startswith(start)), "")


class FirstReportTest(StudyCase, unittest.TestCase):
    """A monthly first report dated 31 October reads the runs started from 1 June: its own month
    and the four before it, rebuilt for the comparison."""

    ROWS = [(9106, "completed", "2026-11-02T06:00:00Z"),
            (9104, "completed", "2026-10-26T06:00:00Z"),
            (9105, "completed_with_warnings", "2026-10-19T06:00:00Z"),
            (9103, "completed", "2026-09-07T06:00:00Z"),
            (9102, "completed", "2026-06-01T00:00:00Z"),
            (9101, "completed", "2026-05-31T23:00:00Z")]

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)
        self.answer_operator()

    def runs(self, rows, date="2026-10-31", check=0, data=None):
        return self.cli("runs", "--study", self.study, "--project", "brand",
                        "--saved", self.save("runs.json", data or listing(rows)), "--date", date, check=check)

    def test_the_completed_runs_of_the_window_by_start_time(self):
        proc = self.runs(self.ROWS)
        self.assertEqual(fetched(proc), [9102, 9103, 9105, 9104])
        self.assertIn("2026-06-01", proc.stdout)
        self.assertEqual(line(proc, "Warning"), "")

    def test_runs_already_ingested_are_not_fetched_again(self):
        self.ingest(run(run_id=9103, started="2026-09-07T06:00:00Z"))
        proc = self.runs(self.ROWS)
        self.assertEqual(fetched(proc), [9102, 9105, 9104])
        self.assertIn("Already ingested: 1", proc.stdout)

    def test_a_run_saved_by_adopt_is_pointed_to(self):
        self.save("run-9104.json", run(run_id=9104, started="2026-10-26T06:00:00Z"))
        proc = self.runs(self.ROWS)
        self.assertIn("inbox/run-9104.json", line(proc, "  run 9104"))

    def test_a_listing_that_starts_after_the_window_is_flagged(self):
        proc = self.runs([(9104, "completed", "2026-10-26T06:00:00Z"), (9103, "completed", "2026-08-03T06:00:00Z")])
        self.assertEqual(fetched(proc), [9103, 9104])
        warning = line(proc, "Warning")
        self.assertIn("2026-08-03", warning)
        self.assertIn("2026-06-01", warning)
        self.assertIn("paging", warning)

    def test_runs_not_final_and_statuses_never_seen_are_listed_apart_and_not_fetched(self):
        proc = self.runs(self.ROWS + [(9107, "running", "2026-10-31T06:00:00Z"), (9108, "pending", None),
                                      (9109, "cancelled", "2026-10-28T06:00:00Z")])
        self.assertEqual(fetched(proc), [9102, 9103, 9105, 9104])
        not_final, unseen = line(proc, "Not final yet"), line(proc, "Status never seen")
        self.assertIn("9107", not_final)
        self.assertIn("9108", not_final)
        self.assertNotIn("9109", not_final)
        self.assertIn("9109", unseen)
        self.assertIn("cancelled", unseen)
        self.assertNotIn("9107", unseen)
        self.assertNotIn("not final", unseen)

    def test_runs_outside_the_window_are_not_reported_as_open_or_unseen(self):
        proc = self.runs(self.ROWS + [(9001, "running", "2026-04-01T06:00:00Z"),
                                      (9002, "cancelled", "2026-05-01T06:00:00Z"),
                                      (9003, "cancelled", "2026-11-03T06:00:00Z"),
                                      (9108, "pending", None)])
        self.assertEqual(line(proc, "Status never seen"), "")
        not_final = line(proc, "Not final yet")
        self.assertIn("9108", not_final)
        self.assertNotIn("9001", not_final)

    def test_start_times_without_a_time_zone_are_read_as_utc(self):
        proc = self.runs([(r, s, t.removesuffix("Z")) for r, s, t in self.ROWS])
        self.assertEqual(fetched(proc), [9102, 9103, 9105, 9104])

    def test_an_unavailable_run_is_requested_again(self):
        for run_id in (9103, 9101):
            self.cli("ingest", "--study", self.study, "--project", "brand", "--unavailable", run_id,
                     "--reason", "An internal server error occurred.", check=0)
        proc = self.runs(self.ROWS)
        self.assertEqual(fetched(proc), [9101, 9102, 9103, 9105, 9104])
        self.assertIn("unavailable", line(proc, "  run 9103"))

    def test_a_listing_of_another_project_is_refused(self):
        self.runs(None, data=listing(self.ROWS, project_id=777), check=2)

    def test_without_a_report_cadence_the_window_is_unknown(self):
        self.answer_operator(report_every=None)
        proc = self.runs(self.ROWS, check=2)
        self.assertIn("report_every", proc.stderr)

    def test_a_completed_run_without_a_start_time_is_refused(self):
        proc = self.runs([(9104, "completed", None)], check=5)
        self.assertIn("list-runs-tool", proc.stderr)
        self.assertIn("runs[0].started_at", proc.stderr)

    def test_a_renamed_run_list_is_refused(self):
        data = listing(self.ROWS)
        data["items"] = data.pop("runs")
        proc = self.runs(None, data=data, check=5)
        self.assertIn("runs: missing", proc.stderr)

    def test_a_status_that_is_not_a_text_is_refused(self):
        data = listing(self.ROWS)
        data["runs"][0]["status"] = 2
        proc = self.runs(None, data=data, check=5)
        self.assertIn("runs[0].status", proc.stderr)


class LaterReportTest(StudyCase, unittest.TestCase):
    """After the report of 31 October, whose last run started on 26 October."""

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)
        self.answer_operator()
        self.ingest_all([run(run_id=9101 + n, started=s) for n, s in enumerate(OCT)])
        self.publish("2026-10-31")

    def runs(self, rows):
        return self.cli("runs", "--study", self.study, "--project", "brand",
                        "--saved", self.save("runs.json", listing(rows)), "--date", "2026-11-30", check=0)

    def test_the_runs_after_the_last_run_of_the_previous_report_up_to_the_report_date(self):
        rows = [(9206, "completed", "2026-12-07T06:00:00Z")]
        rows += [(9201 + n, "completed", s) for n, s in reversed(list(enumerate(NOV)))]
        rows += [(9110, "completed", "2026-10-28T06:00:00Z")]
        rows += [(9101 + n, "completed", s) for n, s in reversed(list(enumerate(OCT)))]
        proc = self.runs(rows)
        self.assertEqual(fetched(proc), [9110, 9201, 9202, 9203, 9204, 9205])
        self.assertEqual(line(proc, "Warning"), "")

    def test_a_listing_that_does_not_reach_the_previous_report_is_flagged(self):
        proc = self.runs([(9201 + n, "completed", s) for n, s in enumerate(NOV)])
        self.assertEqual(fetched(proc), [9201, 9202, 9203, 9204, 9205])
        warning = line(proc, "Warning")
        self.assertIn("2026-11-02", warning)
        self.assertIn("2026-10-26", warning)


class AdoptViewTest(StudyCase, unittest.TestCase):
    """Without --project, `runs` names the latest completed run for adopt; no study is needed."""

    def test_the_latest_completed_run_by_start_time_not_by_place_in_the_listing(self):
        rows = [(12, "completed", "2026-10-01T06:00:00Z"), (13, "running", "2026-10-08T06:00:00Z"),
                (11, "completed", "2026-10-02T06:00:00Z"), (10, "completed_with_warnings", "2026-09-01T06:00:00Z")]
        proc = self.cli("runs", "--study", self.study, "--saved", self.save("runs.json", listing(rows)), check=0)
        self.assertIn("Latest completed run: 11", proc.stdout)
        self.assertTrue(line(proc, "If Sentl cannot return them").endswith("newest first: 12, 10."),
                        proc.stdout)
        self.assertIn("3 completed runs", proc.stdout)
        self.assertIn("2026-09-01", proc.stdout)
        self.assertIn("13", line(proc, "Not final yet"))

    def test_a_listing_without_a_completed_run_says_so(self):
        proc = self.cli("runs", "--study", self.study,
                        "--saved", self.save("runs.json", listing([(13, "running", "2026-10-08T06:00:00Z")])), check=0)
        self.assertIn("No completed run", proc.stdout)


if __name__ == "__main__":
    unittest.main()
