"""Periods pool the runs since the previous report and compare with the earlier periods
(ARCHITECTURE.md §Periods, §Comparability, §What counts as a change)."""

import unittest

from fixtures import ANSWERS, GEM, GPT, NEW, RETIRED, StudyCase, models, project, run, weekly
from test_detect import ADOPTED, FOUND, NEW_TEXT, OLD_TEXT, edited

OCT = weekly("2026-10-05", 4)
NOV = weekly("2026-11-02", 5)
CHEAPER = "Avenello costa poco più del latte vaccino, secondo i listini."


def runs(starts, first_id, **kw):
    return [run(run_id=first_id + n, started=s, **kw) for n, s in enumerate(starts)]


def without_prezzo(data):
    data["run"]["responses"] = [r for r in data["run"]["responses"] if r["dimension"] != "Prezzo"]
    return data


class PoolingTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)

    def test_four_weekly_runs_pool_into_one_monthly_period(self):
        self.answer_operator()
        lower = {("salute-1", GPT): ANSWERS[("salute-1", GPT)][:1] + (2,) + ANSWERS[("salute-1", GPT)][2:]}
        self.ingest_all([run(run_id=9101, started=OCT[0]), run(run_id=9102, started=OCT[1]),
                         run(run_id=9103, started=OCT[2], overrides=lower),
                         run(run_id=9104, started=OCT[3], overrides=lower),
                         run(run_id=9105, started="2026-11-02T06:00:00Z")])
        self.build("2026-10-31")
        p = self.period_file("2026-10-31")
        self.assertEqual(p["runs"], {"brand": [9101, 9102, 9103, 9104]})
        self.assertEqual((p["from"], p["to"]), (OCT[0], OCT[3]))
        salute = p["projects"]["brand"]["dimensions"]["salute"]
        self.assertEqual((salute["total"]["judged"], salute["total"]["expected"]), (16, 16))
        self.assertAlmostEqual(salute["total"]["mean"], 3.5)
        self.assertAlmostEqual(salute["questions"]["salute-1"]["by_model"][GPT]["mean"], 3.0)
        self.assertIn({"question": "salute-1", "model": GPT}, salute["total"]["unstable_pairs"])

    def test_daily_runs_pool_into_a_weekly_period(self):
        self.answer_operator(report_every="weekly")
        self.ingest_all([run(run_id=9100 + day, started=f"2026-10-{day}T06:00:00Z") for day in range(24, 32)])
        self.build("2026-10-31")
        p = self.period_file("2026-10-31")
        self.assertEqual(p["runs"], {"brand": list(range(9125, 9132))})
        self.assertEqual(p["projects"]["brand"]["total"]["expected"], 7 * 6)
        earlier = self.period_file("2026-10-24")
        self.assertEqual((earlier["runs"], earlier["rebuilt"]), ({"brand": [9124]}, True))


class RoundsTest(StudyCase, unittest.TestCase):

    def test_rounds_pool_as_repeated_responses(self):
        three = project()
        three["project"]["rounds"] = 3
        self.adopt(at=ADOPTED, project_data=three)
        self.answer_operator()
        self.ingest_all(runs(OCT[:2], 9101, rounds=3))
        self.build("2026-10-31")
        salute = self.period_file("2026-10-31")["projects"]["brand"]["dimensions"]["salute"]
        self.assertEqual((salute["total"]["received"], salute["total"]["expected"]), (24, 24))
        pair = salute["questions"]["salute-1"]["by_model"][GPT]
        self.assertEqual((pair["received"], pair["expected"]), (6, 6))


class CadenceTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)

    def test_without_a_report_cadence_the_period_is_refused(self):
        self.ingest(run())
        proc = self.build("2026-10-31", check=2)
        self.assertIn("report_every", proc.stdout + proc.stderr)

    def test_a_criteria_change_inside_the_period_keeps_the_runs_of_the_latest_version_only(self):
        self.answer_operator()
        self.ingest_all(runs(OCT[:2], 9101))
        self.detect(project(), "2026-10-13T12:00:00Z")
        self.detect(edited(rubric="Prezzo corretto, con la fonte del listino"), "2026-10-15T12:00:00Z")
        self.ingest_all(runs(OCT[2:], 9103))
        proc = self.build("2026-10-31")
        p = self.period_file("2026-10-31")
        self.assertEqual(p["versions"], {"brand": [1, 1, 2, 2]})
        dims = p["projects"]["brand"]["dimensions"]
        self.assertEqual(dims["prezzo"]["total"]["expected"], 4)
        self.assertEqual(dims["salute"]["total"]["expected"], 16)
        self.assertIn("criteria", proc.stdout)


