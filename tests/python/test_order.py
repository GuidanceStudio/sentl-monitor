"""`history/reports.json` sets the order of a report's sections; `check` records a
passing report there and verifies the `changes` section against the comparison."""

import json
import re
import unittest

from fixtures import ANSWERS, GEM, GPT, NEW, StudyCase, models, run
from test_detect import ADOPTED, FOUND, NEW_TEXT, OLD_TEXT, edited
from test_history import CHEAPER, NOV, OCT, runs
from test_method import CHANGES, FINDINGS, IT_ORDER, SUMMARY, sections

LATER_ORDER = [SUMMARY, CHANGES, FINDINGS] + IT_ORDER[:5]


def headings(text):
    return re.findall(r"^## \d+\. (.+)$", text, flags=re.M)


def reorder(text, order):
    """The report with its sections rearranged into `order`, numbered again."""
    head, *parts = re.split(r"(?=^## \d+\. )", text, flags=re.M)
    by_title = {re.match(r"## \d+\. (.+)", p).group(1): p.split("\n", 1)[1] for p in parts}
    return head + "".join(f"## {n}. {title}\n{by_title[title]}" for n, title in enumerate(order, 1))


class OrderCase(StudyCase):
    """An October history, adopted and answered, and the helpers of the order tests."""


    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101))

    def method(self, date, *extra, check=0):
        return self.cli("method", "--study", self.study, "--date", date,
                        "--models", self.save("models.json", models()), *extra, check=check)

    def report(self, date):
        return (self.study / "reports" / f"{date}.md").read_text(encoding="utf-8")

    def later(self, **kw):
        """A final report on October, then the November period and its method sections."""
        self.publish("2026-10-31")
        for n, start in enumerate(NOV):
            self.ingest(run(run_id=9201 + n, started=start, **kw), name=f"run-{9201 + n}.json")
        self.build("2026-11-30")
        self.method("2026-11-30")
        return self.study / "reports" / "2026-11-30.md"

    def fill(self, path, text="le risposte descrivono Avenello"):
        path.write_text(re.sub(r"\[\[[^\]]*\]\]", text, path.read_text(encoding="utf-8")), encoding="utf-8")


class OrderTest(OrderCase, unittest.TestCase):

    def test_a_passing_check_records_the_report_as_final(self):
        self.publish("2026-10-31")
        [entry] = self.read("history/reports.json")
        p = self.period_file("2026-10-31")
        self.assertEqual(entry, {"date": "2026-10-31", "file": "reports/2026-10-31.md", "status": "final",
                                 "period": {"from": p["from"], "to": p["to"]}, "runs": p["runs"], "previous": None})

    def test_a_failing_check_records_nothing(self):
        self.build("2026-10-31")
        self.method("2026-10-31")
        self.cli("check", "--study", self.study, self.study / "reports/2026-10-31.md", check=1)
        self.assertFalse((self.study / "history/reports.json").exists())

    def test_a_later_report_opens_with_changes_and_findings(self):
        self.assertEqual(headings(self.later().read_text(encoding="utf-8")), LATER_ORDER)

    def test_the_method_sections_of_a_later_report_are_those_of_a_first_report(self):
        later = sections(self.later().read_text(encoding="utf-8"))
        (self.study / "history/reports.json").unlink()
        self.method("2026-11-30", "--force")
        first = sections(self.report("2026-11-30"))
        self.assertEqual(headings(self.report("2026-11-30")), IT_ORDER)
        for title in IT_ORDER[:5]:
            self.assertEqual(later[title].strip(), first[title].strip(), title)

    def test_a_draft_report_leaves_the_next_one_in_the_first_order(self):
        self.build("2026-10-31")
        p = self.period_file("2026-10-31")
        (self.study / "history/reports.json").write_text(json.dumps([
            {"date": "2026-10-31", "file": "reports/2026-10-31.draft.md", "status": "draft",
             "period": {"from": p["from"], "to": p["to"]}, "runs": p["runs"], "previous": None}]), encoding="utf-8")
        for n, start in enumerate(NOV):
            self.ingest(run(run_id=9201 + n, started=start), name=f"run-{9201 + n}.json")
        self.build("2026-11-30")
        self.method("2026-11-30")
        self.assertEqual(headings(self.report("2026-11-30")), IT_ORDER)
        self.assertEqual(self.period_file("2026-11-30")["comparison"]["previous"], "2026-10-31")

    def test_check_refuses_a_later_report_in_the_first_report_order(self):
        path = self.later()
        self.fill(path)
        self.cli("check", "--study", self.study, path, check=0)
        path.write_text(reorder(path.read_text(encoding="utf-8"), IT_ORDER), encoding="utf-8")
        self.assertIn("out of order", self.cli("check", "--study", self.study, path, check=1).stdout)

    def test_check_refuses_a_first_report_in_the_later_order(self):
        self.build("2026-10-31")
        self.method("2026-10-31")
        path = self.study / "reports/2026-10-31.md"
        self.fill(path)
        path.write_text(reorder(path.read_text(encoding="utf-8"), LATER_ORDER), encoding="utf-8")
        self.assertIn("out of order", self.cli("check", "--study", self.study, path, check=1).stdout)

    def test_scoring_says_what_counts_as_a_change(self):
        self.build("2026-10-31")
        self.method("2026-10-31")
        scoring = sections(self.report("2026-10-31"))[IT_ORDER[4]]
        self.assertIn("0,3 punti", scoring)
        self.assertIn("10 punti percentuali", scoring)

    def test_changes_states_the_design_changes_in_the_report_language(self):
        self.publish("2026-10-31")
        self.detect(edited(text=NEW_TEXT, add_model=NEW), FOUND)
        for n, start in enumerate(NOV):
            self.ingest(run(run_id=9201 + n, started=start, models=[GPT, GEM, NEW],
                            texts={"salute-2": NEW_TEXT}), name=f"run-{9201 + n}.json")
        self.build("2026-11-30")
        self.method("2026-11-30")
        changes = sections(self.report("2026-11-30"))[CHANGES]
        self.assertIn(f"«{OLD_TEXT}»", changes)
        self.assertIn(f"«{NEW_TEXT}»", changes)
        self.assertIn("2 novembre 2026", changes)
        self.assertIn("Zenith Answer", changes)
        self.assertIn("Acme Chat e Orbit Reason", changes)
        self.assertIn("[[", changes)
        self.assertNotIn("prima misurazione", changes)

    def changes_report(self, text):
        path = self.later(overrides={("prezzo-1", GEM): (CHEAPER, 4, "positive", [])})
        body = path.read_text(encoding="utf-8")
        marker = re.search(r"\[\[[^\]]*\]\]", sections(body)[CHANGES]).group(0)
        path.write_text(body.replace(marker, text, 1), encoding="utf-8")
        self.fill(path)
        return path

    def test_changes_may_quote_the_previous_period_and_cite_its_comparison(self):
        text = ("Il punteggio di Prezzo passa da 2,5 a 3,5 e il giudizio di Orbit Reason sul prezzo diventa favorevole.\n\n"
                f"> {ANSWERS[('prezzo-1', GEM)][0]}\n\nOrbit Reason, nel periodo precedente.\n\n"
                f"> {CHEAPER}\n\nOrbit Reason, in questo periodo.")
        self.cli("check", "--study", self.study, self.changes_report(text), check=0)

    def test_changes_refuses_a_figure_outside_the_comparison(self):
        proc = self.cli("check", "--study", self.study,
                        self.changes_report("Il punteggio di Prezzo passa da 2,5 a 3,7."), check=1)
        self.assertIn("3,7", proc.stdout)

    def test_changes_refuses_a_quote_from_no_period(self):
        self.cli("check", "--study", self.study, self.changes_report("> Avenello costa il triplo."), check=1)


