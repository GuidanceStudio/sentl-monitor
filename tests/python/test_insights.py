"""The rules of each insight (DEVPLAN M2b), on bare values."""

import unittest

import fixtures  # noqa: F401  (puts the skill's scripts on sys.path)
from sentlmon.insights import classify, episodes, page_of, readings, says_missing

TERMS = {"current": ["2,10 €"], "outdated": ["1,90 €"]}
REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"


class ClassifyTest(unittest.TestCase):

    def test_current_outdated_both_and_neither(self):
        self.assertEqual(classify("Avenello costa 2,10 € al litro.", TERMS), "current_only")
        self.assertEqual(classify("Costa 1,90 € al litro.", TERMS), "outdated_only")
        self.assertEqual(classify("Costava 1,90 €, ora 2,10 €.", TERMS), "both")
        self.assertIsNone(classify("Costa poco.", TERMS))
        self.assertIsNone(classify(None, TERMS))

    def test_a_term_never_matches_inside_a_longer_number(self):
        self.assertIsNone(classify("Costa £2.10 al litro.", {"current": ["£2"], "outdated": []}))
        self.assertIsNone(classify("La confezione costa 12,10 €.", {"current": ["10 €"], "outdated": []}))
        self.assertIsNone(classify("Costa €1,99.", {"current": ["€1"], "outdated": []}))
        self.assertEqual(classify("Costa £2 al litro.", {"current": ["£2"], "outdated": []}), "current_only")

    def test_the_space_between_a_number_and_a_currency_sign_is_optional_on_both_sides(self):
        self.assertEqual(classify("Avenello costa 2,10€ al litro.", TERMS), "current_only")
        self.assertEqual(classify("It costs £ 4.20 a litre.", {"current": ["£4.20"], "outdated": []}), "current_only")

    def test_terms_are_folded_and_matched_on_word_boundaries(self):
        self.assertEqual(classify("Il prezzo è 2,10 €.", TERMS), "current_only")
        self.assertIsNone(classify("La confezione da sei costa 12,10 €.", TERMS))
        accented = {"current": ["Città Verde"], "outdated": []}
        self.assertEqual(classify("lo distribuisce CITTA VERDE", accented), "current_only")


class TopSourcesTest(unittest.TestCase):
    """`top_sources(group, opposite)`: the five domains cited by most answers of a group, each
    with its count and share there and in the opposite group."""

    def top(self, group, opposite):
        from sentlmon.insights import top_sources
        return top_sources(group, opposite)

    def test_the_five_domains_cited_by_most_answers_ties_broken_by_name(self):
        group = ([{"a.example", "b.example", "c.example"}] * 5 + [{"a.example", "d.example", "f.example"}]
                 + [{"d.example", "e.example"}] * 2 + [{"e.example", "f.example", "g.example"}])
        listed = self.top(group, [])
        self.assertEqual([(e["domain"], e["citing"]) for e in listed],
                         [("a.example", 6), ("b.example", 5), ("c.example", 5), ("d.example", 3), ("e.example", 3)])
        self.assertEqual((listed[0]["answers"], listed[0]["share"]), (9, 6 / 9))

    def test_each_domain_carries_its_count_and_share_in_the_opposite_group(self):
        [entry] = self.top([{"a.example"}] * 2, [{"a.example"}, {"z.example"}, {"z.example"}, set()])
        self.assertEqual(entry["other"], {"citing": 1, "answers": 3, "share": 1 / 3})

    def test_a_domain_cited_by_a_single_answer_is_listed(self):
        self.assertEqual([e["domain"] for e in self.top([{"solo.example"}, {"altro.example"}], [])],
                         ["altro.example", "solo.example"])

    def test_answers_citing_nothing_are_in_no_denominator(self):
        [entry] = self.top([{"a.example"}] * 3 + [set()] * 7, [set()] * 4)
        self.assertEqual((entry["answers"], entry["other"]), (3, {"citing": 0, "answers": 0, "share": None}))

    def test_a_group_whose_answers_cite_nothing_gets_no_list(self):
        self.assertEqual(self.top([set(), set()], [{"a.example"}]), [])
        self.assertEqual(self.top([], [{"a.example"}]), [])


class ReadingsTest(unittest.TestCase):

    @staticmethod
    def answer(urls, run=1, model="m", question="q", titles=None):
        return {"run": run, "question": question, "model": model, "answer": "...",
                "sources": [{"url": u, "title": (titles or {}).get(u, ""), "domain": t}
                            for u, t in ((u, (titles or {}).get(u, "x.example")) for u in urls)]}

    def test_three_rounds_with_one_source_list_are_one_reading(self):
        same = ["https://a.example/p", "https://b.example/q"]
        self.assertEqual(readings([self.answer(same) for _ in range(3)]), 1)

    def test_three_different_lists_are_three_readings(self):
        lists = [["https://a.example/p"], ["https://b.example/q"], ["https://b.example/q", "https://a.example/p"]]
        self.assertEqual(readings([self.answer(u) for u in lists]), 3)

    def test_query_strings_and_redirect_urls_do_not_split_a_reading(self):
        first = self.answer(["https://a.example/p?utm=1", REDIRECT + "AAA"], titles={REDIRECT + "AAA": "b.example"})
        second = self.answer(["https://a.example/p?utm=2", REDIRECT + "BBB"], titles={REDIRECT + "BBB": "b.example"})
        self.assertEqual(readings([first, second]), 1)

    def test_answers_without_sources_are_one_reading_each_and_runs_and_models_apart(self):
        bare = [self.answer([]), self.answer([])]
        apart = [self.answer(["https://a.example/p"], run=1), self.answer(["https://a.example/p"], run=2),
                 self.answer(["https://a.example/p"], model="n")]
        self.assertEqual(readings(bare + apart), 5)

    def test_a_page_is_its_host_and_path(self):
        self.assertEqual(page_of({"url": "https://www.a.example/p/?x=1#top", "domain": "a.example"}), "a.example/p")
        self.assertEqual(page_of({"url": REDIRECT + "Z", "title": "b.example", "domain": "b.example"}), "b.example")


