import copy
import gzip
import hashlib
import http.server
import json
import threading
import unittest
import urllib.error
from unittest import mock

from fixtures import GEM, GPT, StudyCase, project, run
from sentlmon import exportfile
from sentlmon.common import Refused

QUESTION_IDS = {"salute-1": 101, "salute-2": 102, "prezzo-1": 103}
DIMENSION_IDS = {"Salute": 11, "Prezzo": 12}


def with_ids(data):
    """The run as Sentl returns it now: each response carries question_id and dimension_id."""
    out = copy.deepcopy(data)
    for r in out["run"]["responses"]:
        key = next((k for k, (d, t) in __import__("fixtures").QUESTION_OF.items() if t == r["question"]), None)
        r["question_id"] = QUESTION_IDS.get(key)
        r["dimension_id"] = DIMENSION_IDS.get(r["dimension"])
    return out


def export_of(*runs, schema_version=1):
    return {"schema_version": schema_version, "generated_at": "2026-10-22T09:00:00Z",
            "project": project(), "runs": list(runs)}


def packed(data):
    return gzip.compress(json.dumps(data, ensure_ascii=False).encode("utf-8"), mtime=0)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def page_of(data, number, last, content, tamper=False):
    page = {"run": {**{k: v for k, v in data["run"].items() if k != "responses"}, "responses": content},
            "page": number, "next_page": None if last else number + 1}
    page["content_sha256"] = exportfile.content_sha256(page)
    if tamper:
        page["run"]["responses"][0]["answer"] += "!"
    return page


class CanonicalJsonTest(unittest.TestCase):
    def test_rfc_8785_sample(self):
        sample = json.loads('{"numbers": [333333333.33333329, 1E30, 4.50, 2e-3, 0.000000000000000000000000001],'
                            ' "string": "\\u20ac$\\u000F\\u000aA\'\\u0042\\u0022\\u005c\\\\\\"/",'
                            ' "literals": [null, true, false]}')
        self.assertEqual(exportfile.jcs(sample),
                         '{"literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],'
                         '"string":"€$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}')

    def test_a_whole_float_is_written_as_an_integer(self):
        self.assertEqual(exportfile.jcs({"score": 4.0, "n": 0.0, "big": 1e21, "small": 0.000001}),
                         '{"big":1e+21,"n":0,"score":4,"small":0.000001}')

    def test_keys_sort_by_utf16_code_units(self):
        self.assertEqual(exportfile.jcs({"\U0001F600": 1, "～": 2, "a": 3}),
                         '{"a":3,"\U0001F600":1,"～":2}')

    def test_content_sha256_ignores_the_field_itself(self):
        page = {"page": 1, "next_page": None}
        digest = exportfile.content_sha256(page)
        self.assertEqual(digest, hashlib.sha256(b'{"next_page":null,"page":1}').hexdigest())
        self.assertEqual(exportfile.content_sha256({**page, "content_sha256": digest}), digest)


