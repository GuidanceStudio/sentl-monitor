"""Live tier: a study folder on which the report route ran twice in a row, unattended, on a
real Sentl project, the first time after a new run (a scheduled run of the project, or a manual
one the operator started). The assistant runs the route, since only it holds the MCP connection;
this test verifies what the two invocations left. Opt in with RUN_LIVE=1 and SENTL_LIVE_STUDY, the
study folder outside this repository.

Failure messages name the file and the property, never the data read from the account.
"""

import json
import os
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get("RUN_LIVE") == "1" and os.environ.get("SENTL_LIVE_STUDY"),
                     "set RUN_LIVE=1 and SENTL_LIVE_STUDY")
class LiveScheduledTest(unittest.TestCase):

    def setUp(self):
        self.study = Path(os.environ["SENTL_LIVE_STUDY"]).resolve()
        self.history = self.study / "history"

    def load(self, name):
        return json.loads((self.history / name).read_text(encoding="utf-8"))

    def test_the_study_folder_is_outside_the_repository(self):
        self.assertFalse(self.study.is_relative_to(REPO))

    def test_the_second_invocation_recorded_nothing_new(self):
        record = self.load("last-report.json")
        self.assertEqual(sorted(record), ["at", "detail", "outcome"])
        self.assertEqual(record["outcome"], "nothing_new")

    def test_the_outcome_record_holds_no_id(self):
        record = self.load("last-report.json")
        self.assertIsNone(re.search(r"\d{5,}", record["detail"]), "last-report.json detail holds an id")

    def test_the_first_invocation_wrote_a_report_that_exists(self):
        entries = self.load("reports.json")
        self.assertTrue(entries, "reports.json is empty")
        for entry in entries:
            self.assertTrue((self.study / entry["file"]).is_file(), f"{entry['file']} is missing")

    def test_no_run_is_in_two_reports(self):
        seen = set()
        for entry in self.load("reports.json"):
            ids = {(key, run_id) for key, runs in entry["runs"].items() for run_id in runs}
            self.assertFalse(seen & ids, f"two reports cover the same run: {entry['date']}")
            seen |= ids

    def test_every_report_file_has_an_entry_in_the_index(self):
        indexed = {Path(e["file"]).name for e in self.load("reports.json")}
        files = {p.name for p in (self.study / "reports").glob("*.md") if not p.name.endswith(".charts.md")}
        self.assertEqual(files - indexed, set())


if __name__ == "__main__":
    unittest.main()
