"""`monitor.py pack` and `unpack`: a study carried between web conversations as one zip
(DEVPLAN R3b)."""

import copy
import hashlib
import json
import os
import shutil
import sys
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock

from fixtures import (AVORIA, GEM, GPT, OPERATOR, PRICE_Q, PRICE_TERMS, StudyCase, market_project, project, results,
                      run, weekly)
from test_detect import ADOPTED, NEW_TEXT, edited
from test_doctor import skill_md_version
from test_halves import OLD_PRICE_LOW, day, rows_of
from test_history import CHEAPER, OCT, runs
from test_rebuild import ADOPTED as REBUILD_ADOPTED, TEN_WEEKS
from test_shared_keys import pack as confezione_answers
from test_three_reports import CHEAPER_PRICE, december_runs, first_two_reports, third_report

PACK_MODULE = sys.modules["sentlmon.pack"]
DOCTOR = sys.modules["sentlmon.doctor"]
MB = 1024 * 1024

OCT_RUNS = [f"history/runs/brand/{i}.json.gz" for i in range(9101, 9105)]
NOV_RUNS = [f"history/runs/brand/{i}.json.gz" for i in range(9201, 9206)]
DEC_FIRST = "history/runs/brand/9301.json.gz"
OCT_HALVES = ["history/periods/2026-10-31.first.json", "history/periods/2026-10-31.second.json"]
PERIODS = ["history/periods/2026-10-31.json", "history/periods/2026-11-30.json"]


def snapshot(folder):
    """{path: bytes, "dir" or "link -> target"} of everything under `folder`, links not followed;
    None when it does not exist."""
    folder = Path(folder)
    if not folder.exists() and not folder.is_symlink():
        return None
    out = {}
    for top, dirs, files in os.walk(folder):
        for name in dirs + files:
            path = Path(top) / name
            rel = path.relative_to(folder).as_posix()
            if path.is_symlink():
                out[rel] = "link -> " + os.readlink(path)
            elif path.is_dir():
                out[rel] = "dir"
            else:
                out[rel] = path.read_bytes()
    return out


def entries(path):
    """The zip's file names, directories left out."""
    with zipfile.ZipFile(path) as zf:
        return sorted(n for n in zf.namelist() if not n.endswith("/"))


def manifest(path):
    with zipfile.ZipFile(path) as zf:
        return json.loads(zf.read("manifest.json"))


def rewrite(src, dst, change):
    """Copy the zip `src` to `dst` after `change` edits its list of (ZipInfo, bytes)."""
    with zipfile.ZipFile(src) as zf:
        items = [(info, zf.read(info)) for info in zf.infolist()]
    with zipfile.ZipFile(dst, "w") as zf:
        for info, data in change(items):
            zf.writestr(info, data)
    return dst


def edit_manifest(items, edit):
    out = []
    for info, data in items:
        if info.filename == "manifest.json":
            data = json.loads(data)
            edit(data)
            data = json.dumps(data).encode("utf-8")
        out.append((info, data))
    return out


def add_entry(items, name, data, kind=0o100644):
    """`items` with one more entry, listed in the manifest with its true size and sha256, so
    the only thing wrong with it is its name or its kind."""
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.external_attr = kind << 16
    files = lambda m: m["files"].append({"path": name, "size": len(data),  # noqa: E731
                                         "sha256": hashlib.sha256(data).hexdigest()})
    return edit_manifest(items, files) + [(info, data)]


class PackCase(StudyCase):

    def setUp(self):
        super().setUp()
        self.tmp = Path(self._tmp.name)

    def pack(self, *extra, study=None, check=0):
        return self.cli("pack", "--study", study or self.study, *extra, check=check)

    def unpack(self, pack, target, check=0):
        return self.cli("unpack", "--study", target, pack, check=check)


class ThirdReportFromPackTest(PackCase, unittest.TestCase):
    """Done when: a study packed after its second report and unpacked into an empty folder
    produces the same third report as the original folder."""

    def test_the_third_period_built_after_pack_and_unpack_equals_the_one_built_in_the_whole_folder(self):
        # `method` reads whether search demand was collected.
        (self.study / "search-demand.json").write_text('{"schema": "sentl-monitor/search-demand@1"}\n',
                                                       encoding="utf-8")
        first_two_reports(self)
        carried = self.tmp / "carried.zip"
        self.pack("--out", carried)
        self.assertIn("search-demand.json", entries(carried))
        restored = self.tmp / "restored"
        self.unpack(carried, restored)
        # The pack is slim: October's runs and halves stayed behind.
        for rel in OCT_RUNS + OCT_HALVES:
            self.assertTrue((self.study / rel).exists(), rel)
            self.assertFalse((restored / rel).exists(), rel)

        third_report(self)
        whole = self.study
        self.study = restored
        (restored / "inbox").mkdir()
        third_report(self)
        for rel in ("history/periods/2026-12-31.json", "history/material/2026-12-31.md", "reports/2026-12-31.md"):
            self.assertEqual((restored / rel).read_bytes(), (whole / rel).read_bytes(), rel)