class SummaryTest(OrderCase, unittest.TestCase):
    """The summary: three to five plain sentences with figures of the period or its comparison."""

    def summary_report(self, summary, later=False):
        path = self.later(overrides={("prezzo-1", GEM): (CHEAPER, 4, "positive", [])}) if later else None
        if not later:
            self.build("2026-10-31")
            self.method("2026-10-31")
            path = self.study / "reports/2026-10-31.md"
        path.write_text(path.read_text(encoding="utf-8").replace("[[summary]]", summary), encoding="utf-8")
        self.fill(path)
        return self.cli("check", "--study", self.study, path)

    def test_the_summary_may_cite_any_dimension_s_figure(self):
        proc = self.summary_report("- Alla domanda se Avenello fa bene alla salute il punteggio medio è 4,5.\n"
                                   "- Prezzo ha un punteggio medio di 2,5.")
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_a_summary_figure_not_in_the_period_fails(self):
        proc = self.summary_report("- Salute ha un punteggio medio di 3,7.")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("3,7", proc.stdout)

    def test_the_summary_of_a_later_report_may_cite_its_comparison(self):
        proc = self.summary_report("- Il punteggio di Prezzo passa da 2,5 a 3,5.", later=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_a_summary_that_quotes_an_answer_fails(self):
        proc = self.summary_report(f"- Orbit Reason scrive:\n\n> {ANSWERS[('prezzo-1', GEM)][0]}")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("summary", proc.stdout)

    def test_the_summary_marker_left_in_place_fails(self):
        self.build("2026-10-31")
        self.method("2026-10-31")
        path = self.study / "reports/2026-10-31.md"
        report = path.read_text(encoding="utf-8").replace("[[summary]]", "@@summary@@")
        path.write_text(re.sub(r"\[\[[^\]]*\]\]", "le risposte descrivono Avenello", report)
                        .replace("@@summary@@", "[[summary]]"), encoding="utf-8")
        self.assertIn("[[", self.cli("check", "--study", self.study, path, check=1).stdout)


class RegenerateTest(OrderCase, unittest.TestCase):

    def test_a_final_report_regenerated_for_its_date_replaces_its_entry(self):
        self.publish("2026-10-31")
        for n, start in enumerate(NOV):
            self.ingest(run(run_id=9201 + n, started=start), name=f"run-{9201 + n}.json")
        self.publish("2026-11-30")
        self.method("2026-10-31", "--force")
        path = self.study / "reports/2026-10-31.md"
        self.assertEqual(headings(path.read_text(encoding="utf-8")), IT_ORDER)
        self.fill(path)
        self.cli("check", "--study", self.study, path, check=0)
        entries = self.read("history/reports.json")
        self.assertEqual([(e["date"], e["status"], e["previous"]) for e in entries],
                         [("2026-10-31", "final", None), ("2026-11-30", "final", "2026-10-31")])


if __name__ == "__main__":
    unittest.main()
