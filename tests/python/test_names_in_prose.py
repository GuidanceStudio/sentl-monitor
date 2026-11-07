"""A name counts where the reader of an answer reads it: in its text, not in a link's address (DEVPLAN M24)."""

import json
import re
import unittest

from fixtures import AVORIA, models
from sentlmon import deck
from sentlmon.common import prose
from sentlmon.period import Reader
from test_deck import DATE, DeckCase, fake_pdf
from test_deck_second import LATER, SecondCase
from test_insights_period import OCT, InsightCase, rows

STUDY = {"subject": {"aliases": ["Avenello"], "owned_domains": ["avenello.example"]}, "foils": [AVORIA]}
ONLY_IN_LINK = "La migliore è Avoria. Fonte: [avenello.example](https://guida.example/latte)."


def age(study, date):
    """The period file of `date` as a period built before names were read in the text: no record of the rule."""
    path = study / "history" / "periods" / f"{date}.json"
    period = json.loads(path.read_text(encoding="utf-8"))
    del period["names_counted_in"]
    path.write_text(json.dumps(period, ensure_ascii=False), encoding="utf-8")


class ReaderTest(unittest.TestCase):

    reader = Reader(STUDY)

    def test_a_name_in_the_text_counts(self):
        self.assertEqual(self.reader.position("La migliore è Avenello."), 1)

    def test_a_name_as_a_links_label_counts(self):
        self.assertEqual(self.reader.position("Si trova da [Avenello](https://shop.example/bevande)."), 1)

    def test_a_link_whose_label_is_a_domain_or_an_address_does_not(self):
        for label in ("avenello.example", "www.avenello.example", "https://avenello.example/prezzi", "Avenello.example/prezzi"):
            with self.subTest(label):
                self.assertIsNone(self.reader.position(f"Fonte: [{label}](https://avenello.example/prezzi)."))

    def test_a_name_in_a_links_target_only_does_not(self):
        self.assertIsNone(self.reader.position("Una guida ([prezzi al litro](https://avenello.example/prezzi))."))

    def test_a_name_in_a_bare_address_does_not(self):
        for text in ("Fonte: https://avenello.example/prezzi", "Fonte: www.avenello.example/prezzi.",
                     "Fonti: <https://avenello.example/prezzi>"):
            with self.subTest(text):
                self.assertIsNone(self.reader.position(text))

    def test_a_domain_written_in_a_sentence_counts(self):
        self.assertEqual(self.reader.position("I prezzi sono su avenello.example, aggiornati a ottobre."), 1)

    def test_a_foil_follows_the_same_rule(self):
        self.assertEqual(self.reader.foils_named("Avoria è la più venduta."), ["Avoria"])
        self.assertEqual(self.reader.foils_named("Si trova da [Avoria](https://shop.example/x)."), ["Avoria"])
        self.assertEqual(self.reader.foils_named("Vedi [avoria.example](https://avoria.example/confronto)."), [])
        self.assertEqual(self.reader.foils_named("Vedi [qui](https://avoria.example/confronto) e https://avoria.example/x."), [])

    def test_a_foil_only_in_a_link_does_not_come_before_the_subject(self):
        self.assertEqual(self.reader.position("Secondo [avoria.example](https://avoria.example/c), Avenello costa meno."), 1)

    def test_the_reader_of_an_earlier_period_reads_links_too(self):
        earlier = Reader(STUDY, prose_only=False)
        self.assertEqual(earlier.position("Fonte: [avenello.example](https://avenello.example/prezzi)."), 1)
        self.assertEqual(Reader.of(STUDY, {}).position("Fonte: https://avenello.example/prezzi"), 1)
        self.assertIsNone(Reader.of(STUDY, {"names_counted_in": "prose"}).position("Fonte: https://avenello.example/prezzi"))


