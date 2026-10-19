"""Live tier for the chart file of a report: `monitor.py charts` on the study's latest report
writes a profile for each project, with its radar when 3 to 12 dimensions have a value, and a
fact-currency line for each question whose fact is stated in two runs or more; every value is a figure of the period as `check` reads it; and md2, when
installed, renders every block as a chart with data, a line with two points or more and a column
with two bars or more.

The assistant runs the report route with read-only tools; this test writes only the chart file.
Opt in with RUN_LIVE=1 and SENTL_LIVE_STUDY (the study folder, outside this repository).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MONITOR = REPO / "skills" / "sentl-monitor" / "scripts" / "monitor.py"
sys.path.insert(0, str(MONITOR.parent))

from sentlmon import check  # noqa: E402
from sentlmon.compare import dimension_entries  # noqa: E402
from sentlmon.i18n import CHARTS  # noqa: E402

BLOCK = re.compile(r'^## (?P<heading>.+)\n\n:::chart (?P<type>\S+) --title "(?P<title>[^"\n]*)"\n'
                   r'(?P<table>(?:\|.*\|\n)+):::$', re.M)
RENDERED = re.compile(r'<div class="md2-chart[" ]')
# md2 draws a line of N points as N-1 cells and a column of N bars as N cells.
CELLS_NEEDED = {"line": 1, "column": 2}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@unittest.skipUnless(os.environ.get("RUN_LIVE") == "1" and os.environ.get("SENTL_LIVE_STUDY"),
                     "set RUN_LIVE=1 and SENTL_LIVE_STUDY")
class LiveChartsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.study = Path(os.environ["SENTL_LIVE_STUDY"]).resolve()
        reports = cls.study / "history" / "reports.json"
        if not reports.exists():
            raise unittest.SkipTest("no report recorded in history/reports.json")
        cls.date = load(reports)[-1]["date"]
        cls.proc = subprocess.run([sys.executable, str(MONITOR), "charts", "--study", str(cls.study),
                                   "--date", cls.date], capture_output=True, text=True)
        cls.path = cls.study / "reports" / f"{cls.date}.charts.md"
        cls.text = cls.path.read_text(encoding="utf-8") if cls.path.exists() else ""
        cls.blocks = list(BLOCK.finditer(cls.text))
        cls.period = load(cls.study / "history" / "periods" / f"{cls.date}.json")
        cls.titles = CHARTS[load(cls.study / "study.json")["report_language"]]

    def test_the_study_folder_is_outside_the_repository(self):
        self.assertFalse(self.study.is_relative_to(REPO))

    def test_the_command_writes_the_chart_file(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout + self.proc.stderr)
        self.assertTrue(self.blocks, "the chart file holds no :::chart block")

    def test_each_project_has_its_profile_and_a_radar_where_3_to_12_dimensions_have_a_value(self):
        profiles = [m for m in self.blocks if m.group("title") == self.titles["profile_title"]]
        bars = [m for m in profiles if m.group("type") == "bar"]
        radars = {(m.group("heading"), m.group("table")) for m in profiles if m.group("type") == "radar"}
        self.assertEqual(len(bars), len(self.period["projects"]), self.proc.stdout)
        drawn = [m for m in bars if 3 <= len(m.group("table").splitlines()) - 2 <= 12]
        self.assertEqual({(m.group("heading"), m.group("table")) for m in drawn}, radars)

    def test_a_question_whose_fact_is_stated_in_two_runs_or_more_has_its_line(self):
        stated = [s for b in self.period["projects"].values() for d in b["dimensions"].values()
                  for s in d["questions"].values()
                  if (s.get("facts") or {}).get("terms", {}).get("current")
                  and sum(r["total"]["current_share"] is not None for r in s["facts"]["runs"]) >= 2]
        self.assertTrue(stated, "no question of the period has its fact stated in two runs")
        self.assertEqual(sum(m.group("type") == "line" for m in self.blocks), len(stated), self.proc.stdout)

    def test_every_value_is_a_figure_of_the_period_file(self):
        comparison = self.period.get("comparison") or {}
        scopes = [s for b in self.period["projects"].values() for s in [b, *b["dimensions"].values()]]
        scopes += [q for b in self.period["projects"].values() for d in b["dimensions"].values()
                   for q in d["questions"].values()]
        entries = [e for d in dimension_entries(comparison).values() for e in [d, *d.get("questions", {}).values()]]
        decimals, percents, _ = check._allowed(scopes, check._compared(entries, comparison.get("verdict_changes", [])))
        for m in self.blocks:
            for line in m.group("table").splitlines()[2:]:
                cells = [c.strip() for c in line.strip()[1:-1].split("|")]
                for value in cells[1:]:
                    if m.group("title").endswith("(%)"):
                        self.assertIn(int(value), percents, line)
                    else:
                        self.assertIn(float(value), decimals, line)

    @unittest.skipUnless(shutil.which("md2"), "md2 is not installed")
    def test_md2_renders_every_block_as_a_chart(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "charts.md"
            shutil.copy(self.path, source)
            proc = subprocess.run(["md2", str(source)], capture_output=True, text=True, cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            html = source.with_suffix(".html").read_text(encoding="utf-8")
        starts = [m.start() for m in RENDERED.finditer(html)]
        self.assertEqual(len(starts), len(self.blocks), proc.stderr)
        for block, at, end in zip(self.blocks, starts, starts[1:] + [len(html)]):
            cells = html[at:end].count("<td")
            self.assertGreaterEqual(cells, CELLS_NEEDED.get(block.group("type"), 1), block.group("heading"))


if __name__ == "__main__":
    unittest.main()
