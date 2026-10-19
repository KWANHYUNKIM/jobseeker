"""agent.db.pick_knobs — 판정 점수로 다음 시안에 걸 교훈을 고른다(DB 없이)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.db import pick_knobs  # noqa: E402


def L(id, apply, score=0, trials=0):
    return {"id": id, "apply": apply, "score": score, "trials": trials}


class PickKnobsTest(unittest.TestCase):
    def test_only_one_untried_lesson_per_trial(self):
        rows = [L(1, {"layout": {"cover": "fullbleed"}}), L(2, {"kit": {"fonts": {"display": "serif"}}})]
        k = pick_knobs(rows, "numbers")
        self.assertEqual(k["lessons"], [1])
        self.assertEqual(k["trying"], 1)
        self.assertEqual(k["kit"], {})

    def test_least_tried_goes_next(self):
        rows = [L(1, {"layout": {"cover": "fullbleed"}}, trials=3), L(2, {"kit": {"image": {"scrim": 0.4}}}, trials=1)]
        self.assertEqual(pick_knobs(rows, "numbers")["trying"], 2)

    def test_liked_kept_disliked_dropped(self):
        rows = [L(1, {"layout": {"cover": "issue"}}, score=3), L(2, {"layout": {"list": "ranked"}}, score=-1),
                L(3, {"kit": {"fonts": {"display": "serif"}}})]
        k = pick_knobs(rows, "numbers")
        self.assertEqual(k["lessons"], [1, 3])
        self.assertNotIn("list", k["layout"])

    def test_always_applied_but_not_scored(self):
        rows = [L(10, {"always": True, "corner": "deadline", "layout": {"list": "dense"}})]
        k = pick_knobs(rows, "deadline")
        self.assertEqual((k["layout"], k["always"], k["lessons"]), ({"list": "dense"}, [10], []))
        self.assertEqual(pick_knobs(rows, "board")["layout"], {})

    def test_text_only_lessons_never_attached(self):
        rows = [L(6, {"baked": "direction.py"}), L(4, {})]
        k = pick_knobs(rows, "numbers")
        self.assertEqual((k["lessons"], k["trying"]), ([], None))

    def test_higher_score_wins_conflict(self):
        rows = [L(1, {"layout": {"cover": "issue"}}, score=5), L(2, {"layout": {"cover": "poster"}}, score=2)]
        k = pick_knobs(rows, "numbers")
        self.assertEqual((k["layout"]["cover"], k["lessons"]), ("issue", [1]))


if __name__ == "__main__":
    unittest.main()