class PackContentsTest(PackCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        first_two_reports(self)
        # A December run ingested after the November report travels with the pack, and so does a run
        # Sentl could not return, to be requested again.
        self.ingest(december_runs()[0], name="run-9301.json")
        self.cli("ingest", "--study", self.study, "--project", "brand", "--unavailable", 9399, check=0)

    def state(self):
        """The files every pack holds: the design, the binding, the versions and the indexes."""
        names = ["study.json", "sentl.json", "history/reports.json", "history/unavailable.json"]
        names += [f"history/versions/{p.name}" for p in (self.study / "history/versions").glob("*.json")]
        return names

    def test_the_runs_to_request_again_travel_with_the_pack(self):
        out = self.tmp / "slim.zip"
        self.pack("--out", out)
        self.assertIn("history/unavailable.json", entries(out))
        restored = self.tmp / "restored"
        self.unpack(out, restored)
        self.assertEqual([e["run_id"] for e in json.loads((restored / "history/unavailable.json").read_text())["runs"]],
                         [9399])

    def test_a_run_the_latest_period_file_lists_after_its_report_is_held(self):
        # Sentl returned a November run late; the November period is built again and lists it, while
        # reports.json keeps the runs the report was checked on.
        late = run(run_id=9250, started="2026-11-20T06:00:00Z", overrides=CHEAPER_PRICE, texts={"salute-2": NEW_TEXT})
        self.ingest(late, name="run-9250.json")
        self.build("2026-11-30")
        self.assertIn(9250, self.period_file("2026-11-30")["runs"]["brand"])
        out = self.tmp / "slim.zip"
        self.pack("--out", out)
        self.assertIn("history/runs/brand/9250.json.gz", entries(out))

    def test_the_slim_pack_holds_the_state_the_latest_periods_and_the_runs_from_the_latest_report_on(self):
        out = self.tmp / "slim.zip"
        self.pack("--out", out)
        self.assertEqual(entries(out), sorted(["manifest.json", *self.state(), *PERIODS, *NOV_RUNS, DEC_FIRST]))

    def test_the_manifest_names_the_schema_the_version_the_projects_the_last_report_and_each_file(self):
        out = self.tmp / "slim.zip"
        self.pack("--out", out)
        m = manifest(out)
        self.assertEqual(m["schema"], "sentl-monitor/pack@1")
        self.assertEqual(m["skill_version"], skill_md_version())
        self.assertEqual(m["projects"], [{"key": "brand", "project_id": 501}])
        self.assertEqual(m["last_report"], "2026-11-30")
        self.assertFalse(m["full"])
        self.assertEqual(sorted(f["path"] for f in m["files"]), [n for n in entries(out) if n != "manifest.json"])
        for f in m["files"]:
            data = (self.study / f["path"]).read_bytes()
            self.assertEqual((f["size"], f["sha256"]), (len(data), hashlib.sha256(data).hexdigest()), f["path"])

    def test_full_holds_every_run_and_every_period(self):
        out = self.tmp / "full.zip"
        self.pack("--full", "--out", out)
        runs_held = sorted(p.relative_to(self.study).as_posix() for p in (self.study / "history/runs").rglob("*.json.gz"))
        periods = sorted(p.relative_to(self.study).as_posix() for p in (self.study / "history/periods").glob("*.json"))
        self.assertEqual(entries(out), sorted(["manifest.json", *self.state(), *periods, *runs_held]))
        self.assertTrue(set(OCT_RUNS + OCT_HALVES) <= set(entries(out)))
        self.assertTrue(manifest(out)["full"])

    def test_inbox_material_and_reports_are_never_packed(self):
        out = self.tmp / "full.zip"
        self.pack("--full", "--out", out)
        self.assertFalse([n for n in entries(out) if n.startswith(("inbox/", "history/material/", "reports/"))])

    def test_two_packs_of_one_folder_are_identical_with_sorted_dated_entries(self):
        first, second = self.tmp / "a.zip", self.tmp / "b.zip"
        self.pack("--out", first)
        self.pack("--out", second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with zipfile.ZipFile(first) as zf:
            infos = zf.infolist()
        self.assertEqual([i.filename for i in infos], sorted(i.filename for i in infos))
        for info in infos:
            self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0), info.filename)
            mode = info.external_attr >> 16
            self.assertEqual(mode, 0o040755 if info.filename.endswith("/") else 0o100644, info.filename)

    def test_the_default_name_holds_the_folder_and_the_last_report_date_next_to_the_study(self):
        proc = self.pack()
        target = self.study.parent / "study-2026-11-30.sentl-pack.zip"
        self.assertTrue(target.is_file(), proc.stdout)
        self.assertIn(target.name, proc.stdout)

    def test_out_naming_a_folder_puts_the_default_name_in_it(self):
        folder = self.tmp / "downloads"
        folder.mkdir()
        self.pack("--out", folder)
        self.assertTrue((folder / "study-2026-11-30.sentl-pack.zip").is_file())

    def test_unpack_writes_every_file_as_it_was_and_says_what_the_next_report_covers(self):
        out = self.tmp / "slim.zip"
        self.pack("--out", out)
        restored = self.tmp / "restored"
        proc = self.unpack(out, restored)
        for name in entries(out):
            if name != "manifest.json":
                self.assertEqual((restored / name).read_bytes(), (self.study / name).read_bytes(), name)
        self.assertFalse((restored / "manifest.json").exists())
        self.assertIn("2026-11-30", proc.stdout)
        self.assertIn("6 runs", proc.stdout)
        self.assertIn("started after the last run of the report of 2026-11-30", proc.stdout)


