"""Live tier: a study folder produced by running the adopt and report routes
against a real Sentl project with read-only tools.

The assistant runs the routes, since only it holds the MCP connection; this test
verifies what they left. Opt in with RUN_LIVE=1, SENTL_LIVE_STUDY (the study
folder, outside this repository) and SENTL_LIVE_PROJECT (the Sentl project id).
"""

import gzip
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MONITOR = REPO / "skills" / "sentl-monitor" / "scripts" / "monitor.py"


@unittest.skipUnless(os.environ.get("RUN_LIVE") == "1" and os.environ.get("SENTL_LIVE_STUDY")
                     and os.environ.get("SENTL_LIVE_PROJECT"),
                     "set RUN_LIVE=1, SENTL_LIVE_STUDY and SENTL_LIVE_PROJECT")
class LiveReportTest(unittest.TestCase):

    def setUp(self):
        self.study = Path(os.environ["SENTL_LIVE_STUDY"]).resolve()
        self.project_id = int(os.environ["SENTL_LIVE_PROJECT"])

    def test_the_study_folder_is_outside_the_repository(self):
        self.assertFalse(self.study.is_relative_to(REPO))

    def test_the_adopted_project_is_bound(self):
        binding = json.loads((self.study / "sentl.json").read_text(encoding="utf-8"))
        self.assertIn(self.project_id, [p["project_id"] for p in binding["projects"].values()])

    def test_the_ingested_run_matched_every_response(self):
        runs = sorted((self.study / "history" / "runs").glob("*/*.json.gz"))
        self.assertTrue(runs, "no run ingested")
        with gzip.open(runs[-1], "rt", encoding="utf-8") as fh:
            run = json.load(fh)
        self.assertEqual([r for r in run["responses"] if r["match"] == "unmatched"], [])

    def test_the_latest_report_passes_check(self):
        reports = sorted(p for p in (self.study / "reports").glob("*.md") if ".draft" not in p.name)
        self.assertTrue(reports, "no report written")
        proc = subprocess.run([sys.executable, str(MONITOR), "check", "--study", str(self.study), str(reports[-1])],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
