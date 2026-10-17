"""The first report on an adopted project rebuilds the periods before it from the
project's earlier runs (ARCHITECTURE.md §Periods)."""

import re
import unittest

from fixtures import StudyCase, models, run, weekly

ADOPTED = "2026-10-16T09:00:00Z"
TEN_WEEKS = weekly("2026-08-10", 10)  # 10 August to 12 October, ids 9101 to 9110
REBUILT_WEEKS = ["2026-09-18", "2026-09-25", "2026-10-02", "2026-10-09"]


class RebuildTest(StudyCase, unittest.TestCase):

    def history(self, starts, report_every="weekly", texts_of=None, skip=(), rounds_of=None):
        self.adopt(at=ADOPTED)
        self.answer_operator(report_every=report_every)
        for n, start in enumerate(starts):
            run_id = 9101 + n
            if run_id in skip:
                continue
            self.ingest(run(run_id=run_id, started=start, texts=(texts_of or {}).get(run_id),
                            rounds=(rounds_of or {}).get(run_id, 1)), name=f"run-{run_id}.json")

    def period_dates(self):
        return sorted(p.stem for p in (self.study / "history/periods").glob("*.json"))

    def test_ten_weekly_runs_give_the_last_week_and_four_rebuilt_weeks(self):
        self.history(TEN_WEEKS)
        proc = self.build("2026-10-16")
        p = self.period_file("2026-10-16")
        self.assertEqual(p["runs"], {"brand": [9110]})
        self.assertEqual(self.period_dates(), REBUILT_WEEKS + ["2026-10-16"])
        for date, run_id in zip(REBUILT_WEEKS, (9106, 9107, 9108, 9109)):
            earlier = self.period_file(date)
            self.assertEqual((earlier["runs"], earlier["rebuilt"]), ({"brand": [run_id]}, True))
            self.assertFalse((self.study / f"history/material/{date}.md").exists())
        self.assertNotIn("rebuilt", p)
        self.assertEqual((p["comparison"]["previous"], p["comparison"]["range_of"]), ("2026-10-09", REBUILT_WEEKS))
        self.assertEqual(p["comparison"]["dimensions"]["salute"]["mean"]["periods"], 4)
        self.assertFalse((self.study / "history/reports.json").exists())
        for date in REBUILT_WEEKS:
            self.assertIn(date, proc.stdout)

    def test_runs_before_the_adopt_version_have_no_version_and_expect_what_they_answered(self):
        self.history(TEN_WEEKS)
        snap = self.read_run("brand", 9110)
        self.assertIsNone(snap["version"])
        self.assertEqual((snap["expected"], snap["plan"]["rounds"]), (6, 1))

    def test_a_run_asked_in_an_earlier_wording_is_left_out_and_its_week_has_no_period(self):
        self.history(TEN_WEEKS, texts_of={9107: {"salute-2": "Il latte d'avena Avenello è salutare?"}})
        proc = self.build("2026-10-16")
        self.assertNotIn("2026-09-25", self.period_dates())
        self.assertIn("9107", proc.stdout)
        self.assertIn("67%", proc.stdout)
        self.assertEqual(len(self.period_file("2026-10-16")["comparison"]["range_of"]), 3)

    def test_an_unavailable_run_is_left_out_and_listed(self):
        self.history(TEN_WEEKS, skip=(9107,))
        self.cli("ingest", "--study", self.study, "--project", "brand", "--unavailable", 9107,
                 "--reason", "An internal server error occurred.", check=0)
        proc = self.build("2026-10-16")
        self.assertNotIn("2026-09-25", self.period_dates())
        self.assertRegex(proc.stdout, r"(?i)unavailable[^\n]*9107")

    def test_a_monthly_cadence_with_ten_weeks_rebuilds_the_months_that_have_runs(self):
        self.history(TEN_WEEKS, report_every="monthly")
        self.build("2026-10-16")
        self.assertEqual(self.period_dates(), ["2026-08-16", "2026-09-16", "2026-10-16"])
        self.assertEqual(self.period_file("2026-10-16")["runs"], {"brand": [9107, 9108, 9109, 9110]})
        self.assertEqual(self.period_file("2026-09-16")["runs"], {"brand": [9102, 9103, 9104, 9105, 9106]})

    def test_earlier_runs_with_one_and_three_rounds_pool_by_their_own_rounds(self):
        self.history(TEN_WEEKS, report_every="monthly", rounds_of={9109: 3, 9110: 3})
        self.build("2026-10-16")
        salute = self.period_file("2026-10-16")["projects"]["brand"]["dimensions"]["salute"]["total"]
        self.assertEqual((salute["received"], salute["expected"]), (4 + 4 + 12 + 12, 32))
        self.assertEqual(self.read_run("brand", 9110)["plan"]["rounds"], 3)

    def test_a_monthly_cadence_with_three_weeks_has_no_earlier_period_and_the_operator_is_told(self):
        self.history(TEN_WEEKS[-3:], report_every="monthly")
        proc = self.build("2026-10-16")
        self.assertEqual(self.period_dates(), ["2026-10-16"])
        self.assertIn("no earlier period", proc.stdout)
        self.assertIsNone(self.period_file("2026-10-16")["comparison"]["previous"])
        self.cli("method", "--study", self.study, "--date", "2026-10-16",
                 "--models", self.save("models.json", models()), check=0)
        report = (self.study / "reports/2026-10-16.md").read_text(encoding="utf-8")
        self.assertIn("prima misurazione", report)
        self.assertNotIn("no earlier period", report)

    def test_the_first_report_keeps_the_first_order_and_compares_with_the_rebuilt_weeks(self):
        self.history(TEN_WEEKS)
        self.build("2026-10-16")
        self.cli("method", "--study", self.study, "--date", "2026-10-16",
                 "--models", self.save("models.json", models()), check=0)
        report = (self.study / "reports/2026-10-16.md").read_text(encoding="utf-8")
        headings = re.findall(r"^## \d+\. (.+)$", report, flags=re.M)
        self.assertEqual(headings[0], "Cosa abbiamo fatto e a che scopo")
        self.assertEqual(headings[-1], "Cosa è cambiato")
        changes = report.split("Cosa è cambiato", 1)[1]
        self.assertNotIn("prima misurazione", changes)
        self.assertIn("5 ottobre 2026", changes)
        self.assertIn("[[", changes)
        (self.study / "reports/2026-10-16.md").unlink()
        self.publish("2026-10-16")
        self.assertEqual([e["date"] for e in self.read("history/reports.json")], ["2026-10-16"])
        self.assertEqual(self.read("history/reports.json")[0]["previous"], "2026-10-09")

    def test_building_the_first_period_again_replaces_the_rebuilt_periods(self):
        self.history(TEN_WEEKS)
        self.build("2026-10-16")
        self.build("2026-10-17")
        dates = self.period_dates()
        self.assertNotIn("2026-10-09", dates)
        self.assertIn("2026-10-10", dates)


if __name__ == "__main__":
    unittest.main()
