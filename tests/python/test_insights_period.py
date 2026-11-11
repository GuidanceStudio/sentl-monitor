"""The insights of DEVPLAN M2b in the period file and the material."""

import datetime as dt
import json
import unittest

from fixtures import (CHOICE_Q, GEM, GPT, NEW, PRICE_Q, WORK_Q, StudyCase, market_project, results, weekly)

OCT = weekly("2026-10-05", 4)
OUTDATED = ("Avenello costa 1,90 € al litro.", 2, ["https://prezzi.example/avena"])
CURRENT = ("Avenello costa 2,10 € al litro.", 5, ["https://avenello.example/prezzi"])
NO_DATA = "Le informazioni sullo stabilimento di Avenello sono piuttosto limitate; i clienti ne apprezzano le bevande."


def rows(price=None, choice=None, work=None):
    """Six answers: per question, (GPT answer, GEM answer), each an (answer, score, urls) triple."""
    price = price or (OUTDATED, CURRENT)
    choice = choice or (("La migliore è Avoria.", 3, ["https://avoria.example/confronto"]),
                        ("Dipende dai gusti.", 3, []))
    work = work or (("Avenello è un buon datore di lavoro.", 4, []), ("Si lavora bene da Avenello.", 4, []))
    return [(q, m, *answer) for q, pair in ((PRICE_Q, price), (CHOICE_Q, choice), (WORK_Q, work))
            for m, answer in zip((GPT, GEM), pair)]


class InsightCase(StudyCase):

    def setUp(self):
        super().setUp()
        self.adopt_market(rows())

    def question(self, date, dim, q_text):
        period = self.period_file(date)
        key = next(q["key"] for d in period["asked"]["market"] for q in d["questions"] if q["text"] == q_text)
        return period["projects"]["market"]["dimensions"][dim]["questions"][key]

    def material(self, date="2026-10-31"):
        return (self.study / f"history/material/{date}.md").read_text(encoding="utf-8")


class FactCurrencyTest(InsightCase, unittest.TestCase):

    def test_current_outdated_and_both_per_model_and_per_run(self):
        self.ingest_market(9101, OCT[0], rows())
        self.ingest_market(9102, OCT[1], rows(price=(
            ("AVENELLO costa 1,90 €; la confezione da sei costa 12,10 €.", 2, ["https://prezzi.example/avena"]),
            ("Costava 1,90 €, ora costa 2,10 € al litro.", 4, ["https://avenello.example/prezzi"]))))
        self.build("2026-10-31")
        facts = self.question("2026-10-31", "prezzo", PRICE_Q)["facts"]
        self.assertEqual(facts["terms"], {"current": ["2,10 €"], "outdated": ["1,90 €"]})
        self.assertEqual(facts["total"], {"given": 4, "stating": 4, "current_only": 1, "outdated_only": 2,
                                          "both": 1, "current_share": 0.5})
        self.assertEqual((facts["by_model"][GPT]["outdated_only"], facts["by_model"][GEM]["both"]), (2, 1))
        self.assertEqual([(r["run_id"], r["date"], r["total"]["current_only"], r["total"]["both"]) for r in facts["runs"]],
                         [(9101, "2026-10-05", 1, 0), (9102, "2026-10-12", 0, 1)])
        self.assertNotIn("facts", self.question("2026-10-31", "scelta", CHOICE_Q))
        material = self.material()
        self.assertIn("##### Fact currency", material)
        self.assertIn("outdated only 2 of 4 (50%)", material)


class PresenceByRunTest(InsightCase, unittest.TestCase):

    def test_an_unbranded_question_shows_its_presence_in_each_run(self):
        named = (("La migliore è Avenello.", 4, []), ("Avenello, senza dubbio.", 4, []))
        for n, start in enumerate(OCT):
            self.ingest_market(9101 + n, start, rows(choice=named) if n >= 2 else rows())
        self.build("2026-10-31")
        runs = self.question("2026-10-31", "scelta", CHOICE_Q)["presence_runs"]
        self.assertEqual([(r["date"], r["named"], r["given"]) for r in runs],
                         [("2026-10-05", 0, 2), ("2026-10-12", 0, 2), ("2026-10-19", 2, 2), ("2026-10-26", 2, 2)])
        self.assertNotIn("presence_runs", self.question("2026-10-31", "prezzo", PRICE_Q))
        self.assertIn("##### Presence by run", self.material())


