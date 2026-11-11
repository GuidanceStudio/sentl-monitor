"""The PDF engines the deck prints with (pdf.print_pdf): their order, the next one when one fails, a browser that cannot
start its sandbox, what `doctor` says of them, and the name of the copy to send (pdf.share_name)."""

import json
import os
import stat
import unittest
from pathlib import Path
from unittest import mock

from fixtures import StudyCase
from sentlmon import deck, pdf
from sentlmon.common import Study

PAGE = "<!doctype html><html><body><p>Avenello</p></body></html>"


class EngineCase(StudyCase):
    """A small page to print and a folder of fake engines that is the whole PATH."""

    def setUp(self):
        super().setUp()
        self.bin = self.study.parent / "bin"
        self.bin.mkdir()
        self.page = self.study / "page.html"
        self.page.write_text(PAGE, encoding="utf-8")
        self.out = self.study / "page.pdf"

    def fake_engine(self, name):
        exe = self.bin / name
        exe.write_text("#!/bin/sh\nfor a; do case \"$a\" in --print-to-pdf=*) out=\"${a#--print-to-pdf=}\";; esac; done\n"
                       "[ -z \"$out\" ] && out=\"$2\"\nprintf '%%PDF-1.4' > \"$out\"\n", encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

    def broken_engine(self, name, said):
        exe = self.bin / name
        exe.write_text(f"#!/bin/sh\necho '{said}' >&2\nexit 1\n", encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

    def print_page(self, engines=deck.ENGINES):
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            return pdf.print_pdf(self.page, self.out, engines)


class EngineTest(EngineCase, unittest.TestCase):

    def test_without_an_engine_nothing_is_printed(self):
        self.assertEqual(self.print_page(), (None, []))
        self.assertFalse(self.out.exists())

    def test_with_an_engine_it_writes_the_pdf(self):
        self.fake_engine("weasyprint")
        self.assertEqual(self.print_page(), ("weasyprint", []))
        self.assertTrue(self.out.read_bytes().startswith(b"%PDF"))

    def test_the_deck_tries_a_browser_before_weasyprint(self):
        self.fake_engine("weasyprint")
        self.fake_engine("google-chrome")
        self.assertEqual(self.print_page()[0], "google-chrome")

    def test_the_first_engine_found_in_the_list_is_used(self):
        self.fake_engine("google-chrome")
        self.fake_engine("chromium")
        self.assertEqual(self.print_page()[0], "chromium")

    def test_the_deck_never_prints_with_wkhtmltopdf(self):
        self.fake_engine("wkhtmltopdf")
        self.assertEqual(self.print_page(), (None, []))
        self.assertNotIn("wkhtmltopdf", [name for name, _ in deck.ENGINES])

    def test_an_engine_that_fails_is_skipped_for_the_next_one(self):
        self.broken_engine("chromium", "cannot open display")
        self.fake_engine("weasyprint")
        engine, failures = self.print_page()
        self.assertEqual(engine, "weasyprint")
        self.assertEqual(len(failures), 1)
        self.assertIn("cannot open display", failures[0])

    def test_when_every_engine_fails_the_reasons_are_told_and_no_pdf_is_left(self):
        self.broken_engine("chromium", "cannot open display")
        self.broken_engine("weasyprint", "missing pango")
        engine, failures = self.print_page()
        self.assertIsNone(engine)
        self.assertIn("cannot open display", " ".join(failures))
        self.assertIn("missing pango", " ".join(failures))
        self.assertFalse(self.out.exists())


# What a Chromium build without an AppArmor profile prints where the system restricts unprivileged user namespaces.
NO_SANDBOX = ("[0:0:FATAL:zygote_host_impl_linux.cc(132)] No usable sandbox! If you are running on Ubuntu 23.10+ or "
              "another Linux distro that has disabled unprivileged user namespaces with AppArmor, see the docs.")


def sandboxless(folder, name):
    """A browser in `folder` that cannot start its sandbox here, and would print if told to run without it."""
    exe = Path(folder) / name
    exe.write_text("#!/bin/sh\nfor a; do case \"$a\" in --print-to-pdf=*) out=\"${a#--print-to-pdf=}\";; "
                   "--no-sandbox) free=1;; esac; done\n"
                   "if [ -n \"$free\" ]; then printf '%%PDF-1.4' > \"$out\"; exit 0; fi\n"
                   f"echo '{NO_SANDBOX}' >&2\nexit 134\n", encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)


class SandboxTest(EngineCase, unittest.TestCase):
    """A browser prints with its sandbox, or the PDF is not printed; `doctor` says which browser prints here."""

    def sandboxless(self, name):
        sandboxless(self.bin, name)

    def test_no_engine_prints_without_the_sandbox(self):
        for name, template in pdf.ENGINES + deck.ENGINES:
            self.assertNotIn("--no-sandbox", template, name)

    def test_a_browser_without_its_sandbox_stops_the_print_with_the_cause_and_the_fix(self):
        self.sandboxless("chromium")
        with self.assertRaises(pdf.NoSandbox) as raised:
            self.print_page()
        said = str(raised.exception)
        for part in ("chromium", "sandbox", "Google Chrome", "AppArmor", "weasyprint", str(self.page)):
            self.assertIn(part, said)
        self.assertFalse(self.out.exists())

    def test_a_sandboxed_browser_after_one_without_its_sandbox_prints(self):
        self.sandboxless("chromium")
        self.fake_engine("google-chrome")
        self.assertEqual(self.print_page()[0], "google-chrome")

    def test_a_sandboxed_browser_after_one_failing_for_another_reason_prints(self):
        self.broken_engine("chromium", "cannot open display")
        self.fake_engine("google-chrome")
        self.assertEqual(self.print_page()[0], "google-chrome")

    def test_doctor_says_which_browser_prints_with_its_sandbox(self):
        self.fake_engine("google-chrome")
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            out = self.cli("doctor", check=0).stdout
        self.assertIn("PDF: google-chrome prints with its sandbox", out)

    def test_doctor_names_a_browser_without_its_sandbox_and_the_fix(self):
        self.sandboxless("chromium")
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            out = self.cli("doctor", check=0).stdout
        line = next(ln for ln in out.splitlines() if ln.startswith("PDF:"))
        self.assertIn("chromium cannot start its sandbox", line)
        self.assertIn("Google Chrome", line)
        self.assertIn("weasyprint", line)

    def test_doctor_says_when_no_engine_is_installed(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            out = self.cli("doctor", check=0).stdout
        self.assertIn("PDF: no PDF engine is installed", out)


class ShareNameTest(StudyCase, unittest.TestCase):
    """The copy to send is named after the subject and the period its deck records."""

    def record(self, start="2026-10-08T09:00:00+00:00", end="2026-10-14T23:59:59+00:00"):
        (self.study / "history").mkdir(exist_ok=True)
        (self.study / "history" / "reports.json").write_text(json.dumps([{
            "date": "2026-10-14", "status": "final", "period": {"from": start, "to": end}, "runs": {}, "previous": None,
            "deck": "reports/2026-10-14.deck.json"}]), encoding="utf-8")

    def name(self, subject="Avenello"):
        return pdf.share_name(Study(self.study), {"subject": {"label": subject}}, "2026-10-14")

    def test_the_name_says_whose_deck_and_which_period(self):
        self.record()
        self.assertEqual(self.name(), "Avenello + Sentl.ai - monitoring deck (2026-10-08 to 2026-10-14)")

    def test_characters_a_file_system_refuses_are_replaced(self):
        self.record()
        self.assertEqual(self.name("Ave/nello: Foods"),
                         "Ave nello Foods + Sentl.ai - monitoring deck (2026-10-08 to 2026-10-14)")

    def test_a_one_day_period_is_named_with_that_day_once(self):
        self.record("2026-10-14T09:00:00+00:00", "2026-10-14T18:00:00+00:00")
        self.assertEqual(self.name(), "Avenello + Sentl.ai - monitoring deck (2026-10-14)")

    def test_without_an_entry_the_name_carries_the_date(self):
        self.assertEqual(self.name(), "Avenello + Sentl.ai - monitoring deck (2026-10-14)")


if __name__ == "__main__":
    unittest.main()
