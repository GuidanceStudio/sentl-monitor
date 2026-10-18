"""A first report on a monitor younger than its report interval compares the second half of
its period with the first (ARCHITECTURE.md §Periods); the rules every comparison shares with
it: a verdict change needs a move of the pair's mean, and the domain lists keep five each."""

import datetime as dt
import re
import unittest
from unittest import mock

import fixtures
from fixtures import CHOICE_Q, GEM, GPT, NEW, PRICE_Q, REPO, WORK_Q, StudyCase, market_project, models, run
from sentlmon.common import fmt_date, fmt_decimal, fmt_percent
from sentlmon.i18n import TEXT, phrase
from sentlmon.period import episodes_behind
from test_method import CHANGES, IT_ORDER, sections
from test_order import headings

OLD_PRICE = ("Un litro di Avenello costa 1,90 €.", 3, ["https://prezzi.example/avena"])
OLD_PRICE_FAIR = ("Un litro di Avenello costa 1,90 €, meno di altre marche.", 4, ["https://prezzi.example/avena"])
OLD_PRICE_LOW = ("Un litro di Avenello costa 1,90 €, troppo per una bevanda.", 1, ["https://prezzi.example/avena"])
NEW_PRICE = ("Un litro di Avenello costa 2,10 €.", 5, ["https://avenello.example/prezzi", "https://listino.example/avena"])
NOT_CHOSEN = ("La migliore è Avoria, secondo il confronto.", 3, ["https://avoria.example/confronto"])
NOT_CHOSEN_WELL = ("La migliore è Avoria, ma anche altre marche sono buone.", 4, ["https://avoria.example/confronto"])
EMPLOYER = ("Avenello è un buon datore di lavoro, secondo i dipendenti.", 3, ["https://lavoro.example/avenello"])
EMPLOYER_BETTER = ("Avenello è un ottimo datore di lavoro, secondo i dipendenti.", 4,
                   ["https://lavoro.example/avenello", "https://carriere.example/avenello"])
SECTOR = ("Nel settore delle bevande vegetali il lavoro è stabile.", 3, ["https://lavoro.example/settore"])
SECTOR_BETTER = ("Nel settore delle bevande vegetali il lavoro è stabile e ben pagato.", 4,
                 ["https://lavoro.example/settore", "https://contratti.example/settore", "https://paghe.example/settore"])
REPORT = "2026-10-31"
FIRST_HALF, SECOND_HALF = range(1, 13), range(13, 25)


def day(n):
    """Day n of the monitor: day 1 is 8 October; day 24 is 31 October, the report's date."""
    return f"{dt.date(2026, 10, 7) + dt.timedelta(days=n)}T06:00:00Z"


def chosen(n):
    """Avenello named first; each day's answer also cites a page of its own, cited once."""
    return ("La migliore è Avenello, prima di Avoria.", 4,
            ["https://classifica.example/2026", "https://avoria.example/confronto", f"https://voto{n}.example/scelta"])


def rows_of(n):
    """Day n's answers. The halves split on 20 October 03:00, the midpoint between the first run
    and the end of the report's date: days 1-12, then 13-24. Acme Chat scores the price 4 on the
    odd days up to day 21, so its mean is 3.5 in the first half and 3.4 in the second. Orbit
    Reason scores the price 1 on days 7-9, an episode below the range in the first half, and
    gives the current price from day 15; from day 15 it scores the choice question 4 and names
    Avenello on days 20-24; in the second half it scores the employer question 4 and names
    Avenello on days 13-15."""
    gpt_price = OLD_PRICE_FAIR if n % 2 and n <= 21 else OLD_PRICE
    gem_price = NEW_PRICE if n >= 15 else OLD_PRICE_LOW if 7 <= n <= 9 else OLD_PRICE
    gem_choice = chosen(n) if n >= 20 else NOT_CHOSEN_WELL if n >= 15 else NOT_CHOSEN
    gem_work = SECTOR if n <= 12 else EMPLOYER_BETTER if n <= 15 else SECTOR_BETTER
    answers = [(PRICE_Q, GPT, gpt_price), (PRICE_Q, GEM, gem_price), (CHOICE_Q, GPT, NOT_CHOSEN),
               (CHOICE_Q, GEM, gem_choice), (WORK_Q, GPT, EMPLOYER), (WORK_Q, GEM, gem_work)]
    return [(q, m, *a) for q, m, a in answers]


def it(value):
    return fmt_decimal(value, "it")


