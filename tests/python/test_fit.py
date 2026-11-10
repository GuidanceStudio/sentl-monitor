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

    def test_the_margin_under_the_last_item_of_a_column_is_cut(self):
        css = "ul { columns: 2; column-gap: 0; margin: 0; padding: 0; } li { margin-bottom: 4px; }"
        self.assertEqual(height("<ul><li>a</li><li>b</li><li>c</li><li>d</li></ul>", css), 24)

    def test_a_flex_row_is_as_tall_as_its_tallest_item(self):
        css = "section { padding: 0 1180px 0 0; } .row { display: flex; gap: 0; } .row > div { flex: 1; }"
        self.assertEqual(height(f'<div class="row"><div>WWWW</div><div>{WORDS}</div></div>', css), 20)


if __name__ == "__main__":
    unittest.main()
