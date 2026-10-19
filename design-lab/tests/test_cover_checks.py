"""evals.checks — 표지 자동 검사. 교훈 하나에 검사 하나(.claude/skills/writing-design-lessons)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evals import checks  # noqa: E402


def deck(cover: dict, *rest: dict) -> dict:
    return {"slides": [{"role": "cover", **cover}, *rest]}


GOOD = deck({"layout": "logowall", "pill": "10월 4주차", "number": "372",
             "title": "이번 주 마감\n*372*곳", "logos": ["logos/a.png", "logos/b.png"]},
            {"role": "list", "items": [{"label": "한국수력원자력"}]})


class CoverChecksTest(unittest.TestCase):
    def test_good_cover_passes_everything(self):
        self.assertEqual([r for r in checks.run(GOOD) if not r["ok"]], [])

    def test_week_pill_required(self):
        r = checks.by_id(deck({"title": "a", "kicker": "가을, 하반기"}), "week-pill")
        self.assertFalse(r["ok"])
        self.assertTrue(checks.by_id(deck({"title": "a", "kicker": "10월 4주차 · 마감"}), "week-pill")["ok"])

    def test_title_at_most_two_short_lines(self):
        self.assertFalse(checks.by_id(deck({"title": "하나\n둘\n셋"}), "title-two-lines")["ok"])
        self.assertFalse(checks.by_id(deck({"title": "지금 개발자를 가장 많이 찾는 직군은 과연 무엇일까"}), "title-two-lines")["ok"])
        self.assertTrue(checks.by_id(deck({"title": "지금 가장 짙게\n물든 *직군*은?"}), "title-two-lines")["ok"])

    def test_focal_points_at_most_three(self):
        busy = deck({"title": "a", "image": {"src": "x"}, "number": "1", "logos": ["l"], "items": [{"label": "x"}]})
        self.assertFalse(checks.by_id(busy, "focal-max-3")["ok"])

    def test_known_name_on_cover(self):
        plain = deck({"title": "지금 가장 짙게\n물든 직군은?"}, {"role": "stat", "items": [{"label": "백엔드"}]})
        self.assertFalse(checks.by_id(plain, "known-name")["ok"])
        named = deck({"title": "한국수력원자력 외\n371곳"}, {"role": "list", "items": [{"label": "한국수력원자력"}]})
        self.assertTrue(checks.by_id(named, "known-name")["ok"])

    def test_cover_number_is_a_fact_not_decoration(self):
        self.assertFalse(checks.by_id(deck({"title": "a", "number": "VOL.01"}), "number-is-fact")["ok"])
        self.assertTrue(checks.by_id(deck({"title": "a", "number": "5,024"}), "number-is-fact")["ok"])
        self.assertTrue(checks.by_id(deck({"title": "a"}), "number-is-fact")["ok"])     # 숫자가 없으면 해당 없음

    def test_question_is_answered_on_slide_two(self):
        q = {"title": "놓친 공고\n없나요?"}
        self.assertFalse(checks.by_id(deck(q, {"role": "end"}), "second-pays")["ok"])
        self.assertTrue(checks.by_id(deck(q, {"role": "list", "items": [{"label": "a"}]}), "second-pays")["ok"])

    def test_every_check_has_lesson_text(self):
        for c in checks.CHECKS.values():
            self.assertTrue(c["lesson"] and c["why"])


if __name__ == "__main__":
    unittest.main()
