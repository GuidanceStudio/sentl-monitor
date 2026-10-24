"""The skill reads Sentl's responses and makes no model call of its own: no model-provider key, no model API."""

import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "skills" / "sentl-monitor"
FORBIDDEN = re.compile(r"OPENROUTER|openrouter\.ai|api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis", re.I)


class NoModelCallsTest(unittest.TestCase):
    def test_no_script_or_playbook_names_a_model_provider_endpoint_or_key(self):
        found = [str(p.relative_to(SKILL)) for p in SKILL.rglob("*")
                 if p.is_file() and p.suffix in (".py", ".md", ".sh", ".json") and "__pycache__" not in p.parts
                 and FORBIDDEN.search(p.read_text(encoding="utf-8", errors="ignore"))]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
