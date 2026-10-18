"""`monitor.py charts` writes a report's figures as md2 `:::chart` tables for a deck
(ARCHITECTURE.md §Charts for a deck)."""

import collections
import json
import re
import unittest

from fixtures import CHOICE_Q, GEM, GPT, NEW, PRICE_Q, WORK_Q, market_project, project, results, run
from sentlmon import check
from sentlmon.compare import dimension_entries
from sentlmon.common import round_half_up
from sentlmon.i18n import CHARTS, TEXT
from test_detect import ADOPTED, FOUND, NEW_TEXT, OLD_TEXT, edited
from test_halves import REPORT, HalvesCase, day, rows_of
from test_history import NOV, OCT, runs

T = CHARTS["it"]
MD2_TYPES = {"bar", "column", "line", "pie", "stacked-bar", "stacked-column", "radar"}
BLOCK = re.compile(r'^## (?P<heading>.+)\n\n:::chart (?P<type>\S+) --title "(?P<title>[^"\n]*)"\n'
                   r'(?P<table>(?:\|.*\|\n)+):::$', re.M)
Chart = collections.namedtuple("Chart", "heading type title header separator rows")
SEPTEMBER = [(9050 + n, f"2026-09-{d:02d}T06:00:00Z") for n, d in enumerate((7, 14, 21, 28))]


def mean(value):
    return f"{round_half_up(value, 1):.1f}"


def pct(ratio):
    return str(int(round_half_up(ratio * 100, 0)))


def blocks(text):
    out = []
    for m in BLOCK.finditer(text):
        cells = [[c.strip() for c in line.strip()[1:-1].split("|")] for line in m.group("table").splitlines()]
        out.append(Chart(m.group("heading"), m.group("type"), m.group("title"), cells[0], cells[1], cells[2:]))
    return out


def left_out(stdout):
    """The part of the command's output that lists what was left out."""
    return stdout.partition("Left out")[2]


class ChartsCase(HalvesCase):

    def charts(self, date=REPORT, check=0):
        proc = self.cli("charts", "--study", self.study, "--date", date, check=check)
        path = self.study / "reports" / f"{date}.charts.md"
        return proc, path.read_text(encoding="utf-8") if path.exists() else ""

    def asked(self, date=REPORT, key="market"):
        return self.period_file(date)["asked"][key]

    def profile(self, found):
        return ([b for b in found if b.type == "radar"],
                [b for b in found if b.type == "bar" and b.title == T["profile_title"]])


class ProfileTest(ChartsCase, unittest.TestCase):

    def test_two_periods_carry_each_period_s_dimension_means(self):
        self.history(extra=SEPTEMBER)
        self.build(REPORT)
        [radar], [bar] = self.profile(blocks(self.charts()[1]))
        before, now = (self.period_file(d)["projects"]["market"]["dimensions"] for d in ("2026-09-30", REPORT))
        expected = [[d["name"], mean(before[d["key"]]["total"]["mean"]), mean(now[d["key"]]["total"]["mean"])]
                    for d in self.asked()]
        self.assertEqual([r[0] for r in expected], ["Prezzo", "Scelta", "Lavoro"])
        self.assertEqual(expected[1][1:], ["3.0", "3.2"])
        self.assertEqual(radar.header, [T["dimension"], "7–28 settembre 2026", "8–31 ottobre 2026"])
        self.assertEqual(radar.rows, expected)
        self.assertEqual((bar.header, bar.rows), (radar.header, expected))

    def test_a_report_on_the_two_halves_carries_each_half_s_dimension_means(self):
        self.history()
        self.build(REPORT)
        [radar], [bar] = self.profile(blocks(self.charts()[1]))
        first, second = (self.read(f"history/periods/{REPORT}.{h}.json")["projects"]["market"]["dimensions"]
                         for h in ("first", "second"))
        expected = [[d["name"], mean(first[d["key"]]["total"]["mean"]), mean(second[d["key"]]["total"]["mean"])]
                    for d in self.asked()]
        self.assertEqual(radar.header, [T["dimension"], "Prima metà (8–19 ottobre 2026)",
                                        "Seconda metà (20–31 ottobre 2026)"])
        self.assertIn("prima metà (8–19 ottobre 2026)", radar.heading)
        self.assertNotIn("Acme Chat", radar.heading)
        self.assertEqual(radar.rows, expected)
        self.assertEqual((bar.header, bar.rows), (radar.header, expected))

    def test_a_first_measurement_has_one_series(self):
        self.history(days=range(16, 25))
        self.build(REPORT)
        [radar], [bar] = self.profile(blocks(self.charts()[1]))
        now = self.period_file(REPORT)["projects"]["market"]["dimensions"]
        self.assertEqual(radar.header, [T["dimension"], "23–31 ottobre 2026"])
        self.assertEqual(radar.rows, [[d["name"], mean(now[d["key"]]["total"]["mean"])] for d in self.asked()])
        self.assertEqual(bar.rows, radar.rows)