class PackBeforeFirstReportTest(PackCase, unittest.TestCase):

    def test_before_a_first_final_report_the_pack_holds_every_run(self):
        self.adopt()
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101))
        self.build("2026-10-31")  # a period built, its report not checked yet
        out = self.tmp / "early.zip"
        proc = self.pack("--out", out)
        held = entries(out)
        self.assertTrue(set(OCT_RUNS) <= set(held), held)
        self.assertFalse([n for n in held if n.startswith("history/periods/")])
        self.assertIsNone(manifest(out)["last_report"])
        default = self.pack()
        self.assertTrue((self.study.parent / "study.sentl-pack.zip").is_file(), default.stdout + proc.stdout)


class PackLeftOutRunTest(PackCase, unittest.TestCase):

    def test_a_run_the_latest_period_left_out_under_the_floor_is_held_and_its_period_rebuilt_the_same(self):
        self.adopt()
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101))
        # 5 of 6 answers judged: left out of October, and started before its last run.
        thin = run(run_id=9150, started="2026-10-06T06:00:00Z",
                   overrides={("salute-1", GPT): ("Non saprei.", None, "neutral", [])})
        self.ingest(thin, name="run-9150.json")
        self.publish("2026-10-31")
        self.assertEqual(self.period_file("2026-10-31")["excluded"]["brand"][0]["run_id"], 9150)
        out = self.tmp / "slim.zip"
        self.pack("--out", out)
        self.assertIn("history/runs/brand/9150.json.gz", entries(out))

        restored = self.tmp / "restored"
        self.unpack(out, restored)
        whole = self.period_file("2026-10-31")
        self.study = restored
        (restored / "inbox").mkdir()
        self.build("2026-10-31")
        self.assertEqual(self.period_file("2026-10-31"), whole)


class LatestFourPeriodsTest(PackCase, unittest.TestCase):
    """Five monthly reports and a rebuilt period: the pack keeps the four latest periods the next
    report compares with."""

    def test_the_slim_pack_keeps_the_four_latest_periods_and_no_other(self):
        self.study.joinpath("study.json").write_text(json.dumps(
            {"schema": "sentl-monitor/study@1", "projects": [{"key": "brand"}]}), encoding="utf-8")
        self.study.joinpath("sentl.json").write_text(json.dumps(
            {"schema": "sentl-monitor/binding@1", "projects": {"brand": {"project_id": 501}}}), encoding="utf-8")
        dates = ["2026-05-31", "2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30"]
        periods = self.study / "history" / "periods"
        periods.mkdir(parents=True)
        reports = []
        for n, date in enumerate(dates):
            reports.append({"date": date, "file": f"reports/{date}.md", "status": "final",
                            "period": {"from": f"{date[:8]}01T00:00:00Z", "to": f"{date}T06:00:00Z"},
                            "runs": {"brand": [100 + n]}, "previous": None})
            (periods / f"{date}.json").write_text(json.dumps({"date": date}), encoding="utf-8")
        (periods / "2026-04-30.json").write_text(json.dumps({"date": "2026-04-30", "rebuilt": True}), encoding="utf-8")
        (periods / "2026-10-15.json").write_text(json.dumps({"date": "2026-10-15"}), encoding="utf-8")  # no report
        self.study.joinpath("history", "reports.json").write_text(json.dumps(reports), encoding="utf-8")
        out = self.tmp / "slim.zip"
        self.pack("--out", out)
        self.assertEqual([n for n in entries(out) if n.startswith("history/periods/")],
                         [f"history/periods/{d}.json" for d in dates[1:]])


