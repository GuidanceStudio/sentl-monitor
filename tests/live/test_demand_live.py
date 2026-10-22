"""Live tier for search demand: one request to Google's suggestion endpoint returns a list of
suggestions that `demand.parse_suggestions` reads.

The only network call in the skill. Opt in with RUN_LIVE=1; no study folder is needed.
"""

import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "skills" / "sentl-monitor" / "scripts"))

from sentlmon import demand  # noqa: E402


@unittest.skipUnless(os.environ.get("RUN_LIVE") == "1", "set RUN_LIVE=1 to send one request to Google")
class AutocompleteLiveTest(unittest.TestCase):

    def test_one_prefix_returns_suggestions_that_start_with_it(self):
        prefix = "oat milk"
        text = demand._get(demand.suggest_url(prefix, "en", "US"))
        suggestions = demand.parse_suggestions(text)
        self.assertGreater(len(suggestions), 0)
        self.assertTrue(all(s.lower().startswith(prefix) for s in suggestions), suggestions)


if __name__ == "__main__":
    unittest.main()
