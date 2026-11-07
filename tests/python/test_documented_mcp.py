"""Sentl read as its MCP documents it: the nine statuses, `round` and the ids on each answer, a paged
listing with `total`, `expected` and `judged`, and the errors of the read tools."""

import json
import random
import re
import unittest

from fixtures import StudyCase, listing, run
from test_detect import ADOPTED

OPEN = ("queued", "pending", "researching", "running", "judging")
ENDED = ("failed", "stalled")
STARTED = "2026-10-20T06:00:00Z"


def fetched(proc):
    m = re.search(r"^Fetch: (.*)$", proc.stdout, re.M)
    return [int(x) for x in m.group(1).split()] if m and m.group(1) != "none" else []


def line(proc, start):
    return next((ln for ln in proc.stdout.splitlines() if ln.startswith(start)), "")


def paged(rows, total, next_page=None, counts=None):
    """A list-runs-tool page: `counts` maps a run id to (expected, received, judged)."""
    data = listing(rows)
    data.update(total=total, next_page=next_page)
    for r in data["runs"]:
        r["expected"], r["received"], r["judged"] = (counts or {}).get(r["id"], (15, 15, 15))
    return data


def numbered(data, ids=None):
    """A results response as Sentl writes it: each answer with its round and ids."""
    per_pair = {}
    for r in data["run"]["responses"]:
        pair = (r["question"], r["model_id"])
        per_pair[pair] = per_pair.get(pair, 0) + 1
        r["round"] = per_pair[pair]
        r["question_id"], r["dimension_id"] = (ids or {}).get(r["question"], (None, None))
    return data


class Case(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)
        self.answer_operator()

    def runs(self, data, date="2026-10-31", check=0):
        return self.cli("runs", "--study", self.study, "--project", "brand",
                        "--saved", self.save("runs.json", data), "--date", date, check=check)


class StatusesTest(Case):

    def test_the_five_open_statuses_are_followed_and_none_is_reported_as_never_seen(self):
        rows = [(9100 + n, status, STARTED) for n, status in enumerate(OPEN)]
        proc = self.runs(listing(rows))
        self.assertEqual(fetched(proc), [])
        for status in OPEN:
            self.assertIn(status, line(proc, "Not final yet"))
        self.assertEqual(line(proc, "Status never seen"), "")

    def test_a_failed_or_stalled_run_is_final_with_no_results_and_is_listed_with_its_status(self):
        data = listing([(9101, "failed", STARTED), (9102, "stalled", STARTED), (9103, "completed", STARTED)])
        data["runs"][1]["error"] = "No queue worker processed this run before the queued timeout."
        proc = self.runs(data)
        self.assertEqual(fetched(proc), [9103])
        ended = line(proc, "Ended with no results")
        self.assertIn("run 9101 (failed", ended)
        self.assertIn("run 9102 (stalled", ended)
        self.assertIn("No queue worker", ended)
        self.assertEqual(line(proc, "Not final yet"), "")
        self.assertEqual(line(proc, "Status never seen"), "")

    def test_a_status_sentl_does_not_document_is_still_reported_as_never_seen(self):
        proc = self.runs(listing([(9101, "cancelled", STARTED)]))
        self.assertIn("cancelled", line(proc, "Status never seen"))

    def test_the_results_of_a_run_in_an_open_status_are_not_ingested_and_are_read_again(self):
        for status in ("researching", "judging"):
            with self.subTest(status):
                proc = self.ingest({"run": {"id": 9001, "status": status}}, check=3)
                self.assertIn(status, proc.stdout + proc.stderr)

    def test_the_results_of_a_failed_or_stalled_run_are_refused_as_having_nothing_to_read(self):
        for status in ENDED:
            with self.subTest(status):
                proc = self.ingest({"run": {"id": 9001, "status": status, "error": "the queue timed out"}}, check=2)
                said = proc.stdout + proc.stderr
                self.assertIn(status, said)
                self.assertIn("no results", said)
                self.assertIn("the queue timed out", said)
                self.assertNotIn("next invocation", said)
        self.assertFalse((self.study / "history" / "runs" / "brand" / "9001.json.gz").exists())

    def test_an_unattended_report_says_how_many_runs_ended_with_no_results(self):
        self.save("runs-501.json", listing([(9101, "stalled", "2026-10-28T06:00:00Z")]))
        proc = self.cli("pending", "--study", self.study, "--date", "2026-10-31", check=0)
        self.assertIn("nothing_new", proc.stdout)
        self.assertIn("1 ended with no results", proc.stdout)


class IngestIdsTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt()
        version = json.loads((self.study / "history" / "versions" / "brand-001.json").read_text(encoding="utf-8"))
        self.ids = {q["text"].replace("’", "'"): (q["id"], d["id"]) for d in version["dimensions"] for q in d["questions"]}

    def snapshot(self, data):
        self.ingest(data)
        got = self.read_run("brand", data["run"]["id"])
        got.pop("ingested_at")
        return got

    def test_three_rounds_in_any_order_give_the_same_run_snapshot(self):
        data = numbered(run(run_id=9002, rounds=3), self.ids)
        ordered = self.snapshot(data)
        shuffled = json.loads(json.dumps(data))
        shuffled["run"]["id"] = 9003
        random.Random(7).shuffle(shuffled["run"]["responses"])
        again = self.snapshot(shuffled)
        again["run_id"] = ordered["run_id"]
        self.assertEqual(again, ordered)
        self.assertEqual(ordered["plan"]["rounds"], 3)
        self.assertEqual({r["round"] for r in ordered["responses"]}, {1, 2, 3})

    def test_the_rounds_come_from_the_round_field_when_an_answer_is_missing(self):
        data = numbered(run(run_id=9002, rounds=3), self.ids)
        kept = [r for r in data["run"]["responses"] if r["round"] != 2]
        data["run"]["responses"] = kept
        self.assertEqual(self.snapshot(data)["plan"]["rounds"], 3)

    def test_a_question_of_a_renamed_dimension_is_matched_by_the_dimension_id_and_its_text(self):
        data = numbered(run(run_id=9002), self.ids)
        first = data["run"]["responses"][0]
        same = next(r for r in self.snapshot(run(run_id=9003))["responses"] if r["response_id"] == 900301)
        first["dimension"] = "Nome nuovo della dimensione"
        first["question_id"] = None
        got = self.snapshot(data)["responses"][0]
        self.assertEqual(got["match"], "dimension")
        self.assertEqual(got["question"], same["question"])

    def test_an_answer_with_null_ids_and_a_text_no_version_holds_is_unmatched_for_a_deleted_question(self):
        data = numbered(run(run_id=9002), self.ids)
        first = data["run"]["responses"][0]
        first.update(question="Una domanda cancellata da Sentl", question_id=None, dimension_id=None)
        proc = self.ingest(data)
        self.assertIn("1 unmatched", proc.stdout)
        self.assertIn("Una domanda cancellata da Sentl", proc.stdout)
        self.assertIn("deleted in Sentl", proc.stdout)

    def test_an_answer_with_null_ids_whose_text_the_version_holds_keeps_its_question(self):
        data = numbered(run(run_id=9002), self.ids)
        first = data["run"]["responses"][0]
        first.update(question_id=None, dimension_id=None)
        self.assertNotEqual(self.snapshot(data)["responses"][0]["match"], "unmatched")

    def test_a_run_without_ids_gives_the_run_snapshot_it_always_gave(self):
        got = self.snapshot(run(run_id=9002))
        self.assertNotIn("round", got["responses"][0])
        self.assertEqual(got["responses"][0]["match"], "exact")


class ListingArgumentsTest(Case):

    def args(self, date="2026-10-31"):
        return self.cli("runs", "--study", self.study, "--project", "brand", "--date", date, check=0)

    def test_a_first_report_prints_the_tool_arguments_of_its_window(self):
        proc = self.args()
        self.assertIn("list-runs-tool arguments", proc.stdout)
        self.assertIn('"project_id": 501', proc.stdout)
        self.assertIn('"started_after": "2026-06-01T00:00:00Z"', proc.stdout)
        self.assertNotIn("status", proc.stdout)

    def test_a_listing_is_needed_only_to_read_it_and_adopt_still_asks_for_one(self):
        proc = self.cli("runs", "--study", self.study, check=2)
        self.assertIn("--saved", proc.stderr)

    def test_a_run_recorded_as_unavailable_reads_the_whole_listing(self):
        self.cli("ingest", "--study", self.study, "--project", "brand", "--unavailable", 8000, "--reason", "server error",
                 check=0)
        proc = self.args()
        self.assertNotIn("started_after", proc.stdout)
        self.assertIn("unavailable", proc.stdout)