class UnpackRefusesTest(PackCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt()
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101))
        self.publish("2026-10-31")
        self.good = self.tmp / "good.zip"
        self.pack("--out", self.good)
        self.target = self.tmp / "target"

    def refused(self, pack, code=2, target=None):
        """The unpack's stderr, after checking it ended with `code` and left the target, its
        parent and every other file under the temporary folder as they were."""
        target = target or self.target
        before = snapshot(self.tmp)
        proc = self.unpack(pack, target, check=code)
        self.assertEqual(snapshot(self.tmp), before, "a refused unpack writes nothing")
        return proc.stderr

    def bound_target(self):
        """An existing target bound to the pack's own project, so only the case under test refuses."""
        self.target.mkdir()
        shutil.copy(self.study / "sentl.json", self.target / "sentl.json")
        return self.target

    def tampered(self, change):
        return rewrite(self.good, self.tmp / "bad.zip", change)

    def test_the_good_pack_unpacks(self):
        self.unpack(self.good, self.target)
        self.assertTrue((self.target / "study.json").is_file())

    def test_a_file_whose_sha256_differs_from_the_manifest(self):
        def change(items):
            return [(i, d.replace(b"Avenello", b"Avenelle", 1) if i.filename == "study.json" else d) for i, d in items]
        self.assertIn("study.json", self.refused(self.tampered(change)))

    def test_an_absolute_path(self):
        self.assertIn("/abs/evil.json", self.refused(self.tampered(lambda items: add_entry(items, "/abs/evil.json", b"{}"))))

    def test_a_path_with_dot_dot(self):
        name = "history/../../evil.json"
        self.assertIn(name, self.refused(self.tampered(lambda items: add_entry(items, name, b"{}"))))

    def test_a_link(self):
        name = "history/versions/brand-009.json"
        stderr = self.refused(self.tampered(lambda items: add_entry(items, name, b"/etc/passwd", kind=0o120777)))
        self.assertIn(name, stderr)
        self.assertIn("link", stderr)

    def test_a_path_a_pack_never_holds(self):
        name = "scripts/monitor.py"
        self.assertIn(name, self.refused(self.tampered(lambda items: add_entry(items, name, b"print()"))))

    def test_a_file_the_manifest_does_not_list(self):
        def change(items):
            info = zipfile.ZipInfo("history/periods/2026-09-30.json", date_time=(1980, 1, 1, 0, 0, 0))
            return items + [(info, b"{}")]
        self.assertIn("2026-09-30", self.refused(self.tampered(change)))

    def test_a_listed_file_missing_from_the_zip(self):
        def change(items):
            return [(i, d) for i, d in items if i.filename != "sentl.json"]
        self.assertIn("sentl.json", self.refused(self.tampered(change)))

    def test_an_unknown_manifest_schema_is_exit_5(self):
        def change(items):
            return edit_manifest(items, lambda m: m.update(schema="sentl-monitor/pack@9"))
        self.assertIn("sentl-monitor/pack@9", self.refused(self.tampered(change), code=5))

    def test_a_zip_without_a_manifest(self):
        def change(items):
            return [(i, d) for i, d in items if i.filename != "manifest.json"]
        self.assertIn("manifest", self.refused(self.tampered(change)))

    def test_a_file_that_is_not_a_zip(self):
        bad = self.tmp / "not.zip"
        bad.write_text("not a zip", encoding="utf-8")
        self.assertIn("not.zip", self.refused(bad))

    def test_a_pack_older_than_the_folders_last_final_report(self):
        newer = self.tmp / "newer"
        shutil.copytree(self.study, newer)
        self.study = newer
        self.ingest_all(runs(["2026-11-02T06:00:00Z", "2026-11-09T06:00:00Z"], 9201))
        self.publish("2026-11-30")
        stderr = self.refused(self.good, target=newer)
        self.assertIn("2026-10-31", stderr)
        self.assertIn("2026-11-30", stderr)

    def test_a_folder_bound_to_other_projects(self):
        self.target.mkdir()
        self.target.joinpath("sentl.json").write_text(json.dumps(
            {"schema": "sentl-monitor/binding@1", "projects": {"brand": {"project_id": 777}}}), encoding="utf-8")
        stderr = self.refused(self.good)
        self.assertIn("777", stderr)
        self.assertIn("501", stderr)

    def test_the_same_pack_unpacks_again_over_its_own_folder(self):
        self.unpack(self.good, self.target)
        self.unpack(self.good, self.target)

    def test_unpack_over_the_study_it_came_from(self):
        self.unpack(self.good, self.study)

    def test_an_empty_folder_takes_the_pack(self):
        self.target.mkdir()
        self.unpack(self.good, self.target)
        self.assertTrue((self.target / "sentl.json").is_file())

    def test_a_folder_that_is_not_empty_and_holds_no_sentl_json(self):
        self.target.mkdir()
        (self.target / "notes.txt").write_text("appunti", encoding="utf-8")
        self.assertIn("sentl.json", self.refused(self.good))

    # --- names in the zip -----------------------------------------------------

    def test_a_drive_letter(self):
        stderr = self.refused(self.tampered(lambda items: add_entry(items, "C:/evil.json", b"{}")))
        self.assertIn("C:/evil.json", stderr)
        self.assertIn("absolute path", stderr)

    def test_a_backslash(self):
        name = "history\\versions\\brand-009.json"
        stderr = self.refused(self.tampered(lambda items: add_entry(items, name, b"{}")))
        self.assertIn("backslash", stderr)

    def test_a_name_held_twice(self):
        def change(items):
            twin = next((zipfile.ZipInfo(i.filename, date_time=i.date_time), d) for i, d in items
                        if i.filename == "study.json")
            return items + [twin]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # zipfile warns of the duplicate it is asked to write
            bad = self.tampered(change)
        self.assertIn("twice", self.refused(bad))

    # --- sizes ----------------------------------------------------------------

    def resized(self, sizes):
        """The good pack with the manifest's declared sizes of the first files set to `sizes`."""
        def change(items):
            def edit(m):
                for entry, size in zip(m["files"], sizes):
                    entry["size"] = size
            return edit_manifest(items, edit)
        return self.tampered(change)

    def test_a_file_declared_over_50_mb(self):
        self.assertIn("50 MB", self.refused(self.resized([50 * MB + 1])))

    def test_files_declared_over_200_mb_in_all(self):
        self.assertIn("200 MB", self.refused(self.resized([45 * MB] * 5)))

    def test_a_file_whose_size_in_the_zip_differs_from_the_manifest(self):
        first = manifest(self.good)["files"][0]
        stderr = self.refused(self.resized([first["size"] + 1]))
        self.assertIn(first["path"], stderr)
        self.assertIn("size", stderr)

    # --- the target -----------------------------------------------------------

    def test_a_file_where_the_pack_needs_a_folder(self):
        target = self.bound_target()
        (target / "history").mkdir()
        (target / "history" / "runs").write_text("not a folder", encoding="utf-8")
        self.assertIn("history/runs", self.refused(self.good).replace(os.sep, "/"))

    def test_a_folder_where_the_pack_writes_a_file(self):
        target = self.bound_target()
        (target / "study.json").mkdir()
        self.assertIn("study.json", self.refused(self.good))

    def test_a_link_inside_the_target(self):
        target = self.bound_target()
        outside = self.tmp / "outside"
        outside.mkdir()
        (target / "history").symlink_to(outside, target_is_directory=True)
        stderr = self.refused(self.good)
        self.assertIn("link", stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_a_tmp_link_beside_a_file_redirects_no_write(self):
        target = self.bound_target()
        outside = self.tmp / "outside.txt"
        outside.write_text("keep", encoding="utf-8")
        (target / "study.json.tmp").symlink_to(outside)
        self.unpack(self.good, target)
        self.assertEqual(outside.read_text(encoding="utf-8"), "keep")
        self.assertEqual((target / "study.json").read_bytes(), (self.study / "study.json").read_bytes())

    # --- all or nothing ---------------------------------------------------------

    def failing_write(self, after):
        """`_write_new` failing on its call number `after` + 1, as on a full disk."""
        real, calls = PACK_MODULE._write_new, []

        def write(*args, **kwargs):
            calls.append(1)
            if len(calls) > after:
                raise OSError(28, "No space left on device")
            return real(*args, **kwargs)
        return mock.patch.object(PACK_MODULE, "_write_new", write)

    def test_a_write_that_fails_leaves_the_study_as_it_was_and_no_staging_folder(self):
        target = self.tmp / "target"
        shutil.copytree(self.study, target)
        # The folder moves on after the pack was written, so the unpack would change files.
        (target / "history" / "reports.json").write_text("[]\n", encoding="utf-8")
        with self.failing_write(3):
            self.refused(self.good, code=6, target=target)

    def test_a_write_that_fails_creates_no_target(self):
        with self.failing_write(3):
            self.refused(self.good, code=6)
        self.assertFalse(self.target.exists())

    # --- over an existing folder -------------------------------------------------

    def moved_on(self):
        """A copy of the study whose state moved on after the pack was written, so the unpack
        replaces its files, and whose period files are gone, so it creates a folder."""
        target = self.tmp / "target"
        shutil.copytree(self.study, target)
        (target / "history" / "reports.json").write_text("[]\n", encoding="utf-8")
        shutil.rmtree(target / "history" / "periods")
        return target

    def read_only(self, folder):
        if os.name != "posix" or os.geteuid() == 0:
            self.skipTest("folder permissions bind only a user other than root on POSIX")
        folder.chmod(0o555)
        # Cleanups run after tearDown has removed the temporary folder, which restores modes itself.
        self.addCleanup(lambda: folder.exists() and folder.chmod(0o755))

    def test_a_folder_the_unpack_cannot_write_is_refused_before_a_move(self):
        target = self.moved_on()
        self.read_only(target / "history" / "runs" / "brand")
        stderr = self.refused(self.good, target=target)
        self.assertIn("history/runs/brand", stderr.replace(os.sep, "/"))
        self.assertIn("written", stderr)

    def failing_move(self, after):
        """`_move` failing on its call number `after` + 1, as across file systems."""
        real, calls = PACK_MODULE._move, []

        def move(src, dst):
            calls.append(1)
            if len(calls) > after:
                raise OSError(18, "Invalid cross-device link")
            return real(src, dst)
        return mock.patch.object(PACK_MODULE, "_move", move), calls

    def test_a_move_that_fails_at_any_point_restores_the_folder(self):
        target = self.moved_on()
        for after in (0, 1, 6, 12, 18):
            with self.subTest(after=after):
                patch, calls = self.failing_move(after)
                with patch:
                    self.refused(self.good, code=6, target=target)
                self.assertGreater(len(calls), after)
        self.unpack(self.good, target)
        self.assertEqual((target / "history" / "reports.json").read_bytes(),
                         (self.study / "history" / "reports.json").read_bytes())

    def test_an_existing_target_under_a_read_only_parent_unpacks(self):
        parent = self.tmp / "locked"
        target = parent / "study"
        target.mkdir(parents=True)
        self.read_only(parent)
        self.unpack(self.good, target)
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["history", "sentl.json", "study.json"])

    def test_a_missing_target_under_a_read_only_parent_is_refused(self):
        parent = self.tmp / "locked"
        parent.mkdir()
        self.read_only(parent)
        self.assertIn("locked", self.refused(self.good, target=parent / "study"))

    # --- the halves -------------------------------------------------------------

    def test_the_halves_of_a_first_report_travel_with_it_and_its_charts_build_the_same(self):
        self.assertTrue(set(OCT_HALVES) <= set(entries(self.good)))
        self.unpack(self.good, self.target)
        for folder in (self.study, self.target):
            self.cli("charts", "--study", folder, "--date", "2026-10-31", check=0)
        rel = "reports/2026-10-31.charts.md"
        self.assertEqual((self.target / rel).read_bytes(), (self.study / rel).read_bytes())