class CriteriaWindowTest(StudyCase, unittest.TestCase):
    """A criteria edit cannot be placed inside its window: a run there may have been judged
    under either rubric."""

    def test_a_criteria_edit_inside_a_window_keeps_only_runs_known_to_be_under_the_new_criteria(self):
        self.adopt(at=ADOPTED)
        self.answer_operator()
        self.detect(edited(rubric="Prezzo corretto, con la fonte del listino"), "2026-10-15T12:00:00Z")
        self.ingest_all(runs(OCT, 9101))  # 5 and 12 October inside the window, 19 and 26 after it
        self.build("2026-10-31")
        dims = self.period_file("2026-10-31")["projects"]["brand"]["dimensions"]
        self.assertEqual(dims["prezzo"]["total"]["expected"], 4)
        self.assertEqual(dims["salute"]["total"]["expected"], 16)

    def test_a_run_with_no_version_loses_a_question_whose_criteria_changed_later_in_the_period(self):
        self.adopt(at="2026-10-10T00:00:00Z")
        self.answer_operator()
        self.detect(edited(rubric="Prezzo corretto, con la fonte del listino"), "2026-10-15T12:00:00Z")
        self.ingest_all([run(run_id=9101, started=OCT[0])] + runs(OCT[2:], 9103))
        self.build("2026-10-31")
        p = self.period_file("2026-10-31")
        self.assertEqual(p["versions"], {"brand": [None, 2, 2]})
        self.assertEqual(p["projects"]["brand"]["dimensions"]["prezzo"]["total"]["expected"], 4)


