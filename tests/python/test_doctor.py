"""`monitor.py doctor` and `--version`: what a host offers the scripts, and the skill's version."""

import os
import platform
import re
import sys
import tempfile
import unittest
from pathlib import Path

from fixtures import REPO, StudyCase, monitor

SKILL_MD = REPO / "skills" / "sentl-monitor" / "SKILL.md"


def skill_md_version():
    """The version SKILL.md declares, read without the code under test."""
    match = re.search(r'^metadata:\n(?:  .*\n)*?  version: "([^"]+)"$', SKILL_MD.read_text(encoding="utf-8"), re.M)
    return match.group(1)


class VersionTest(StudyCase, unittest.TestCase):

    def test_version_prints_the_version_skill_md_declares(self):
        proc = self.cli("--version", check=0)
        self.assertEqual(proc.stdout.strip(), skill_md_version())

    def test_doctor_names_the_version(self):
        proc = self.cli("doctor", check=0)
        self.assertIn(f"sentl-monitor {skill_md_version()}", proc.stdout)


class DoctorPythonTest(StudyCase, unittest.TestCase):

    def test_this_python_is_reported_with_its_version_and_the_minimum(self):
        proc = self.cli("doctor", check=0)
        here = ".".join(str(n) for n in sys.version_info[:3])
        self.assertRegex(proc.stdout, rf"Python {re.escape(here)}\b.*3\.10 or later")
        self.assertIn(platform.system(), proc.stdout)

    def test_an_older_python_is_a_problem(self):
        lines, ok = monitor.doctor.report(version_info=(3, 9, 18, "final", 0))
        self.assertFalse(ok)
        self.assertTrue(any("Python 3.9.18" in line and "needs 3.10 or later" in line for line in lines), lines)

    def test_the_guard_names_an_older_python_and_passes_a_supported_one(self):
        self.assertIn("3.9.18", monitor.doctor.python_problem((3, 9, 18, "final", 0)))
        self.assertIsNone(monitor.doctor.python_problem((3, 10, 0, "final", 0)))


class DoctorStudyFolderTest(StudyCase, unittest.TestCase):

    def test_a_writable_study_folder_is_reported_writable(self):
        proc = self.cli("doctor", "--study", self.study, check=0)
        self.assertRegex(proc.stdout, rf"Study folder {re.escape(str(self.study))}: writable")
        self.assertEqual(sorted(p.name for p in self.study.iterdir()), ["inbox"], "doctor leaves no file behind")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root writes to a read-only folder")
    def test_a_read_only_study_folder_is_a_problem(self):
        self.study.chmod(0o555)
        try:
            proc = self.cli("doctor", "--study", self.study, check=1)
        finally:
            self.study.chmod(0o755)
        self.assertRegex(proc.stdout, rf"Study folder {re.escape(str(self.study))}: not writable")

    def test_a_missing_folder_under_a_writable_one_can_be_created(self):
        missing = self.study / "new" / "study"
        proc = self.cli("doctor", "--study", missing, check=0)
        self.assertIn("does not exist yet", proc.stdout)
        self.assertIn("can be created", proc.stdout)
        self.assertFalse(missing.exists())

    def test_a_file_is_not_a_study_folder(self):
        path = self.study / "notes.txt"
        path.write_text("x", encoding="utf-8")
        proc = self.cli("doctor", "--study", path, check=1)
        self.assertIn("not a folder", proc.stdout)


class SandboxTest(unittest.TestCase):

    def test_the_web_sandbox_folders_are_recognised(self):
        sandbox_root = monitor.doctor.sandbox_root
        self.assertEqual(sandbox_root("/mnt/data/study"), "/mnt/data")
        self.assertEqual(sandbox_root("/mnt/data"), "/mnt/data")
        self.assertEqual(sandbox_root("/mnt/user-data/outputs/study"), "/mnt/user-data")
        for path in ["/mnt/database/study", "/srv/mnt/data/study", "/mnt", tempfile.gettempdir()]:
            self.assertIsNone(sandbox_root(path), path)

    def test_a_relative_path_is_read_from_the_current_folder(self):
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        try:
            os.chdir("/mnt/data")
        except OSError:
            self.skipTest("no /mnt/data on this machine")
        self.assertEqual(monitor.doctor.sandbox_root("study"), "/mnt/data")

    def test_doctor_says_a_sandbox_folder_does_not_last(self):
        lines, _ = monitor.doctor.report(study="/mnt/user-data/outputs/study")
        text = "\n".join(lines)
        self.assertIn("/mnt/user-data", text)
        self.assertIn("deleted when the conversation ends", text)

    def test_a_folder_outside_the_sandbox_gets_no_such_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            absent = os.path.join(tmp, "no-sandbox-here")
            lines, ok = monitor.doctor.report(study=tmp, roots=(absent,))
        self.assertTrue(ok)
        self.assertNotIn("conversation ends", "\n".join(lines))
        self.assertNotIn("sandbox", "\n".join(lines))


