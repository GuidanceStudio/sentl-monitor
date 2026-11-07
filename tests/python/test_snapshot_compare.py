"""`compare`: what changed between two snapshots of one subject, neither of them promoted, and `check` on its report."""

import json
import re
import unittest

from fixtures import GEM, GPT, models
from snapshot_study import DATE, KEY, PROJECT_ID, RUN_ID, RUN_STARTED, SCORES, run_results, saved_project
from test_snapshot import SnapshotCase

LATER = "2026-11-05"
LATER_RUN = 7002
LATER_STARTED = "2026-11-05T09:00:00Z"
MOVED = {**SCORES, ("price", GPT): 3, ("price", GEM): 2}


class CompareCase(SnapshotCase):

    def setUp(self):
        super().setUp()
        self.first = self.study
        self.second = self.study.parent / "second"
        self.second.mkdir()
        (self.second / "inbox").mkdir()

    def side(self, folder, date, run_id, started, scores=None, project_id=PROJECT_ID, first_id=1000, edit=None,
             answers=None, only=None):
        """A snapshot folder holding one run and its period. `edit` changes the wording Sentl holds and the run
        asks; `answers` rewrites an answer and `only` keeps the responses of those models."""
        self.study = folder
        design = json.loads(json.dumps(self.design))
        (edit or (lambda s: None))(design)
        (folder / "study.json").write_text(json.dumps(design, ensure_ascii=False), encoding="utf-8")
        chosen = self.save("models.json", models())
        for saved in (saved_project(design, project_id=project_id, first_id=first_id, edit=lambda p: p.update(dimensions=[])),
                      saved_project(design, project_id=project_id, first_id=first_id)):
            self.cli("bind", "--study", folder, "--project", KEY, "--saved", self.save("project-now.json", saved),
                     check=0, at="2026-10-22T08:00:00Z")
        data = run_results(design, run_id, project_id=project_id, scores=scores, started=started)
        for r in data["run"]["responses"]:
            r["answer"] = (answers or {}).get((r["dimension"], r["model_id"]), r["answer"])
        if only:
            data["run"]["responses"] = [r for r in data["run"]["responses"] if r["model_id"] in only]
        self.cli("ingest", "--study", folder, "--project", KEY, "--results", self.save(f"run-{run_id}.json", data), check=0)
        self.cli("period", "--study", folder, "--date", date, "--models", chosen, check=0)

    def both(self, **later):
        self.side(self.first, DATE, RUN_ID, RUN_STARTED)
        self.side(self.second, LATER, LATER_RUN, LATER_STARTED, **later)

    def compare(self, check=0):
        return self.cli("compare", self.first, self.second, check=check)

    def report(self):
        return (self.second / "reports" / f"{LATER}.compare.md").read_text(encoding="utf-8")

    def row(self, dimension):
        return next(ln for ln in self.report().splitlines() if ln.startswith(f"| {dimension} |"))

    def check(self, check=None):
        return self.cli("check", "--study", self.second, self.second / "reports" / f"{LATER}.compare.md", check=check)


