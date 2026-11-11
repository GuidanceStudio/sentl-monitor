"""Live tier for a first report on a monitor younger than its report interval: its period
compares the second half with the first, and its deck passes `check`.

The assistant runs the report route with read-only tools; this test verifies what it left.
Opt in with RUN_LIVE=1, SENTL_LIVE_STUDY (the study folder, outside this repository) and
SENTL_LIVE_PROJECT (the Sentl project id).
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MONITOR = REPO / "skills" / "sentl-monitor" / "scripts" / "monitor.py"
sys.path.insert(0, str(MONITOR.parent))

from sentlmon.compare import dimension_entries  # noqa: E402


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@unittest.skipUnless(os.environ.get("RUN_LIVE") == "1" and os.environ.get("SENTL_LIVE_STUDY")
                     and os.environ.get("SENTL_LIVE_PROJECT"),
                     "set RUN_LIVE=1, SENTL_LIVE_STUDY and SENTL_LIVE_PROJECT")
class LiveHalvesTest(unittest.TestCase):

    def setUp(self):
        self.study = Path(os.environ["SENTL_LIVE_STUDY"]).resolve()
        project_id = int(os.environ["SENTL_LIVE_PROJECT"])
        binding = load(self.study / "sentl.json")
        self.key = next(k for k, p in binding["projects"].items() if p["project_id"] == project_id)
        reports = self.study / "history" / "reports.json"
        self.assertTrue(reports.exists(), "no report recorded in history/reports.json")
        self.first = load(reports)[0]
        periods = self.study / "history" / "periods"
        self.period = load(periods / f"{self.first['date']}.json")
        self.halves = [periods / f"{self.first['date']}.{h}.json" for h in ("first", "second")]

    def test_the_study_folder_is_outside_the_repository(self):
        self.assertFalse(self.study.is_relative_to(REPO))

    def test_the_first_report_has_no_earlier_period_and_compares_the_two_halves(self):
        comparison = self.period["comparison"]
        self.assertIsNone(self.first["previous"])
        self.assertIsNone(comparison["previous"])
        self.assertIn("halves", comparison, "the first period was not split into halves")
        for path, half in zip(self.halves, ("first", "second")):
            self.assertTrue(path.exists(), f"the {half} half is not in history/periods/")
            self.assertEqual(load(path)["half"], half)
        compared = [e for (key, _), e in dimension_entries(comparison).items() if key == self.key]
        self.assertTrue(compared, "no dimension of the project is in the comparison")
        self.assertTrue(any(e["status"] == "compared" for e in compared), "no dimension is compared between the halves")

    def test_the_first_deck_passes_check(self):
        self.assertIn("deck", self.first, "the first period has no deck recorded in history/reports.json")
        proc = subprocess.run([sys.executable, str(MONITOR), "check", "--study", str(self.study),
                               "--date", self.first["date"], str(self.study / self.first["deck"])],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
