"""Live tier: a study folder produced by running the setup route in an organization the operator
designates for tests: create, dry run, save, bind, and no run triggered.

The assistant runs the route, since only it holds the MCP connection and the operator's go for
every write; this test verifies what it left. Opt in with RUN_LIVE=1, SENTL_LIVE_SETUP_STUDY (the
study folder, outside this repository, of a fictional study) and SENTL_LIVE_TEST_ORG (the slug of
the test organization, which the study must name). The test prints no organization and no
account data, and keeps nothing: it reads the folder and writes into a temporary copy.
"""

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


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@unittest.skipUnless(os.environ.get("RUN_LIVE") == "1" and os.environ.get("SENTL_LIVE_SETUP_STUDY")
                     and os.environ.get("SENTL_LIVE_TEST_ORG"),
                     "set RUN_LIVE=1, SENTL_LIVE_SETUP_STUDY and SENTL_LIVE_TEST_ORG")
class LiveSetupTest(unittest.TestCase):

    def setUp(self):
        self.study = Path(os.environ["SENTL_LIVE_SETUP_STUDY"]).resolve()
        self.study_json = read(self.study / "study.json")
        self.binding = read(self.study / "sentl.json")

    def test_the_study_folder_is_outside_the_repository(self):
        self.assertFalse(self.study.is_relative_to(REPO))

    def test_the_study_names_the_test_organization_and_no_other(self):
        self.assertTrue(self.study_json["organization"] == os.environ["SENTL_LIVE_TEST_ORG"])
        self.assertTrue(self.binding["organization"] == os.environ["SENTL_LIVE_TEST_ORG"])

    def test_every_project_is_bound_with_every_question_and_a_setup_version(self):
        for project in self.study_json["projects"]:
            bound = self.binding["projects"][project["key"]]
            self.assertIsInstance(bound["project_id"], int)
            for d in project["dimensions"]:
                self.assertIn(d["key"], bound["dimensions"])
                for q in d["questions"]:
                    self.assertIn(q["key"], bound["questions"])
            version = read(self.study / "history" / "versions" / f"{project['key']}-{bound['version']:03d}.json")
            self.assertEqual(version["source"], "setup")
            self.assertFalse(version["settings"]["active"], "a test project is left paused")

    def test_the_dry_run_came_before_the_save(self):
        for project in self.study_json["projects"]:
            self.assertTrue((self.study / "inbox" / f"dry-run-{project['key']}.json").is_file())

    def test_no_run_was_triggered(self):
        self.assertFalse(list((self.study / "history" / "runs").glob("*/*.json.gz")))
        for project in self.study_json["projects"]:
            runs = read(self.study / "inbox" / f"runs-{project['key']}.json")
            self.assertEqual(runs.get("runs"), [])

    def test_the_saved_project_matches_the_study_so_payload_asks_for_no_change(self):
        for project in self.study_json["projects"]:
            key = project["key"]
            with tempfile.TemporaryDirectory() as tmp:
                copy = Path(tmp) / "study"
                shutil.copytree(self.study, copy)
                proc = subprocess.run(
                    [sys.executable, str(MONITOR), "payload", "--study", str(copy), "--project", key,
                     "--models", str(copy / "inbox" / "models.json"),
                     "--saved", str(copy / "inbox" / f"project-{key}.json"),
                     "--runs", str(copy / "inbox" / f"runs-{key}.json")],
                    capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, "payload refused the folder's own saved project (output withheld)")
            out = json.loads(proc.stdout)
            self.assertNotIn("update-project-settings-tool", out)
            bound = self.binding["projects"][key]
            sent = out["save-project-questions-tool"]["dimensions"]
            self.assertEqual(sorted(d["id"] for d in sent), sorted(bound["dimensions"].values()))
            self.assertEqual(sorted(q["id"] for d in sent for q in d["questions"]), sorted(bound["questions"].values()))


if __name__ == "__main__":
    unittest.main()
