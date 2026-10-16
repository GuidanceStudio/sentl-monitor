"""`detect`: a saved get-project-tool response that differs from the latest version
becomes a `detected` version; runs inside its window match either text."""

import unittest

from fixtures import GEM, GPT, NEW, StudyCase, project, run

ADOPTED = "2026-09-30T12:00:00Z"
SEEN = "2026-10-31T12:00:00Z"
FOUND = "2026-11-30T12:00:00Z"
OLD_TEXT = "Il latte d'avena Avenello fa bene alla salute?"
NEW_TEXT = "Bere ogni giorno il latte d'avena Avenello fa bene?"


def edited(text=None, rubric=None, add_model=None, rounds=None, archive_prezzo=False,
           drop_question=None, add_question=False, add_dimension=False):
    p = project()
    proj = p["project"]
    salute, prezzo = proj["dimensions"][0], proj["dimensions"][1]
    if text:
        salute["questions"][1]["question"] = text
    if rubric:
        prezzo["questions"][0]["grading_rubric"]["5"] = rubric
    if add_model:
        proj["researcher_model_ids"].append(add_model)
    if rounds:
        proj["rounds"] = rounds
    if archive_prezzo:
        prezzo["archived"] = True
    if drop_question:
        salute["questions"] = [q for q in salute["questions"] if q["id"] != drop_question]
    if add_question:
        salute["questions"].append({"id": 105, "label": "Avenello e glutine",
                                    "question": "Il latte d'avena Avenello contiene glutine?",
                                    "grading_rubric": {"1": "a", "2": "b", "3": "c", "4": "d", "5": "e"},
                                    "additional_instructions": ""})
    if add_dimension:
        proj["dimensions"].append({"id": 14, "name": "Gusto", "archived": False, "questions": [
            {"id": 106, "label": "Gusto Avenello", "question": "Che sapore ha il latte d'avena Avenello?",
             "grading_rubric": {"1": "a", "2": "b", "3": "c", "4": "d", "5": "e"},
             "additional_instructions": ""}]})
    return p


class DetectTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)

    def question(self, key):
        study = self.read("study.json")
        return next(q for d in study["projects"][0]["dimensions"] for q in d["questions"] if q["key"] == key)

    def test_an_unchanged_project_records_no_version_and_is_marked_seen(self):
        proc = self.detect(project(), SEEN)
        self.assertIn("unchanged", proc.stdout)
        self.assertFalse((self.study / "history/versions/brand-002.json").exists())
        self.assertEqual(self.read("history/versions/brand-001.json")["seen_at"], SEEN)

    def test_a_difference_of_quotes_and_spacing_only_is_no_change(self):
        p = project()
        q = p["project"]["dimensions"][0]["questions"][0]
        q["question"] = q["question"].replace("’", "'").replace(" fa ", "  fa ")
        self.detect(p, SEEN)
        self.assertFalse((self.study / "history/versions/brand-002.json").exists())

    def test_a_reworded_question_is_a_detected_version_with_its_window(self):
        self.detect(project(), SEEN)
        proc = self.detect(edited(text=NEW_TEXT), FOUND)
        v = self.read("history/versions/brand-002.json")
        self.assertEqual((v["version"], v["source"], v["recorded_at"]), (2, "detected", FOUND))
        self.assertEqual(v["window"], {"from": SEEN, "to": FOUND})
        self.assertEqual(v["changes"], [{"question": "salute-2", "change": "reworded"}])
        self.assertEqual(self.read("sentl.json")["projects"]["brand"]["version"], 2)
        q = self.question("salute-2")
        self.assertEqual(q["text"], NEW_TEXT)
        self.assertEqual(q["lineage"][-1], {"version": 2, "change": "reworded"})
        self.assertIn(NEW_TEXT, proc.stdout)
        self.assertIn("--new-intent", proc.stdout)

    def test_a_window_opens_at_the_adopt_version_when_it_was_never_seen_again(self):
        self.detect(edited(text=NEW_TEXT), FOUND)
        self.assertEqual(self.read("history/versions/brand-002.json")["window"], {"from": ADOPTED, "to": FOUND})

    def test_a_dry_run_lists_the_changes_and_writes_nothing(self):
        proc = self.detect(edited(text=NEW_TEXT), FOUND, "--dry-run")
        self.assertIn("reworded", proc.stdout)
        self.assertFalse((self.study / "history/versions/brand-002.json").exists())
        self.assertEqual(self.question("salute-2")["text"], OLD_TEXT)

    def test_criteria_models_and_rounds_are_classified(self):
        self.detect(edited(rubric="Prezzo corretto, con la fonte del listino", add_model=NEW, rounds=3), FOUND)
        v = self.read("history/versions/brand-002.json")
        self.assertIn({"question": "prezzo-1", "change": "criteria"}, v["changes"])
        self.assertIn({"change": "models", "added": [NEW], "removed": []}, v["changes"])
        self.assertIn({"change": "rounds", "from": 1, "to": 3}, v["changes"])
        self.assertEqual(v["settings"]["models"], [GPT, GEM, NEW])
        proj = self.read("study.json")["projects"][0]
        self.assertEqual((proj["models"], proj["rounds"]), ([GPT, GEM, NEW], 3))
        self.assertEqual(self.question("prezzo-1")["rubric"]["5"], "Prezzo corretto, con la fonte del listino")

    def test_archived_and_new_dimensions_and_a_new_question_get_keys_and_ids(self):
        self.detect(edited(archive_prezzo=True, add_question=True, add_dimension=True), FOUND)
        changes = self.read("history/versions/brand-002.json")["changes"]
        for change in ({"dimension": "prezzo", "change": "dimension_archived"},
                       {"question": "salute-3", "change": "created"},
                       {"dimension": "gusto", "change": "dimension_added"},
                       {"question": "gusto-1", "change": "created"}):
            self.assertIn(change, changes)
        binding = self.read("sentl.json")["projects"]["brand"]
        self.assertEqual((binding["questions"]["salute-3"], binding["questions"]["gusto-1"],
                          binding["dimensions"]["gusto"]), (105, 106, 14))
        study = self.read("study.json")
        dims = {d["key"]: d for d in study["projects"][0]["dimensions"]}
        self.assertTrue(dims["prezzo"]["archived"])
        self.assertEqual(dims["gusto"]["questions"][0]["lineage"], [{"version": 2, "change": "created"}])
        self.assertIn({"id": "gusto", "label": "Gusto", "origins": [], "dimension": "gusto"}, study["themes"])

    def test_a_question_deleted_in_sentl_is_retired(self):
        self.detect(edited(drop_question=102), FOUND)
        self.assertIn({"question": "salute-2", "change": "retired"},
                      self.read("history/versions/brand-002.json")["changes"])
        self.assertNotIn("salute-2", self.read("sentl.json")["projects"]["brand"]["questions"])
        keys = [q["key"] for d in self.read("study.json")["projects"][0]["dimensions"] for q in d["questions"]]
        self.assertNotIn("salute-2", keys)

    def test_a_new_intent_gives_the_question_a_new_key_and_retires_the_old_one(self):
        self.detect(edited(text=NEW_TEXT), FOUND, "--new-intent", "salute-2")
        v = self.read("history/versions/brand-002.json")
        self.assertEqual(v["changes"], [{"question": "salute-3", "change": "new_intent", "replaces": "salute-2"},
                                        {"question": "salute-2", "change": "retired"}])
        questions = self.read("sentl.json")["projects"]["brand"]["questions"]
        self.assertEqual(questions["salute-3"], 102)
        self.assertNotIn("salute-2", questions)
        q = self.question("salute-3")
        self.assertEqual((q["text"], q["lineage"]),
                         (NEW_TEXT, [{"version": 2, "change": "new_intent", "replaces": "salute-2"}]))

    def test_a_saved_project_of_another_sentl_project_is_refused(self):
        other = project()
        other["project"]["id"] = 777
        self.detect(other, FOUND, check=2)