class HalvesCase(StudyCase):

    def history(self, days=range(1, 25), extra=()):
        """The market project adopted on 1 September, a run on each of `days`, and runs at the
        given (run id, start) pairs of `extra` with day 1's answers."""
        self.adopt_market(rows_of(1))
        for run_id, start in extra:
            self.ingest_market(run_id, start, rows_of(1))
        for n in days:
            self.ingest_market(9100 + n, day(n), rows_of(n))

    def edit(self, data, n, key="market"):
        """The project seen unchanged after day n's run, then edited one hour later."""
        for hour, saved in (("07", market_project()), ("08", data)):
            self.cli("detect", "--study", self.study, "--project", key, "--saved", self.save(f"edit-{hour}.json", saved),
                     check=0, at=day(n).replace("T06", f"T{hour}"))

    def comparison(self, date=REPORT):
        return self.period_file(date)["comparison"]

    def question(self, dim, date=REPORT):
        return next(iter(self.comparison(date)["dimensions"][dim]["questions"].values()))

    def half_files(self):
        return sorted(p.name for p in (self.study / "history/periods").glob("*.json")
                      if self.read(f"history/periods/{p.name}").get("half"))

    def method(self, date=REPORT):
        self.cli("method", "--study", self.study, "--date", date, "--models", self.save("models.json", models()),
                 check=0)
        return self.study / "reports" / f"{date}.md"