class PackSizeCapsTest(PackCase, unittest.TestCase):
    """`pack` refuses what `unpack` would refuse: a file over 50 MB, more than 200 MB in all."""

    def setUp(self):
        super().setUp()
        self.adopt()
        self.answer_operator()

    def sparse(self, rel, size):
        path = self.study / rel
        with open(path, "wb") as fh:
            fh.truncate(size)

    def refused_pack(self):
        out = self.tmp / "big.zip"
        stderr = self.pack("--out", out, check=2).stderr
        self.assertFalse(out.exists())
        self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.endswith(".tmp")], [])
        return stderr

    def test_a_file_over_50_mb_is_refused_and_named(self):
        self.sparse("history/versions/brand-099.json", 50 * MB + 1)
        stderr = self.refused_pack()
        self.assertIn("50 MB", stderr)
        self.assertIn("brand-099.json", stderr)

    def test_more_than_200_mb_in_all_is_refused_naming_the_largest_files(self):
        for n in range(5):
            self.sparse(f"history/versions/brand-09{n}.json", (40 + n) * MB)
        stderr = self.refused_pack()
        self.assertIn("200 MB", stderr)
        self.assertIn("brand-094.json", stderr)


class RedoFromSlimPackTest(PackCase, unittest.TestCase):
    """A pack without --full serves the next report; building or checking its latest report again
    needs runs it does not hold, and is refused instead of failing or dropping periods."""

    def test_building_or_checking_the_latest_later_report_again_is_refused_and_works_from_a_full_pack(self):
        first_two_reports(self)
        whole = self.period_file("2026-11-30")
        slim, full = self.tmp / "slim.zip", self.tmp / "full.zip"
        self.pack("--out", slim)
        self.pack("--full", "--out", full)
        restored = self.tmp / "restored"
        self.unpack(slim, restored)
        self.study = restored
        (restored / "inbox").mkdir()
        self.assertIn("--full", self.build("2026-11-30", check=2).stderr)
        (restored / "reports").mkdir()
        shutil.copy(self.tmp / "study" / "reports" / "2026-11-30.md", restored / "reports" / "2026-11-30.md")
        self.assertIn("--full", self.cli("check", "--study", restored, restored / "reports" / "2026-11-30.md",
                                         check=2).stderr)

        again = self.tmp / "again"
        self.unpack(full, again)
        self.study = again
        (again / "inbox").mkdir()
        self.build("2026-11-30")
        self.assertEqual(self.period_file("2026-11-30"), whole)

    def test_building_a_first_report_with_rebuilt_periods_again_is_refused_and_keeps_them(self):
        self.adopt(at=REBUILD_ADOPTED)
        self.answer_operator(report_every="weekly")
        self.ingest_all(runs(TEN_WEEKS, 9101))
        self.publish("2026-10-16")
        slim = self.tmp / "slim.zip"
        self.pack("--out", slim)
        restored = self.tmp / "restored"
        self.unpack(slim, restored)
        self.study = restored
        (restored / "inbox").mkdir()
        periods = snapshot(restored / "history" / "periods")
        self.assertIn("--full", self.build("2026-10-16", check=2).stderr)
        self.assertEqual(snapshot(restored / "history" / "periods"), periods)


