"""An episode's close date is the first run back inside its range and says nothing about the runs
after it: the material lists the later runs on the episode's side, and `check` refuses a sentence
that says the measure was outside the range only during the episode while such a run exists
(ARCHITECTURE.md §Insights, report/INSIGHTS.md §Episodes)."""

import copy
import json
import re
import unittest

from fixtures import CHOICE_Q, GEM, GPT, PRICE_Q, WORK_Q, models
from sentlmon import check
from sentlmon.i18n import TEXT
from test_halves import EMPLOYER, NEW_PRICE, NOT_CHOSEN, OLD_PRICE, OLD_PRICE_LOW, REPORT, HalvesCase, day

# Orbit Reason gives the current price on days 7-9 (14-16 October), an episode above the 0% of the
# six runs before, back inside on day 10 (17 October); then again on days 14 and 17 (21 and 24
# October), where Acme Chat gives it too on day 17.
EPISODE = ({7: NEW_PRICE, 8: NEW_PRICE, 9: NEW_PRICE, 14: NEW_PRICE, 17: NEW_PRICE}, {17: NEW_PRICE})
ONLY = "Il prezzo attuale è comparso solo dal 14 al 16 ottobre."


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


def episode(first="2026-10-02", last="2026-10-08", closed="2026-10-09", later=("2026-10-11", "2026-10-15")):
    return {"measure": "current_share", "first": first, "last": last, "closed": closed,
            "later": [{"date": d, "value": 0.5} for d in later]}