class HalvesTest(HalvesCase, unittest.TestCase):

    def test_the_period_is_split_at_the_midpoint_into_two_halves_with_no_report(self):
        self.history()
        proc = self.build(REPORT)
        self.assertEqual(self.half_files(), [f"{REPORT}.first.json", f"{REPORT}.second.json"])
        first, second = (self.read(f"history/periods/{REPORT}.{h}.json") for h in ("first", "second"))
        self.assertEqual((first["half"], second["half"]), ("first", "second"))
        self.assertEqual(first["runs"], {"market": [9100 + n for n in FIRST_HALF]})
        self.assertEqual(second["runs"], {"market": [9100 + n for n in SECOND_HALF]})
        self.assertNotIn("rebuilt", first)
        self.assertNotIn("comparison", first)
        c = self.comparison()
        self.assertIsNone(c["previous"])
        self.assertEqual({k: c["halves"]["first"][k] for k in ("from", "to")}, {"from": day(1), "to": day(12)})
        self.assertEqual({k: c["halves"]["second"][k] for k in ("from", "to")}, {"from": day(13), "to": day(24)})
        self.assertEqual(c["halves"]["split"], "2026-10-20T03:00:00Z")
        self.assertEqual(c["halves"]["first"]["projects"], {"market": {"runs": 12, "answers": 72}})
        self.assertEqual(sorted(p.name for p in (self.study / "history/material").glob("*.md")), [f"{REPORT}.md"])
        self.assertFalse((self.study / "history/reports.json").exists())
        self.assertIn("half", proc.stdout)
        self.assertNotIn("first measurement", proc.stdout)

    def test_a_dimension_moving_half_a_point_is_a_change_and_one_moving_less_is_not(self):
        self.history()
        self.build(REPORT)
        lavoro, scelta = (self.comparison()["dimensions"][d]["mean"] for d in ("lavoro", "scelta"))
        self.assertEqual((lavoro["previous"], lavoro["now"], lavoro["periods"]), (3.0, 3.5, 1))
        self.assertAlmostEqual(lavoro["delta"], 0.5)
        self.assertTrue(lavoro["changed"])
        self.assertEqual(scelta["previous"], 3.0)
        self.assertAlmostEqual(scelta["now"], 82 / 24)
        self.assertFalse(scelta["changed"])

    def test_a_question_gaining_the_subject_by_20_points_is_a_change_and_one_by_10_is_not(self):
        self.history()
        self.build(REPORT)
        choice, work = self.question("scelta")["presence"], self.question("lavoro")["presence"]
        self.assertEqual(choice["previous"], 0.0)
        self.assertAlmostEqual(choice["now"], 5 / 24)
        self.assertTrue(choice["changed"])
        self.assertEqual(work["previous"], 0.5)
        self.assertAlmostEqual(work["now"], 15 / 24)
        self.assertFalse(work["changed"])

    def test_a_fact_whose_current_share_moves_is_a_change(self):
        self.history()
        self.build(REPORT)
        share = self.question("prezzo")["current_share"]
        self.assertEqual((share["previous"], share["periods"]), (0.0, 1))
        self.assertAlmostEqual(share["now"], 10 / 24)
        self.assertTrue(share["changed"])
        self.assertNotIn("current_share", self.question("scelta"))

    def test_the_project_mean_of_each_half_is_compared(self):
        self.history()
        self.build(REPORT)
        project = self.comparison()["projects"]["market"]
        self.assertEqual(project["dimensions"], ["lavoro", "prezzo", "scelta"])
        self.assertAlmostEqual(project["mean"]["previous"], (72 / 24 + 3.0 + 3.0) / 3)
        self.assertAlmostEqual(project["mean"]["now"], (97 / 24 + 82 / 24 + 3.5) / 3)
        self.assertTrue(project["mean"]["changed"])

    def test_a_verdict_change_needs_the_pair_s_mean_to_move_by_the_threshold(self):
        self.history()
        self.build(REPORT)
        c = self.comparison()
        self.assertEqual(sorted((v["dimension"], v["model"], v["from"], v["to"]) for v in c["verdict_changes"]),
                         [("lavoro", GEM, "mixed", "favourable"), ("prezzo", GEM, "mixed", "favourable"),
                          ("scelta", GEM, "mixed", "favourable")])
        price = self.period_file(REPORT)["projects"]["market"]["dimensions"]["prezzo"]["questions"]
        self.assertEqual(len(price), 1)

    def test_the_new_domains_are_the_five_cited_by_most_answers_ties_broken_by_name(self):
        self.history()
        self.build(REPORT)
        c = self.comparison()
        self.assertEqual([(d["dimension"], d["domain"], d["answers"]) for d in c["domains"]["new"]],
                         [("prezzo", "avenello.example", 10), ("prezzo", "listino.example", 10),
                          ("lavoro", "contratti.example", 9), ("lavoro", "paghe.example", 9),
                          ("scelta", "classifica.example", 5)])
        [moved] = c["presence_sources"]
        self.assertEqual(moved["dimension"], "scelta")
        self.assertEqual(moved["new"], [{"domain": "classifica.example", "answers": 5}]
                         + [{"domain": f"voto{n}.example", "answers": 1} for n in range(20, 24)])

    def test_the_insights_for_the_findings_still_read_the_whole_period(self):
        self.history()
        self.build(REPORT)
        price = self.period_file(REPORT)["projects"]["market"]["dimensions"]["prezzo"]
        scope = next(iter(price["questions"].values()))
        self.assertEqual((price["total"]["judged"], len(scope["facts"]["runs"])), (48, 24))
        self.assertEqual(sorted((e["measure"], e["first"], e["side"], e["runs"]) for e in scope["episodes"]),
                         [("current_share", "2026-10-22", "above", 10), ("mean", "2026-10-14", "below", 3),
                          ("mean", "2026-10-22", "above", 10)])
        below = next(e for e in scope["episodes"] if e["side"] == "below")
        self.assertEqual((below["first_at"], below["last_at"], below["closed"]), (day(7), day(9), "2026-10-17"))
        choice = next(iter(self.period_file(REPORT)["projects"]["market"]["dimensions"]["scelta"]["questions"].values()))
        self.assertEqual(len(choice["presence_runs"]), 24)

    def test_runs_spanning_14_days_are_split_and_13_days_are_the_first_measurement(self):
        self.history(days=range(10, 25))
        self.build(REPORT)
        self.assertIn("halves", self.comparison())
        (self.study / "history/runs/market/9110.json.gz").unlink()
        proc = self.build(REPORT)
        self.assertEqual(self.half_files(), [])
        c = self.comparison()
        self.assertIsNone(c["previous"])
        self.assertNotIn("halves", c)
        self.assertIn("first measurement", proc.stdout)
        self.assertIn("13 days", proc.stdout)
        self.assertIn("prima misurazione", sections(self.method().read_text(encoding="utf-8"))[CHANGES])

    def test_with_a_run_before_the_interval_the_rebuilt_period_is_compared_and_no_half_is_built(self):
        self.history(extra=[(9050, "2026-09-25T06:00:00Z")])
        self.build(REPORT)
        c = self.comparison()
        self.assertEqual((c["previous"], c["range_of"]), ("2026-09-30", ["2026-09-30"]))
        self.assertNotIn("halves", c)
        self.assertEqual(self.half_files(), [])
        self.assertTrue(self.period_file("2026-09-30")["rebuilt"])

    def test_building_the_first_report_again_replaces_its_halves_and_keeps_those_of_other_dates(self):
        self.history()
        self.build(REPORT)
        self.build("2026-10-30")
        self.assertEqual(self.half_files(), ["2026-10-30.first.json", "2026-10-30.second.json",
                                             f"{REPORT}.first.json", f"{REPORT}.second.json"])
        (self.study / "history/runs/market/9124.json.gz").unlink()
        self.build(REPORT)
        self.assertEqual(self.read(f"history/periods/{REPORT}.second.json")["runs"]["market"][-1], 9123)

    def test_the_halves_split_the_whole_period_s_runs_after_a_criteria_change(self):
        self.history(days=range(1, 18))
        edited = market_project()
        price = edited["project"]["dimensions"][0]["questions"][0]
        price["grading_rubric"] = {**price["grading_rubric"], "5": "Prezzo attuale con la fonte"}
        self.edit(edited, 17)
        for n in range(18, 25):
            self.ingest_market(9100 + n, day(n), rows_of(n))
        self.build(REPORT)
        whole = self.period_file(REPORT)["projects"]["market"]
        first, second = (self.read(f"history/periods/{REPORT}.{h}.json")["projects"]["market"] for h in ("first", "second"))
        self.assertNotIn("prezzo", first["dimensions"])
        self.assertEqual(first["total"]["received"] + second["total"]["received"], whole["total"]["received"])
        self.assertEqual(second["dimensions"]["prezzo"]["total"]["received"], 7 * 2)
        c = self.comparison()
        self.assertEqual(c["dimensions"]["prezzo"]["status"], "new_baseline")
        self.assertEqual([(d["change"], d.get("since")) for d in c["design_changes"]], [("criteria", "2026-10-25")])

    def test_a_question_reworded_inside_the_first_half_is_stated(self):
        reworded = "Quale bevanda all'avena conviene comprare oggi?"
        with mock.patch.dict(fixtures.QUESTION_DIM, {reworded: "Scelta"}):
            self.history(days=range(1, 6))
            edited = market_project()
            edited["project"]["dimensions"][1]["questions"][0]["question"] = reworded
            self.edit(edited, 5)
            for n in range(6, 25):
                self.ingest_market(9100 + n, day(n), [(reworded if q == CHOICE_Q else q, *rest) for q, *rest in rows_of(n)])
            self.build(REPORT)
        [change] = self.comparison()["design_changes"]
        self.assertEqual((change["change"], change["text"], change["previous_text"], change["since"]),
                         ("reworded", reworded, CHOICE_Q, "2026-10-13"))

    def test_a_dimension_archived_inside_the_first_half_is_stated(self):
        self.history(days=range(1, 6))
        edited = market_project()
        edited["project"]["dimensions"][2]["archived"] = True
        self.edit(edited, 5)
        for n in range(6, 25):
            self.ingest_market(9100 + n, day(n), [r for r in rows_of(n) if r[0] != WORK_Q])
        self.build(REPORT)
        self.assertEqual([(d["change"], d.get("dimension")) for d in self.comparison()["design_changes"]],
                         [("dimension_archived", "lavoro")])

    def test_an_assistant_silent_in_the_last_run_before_any_version_is_not_said_to_stop(self):
        self.adopt_market(rows_of(1), at="2026-11-02T00:00:00Z")
        for n in range(1, 25):
            self.ingest_market(9100 + n, day(n), [r for r in rows_of(n) if n < 24 or r[1] != GEM])
        self.build(REPORT)
        self.assertIn("halves", self.comparison())
        self.assertEqual(self.comparison()["design_changes"], [])

    def test_an_assistant_added_inside_the_first_half_is_stated(self):
        self.history(days=range(1, 4))
        edited = market_project()
        edited["project"]["researcher_model_ids"].append(NEW)
        self.edit(edited, 3)
        for n in range(4, 25):
            self.ingest_market(9100 + n, day(n), rows_of(n) + [(q, NEW, *OLD_PRICE) for q in (PRICE_Q,)]
                               + [(CHOICE_Q, NEW, *NOT_CHOSEN), (WORK_Q, NEW, *EMPLOYER)])
        self.build(REPORT)
        changes = [d for d in self.comparison()["design_changes"] if d["change"] == "models"]
        self.assertEqual([(d["added"], d["removed"]) for d in changes], [([NEW], [])])
        report = sections(self.method().read_text(encoding="utf-8"))[CHANGES]
        self.assertIn("In questo periodo risponde anche Zenith Answer. I confronti sono calcolati sulle risposte degli "
                      "assistenti presenti in entrambe le metà: Acme Chat, Orbit Reason e Zenith Answer.", report)


