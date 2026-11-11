"""`check` on a period's deck records the period in `history/reports.json`: a passing deck as final, a failing
one not at all, or as a draft when unattended; the next period starts after the runs of the latest entry, an
entry an earlier version wrote for its long report included."""

import json
import unittest

from fixtures import StudyCase, run
from test_detect import ADOPTED
from test_history import NOV, OCT, runs


class OrderCase(StudyCase):
    """An October history, adopted and answered."""

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101))

    def november(self):
        for n, start in enumerate(NOV):
            self.ingest(run(run_id=9201 + n, started=start), name=f"run-{9201 + n}.json")


class OrderTest(OrderCase, unittest.TestCase):

    def test_a_passing_check_records_the_period_as_final(self):
        self.publish("2026-10-31")
        [entry] = self.read("history/reports.json")
        p = self.period_file("2026-10-31")
        self.assertEqual(entry, {"date": "2026-10-31", "status": "final", "period": {"from": p["from"], "to": p["to"]},
                                 "runs": p["runs"], "previous": None, "deck": "reports/2026-10-31.deck.json"})

    def test_a_failing_check_records_nothing(self):
        self.publish("2026-10-31", problems=["a figure the period does not hold"])
        self.assertFalse((self.study / "history/reports.json").exists())

    def test_a_draft_period_is_the_previous_period_of_the_next_one(self):
        self.publish("2026-10-31", problems=["a figure the period does not hold"], unattended=True)
        self.assertEqual([(e["date"], e["status"]) for e in self.read("history/reports.json")],
                         [("2026-10-31", "draft")])
        self.november()
        self.build("2026-11-30")
        p = self.period_file("2026-11-30")
        self.assertEqual(p["runs"], {"brand": [9201, 9202, 9203, 9204, 9205]})
        self.assertEqual(p["comparison"]["previous"], "2026-10-31")

    def test_a_draft_long_report_an_earlier_version_recorded_is_the_previous_period_of_the_next_one(self):
        self.build("2026-10-31")
        p = self.period_file("2026-10-31")
        (self.study / "reports").mkdir()
        (self.study / "reports/2026-10-31.draft.md").write_text("# Rapporto di ottobre\n", encoding="utf-8")
        old = {"date": "2026-10-31", "file": "reports/2026-10-31.draft.md", "status": "draft",
               "period": {"from": p["from"], "to": p["to"]}, "runs": p["runs"], "previous": None}
        (self.study / "history/reports.json").write_text(json.dumps([old]), encoding="utf-8")
        self.november()
        self.publish("2026-11-30")
        self.assertEqual(self.period_file("2026-11-30")["runs"], {"brand": [9201, 9202, 9203, 9204, 9205]})
        first, second = self.read("history/reports.json")
        self.assertEqual(first, old)
        self.assertEqual((second["date"], second["status"], second["previous"]), ("2026-11-30", "final", "2026-10-31"))


class RegenerateTest(OrderCase, unittest.TestCase):

    def test_a_final_period_checked_again_for_its_date_replaces_its_entry(self):
        self.publish("2026-10-31")
        self.november()
        self.publish("2026-11-30")
        self.publish("2026-10-31")
        entries = self.read("history/reports.json")
        self.assertEqual([(e["date"], e["status"], e["previous"]) for e in entries],
                         [("2026-10-31", "final", None), ("2026-11-30", "final", "2026-10-31")])


if __name__ == "__main__":
    unittest.main()
