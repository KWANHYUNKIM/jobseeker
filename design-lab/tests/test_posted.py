"""publish.posted — 이미 내보낸 공고를 원장·inbox 에서 모은다."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from publish import posted  # noqa: E402


class PostedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = (posted.LEDGERS, posted.INBOX)
        posted.LEDGERS = (self.tmp / "q.json",)
        posted.INBOX = self.tmp / "inbox"

    def tearDown(self):
        posted.LEDGERS, posted.INBOX = self.saved

    def _bundle(self, folder: str, bid: str, keys: list[str]) -> None:
        d = self.tmp / "inbox" / folder / bid if folder else self.tmp / "inbox" / bid
        d.mkdir(parents=True)
        (d / "bundle.json").write_text(json.dumps({
            "id": bid, "job_key": "collection:week", "approved_at": "2026-09-29T10:00:00",
            "collection": {"jobs": [{"key": k} for k in keys]}}), encoding="utf-8")

    def test_ledger_statuses(self):
        (self.tmp / "q.json").write_text(json.dumps({"items": [
            {"id": "1", "job_key": "wanted-1", "status": "published", "created_at": "2026-09-16"},
            {"id": "2", "job_key": "wanted-2", "status": "failed", "created_at": "2026-09-16"},
            {"id": "3", "job_key": "collection:week-x", "status": "scheduled", "created_at": "2026-09-16",
             "collection": {"jobs": [{"key": "wanted-3"}, {"key": "wanted-4"}]}},
        ]}), encoding="utf-8")
        got = posted.posted()
        self.assertEqual(sorted(got), ["wanted-1", "wanted-3", "wanted-4"])   # 실패한 것은 다시 쓸 수 있다
        self.assertNotIn("collection:week-x", got)

    def test_inbox_and_sent_count_but_held_does_not(self):
        self._bundle("", "a1", ["wanted-5"])
        self._bundle("_sent", "b2", ["wanted-6"])
        self._bundle("_held", "c3", ["wanted-7"])
        got = posted.posted()
        self.assertEqual(got["wanted-5"]["status"], "approved")
        self.assertEqual(got["wanted-6"]["status"], "sent")
        self.assertNotIn("wanted-7", got)

    def test_same_company_and_title_counts_as_posted(self):
        # 토스가 같은 'Node.js Developer' 를 번호 둘로 올려 둔 것 — 두 번째 번호도 이미 낸 것이다
        (self.tmp / "q.json").write_text(json.dumps({"items": [
            {"id": "1", "job_key": "collection:week", "status": "approved", "created_at": "2026-09-29",
             "collection": {"jobs": [{"key": "wanted-363475", "company": "비바리퍼블리카(토스)",
                                      "role": "Node.js Developer"}]}}]}), encoding="utf-8")
        table = posted.posted()
        other = {"key": "wanted-374054", "company": "비바리퍼블리카(토스)", "title": "Node.js  developer"}
        self.assertIsNotNone(posted.taken(other, table))
        self.assertIsNone(posted.taken({**other, "title": "Server Developer"}, table))


if __name__ == "__main__":
    unittest.main()