class AuthorsTest(InsightCase, unittest.TestCase):

    def test_cited_domains_are_owned_a_foil_s_or_third_party(self):
        self.ingest_market(9101, OCT[0], rows(choice=(
            ("La migliore è Avoria.", 3, ["https://avoria.example/confronto?ref=1", "https://guida.example/latte"]),
            ("Avoria ha le offerte migliori.", 3, ["https://shop.avoria.example/offerte"]))))
        self.ingest_market(9102, OCT[1], rows(choice=(
            ("La migliore è Avoria.", 3, ["https://avoria.example/confronto"]),
            ("Avenello è buona.", 4, ["https://avenello.example/bevande"]))))
        self.build("2026-10-31")
        authors = self.period_file("2026-10-31")["projects"]["market"]["dimensions"]["scelta"]["total"]["authors"]
        self.assertEqual({k: authors[k] for k in ("owned", "foil", "third", "with_sources")},
                         {"owned": 1, "foil": 3, "third": 1, "with_sources": 4})
        self.assertEqual(authors["foil_pages"], [{"page": "avoria.example/confronto", "foil": "Avoria", "answers": 2},
                                                 {"page": "shop.avoria.example/offerte", "foil": "Avoria", "answers": 1}])
        material = self.material()
        self.assertIn("##### Who wrote the sources", material)
        self.assertIn("avoria.example/confronto (Avoria, 2 answers)", material)

    def test_without_foil_domains_the_section_is_left_out(self):
        self._tmp.cleanup()
        StudyCase.setUp(self)
        self.adopt_market(rows(), foils=())
        self.ingest_market(9101, OCT[0], rows())
        self.build("2026-10-31")
        self.assertNotIn("##### Who wrote the sources", self.material())


class MissingEvidenceTest(InsightCase, unittest.TestCase):

    def test_a_pair_s_mean_with_and_without_the_answers_that_found_no_source(self):
        missing = (NO_DATA, 3, [])
        for n, start in enumerate(OCT):
            work = (missing, ("Si lavora bene da Avenello.", 4, [])) if n in (1, 2) else None
            self.ingest_market(9101 + n, start, rows(work=work))
        self.build("2026-10-31")
        found = self.question("2026-10-31", "lavoro", WORK_Q)["missing"]
        self.assertEqual(list(found), [GPT])
        self.assertEqual(found[GPT], {"answers": 2, "given": 4, "judged": 4, "mean": 3.5, "mean_without": 4.0})
        self.assertIn("##### Missing evidence", self.material())


class ReadingsTest(InsightCase, unittest.TestCase):

    def test_rounds_citing_one_source_list_are_one_reading(self):
        self._tmp.cleanup()
        StudyCase.setUp(self)
        self.adopt_market(rows() * 3, rounds=3)
        self.ingest_market(9101, OCT[0], rows() * 3)
        self.build("2026-10-31")
        cell = self.question("2026-10-31", "prezzo", PRICE_Q)["by_model"][GPT]
        self.assertEqual((cell["received"], cell["readings"]), (3, 1))
        self.assertIn("2 readings of 6 answers", self.material())


class GroupSourcesTest(InsightCase, unittest.TestCase):

    def test_each_group_lists_the_domains_its_answers_cite_most_with_the_opposite_group(self):
        price = (("Avenello costa 1,90 € al litro.", 2, ["https://prezzi.example/avena", "https://sport.example/avena"]),
                 CURRENT)
        for n, start in enumerate(weekly("2026-10-01", 3)):
            self.ingest_market(9101 + n, start, rows(price=price))
        self.build("2026-10-31")
        groups = self.question("2026-10-31", "prezzo", PRICE_Q)["group_sources"]
        self.assertEqual(set(groups), {"outdated", "current", "low", "high"})
        self.assertEqual([(e["domain"], e["citing"], e["answers"]) for e in groups["outdated"]],
                         [("prezzi.example", 3, 3), ("sport.example", 3, 3)])
        self.assertEqual(groups["outdated"][0]["other"], {"citing": 0, "answers": 3, "share": 0.0})
        self.assertEqual([e["domain"] for e in groups["current"]], ["avenello.example"])
        self.assertNotIn("group_sources", self.question("2026-10-31", "scelta", CHOICE_Q))
        material = self.material()
        self.assertIn("##### Sources behind the fact", material)
        self.assertIn("- prezzi.example: 3 of 3 (100%); in the answers stating a current term: 0 of 3 (0%)", material)
        self.assertIn("##### Sources behind the score", material)


