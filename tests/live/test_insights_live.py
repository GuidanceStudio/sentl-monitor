"""Live tier for the insights (DEVPLAN M2b): the first report on a real adopted project with
several weeks of runs has a deck that passes `check`, and its material holds the insight sections
the study's patterns call for (fact terms, foil domains).

The assistant runs the adopt and report routes with read-only tools; this test verifies what
they left. Opt in with RUN_LIVE=1, SENTL_LIVE_STUDY (the study folder, outside this
repository) and SENTL_LIVE_PROJECT (the Sentl project id).
"""

import datetime as dt
import gzip
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MONITOR = REPO / "skills" / "sentl-monitor" / "scripts" / "monitor.py"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@unittest.skipUnless(os.environ.get("RUN_LIVE") == "1" and os.environ.get("SENTL_LIVE_STUDY")
                     and os.environ.get("SENTL_LIVE_PROJECT"),
                     "set RUN_LIVE=1, SENTL_LIVE_STUDY and SENTL_LIVE_PROJECT")
class LiveInsightsTest(unittest.TestCase):

    def setUp(self):
        self.study = Path(os.environ["SENTL_LIVE_STUDY"]).resolve()
        project_id = int(os.environ["SENTL_LIVE_PROJECT"])
        binding = load(self.study / "sentl.json")
        self.key = next(k for k, p in binding["projects"].items() if p["project_id"] == project_id)
        reports = self.study / "history" / "reports.json"
        self.assertTrue(reports.exists(), "no report recorded in history/reports.json")
        self.first = load(reports)[0]
        self.period = load(self.study / "history" / "periods" / f"{self.first['date']}.json")
        self.material = (self.study / "history" / "material" / f"{self.first['date']}.md").read_text(encoding="utf-8")
        self.config = load(self.study / "study.json")

    def scopes(self):
        block = self.period["projects"].get(self.key, {})
        for dim in block.get("dimensions", {}).values():
            yield from dim["questions"].values()

    def test_the_study_folder_is_outside_the_repository(self):
        self.assertFalse(self.study.is_relative_to(REPO))

    def test_the_project_has_several_weeks_of_runs(self):
        starts = []
        for path in (self.study / "history" / "runs" / self.key).glob("*.json.gz"):
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                starts.append(dt.datetime.fromisoformat(json.load(fh)["started_at"].replace("Z", "+00:00")))
        self.assertGreaterEqual((max(starts) - min(starts)).days, 14, "fewer than two weeks of runs ingested")

    def test_the_first_deck_passes_check(self):
        self.assertIn("deck", self.first, "the first period has no deck recorded in history/reports.json")
        proc = subprocess.run([sys.executable, str(MONITOR), "check", "--study", str(self.study),
                               "--date", self.first["date"], str(self.study / self.first["deck"])],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_the_material_holds_the_insights_the_study_defines(self):
        has_terms = any(f.get("current") or f.get("outdated") for p in self.config["projects"]
                        for d in p["dimensions"] for q in d["questions"] for f in q.get("facts") or [])
        has_foil_domains = any(f.get("domains") for f in self.config.get("foils") or [])
        self.assertTrue(has_terms or has_foil_domains, "the study defines no fact terms and no foil domains")
        if has_terms:
            self.assertTrue(any("facts" in s for s in self.scopes()), "fact terms defined, no fact currency computed")
        if any(s.get("facts", {}).get("total", {}).get("stating") for s in self.scopes()):
            self.assertIn("##### Fact currency", self.material)
        foil_cited = any(d["total"]["authors"]["foil"] for d in self.period["projects"][self.key]["dimensions"].values())
        if has_foil_domains and foil_cited:
            self.assertIn("##### Who wrote the sources", self.material)


if __name__ == "__main__":
    unittest.main()