class ProfileBasisTest(ChartsCase, unittest.TestCase):

    def test_an_assistant_added_in_the_second_half_is_left_out_and_the_heading_names_the_assistants(self):
        self.adopt_market(rows_of(1))
        for n in range(1, 13):
            self.ingest_market(9100 + n, day(n), rows_of(n))
        added = market_project()
        added["project"]["researcher_model_ids"].append(NEW)
        self.edit(added, 12)
        low = [(PRICE_Q, NEW, "Un litro di Avenello costa 1,90 €.", 1, []), (CHOICE_Q, NEW, "La migliore è Avoria.", 1, []),
               (WORK_Q, NEW, "Da Avenello si lavora male.", 1, [])]
        for n in range(13, 25):
            self.ingest_market(9100 + n, day(n), rows_of(n) + low)
        self.build(REPORT)
        [radar], [bar] = self.profile(blocks(self.charts()[1]))
        compared = self.comparison()["dimensions"]["market"]
        self.assertIn(T["basis_models"][1][1].format(names="Acme Chat e Orbit Reason"), radar.heading)
        self.assertNotIn("Zenith", radar.heading)
        self.assertEqual(radar.rows, [[d["name"], mean(compared[d["key"]]["mean"]["previous"]),
                                       mean(compared[d["key"]]["mean"]["now"])] for d in self.asked()])
        second = self.read(f"history/periods/{REPORT}.second.json")["projects"]["market"]["dimensions"]
        self.assertNotEqual([r[2] for r in radar.rows], [mean(second[d["key"]]["total"]["mean"]) for d in self.asked()])
        self.assertEqual(bar.heading, radar.heading)

    def test_a_question_with_a_new_intent_is_named_in_the_profile_heading(self):
        self.adopt(at=ADOPTED)
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101))
        self.publish("2026-10-31")
        self.detect(edited(text=NEW_TEXT), FOUND, "--new-intent", "salute-2")
        self.ingest_all(runs(NOV, 9201, texts={"salute-2": NEW_TEXT}))
        self.build("2026-11-30")
        [bar] = [b for b in blocks(self.charts("2026-11-30")[1]) if b.title == T["profile_title"]]
        self.assertIn(T["basis_questions"][0][1].format(questions=f"«{NEW_TEXT}» e «{OLD_TEXT}»"), bar.heading)
        self.assertNotIn("assistenti presenti", bar.heading)

    def test_one_shared_assistant_is_named_in_the_singular(self):
        self.adopt_market(rows_of(1))
        for n in range(1, 13):
            self.ingest_market(9100 + n, day(n), rows_of(n))
        swapped = market_project()
        swapped["project"]["researcher_model_ids"] = [GPT, NEW]
        self.edit(swapped, 12)
        low = [(PRICE_Q, NEW, "Un litro di Avenello costa 1,90 €.", 1, []), (CHOICE_Q, NEW, "La migliore è Avoria.", 1, []),
               (WORK_Q, NEW, "Da Avenello si lavora male.", 1, [])]
        for n in range(13, 25):
            self.ingest_market(9100 + n, day(n), [r for r in rows_of(n) if r[1] == GPT] + low)
        self.build(REPORT)
        [radar], _ = self.profile(blocks(self.charts()[1]))
        self.assertIn("sulle risposte dell'unico assistente presente in entrambe le metà, Acme Chat", radar.heading)

    def test_one_question_left_out_is_named_in_the_singular(self):
        self.adopt(at=ADOPTED)
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101))
        self.publish("2026-10-31")
        self.detect(edited(add_question=True), FOUND)
        gluten = [{"id": 1, "model_id": m, "question": "Il latte d'avena Avenello contiene glutine?", "dimension": "Salute",
                   "answer": "Avenello non contiene glutine.", "judge_score": 4, "sentiment": "positive", "sources": []}
                  for m in (GPT, GEM)]
        self.ingest_all(runs(NOV, 9201, extra=gluten))
        self.build("2026-11-30")
        [bar] = [b for b in blocks(self.charts("2026-11-30")[1]) if b.title == T["profile_title"]]
        self.assertIn("senza «Il latte d'avena Avenello contiene glutine?», non confrontabile tra i due periodi",
                      bar.heading)

    def test_the_notes_on_assistants_are_the_report_s_own_sentences(self):
        for lang in ("it", "en"):
            for halves, key in ((0, "models_basis"), (1, "models_basis_halves")):
                for plural in (0, 1):
                    note = CHARTS[lang]["basis_models"][halves][plural]
                    self.assertGreater(len(note), 20)
                    self.assertIn(note.removeprefix("on "), TEXT[lang][key][plural])

    def test_a_project_whose_runs_end_early_gets_the_report_s_half_labels_and_its_own_days_in_its_heading(self):
        self.adopt(at=ADOPTED)
        self.cli("adopt", "--study", self.study, "--project", self.save("market.json", market_project()),
                 "--run", self.save("market-run.json", results(9000, "2026-09-29T06:00:00Z", rows_of(1))),
                 "--key", "market", check=0, at=ADOPTED)
        self.answer_operator()
        self.ingest_all(runs([day(n) for n in (1, 8, 15, 24)], 9301))
        for n in range(1, 19):
            self.ingest_market(9100 + n, day(n), rows_of(n))
        self.build(REPORT)
        self.assertEqual(self.comparison()["halves"]["second"]["to"], day(24))
        found = blocks(self.charts()[1])
        [radar] = [b for b in found if b.type == "radar"]
        self.assertEqual(radar.header, [T["dimension"], "Prima metà (8–19 ottobre 2026)", "Seconda metà (20–31 ottobre 2026)"])
        self.assertTrue(radar.heading.startswith("Avenello · Mercato (rilevazioni dall'8 ottobre 2026 al 25 ottobre 2026): "),
                        radar.heading)
        [column] = [b for b in found if b.type == "column"]
        self.assertEqual(column.header[1], "8–31 ottobre 2026")
        [brand] = [b for b in found if b.title == T["profile_title"] and b.heading.startswith("Avenello · Con il marchio")]
        self.assertNotIn("rilevazioni", brand.heading)