class LaterPeriodTest(StudyCase, unittest.TestCase):
    """A report on 31 October, then the November runs compared with it."""

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101))
        self.publish("2026-10-31")

    def november(self, all_overrides=None, per_run=None, **kw):
        for n, start in enumerate(NOV):
            overrides = {**(all_overrides or {}), **(per_run or {}).get(n, {})}
            self.ingest(run(run_id=9201 + n, started=start, overrides=overrides, **kw), name=f"run-{9201 + n}.json")

    def comparison(self):
        self.build("2026-11-30")
        return self.period_file("2026-11-30")["comparison"]

    def test_the_period_covers_the_runs_after_the_last_run_of_the_previous_report(self):
        self.november()
        c = self.comparison()
        p = self.period_file("2026-11-30")
        self.assertEqual(p["runs"], {"brand": [9201, 9202, 9203, 9204, 9205]})
        self.assertEqual((c["previous"], c["range_of"]), ("2026-10-31", ["2026-10-31"]))
        salute = c["dimensions"]["salute"]
        self.assertEqual((salute["status"], salute["models"]), ("compared", [GPT, GEM]))
        self.assertAlmostEqual(salute["mean"]["delta"], 0.0)
        self.assertFalse(salute["mean"]["changed"])
        self.assertEqual(c["verdict_changes"], [])
        self.assertEqual(c["design_changes"], [])

    def test_a_move_beyond_the_threshold_is_a_change_and_a_new_band_a_verdict_change(self):
        self.november(all_overrides={("prezzo-1", GEM): (CHEAPER, 4, "positive", ["https://prezzi.example/avena"])})
        c = self.comparison()
        prezzo = c["dimensions"]["prezzo"]["mean"]
        self.assertEqual((prezzo["now"], prezzo["previous"], prezzo["range"], prezzo["periods"]),
                         (3.5, 2.5, [2.5, 2.5], 1))
        self.assertAlmostEqual(prezzo["delta"], 1.0)
        self.assertTrue(prezzo["changed"])
        self.assertTrue(c["dimensions"]["prezzo"]["questions"]["prezzo-1"]["mean"]["changed"])
        [verdict] = c["verdict_changes"]
        self.assertEqual({k: verdict[k] for k in ("dimension", "question", "model", "from", "to")},
                         {"dimension": "prezzo", "question": "prezzo-1", "model": GEM,
                          "from": "unfavourable", "to": "favourable"})
        self.assertEqual((verdict["previous_mean"], verdict["mean"]), (2.0, 4.0))
        self.assertIn(verdict["previous_answer"]["run_id"], range(9101, 9105))
        self.assertIn(verdict["answer"]["run_id"], range(9201, 9206))
        material = (self.study / "history/material/2026-11-30.md").read_text(encoding="utf-8")
        self.assertIn(CHEAPER, material)
        self.assertIn(ANSWERS[("prezzo-1", GEM)][0], material)

    def test_new_and_lost_domains_per_dimension(self):
        def cited(*urls):
            return {("prezzo-1", GEM): (ANSWERS[("prezzo-1", GEM)][0], 2, "negative", list(urls))}
        self.november(all_overrides={("prezzo-1", GPT): (ANSWERS[("prezzo-1", GPT)][0], 3, "neutral",
                                                         ["https://confronto.example/latte"]), **cited()},
                      per_run={0: cited("https://listino.avenello.example/2026"),
                               1: cited("https://listino.avenello.example/2026"),
                               2: cited("https://blog.example/avena")})
        c = self.comparison()
        new = {(d["dimension"], d["domain"]): (d["answers"], d["owned"]) for d in c["domains"]["new"]}
        self.assertEqual(new, {("prezzo", "confronto.example"): (5, False),
                               ("prezzo", "listino.avenello.example"): (2, True)})
        self.assertEqual([(d["dimension"], d["domain"], d["answers"]) for d in c["domains"]["lost"]],
                         [("prezzo", "prezzi.example", 8)])

    def test_a_reworded_question_is_compared_and_its_new_wording_reported(self):
        self.detect(edited(text=NEW_TEXT), FOUND)
        self.november(texts={"salute-2": NEW_TEXT})
        c = self.comparison()
        self.assertEqual(c["dimensions"]["salute"]["questions"]["salute-2"]["status"], "compared")
        self.assertEqual(c["design_changes"], [{"project": "brand", "change": "reworded", "question": "salute-2",
                                                "text": NEW_TEXT, "previous_text": OLD_TEXT, "since": "2026-11-02"}])

    def test_a_question_with_a_new_intent_starts_a_new_baseline(self):
        self.detect(edited(text=NEW_TEXT), FOUND, "--new-intent", "salute-2")
        self.november(texts={"salute-2": NEW_TEXT},
                      all_overrides={("salute-2", GEM): ("Avenello non fa bene.", 1, "negative", [])})
        c = self.comparison()
        salute = c["dimensions"]["salute"]
        self.assertEqual(salute["questions"]["salute-3"], {"status": "new_baseline", "reason": "new_intent"})
        self.assertEqual(salute["compared_questions"], ["salute-1"])
        self.assertEqual([v for v in c["verdict_changes"] if v["question"] == "salute-3"], [])
        self.assertEqual(c["design_changes"], [{"project": "brand", "change": "new_intent", "question": "salute-3",
                                                "replaces": "salute-2", "text": NEW_TEXT,
                                                "previous_text": OLD_TEXT, "since": "2026-11-02"}])

    def test_changed_criteria_start_a_new_baseline_and_list_no_verdict(self):
        self.detect(edited(rubric="Prezzo corretto, con la fonte del listino"), "2026-11-01T12:00:00Z")
        self.november(all_overrides={("prezzo-1", GEM): (CHEAPER, 4, "positive", [])})
        c = self.comparison()
        prezzo = c["dimensions"]["prezzo"]
        self.assertEqual(prezzo["status"], "new_baseline")
        self.assertEqual(prezzo["questions"]["prezzo-1"], {"status": "new_baseline", "reason": "criteria"})
        self.assertEqual(c["verdict_changes"], [])
        self.assertEqual(c["design_changes"], [{"project": "brand", "change": "criteria", "question": "prezzo-1",
                                                "text": "Quanto costa il latte d'avena Avenello rispetto al latte vaccino?",
                                                "since": "2026-11-02"}])

    def test_an_added_model_is_left_out_of_the_comparison(self):
        self.detect(edited(add_model=NEW), FOUND)
        self.november(models=[GPT, GEM, NEW], all_overrides={("salute-1", NEW): ("Avenello fa male.", 1, "negative", [])})
        c = self.comparison()
        self.assertEqual(c["dimensions"]["salute"]["models"], [GPT, GEM])
        self.assertAlmostEqual(c["dimensions"]["salute"]["mean"]["now"], 3.75)
        self.assertEqual(c["verdict_changes"], [])
        self.assertEqual(c["design_changes"], [{"project": "brand", "change": "models", "added": [NEW], "removed": [],
                                                "basis": [GPT, GEM]}])

    def test_an_archived_dimension_is_no_longer_measured(self):
        self.detect(edited(archive_prezzo=True), FOUND)
        for n, start in enumerate(NOV):
            self.ingest(without_prezzo(run(run_id=9201 + n, started=start)), name=f"run-{9201 + n}.json")
        c = self.comparison()
        self.assertNotIn("prezzo", c["dimensions"])
        self.assertEqual(c["design_changes"], [{"project": "brand", "change": "dimension_archived",
                                                "dimension": "prezzo", "name": "Prezzo"}])

    def test_an_added_dimension_is_new(self):
        self.detect(edited(add_dimension=True), FOUND)
        gusto = [{"id": 1, "model_id": m, "question": "Che sapore ha il latte d'avena Avenello?", "dimension": "Gusto",
                  "answer": "Avenello sa di avena.", "judge_score": 4, "sentiment": "positive", "sources": []}
                 for m in (GPT, GEM)]
        for n, start in enumerate(NOV):
            self.ingest(run(run_id=9201 + n, started=start, extra=gusto), name=f"run-{9201 + n}.json")
        c = self.comparison()
        self.assertEqual(c["dimensions"]["gusto"]["status"], "new")
        self.assertIn({"project": "brand", "change": "dimension_added", "dimension": "gusto", "name": "Gusto"},
                      c["design_changes"])


    def test_runs_made_before_a_dimension_was_added_keep_the_earlier_version(self):
        self.detect(edited(add_dimension=True), FOUND)
        self.november()
        self.build("2026-11-30")
        self.assertEqual(self.period_file("2026-11-30")["versions"], {"brand": [1, 1, 1, 1, 1]})

    def test_an_edit_after_the_last_run_of_the_period_is_left_to_the_next_period(self):
        self.november()
        self.detect(edited(text=NEW_TEXT, add_dimension=True), FOUND)
        self.answer_operator()
        c = self.comparison()
        self.assertNotIn("gusto", c["dimensions"])
        self.assertEqual(c["design_changes"], [])
        material = (self.study / "history/material/2026-11-30.md").read_text(encoding="utf-8")
        self.assertIn(OLD_TEXT, material)
        self.assertNotIn(NEW_TEXT, material)
        self.cli("method", "--study", self.study, "--date", "2026-11-30",
                 "--models", self.save("models.json", models()), check=0)
        report = (self.study / "reports/2026-11-30.md").read_text(encoding="utf-8")
        self.assertIn(OLD_TEXT, report)
        self.assertNotIn(NEW_TEXT, report)
        self.assertNotIn("Gusto", report)