class CheckRemindsToPackTest(PackCase, unittest.TestCase):

    def publish_with_sandbox(self, roots):
        self.adopt()
        self.answer_operator()
        self.ingest_all(runs(OCT, 9101))
        with mock.patch.object(DOCTOR, "SANDBOX_ROOTS", roots):
            return self.publish("2026-10-31")

    def test_check_passing_in_a_sandbox_says_to_pack_and_offer_both_files(self):
        sandbox = self.tmp / "mnt-data"
        sandbox.mkdir()
        out = self.publish_with_sandbox((str(sandbox),)).stdout
        self.assertIn("monitor.py pack", out)
        self.assertIn("download", out)

    def test_check_passing_on_a_lasting_folder_says_nothing_of_the_pack(self):
        out = self.publish_with_sandbox((str(self.tmp / "no-such-sandbox"),)).stdout
        self.assertNotIn("monitor.py pack", out)


def brand(text=None):
    """The branded project with Confezione, archived when it was adopted, restored; `text` rewords
    salute-2."""
    p = edited(text=text) if text else project()
    p["project"]["dimensions"][2]["archived"] = False
    return p


def market_rows(n):
    """Day n's answers of the daily market project; Orbit Reason calls the price too high on days
    64-66 (10-12 December), an episode below the range of the November runs."""
    rows = rows_of(n)
    if 64 <= n <= 66:
        rows = [(PRICE_Q, GEM, *OLD_PRICE_LOW) if r[:2] == (PRICE_Q, GEM) else r for r in rows]
    return rows