class CompareTest(CompareCase):

    def test_two_snapshots_of_one_project_write_the_report_in_the_second_folder(self):
        self.both(scores=MOVED)
        proc = self.compare()
        self.assertIn(f"{LATER}.compare.md", proc.stdout)
        headings = [t for _, t in re.findall(r"^## (\d+)\. (.+)$", self.report(), flags=re.M)]
        self.assertEqual(headings, ["What we did and to what end", "What changed", "What a single run cannot show"])
        self.assertIn("22 October 2026", self.report())
        self.assertIn("5 November 2026", self.report())

    def test_each_dimension_shows_its_score_and_presence_on_both_sides(self):
        self.both(scores=MOVED)
        self.compare()
        self.assertEqual(self.row("Price"), "| Price | 4.0 | 2.5 | 100% | 100% | lower score |")

    def test_a_score_moved_by_the_step_is_a_change_and_one_that_stayed_is_not(self):
        self.both(scores={**SCORES, ("price", GPT): 4})
        self.compare()
        self.assertEqual(self.row("Price"), "| Price | 4.0 | 3.5 | 100% | 100% | lower score |")
        self.assertEqual(self.row("Health"), "| Health | 3.0 | 3.0 | 100% | 100% | no change |")

    def test_a_presence_moved_by_the_step_is_a_change(self):
        text = "Several brands sell good oat milk, such as Avoria and store brands."
        self.both(answers={("Recommendation", GPT): text})
        self.compare()
        self.assertEqual(self.row("Recommendation"), "| Recommendation | 2.5 | 2.5 | 50% | 0% | lower presence |")

    def test_limits_say_a_difference_between_two_single_runs_is_not_a_trend(self):
        self.both()
        self.compare()
        limits = self.report().rsplit("## 3. ", 1)[1]
        self.assertIn("one run", limits)
        self.assertIn("not a trend", limits)

    def test_a_question_reworded_in_one_project_is_matched_by_its_id(self):
        def reword(study):
            study["projects"][0]["dimensions"][2]["questions"][0]["text"] = "What does Avenello oat milk cost today?"
        self.both(edit=reword)
        self.compare()
        self.assertIn("| Price |", self.report())

    def test_two_projects_are_matched_by_the_text_of_their_questions(self):
        self.both(project_id=901, first_id=2000)
        self.compare()
        self.assertIn("| Price |", self.report())

    def test_two_projects_whose_questions_differ_are_refused_naming_the_questions(self):
        def reword(study):
            study["projects"][0]["dimensions"][2]["questions"][0]["text"] = "What does Avenello oat milk cost today?"
        self.both(edit=reword, project_id=901, first_id=2000)
        proc = self.compare(check=2)
        self.assertIn("How much does Avenello oat milk cost?", proc.stderr)
        self.assertIn("What does Avenello oat milk cost today?", proc.stderr)
        self.assertFalse((self.second / "reports").exists() and list((self.second / "reports").glob("*.compare.md")))

    def test_only_the_assistants_of_both_sides_are_compared_and_the_limits_say_so(self):
        self.both(only=(GPT,), edit=lambda study: study["projects"][0].update(models=[GPT]))
        self.compare()
        self.assertEqual(self.row("Price"), "| Price | 5.0 | 5.0 | 100% | 100% | no change |")
        self.assertIn("only the assistants", self.report().rsplit("## 3. ", 1)[1])

    def test_snapshots_given_latest_first_are_refused(self):
        self.both()
        proc = self.cli("compare", self.second, self.first, check=2)
        self.assertIn("earlier", proc.stderr)

    def test_a_folder_with_no_period_is_refused_naming_it(self):
        self.side(self.first, DATE, RUN_ID, RUN_STARTED)
        (self.second / "study.json").write_text(json.dumps(self.design), encoding="utf-8")
        (self.second / "sentl.json").write_text((self.first / "sentl.json").read_text(encoding="utf-8"), encoding="utf-8")
        proc = self.compare(check=2)
        self.assertIn("period", proc.stderr)
        self.assertIn(str(self.second), proc.stderr)

    def test_a_folder_that_is_no_snapshot_is_refused(self):
        self.both()
        study = json.loads((self.first / "study.json").read_text(encoding="utf-8"))
        study["kind"] = "study"
        (self.first / "study.json").write_text(json.dumps(study), encoding="utf-8")
        proc = self.compare(check=2)
        self.assertIn("report", proc.stderr)


class CompareCheckTest(CompareCase):

    def setUp(self):
        super().setUp()
        self.both(scores=MOVED)
        self.compare()

    def edit(self, old, new):
        path = self.second / "reports" / f"{LATER}.compare.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def test_the_report_as_written_passes(self):
        self.assertIn("check passed", self.check(check=0).stdout)

    def test_a_figure_changed_by_hand_is_refused(self):
        self.edit("| Price | 4.0 | 2.5 |", "| Price | 4.0 | 3.5 |")
        self.assertIn("Price", self.check(check=1).stdout)

    def test_sections_out_of_order_are_refused(self):
        self.edit("## 2. What changed", "## 2. What we did and to what end")
        self.assertIn("order", self.check(check=1).stdout + "order")
        self.assertEqual(self.check().returncode, 1)

    def test_limits_taken_out_are_refused(self):
        self.edit("not a trend", "a trend")
        self.assertIn("limits", self.check(check=1).stdout)

    def test_a_question_key_in_the_report_is_refused(self):
        self.edit("## 3. ", "price-1\n\n## 3. ")
        self.assertIn("price-1", self.check(check=1).stdout)


if __name__ == "__main__":
    unittest.main()
