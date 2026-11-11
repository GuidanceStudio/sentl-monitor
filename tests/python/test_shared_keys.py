"""Two projects of a study may share a dimension key: the comparison keys each dimension by its
project, and the material reads it so (ARCHITECTURE.md §Period metrics)."""

import json
import unittest
from unittest import mock

import fixtures
from fixtures import GEM, GPT, WORK_Q, market_project, project, results, run
from sentlmon.compare import dimension_entries
from test_detect import ADOPTED
from test_halves import REPORT, HalvesCase, day, rows_of

BRAND, MARKET = "Avenello · Con il marchio", "Avenello · Mercato"
PACK = "La confezione di Avenello è riciclabile?"


def pack(scores, run_id):
    return [{"id": run_id * 1000 + n, "model_id": m, "question": PACK, "dimension": "Confezione", "sentiment": "neutral",
             "answer": f"La confezione di Avenello è riciclabile, secondo il produttore ({score}).",
             "judge_score": score, "sources": []} for n, (m, score) in enumerate(zip((GPT, GEM), scores))]


class SharedKeyTest(HalvesCase, unittest.TestCase):
    """The branded project's Confezione is archived when it is adopted, so it gets no theme, and the
    market project, adopted next with its employer dimension named Confezione, takes the key
    `confezione`; Confezione is then restored in the branded project. Both projects measure a
    dimension keyed `confezione`, with a question keyed `confezione-1`. The branded one moves from
    1.25 to 4.75 between the halves."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(fixtures.QUESTION_DIM, {WORK_Q: "Confezione"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.adopt(at=ADOPTED)
        market = market_project()
        market["project"]["dimensions"][2]["name"] = "Confezione"
        self.cli("adopt", "--study", self.study, "--project", self.save("market.json", market),
                 "--run", self.save("market-run.json", results(9000, "2026-09-29T06:00:00Z", rows_of(1))),
                 "--key", "market", check=0, at=ADOPTED)
        restored = project()
        restored["project"]["dimensions"][2]["archived"] = False
        self.detect(restored, "2026-10-02T12:00:00Z")
        self.answer_operator()
        study = self.read("study.json")
        for theme in study["themes"]:
            theme["origins"] = [{"kind": "client_issue", "detail": "Domande al servizio clienti, 2026"}]
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        for n, (d, scores) in enumerate(((1, (1, 2)), (8, (1, 1)), (15, (5, 4)), (24, (5, 5)))):
            self.ingest(run(run_id=9301 + n, started=day(d), extra=pack(scores, 9301 + n)), name=f"b-{n}.json")
        for n in range(1, 25):
            self.ingest_market(9100 + n, day(n), rows_of(n))
        self.build(REPORT)

    def test_the_two_projects_share_the_key(self):
        keys = {p["key"]: [d["key"] for d in p["dimensions"] if not d["archived"]]
                for p in self.read("study.json")["projects"]}
        self.assertEqual(keys, {"brand": ["salute", "prezzo", "confezione"],
                                "market": ["prezzo-2", "scelta", "confezione"]})

    def test_both_projects_dimension_of_the_shared_key_is_compared(self):
        dims = self.comparison()["dimensions"]
        self.assertEqual(sorted(dims), ["brand", "market"])
        self.assertEqual(sorted(dims["brand"]), ["confezione", "prezzo", "salute"])
        self.assertEqual(sorted(dims["market"]), ["confezione", "prezzo-2", "scelta"])
        brand = dims["brand"]["confezione"]
        self.assertEqual((brand["project"], brand["status"]), ("brand", "compared"))
        self.assertEqual((brand["mean"]["previous"], brand["mean"]["now"]), (1.25, 4.75))
        market = dims["market"]["confezione"]
        self.assertEqual((market["project"], market["status"], market["mean"]["previous"]), ("market", "compared", 3.0))

    def test_the_material_states_each_project_s_dimension_with_its_own_question(self):
        material = (self.study / f"history/material/{REPORT}.md").read_text(encoding="utf-8")
        changes = material[material.index("## Changes between the two halves"):]
        sections = {s.split("\n", 1)[0]: s.split("\n### ")[0] for s in changes.split("### Dimension ")[1:]}
        brand, market = sections[f"Confezione ({BRAND}): compared"], sections[f"Confezione ({MARKET}): compared"]
        self.assertIn("mean: second half 4,8, first half 1,3", brand)
        self.assertIn(f"«{PACK}»", brand)
        self.assertNotIn(f"«{PACK}»", market)
        self.assertIn(f"«{WORK_Q}»", market)
        self.assertIn("Salute: compared", sections)
        self.assertIn(f"- Confezione ({BRAND}), «{PACK}», Acme Chat: unfavourable", changes)


class EarlierShapeTest(HalvesCase, unittest.TestCase):
    """A period file written before the comparison keyed dimensions by project holds them by key
    alone, each with its project: `dimension_entries` reads it as it reads the current shape."""

    def test_a_comparison_keyed_by_dimension_alone_reads_as_before(self):
        self.history()
        self.build(REPORT)
        comparison = self.comparison()
        earlier = {**comparison, "dimensions": {k: e for by_key in comparison["dimensions"].values()
                                                for k, e in by_key.items()}}
        self.assertEqual(dimension_entries(earlier), dimension_entries(comparison))
        self.assertEqual(sorted(dimension_entries(comparison)),
                         [("market", "lavoro"), ("market", "prezzo"), ("market", "scelta")])


if __name__ == "__main__":
    unittest.main()
