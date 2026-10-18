"""A fictional history built to contain every insight of DEVPLAN M2b (done when): two weekly
periods of daily runs, three rounds each. The second period's material lists every insight
with its figures, and a report that states them passes `check`."""

import datetime as dt
import re
import unittest

from fixtures import CHOICE_Q, GEM, GPT, PRICE_Q, WORK_Q, StudyCase, models, results
from sentlmon.common import fmt_decimal, fmt_percent
from test_insights_period import NO_REVIEWS

OUTDATED = ("Un litro di Avenello costa 1,90 €.", 2, ["https://prezzi.example/avena", "https://recensioni.example/avena"])
CURRENT = ("Un litro di Avenello costa 2,10 €.", 5, ["https://avenello.example/prezzi"])
UNNAMED = ("La migliore è Avoria, secondo il confronto.", 3, ["https://avoria.example/confronto"])
NAMED = ("La migliore è Avenello, prima di Avoria.", 4, ["https://classifica.example/2026", "https://avoria.example/confronto"])
GOOD_JOB = ("Avenello è un buon datore di lavoro, secondo i dipendenti.", 4, ["https://lavoro.example/avenello"])
NO_JOB = (NO_REVIEWS, 3, ["https://clienti.example/avenello"])


def day(n):
    return f"{dt.date(2026, 10, 1) + dt.timedelta(days=n - 1)}T06:00:00Z"


def rows_of(n):
    """Day n's answers. From day 8: the current price on days 9-11, Avenello named on days 13-14,
    and Acme Chat finding no lab tests from day 11."""
    gem_price = CURRENT if n in (9, 10, 11) else OUTDATED
    choice = NAMED if n in (13, 14) else UNNAMED
    gpt_work = NO_JOB if n >= 11 else GOOD_JOB
    answers = [(PRICE_Q, GPT, OUTDATED), (PRICE_Q, GEM, gem_price), (CHOICE_Q, GPT, choice), (CHOICE_Q, GEM, choice),
               (WORK_Q, GPT, gpt_work), (WORK_Q, GEM, GOOD_JOB)]
    return [(q, m, *a) for q, m, a in answers] * 3


def it(value):
    return fmt_decimal(value, "it")


class InsightHistoryTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt_market(rows_of(1), rounds=3, report_every="weekly")
        for n in range(1, 15):
            self.ingest_market(9100 + n, day(n), rows_of(n))
        self.publish("2026-10-07")
        self.build("2026-10-14")
        self.period = self.period_file("2026-10-14")
        self.material = (self.study / "history/material/2026-10-14.md").read_text(encoding="utf-8")

    def scope(self, dim):
        block = self.period["projects"]["market"]["dimensions"][dim]
        return block, next(iter(block["questions"].values()))

    def test_the_material_lists_every_insight(self):
        for heading in ("##### Fact currency", "##### Sources behind the fact", "##### Sources behind the score",
                        "##### Episodes", "##### Presence by run", "##### Missing evidence",
                        "##### Who wrote the sources", "### Presence changes"):
            self.assertIn(heading, self.material)
        self.assertRegex(self.material, r"\d+ readings of \d+ answers")

    def test_a_report_that_states_the_insights_passes_check(self):
        _, price = self.scope("prezzo")
        facts = price["facts"]["total"]
        current_episode = next(e for e in price["episodes"] if e["measure"] == "current_share")
        mean_episode = next(e for e in price["episodes"] if e["measure"] == "mean")
        old_source = next(e for e in price["group_sources"]["outdated"] if e["domain"] == "prezzi.example")
        choice_block, choice = self.scope("scelta")
        named_run = choice["presence_runs"][-1]
        authors = choice_block["total"]["authors"]
        readings = choice["total"]
        _, work = self.scope("lavoro")
        missing = work["missing"][GPT]
        work_episode = work["episodes"][0]
        presence = self.period["comparison"]["dimensions"]["market"]["scelta"]["questions"][next(iter(choice_block["questions"]))]["presence"]
        [moved] = self.period["comparison"]["presence_sources"]

        findings = {
            "Prezzo": (f"In {facts['outdated_only']} su {facts['stating']} risposte che citano un prezzo, il prezzo è "
                       f"quello dell'anno scorso ({fmt_percent(facts['outdated_only'] / facts['stating'])}). Dal 9 all'11 "
                       f"ottobre le risposte con il prezzo attuale sono salite al {fmt_percent(current_episode['values'][0])}, "
                       f"e il punteggio medio a {it(mean_episode['values'][0])}. Le risposte con il prezzo vecchio citano "
                       f"prezzi.example in {old_source['citing']} su {old_source['answers']} risposte "
                       f"({fmt_percent(old_source['share'])}), quelle con il prezzo attuale in "
                       f"{old_source['other']['citing']} su {old_source['other']['answers']} risposte "
                       f"({fmt_percent(old_source['other']['share'])})."),
            "Scelta": (f"Avenello è nominato in {named_run['named']} su {named_run['given']} risposte del 14 ottobre. "
                       f"La presenza si basa su {readings['readings']} letture su {readings['presence']['given']} risposte. "
                       f"Le pagine di Avoria sono citate da {authors['foil']} su {authors['with_sources']} risposte con "
                       f"fonti ({fmt_percent(authors['foil'] / authors['with_sources'])})."),
            "Lavoro": (f"In {missing['answers']} su {missing['given']} risposte Acme Chat dice di non trovare recensioni "
                       f"dei dipendenti; la sua media è {it(missing['mean'])} con queste risposte e "
                       f"{it(missing['mean_without'])} senza. Dall'11 ottobre il punteggio medio è "
                       f"{it(work_episode['values'][0])}."),
        }
        changes = (f"Avenello è nominato nel {fmt_percent(presence['now'])} delle risposte alla domanda sulla scelta, "
                   f"contro il {fmt_percent(presence['previous'])} del periodo precedente. Le risposte che lo nominano "
                   f"citano {moved['new'][0]['domain']}, che nessuna risposta citava prima.")
        self.cli("method", "--study", self.study, "--date", "2026-10-14",
                 "--models", self.save("models.json", models()), check=0)
        path = self.study / "reports/2026-10-14.md"
        report = path.read_text(encoding="utf-8")
        for name, text in findings.items():
            report = re.sub(r"(^### " + name + r": )\[\[[^\]]*\]\]\n\n\[\[[^\]]*\]\]",
                            lambda m, text=text: m.group(1) + "cosa dicono le risposte\n\n" + text, report, flags=re.M)
        report = re.sub(r"\[\[[^\]]*\]\]", changes, report)
        path.write_text(report, encoding="utf-8")
        proc = self.cli("check", "--study", self.study, path)
        self.assertEqual(proc.returncode, 0, proc.stdout)


if __name__ == "__main__":
    unittest.main()
