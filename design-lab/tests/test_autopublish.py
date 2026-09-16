"""자동 발행 데몬 — 원장이 앞으로만 가는지, 두 번 올리지 않는지.

    cd design-lab && python -m unittest tests.test_autopublish -v

실제 인스타는 부르지 않는다. 발행기는 가짜를 끼우고, 원장·inbox 는 임시 폴더로 돌린다.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from publish import base, daemon, queue          # noqa: E402
from publish.base import PublishResult             # noqa: E402
from publish.instagram import InstagramPublisher  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


class FakePublisher:
    login = "instagram"

    def __init__(self, name="instagram", *, ready=True, fail=False):
        self.name, self.ready, self.fail, self.calls = name, ready, fail, []

    def missing(self):
        return [] if self.ready else ["access_token"]

    def publish(self, *, image, caption, link="", dry_run=True):
        self.calls.append({"image": image, "caption": caption, "dry_run": dry_run})
        if self.fail:
            return PublishResult(self.name, False, dry_run, error="HTTP 400")
        if dry_run:
            return PublishResult(self.name, True, True)
        return PublishResult(self.name, True, False, remote_id="1789",
                             url=f"https://{self.name}.example/p/abc")

    def publish_many(self, *, images, caption, link="", dry_run=True):
        # 데몬은 한 장짜리도 publish_many 로 부른다(묶음과 같은 길)
        self.many = getattr(self, "many", []) + [list(images)]
        return self.publish(image=images[0], caption=caption, dry_run=dry_run)

    def media_stats(self, media_id):
        return {"likes": 12, "comments": 3, "permalink": "https://www.instagram.com/p/abc/"}

    def publishing_limit(self):
        return {"used": 1, "limit": 100}


class AutopublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = {
            (queue, "LEDGER"): queue.LEDGER, (daemon, "INBOX"): daemon.INBOX,
            (daemon, "APPROVED_DIR"): daemon.APPROVED_DIR, (daemon, "STATUS"): daemon.STATUS,
            (daemon, "LOCK"): daemon.LOCK, (daemon, "LAB_DIR"): daemon.LAB_DIR,
            (base, "EXPOSED"): base.EXPOSED,
        }
        queue.LEDGER = self.tmp / "state" / "publish_queue.json"
        daemon.LAB_DIR = self.tmp
        daemon.INBOX = self.tmp / "inbox"
        daemon.APPROVED_DIR = self.tmp / "state" / "approved"
        daemon.STATUS = self.tmp / "state" / "publish_status.json"
        daemon.LOCK = self.tmp / "state" / "publish.lock"
        base.EXPOSED = self.tmp / "exposed"
        self.conf = daemon.settings({})
        self.now = datetime(2026, 9, 17, 9, 0)

    def tearDown(self):
        for (mod, name), value in self.saved.items():
            setattr(mod, name, value)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pubs(self, **kw):
        """플랫폼 → 발행기."""
        return {"instagram": kw.get("instagram") or FakePublisher("instagram"),
                "facebook": kw.get("facebook") or FakePublisher("facebook")}

    def drop(self, item_id, job_key, *, complete=True, platforms=("instagram",)):
        d = daemon.INBOX / item_id
        d.mkdir(parents=True)
        (d / "poster.jpg").write_bytes(JPEG)
        if complete:
            (d / "bundle.json").write_text(json.dumps({
                "id": item_id, "job_key": job_key, "company": "쿠팡",
                "captions": {x: f"{x} 캡션" for x in platforms},
                "platforms": list(platforms), "approved_at": "2026-09-16T10:00:00"}), encoding="utf-8")

    def run_until_publish(self, pubs, now=None):
        log = []
        daemon.ingest(log)
        daemon.drop_closed(log, status_of=lambda k: "active")
        daemon.schedule(self.now, self.conf, log)
        return daemon.publish_due(now or datetime(2026, 9, 17, 12, 31), {}, self.conf, log, pubs), log

    # --- 받기 --------------------------------------------------------------
    def test_ingest_skips_half_copied_bundle(self):
        self.drop("aaaa0001", "wanted-1", complete=False)
        self.assertEqual(daemon.ingest([]), 0)
        self.assertTrue((daemon.INBOX / "aaaa0001").is_dir(), "bundle.json 없는 묶음은 그대로 둔다")

    def test_ingest_rejects_second_bundle_for_same_job(self):
        self.drop("aaaa0001", "wanted-1")
        self.drop("aaaa0002", "wanted-1")
        log = []
        daemon.ingest(log)
        self.assertEqual([i["id"] for i in queue.items()], ["aaaa0001"])
        self.assertTrue((daemon.INBOX / "_rejected" / "aaaa0002").is_dir())

    # --- 마감·예약 --------------------------------------------------------
    def test_closed_job_is_skipped_not_published(self):
        self.drop("aaaa0001", "wanted-1")
        daemon.ingest([])
        daemon.drop_closed([], status_of=lambda k: "closed")
        self.assertEqual(queue.get("aaaa0001")["status"], "skipped")

    def test_slots_are_not_shared(self):
        for n in range(3):
            self.drop(f"aaaa000{n}", f"wanted-{n}")
        daemon.ingest([])
        daemon.schedule(self.now, self.conf, [])
        got = sorted(i["scheduled_at"] for i in queue.items())
        self.assertEqual(got, ["2026-09-17T12:30:00", "2026-09-17T19:30:00", "2026-09-18T12:30:00"])

    def test_next_slot_rolls_to_tomorrow(self):
        slot = daemon.next_slot(datetime(2026, 9, 17, 20, 0), ["12:30", "19:30"], set())
        self.assertEqual(slot, datetime(2026, 9, 18, 12, 30))

    # --- 발행 --------------------------------------------------------------
    def test_not_due_yet_does_nothing(self):
        self.drop("aaaa0001", "wanted-1")
        pub = FakePublisher()
        self.conf["live"] = True
        item, _ = self.run_until_publish(self.pubs(instagram=pub), now=datetime(2026, 9, 17, 12, 0))
        self.assertIsNone(item)
        self.assertEqual(pub.calls, [])

    def test_live_off_rehearses_and_never_goes_out(self):
        self.drop("aaaa0001", "wanted-1")
        pub = FakePublisher(ready=True)
        item, _ = self.run_until_publish(self.pubs(instagram=pub))
        self.assertEqual(item["status"], "rehearsed")
        self.assertTrue(pub.calls[0]["dry_run"])
        self.assertEqual(queue.published_platforms("wanted-1"), set())

    def test_live_without_credentials_rehearses(self):
        self.drop("aaaa0001", "wanted-1")
        self.conf["live"] = True
        item, _ = self.run_until_publish(self.pubs(instagram=FakePublisher(ready=False)))
        self.assertEqual(item["status"], "rehearsed")

    def test_live_publish_records_permalink_and_blocks_repeat(self):
        self.drop("aaaa0001", "wanted-1")
        self.conf["live"] = True
        item, _ = self.run_until_publish(self.pubs())
        self.assertEqual(item["status"], "published")
        self.assertEqual(item["results"]["instagram"]["url"], "https://instagram.example/p/abc")
        self.assertEqual(queue.published_platforms("wanted-1"), {"instagram"})
        self.drop("aaaa0002", "wanted-1")
        daemon.ingest([])
        self.assertIsNone(queue.get("aaaa0002"), "이미 올라간 공고의 새 승인은 받지 않는다")

    def test_failure_retries_next_slot_then_gives_up(self):
        self.drop("aaaa0001", "wanted-1")
        self.conf["live"] = True
        pub = FakePublisher(fail=True)
        item, _ = self.run_until_publish(self.pubs(instagram=pub))
        self.assertEqual((item["status"], item["attempts"], item["scheduled_at"]),
                         ("scheduled", 1, "2026-09-17T19:30:00"))
        item = daemon.publish_due(datetime(2026, 9, 17, 19, 31), {}, self.conf, [], self.pubs(instagram=pub))
        item = daemon.publish_due(datetime(2026, 9, 18, 12, 31), {}, self.conf, [], self.pubs(instagram=pub))
        self.assertEqual((item["status"], item["attempts"]), ("failed", 3))

    def test_one_post_per_tick(self):
        self.drop("aaaa0001", "wanted-1")
        self.drop("aaaa0002", "wanted-2")
        self.conf["live"] = True
        pub = FakePublisher()
        self.run_until_publish(self.pubs(instagram=pub), now=datetime(2026, 9, 18, 0, 0))   # 둘 다 시각이 지났어도
        self.assertEqual(len(pub.calls), 1)

    def test_stats_refresh_for_recent_posts(self):
        self.drop("aaaa0001", "wanted-1")
        self.conf["live"] = True
        pub = FakePublisher()
        self.run_until_publish(self.pubs(instagram=pub))
        queue.update("aaaa0001", published_at="2026-09-17T12:31:00")
        n = daemon.refresh_stats(datetime(2026, 9, 17, 18, 0), {}, self.conf, [], pub)
        self.assertEqual(n, 1)
        self.assertEqual(queue.get("aaaa0001")["stats"]["likes"], 12)

    # --- 두 곳에 함께 --------------------------------------------------------
    def test_posts_to_both_with_platform_captions(self):
        self.drop("aaaa0001", "wanted-1", platforms=("instagram", "facebook"))
        self.conf["live"] = True
        pubs = self.pubs()
        item, _ = self.run_until_publish(pubs)
        self.assertEqual(item["status"], "published")
        self.assertEqual(item["posted"], ["facebook", "instagram"])
        self.assertEqual(pubs["instagram"].calls[0]["caption"], "instagram 캡션")
        self.assertEqual(pubs["facebook"].calls[0]["caption"], "facebook 캡션")
        self.assertEqual(queue.published_platforms("wanted-1"), {"instagram", "facebook"})

    def test_one_side_fails_retry_does_not_repost_the_other(self):
        self.drop("aaaa0001", "wanted-1", platforms=("instagram", "facebook"))
        self.conf["live"] = True
        ig, fb = FakePublisher("instagram"), FakePublisher("facebook", fail=True)
        item, _ = self.run_until_publish({"instagram": ig, "facebook": fb})
        self.assertEqual(item["status"], "scheduled", "실패한 페이스북 때문에 재시도로 남는다")
        self.assertTrue(item["results"]["instagram"]["ok"])

        fb.fail = False
        item = daemon.publish_due(datetime(2026, 9, 17, 19, 31), {}, self.conf, [],
                                  {"instagram": ig, "facebook": fb})
        self.assertEqual(item["status"], "published")
        self.assertEqual(len(ig.calls), 1, "인스타에는 두 번 올리지 않는다")
        self.assertEqual(len(fb.calls), 2)

    def test_one_platform_without_credentials_holds_the_whole_post(self):
        self.drop("aaaa0001", "wanted-1", platforms=("instagram", "facebook"))
        self.conf["live"] = True
        pubs = {"instagram": FakePublisher("instagram", ready=False), "facebook": FakePublisher("facebook")}
        item, _ = self.run_until_publish(pubs)
        # 한쪽 자격이 없으면 그쪽은 연습으로 남고, 판 전체가 rehearsed 가 된다
        self.assertEqual(item["status"], "rehearsed")
        self.assertTrue(pubs["instagram"].calls[0]["dry_run"])

    # --- 공개 이미지 --------------------------------------------------------
    def test_expose_uses_content_hash_not_job_key(self):
        img = self.tmp / "wanted-1.jpg"
        img.write_bytes(JPEG)
        name = base.expose(img)
        self.assertNotIn("wanted", name)
        self.assertEqual(name, base.expose(img), "같은 내용은 같은 이름")
        self.assertTrue((base.EXPOSED / name).is_file())


class InstagramAdapterTest(unittest.TestCase):
    """HTTP 는 가짜로 — 컨테이너가 끝나기를 기다린 뒤에만 게시하는지."""

    def make(self, statuses):
        pub = InstagramPublisher({"public_base_url": "https://v.example/ig",
                                  "instagram": {"ig_user_id": "42", "access_token": "T"}})
        pub.sleep = lambda s: None
        pub.public_url_for = lambda image: "https://v.example/ig/x.jpg"
        calls = []
        seq = list(statuses)

        def fake(url, data=None, method="POST", **_):
            calls.append((method, url.rsplit("/", 1)[-1]))
            if url.endswith("/media"):
                return {"json": {"id": "C1"}}
            if url.endswith("/media_publish"):
                return {"json": {"id": "M1"}}
            if url.endswith("/C1"):
                return {"json": {"status_code": seq.pop(0)}}
            if url.endswith("/M1"):
                return {"json": {"permalink": "https://www.instagram.com/p/xyz/"}}
            raise AssertionError(url)

        pub._request = fake
        return pub, calls

    def test_waits_for_finished_then_publishes(self):
        pub, calls = self.make(["IN_PROGRESS", "FINISHED"])
        img = Path(tempfile.mkdtemp()) / "p.jpg"
        img.write_bytes(JPEG)
        res = pub.publish(image=img, caption="c", dry_run=False)
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.url, "https://www.instagram.com/p/xyz/")
        self.assertEqual([c[1] for c in calls], ["media", "C1", "C1", "media_publish", "M1"])

    def test_container_error_does_not_publish(self):
        pub, calls = self.make(["ERROR"])
        img = Path(tempfile.mkdtemp()) / "p.jpg"
        img.write_bytes(JPEG)
        res = pub.publish(image=img, caption="c", dry_run=False)
        self.assertFalse(res.ok)
        self.assertNotIn("media_publish", [c[1] for c in calls])

    def test_png_is_refused(self):
        pub, _ = self.make([])
        res = pub.publish(image=Path("x.png"), caption="c", dry_run=False)
        self.assertIn("JPEG", res.error)


if __name__ == "__main__":
    unittest.main()
