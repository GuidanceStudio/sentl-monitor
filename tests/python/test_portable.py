import os
import subprocess
import sys
import unittest
from pathlib import Path

from fixtures import StudyCase, models, project

MONITOR = Path(__file__).resolve().parents[2] / "skills" / "sentl-monitor" / "scripts" / "monitor.py"


class Utf8OutputTest(StudyCase, unittest.TestCase):

    def test_output_with_an_arrow_survives_a_cp1252_stream(self):
        self.adopt()
        self.detect(project(), "2026-10-02T00:00:00Z")
        changed = project()
        question = changed["project"]["dimensions"][0]["questions"][0]
        question["question"] = question["question"].replace("fa male", "è dannoso")
        saved = self.save("project-now.json", changed)
        env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
        proc = subprocess.run([sys.executable, str(MONITOR), "detect", "--study", str(self.study), "--project",
                               "brand", "--saved", str(saved), "--dry-run"],
                              env=env, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertNotIn(b"UnicodeEncodeError", proc.stderr)
        self.assertIn("→".encode("utf-8"), proc.stdout)


class ReportLanguageTest(StudyCase, unittest.TestCase):

    def unsupported(self):
        self.ready()
        self.answer_operator(report_language="de")

    def test_adopt_refuses_a_language_it_cannot_write(self):
        self.unsupported()
        proc = self.cli("adopt", "--study", self.study, "--project", self.save("p2.json", project()),
                        "--key", "second")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("report_language 'de' is not supported; supported: en, it", proc.stderr)

    def test_method_refuses_it(self):
        self.unsupported()
        proc = self.cli("method", "--study", self.study, "--date", "2026-10-31",
                        "--models", self.save("models.json", models()))
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("report_language 'de' is not supported; supported: en, it", proc.stderr)

    def test_period_refuses_it(self):
        self.unsupported()
        proc = self.cli("period", "--study", self.study, "--date", "2026-10-31")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("report_language 'de' is not supported; supported: en, it", proc.stderr)


if __name__ == "__main__":
    unittest.main()
