"""Three consecutive reports on a fictional history: a reworded question in the second
period, a criteria change and an added model in the third (DEVPLAN M2, done when)."""

import re
import unittest

from fixtures import ANSWERS, GEM, GPT, NEW, StudyCase, project, run, weekly
from test_detect import ADOPTED, NEW_TEXT, OLD_TEXT, edited
from test_history import CHEAPER, NOV, OCT, runs
from test_method import CHANGES, FINDINGS, IT_ORDER, SUMMARY, sections
from test_order import LATER_ORDER, headings

PRICE = "Quanto costa il latte d'avena Avenello rispetto al latte vaccino?"
DEC = weekly("2026-12-07", 4)
NOVEMBER_CHANGES = (
    "Orbit Reason descrive ora Avenello come poco più caro del latte vaccino: il punteggio di Prezzo passa "
    "da 2,5 a 3,5, e il giudizio di Orbit Reason sulla domanda del prezzo passa da sfavorevole a favorevole.\n\n"
    f"> {ANSWERS[('prezzo-1', GEM)][0]}\n\n«{PRICE}», Orbit Reason, nel periodo precedente.\n\n"
    f"> {CHEAPER}\n\n«{PRICE}», Orbit Reason, in questo periodo.\n\nSalute è invariata.")
DECEMBER_CHANGES = "Salute è invariata. Prezzo ha un nuovo punto di partenza."


class ThreeReportsTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)
        self.answer_operator()
        cheaper = {("prezzo-1", GEM): (CHEAPER, 4, "positive", ["https://prezzi.example/avena"])}

        self.ingest_all(runs(OCT, 9101))
        self.detect(project(), "2026-10-31T12:00:00Z")
        self.publish("2026-10-31")

        # salute-2 is reworded in Sentl between the second and third November run.
        self.detect(edited(text=NEW_TEXT), "2026-11-30T12:00:00Z")
        self.ingest_all(runs(NOV[:2], 9201, overrides=cheaper)
                        + runs(NOV[2:], 9203, overrides=cheaper, texts={"salute-2": NEW_TEXT}))
        self.publish("2026-11-30", changes=NOVEMBER_CHANGES)

        # prezzo-1's rubric is rewritten and Zenith Answer added after the first December run.
        self.detect(edited(text=NEW_TEXT, rubric="Prezzo corretto, con la fonte del listino", add_model=NEW),
                    "2026-12-31T12:00:00Z")
        self.ingest_all(runs(DEC[:1], 9301, overrides=cheaper, texts={"salute-2": NEW_TEXT})
                        + runs(DEC[1:], 9302, overrides=cheaper, texts={"salute-2": NEW_TEXT}, models=[GPT, GEM, NEW]))
        self.publish("2026-12-31", changes=DECEMBER_CHANGES)
        self.reports = {d: (self.study / f"reports/{d}.md").read_text(encoding="utf-8")
                        for d in ("2026-10-31", "2026-11-30", "2026-12-31")}

    def changes(self, date):
        return sections(self.reports[date])[CHANGES]

    def test_the_first_report_is_in_the_first_order_and_the_later_ones_open_with_changes(self):
        self.assertEqual(headings(self.reports["2026-10-31"]), IT_ORDER)
        self.assertEqual(headings(self.reports["2026-11-30"]), LATER_ORDER)
        self.assertEqual(headings(self.reports["2026-12-31"]), LATER_ORDER)

    def test_every_report_is_final_and_compares_with_the_one_before(self):
        entries = self.read("history/reports.json")
        self.assertEqual([(e["date"], e["status"], e["previous"]) for e in entries],
                         [("2026-10-31", "final", None), ("2026-11-30", "final", "2026-10-31"),
                          ("2026-12-31", "final", "2026-11-30")])

    def test_the_first_changes_section_compares_the_two_halves_of_october(self):
        self.assertIn("la seconda metà di questo periodo, dal 19 ottobre 2026 al 26 ottobre 2026, è confrontata con "
                      "la prima, dal 5 ottobre 2026 al 12 ottobre 2026", self.changes("2026-10-31"))

    def test_the_second_changes_section_states_the_answers_then_the_reworded_question(self):
        changes = self.changes("2026-11-30")
        self.assertIn("da 2,5 a 3,5", changes)
        self.assertIn(f"«{OLD_TEXT}»", changes)
        self.assertIn(f"«{NEW_TEXT}»", changes)
        self.assertIn("16 novembre 2026", changes)
        self.assertLess(changes.index("da 2,5 a 3,5"), changes.index(f"«{NEW_TEXT}»"))

    def test_the_third_changes_section_states_the_criteria_and_the_added_assistant(self):
        changes = self.changes("2026-12-31")
        self.assertIn(f"«{PRICE}»", changes)
        self.assertIn("criteri", changes)
        self.assertIn("14 dicembre 2026", changes)
        self.assertIn("Zenith Answer", changes)
        self.assertIn("Acme Chat e Orbit Reason", changes)
        self.assertNotIn("formulazione", changes)

    def test_the_third_period_compares_on_the_two_earlier_periods_and_restarts_prezzo(self):
        c = self.period_file("2026-12-31")["comparison"]
        self.assertEqual(c["range_of"], ["2026-10-31", "2026-11-30"])
        self.assertEqual(c["dimensions"]["salute"]["mean"]["periods"], 2)
        self.assertEqual(c["dimensions"]["prezzo"]["status"], "new_baseline")
        p = self.period_file("2026-12-31")
        self.assertEqual(p["versions"], {"brand": [2, 3, 3, 3]})
        self.assertEqual(p["projects"]["brand"]["dimensions"]["prezzo"]["total"]["expected"], 3 * 3)

    def test_method_sections_close_the_later_reports_complete(self):
        for date in ("2026-11-30", "2026-12-31"):
            body = sections(self.reports[date])
            self.assertIn(NEW_TEXT, body[IT_ORDER[3]])
            self.assertIn("il team marketing di Avenello", body[IT_ORDER[4]])
            self.assertFalse(re.search(r"\[\[", self.reports[date]))


if __name__ == "__main__":
    unittest.main()
