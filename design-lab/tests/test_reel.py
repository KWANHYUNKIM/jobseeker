"""묶음을 영상 한 편으로 — 판 → mp4 → 릴스.

    cd design-lab && python -m unittest tests.test_reel -v

메타는 부르지 않는다. ffmpeg 이 필요한 검사는 없으면 건너뛴다(CI 에는 없을 수 있다).
지키려는 것은 셋이다.

  1. 길이 계산이 맞나 — 장 수가 바뀌면 영상 길이가 따라 바뀐다. 3초 아래로 내려가면
     메타가 거절하는데, 그 사실을 올려 보고 알면 늦다.
  2. 한 묶음이 **한 형태로만** 나가나 — 캐러셀과 릴스를 둘 다 올리면 중복 게시다.
  3. 릴스 판(9:16)이 피드 비율 검사에 걸려 죽지 않나 — 두 기준이 아예 다르다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from poster import video                           # noqa: E402
from publish import base, cli, daemon, queue       # noqa: E402
from publish.base import PublishResult             # noqa: E402
from publish.facebook import FacebookPublisher     # noqa: E402
from publish.instagram import InstagramPublisher   # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


def has_ffmpeg() -> bool:
    try:
        video.ffmpeg_exe()
        return True
    except video.FFmpegMissing:
        return False


class DurationTest(unittest.TestCase):
    """장 수 → 길이. 릴스 하한(3초)에 걸리는 자리를 고정해 둔다."""

    def test_length_follows_slide_count(self):
        # n*hold + fade — 겹치는 구간은 앞 장의 hold 에 이어 붙으므로 한 번만 더해진다
        self.assertAlmostEqual(video.duration_for(8, hold=1.8, fade=0.4), 14.8)
        self.assertAlmostEqual(video.duration_for(10, hold=1.8, fade=0.4), 18.4)
        self.assertAlmostEqual(video.duration_for(1, hold=1.8, fade=0.4), 2.2)

    def test_one_slide_is_too_short_for_reels(self):
        # 표지 한 장만 있고 공고 판이 하나도 안 붙은 묶음이 여기 걸린다.
        self.assertLess(video.duration_for(1), video.MIN_SECONDS)
        self.assertGreater(video.duration_for(2), video.MIN_SECONDS)

    def test_filter_chain_offsets_are_multiples_of_hold(self):
        chain = video._filter_chain(3, hold=2.0, fade=0.5, size=(1080, 1920))
        self.assertIn("offset=2.000", chain)
        self.assertIn("offset=4.000", chain)
        # 입력마다 캔버스에 맞춘 뒤에 이어 붙인다 — 크기가 섞여도 xfade 가 안 죽는다
        self.assertEqual(chain.count("force_original_aspect_ratio=decrease"), 3)


class BuildTest(unittest.TestCase):
    """실제로 ffmpeg 을 돌려 규격을 지키는지 본다."""

    def setUp(self):
        if not has_ffmpeg():
            self.skipTest("ffmpeg 이 없어 건너뜁니다")
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _slides(self, n: int, size=(1080, 1920), tag: str = "a") -> list[Path]:
        """단색 장면 n 장. ffmpeg 으로 만들어 Pillow 의존을 피한다."""
        exe = video.ffmpeg_exe()
        out = []
        for i in range(n):
            p = self.tmp / f"{tag}{i:02d}.jpg"
            color = f"0x{(i * 40) % 256:02x}3355"
            subprocess.run([exe, "-y", "-loglevel", "error", "-f", "lavfi",
                            "-i", f"color=c={color}:s={size[0]}x{size[1]}",
                            "-frames:v", "1", str(p)], check=True)
            out.append(p)
        return out

    def test_built_reel_meets_every_requirement(self):
        dest = video.build(self._slides(4), self.tmp / "reel.mp4")
        self.assertEqual(video.check(dest), [], "릴스 규격 위반이 없어야 한다")
        info = video.probe(dest)
        self.assertEqual((info["width"], info["height"]), (1080, 1920), "9:16 이어야 한다")
        self.assertEqual(info["video_codec"], "h264")
        # yuvj420p 로 나가면 폰마다 색이 뜬다. JPEG 은 full range 로 들어오므로
        # 필터에서 tv range 로 바꿔 줘야 하고, 그게 됐는지가 여기서 갈린다.
        self.assertEqual(info["pix_fmt"], "yuv420p")
        # 무음이라도 오디오 트랙이 있어야 한다 — 없으면 인스타가 되돌려 보낸다
        self.assertEqual(info["audio_codec"], "aac")
        self.assertAlmostEqual(info["seconds"], video.duration_for(4), delta=0.3)

    def test_mixed_sizes_still_build(self):
        # 4:5 판이 섞여 들어와도 캔버스에 맞춰 넣는다(xfade 는 크기가 다르면 죽는다).
        slides = self._slides(2, tag="tall") + self._slides(2, size=(1080, 1350), tag="wide")
        dest = video.build(slides, self.tmp / "mixed.mp4")
        self.assertEqual(video.probe(dest)["height"], 1920)

    def test_too_few_slides_is_refused_before_ffmpeg(self):
        with self.assertRaises(ValueError) as e:
            video.build(self._slides(1), self.tmp / "short.mp4")
        self.assertIn("하한", str(e.exception))


class RatioCheckTest(unittest.TestCase):
    """릴스 판(9:16)과 피드 판(4:5)은 서로 다른 잣대로 잰다."""

    def setUp(self):
        try:
            from PIL import Image                                   # noqa: F401
        except ImportError:
            self.skipTest("Pillow 가 없어 비율 검사를 건너뜁니다")
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _jpeg(self, w: int, h: int) -> Path:
        from PIL import Image
        p = self.tmp / f"{w}x{h}.jpg"
        Image.new("RGB", (w, h), (30, 40, 50)).save(p, "JPEG")
        return p

    def test_reel_slide_passes_as_reel_and_fails_as_feed(self):
        tall = self._jpeg(1080, 1920)
        self.assertEqual(cli._check_image(tall, reel=True), "")
        self.assertIn("밖입니다", cli._check_image(tall),
                      "9:16 은 피드 비율이 아니다 — 두 잣대가 갈려 있어야 한다")

    def test_feed_slide_passes_as_feed_and_fails_as_reel(self):
        wide = self._jpeg(1080, 1350)
        self.assertEqual(cli._check_image(wide), "")
        self.assertIn("밖입니다", cli._check_image(wide, reel=True))


class FakePublisher:
    """캐러셀과 릴스 중 무엇으로 불렸는지 기록한다."""
    login = "instagram"

    def __init__(self, name="instagram"):
        self.name, self.videos, self.carousels = name, [], []

    def missing(self):
        return []

    def publish(self, *, image, caption, link="", dry_run=True):
        return PublishResult(self.name, True, dry_run, remote_id="1")

    def publish_many(self, *, images, caption, link="", dry_run=True):
        self.carousels.append(list(images))
        return PublishResult(self.name, True, dry_run, remote_id="1")

    def publish_video(self, *, video, caption, cover=None, link="", dry_run=True):
        self.videos.append(video)
        return PublishResult(self.name, True, dry_run, remote_id="2",
                             url=f"https://{self.name}.example/reel/xyz")

    def media_stats(self, media_id):
        return {"likes": 1, "comments": 0, "permalink": ""}

    def publishing_limit(self):
        return {"used": 0, "limit": 100}


class ReelPipelineTest(unittest.TestCase):
    """승인 묶음(inbox) → 원장 → 발행. 릴스는 릴스 길로만 간다."""

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

    def tearDown(self):
        for (mod, name), value in self.saved.items():
            setattr(mod, name, value)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def drop(self, item_id, job_key, *, reel: bool):
        d = daemon.INBOX / item_id
        d.mkdir(parents=True)
        (d / "poster.jpg").write_bytes(JPEG)
        if reel:
            (d / "reel.mp4").write_bytes(MP4)
        else:
            (d / "slide_01.jpg").write_bytes(JPEG)
            (d / "slide_02.jpg").write_bytes(JPEG)
        (d / "bundle.json").write_text(json.dumps({
            "id": item_id, "job_key": job_key, "company": "묶음",
            "format": "reel" if reel else "carousel",
            "captions": {"instagram": "캡션"}, "platforms": ["instagram"],
            "approved_at": "2026-09-16T10:00:00"}), encoding="utf-8")

    def _run(self, pub):
        log: list[str] = []
        daemon.ingest(log)
        daemon.drop_closed(log, status_of=lambda k: "active")
        daemon.schedule(datetime(2026, 9, 17, 9, 0), self.conf, log)
        daemon.publish_due(datetime(2026, 9, 17, 12, 31), {}, self.conf, log,
                           {"instagram": pub})
        return log

    def test_reel_bundle_is_recorded_as_video(self):
        self.drop("bbbb0001", "collection:week-1", reel=True)
        daemon.ingest([])
        item = queue.items()[0]
        self.assertEqual(item["format"], "reel")
        self.assertTrue(item["video"].endswith(".mp4"), item["video"])
        self.assertTrue((daemon.LAB_DIR / item["video"]).is_file(), "mp4 가 보관돼야 한다")

    def test_reel_goes_to_publish_video_not_carousel(self):
        self.drop("bbbb0002", "collection:week-2", reel=True)
        pub = FakePublisher()
        self._run(pub)
        self.assertEqual(len(pub.videos), 1, "릴스는 영상 길로 가야 한다")
        self.assertEqual(pub.carousels, [], "같은 묶음을 캐러셀로도 올리면 중복 게시다")

    def test_reel_bundle_is_a_collection_not_a_single_job(self):
        """판 대신 mp4 하나로 와도 묶음은 묶음이다.

        공고 한 건으로 오인되면 drop_closed 가 `collection:week-…` 를 공고 색인에서
        찾는다. 거기 없으니 마감으로 보고 묶음을 통째로 버린다 — 8곳이 든 게시물이
        조용히 사라진다.
        """
        self.drop("bbbb0004", "collection:week-4", reel=True)
        daemon.ingest([])
        self.assertEqual(queue.items()[0]["kind"], "collection")
        # 색인에 없는 키는 마감으로 답하는 상황을 만들어 본다
        log: list[str] = []
        daemon.drop_closed(log, status_of=lambda k: "closed")
        self.assertEqual(queue.items()[0]["status"], "approved",
                         f"묶음은 마감 검사 대상이 아니다: {log}")

    def test_carousel_bundle_is_untouched(self):
        self.drop("bbbb0003", "collection:week-3", reel=False)
        pub = FakePublisher()
        self._run(pub)
        self.assertEqual(pub.videos, [], "영상이 아닌 묶음은 예전 길 그대로다")
        self.assertEqual(len(pub.carousels), 1)
        self.assertEqual(len(pub.carousels[0]), 3, "표지 + 판 2장")


class AdapterTest(unittest.TestCase):
    """요청을 실제로 보내지 않고, 만들어지는 요청의 모양만 본다."""

    def _ig(self):
        return InstagramPublisher({"instagram": {"ig_user_id": "1", "access_token": "t"},
                                   "public_base_url": "https://x.test/ig"})

    def test_instagram_reel_shares_to_feed(self):
        res = self._ig().publish_video(video=Path("reel.mp4"), caption="캡션", dry_run=True)
        self.assertTrue(res.ok, res.error)
        create = res.steps[0]
        self.assertEqual(create["params"]["media_type"], "REELS")
        # 이게 빠지면 릴스 탭에만 남고 프로필 피드(타임라인)에는 안 보인다
        self.assertEqual(create["params"]["share_to_feed"], "true")

    def test_instagram_refuses_non_video(self):
        res = self._ig().publish_video(video=Path("poster.jpg"), caption="캡션", dry_run=True)
        self.assertFalse(res.ok)
        self.assertIn("mp4", res.error)

    def test_facebook_video_needs_no_public_url(self):
        # 페이스북은 파일을 직접 받는다 — public_base_url 이 없어도 된다.
        pub = FacebookPublisher({"facebook": {"page_id": "1", "access_token": "t"}})
        res = pub.publish_video(video=Path("reel.mp4"), caption="캡션", dry_run=True)
        self.assertTrue(res.ok, res.error)
        self.assertTrue(res.steps[0]["url"].endswith("/videos"))

    def test_linkedin_says_it_cannot(self):
        # 조용히 이미지로 물러나면 영상을 기대한 자리에 정지 화면이 올라간다.
        pub = base.publisher_for("linkedin", {})
        res = pub.publish_video(video=Path("reel.mp4"), caption="캡션", dry_run=True)
        self.assertFalse(res.ok)
        self.assertIn("영상", res.error)


if __name__ == "__main__":
    unittest.main()
