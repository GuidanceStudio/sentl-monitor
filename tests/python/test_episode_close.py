"""An episode's close date is the first run back inside its range and says nothing about the runs
after it: the period file and the material list the later runs on the episode's side, and their
values are figures the deck may cite where the question has a figure (ARCHITECTURE.md §Insights,
report/INSIGHTS.md §Episodes)."""

import copy
import unittest

from fixtures import CHOICE_Q, GEM, GPT, PRICE_Q, WORK_Q
from sentlmon import check
from test_halves import EMPLOYER, NEW_PRICE, NOT_CHOSEN, OLD_PRICE, OLD_PRICE_LOW, REPORT, HalvesCase, day

# Orbit Reason gives the current price on days 7-9 (14-16 October), an episode above the 0% of the
# six runs before, back inside on day 10 (17 October); then again on days 14 and 17 (21 and 24
# October), where Acme Chat gives it too on day 17.
EPISODE = ({7: NEW_PRICE, 8: NEW_PRICE, 9: NEW_PRICE, 14: NEW_PRICE, 17: NEW_PRICE}, {17: NEW_PRICE})


def rows(n, scenario=EPISODE, unjudged=False):
    """Day n's answers: each assistant's price answer from the scenario's (Orbit Reason, Acme Chat)
    days, the old price otherwise. `unjudged`: a second round in which Orbit Reason's price answer is
    not judged."""
    gem, gpt = (s.get(n, OLD_PRICE) for s in scenario)
    out = ([(PRICE_Q, GPT, *gpt), (PRICE_Q, GEM, *gem)] + [(CHOICE_Q, m, *NOT_CHOSEN) for m in (GPT, GEM)]
           + [(WORK_Q, m, *EMPLOYER) for m in (GPT, GEM)])
    if unjudged:
        out += [(q, m, a, None if (q, m) == (PRICE_Q, GEM) else s, u) for q, m, a, s, u in out]
    return out


class EpisodeCloseCase(HalvesCase):

    def build_history(self, scenario=EPISODE, unjudged=False):
        self.adopt_market(rows(1, scenario), rounds=2 if unjudged else 1)
        for n in range(1, 25):
            self.ingest_market(9100 + n, day(n), rows(n, scenario, unjudged))
        self.build(REPORT)

    def price(self):
        [price] = self.period_file(REPORT)["projects"]["market"]["dimensions"]["prezzo"]["questions"].values()
        return price

    def episodes(self, measure):
        return [e for e in self.price()["episodes"] if e["measure"] == measure]

    def material(self):
        return (self.study / f"history/material/{REPORT}.md").read_text(encoding="utf-8")


class MaterialTest(EpisodeCloseCase, unittest.TestCase):

    def test_a_closed_episode_lists_the_later_runs_on_its_side_with_their_values(self):
        self.build_history()
        [share], [mean] = self.episodes("current_share"), self.episodes("mean")
        self.assertEqual((share["first"], share["last"], share["closed"], share["range"]),
                         ("2026-10-14", "2026-10-16", "2026-10-17", [0.0, 0.0]))
        self.assertEqual(share["later"], [{"date": "2026-10-21", "value": 0.5}, {"date": "2026-10-24", "value": 1.0}])
        self.assertEqual(mean["later"], [{"date": "2026-10-21", "value": 4.0}, {"date": "2026-10-24", "value": 5.0}])
        material = self.material()
        self.assertIn("still above that range after the close: 2026-10-21 (50%); 2026-10-24 (100%)", material)
        self.assertIn("still above that range after the close: 2026-10-21 (4,0); 2026-10-24 (5,0)", material)

    def test_a_closed_episode_with_no_later_run_on_its_side_stores_an_empty_list(self):
        self.build_history(({7: NEW_PRICE, 8: NEW_PRICE, 9: NEW_PRICE}, {}))
        [share] = self.episodes("current_share")
        self.assertEqual((share["closed"], share["later"]), ("2026-10-17", []))
        self.assertNotIn("after the close", self.material())

    def test_an_episode_below_its_range_lists_the_later_runs_below_it(self):
        low = {d: OLD_PRICE_LOW for d in (7, 8, 9, 14)}
        self.build_history((low, {}))
        [mean] = self.episodes("mean")
        self.assertEqual((mean["side"], mean["closed"], mean["later"]),
                         ("below", "2026-10-17", [{"date": "2026-10-21", "value": 2.0}]))
        self.assertIn("still below that range after the close: 2026-10-21 (2,0)", self.material())

    def test_an_episode_ended_by_a_switch_carries_no_later_runs(self):
        self.build_history(({7: NEW_PRICE, 8: NEW_PRICE, 9: NEW_PRICE, 10: OLD_PRICE_LOW}, {}))
        [mean] = self.episodes("mean")
        self.assertEqual((mean["closed"], mean["switched"]), (None, "2026-10-17"))
        self.assertNotIn("later", mean)

    def test_two_episodes_on_one_question_each_list_their_own_later_runs(self):
        both = {d: NEW_PRICE for d in (18, 19, 20, 23)}
        self.build_history(({**both, 7: NEW_PRICE, 8: NEW_PRICE, 9: NEW_PRICE}, both))
        first, second = self.episodes("current_share")
        self.assertEqual((first["first"], first["closed"]), ("2026-10-14", "2026-10-17"))
        self.assertEqual([x["date"] for x in first["later"]], ["2026-10-25", "2026-10-26", "2026-10-27", "2026-10-30"])
        self.assertEqual((second["first"], second["last"], second["range"], second["closed"]),
                         ("2026-10-25", "2026-10-27", [0.0, 0.5], "2026-10-28"))
        self.assertEqual(second["later"], [{"date": "2026-10-30", "value": 1.0}])

    def test_a_mean_episode_on_a_question_without_a_figure_lists_dates_only_and_its_values_are_not_citable(self):
        self.build_history(unjudged=True)
        price = self.price()
        self.assertFalse(price["total"]["figure"])
        [mean] = self.episodes("mean")
        self.assertEqual([round(x["value"], 2) for x in mean["later"]], [3.67, 5.0])
        self.assertIn("still above that range after the close: 2026-10-21; 2026-10-24; the close date", self.material())
        self.assertNotIn(3.7, check._allowed([price])[0])


class FiguresTest(EpisodeCloseCase, unittest.TestCase):

    def test_a_later_value_the_by_run_figures_do_not_hold_may_be_cited(self):
        self.build_history()
        price = self.price()
        without = copy.deepcopy(price)
        for e in without["episodes"]:
            e.pop("later", None)
        self.assertNotIn(5.0, check._allowed([without])[0])
        self.assertIn(5.0, check._allowed([price])[0])


if __name__ == "__main__":
    unittest.main()
