"""A question or a dimension that Sentl gives a new id, with the text or name of one the
project no longer holds, is the same question or dimension: it keeps its key, and so its
comparison."""

import unittest

from fixtures import StudyCase, project, run
from test_detect import ADOPTED, FOUND, NEW_TEXT, edited
from test_history import NOV, OCT, runs

EDITED = "2026-11-01T12:00:00Z"


def renumbered(questions=None, dimensions=None, data=None):
    p = data or project()
    for d in p["project"]["dimensions"]:
        d["id"] = (dimensions or {}).get(d["id"], d["id"])
        for q in d["questions"]:
            q["id"] = (questions or {}).get(q["id"], q["id"])
    return p


class RenumberedTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)

    def changes(self):
        return self.read("history/versions/brand-002.json")["changes"]

    def keys(self):
        return [q["key"] for d in self.read("study.json")["projects"][0]["dimensions"] for q in d["questions"]]

    def test_a_question_with_a_new_id_and_the_same_text_keeps_its_key(self):
        proc = self.detect(renumbered({102: 202}), FOUND)
        self.assertEqual(self.changes(), [{"question": "salute-2", "change": "renumbered", "from": 102, "to": 202}])
        self.assertEqual(self.read("sentl.json")["projects"]["brand"]["questions"],
                         {"salute-1": 101, "salute-2": 202, "prezzo-1": 103, "confezione-1": 104})
        self.assertEqual(self.keys(), ["salute-1", "salute-2", "prezzo-1", "confezione-1"])
        salute2 = self.read("study.json")["projects"][0]["dimensions"][0]["questions"][1]
        self.assertEqual(salute2["lineage"], [{"version": 1, "change": "adopted"}])
        self.assertIn("salute-2", proc.stdout)
        self.assertIn("new id", proc.stdout)

    def test_a_text_that_differs_only_by_quotes_is_the_same_text(self):
        p = renumbered({101: 201})
        q = p["project"]["dimensions"][0]["questions"][0]
        q["question"] = q["question"].replace("’", "'")
        self.detect(p, FOUND)
        self.assertEqual(self.changes(), [{"question": "salute-1", "change": "renumbered", "from": 101, "to": 201}])

    def test_a_dimension_with_a_new_id_and_the_same_name_keeps_its_key(self):
        self.detect(renumbered({101: 201, 102: 202}, {11: 21}), FOUND)
        self.assertEqual(self.changes(), [{"dimension": "salute", "change": "dimension_renumbered", "from": 11, "to": 21},
                                          {"question": "salute-1", "change": "renumbered", "from": 101, "to": 201},
                                          {"question": "salute-2", "change": "renumbered", "from": 102, "to": 202}])
        binding = self.read("sentl.json")["projects"]["brand"]
        self.assertEqual(binding["dimensions"], {"salute": 21, "prezzo": 12, "confezione": 13})
        self.assertEqual(self.keys(), ["salute-1", "salute-2", "prezzo-1", "confezione-1"])

    def test_a_dimension_renumbered_alone(self):
        self.detect(renumbered(dimensions={12: 22}), FOUND)
        self.assertEqual(self.changes(), [{"dimension": "prezzo", "change": "dimension_renumbered", "from": 12, "to": 22}])

    def test_a_new_id_with_another_text_is_a_new_question(self):
        self.detect(renumbered({102: 202}, data=edited(text=NEW_TEXT)), FOUND)
        self.assertEqual(self.changes(), [{"question": "salute-3", "change": "created"},
                                          {"question": "salute-2", "change": "retired"}])

    def test_a_dry_run_lists_the_renumbering_and_writes_nothing(self):
        proc = self.detect(renumbered({102: 202}), FOUND, "--dry-run")
        self.assertIn("new id", proc.stdout)
        self.assertFalse((self.study / "history/versions/brand-002.json").exists())

    def test_a_recorded_renumbering_is_not_found_again(self):
        self.detect(renumbered({102: 202}), FOUND)
        proc = self.detect(renumbered({102: 202}), "2026-12-01T12:00:00Z")
        self.assertIn("unchanged", proc.stdout)


class RenumberedComparisonTest(StudyCase, unittest.TestCase):
    """October reported; on 1 November Sentl renumbers the Salute dimension and its questions."""

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101))
        self.publish("2026-10-31")

    def test_a_renumbered_question_and_dimension_keep_their_comparison(self):
        self.detect(renumbered({101: 201, 102: 202}, {11: 21}), EDITED)
        for n, start in enumerate(NOV):
            self.ingest(run(run_id=9201 + n, started=start), name=f"run-{9201 + n}.json")
        self.build("2026-11-30")
        c = self.period_file("2026-11-30")["comparison"]
        salute = c["dimensions"]["brand"]["salute"]
        self.assertEqual((salute["status"], salute["compared_questions"]), ("compared", ["salute-1", "salute-2"]))
        self.assertEqual(salute["questions"]["salute-2"]["status"], "compared")
        self.assertEqual(c["design_changes"], [])


if __name__ == "__main__":
    unittest.main()