class ModelsAcrossPeriodsTest(StudyCase, unittest.TestCase):
    """October answered by a model Sentl no longer lists (A5), November by another one."""

    def test_deltas_are_computed_on_the_models_present_in_both_periods(self):
        self.adopt(at="2026-11-01T00:00:00Z")
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101, models=[GPT, RETIRED]))
        lower = {("salute-1", GPT): ("Avenello contiene zuccheri.", 2, "negative", [])}
        self.ingest_all(runs(NOV, 9201, models=[GPT, GEM], overrides=lower))
        self.build("2026-11-30")
        p = self.period_file("2026-11-30")
        c = p["comparison"]
        self.assertEqual(c["previous"], "2026-10-31")
        salute = c["dimensions"]["salute"]
        self.assertEqual(salute["models"], [GPT])
        self.assertEqual((salute["mean"]["now"], salute["mean"]["previous"]), (3.5, 4.5))
        self.assertTrue(salute["mean"]["changed"])
        self.assertEqual([(v["question"], v["model"]) for v in c["verdict_changes"]], [("salute-1", GPT)])
        self.assertIn({"project": "brand", "change": "models", "added": [GEM], "removed": [RETIRED], "basis": [GPT]},
                      c["design_changes"])
        self.assertEqual(p["names"][RETIRED], "legacy-7b (oldco)")

    def test_the_range_ends_at_the_first_period_without_one_of_the_compared_models(self):
        self.adopt(at="2027-01-01T00:00:00Z")
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101, models=[GPT, GEM]) + runs(NOV, 9201, models=[GPT, GEM, NEW])
                        + runs(weekly("2026-12-07", 4), 9301, models=[GPT, GEM, NEW]))
        self.build("2026-12-31")
        c = self.period_file("2026-12-31")["comparison"]
        self.assertEqual(c["range_of"], ["2026-10-31", "2026-11-30"])
        self.assertEqual(c["dimensions"]["salute"]["models"], [GPT, GEM, NEW])
        self.assertEqual(c["dimensions"]["salute"]["mean"]["periods"], 1)


if __name__ == "__main__":
    unittest.main()