class EpisodesTest(unittest.TestCase):
    """`episodes(earlier values, [(date, value)] of this period)`."""

    @staticmethod
    def days(*values):
        return [(f"2026-10-{n:02d}", v) for n, v in enumerate(values, 1)]

    def test_three_consecutive_values_outside_the_range_open_one_closed_by_the_next_inside(self):
        [e] = episodes([0.1] * 5, self.days(0.1, 0.4, 0.45, 0.5, 0.1))
        self.assertEqual((e["first"], e["last"], e["closed"], e["runs"]), ("2026-10-02", "2026-10-04", "2026-10-05", 3))
        self.assertEqual((e["values"], e["range"], e["earlier"], e["side"]), ([0.4, 0.45, 0.5], [0.1, 0.1], 6, "above"))

    def test_two_consecutive_values_open_none(self):
        self.assertEqual(episodes([0.1] * 5, self.days(0.1, 0.4, 0.45, 0.1)), [])

    def test_fewer_than_five_earlier_runs_open_none(self):
        self.assertEqual(episodes([0.1] * 2, self.days(0.1, 0.1, 0.4, 0.4, 0.4)), [])

    def test_an_episode_still_outside_at_the_end_is_open(self):
        [e] = episodes([3.0] * 5, self.days(2.0, 2.0, 2.0))
        self.assertEqual((e["closed"], e["side"]), (None, "below"))

    def test_a_first_period_is_read_against_its_own_earlier_runs(self):
        [e] = episodes([], self.days(0.1, 0.2, 0.1, 0.2, 0.1, 0.4, 0.4, 0.4, 0.2))
        self.assertEqual((e["first"], e["last"], e["range"]), ("2026-10-06", "2026-10-08", [0.1, 0.2]))

    def test_a_jump_to_the_other_side_ends_an_episode_as_a_switch(self):
        [e] = episodes([3.0, 3.4, 3.2, 3.1, 3.3], self.days(3.6, 3.7, 3.8, 2.5))
        self.assertEqual((e["last"], e["closed"], e["switched"]), ("2026-10-03", None, "2026-10-04"))

    def test_runs_without_a_value_are_skipped(self):
        [e] = episodes([0.1] * 5, self.days(0.4, None, 0.4, 0.4))
        self.assertEqual(e["runs"], 3)


class MissingEvidenceTest(unittest.TestCase):

    def test_english_phrases(self):
        for text in ("Lab-test data on oat drinks from avenello.example was not accessible in the provided results.",
                     "Independent sources for Avenello's oat drink are limited in the search results.",
                     "Information on where Avenello buys its oats is quite limited.",
                     "I could not find any reports on the sugar content of the barista edition.",
                     "No independent reviews were found.", "I found no recent reviews of the oat drink.",
                     "There is limited information available.",
                     "Public data on Avenello's oat farms is quite limited compared with its nutrition labels."):
            self.assertTrue(says_missing(text, "en"), text)

    def test_english_product_sentences_are_not_missing_evidence(self):
        for text in ("Avenello offers a limited range of flavours.", "There is a limited summer edition.",
                     "The information about pricing is limited to the one-litre carton.",
                     "Stock is limited in the summer.", "Results are limited to Italy.",
                     "Some customers said they could not find information about the oats' origin on the carton.",
                     "Shoppers cannot read the data on the new carton.",
                     "Customers report that no information was available on the shelf label."):
            self.assertFalse(says_missing(text, "en"), text)

    def test_italian_phrases(self):
        for text in ("Le informazioni sulla provenienza dell'avena di Avenello sono piuttosto limitate.",
                     "I dati sui test di laboratorio della bevanda non sono disponibili nei risultati forniti.",
                     "Le fonti sulla filiera dell'avena sono scarse nei risultati della ricerca.",
                     "Non ho trovato recensioni indipendenti del latte d'avena Avenello.",
                     "Le prove di assaggio indipendenti non sono disponibili nelle fonti consultate.",
                     "Non sono disponibili recensioni indipendenti della versione barista."):
            self.assertTrue(says_missing(text, "it"), text)

    def test_italian_product_sentences_are_not_missing_evidence(self):
        for text in ("Avenello ha una gamma di gusti limitata.", "Le scorte sono limitate.",
                     "La disponibilità nei negozi è limitata.", "Le informazioni nutrizionali sono chiare.",
                     "Alcuni clienti dicono di non aver trovato informazioni sull'origine dell'avena.",
                     "Gli acquirenti non riescono a leggere i dati sulla nuova confezione.",
                     "I clienti segnalano che non sono disponibili informazioni nelle fonti ufficiali."):
            self.assertFalse(says_missing(text, "it"), text)


if __name__ == "__main__":
    unittest.main()
