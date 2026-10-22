"""Live tier: a snapshot folder produced by running the snapshot route in an organization the operator
designates for tests: estimate, one run on the operator's go, the report, the pause.

The assistant runs the route, since only it holds the MCP connection and the operator's go for every
write and for the run; this test verifies what it left. It also settles assumption A6: a run started
by `trigger-run-tool` on a project that was never active. Opt in with RUN_LIVE=1,
SENTL_LIVE_SNAPSHOT_STUDY (the study folder, outside this repository, of a fictional subject) and
SENTL_LIVE_TEST_ORG (the slug of the test organization, which the study must name). The test prints
no organization and no account data, keeps nothing, and never starts a run: it reads the folder and
writes into a temporary copy.
"""

import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MONITOR = REPO / "skills" / "sentl-monitor" / "scripts" / "monitor.py"
ORDER = ["purpose", "dimensions", "questions", "scoring", "findings", "limits"]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@unittest.skipUnless(os.environ.get("RUN_LIVE") == "1" and os.environ.get("SENTL_LIVE_SNAPSHOT_STUDY")
                     and os.environ.get("SENTL_LIVE_TEST_ORG"),
                     "set RUN_LIVE=1, SENTL_LIVE_SNAPSHOT_STUDY and SENTL_LIVE_TEST_ORG")
class LiveSnapshotTest(unittest.TestCase):

    def setUp(self):
        self.study = Path(os.environ["SENTL_LIVE_SNAPSHOT_STUDY"]).resolve()
        self.design = read(self.study / "study.json")
        self.binding = read(self.study / "sentl.json")
        self.key = self.design["projects"][0]["key"]
        self.bound = self.binding["projects"][self.key]

    def monitor(self, *args):
        """monitor.py on a temporary copy of the folder; the output is withheld from any failure message."""
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "study"
            shutil.copytree(self.study, copy)
            return subprocess.run([sys.executable, str(MONITOR), *args, "--study", str(copy)],
                                  capture_output=True, text=True)

    def test_the_study_folder_is_outside_the_repository(self):
        self.assertFalse(self.study.is_relative_to(REPO))

    def test_the_study_names_the_test_organization_and_no_other(self):
        self.assertTrue(self.design["organization"] == os.environ["SENTL_LIVE_TEST_ORG"])
        self.assertTrue(self.binding["organization"] == os.environ["SENTL_LIVE_TEST_ORG"])

    def test_the_study_is_a_snapshot_of_one_project_with_one_round_and_no_schedule(self):
        self.assertEqual(self.design["kind"], "snapshot")
        self.assertEqual(len(self.design["projects"]), 1)
        project = self.design["projects"][0]
        self.assertEqual(project["rounds"], 1)
        self.assertNotIn("schedule", project)
        self.assertIn(len(project["dimensions"]), (4, 5))

    def test_the_cost_was_estimated_before_the_run(self):
        self.assertTrue((self.study / "inbox" / "estimate.json").is_file())

    def test_the_project_was_never_active_and_its_one_run_was_ingested(self):
        versions = sorted((self.study / "history" / "versions").glob(f"{self.key}-*.json"))
        self.assertTrue(versions)
        self.assertTrue(all(not read(v)["settings"]["active"] for v in versions), "the project was active")
        runs = sorted((self.study / "history" / "runs" / self.key).glob("*.json.gz"))
        self.assertEqual(len(runs), 1)
        with gzip.open(runs[0], "rt", encoding="utf-8") as fh:
            run = json.load(fh)
        self.assertIn(run["status"], ("completed", "completed_with_warnings"))

    def test_the_report_passes_check_in_the_snapshot_order(self):
        reports = read(self.study / "history" / "reports.json")
        self.assertEqual([e["status"] for e in reports], ["final"])
        report = self.study / reports[0]["file"]
        proc = self.monitor("check", str(report))
        self.assertEqual(proc.returncode, 0, "check refused the folder's own report (output withheld)")
        validated = self.monitor("validate", "--models", str(self.study / "inbox" / "models.json"))
        self.assertEqual(validated.returncode, 0, "validate refused the folder's snapshot (output withheld)")

    def test_the_report_holds_the_snapshot_sections_and_no_changes_section(self):
        reports = read(self.study / "history" / "reports.json")
        text = (self.study / reports[0]["file"]).read_text(encoding="utf-8")
        lang = self.design["report_language"]
        sys.path.insert(0, str(MONITOR.parent))
        from sentlmon.i18n import SECTIONS
        positions = [text.find(f". {SECTIONS[lang][k]}\n") for k in ORDER]
        self.assertTrue(all(p >= 0 for p in positions) and positions == sorted(positions))
        self.assertEqual(text.find(f". {SECTIONS[lang]['changes']}\n"), -1)

    def test_the_project_is_paused_and_closed_for_the_operator_to_archive(self):
        self.assertEqual(self.bound["closed"]["archive"], "operator")
        self.assertTrue(self.bound["closed"]["paused_at"])
        version = read(sorted((self.study / "history" / "versions").glob(f"{self.key}-*.json"))[-1])
        self.assertFalse(version["settings"]["active"], "the project was left active")


if __name__ == "__main__":
    unittest.main()