class PagedListingTest(Case):

    ROWS = [(9103, "completed", "2026-10-26T06:00:00Z"), (9102, "completed", "2026-10-19T06:00:00Z"),
            (9101, "completed", "2026-10-12T06:00:00Z")]

    def test_a_complete_listing_with_total_needs_no_warning_on_its_oldest_run(self):
        proc = self.runs(paged(self.ROWS, total=3))
        self.assertEqual(fetched(proc), [9101, 9102, 9103])
        self.assertEqual(line(proc, "Warning"), "")

    def test_a_listing_whose_total_exceeds_the_runs_read_is_refused_naming_the_missing_page(self):
        proc = self.runs(paged(self.ROWS[:2], total=3, next_page=2), check=2)
        self.assertIn("2 of the 3", proc.stderr)
        self.assertIn("page 2", proc.stderr)

    def test_the_pages_of_a_listing_are_read_together(self):
        first = self.save("runs-p1.json", paged(self.ROWS[:2], total=3, next_page=2))
        second = self.save("runs-p2.json", paged(self.ROWS[2:], total=3))
        proc = self.cli("runs", "--study", self.study, "--project", "brand", "--saved", first, second,
                        "--date", "2026-10-31", check=0)
        self.assertEqual(fetched(proc), [9101, 9102, 9103])

    def test_an_unattended_report_reads_the_pages_saved_beside_the_listing(self):
        self.save("runs-501.json", paged(self.ROWS[:2], total=3, next_page=2))
        self.save("runs-501.p2.json", paged(self.ROWS[2:], total=3))
        proc = self.cli("pending", "--study", self.study, "--date", "2026-10-31", check=0)
        self.assertIn("3 runs to fetch", proc.stdout)


class FloorInTheListingTest(Case):

    ROWS = [(9102, "completed", "2026-10-19T06:00:00Z"), (9101, "completed_with_warnings", "2026-10-12T06:00:00Z")]

    def test_a_run_under_the_floor_in_the_listing_is_left_out_before_its_results_are_read(self):
        proc = self.runs(paged(self.ROWS, total=2, counts={9101: (15, 15, 12)}))
        self.assertEqual(fetched(proc), [9102])
        under = line(proc, "Under the 90% floor")
        self.assertIn("run 9101", under)
        self.assertIn("12 of 15", under)

    def test_a_run_at_the_floor_is_read(self):
        proc = self.runs(paged(self.ROWS, total=2, counts={9101: (10, 10, 9)}))
        self.assertEqual(fetched(proc), [9101, 9102])

    def test_a_run_whose_listing_lacks_the_counts_is_decided_from_its_results(self):
        data = paged(self.ROWS, total=2, counts={9101: (None, 15, 12)})
        del data["runs"][1 - 1]["judged"]
        self.assertEqual(fetched(self.runs(data)), [9101, 9102])


class ErrorInASavedResponseTest(Case):

    ERROR = {"error": {"code": "not_found", "message": "Run 9001 not found."}}

    def test_a_saved_error_is_refused_naming_its_code_and_message(self):
        for args in (("ingest", "--study", self.study, "--project", "brand", "--results", self.save("run.json", self.ERROR)),
                     ("runs", "--saved", self.save("runs.json", self.ERROR))):
            with self.subTest(args[0]):
                proc = self.cli(*args, check=2)
                self.assertIn("not_found", proc.stderr)
                self.assertIn("Run 9001 not found.", proc.stderr)
                self.assertNotIn("shape", proc.stderr)

    def test_each_code_says_what_to_do(self):
        for code, told in (("internal", "once more"), ("not_found", "check the id"), ("invalid_argument", "needs an update")):
            with self.subTest(code):
                saved = self.save("run.json", {"error": {"code": code, "message": "m"}})
                proc = self.cli("runs", "--saved", saved, check=2)
                self.assertIn(told, proc.stderr)

    def test_a_run_whose_own_error_field_is_a_text_is_not_an_error_response(self):
        data = run(run_id=9002)
        data["run"]["error"] = "One model did not answer."
        self.assertEqual(self.ingest(data).returncode, 0)


class LiveShapeTest(Case):

    def test_a_listing_as_sentl_writes_it_today_passes_the_schema(self):
        data = paged([(9102, "stalled", "2026-10-19T06:00:00Z")], total=1, counts={9102: (15, 0, 0)})
        data.update(schema_version=1, content_sha256="0" * 64)
        data["runs"][0]["dimension_scores"] = []
        proc = self.runs(data)
        self.assertEqual(fetched(proc), [])
        self.assertEqual(line(proc, "Under the 90% floor"), "")


if __name__ == "__main__":
    unittest.main()