class ProseTest(unittest.TestCase):

    def test_a_link_keeps_its_label_and_loses_its_target(self):
        self.assertEqual(prose('Vedi [la guida](https://wiki.example/Avenello_(azienda) "Avenello") qui.'), "Vedi la guida qui.")

    def test_a_reference_link_and_its_definition(self):
        text = "Vedi [la guida][1] e [avenello.example][2].\n\n[1]: https://guida.example/avenello \"Avenello\"\n[2]: <https://avenello.example>"
        self.assertEqual(prose(text).split(), ["Vedi", "la", "guida", "e", "."])

    def test_text_with_no_link_is_unchanged(self):
        text = "Avenello costa 2,10 € al litro (prezzo di listino); vedi avenello.example."
        self.assertEqual(prose(text), text)
        self.assertEqual(prose(None), "")


class PeriodTest(InsightCase, unittest.TestCase):

    def test_presence_reads_the_text_and_the_period_records_the_rule(self):
        self.ingest_market(9101, OCT[0], rows(choice=((ONLY_IN_LINK, 3, ["https://guida.example/latte"]),
                                                      ("Dipende dai gusti: https://avenello.example/bevande", 3, []))))
        self.build("2026-10-31")
        period = self.period_file("2026-10-31")
        self.assertEqual(period["names_counted_in"], "prose")
        total = self.question("2026-10-31", "scelta", "Qual è la migliore bevanda all'avena da comprare?")["total"]
        self.assertEqual((total["presence"]["named"], total["presence"]["given"]), (0, 2))
        self.assertEqual(total["foils"], {"Avoria": 1})


class EarlierRuleDeckTest(InsightCase, unittest.TestCase):
    """A deck drawn from a period built before the rule counts names as that period did."""

    def naming(self):
        folder, _, study, period, _ = deck.load(self.study, "2026-10-31")
        return deck.build_model(folder, study, period, {})["blocks"]["reach"]["sources"]["third_naming"]["guida.example"]

    def test_the_sites_naming_count_follows_the_periods_rule(self):
        self.ingest_market(9101, OCT[0], rows(choice=((ONLY_IN_LINK, 3, ["https://guida.example/latte"]),
                                                      ("Dipende dai gusti.", 3, []))))
        self.build("2026-10-31")
        self.assertEqual(self.naming(), 0)
        age(self.study, "2026-10-31")
        self.assertEqual(self.naming(), 1)


class EarlierPeriodTest(DeckCase, unittest.TestCase):
    """A period on file from before the rule is read as it is, never refused nor asked to be built again."""

    def setUp(self):
        super().setUp()
        age(self.study, DATE)

    def test_the_report_is_written_and_passes_check(self):
        self.cli("method", "--study", self.study, "--date", DATE, "--models", self.save("models.json", models()), check=0)
        path = self.study / "reports" / f"{DATE}.md"
        path.write_text(re.sub(r"\[\[[^\]]*\]\]", "le risposte descrivono Avenello", path.read_text(encoding="utf-8")),
                        encoding="utf-8")
        self.cli("check", "--study", self.study, path, check=0)

    def test_the_deck_passes_check_and_prints(self):
        self.cli("deck", "--study", self.study, "--date", DATE, check=0)
        self.save_doc(self.filled())
        self.cli("check", "--study", self.study, self.path, check=0)
        deck.render(self.study, DATE, printer=fake_pdf(deck.page_of(self.study, DATE)[1]))
        self.assertTrue((self.study / "reports" / f"{DATE}.deck.pdf").exists())
        self.assertNotIn("names_counted_in", json.loads((self.study / "history" / "periods" / f"{DATE}.json").read_text()))


class EarlierPeriodSecondTest(SecondCase):
    """A second edition whose earlier deck stands on a period from before the rule."""

    old = True

    def test_the_second_edition_passes_check(self):
        self.assertEqual(self.problems(self.second()), "")

    def test_the_new_period_records_the_rule_and_tells_the_operator(self):
        self.assertEqual(self.period_file(LATER)["names_counted_in"], "prose")
        self.assertIn(f"The period of {DATE} counted the names in the whole answer", self.built.stdout)


class SameRuleSecondTest(SecondCase):

    def test_two_periods_on_the_same_rule_say_nothing_of_it(self):
        self.assertNotIn("counted the names", self.built.stdout)


if __name__ == "__main__":
    unittest.main()
