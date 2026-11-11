"""A fictional history built to contain every insight of DEVPLAN M2b (done when): two weekly
periods of daily runs, three rounds each. The second period's material lists every insight
with its figures."""

import datetime as dt
import unittest

from fixtures import CHOICE_Q, GEM, GPT, PRICE_Q, WORK_Q, StudyCase
from test_insights_period import NO_DATA

OUTDATED = ("Un litro di Avenello costa 1,90 €.", 2, ["https://prezzi.example/avena", "https://recensioni.example/avena"])
CURRENT = ("Un litro di Avenello costa 2,10 €.", 5, ["https://avenello.example/prezzi"])
UNNAMED = ("La migliore è Avoria, secondo il confronto.", 3, ["https://avoria.example/confronto"])
NAMED = ("La migliore è Avenello, prima di Avoria.", 4, ["https://classifica.example/2026", "https://avoria.example/confronto"])
GOOD_JOB = ("Avenello è un buon datore di lavoro, secondo i dipendenti.", 4, ["https://lavoro.example/avenello"])
NO_JOB = (NO_DATA, 3, ["https://clienti.example/avenello"])


def day(n):
    return f"{dt.date(2026, 10, 1) + dt.timedelta(days=n - 1)}T06:00:00Z"


def rows_of(n):
    """Day n's answers. From day 8: the current price on days 8-10, Avenello named on days 13-14,
    and Acme Chat finding no information on Avenello's plant from day 12."""
    gem_price = CURRENT if n in (8, 9, 10) else OUTDATED
    choice = NAMED if n in (13, 14) else UNNAMED
    gpt_work = NO_JOB if n >= 12 else GOOD_JOB
    answers = [(PRICE_Q, GPT, OUTDATED), (PRICE_Q, GEM, gem_price), (CHOICE_Q, GPT, choice), (CHOICE_Q, GEM, choice),
               (WORK_Q, GPT, gpt_work), (WORK_Q, GEM, GOOD_JOB)]
    return [(q, m, *a) for q, m, a in answers] * 3


class InsightHistoryTest(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.adopt_market(rows_of(1), rounds=3, report_every="weekly")
        for n in range(1, 15):
            self.ingest_market(9100 + n, day(n), rows_of(n))
        self.publish("2026-10-07")
        self.build("2026-10-14")
        self.material = (self.study / "history/material/2026-10-14.md").read_text(encoding="utf-8")

    def test_the_material_lists_every_insight(self):
        for heading in ("##### Fact currency", "##### Sources behind the fact", "##### Sources behind the score",
                        "##### Episodes", "##### Presence by run", "##### Missing evidence",
                        "##### Who wrote the sources", "### Presence changes"):
            self.assertIn(heading, self.material)
        self.assertRegex(self.material, r"\d+ readings of \d+ answers")


if __name__ == "__main__":
    unittest.main()
