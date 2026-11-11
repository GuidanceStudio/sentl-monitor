"""The look of the deck: Sentl's by default, replaced by a theme the user points at."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fixtures import StudyCase
from sentlmon import deck, theme
from sentlmon import pdf as report_pdf
from sentlmon.common import Refused, Study
from test_deck import DATE, DeckCase

SENTL_ORANGE = "#FF850D"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class DefaultThemeTest(unittest.TestCase):

    def test_the_default_theme_carries_sentls_colours_and_mark(self):
        chosen = theme.builtin()
        self.assertIn(f"--sl-primary: {SENTL_ORANGE};", theme.variables(chosen))
        self.assertIn("--sl-deep: #B85C00;", theme.variables(chosen))
        self.assertTrue(chosen["logo"].startswith("data:image/png;base64,"))

    def test_every_colour_and_the_font_are_variables(self):
        variables = theme.variables(theme.builtin())
        for name in ("--sl-primary", "--sl-deep", "--sl-text", "--sl-muted", "--sl-line", "--sl-tint", "--sl-font"):
            self.assertIn(name + ":", variables)


class ThemeFileTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_a_json_theme_changes_the_colours_and_the_font(self):
        file = write(self.tmp / "t.json", json.dumps({
            "colors": {"primary": "#2255AA", "deep": "#112244"}, "font": "Georgia, serif"}))
        loaded, notes = theme.load(file)
        variables = theme.variables(loaded)
        self.assertIn("--sl-primary: #2255AA;", variables)
        self.assertIn("--sl-deep: #112244;", variables)
        self.assertIn("--sl-font: Georgia, serif;", variables)
        self.assertNotIn(SENTL_ORANGE, variables)
        self.assertEqual(notes, [])

    def test_what_a_theme_leaves_out_stays_Sentls(self):
        file = write(self.tmp / "t.json", json.dumps({"colors": {"primary": "#2255AA"}}))
        loaded, _ = theme.load(file)
        self.assertEqual(loaded["colors"]["deep"], theme.builtin()["colors"]["deep"])
        self.assertEqual(loaded["logo"], theme.builtin()["logo"])

    def test_a_css_theme_keeps_sentls_variables_and_adds_its_rules(self):
        css = ":root { --sl-primary: #00AA55; }\n.foot { display: none; }"
        loaded, _ = theme.load(write(self.tmp / "t.css", css))
        self.assertEqual(loaded["css"], css)
        self.assertEqual(loaded["colors"], theme.builtin()["colors"])

    def test_a_logo_path_is_embedded_and_an_inline_svg_is_kept(self):
        mark = self.tmp / "mark.png"
        mark.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        loaded, _ = theme.load(write(self.tmp / "a.json", json.dumps({"logo": "mark.png"})))
        self.assertTrue(loaded["logo"].startswith("data:image/png;base64,"))
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
        loaded, _ = theme.load(write(self.tmp / "b.json", json.dumps({"logo": svg})))
        self.assertTrue(loaded["logo"].startswith("data:image/svg+xml;base64,"))

    def test_a_missing_logo_falls_back_to_the_sentl_mark_and_says_so(self):
        loaded, notes = theme.load(write(self.tmp / "t.json", json.dumps({"logo": "nowhere.png"})))
        self.assertEqual(loaded["logo"], theme.builtin()["logo"])
        self.assertEqual(len(notes), 1)
        self.assertIn("nowhere.png", notes[0])
        self.assertIn("Sentl", notes[0])

    def test_font_url_is_kept_only_when_it_is_set(self):
        plain, _ = theme.load(write(self.tmp / "a.json", json.dumps({"font": "Inter"})))
        self.assertIsNone(plain["font_url"])
        linked, _ = theme.load(write(self.tmp / "b.json", json.dumps(
            {"font": "Inter", "font_url": "https://fonts.example.com/inter.css"})))
        self.assertEqual(linked["font_url"], "https://fonts.example.com/inter.css")

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


class DeckPageTest(DeckCase, unittest.TestCase):
    """What the deck's page carries of the theme, with no user theme on this machine."""

    def setUp(self):
        super().setUp()
        home = self.study.parent / "home"
        home.mkdir()
        env = mock.patch.dict(os.environ, {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")})
        env.start()
        self.addCleanup(env.stop)
        self.save_doc(self.filled())

    def page(self, option=None):
        return deck.page_of(self.study, DATE, option)[0]

    def style(self, option=None):
        return self.page(option).split("<style>", 1)[1].split("</style>", 1)[0]

    def test_the_default_page_carries_sentls_colours_and_mark(self):
        text = self.page()
        self.assertIn(SENTL_ORANGE, text)
        self.assertIn("#B85C00", text)
        self.assertIn('<img src="data:image/png;base64,', text)

    def test_the_page_needs_no_network(self):
        text = self.page()
        self.assertNotRegex(text, r'(src|href)="https?://')
        self.assertNotIn("@import", text)
        self.assertNotIn("<link", text)

    def test_the_slides_take_the_theme_s_colours_through_its_variables_only(self):
        style = self.style()
        for name, value in theme.COLORS.items():
            self.assertEqual(style.count(value), 1, name)

    def test_a_json_theme_reaches_the_page(self):
        option = write(self.study.parent / "t.json", json.dumps({"colors": {"primary": "#2255AA"},
                                                                 "font": "Georgia, serif"}))
        style = self.style(option)
        self.assertIn("--sl-primary: #2255AA;", style)
        self.assertIn("--sl-font: Georgia, serif;", style)
        self.assertNotIn(SENTL_ORANGE, style)

    def test_a_css_theme_overrides_the_variables_after_the_defaults(self):
        css = ":root { --sl-primary: #00AA55; }\n.foot { display: none; }"
        style = self.style(write(self.study.parent / "t.css", css))
        self.assertLess(style.index(f"--sl-primary: {SENTL_ORANGE}"), style.index("--sl-primary: #00AA55"))
        self.assertTrue(style.endswith(css))

    def test_an_inline_svg_logo_is_embedded(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
        option = write(self.study.parent / "t.json", json.dumps({"logo": svg}))
        self.assertIn('<img src="data:image/svg+xml;base64,', self.page(option))

    def test_font_url_becomes_a_link_only_when_it_is_set(self):
        plain = write(self.study.parent / "a.json", json.dumps({"font": "Inter"}))
        self.assertNotIn("<link", self.page(plain))
        linked = write(self.study.parent / "b.json", json.dumps(
            {"font": "Inter", "font_url": "https://fonts.example.com/inter.css"}))
        self.assertIn('<link rel="stylesheet" href="https://fonts.example.com/inter.css">', self.page(linked))

    def test_the_theme_option_of_pdf_reaches_the_page(self):
        self.cli("check", "--study", self.study, self.path, check=0)
        option = write(self.study.parent / "t.json", json.dumps({"colors": {"primary": "#555555"}}))
        with mock.patch.object(report_pdf, "print_pdf", lambda target, pdf, engines: (None, [])):
            self.cli("pdf", "--study", self.study, "--date", DATE, "--theme", option, check=0)
        self.assertIn("--sl-primary: #555555;", (self.study / "reports" / f"{DATE}.deck.html").read_text(encoding="utf-8"))


class ResolutionTest(StudyCase, unittest.TestCase):
    """Which theme the deck is drawn with: the option, the `theme` key of study.json, the study folder, the user's
    folder, Sentl's."""

    def setUp(self):
        super().setUp()
        self.home = self.study.parent / "home"
        self.home.mkdir()
        env = mock.patch.dict(os.environ, {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config")})
        env.start()
        self.addCleanup(env.stop)

    def resolved(self, option=None):
        return theme.resolve(Study(self.study), option)

    def primary(self, option=None):
        return self.resolved(option)[0]["colors"]["primary"]

    def theme_json(self, path, colour):
        write(path, json.dumps({"colors": {"primary": colour}}))

    def test_nothing_set_gives_sentls_orange(self):
        self.assertEqual(self.primary(), SENTL_ORANGE)

    def test_the_user_folder_replaces_the_default(self):
        self.theme_json(self.home / ".config" / "sentl-monitor" / "theme.json", "#111111")
        self.assertEqual(self.primary(), "#111111")

    def test_the_study_folder_beats_the_user_folder(self):
        self.theme_json(self.home / ".config" / "sentl-monitor" / "theme.json", "#111111")
        self.theme_json(self.study / "theme.json", "#222222")
        self.assertEqual(self.primary(), "#222222")

    def test_theme_css_in_the_study_folder_is_found_when_there_is_no_json(self):
        write(self.study / "theme.css", ":root { --sl-primary: #333333; }")
        self.assertIn("--sl-primary: #333333;", self.resolved()[0]["css"])

    def test_the_theme_key_of_study_json_beats_the_study_folder(self):
        self.theme_json(self.study / "theme.json", "#222222")
        self.theme_json(self.study / "brand" / "own.json", "#444444")
        write(self.study / "study.json", json.dumps({"theme": "brand/own.json", "report_language": "en"}))
        self.assertEqual(self.primary(), "#444444")

    def test_the_option_beats_everything(self):
        self.theme_json(self.study / "theme.json", "#222222")
        write(self.study / "study.json", json.dumps({"theme": "theme.json"}))
        other = self.study.parent / "other.json"
        self.theme_json(other, "#555555")
        self.assertEqual(self.primary(other), "#555555")

    def test_an_option_that_points_nowhere_is_refused(self):
        with self.assertRaisesRegex(Refused, "absent.json"):
            self.resolved(self.study / "absent.json")

    def test_a_missing_logo_is_named_in_the_notes(self):
        write(self.study / "theme.json", json.dumps({"logo": "gone.png"}))
        notes = self.resolved()[1]
        self.assertEqual(len(notes), 1)
        self.assertIn("gone.png", notes[0])


if __name__ == "__main__":
    unittest.main()