class ImportTest(StudyCase, unittest.TestCase):
    def export_file(self, data=None, name="export.json.gz"):
        raw = packed(data or export_of(with_ids(run(9001)), with_ids(run(9002, started="2026-10-08T06:00:00Z"))))
        path = self.study / name
        path.write_bytes(raw)
        return path, sha(raw)

    def test_import_writes_the_inbox_files_the_other_commands_read(self):
        path, digest = self.export_file()
        proc = self.cli("import", "--study", self.study, "--sha256", digest, path, check=0)
        self.assertIn("2 runs", proc.stdout)
        inbox = self.study / "inbox"
        self.assertEqual(sorted(p.name for p in inbox.glob("*.json")),
                         ["project-501.json", "run-9001.json", "run-9002.json", "runs-501.json"])
        listing = self.read("inbox/runs-501.json")
        self.assertEqual(listing["project_id"], 501)
        self.assertEqual([(r["id"], r["status"], r["started_at"]) for r in listing["runs"]],
                         [(9001, "completed", "2026-10-01T06:00:00Z"), (9002, "completed", "2026-10-08T06:00:00Z")])

    def test_the_imported_files_adopt_and_ingest(self):
        path, _ = self.export_file()
        self.cli("import", "--study", self.study, path, check=0)
        inbox = self.study / "inbox"
        self.cli("adopt", "--study", self.study, "--project", inbox / "project-501.json",
                 "--run", inbox / "run-9001.json", "--key", "brand", check=0)
        self.cli("ingest", "--study", self.study, "--project", "brand", "--results", inbox / "run-9002.json", check=0)
        self.assertEqual(self.read_run("brand", 9002)["received"], 6)

    def test_a_changed_byte_is_refused_and_nothing_is_written(self):
        path, digest = self.export_file()
        raw = bytearray(path.read_bytes())
        raw[len(raw) // 2] ^= 1
        path.write_bytes(bytes(raw))
        proc = self.cli("import", "--study", self.study, "--sha256", digest, path, check=2)
        self.assertIn("sha256", proc.stderr)
        self.assertEqual(list((self.study / "inbox").glob("*.json")), [])

    def test_a_file_that_is_not_gzip_is_refused(self):
        path = self.study / "export.json.gz"
        path.write_bytes(b"{}")
        self.cli("import", "--study", self.study, path, check=2)

    def test_an_unknown_schema_version_is_refused_with_exit_5(self):
        path, _ = self.export_file(export_of(with_ids(run(9001)), schema_version=2))
        proc = self.cli("import", "--study", self.study, path, check=5)
        self.assertIn("schema_version", proc.stderr)
        self.assertEqual(list((self.study / "inbox").glob("*.json")), [])

    def test_a_run_not_final_is_imported_for_its_status_only(self):
        path, _ = self.export_file(export_of(with_ids(run(9001, status="running"))))
        self.cli("import", "--study", self.study, path, check=0)
        self.assertEqual(self.read("inbox/runs-501.json")["runs"][0]["status"], "running")

    def test_a_run_of_another_project_is_refused(self):
        other = with_ids(run(9001))
        other["run"]["project_id"] = 777
        path, _ = self.export_file(export_of(other))
        proc = self.cli("import", "--study", self.study, path, check=2)
        self.assertIn("9001", proc.stderr)


class Server:
    """A local HTTP server answering every GET with the same bytes."""

    def __init__(self, body, status=200):
        outer = self
        outer.hits = 0

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.hits += 1
                self.send_response(status)
                self.send_header("Content-Type", "application/gzip")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/export.json.gz"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class DownloadTest(StudyCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.raw = packed(export_of(with_ids(run(9001))))
        self.local = {"hosts": ("127.0.0.1",), "schemes": ("http",)}

    def serve(self, body, status=200):
        server = Server(body, status)
        self.addCleanup(server.close)
        return server

    def test_download_checks_the_digest_and_imports(self):
        server = self.serve(self.raw)
        text = exportfile.download(self.study, server.url, sha(self.raw), **self.local)
        self.assertIn("1 run", text)
        self.assertTrue((self.study / "inbox" / "run-9001.json").exists())

    def test_a_wrong_digest_is_refused_and_nothing_is_written(self):
        server = self.serve(self.raw)
        with self.assertRaisesRegex(Refused, "sha256"):
            exportfile.download(self.study, server.url, "0" * 64, **self.local)
        self.assertEqual(list((self.study / "inbox").glob("*")), [])

    def test_a_download_over_the_size_cap_is_refused(self):
        server = self.serve(self.raw)
        with self.assertRaisesRegex(Refused, "larger than"):
            exportfile.download(self.study, server.url, sha(self.raw), cap=len(self.raw) - 1, **self.local)
        self.assertEqual(list((self.study / "inbox").glob("*")), [])

    def test_an_expired_link_is_unreachable(self):
        server = self.serve(b"", status=410)
        with self.assertRaises(exportfile.Unreachable) as caught:
            exportfile.download(self.study, server.url, sha(self.raw), **self.local)
        self.assertIn("410", str(caught.exception))

    def test_no_credential_is_sent(self):
        seen = {}

        def opener(request, timeout):
            seen.update(request.header_items())
            raise urllib.error.URLError("stop here")

        with self.assertRaises(exportfile.Unreachable):
            exportfile.download(self.study, "https://app.sentl.ai/export/abc", sha(self.raw), opener=opener)
        self.assertEqual({k.lower() for k in seen} - {"user-agent", "accept", "host"}, set())

    def test_only_https_on_a_sentl_host_is_accepted(self):
        for url in ("http://app.sentl.ai/export/abc", "https://evil.example/export/abc",
                    "https://app.sentl.ai.evil.example/export/abc", "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaisesRegex(Refused, "not a Sentl download link"):
                exportfile.download(self.study, url, sha(self.raw))

    def test_the_command_exits_7_when_the_link_is_unreachable(self):
        with mock.patch.object(exportfile, "_open", side_effect=urllib.error.URLError("no route")):
            proc = self.cli("download", "--study", self.study, "--sha256", sha(self.raw),
                            "--url", "https://app.sentl.ai/export/abc", check=7)
        self.assertIn("export again", proc.stderr)

    def test_the_command_refuses_a_link_outside_sentl(self):
        self.cli("download", "--study", self.study, "--sha256", "0" * 64, "--url", "https://evil.example/x", check=2)


class PagesTest(StudyCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.adopt()
        self.data = with_ids(run(9001))
        rows = self.data["run"]["responses"]
        self.pages = [page_of(self.data, 1, False, rows[:2]), page_of(self.data, 2, False, rows[2:4]),
                      page_of(self.data, 3, True, rows[4:])]

    def pages_cli(self, pages, check=0):
        files = [self.save(f"page-{i}.json", p) for i, p in enumerate(pages, 1)]
        return self.cli("ingest", "--study", self.study, "--project", "brand", "--pages", *files, check=check)

    def test_pages_in_any_order_are_assembled_and_ingested(self):
        self.pages_cli([self.pages[2], self.pages[0], self.pages[1]])
        self.assertEqual(self.read_run("brand", 9001)["received"], 6)

    def test_the_assembled_run_equals_the_run_read_whole(self):
        self.pages_cli(self.pages)
        paged = self.read_run("brand", 9001)
        whole = self.cli("ingest", "--study", self.study, "--project", "brand",
                         "--results", self.save("whole.json", self.data))
        self.assertIn("already ingested", whole.stdout)
        self.assertEqual(paged["judged"], 6)

    def test_a_missing_page_is_refused_naming_it(self):
        proc = self.pages_cli([self.pages[0], self.pages[2]], check=2)
        self.assertIn("page 2", proc.stderr)
        self.assertFalse((self.study / "history" / "runs" / "brand" / "9001.json.gz").exists())

    def test_a_last_page_missing_is_refused_naming_the_page_that_follows(self):
        proc = self.pages_cli(self.pages[:2], check=2)
        self.assertIn("page 3", proc.stderr)

    def test_a_duplicate_response_is_refused_naming_the_page(self):
        pages = copy.deepcopy(self.pages)
        pages[1] = page_of(self.data, 2, False, [self.data["run"]["responses"][0], self.data["run"]["responses"][2]])
        proc = self.pages_cli(pages, check=2)
        self.assertIn("page 2", proc.stderr)
        self.assertIn(str(self.data["run"]["responses"][0]["id"]), proc.stderr)

    def test_a_different_run_header_is_refused_naming_the_page(self):
        other = copy.deepcopy(self.data)
        other["run"]["status"] = "failed"
        pages = [self.pages[0], page_of(other, 2, False, self.data["run"]["responses"][2:4]), self.pages[2]]
        proc = self.pages_cli(pages, check=2)
        self.assertIn("page 2", proc.stderr)
        self.assertIn("status", proc.stderr)

    def test_a_checksum_mismatch_is_refused_naming_the_page(self):
        pages = [self.pages[0], page_of(self.data, 2, False, self.data["run"]["responses"][2:4], tamper=True), self.pages[2]]
        proc = self.pages_cli(pages, check=2)
        self.assertIn("page 2", proc.stderr)
        self.assertIn("content_sha256", proc.stderr)


class QuestionIdTest(StudyCase, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.adopt()

    def test_a_response_with_question_id_matches_after_the_text_changes(self):
        data = with_ids(run(9001))
        first = data["run"]["responses"][0]
        first["question"] = first["question"].replace("fa male", "fa molto male")
        self.ingest(data)
        rows = self.read_run("brand", 9001)["responses"]
        [moved] = [r for r in rows if r["response_id"] == first["id"]]
        self.assertEqual((moved["question"], moved["match"]), ("salute-1", "id"))
        self.assertEqual(sum(1 for r in rows if r["match"] == "unmatched"), 0)

    def test_a_question_id_unknown_to_the_version_falls_back_to_the_text(self):
        data = with_ids(run(9001))
        data["run"]["responses"][0]["question_id"] = 9999
        self.ingest(data)
        [r] = [r for r in self.read_run("brand", 9001)["responses"] if r["response_id"] == data["run"]["responses"][0]["id"]]
        self.assertEqual((r["question"], r["match"]), ("salute-1", "exact"))

    def test_a_null_question_id_falls_back_to_the_text(self):
        data = with_ids(run(9001))
        for r in data["run"]["responses"]:
            r["question_id"] = None
        self.ingest(data)
        self.assertEqual(self.read_run("brand", 9001)["judged"], 6)


if __name__ == "__main__":
    unittest.main()