HARMFUL = ("Il latte d'avena Avenello fa male a chi è intollerante all'avena.", 2, "negative",
           ["https://salute.example/intolleranze"])


class RichStudyFromPackTest(PackCase, unittest.TestCase):
    """Done when, on a fuller history: a weekly branded project and a daily market project; a
    dimension archived when adopted and restored; a run under the judged floor and a run Sentl could
    not return in the second period; a question reworded in Sentl; and a third period with an
    episode and verdict changes, built from the folder unpacked from a slim pack."""

    def setUp(self):
        super().setUp()
        self.adopt(at=ADOPTED)
        self.cli("adopt", "--study", self.study, "--project", self.save("market.json", market_project()),
                 "--run", self.save("market-run.json", results(9000, "2026-09-29T06:00:00Z", rows_of(1))),
                 "--key", "market", check=0, at=ADOPTED)
        self.detect(brand(), "2026-10-02T12:00:00Z")
        self.answer_operator(foils=[*copy.deepcopy(OPERATOR["foils"]), copy.deepcopy(AVORIA)])
        study = self.read("study.json")
        for theme in study["themes"]:
            theme["origins"] = [{"kind": "client_issue", "detail": "Domande al servizio clienti, 2026"}]
        market = next(p for p in study["projects"] if p["key"] == "market")
        market["dimensions"][0]["questions"][0]["facts"] = [
            {"fact": "Il prezzo al litro è 2,10 € dal 2026", "source": "https://avenello.example/prezzi",
             "date": "2026-09-01", **copy.deepcopy(PRICE_TERMS)}]
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")

        self.brand_runs(weekly("2026-10-08", 4), 9401)
        self.market_days(range(1, 25))
        self.publish("2026-10-31")

        # November: salute-2 reworded in Sentl after the second run, Orbit Reason now finds Avenello
        # cheaper, a run with an unjudged answer, and a market run Sentl could not return.
        self.detect(brand(text=NEW_TEXT), "2026-11-30T12:00:00Z")
        nov = weekly("2026-11-05", 4)
        self.brand_runs(nov[:2], 9411, overrides=CHEAPER_PRICE)
        self.brand_runs(nov[2:], 9413, overrides=CHEAPER_PRICE, texts={"salute-2": NEW_TEXT})
        thin = {**CHEAPER_PRICE, ("salute-1", GPT): ("Non saprei.", None, "neutral", [])}
        self.brand_runs(["2026-11-08T06:00:00Z"], 9415, overrides=thin)
        self.cli("ingest", "--study", self.study, "--project", "market", "--unavailable", 9599, check=0)
        self.market_days(range(25, 55))
        self.publish("2026-11-30")

    def brand_runs(self, starts, first_id, overrides=None, texts=None):
        for n, start in enumerate(starts):
            run_id = first_id + n
            self.ingest(run(run_id=run_id, started=start, overrides=overrides, texts=texts,
                            extra=confezione_answers((3, 4), run_id)), name=f"b-{run_id}.json")

    def market_days(self, days):
        for n in days:
            self.ingest_market(9500 + n, day(n), market_rows(n))

    def december(self):
        """The December runs ingested and the period built; then the report published. Returns the
        period's output."""
        self.brand_runs(weekly("2026-12-03", 4), 9421, overrides={**CHEAPER_PRICE, ("salute-1", GPT): HARMFUL},
                        texts={"salute-2": NEW_TEXT})
        self.market_days(range(55, 86))
        out = self.build("2026-12-31").stdout
        self.publish("2026-12-31")
        return out

    def test_the_next_report_from_the_unpacked_slim_pack_is_the_same(self):
        carried = self.tmp / "carried.zip"
        self.pack("--out", carried)
        held = entries(carried)
        self.assertNotIn("history/runs/market/9501.json.gz", held)
        self.assertNotIn("history/runs/brand/9401.json.gz", held)
        self.assertIn("history/runs/brand/9415.json.gz", held)
        restored = self.tmp / "restored"
        self.unpack(carried, restored)

        whole = self.study
        out = {}
        for folder in (whole, restored):
            self.study = folder
            (folder / "inbox").mkdir(exist_ok=True)
            out[folder] = self.december()
        self.assertEqual(out[restored], out[whole])
        self.assertIn("9599", out[whole])
        for rel in ("history/periods/2026-12-31.json", "history/material/2026-12-31.md", "reports/2026-12-31.md"):
            self.assertEqual((restored / rel).read_bytes(), (whole / rel).read_bytes(), rel)
        period = json.loads((whole / "history/periods/2026-12-31.json").read_text(encoding="utf-8"))
        self.assertTrue(period["comparison"]["verdict_changes"])
        self.assertIn('"episodes"', json.dumps(period["projects"]["market"]))
        self.assertIn("confezione", period["projects"]["brand"]["dimensions"])


if __name__ == "__main__":
    unittest.main()