class WindowMatchTest(StudyCase, unittest.TestCase):
    """Version 2 adds a model and rewords salute-2; the edit lies somewhere in its window."""

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)
        self.detect(project(), SEEN)
        self.detect(edited(text=NEW_TEXT, add_model=NEW), FOUND)

    def ingested(self, run_id, started, models, text):
        self.ingest(run(run_id=run_id, started=started, models=models, texts={"salute-2": text}),
                    name=f"run-{run_id}.json")
        snap = self.read_run("brand", run_id)
        return snap, {(r["question"], r["model"]): r["match"] for r in snap["responses"]}

    def test_a_run_before_the_window_matches_the_earlier_version(self):
        snap, matches = self.ingested(9101, "2026-10-26T06:00:00Z", [GPT, GEM], OLD_TEXT)
        self.assertEqual(snap["version"], 1)
        self.assertEqual(set(matches.values()), {"exact"})

    def test_a_run_inside_the_window_with_the_earlier_configuration_takes_the_earlier_version(self):
        snap, matches = self.ingested(9102, "2026-11-09T06:00:00Z", [GPT, GEM], OLD_TEXT)
        self.assertEqual((snap["version"], snap["expected"]), (1, 6))
        self.assertEqual(set(matches.values()), {"exact"})

    def test_a_response_inside_the_window_matches_the_previous_text(self):
        snap, matches = self.ingested(9103, "2026-11-16T06:00:00Z", [GPT, GEM, NEW], OLD_TEXT)
        self.assertEqual((snap["version"], snap["expected"], snap["judged"]), (2, 9, 9))
        self.assertEqual(matches[("salute-2", NEW)], "version")
        self.assertEqual(matches[("salute-1", NEW)], "exact")

    def test_a_run_after_the_window_with_the_earlier_text_is_unmatched(self):
        snap, matches = self.ingested(9104, "2026-12-07T06:00:00Z", [GPT, GEM, NEW], OLD_TEXT)
        self.assertEqual(snap["version"], 2)
        self.assertEqual(matches[(None, GPT)], "unmatched")

    def test_a_run_after_the_window_with_the_current_text_matches_exactly(self):
        snap, matches = self.ingested(9105, "2026-12-07T06:00:00Z", [GPT, GEM, NEW], NEW_TEXT)
        self.assertEqual(set(matches.values()), {"exact"})


class EarlierWordingTest(StudyCase, unittest.TestCase):
    """A1: an earlier run returns the text asked at the time."""

    def test_a_run_older_than_the_first_version_with_an_earlier_wording_is_unmatched(self):
        self.adopt(at="2026-10-16T09:00:00Z")
        self.ingest(run(run_id=9001, started="2026-09-01T06:00:00Z",
                        texts={"salute-2": "Il latte d'avena Avenello è salutare?"}))
        snap = self.read_run("brand", 9001)
        self.assertIsNone(snap["version"])
        self.assertEqual([r["model"] for r in snap["responses"] if r["match"] == "unmatched"], [GPT, GEM])
        self.assertEqual((snap["expected"], snap["judged"]), (6, 4), "the unmatched question still counts as asked")


if __name__ == "__main__":
    unittest.main()
