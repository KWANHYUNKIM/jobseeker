"""evals.brand — 회사 전용 판(brands/<회사>.json)의 규칙 검사. 절차는 .claude/skills/brand-poster."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evals import brand  # noqa: E402

MED = {"ground": "paper", "text_load": "one-line", "hand": "grid-print", "dominant": "격자", "why": "칸"}
GOOD = {"signature": {"id": "x", "evidence": ["https://a.example/1 — 공식 문장"], "medium": MED,
                     "alternatives": [{"what": "후보", "why_not": "로고 변형"}]},
        "points": [{"id": "p1"}]}


class BrandChecksTest(unittest.TestCase):
    def run_one(self, data, cid, others=None):
        return brand.by_id("회사", data, cid, others or {})

    def test_good_passes_everything(self):
        self.assertEqual([r for r in brand.run("회사", GOOD, {}) if not r["ok"]], [])

    def test_points_at_most_two(self):
        self.assertFalse(self.run_one({**GOOD, "points": [{}, {}, {}]}, "points-max-2")["ok"])

    def test_evidence_needs_a_url(self):
        bad = {**GOOD, "signature": {**GOOD["signature"], "evidence": ["공식 사이트에서 봤다"]}}
        self.assertFalse(self.run_one(bad, "signature-evidence-url")["ok"])

    def test_alternatives_with_reasons(self):
        none = {**GOOD, "signature": {**GOOD["signature"], "alternatives": []}}
        self.assertFalse(self.run_one(none, "signature-alternatives")["ok"])
        no_reason = {**GOOD, "signature": {**GOOD["signature"], "alternatives": [{"what": "후보"}]}}
        self.assertFalse(self.run_one(no_reason, "signature-alternatives")["ok"])

    def test_medium_must_not_repeat_another_company(self):
        others = {"다른회사": ("paper", "one-line", "grid-print")}
        self.assertFalse(self.run_one(GOOD, "medium-unique", others)["ok"])
        self.assertTrue(self.run_one(GOOD, "medium-unique", {"다른회사": ("flat", "full", "print")})["ok"])

    def test_images_at_most_600kb(self):
        with tempfile.TemporaryDirectory() as d:
            big = Path(d) / "big.jpg"
            big.write_bytes(b"0" * (601 * 1024))
            saved = brand.LAB_DIR
            brand.LAB_DIR = Path(d)
            try:
                r = self.run_one({**GOOD, "ui": {"images": {"cover": "big.jpg"}}}, "images-600kb")
            finally:
                brand.LAB_DIR = saved
        self.assertFalse(r["ok"])

    def test_medium_must_be_chosen_not_observed(self):
        seen = {**GOOD, "signature": {**GOOD["signature"], "medium": {**MED, "observed": True}}}
        self.assertFalse(self.run_one(seen, "medium-chosen")["ok"])
        self.assertTrue(self.run_one(GOOD, "medium-chosen")["ok"])

    def test_cover_does_not_carry_full_text(self):
        full = {**GOOD, "signature": {**GOOD["signature"], "medium": {**MED, "text_load": "full"}}}
        self.assertFalse(self.run_one(full, "cover-not-full")["ok"])
        self.assertTrue(self.run_one(GOOD, "cover-not-full")["ok"])

    def test_every_check_has_rule_and_section(self):
        for c in brand.CHECKS.values():
            self.assertTrue(c["rule"] and c["ref"])


if __name__ == "__main__":
    unittest.main()
