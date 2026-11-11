"""Three consecutive periods on a fictional history, each recorded by its deck: a reworded question in the second
period, a criteria change and an added model in the third (DEVPLAN M2, done when)."""

import unittest

from fixtures import GEM, GPT, NEW, StudyCase, project, weekly
from test_detect import ADOPTED, NEW_TEXT, OLD_TEXT, edited
from test_history import CHEAPER, NOV, OCT, runs

PRICE = "Quanto costa il latte d'avena Avenello rispetto al latte vaccino?"
DEC = weekly("2026-12-07", 4)
CHEAPER_PRICE = {("prezzo-1", GEM): (CHEAPER, 4, "positive", ["https://prezzi.example/avena"])}


def first_two_reports(case):
    """The study adopted, then its October and November periods recorded."""
    case.adopt(at=ADOPTED)
    case.answer_operator()
    case.ingest_all(runs(OCT, 9101))
    case.detect(project(), "2026-10-31T12:00:00Z")
    case.publish("2026-10-31")

    # salute-2 is reworded in Sentl between the second and third November run.
    case.detect(edited(text=NEW_TEXT), "2026-11-30T12:00:00Z")
    case.ingest_all(runs(NOV[:2], 9201, overrides=CHEAPER_PRICE)
                    + runs(NOV[2:], 9203, overrides=CHEAPER_PRICE, texts={"salute-2": NEW_TEXT}))
    case.publish("2026-11-30")


def december_runs():
    """The December runs: Zenith Answer answers from the second one on."""
    return (runs(DEC[:1], 9301, overrides=CHEAPER_PRICE, texts={"salute-2": NEW_TEXT})
            + runs(DEC[1:], 9302, overrides=CHEAPER_PRICE, texts={"salute-2": NEW_TEXT}, models=[GPT, GEM, NEW]))


def third_report(case):
    """The December period: prezzo-1's rubric is rewritten and Zenith Answer added after the
    first December run."""
    case.detect(edited(text=NEW_TEXT, rubric="Prezzo corretto, con la fonte del listino", add_model=NEW),
                "2026-12-31T12:00:00Z")
    case.ingest_all(december_runs())
    case.publish("2026-12-31")


class ThreeReportsTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        first_two_reports(self)
        third_report(self)

    def comparison(self, date):
        return self.period_file(date)["comparison"]

    def test_every_period_is_final_and_compares_with_the_one_before(self):
        entries = self.read("history/reports.json")
        self.assertEqual([(e["date"], e["status"], e["previous"]) for e in entries],
                         [("2026-10-31", "final", None), ("2026-11-30", "final", "2026-10-31"),
                          ("2026-12-31", "final", "2026-11-30")])

    def test_the_first_period_compares_the_two_halves_of_october(self):
        halves = self.comparison("2026-10-31")["halves"]
        self.assertEqual({h: (halves[h]["from"], halves[h]["to"]) for h in ("first", "second")},
                         {"first": (OCT[0], OCT[1]), "second": (OCT[2], OCT[3])})

    def test_the_second_period_states_the_price_move_and_the_reworded_question(self):
        c = self.comparison("2026-11-30")
        prezzo = c["dimensions"]["brand"]["prezzo"]["mean"]
        self.assertEqual((prezzo["previous"], prezzo["now"]), (2.5, 3.5))
        self.assertEqual(c["design_changes"], [{"project": "brand", "change": "reworded", "question": "salute-2",
                                                "text": NEW_TEXT, "previous_text": OLD_TEXT, "since": "2026-11-16"}])

    def test_the_third_period_states_the_criteria_and_the_added_assistant(self):
        changes = self.comparison("2026-12-31")["design_changes"]
        self.assertEqual(sorted(changes, key=lambda c: c["change"]), [
            {"project": "brand", "change": "criteria", "question": "prezzo-1", "text": PRICE, "since": "2026-12-14"},
            {"project": "brand", "change": "models", "added": [NEW], "removed": [], "basis": [GPT, GEM]}])

    def test_the_third_period_compares_on_the_two_earlier_periods_and_restarts_prezzo(self):
        c = self.comparison("2026-12-31")
        self.assertEqual(c["range_of"], ["2026-10-31", "2026-11-30"])
        self.assertEqual(c["dimensions"]["brand"]["salute"]["mean"]["periods"], 2)
        self.assertEqual(c["dimensions"]["brand"]["prezzo"]["status"], "new_baseline")
        p = self.period_file("2026-12-31")
        self.assertEqual(p["versions"], {"brand": [2, 3, 3, 3]})
        self.assertEqual(p["projects"]["brand"]["dimensions"]["prezzo"]["total"]["expected"], 3 * 3)


if __name__ == "__main__":
    unittest.main()