class InsightChartsTest(ChartsCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.history()
        self.build(REPORT)
        self.proc, self.text = self.charts()
        self.found = blocks(self.text)
        self.period = self.period_file(REPORT)

    def scope(self, dim):
        return next(iter(self.period["projects"]["market"]["dimensions"][dim]["questions"].values()))

    def test_the_fact_currency_line_has_one_point_per_run_with_the_period_s_share(self):
        [line] = [b for b in self.found if b.type == "line"]
        self.assertIn(f"«{PRICE_Q}»", line.heading)
        self.assertEqual(line.title, T["currency_title"])
        runs = self.scope("prezzo")["facts"]["runs"]
        self.assertEqual(len(line.rows), 24)
        self.assertEqual([r[1] for r in line.rows], [pct(r["total"]["current_share"]) for r in runs])
        self.assertEqual((line.rows[0][0], line.rows[-1][0]), ("8 ott", "31 ott"))

    def test_the_presence_columns_have_one_column_per_run(self):
        [column] = [b for b in self.found if b.type == "column"]
        self.assertIn(f"«{CHOICE_Q}»", column.heading)
        self.assertEqual(column.title, T["presence_title"].format(subject="Avenello"))
        runs = self.scope("scelta")["presence_runs"]
        self.assertEqual(len(column.rows), 24)
        self.assertEqual([r[1] for r in column.rows], [pct(r["named"] / r["given"]) for r in runs])
        self.assertEqual(column.rows[12][0], "20 ott")

    def test_the_sources_bars_give_both_groups_shares_of_each_listed_domain(self):
        pairs = (("outdated", "current"), ("low", "high"))
        listed = self.scope("prezzo")["group_sources"]
        self.assertEqual(set(listed), {"outdated", "current", "low", "high"})
        for one, other in pairs:
            [bar] = [b for b in self.found if b.type == "bar" and f"«{PRICE_Q}»" in b.heading
                     and b.header[1:] == [T["groups"][one], T["groups"][other]]]
            self.assertEqual(bar.title, T["sources_title"])
            self.assertEqual(bar.header[0], T["domain"])
            expected = {e["domain"]: [pct(e["share"]), pct(e["other"]["share"])] for e in listed[one]}
            for e in listed[other]:
                expected.setdefault(e["domain"], [pct(e["other"]["share"]), pct(e["share"])])
            self.assertEqual({r[0]: r[1:] for r in bar.rows}, expected)
            self.assertEqual([r[0] for r in bar.rows[:len(listed[one])]], [e["domain"] for e in listed[one]])
        every = sum(all(g in (s.get("group_sources") or {}) for g in pair) for pair in pairs
                    for d in self.period["projects"]["market"]["dimensions"].values() for s in d["questions"].values())
        self.assertEqual(sum(b.title == T["sources_title"] for b in self.found), every)

    def test_the_assistant_bars_have_one_series_per_assistant(self):
        [bar] = [b for b in self.found if b.title == T["by_model_title"]]
        self.assertEqual(bar.header, [T["dimension"], "Acme Chat", "Orbit Reason"])
        dims = self.period["projects"]["market"]["dimensions"]
        self.assertEqual(bar.rows, [[d["name"], mean(dims[d["key"]]["by_model"][GPT]["mean"]),
                                     mean(dims[d["key"]]["by_model"][GEM]["mean"])] for d in self.asked()])

    def test_every_chart_written_is_listed_with_its_type_and_size(self):
        for b in self.found:
            self.assertIn(f"{b.type} {len(b.rows)}×{len(b.header) - 1}: {b.heading}", self.proc.stdout)
        self.assertIn(f"reports/{REPORT}.charts.md", self.proc.stdout)


class ChartFileTest(ChartsCase, unittest.TestCase):

    def assert_figures_of_the_period(self, date=REPORT):
        """Every value is a figure of the period file, as `check` rounds and accepts it in a report."""
        _, text = self.charts(date)
        period = self.period_file(date)
        comparison = period.get("comparison") or {}
        scopes = [s for b in period["projects"].values() for s in [b, *b["dimensions"].values()]]
        scopes += [q for b in period["projects"].values() for d in b["dimensions"].values() for q in d["questions"].values()]
        entries = [e for d in dimension_entries(comparison).values() for e in [d, *d.get("questions", {}).values()]]
        decimals, percents, _ = check._allowed(scopes, check._compared(entries, comparison.get("verdict_changes", [])))
        found = blocks(text)
        self.assertGreater(len(found), 5)
        for b in found:
            for row in b.rows:
                for value in row[1:]:
                    if b.title.endswith("(%)"):
                        self.assertIn(int(value), percents, (b.heading, row))
                    else:
                        self.assertRegex(value, r"^\d\.\d$")
                        self.assertIn(float(value), decimals, (b.heading, row))

    def test_every_value_of_a_halves_report_is_a_figure_of_its_period(self):
        self.history()
        self.build(REPORT)
        self.assert_figures_of_the_period()

    def test_every_value_of_a_report_compared_with_an_earlier_period_is_a_figure_of_its_period(self):
        self.history(extra=SEPTEMBER)
        self.build(REPORT)
        self.assert_figures_of_the_period()

    def test_the_file_parses_as_md2_chart_blocks(self):
        self.history()
        self.build(REPORT)
        _, text = self.charts()
        found = blocks(text)
        self.assertEqual(len(found), sum(line.startswith(":::chart ") for line in text.splitlines()))
        self.assertEqual(len(found), sum(line == ":::" for line in text.splitlines()))
        for b in found:
            self.assertIn(b.type, MD2_TYPES)
            self.assertNotIn('"', b.title)
            self.assertEqual(set(b.separator), {"---"})
            self.assertGreaterEqual(len(b.header), 2)
            for row in b.rows:
                self.assertEqual(len(row), len(b.header), (b.heading, row))
                for value in row[1:]:
                    self.assertRegex(value, r"^\d+(\.\d)?$")
            if b.type == "radar":
                self.assertTrue(3 <= len(b.rows) <= 12 and 1 <= len(b.header) - 1 <= 4)
        # The profile's radar and bar, the assistants' bar, the fact line, the presence columns, and the price
        # question's two sources bars: no other question has an answer scored 1-2.
        self.assertEqual(collections.Counter(b.type for b in found), {"radar": 1, "bar": 4, "line": 1, "column": 1})

    def test_a_chart_with_no_data_is_left_out_and_listed(self):
        unpriced = ("Un litro di Avenello costa poco.", 3, ["https://prezzi.example/avena"])
        self.adopt_market(rows_of(1))
        for n in range(1, 25):
            self.ingest_market(9100 + n, day(n), [(q, m, *unpriced) if q == PRICE_Q else (q, m, *a)
                                                  for q, m, *a in rows_of(n)])
        self.build(REPORT)
        [price] = self.period_file(REPORT)["projects"]["market"]["dimensions"]["prezzo"]["questions"].values()
        self.assertEqual(price["facts"]["total"]["stating"], 0)
        proc, text = self.charts()
        self.assertFalse([b for b in blocks(text) if b.type == "line"])
        self.assertIn(f"«{PRICE_Q}»", left_out(proc.stdout))
        self.assertNotIn(PRICE_Q, text)

    def test_a_run_with_no_answer_stating_the_fact_is_left_out_of_the_line_and_listed(self):
        unpriced = ("Un litro di Avenello costa poco.", 3, ["https://prezzi.example/avena"])
        self.adopt_market(rows_of(1))
        for n in range(1, 25):
            self.ingest_market(9100 + n, day(n), [(q, m, *unpriced) if q == PRICE_Q and n <= 3 else (q, m, *a)
                                                  for q, m, *a in rows_of(n)])
        self.build(REPORT)
        proc, text = self.charts()
        [line] = [b for b in blocks(text) if b.type == "line"]
        self.assertEqual((len(line.rows), line.rows[0][0]), (21, "11 ott"))
        self.assertIn(f"«{PRICE_Q}»", left_out(proc.stdout))
        self.assertIn("3 run(s)", left_out(proc.stdout))

    def test_a_dimension_not_compared_is_left_out_of_the_profile_and_a_radar_needs_three(self):
        self.history(days=range(1, 18))
        edited = market_project()
        price = edited["project"]["dimensions"][0]["questions"][0]
        price["grading_rubric"] = {**price["grading_rubric"], "5": "Prezzo attuale con la fonte"}
        self.edit(edited, 17)
        for n in range(18, 25):
            self.ingest_market(9100 + n, day(n), rows_of(n))
        self.build(REPORT)
        self.assertEqual(self.comparison()["dimensions"]["market"]["prezzo"]["status"], "new_baseline")
        proc, text = self.charts()
        radar, [bar] = self.profile(blocks(text))
        self.assertEqual(radar, [])
        self.assertEqual([r[0] for r in bar.rows], ["Scelta", "Lavoro"])
        self.assertIn("Prezzo", left_out(proc.stdout))
        self.assertIn("radar", left_out(proc.stdout))

    def test_a_dimension_an_assistant_has_no_figure_on_is_left_out_of_the_assistants_bar(self):
        self.adopt_market(rows_of(1), rounds=2)
        for n in range(16, 25):
            # One of Orbit Reason's two rounds on the employer question is not judged: 11 of 12 answers clear
            # the run floor, 9 of 18 leave the pair without a figure.
            unjudged = [(q, m, a, None if (q, m) == (WORK_Q, GEM) else s, u) for q, m, a, s, u in rows_of(n)]
            self.ingest_market(9100 + n, day(n), rows_of(n) + unjudged)
        self.build(REPORT)
        cells = self.period_file(REPORT)["projects"]["market"]["dimensions"]["lavoro"]["by_model"]
        self.assertEqual((cells[GPT]["figure"], cells[GEM]["figure"]), (True, False))
        proc, text = self.charts()
        [bar] = [b for b in blocks(text) if b.title == T["by_model_title"]]
        self.assertEqual([r[0] for r in bar.rows], ["Prezzo", "Scelta"])
        self.assertIn("Orbit Reason", left_out(proc.stdout))

    def test_a_chart_by_run_with_one_run_is_left_out_and_listed(self):
        self.history(days=[24])
        self.build(REPORT)
        proc, text = self.charts()
        self.assertEqual([b.type for b in blocks(text) if b.type in ("line", "column")], [])
        self.assertIn(f"«{PRICE_Q}»", left_out(proc.stdout))
        self.assertIn(f"«{CHOICE_Q}»", left_out(proc.stdout))

    def test_runs_started_on_the_same_utc_day_are_labelled_with_their_utc_start_time(self):
        # 01:00 at UTC+2 on 1 November is 23:00 UTC on 31 October, the day of the run of day 24.
        self.history(extra=[(9200, "2026-11-01T01:00:00+02:00")])
        self.build(REPORT)
        found = blocks(self.charts()[1])
        for kind in ("line", "column"):
            [chart] = [b for b in found if b.type == kind]
            self.assertEqual(len(chart.rows), 25)
            self.assertEqual([r[0] for r in chart.rows[-3:]], ["30 ott", "31 ott 06:00 UTC", "31 ott 23:00 UTC"])

    def test_a_line_whose_fact_is_stated_in_one_run_is_left_out_and_says_so(self):
        unpriced = ("Un litro di Avenello costa poco.", 3, ["https://prezzi.example/avena"])
        self.adopt_market(rows_of(1))
        for n in range(1, 25):
            self.ingest_market(9100 + n, day(n), [(q, m, *unpriced) if q == PRICE_Q and n < 24 else (q, m, *a)
                                                  for q, m, *a in rows_of(n)])
        self.build(REPORT)
        proc, text = self.charts()
        self.assertFalse([b for b in blocks(text) if b.type == "line"])
        [line] = [x for x in left_out(proc.stdout).splitlines() if f"«{PRICE_Q}»" in x and "attuale o superato" in x]
        self.assertIn("stated in 1 run(s)", line)

    def test_whitespace_in_a_title_is_collapsed(self):
        self.history()
        self.build(REPORT)
        study = self.read("study.json")
        study["subject"]["label"] = "Avenello \n  Bio"
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        [column] = [b for b in blocks(self.charts()[1]) if b.type == "column"]
        self.assertEqual(column.title, T["presence_title"].format(subject="Avenello Bio"))

    def test_one_assistant_gets_no_assistant_chart(self):
        one = project()
        one["project"]["researcher_model_ids"] = [GPT]
        self.adopt(project_data=one, run_data=run(models=[GPT]))
        self.answer_operator()
        self.ingest(run(models=[GPT]))
        self.build("2026-10-31")
        proc, text = self.charts("2026-10-31")
        found = blocks(text)
        self.assertEqual([(b.type, b.title) for b in found], [("bar", T["profile_title"])])
        self.assertEqual([r[0] for r in found[0].rows], ["Salute", "Prezzo"])
        self.assertIn("radar", left_out(proc.stdout))

    def test_without_a_period_the_command_is_refused(self):
        self.history()
        proc, text = self.charts("2026-01-31", check=2)
        self.assertIn("period --date 2026-01-31", proc.stderr)
        self.assertEqual(text, "")


if __name__ == "__main__":
    unittest.main()