class GroupPairTest(InsightCase, unittest.TestCase):

    def test_a_pair_of_groups_is_listed_only_when_both_groups_cite_a_source(self):
        work = (("Avenello è un buon datore di lavoro.", 4, ["https://lavoro.example/avenello"]),
                ("Si lavora bene da Avenello.", 5, ["https://lavoro.example/avenello"]))
        for n, start in enumerate(weekly("2026-10-01", 3)):
            self.ingest_market(9101 + n, start, rows(work=work))
        self.build("2026-10-31")
        self.assertNotIn("group_sources", self.question("2026-10-31", "lavoro", WORK_Q))
        material = self.material()
        work_part = material[material.index(f"#### Question: {WORK_Q}"):]
        self.assertNotIn("##### Sources behind the score", work_part)


class PresenceChangeTest(InsightCase, unittest.TestCase):

    def test_a_presence_change_lists_the_domains_new_and_lost_in_the_answers_naming_the_subject(self):
        september = (("Avenello è buona.", 4, ["https://vecchio.example/classifica"]),
                     ("Dipende dai gusti.", 3, ["https://guida.example/latte"]))
        october = (("La migliore è Avenello.", 4, ["https://classifica.example/2026", "https://guida.example/latte"]),
                   ("Avenello, senza dubbio.", 4, ["https://avenello.example/bevande"]))
        for n, start in enumerate(weekly("2026-09-07", 4)):
            self.ingest_market(9001 + n, start, rows(choice=september))
        self.publish("2026-09-30")
        for n, start in enumerate(OCT):
            self.ingest_market(9101 + n, start, rows(choice=october))
        self.build("2026-10-31")
        c = self.period_file("2026-10-31")["comparison"]
        self.assertTrue(c["dimensions"]["market"]["scelta"]["presence"]["changed"])
        [entry] = c["presence_sources"]
        self.assertEqual(entry["dimension"], "scelta")
        self.assertEqual(entry["new"], [{"domain": "avenello.example", "answers": 4},
                                        {"domain": "classifica.example", "answers": 4}])
        self.assertEqual(entry["lost"], [{"domain": "vecchio.example", "answers": 4}])
        self.assertIn("### Presence changes", self.material())


