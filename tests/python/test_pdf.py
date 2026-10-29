"""`monitor.py pdf`: the report as a print-ready page, and as a PDF when an engine is on the path."""

import os
import stat
import unittest
from pathlib import Path
from unittest import mock

from fixtures import StudyCase
from sentlmon import pdf

REPORT = """# What do people ask?

Avenello · period from 8 October to 14 October 2026

## 1. What we did

We asked **3 questions** to *2 assistants* and kept `inbox/` out.

- Nutrition: sugar
- Choice: best oat milk

| Dimension | Score |
|---|---|
| Nutrition | 3.5 |
| Choice | 4.0 |

> Avenello Original has about 5 g of sugar. <script>x</script>

1. First
2. Second
"""


class RenderTest(unittest.TestCase):

    def test_headings_lists_tables_quotes_and_emphasis(self):
        out = pdf.render(REPORT)
        for part in ("<h1>What do people ask?</h1>", "<h2>1. What we did</h2>", "<strong>3 questions</strong>",
                     "<em>2 assistants</em>", "<code>inbox/</code>", "<li>Nutrition: sugar</li>",
                     "<ol><li>First</li><li>Second</li></ol>", "<th>Dimension</th>", "<td>3.5</td>",
                     "<blockquote>"):
            self.assertIn(part, out)

    def test_text_is_escaped(self):
        out = pdf.render(REPORT)
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_the_page_is_a_document_with_the_title_and_a_print_style(self):
        out = pdf.page(REPORT, "it")
        self.assertTrue(out.startswith("<!doctype html>"))
        self.assertIn('<html lang="it">', out)
        self.assertIn("<title>What do people ask?</title>", out)
        self.assertIn("@page", out)


class CommandTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        (self.study / "reports").mkdir()
        (self.study / "reports" / "2026-10-14.md").write_text(REPORT, encoding="utf-8")
        (self.study / "reports" / "2026-10-14.draft.md").write_text("# draft", encoding="utf-8")
        self.bin = self.study.parent / "bin"
        self.bin.mkdir()

    def fake_engine(self, name):
        exe = self.bin / name
        exe.write_text("#!/bin/sh\nfor a; do case \"$a\" in --print-to-pdf=*) out=\"${a#--print-to-pdf=}\";; esac; done\n"
                       "[ -z \"$out\" ] && out=\"$2\"\nprintf '%%PDF-1.4' > \"$out\"\n", encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

    def run_pdf(self, *args, check=0):
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            return self.cli("pdf", "--study", self.study, *args, check=check)

    def test_without_an_engine_it_writes_the_page_and_says_how_to_print_it(self):
        proc = self.run_pdf()
        self.assertTrue((self.study / "reports" / "2026-10-14.html").exists())
        self.assertFalse((self.study / "reports" / "2026-10-14.pdf").exists())
        self.assertIn("print it to PDF", proc.stdout)

    def test_with_an_engine_it_writes_the_pdf(self):
        self.fake_engine("weasyprint")
        proc = self.run_pdf()
        pdf_file = self.study / "reports" / "2026-10-14.pdf"
        self.assertTrue(pdf_file.read_bytes().startswith(b"%PDF"))
        self.assertIn("weasyprint", proc.stdout)

    def test_the_first_engine_found_in_the_list_is_used(self):
        self.fake_engine("wkhtmltopdf")
        self.fake_engine("chromium")
        self.assertIn("(engine: chromium)", self.run_pdf().stdout)

    def test_an_engine_that_fails_is_skipped_for_the_next_one(self):
        broken = self.bin / "weasyprint"
        broken.write_text("#!/bin/sh\necho 'no sandbox' >&2\nexit 1\n", encoding="utf-8")
        broken.chmod(broken.stat().st_mode | stat.S_IEXEC)
        self.fake_engine("wkhtmltopdf")
        self.assertIn("(engine: wkhtmltopdf)", self.run_pdf().stdout)

    def test_when_every_engine_fails_the_page_is_kept_and_the_reasons_are_told(self):
        broken = self.bin / "weasyprint"
        broken.write_text("#!/bin/sh\necho 'no sandbox' >&2\nexit 1\n", encoding="utf-8")
        broken.chmod(broken.stat().st_mode | stat.S_IEXEC)
        out = self.run_pdf().stdout
        self.assertIn("no sandbox", out)
        self.assertTrue((self.study / "reports" / "2026-10-14.html").exists())
        self.assertFalse((self.study / "reports" / "2026-10-14.pdf").exists())

    def test_a_draft_is_not_the_latest_report_and_a_date_picks_one(self):
        self.run_pdf("--date", "2026-10-14")
        self.assertFalse((self.study / "reports" / "2026-10-14.draft.html").exists())

    def test_no_report_is_refused(self):
        (self.study / "reports" / "2026-10-14.md").unlink()
        self.assertIn("no final report", self.run_pdf(check=2).stderr)

    def test_an_unknown_date_is_refused(self):
        self.run_pdf("--date", "2026-01-01", check=2)


if __name__ == "__main__":
    unittest.main()
