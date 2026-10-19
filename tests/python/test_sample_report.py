"""The sample report the README links still passes `check` on the study it was written from,
rebuilt from the fictional responses in sample_study.py, and its chart file is the one
`charts` writes for it (DEVPLAN R1)."""

import shutil
import tempfile
import unittest
from pathlib import Path

import sample_study
from sample_study import CHARTS, DATE, REPORT, build, cli


class SampleReportTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.study = build(Path(cls._tmp.name) / "avenello")
        cls.outline = (cls.study / "reports" / f"{DATE}.md").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_sample_report_and_charts_are_in_examples(self):
        self.assertTrue(REPORT.is_file(), f"{REPORT.relative_to(sample_study.REPO)} is missing")
        self.assertTrue(CHARTS.is_file(), f"{CHARTS.relative_to(sample_study.REPO)} is missing")

    def test_the_sample_report_passes_check(self):
        target = self.study / "reports" / f"{DATE}.md"
        try:
            shutil.copyfile(REPORT, target)
            code, out = cli("check", "--study", self.study, target)
            self.assertEqual(code, 0, out)
        finally:
            target.write_text(self.outline, encoding="utf-8")

    def test_the_sample_charts_are_what_charts_writes(self):
        code, out = cli("charts", "--study", self.study, "--date", DATE)
        self.assertEqual(code, 0, out)
        written = (self.study / "reports" / f"{DATE}.charts.md").read_text(encoding="utf-8")
        self.assertEqual(CHARTS.read_text(encoding="utf-8"), written)


if __name__ == "__main__":
    unittest.main()