class AdoptAnswersTest(StudyCase, unittest.TestCase):

    def test_adopt_asks_for_foil_domains_and_fact_terms(self):
        proc = self.cli("adopt", "--study", self.study, "--project", self.save("p.json", market_project()),
                        "--run", self.save("r.json", results(9000, "2026-08-31T06:00:00Z", rows())),
                        "--key", "market", check=0)
        self.assertIn("foils[].domains", proc.stdout)
        self.assertIn("facts", proc.stdout)
        self.assertIn("current", proc.stdout)

    def test_the_operator_s_terms_and_domains_survive_a_detected_edit_and_sentl_s_texts_stay(self):
        self.adopt_market(rows())
        edited = market_project()
        edited["project"]["dimensions"][0]["questions"][0]["question"] = "Quanto costa al litro il latte d'avena Avenello?"
        self.cli("detect", "--study", self.study, "--project", "market", "--saved", self.save("now.json", edited),
                 check=0, at="2026-10-31T12:00:00Z")
        study = self.read("study.json")
        price = study["projects"][0]["dimensions"][0]["questions"][0]
        self.assertEqual(price["text"], "Quanto costa al litro il latte d'avena Avenello?")
        self.assertEqual((price["facts"][0]["current"], price["facts"][0]["outdated"]), (["2,10 €"], ["1,90 €"]))
        self.assertEqual(study["foils"][0]["domains"], ["avoria.example"])

    def test_misshapen_terms_or_domains_are_listed_before_a_report(self):
        self.adopt_market(rows())
        study = self.read("study.json")
        study["foils"][0]["domains"] = "avoria.example"
        study["projects"][0]["dimensions"][0]["questions"][0]["facts"][0]["current"] = "2,10 €"
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.ingest_market(9101, OCT[0], rows())
        self.build("2026-10-31")
        proc = self.cli("deck", "--study", self.study, "--date", "2026-10-31", check=2)
        self.assertIn("foils[avoria].domains", proc.stdout + proc.stderr)
        self.assertIn("facts", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()


def daily(first, count):
    day = dt.date.fromisoformat(first)
    return [f"{day + dt.timedelta(days=n)}T06:00:00Z" for n in range(count)]


class EpisodeComparabilityTest(StudyCase, unittest.TestCase):
    """Episodes compare runs on the same assistants and the same criteria."""

    def test_an_assistant_added_inside_the_period_opens_no_episode(self):
        self.adopt_market(rows(), at="2026-11-01T00:00:00Z")
        harsh = [(q, NEW, "Avenello non convince.", 1, []) for q in (PRICE_Q, CHOICE_Q, WORK_Q)]
        for n, start in enumerate(daily("2026-10-01", 10)):
            self.ingest_market(9101 + n, start, rows() + (harsh if n >= 7 else []))
        self.build("2026-10-31")
        self.assertNotIn("episodes", self.question_scope("2026-10-31", "lavoro"))

    def test_runs_before_a_rubric_edit_are_not_the_range_of_an_episode(self):
        self.adopt_market(rows(), report_every="weekly")
        for n, start in enumerate(daily("2026-10-01", 7)):
            self.ingest_market(9101 + n, start, rows())
        self.publish("2026-10-07")
        changed = market_project()
        changed["project"]["dimensions"][2]["questions"][0]["grading_rubric"]["5"] = "Cita i dati dello stabilimento"
        self.cli("detect", "--study", self.study, "--project", "market", "--saved", self.save("now.json", changed),
                 check=0, at="2026-10-07T12:00:00Z")
        better = (("Avenello è un ottimo datore di lavoro.", 5, []), ("Si lavora molto bene da Avenello.", 5, []))
        for n, start in enumerate(daily("2026-10-08", 7)):
            self.ingest_market(9201 + n, start, rows(work=better))
        self.build("2026-10-14")
        self.assertNotIn("episodes", self.question_scope("2026-10-14", "lavoro"))

    def question_scope(self, date, dim):
        return next(iter(self.period_file(date)["projects"]["market"]["dimensions"][dim]["questions"].values()))


class NoFigureTest(unittest.TestCase):
    """A question without a figure has no mean to cite, so its insights print none."""

    def test_a_question_without_a_figure_shows_its_counts_and_no_mean(self):
        from sentlmon.period import _question_lines
        scope = {"total": {"figure": False},
                 "missing": {GPT: {"answers": 2, "given": 4, "judged": 2, "mean": 3.5, "mean_without": 4.0}},
                 "episodes": [{"measure": "mean", "first": "2026-10-09", "last": "2026-10-11", "runs": 3,
                               "values": [3.5, 3.5, 3.5], "range": [2.0, 2.0], "earlier": 8, "side": "above",
                               "closed": "2026-10-12", "switched": None}]}
        text = "\n".join(_question_lines(scope, lambda m: m, "it"))
        self.assertIn("2 of 4 answers", text)
        self.assertIn("from 2026-10-09 to 2026-10-11", text)
        for figure in ("3,5", "4,0", "2,0"):
            self.assertNotIn(figure, text)


class FoldOnceTest(StudyCase, unittest.TestCase):
    """Each answer is folded once per period, however many insights read it."""

    def test_fold_calls_grow_with_the_answers_not_with_the_insights(self):
        from unittest import mock
        import sentlmon.common as common
        self.adopt_market(rows(), report_every="monthly")
        runs = daily("2026-10-01", 10)
        for n, start in enumerate(runs):
            varied = [(q, m, f"{a} Rilevazione {n}.", sc, u) for q, m, a, sc, u in rows()]
            self.ingest_market(9101 + n, start, varied)
        calls = []
        real = common.fold
        with mock.patch.object(common, "fold", lambda text: calls.append(1) or real(text)):
            self.build("2026-10-31")
        answers = len(runs) * len(rows())
        self.assertLessEqual(len(calls), 2 * answers + 50, f"{len(calls)} fold calls for {answers} answers")
