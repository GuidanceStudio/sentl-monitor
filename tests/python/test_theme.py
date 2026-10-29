"""The look of a report: Sentl's by default, replaced by a theme the user points at."""

import json
import os
import re
import unittest
from pathlib import Path
from unittest import mock

from fixtures import StudyCase
from sentlmon import pdf, theme
from sentlmon.common import Refused
from test_pdf import CommandBase, REPORT

SENTL_ORANGE = "#FF850D"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class DefaultThemeTest(unittest.TestCase):

    def test_the_default_page_carries_sentls_colours_and_mark(self):
        out = pdf.page(REPORT, "en", theme.builtin())
        self.assertIn(SENTL_ORANGE, out)
        self.assertIn("#B85C00", out)
        self.assertIn('src="data:image/png;base64,', out)
        self.assertIn("Sentl.AI", out)

    def test_the_page_needs_no_network(self):
        out = pdf.page(REPORT, "en", theme.builtin())
        self.assertNotRegex(out, r'(src|href)="https?://')
        self.assertNotIn("@import", out)
        self.assertNotIn("<link", out)

    def test_the_structure_is_styled_through_variables(self):
        out = pdf.page(REPORT, "en", theme.builtin())
        for name in ("--sl-primary", "--sl-deep", "--sl-text", "--sl-muted", "--sl-line", "--sl-tint", "--sl-font"):
            self.assertIn(name + ":", out)
        body = out.split("</style>")[0].split("<style>")[1]
        rules = body.split("body {", 1)[1]
        self.assertNotRegex(rules, r"#[0-9A-Fa-f]{6}")


