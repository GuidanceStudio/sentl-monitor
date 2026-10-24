"""SKILL.md's "When to use" names one route for each request the operator can make."""

import re
import unittest
from pathlib import Path

SKILL = (Path(__file__).resolve().parents[2] / "skills" / "sentl-monitor" / "SKILL.md").read_text(encoding="utf-8")
WHEN = SKILL.split("## When to use", 1)[1].split("## Routes", 1)[0]

# request shape -> words the bullet that answers it must contain
SHAPES = {
    "a project exists in Sentl, no study folder": ["adopt <project>"],
    "runs completed since the last report": ["report"],
    "what changed between two moments": ["what changed", "report"],
    "a first look at a subject": ["first look", "snapshot <subject>"],
    "follow a subject already looked at": ["follow a subject they already looked at", "promote"],
    "start a study": ["brief <subject>", "design"],
    "projects not yet in Sentl": ["setup"],
}


class RoutingTest(unittest.TestCase):
    def test_each_request_shape_has_a_bullet_naming_its_route(self):
        bullets = re.findall(r"^- (.+(?:\n  .+)*)", WHEN, re.M)
        for shape, words in SHAPES.items():
            with self.subTest(shape):
                self.assertTrue(any(all(w in b for w in words) for b in bullets), shape)

    def test_every_route_in_the_table_has_a_playbook_that_exists(self):
        root = Path(__file__).resolve().parents[2] / "skills" / "sentl-monitor"
        for playbook in re.findall(r"`([a-z]+/[A-Z]+\.md)`", SKILL):
            self.assertTrue((root / playbook).exists(), playbook)


if __name__ == "__main__":
    unittest.main()
