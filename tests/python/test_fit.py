"""The estimate of a slide's height lays its text out as the browser does: these are the rules it follows."""

import unittest

import fixtures  # noqa: F401  (puts the skill's scripts on the path)
from sentlmon import fit

# 10 px Arial on lines of 10 px; "WWWW" is 37.76 px wide, a space 2.78 px.
BASE = "section { font-size: 10px; line-height: 1; } p { margin: 0; } "
WORDS = "WWWW WWWW"


def height(body, css):
    return fit.heights(f"<section>{body}</section>", BASE + css)[0]


class FitTest(unittest.TestCase):

    def test_words_wrap_at_the_width_of_their_box(self):
        narrow = "section { padding: 0 1200px 0 0; }"  # 80 px of text
        self.assertEqual(height(f"<p>{WORDS}</p>", narrow), 10)
        self.assertEqual(height(f"<p>{WORDS} {WORDS}</p>", narrow), 20)

    def test_three_values_of_padding_give_the_second_to_both_sides(self):
        self.assertEqual(height(f"<p>{WORDS} WWWW</p>", "section { padding: 0 600px 0; }"), 20)

    def test_a_shorthand_resets_the_longhand_an_earlier_rule_set(self):
        # The browser gives a list padding-left: 40px; `padding: 0` takes it away, and the two words fit on one line.
        css = "section { padding: 0 1200px 0 0; } ul.x { margin: 0; padding: 0; }"
        self.assertEqual(height(f'<ul class="x"><li>{WORDS}</li></ul>', css), 10)

    def test_text_that_must_not_wrap_stays_on_one_line(self):
        css = "section { padding: 0 1230px 0 0; } .n { white-space: nowrap; }"
        self.assertEqual(height(f'<p><span class="n">{WORDS}</span></p>', css), 10)
        self.assertEqual(height(f"<p>{WORDS}</p>", css), 20)

    def test_a_box_is_no_wider_than_its_max_width(self):
        self.assertEqual(height(f'<div class="m">{WORDS}</div>', "section { padding: 0 1200px 0 0; } .m { max-width: 50px; }"), 20)

    def test_columns_grow_from_an_even_share_until_they_hold_every_item(self):
        css = "ul { columns: 2; column-gap: 0; margin: 0; padding: 0; } li { margin-bottom: 4px; }"
        self.assertEqual(height("<ul><li>a</li><li>b</li><li>c</li><li>d</li></ul>", css), 28)  # 56 px over two
        self.assertEqual(height("<ul><li>a</li><li>b</li><li>c<br>c<br>c</li></ul>", css), 31)
        # An item taller than the even share sets the height, the margin under it cut.
        self.assertEqual(height("<ul><li>a<br>a</li><li>b</li></ul>", css), 20)

    def test_a_flex_row_is_as_tall_as_its_tallest_item(self):
        css = "section { padding: 0 1180px 0 0; } .row { display: flex; gap: 0; } .row > div { flex: 1; }"
        self.assertEqual(height(f'<div class="row"><div>WWWW</div><div>{WORDS}</div></div>', css), 20)

    def test_a_fixed_table_column_holds_its_cells_padding_beside_their_width(self):
        # 200 px of table; the first column is its cell's 50 px and 20 px of padding, so the second holds 110 px of text.
        css = ("section { padding: 0 1080px 0 0; } table { table-layout: fixed; width: 100%; border-collapse: collapse; } "
               "td { padding: 0 10px; } .a { width: 50px; } .b { width: 25%; }")
        for first in ("a", "b"):
            self.assertEqual(height(f'<table><tr><td class="{first}">1</td><td>{WORDS} WWWW</td></tr></table>', css), 20, first)

    def test_growing_items_keep_their_padding_before_they_share_the_room(self):
        # 200 px: the first item keeps its 60 px of padding, and the 140 px left go half to each.
        css = ("section { padding: 0 1080px 0 0; } .row { display: flex; } .row > div { flex: 1 1 0; } "
               ".row > .pad { padding: 0 30px; }")
        self.assertEqual(height(f'<div class="row"><div class="pad">W</div><div>{WORDS}</div></div>', css), 20)

    def test_a_line_breaks_where_the_browser_breaks_it(self):
        narrow = "section { padding: 0 1230px 0 0; }"  # 50 px of text
        for text in ("WWWW-WWWW", "WWWW—WWWW", "WWWW…WWWW", "WWWW?WWWW", "WWWW–WWWW"):
            self.assertEqual(height(f"<p>{text}</p>", narrow), 20, text)
        for text in ("WWWW/WWWW", "WWWW.WWWW", "WWWW’WWWW", "WWWW-«WWW"):
            self.assertEqual(height(f"<p>{text}</p>", narrow), 10, text)
        # A minus sign keeps its number, and a dash after a space keeps its word: 30 px of text.
        thin = "section { padding: 0 1250px 0 0; }"
        for text, lines in (("-1234567", 1), ("(-1234567", 1), ("WW-1234567", 2), ("–WWWWW", 1), ("WW–WWWWW", 2)):
            self.assertEqual(height(f"<p>{text}</p>", thin), 10 * lines, text)
        # An inline block, such as a legend's swatch, starts or ends a line beside any word.
        swatch = "section { padding: 0 1230px 0 0; } i { display: inline-block; width: 11px; margin-right: 5px; }"
        self.assertEqual(height("<p><i></i>WWWWW</p>", swatch), 20)
        # Text that must not wrap breaks at no hyphen either.
        self.assertEqual(height('<p><span class="n">WWWW-WWWW</span></p>', narrow + " .n { white-space: nowrap; }"), 10)

    def test_line_heights_a_theme_may_set(self):
        self.assertEqual(height(f"<p>{WORDS}</p>", "section { font-size: 20px; line-height: normal; }"), 23)
        self.assertEqual(height("<p>x</p>", "section { font-size: 20px; line-height: 150%; } p { font-size: 10px; }"), 30)
        self.assertEqual(height("<p>x</p>", "section { font-size: 20px; line-height: 2em; } p { font-size: 10px; }"), 40)
        self.assertEqual(height("<p>x</p>", "p { font-size: 2rem; line-height: 24px; }"), 24)
        self.assertEqual(height("<p>x</p>", "p { font: 700 2rem/1.5 Inter, sans-serif; }"), 48)
        self.assertEqual(height("<p>x</p>", "p { font: 20px Inter, sans-serif; }"), 23)

    def test_values_the_estimate_cannot_read_leave_it_standing(self):
        css = ("p { font-size: var(--size); line-height: var(--lead); padding: calc(1em + 2px) 1rem; margin: auto; "
               "width: min(10px, 5vw); gap: normal; } section { font-size: larger; }")
        self.assertGreater(height("<p>x</p>", css), 0)


if __name__ == "__main__":
    unittest.main()