class HalvesReportTest(HalvesCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.history()
        self.build(REPORT)
        self.path = self.method()
        self.text = self.path.read_text(encoding="utf-8")
        self.material = (self.study / f"history/material/{REPORT}.md").read_text(encoding="utf-8")

    def write_changes(self, changes, halves_line=None):
        text = self.text.replace(TEXT["it"]["changes_marker_halves"], changes)
        if halves_line is not None:
            text = text.replace(self.halves_line(), halves_line)
        self.path.write_text(re.sub(r"\[\[[^\]]*\]\]", "le risposte descrivono Avenello", text), encoding="utf-8")
        return self.cli("check", "--study", self.study, self.path)

    def halves_line(self):
        return next(line for line in sections(self.text)[CHANGES].splitlines() if "metà" in line)

    def material_block(self, dimension):
        changes = self.material.split("## Changes between the two halves of the period", 1)[1]
        return changes.split(f"### Dimension {dimension}:", 1)[1].split("\n### ", 1)[0]

    def test_the_changes_section_names_the_two_halves_their_dates_runs_and_answers(self):
        self.assertEqual(headings(self.text), IT_ORDER)
        changes = sections(self.text)[CHANGES]
        self.assertIn("la seconda metà di questo periodo, dal 20 ottobre 2026 al 31 ottobre 2026, è confrontata con "
                      "la prima, dall'8 ottobre 2026 al 19 ottobre 2026. Avenello · Mercato: 12 rilevazioni e 72 "
                      "risposte nella prima metà, 12 rilevazioni e 72 nella seconda.", changes)
        self.assertIn(TEXT["it"]["changes_marker_halves"], changes)
        self.assertNotIn("prima misurazione", changes)

    def test_the_material_states_an_episode_s_first_date_beside_the_change_it_explains(self):
        self.assertIn("episode", self.material_block("Prezzo"))
        self.assertIn("2026-10-22", self.material_block("Prezzo"))
        self.assertNotIn("2026-10-14", self.material_block("Prezzo"))
        self.assertIn("2026-10-20", self.material_block("Lavoro"))
        self.assertNotIn("episode", self.material_block("Scelta"))

    def test_the_material_s_halves_header_gives_dates_runs_and_answers(self):
        header = self.material.split("## Changes between the two halves of the period", 1)[1].split("\n### ", 1)[0]
        self.assertIn("runs started 2026-10-20 to 2026-10-31", header)
        self.assertIn("runs started 2026-10-08 to 2026-10-19", header)
        self.assertIn("split at 2026-10-20 03:00 UTC", header)
        self.assertIn("Avenello · Mercato: 12 runs and 72 answers in the first half, 12 runs and 72 in the second", header)
        self.assertNotIn("T06:00", header)

    def test_the_scoring_section_says_a_verdict_change_needs_the_mean_to_move(self):
        self.assertIn("un cambio di giudizio è riportato solo quando la media dell'assistente sulla domanda si sposta "
                      "anche di almeno 0,3 punti, 0,5 con un solo periodo precedente", self.text)

    def test_an_episode_note_is_printed_once_under_its_question(self):
        block = self.material_block("Lavoro")
        self.assertEqual(block.count("episode behind"), 1)
        self.assertLess(block.index("- «"), block.index("episode behind"))

    def test_the_material_s_metric_lines_name_the_halves(self):
        changes = self.material.split("## Changes between the two halves of the period", 1)[1].split("### Verdict", 1)[0]
        lines = changes[changes.index("\n### "):]
        self.assertIn("mean: second half 3,5, first half 3,0, delta +0,5: CHANGE CALLED", lines)
        self.assertNotIn("earlier period", lines)
        self.assertNotIn("previous", lines)

    def test_the_material_says_first_and_second_half_where_a_later_report_says_previous_and_this_period(self):
        changes = self.material.split("## Changes between the two halves of the period", 1)[1]
        self.assertIn("First half, score", changes)
        self.assertIn("Second half, score", changes)
        self.assertIn("mixed (mean 2,5) in the first half, favourable (mean 4,7) in the second half", changes)
        for later in ("previous period", "Previous period", "This period", "this one"):
            self.assertNotIn(later, changes)

    def test_check_refuses_a_report_whose_half_file_is_missing(self):
        (self.study / f"history/periods/{REPORT}.first.json").unlink()
        proc = self.write_changes("Le dimensioni sono invariate.")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("first half", proc.stderr)
        self.assertIn("run period", proc.stderr)
        self.assertFalse((self.study / "history/reports.json").exists())

    def test_a_domain_cited_by_one_answer_is_written_as_one_answer(self):
        self.assertIn("voto20.example (1 answer)", self.material)
        self.assertNotRegex(self.material, r"(?<![\d])1 answers")

    def test_a_report_with_the_figures_of_both_halves_passes_check(self):
        c = self.period_file(REPORT)["comparison"]
        first, second = (self.read(f"history/periods/{REPORT}.{h}.json")["projects"]["market"] for h in ("first", "second"))
        project, lavoro = c["projects"]["market"]["mean"], c["dimensions"]["lavoro"]["mean"]
        presence, share = self.question("scelta")["presence"], self.question("prezzo")["current_share"]
        changes = (f"Il punteggio complessivo passa da {it(project['previous'])} a {it(project['now'])}. Lavoro passa da "
                   f"{it(lavoro['previous'])} a {it(lavoro['now'])}, dal 20 ottobre. Avenello è nominato nel "
                   f"{fmt_percent(presence['now'])} delle risposte alla domanda sulla scelta, contro il "
                   f"{fmt_percent(presence['previous'])} della prima metà. Le risposte con il prezzo attuale passano dal "
                   f"{fmt_percent(share['previous'])} al {fmt_percent(share['now'])}, dal 22 ottobre. In ciascuna metà "
                   f"sono state valutate {first['total']['judged']} su {first['total']['expected']} risposte; Orbit "
                   f"Reason ha una media di {it(first['by_model'][GEM]['mean'])} nella prima metà e di "
                   f"{it(second['by_model'][GEM]['mean'])} nella seconda.")
        self.assertIn("4,2", changes)
        proc = self.write_changes(changes)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        [entry] = self.read("history/reports.json")
        self.assertEqual((entry["date"], entry["previous"]), (REPORT, None))

    def test_check_refuses_a_figure_of_neither_half(self):
        proc = self.write_changes("Il punteggio complessivo passa a 9,9.")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("9,9", proc.stdout)

    def test_check_refuses_a_halves_report_whose_changes_section_names_no_halves(self):
        proc = self.write_changes("Lavoro passa da 3,0 a 3,5.", halves_line=TEXT["it"]["first"])
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("halves", proc.stdout)
        self.assertFalse((self.study / "history/reports.json").exists())


def plain(work):
    """One answer per question and assistant, the employer question asked only when `work`."""
    questions = [PRICE_Q, CHOICE_Q] + ([WORK_Q] if work else [])
    return [(q, m, "Avenello costa 1,90 €.", 3, ["https://prezzi.example/avena"]) for q in questions for m in (GPT, GEM)]


class AddedBeforeAdoptionTest(HalvesCase, unittest.TestCase):
    """The market project adopted on 1 November, after runs that did not yet ask the employer
    question."""

    def test_a_dimension_the_rebuilt_period_never_asked_is_new_with_its_design_line(self):
        self.adopt_market(plain(False), at="2026-11-01T00:00:00Z")
        for d in range(1, 31):
            self.ingest_market(9500 + d, f"2026-09-{d:02d}T06:00:00Z", plain(False))
        for d in range(1, 32):
            self.ingest_market(9600 + d, f"2026-10-{d:02d}T06:00:00Z", plain(True))
        self.build(REPORT)
        c = self.comparison()
        self.assertEqual((c["previous"], c["dimensions"]["lavoro"]["status"]), ("2026-09-30", "new"))
        self.assertEqual([(d["change"], d.get("dimension")) for d in c["design_changes"]],
                         [("dimension_added", "lavoro")])

    def test_a_dimension_the_first_half_never_asked_is_new_with_its_design_line(self):
        self.adopt_market(plain(False), at="2026-11-01T00:00:00Z")
        for n in range(1, 25):
            self.ingest_market(9100 + n, day(n), plain(n >= 15))
        self.build(REPORT)
        c = self.comparison()
        self.assertEqual((("halves" in c), c["dimensions"]["lavoro"]["status"]), (True, "new"))
        self.assertEqual([(d["change"], d.get("dimension")) for d in c["design_changes"]],
                         [("dimension_added", "lavoro")])


class OneHalfProjectTest(HalvesCase, unittest.TestCase):
    """The market project runs daily; the branded project runs on days 1 and 8 only."""

    def setUp(self):
        super().setUp()
        self.adopt(at="2026-09-01T00:00:00Z")

    def branded(self):
        for run_id, n in ((9401, 1), (9402, 8)):
            self.ingest(run(run_id=run_id, started=day(n)), name=f"b-{run_id}.json")

    def test_a_project_with_runs_in_one_half_only_is_not_compared_and_is_stated(self):
        self.history()
        self.branded()
        proc = self.build(REPORT)
        c = self.comparison()
        self.assertEqual({e["project"] for e in c["dimensions"].values()}, {"market"})
        self.assertEqual(c["halves"]["first"]["projects"]["brand"], {"runs": 2, "answers": 12})
        self.assertNotIn("brand", c["halves"]["second"]["projects"])
        self.assertNotIn("brand", c["projects"])
        self.assertRegex(proc.stdout, r"brand has runs in the first half only")
        changes = sections(self.method().read_text(encoding="utf-8"))[CHANGES]
        self.assertIn("Avenello · Con il marchio: 2 rilevazioni e 12 risposte solo nella prima metà, quindi non è "
                      "confrontato.", changes)

    def test_one_run_in_each_half_is_counted_as_one_run(self):
        self.history()
        for run_id, n in ((9401, 1), (9402, 20)):
            self.ingest(run(run_id=run_id, started=day(n)), name=f"b-{run_id}.json")
        self.build(REPORT)
        material = (self.study / f"history/material/{REPORT}.md").read_text(encoding="utf-8")
        self.assertIn("Avenello · Con il marchio: 1 run and 6 answers in the first half, 1 run and 6 in the second.",
                      material)
        self.assertNotIn("1 runs", material)
        changes = sections(self.method().read_text(encoding="utf-8"))[CHANGES]
        self.assertIn("Avenello · Con il marchio: 1 rilevazione e 6 risposte nella prima metà, 1 rilevazione e 6 nella "
                      "seconda.", changes)

    def test_with_no_project_in_both_halves_the_report_is_the_first_measurement(self):
        self.history(days=SECOND_HALF)
        self.branded()
        proc = self.build(REPORT)
        self.assertNotIn("halves", self.comparison())
        self.assertEqual(self.half_files(), [])
        self.assertIn("No project has runs in both halves", proc.stdout)


class EpisodesBehindTest(unittest.TestCase):
    """The episodes that may stand beside a change: on the side of its move, and running in
    the later side of the comparison, which starts at the split, 20 October 03:00."""

    SPLIT = "2026-10-20T03:00:00Z"
    EPISODES = [{"measure": "mean", "side": "above", "first": "2026-10-22", "last_at": "2026-10-31T06:00:00Z"},
                {"measure": "mean", "side": "below", "first": "2026-10-23", "last_at": "2026-10-25T06:00:00Z"},
                {"measure": "mean", "side": "above", "first": "2026-10-10", "last_at": "2026-10-14T06:00:00Z"},
                {"measure": "mean", "side": "above", "first": "2026-10-16", "last_at": "2026-10-20T01:00:00+00:00"},
                {"measure": "mean", "side": "above", "first": "2026-10-17", "last_at": "2026-10-20T06:00:00+00:00"},
                {"measure": "current_share", "side": "above", "first": "2026-10-22", "last_at": "2026-10-31T06:00:00Z"}]

    def test_a_rise_keeps_the_episodes_above_the_range_running_after_the_split(self):
        kept = episodes_behind(self.EPISODES, "mean", 0.5, self.SPLIT)
        self.assertEqual([e["first"] for e in kept], ["2026-10-22", "2026-10-17"])

    def test_a_fall_keeps_the_episodes_below_the_range(self):
        self.assertEqual([e["first"] for e in episodes_behind(self.EPISODES, "mean", -0.5, self.SPLIT)],
                         ["2026-10-23"])


class ItalianDatesTest(unittest.TestCase):

    def test_a_preposition_elides_before_8_and_11_and_the_first_of_the_month_is_1st(self):
        it = [fmt_date(d, "it") for d in ("2026-10-01", "2026-10-08", "2026-10-11", "2026-10-21")]
        self.assertEqual(it[0], "1° ottobre 2026")
        self.assertEqual(phrase("it", "compared_period", start=it[1], end=it[2]),
                         "Il confronto è con il periodo precedente, dall'8 ottobre 2026 all'11 ottobre 2026.")
        self.assertEqual(phrase("it", "compared_period", start=it[0], end=it[3]),
                         "Il confronto è con il periodo precedente, dal 1° ottobre 2026 al 21 ottobre 2026.")
        self.assertEqual(phrase("it", "span_day", start=it[1]), "l'8 ottobre 2026")
        self.assertEqual(phrase("it", "compared_day", start=it[2]), "Il confronto è con la rilevazione precedente, "
                                                                  "dell'11 ottobre 2026.")
        self.assertTrue(phrase("it", "reworded", since=it[1], previous="a", text="b").startswith("Dall'8 ottobre"))

    def test_english_dates_are_unchanged(self):
        self.assertEqual(phrase("en", "compared_period", start=fmt_date("2026-10-08", "en"),
                                end=fmt_date("2026-10-01", "en")),
                         "The comparison is with the previous period, from 8 October 2026 to 1 October 2026.")


class DocsTest(unittest.TestCase):

    def test_the_readme_dates_a_movement_only_where_the_runs_allow_it(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("the date each movement\n   started", readme)
        self.assertIn("daily runs", readme.split("4. **`report`, first time.**", 1)[1].split("5. **", 1)[0])

    def test_the_architecture_caps_the_domain_lists_across_dimensions_and_projects(self):
        text = " ".join((REPO / "ARCHITECTURE.md").read_text(encoding="utf-8").split())
        self.assertIn("five per list across all dimensions and projects", text)


class VerdictMoveTest(StudyCase, unittest.TestCase):

    def test_with_two_earlier_periods_a_verdict_change_needs_a_move_of_0_3(self):
        """Weekly reports on daily runs from 1 October: the first report on 21 October compares
        with two rebuilt weeks. Acme Chat's employer mean goes from 22/7 to 25/7 (0.43), Orbit
        Reason's from 24/7 to 25/7 (0.14); both cross into favourable."""
        def rows(d):
            week, i = divmod(d - 1, 7)
            gpt = 4 if (week < 2 and i == 0) or (week == 2 and i < 4) else 3
            gem = 4 if (week < 2 and i < 3) or (week == 2 and i < 4) else 3
            return [(PRICE_Q, m, *OLD_PRICE) for m in (GPT, GEM)] + [(CHOICE_Q, m, *NOT_CHOSEN) for m in (GPT, GEM)] + [
                (WORK_Q, GPT, EMPLOYER[0], gpt, EMPLOYER[2]), (WORK_Q, GEM, EMPLOYER[0], gem, EMPLOYER[2])]
        self.adopt_market(rows(1), report_every="weekly")
        for d in range(1, 22):
            self.ingest_market(9300 + d, f"2026-10-{d:02d}T06:00:00Z", rows(d))
        self.build("2026-10-21")
        c = self.period_file("2026-10-21")["comparison"]
        self.assertEqual(c["range_of"], ["2026-10-07", "2026-10-14"])
        self.assertEqual([(v["dimension"], v["model"], v["from"], v["to"]) for v in c["verdict_changes"]],
                         [("lavoro", GPT, "mixed", "favourable")])


class SecondReportTest(HalvesCase, unittest.TestCase):

    def test_the_second_report_compares_with_the_whole_first_period_and_never_with_its_halves(self):
        self.history()
        self.publish(REPORT)
        for n, start in enumerate(("2026-11-02", "2026-11-09", "2026-11-16", "2026-11-23")):
            self.ingest_market(9201 + n, f"{start}T06:00:00Z", rows_of(24))
        self.build("2026-11-30")
        c = self.comparison("2026-11-30")
        self.assertEqual((c["previous"], c["range_of"]), (REPORT, [REPORT]))
        self.assertNotIn("halves", c)
        self.assertEqual(c["previous_period"]["from"], day(1))
        whole = self.period_file(REPORT)["projects"]["market"]["dimensions"]["lavoro"]["total"]["mean"]
        self.assertEqual(c["dimensions"]["lavoro"]["mean"]["previous"], whole)
        self.assertEqual(c["dimensions"]["lavoro"]["mean"]["periods"], 1)
        self.assertEqual(self.half_files(), [f"{REPORT}.first.json", f"{REPORT}.second.json"])
        self.assertEqual(self.read("history/reports.json")[0]["previous"], None)


if __name__ == "__main__":
    unittest.main()