class ThemeFileTest(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_a_json_theme_changes_the_variables_the_footer_and_the_font(self):
        file = write(self.tmp / "t.json", json.dumps({
            "colors": {"primary": "#2255AA", "deep": "#112244"}, "font": "Georgia, serif",
            "footer": "Prepared for Avenello"}))
        loaded, notes = theme.load(file)
        out = pdf.page(REPORT, "en", loaded)
        self.assertIn("--sl-primary: #2255AA;", out)
        self.assertIn("--sl-deep: #112244;", out)
        self.assertIn("--sl-font: Georgia, serif;", out)
        self.assertIn("Prepared for Avenello", out)
        self.assertNotIn("#FF850D", out)
        self.assertEqual(notes, [])

    def test_what_a_theme_leaves_out_stays_Sentls(self):
        file = write(self.tmp / "t.json", json.dumps({"colors": {"primary": "#2255AA"}}))
        loaded, _ = theme.load(file)
        self.assertEqual(loaded["colors"]["deep"], theme.builtin()["colors"]["deep"])
        self.assertEqual(loaded["logo"], theme.builtin()["logo"])

    def test_a_css_theme_overrides_the_variables_after_the_defaults(self):
        file = write(self.tmp / "t.css", ":root { --sl-primary: #00AA55; }\n.sl-footer { display: none; }")
        loaded, _ = theme.load(file)
        out = pdf.page(REPORT, "en", loaded)
        self.assertLess(out.index("--sl-primary: #FF850D"), out.index("--sl-primary: #00AA55"))
        self.assertIn(".sl-footer { display: none; }", out)

    def test_a_logo_path_is_embedded_and_an_inline_svg_is_kept(self):
        mark = self.tmp / "mark.png"
        mark.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        loaded, _ = theme.load(write(self.tmp / "a.json", json.dumps({"logo": "mark.png"})))
        self.assertTrue(loaded["logo"].startswith("data:image/png;base64,"))
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
        loaded, _ = theme.load(write(self.tmp / "b.json", json.dumps({"logo": svg})))
        out = pdf.page(REPORT, "en", loaded)
        self.assertIn('<img class="sl-logo" src="data:image/svg+xml;base64,', out)

    def test_a_missing_logo_falls_back_to_the_sentl_mark_and_says_so(self):
        loaded, notes = theme.load(write(self.tmp / "t.json", json.dumps({"logo": "nowhere.png"})))
        self.assertEqual(loaded["logo"], theme.builtin()["logo"])
        self.assertEqual(len(notes), 1)
        self.assertIn("nowhere.png", notes[0])
        self.assertIn("Sentl", notes[0])

    def test_font_url_becomes_a_link_only_when_it_is_set(self):
        plain, _ = theme.load(write(self.tmp / "a.json", json.dumps({"font": "Inter"})))
        self.assertNotIn("<link", pdf.page(REPORT, "en", plain))
        linked, _ = theme.load(write(self.tmp / "b.json", json.dumps(
            {"font": "Inter", "font_url": "https://fonts.example.com/inter.css"})))
        self.assertIn('<link rel="stylesheet" href="https://fonts.example.com/inter.css">', pdf.page(REPORT, "en", linked))

    def test_a_value_that_could_break_out_of_the_stylesheet_is_refused(self):
        file = write(self.tmp / "t.json", json.dumps({"colors": {"primary": "red; } body { display: none"}}))
        with self.assertRaises(Refused):
            theme.load(file)

    def test_a_theme_that_is_not_json_or_css_or_unreadable_is_refused(self):
        with self.assertRaises(Refused):
            theme.load(write(self.tmp / "t.json", "{not json"))
        with self.assertRaises(Refused):
            theme.load(self.tmp / "absent.json")
        with self.assertRaises(Refused):
            theme.load(write(self.tmp / "t.txt", "x"))


class ResolutionTest(CommandBase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.home = self.study.parent / "home"
        self.home.mkdir()
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config")}

    def primary(self, *args):
        with mock.patch.dict(os.environ, self.env):
            proc = self.run_pdf(*args)
        page = (self.study / "reports" / "2026-10-14.html").read_text(encoding="utf-8")
        return re.findall(r"--sl-primary: (#[0-9A-Fa-f]{6});", page)[-1], proc

    def theme_json(self, path, colour):
        write(path, json.dumps({"colors": {"primary": colour}}))

    def test_nothing_set_gives_sentls_orange(self):
        self.assertEqual(self.primary()[0], SENTL_ORANGE)

    def test_the_user_folder_replaces_the_default(self):
        self.theme_json(self.home / ".config" / "sentl-monitor" / "theme.json", "#111111")
        self.assertEqual(self.primary()[0], "#111111")

    def test_the_study_folder_beats_the_user_folder(self):
        self.theme_json(self.home / ".config" / "sentl-monitor" / "theme.json", "#111111")
        self.theme_json(self.study / "theme.json", "#222222")
        self.assertEqual(self.primary()[0], "#222222")

    def test_theme_css_in_the_study_folder_is_found_when_there_is_no_json(self):
        write(self.study / "theme.css", ":root { --sl-primary: #333333; }")
        self.assertEqual(self.primary()[0], "#333333")

    def test_the_theme_key_of_study_json_beats_the_study_folder(self):
        self.theme_json(self.study / "theme.json", "#222222")
        self.theme_json(self.study / "brand" / "own.json", "#444444")
        write(self.study / "study.json", json.dumps({"theme": "brand/own.json", "report_language": "en"}))
        self.assertEqual(self.primary()[0], "#444444")

    def test_the_option_beats_everything(self):
        self.theme_json(self.study / "theme.json", "#222222")
        write(self.study / "study.json", json.dumps({"theme": "theme.json"}))
        other = self.study.parent / "other.json"
        self.theme_json(other, "#555555")
        self.assertEqual(self.primary("--theme", other)[0], "#555555")

    def test_an_option_that_points_nowhere_is_refused(self):
        with mock.patch.dict(os.environ, self.env):
            proc = self.run_pdf("--theme", self.study / "absent.json", check=2)
        self.assertIn("absent.json", proc.stderr)

    def test_a_missing_logo_is_reported_by_the_command(self):
        write(self.study / "theme.json", json.dumps({"logo": "gone.png"}))
        _, proc = self.primary()
        self.assertIn("gone.png", proc.stdout)

    def test_the_copy_to_send_is_the_themed_page(self):
        self.theme_json(self.study / "theme.json", "#222222")
        self.primary()
        copies = list((self.study / "reports" / "share").glob("*.html"))
        self.assertEqual(len(copies), 1)
        self.assertIn("--sl-primary: #222222;", copies[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