class EpisodeCloseCase(HalvesCase):

    def build_history(self, scenario=EPISODE, lang="it", unjudged=False):
        self.adopt_market(rows(1, scenario), rounds=2 if unjudged else 1)
        if lang != "it":
            study = self.read("study.json")
            study["report_language"] = lang
            (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        for n in range(1, 25):
            self.ingest_market(9100 + n, day(n), rows(n, scenario, unjudged))
        self.build(REPORT)

    def episodes(self, measure):
        [price] = self.period_file(REPORT)["projects"]["market"]["dimensions"]["prezzo"]["questions"].values()
        return [e for e in price["episodes"] if e["measure"] == measure]

    def material(self):
        return (self.study / f"history/material/{REPORT}.md").read_text(encoding="utf-8")

    def report(self, sentence, dimension="Prezzo", lang="it"):
        """The report with every marker filled and `sentence` in a dimension's findings entry."""
        self.cli("method", "--study", self.study, "--date", REPORT, "--models", self.save("models.json", models()),
                 "--force", check=0)
        path = self.study / "reports" / f"{REPORT}.md"
        marker = TEXT[lang]["finding_body"].format(dimension=dimension)
        text = path.read_text(encoding="utf-8").replace(marker, sentence)
        path.write_text(re.sub(r"\[\[[^\]]*\]\]", "le risposte descrivono Avenello", text), encoding="utf-8")
        return self.cli("check", "--study", self.study, path)

    def only_problems(self, sentence, **kw):
        return [line for line in self.report(sentence, **kw).stdout.splitlines() if "beside the episode" in line]


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
        self.assertIn("beside the episode", "\n".join(self.only_problems("Il prezzo attuale è comparso solo dal 25 al 27 "
                                                                         "ottobre.")))
        self.assertEqual(self.only_problems("Il prezzo attuale è comparso solo dal 25 al 27 ottobre e il 30 ottobre."),
                         [])

    def test_a_mean_episode_on_a_question_without_a_figure_lists_dates_only_and_its_values_are_not_citable(self):
        self.build_history(unjudged=True)
        [price] = self.period_file(REPORT)["projects"]["market"]["dimensions"]["prezzo"]["questions"].values()
        self.assertFalse(price["total"]["figure"])
        [mean] = self.episodes("mean")
        self.assertEqual([round(x["value"], 2) for x in mean["later"]], [3.67, 5.0])
        self.assertIn("still above that range after the close: 2026-10-21; 2026-10-24; the close date", self.material())
        refused = self.report("Il 21 ottobre il punteggio medio è tornato a 3,7.")
        self.assertIn("figure 3,7 is not in the period's figures", refused.stdout)


class CheckTest(EpisodeCloseCase, unittest.TestCase):

    def test_only_and_its_synonyms_before_the_episode_s_span_are_refused_when_a_later_run_lies_on_its_side(self):
        self.build_history()
        for word in ("solo", "soltanto", "solamente", "unicamente", "esclusivamente"):
            with self.subTest(word=word):
                [problem] = self.only_problems(f"Il prezzo attuale è comparso {word} dal 14 al 16 ottobre.")
                self.assertIn(f"«{word}»", problem)
                self.assertIn("21 ottobre 2026, 24 ottobre 2026", problem)
        self.assertEqual(self.report("Il prezzo attuale è comparso dal 14 al 16 ottobre.").returncode, 0)

    def test_a_sentence_must_name_every_later_run_to_say_only(self):
        self.build_history()
        self.assertTrue(self.only_problems("Il prezzo attuale è comparso solo dal 14 al 16 ottobre; il 24 ottobre Acme "
                                           "Chat non ha risposto."))
        self.assertTrue(self.only_problems("Il prezzo attuale è comparso solo dal 14 al 16 ottobre e di nuovo il 21 "
                                           "ottobre."))
        self.assertEqual(self.only_problems("Il prezzo attuale è comparso solo dal 14 al 16 ottobre, poi di nuovo il "
                                            "21 ottobre e il 24 ottobre."), [])

    def test_only_outside_the_episode_s_clause_or_inside_a_quote_is_accepted(self):
        self.build_history()
        for sentence in ("Dal 14 al 16 ottobre il prezzo attuale era nel 50% delle risposte, e solo Orbit Reason lo dava.",
                         "Il 14 ottobre solo 3 risposte su 6 citavano la fonte ufficiale.",
                         "Il 16 ottobre Orbit Reason scriveva «disponibile solo online»."):
            with self.subTest(sentence=sentence):
                self.assertEqual(self.only_problems(sentence), [])

    def test_a_finding_is_read_against_its_own_dimension_s_episodes(self):
        self.build_history()
        self.assertEqual(self.only_problems(ONLY, dimension="Scelta"), [])
        self.assertEqual(self.only_problems("Il 14 ottobre solo 3 risposte su 6 citavano la fonte ufficiale.",
                                            dimension="Scelta"), [])

    def test_a_hard_wrapped_sentence_is_read_whole(self):
        self.build_history()
        self.assertTrue(self.only_problems("Il prezzo attuale è comparso solo\ndal 14 al 16 ottobre."))

    def test_an_english_report_refuses_only_beside_the_episode_s_dates(self):
        self.build_history(lang="en")
        for sentence in ("The current price appeared only from 14 to 16 October.",
                         "The current price appeared only on October 14.",
                         "The current price was given just until 17 October."):
            with self.subTest(sentence=sentence):
                self.assertTrue(self.only_problems(sentence, lang="en"))
        self.assertEqual(self.only_problems("From 14 to 16 October the current price was in 50% of the answers, and "
                                            "only Orbit Reason gave it.", lang="en"), [])

    def test_a_later_value_the_by_run_figures_do_not_hold_may_be_cited(self):
        self.build_history()
        [price] = self.period_file(REPORT)["projects"]["market"]["dimensions"]["prezzo"]["questions"].values()
        without = copy.deepcopy(price)
        for e in without["episodes"]:
            e.pop("later", None)
        self.assertNotIn(5.0, check._allowed([without])[0])
        self.assertIn(5.0, check._allowed([price])[0])
        proc = self.report("Dal 14 al 16 ottobre il prezzo attuale è comparso; il 24 ottobre il punteggio medio era 5,0.")
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_a_period_built_before_episodes_recorded_their_later_runs_is_refused(self):
        self.build_history()
        path = self.study / "history" / "periods" / f"{REPORT}.json"
        period = json.loads(path.read_text(encoding="utf-8"))
        [price] = period["projects"]["market"]["dimensions"]["prezzo"]["questions"].values()
        for e in price["episodes"]:
            e.pop("later", None)
        path.write_text(json.dumps(period, ensure_ascii=False), encoding="utf-8")
        refused = self.report(ONLY)
        self.assertEqual(refused.returncode, 2)
        self.assertIn(f"period --date {REPORT}", refused.stderr)


class SpanTest(unittest.TestCase):
    """The forms in which a report writes an episode's span or its close: the rule reads them in the
    clause after the word, and nothing else."""

    def problems(self, sentence, lang="it"):
        return check._only_beside_episodes(sentence, [episode()], lang)

    def test_the_spans_and_dates_a_report_writes_are_read(self):
        for sentence in ("Il prezzo era alto solo dal 2 all'8 ottobre.", "Il prezzo era alto solo tra il 2 e l'8.",
                         "Il prezzo era alto solo fino al 9 ottobre.", "Il prezzo era alto solo il 2 ottobre."):
            with self.subTest(sentence=sentence):
                self.assertTrue(self.problems(sentence))
        for sentence in ("The price was high only from 2 to 8 October.", "The price was high only 2–8 October.",
                         "The price was high only on October 2.", "The price was high only until 9 October.",
                         "The price was high only until October 9."):
            with self.subTest(sentence=sentence):
                self.assertTrue(self.problems(sentence, "en"))

    def test_other_dates_and_other_clauses_are_not_read(self):
        for sentence in ("Il prezzo era alto solo il 2/10.", "Il prezzo era alto solo il 2 ott.",
                         "Solo 3 risposte su 6 lo dicevano, dal 2 all'8 ottobre.",
                         "Orbit Reason scriveva «solo dal 2 all'8 ottobre».",
                         "Il prezzo era alto solo dal 2 all'8 ottobre, poi l'11 ottobre e il 15 ottobre."):
            with self.subTest(sentence=sentence):
                self.assertEqual(self.problems(sentence), [])


if __name__ == "__main__":
    unittest.main()