class HostSandboxTest(unittest.TestCase):
    """A host where a web sandbox folder exists is a sandbox as a whole: no folder on it lasts."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "mnt-data"
        self.study = self.tmp / "elsewhere" / "study"
        self.study.mkdir(parents=True)

    def test_an_existing_sandbox_folder_makes_the_host_a_sandbox(self):
        self.root.mkdir()
        self.assertEqual(monitor.doctor.host_sandbox((str(self.root), str(self.tmp / "absent"))), [str(self.root)])
        lines, ok = monitor.doctor.report(roots=(str(self.root),))
        text = "\n".join(lines)
        self.assertTrue(ok)
        self.assertIn(f"{self.root} exists", text)
        self.assertIn("deleted when the conversation ends", text)

    def test_a_study_folder_outside_the_sandbox_folders_does_not_last_on_such_a_host(self):
        self.root.mkdir()
        lines, ok = monitor.doctor.report(study=self.study, roots=(str(self.root),))
        study_lines = [line for line in lines if line.startswith(f"Study folder {self.study}")]
        self.assertTrue(ok)
        self.assertTrue(any("writable" in line for line in study_lines), study_lines)
        self.assertTrue(any("deleted when the conversation ends" in line for line in study_lines), study_lines)

    def test_a_host_without_those_folders_is_not_a_sandbox(self):
        self.assertEqual(monitor.doctor.host_sandbox((str(self.root),)), [])
        lines, _ = monitor.doctor.report(study=self.study, roots=(str(self.root),))
        self.assertNotIn("sandbox", "\n".join(lines))

    def test_a_path_under_an_injected_root_is_recognised(self):
        self.assertEqual(monitor.doctor.sandbox_root(self.root / "study", roots=(str(self.root),)), str(self.root))
        self.assertIsNone(monitor.doctor.sandbox_root(self.study, roots=(str(self.root),)))


class FrontmatterTest(unittest.TestCase):
    """The YAML subset SKILL.md uses, read with the standard library."""

    def parse(self, text):
        return monitor.frontmatter.parse(text)

    def test_skill_md_parses(self):
        fm = monitor.frontmatter.read(SKILL_MD)
        self.assertEqual(fm["name"], "sentl-monitor")
        self.assertEqual(fm["metadata"]["version"], skill_md_version())
        self.assertNotIn("\n", fm["description"])
        self.assertTrue(fm["description"].startswith("Reports what AI assistants say"))
        self.assertTrue(fm["description"].endswith("LLM reputation reports."))

    def test_folded_literal_quoted_and_nested_values(self):
        fm = self.parse("---\r\nname: x\r\ndescription: >-\r\n  one\r\n  two\r\n\r\n  three\r\n"
                        "notes: |\n  a\n  b\nlicense: 'it''s'\nkey: \"a: b\"\nmetadata:\n  version: \"1.2.3\"\n"
                        "  homepage: https://example.com/x\n# a comment\n---\nbody\n")
        self.assertEqual(fm["description"], "one two\nthree")
        self.assertEqual(fm["notes"], "a\nb\n")
        self.assertEqual(fm["license"], "it's")
        self.assertEqual(fm["key"], "a: b")
        self.assertEqual(fm["metadata"], {"version": "1.2.3", "homepage": "https://example.com/x"})

    def test_a_file_without_frontmatter_is_refused(self):
        for text in ["# title\n", "---\nname: x\n"]:
            with self.assertRaises(monitor.frontmatter.Malformed):
                self.parse(text)


if __name__ == "__main__":
    unittest.main()
