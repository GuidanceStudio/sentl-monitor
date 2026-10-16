"""The rules of ARCHITECTURE.md §What counts as a change, on bare values."""

import unittest

import fixtures  # noqa: F401  (puts the skill's scripts on sys.path)
from sentlmon.compare import band, called


class BandTest(unittest.TestCase):

    def test_bands_on_their_edges(self):
        self.assertEqual([band(m) for m in (2.45, 2.5, 3.49, 3.5)],
                         ["unfavourable", "mixed", "mixed", "favourable"])

    def test_a_pair_without_a_judged_answer_has_no_band(self):
        self.assertIsNone(band(None))


class CalledTest(unittest.TestCase):
    """`called(now, previous values latest first, kind)`."""

    def test_one_previous_period_needs_half_a_point(self):
        self.assertFalse(called(3.4, [3.0], "mean"))
        self.assertTrue(called(3.5, [3.0], "mean"))
        self.assertTrue(called(2.5, [3.0], "mean"))

    def test_two_previous_periods_need_the_range_and_three_tenths(self):
        self.assertTrue(called(3.3, [3.0, 2.6], "mean"))
        self.assertFalse(called(3.2, [3.0, 2.6], "mean"), "outside the range, 0.2 from the previous period")
        self.assertFalse(called(2.7, [3.0, 2.6], "mean"), "inside the range")

    def test_four_previous_periods_set_the_range(self):
        values = [3.0, 2.5, 3.5, 2.8]
        self.assertFalse(called(3.4, values, "mean"))
        self.assertFalse(called(2.6, values, "mean"))
        self.assertTrue(called(3.6, values, "mean"))
        self.assertTrue(called(2.4, values, "mean"))

    def test_only_the_four_latest_periods_make_the_range(self):
        self.assertTrue(called(3.6, [3.0, 2.9, 3.1, 3.0, 4.5], "mean"))

    def test_presence_moves_are_in_percentage_points(self):
        self.assertFalse(called(0.69, [0.5], "presence"))
        self.assertTrue(called(0.70, [0.5], "presence"))
        self.assertTrue(called(0.60, [0.5, 0.45], "presence"))
        self.assertFalse(called(0.59, [0.5, 0.45], "presence"))

    def test_no_previous_value_calls_no_change(self):
        self.assertFalse(called(3.0, [], "mean"))
        self.assertFalse(called(None, [3.0], "mean"))


if __name__ == "__main__":
    unittest.main()
