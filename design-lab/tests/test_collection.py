"""묶음(카테고리) — 뭘 골라 넣나, 캐러셀로 어떻게 나가나.

    cd design-lab && python -m unittest tests.test_collection -v

공고 색인·인스타는 부르지 않는다. 공고는 손으로 만든 목록을 넣고, 발행기는 가짜를 끼운다.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from poster import collection                     # noqa: E402
from publish import base, caption, daemon, queue  # noqa: E402
from publish.base import PublishResult            # noqa: E402
from publish.instagram import InstagramPublisher  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def job(key, company, title="백엔드 개발자", *, status="active", career="경력 3년 이상",
        deadline="", stack=("Java",)):
    return {"key": key, "company": company, "title": title, "status": status,
            "career": career, "deadline": deadline, "stack": list(stack),
            "tasks": ["서버 개발"], "qualifications": ["경력 3년"], "site": "wanted"}


ALL_OPEN = lambda: (lambda job: ("open", "시험"))          # noqa: E731 — 네트워크를 타지 않는다
NO_DATES = lambda job: {}                                  # noqa: E731 — 원본 조회도 하지 않는다


class PickTest(unittest.TestCase):
    def setUp(self):
        # brands.find·회사 규모표·모집중 확인은 파일과 네트워크를 쓴다 — 시험에서는 끼워 넣는다
        self.saved = (collection.brands.find, collection._sizes, collection._verifier, collection._dates)
        collection.brands.find = lambda c: None
        collection._sizes = lambda: {"쿠팡": "대기업", "당근서비스": "대기업", "와탭랩스": "중소기업"}
        collection._verifier = ALL_OPEN
        collection._dates = NO_DATES

    def tearDown(self):
        collection.brands.find, collection._sizes, collection._verifier, collection._dates = self.saved

    def test_closed_and_empty_jobs_are_left_out(self):
        rows = [job("a", "가", status="closed"), job("b", "나"),
                {**job("c", "다"), "tasks": [], "qualifications": []}]
        got = collection.build("week", jobs=rows, brand_only=False)
        self.assertEqual([j["company"] for j in got["jobs"]], ["나"])

    def test_one_slot_per_company(self):
        rows = [job("a", "쿠팡", "백엔드"), job("b", "쿠팡", "프론트엔드"), job("c", "당근서비스")]
        got = collection.build("week", jobs=rows, brand_only=False)
        self.assertEqual([j["company"] for j in got["jobs"]], ["당근서비스", "쿠팡"])

    def test_limit_caps_slides(self):
        rows = [job(f"k{i}", f"회사{i}") for i in range(20)]
        self.assertEqual(collection.build("week", jobs=rows, limit=9, brand_only=False)["count"], 9)

    def test_role_category_uses_family(self):
        rows = [job("a", "가", "백엔드 엔지니어"), job("b", "나", "프론트엔드 개발자"),
                job("c", "다", "iOS 개발자")]
        got = collection.build("role", value="frontend", jobs=rows, brand_only=False)
        self.assertEqual([j["company"] for j in got["jobs"]], ["나"])
        self.assertEqual(got["title"], "프론트엔드 개발자")

    def test_size_category(self):
        rows = [job("a", "쿠팡"), job("b", "와탭랩스")]
        got = collection.build("size", value="대기업", jobs=rows, brand_only=False)
        self.assertEqual([j["company"] for j in got["jobs"]], ["쿠팡"])
        self.assertEqual(got["title"], "대기업 채용")

    def test_deadline_category_keeps_only_that_window(self):
        rows = [job("a", "가", deadline="2026-09-18"), job("b", "나", deadline="2026-10-30"),
                job("c", "다", deadline="")]
        got = collection.build("deadline", since="2026-09-14", until="2026-09-20", jobs=rows, brand_only=False)
        self.assertEqual([j["company"] for j in got["jobs"]], ["가"])
        self.assertIn("마감", got["title"])

    def test_week_label_same_month_is_short(self):
        got = collection.build("week", since="2026-09-14", until="2026-09-20", jobs=[job("a", "가")], brand_only=False)
        self.assertEqual(got["title"], "9월 14–20일")

    def test_stack_category_matches_whole_token(self):
        rows = [job("a", "가", stack=("Go",)), job("b", "나", stack=("Golang",))]
        got = collection.build("stack", value="Go", jobs=rows, brand_only=False)
        self.assertEqual([j["company"] for j in got["jobs"]], ["가"])

    def test_newgrad_category(self):
        rows = [job("a", "가", career="신입-경력 3년"), job("b", "나", career="경력 5년 이상")]
        self.assertEqual([j["company"] for j in collection.build("newgrad", jobs=rows, brand_only=False)["jobs"]], ["가"])

    def test_role_label_drops_trailing_noise(self):
        got = collection.build("week", jobs=[job("a", "가", "JAVA 풀스택 개발자 경력")], brand_only=False)
        self.assertEqual(got["jobs"][0]["role"], "JAVA 풀스택 개발자")


class BadDataTest(unittest.TestCase):
    """묶음에 들어가면 안 되는 공고 — 지난 마감, 깨진 원본."""

    def setUp(self):
        self.saved = (collection.brands.find, collection._sizes, collection._verifier, collection._dates)
        collection._sizes = lambda: {}
        collection._verifier = ALL_OPEN
        collection._dates = NO_DATES
        self.warns = {}
        collection.brands.find = lambda c: ({"frame": "x.html", **({"data_warning": self.warns[c]} if c in self.warns else {})}
                                            if c in ("가", "나", "다") else None)

    def tearDown(self):
        collection.brands.find, collection._sizes, collection._verifier, collection._dates = self.saved

    def test_year_less_deadline_is_read(self):
        # '~ 06.16(화) 18시' 처럼 연도가 없는 표기 — 못 읽으면 지난 공고가 안 걸러진다
        self.assertEqual(collection._deadline({"deadline": "~ 06.16(화) 18시"}, date(2026, 9, 16)),
                         date(2026, 6, 16))
        self.assertEqual(collection._deadline({"deadline": "~ 01.05"}, date(2026, 12, 20)),
                         date(2027, 1, 5), "연말에 적힌 내년 1월 마감")
        self.assertIsNone(collection._deadline({"deadline": "상시채용"}, date(2026, 9, 16)))

    def test_past_deadline_is_dropped_even_when_status_active(self):
        rows = [job("a", "가", deadline="~ 06.16(화) 18시"), job("b", "나", deadline="2026-12-01")]
        got = collection.build("week", jobs=rows)
        self.assertEqual([j["company"] for j in got["jobs"]], ["나"])

    def test_job_with_broken_source_text_is_dropped(self):
        self.warns["가"] = {"job": "a", "ocr_broken": True, "note": "OCR 로 깨진 본문"}
        rows = [job("a", "가"), job("b", "나")]
        got = collection.build("week", jobs=rows)
        self.assertEqual([j["company"] for j in got["jobs"]], ["나"])

    def test_company_wide_warning_drops_every_posting(self):
        self.warns["다"] = {"note": "회사 전체 보류"}
        rows = [job("a", "다"), job("b", "다", "프론트엔드"), job("c", "나")]
        got = collection.build("week", jobs=rows)
        self.assertEqual([j["company"] for j in got["jobs"]], ["나"])


class OpenCheckTest(unittest.TestCase):
    """끝난 모집은 **고르는 단계에서** 빠진다 — 판을 그리기 전에. 렌더가 제일 비싸다."""

    def setUp(self):
        self.saved = (collection.brands.find, collection._sizes, collection._verifier, collection._dates)
        collection._sizes = lambda: {}
        collection.brands.find = lambda c: {"frame": "x.html"}
        self.verdicts = {}
        collection._dates = NO_DATES
        collection._verifier = lambda: (lambda job: self.verdicts.get(job["key"], ("open", "확인")))

    def tearDown(self):
        collection.brands.find, collection._sizes, collection._verifier, collection._dates = self.saved

    def test_closed_posting_never_reaches_render(self):
        self.verdicts["b"] = ("closed", "원본 확인: 원본 상태 close")
        rows = [job("a", "가"), job("b", "나"), job("c", "다")]
        got = collection.build("week", jobs=rows, limit=3)
        self.assertEqual([j["company"] for j in got["jobs"]], ["가", "다"])
        self.assertEqual([r["company"] for r in got["closed_out"]], ["나"])
        self.assertIn("close", got["closed_out"][0]["why"])

    def test_unverifiable_posting_is_left_out_too(self):
        # 확인 불가는 '열려 있다' 가 아니다 — 홍보물에는 넣지 않는다
        self.verdicts["a"] = ("unknown", "재확인 실패: timeout")
        got = collection.build("week", jobs=[job("a", "가"), job("b", "나")], limit=2)
        self.assertEqual([j["company"] for j in got["jobs"]], ["나"])

    def test_verify_off_skips_the_network(self):
        called = []
        collection._verifier = lambda: (lambda job: called.append(job["key"]) or ("open", ""))
        collection.build("week", jobs=[job("a", "가")], verify=False)
        self.assertEqual(called, [], "verify=False 면 묻지 않는다")

    def test_spares_are_filled_from_open_candidates(self):
        self.verdicts["a"] = ("closed", "마감")
        rows = [job(k, c) for k, c in zip("abcd", "가나다라")]
        got = collection.build("week", jobs=rows, limit=2)
        self.assertEqual([j["company"] for j in got["jobs"]], ["나", "다"])


class BrandGateTest(unittest.TestCase):
    """묶음은 회사 전용 판(BRAND_RESEARCH.md)이 있는 회사만 넣는다 — 기본 틀 판이 섞이면 안 된다."""

    def setUp(self):
        self.saved = (collection.brands.find, collection._sizes, collection._verifier, collection._dates)
        collection._sizes = lambda: {"쿠팡": "대기업", "노타": "중소기업"}
        collection.brands.find = lambda c: {"frame": "brand_coupang.html"} if c == "쿠팡" else None
        collection._verifier = ALL_OPEN
        collection._dates = NO_DATES

    def tearDown(self):
        collection.brands.find, collection._sizes, collection._verifier, collection._dates = self.saved

    def test_only_companies_with_their_own_poster(self):
        rows = [job("a", "쿠팡"), job("b", "노타")]
        got = collection.build("week", jobs=rows)
        self.assertEqual([j["company"] for j in got["jobs"]], ["쿠팡"])
        self.assertEqual(got["short_by"], collection.MAX_SLIDES - 1, "못 채운 자리를 알려 준다")

    def test_gaps_name_the_companies_to_make_next(self):
        rows = [job("a", "쿠팡"), job("b", "노타"), job("c", "노타", "프론트엔드")]
        got = collection.build("week", jobs=rows)
        self.assertEqual([g["company"] for g in got["gaps"]], ["노타"])
        self.assertEqual(got["gaps"][0]["postings"], 2)

    def test_allow_generic_lets_the_basic_frame_in(self):
        rows = [job("a", "쿠팡"), job("b", "노타")]
        got = collection.build("week", jobs=rows, brand_only=False)
        self.assertEqual(sorted(j["company"] for j in got["jobs"]), ["노타", "쿠팡"])


class CollectionCaptionTest(unittest.TestCase):
    def test_lists_companies_and_has_no_job_site_url(self):
        col = {"kind": "week", "kicker": "이번 주 채용", "title": "9월 14–20일", "count": 2,
               "jobs": [{"company": "쿠팡", "role": "Frontend", "career": "경력 7-14년", "stack": ["React"]},
                        {"company": "당근", "role": "Product", "career": "경력 3년 이상", "stack": []}]}
        text = caption.build_collection(col, "instagram")
        self.assertIn("01. 쿠팡 — Frontend (7-14년)", text)
        self.assertIn("02. 당근 — Product", text)
        self.assertIn("#이번주채용", text)
        self.assertNotIn("wanted", text.lower())
        self.assertNotIn("http", text)


class FakeIG:
    name = "instagram"
    login = "instagram"

    def __init__(self):
        self.many, self.single = [], []

    def missing(self):
        return []

    def publish(self, *, image, caption, link="", dry_run=True):
        self.single.append(image)
        return PublishResult(self.name, True, dry_run, remote_id="1", url="https://ig/p/x")

    def publish_many(self, *, images, caption, link="", dry_run=True):
        self.many.append(list(images))
        return PublishResult(self.name, True, dry_run, remote_id="9",
                             url="https://ig/p/carousel", image_url="https://v/ig/a.jpg")

    def media_stats(self, media_id):
        return {"likes": 1, "comments": 0, "permalink": "https://ig/p/carousel"}

    def publishing_limit(self):
        return {"used": 0, "limit": 100}


class CarouselFlowTest(unittest.TestCase):
    """묶음이 원장을 거쳐 '한 게시물 여러 장' 으로 나가는지."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = {(queue, "LEDGER"): queue.LEDGER, (daemon, "INBOX"): daemon.INBOX,
                      (daemon, "APPROVED_DIR"): daemon.APPROVED_DIR, (daemon, "STATUS"): daemon.STATUS,
                      (daemon, "LOCK"): daemon.LOCK, (daemon, "LAB_DIR"): daemon.LAB_DIR,
                      (base, "EXPOSED"): base.EXPOSED}
        queue.LEDGER = self.tmp / "state" / "publish_queue.json"
        daemon.LAB_DIR, daemon.INBOX = self.tmp, self.tmp / "inbox"
        daemon.APPROVED_DIR = self.tmp / "state" / "approved"
        daemon.STATUS, daemon.LOCK = self.tmp / "state" / "s.json", self.tmp / "state" / "l"
        base.EXPOSED = self.tmp / "exposed"
        self.conf = {**daemon.settings({}), "live": True}
        d = daemon.INBOX / "cccc0001"
        d.mkdir(parents=True)
        (d / "poster.jpg").write_bytes(JPEG)                      # 표지
        for i in (1, 2, 3):
            (d / f"slide_{i:02d}.jpg").write_bytes(JPEG)          # 공고 판
        (d / "bundle.json").write_text(json.dumps({
            "id": "cccc0001", "job_key": "collection:week-20260916",
            "company": "이번 주 채용", "role": "9월 14–20일", "platforms": ["instagram"],
            "captions": {"instagram": "묶음 캡션"},
            "collection": {"kind": "week", "count": 3}}), encoding="utf-8")

    def tearDown(self):
        for (mod, name), value in self.saved.items():
            setattr(mod, name, value)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_all_slides_go_out_as_one_post_in_order(self):
        daemon.ingest([])
        item = queue.get("cccc0001")
        self.assertEqual(item["kind"], "collection")
        self.assertEqual(len(item["images"]), 4, "표지 + 공고 판 3장")
        daemon.schedule(daemon._parse("2026-09-16T09:00"), self.conf, [])
        pub = FakeIG()
        out = daemon.publish_due(daemon._parse("2026-09-17T12:31"), {}, self.conf, [],
                                 {"instagram": pub})
        self.assertEqual(out["status"], "published")
        self.assertEqual(len(pub.many), 1, "게시물 하나로 나간다")
        self.assertEqual([p.name for p in pub.many[0]],
                         ["cccc0001.jpg", "cccc0001_slide_01.jpg",
                          "cccc0001_slide_02.jpg", "cccc0001_slide_03.jpg"])
        self.assertEqual(pub.single, [], "장별로 따로 올리지 않는다")

    def test_collection_is_not_dropped_when_one_job_closes(self):
        daemon.ingest([])
        n = daemon.drop_closed([], status_of=lambda key: "closed")
        self.assertEqual(n, 0)
        self.assertEqual(queue.get("cccc0001")["status"], "approved")


class InstagramCarouselTest(unittest.TestCase):
    def make(self, statuses):
        pub = InstagramPublisher({"public_base_url": "https://v.example/ig",
                                  "instagram": {"ig_user_id": "42", "access_token": "T"}})
        pub.sleep = lambda s: None
        pub.public_url_for = lambda image: f"https://v.example/ig/{image.name}"
        calls, seq = [], list(statuses)

        def fake(url, data=None, method="POST", **_):
            calls.append((method, url.rsplit("/", 1)[-1], (data or {}).get("media_type",
                          "item" if (data or {}).get("is_carousel_item") else "")))
            if url.endswith("/media"):
                return {"json": {"id": "CAR" if (data or {}).get("media_type") == "CAROUSEL"
                                 else f"C{len(calls)}"}}
            if url.endswith("/media_publish"):
                return {"json": {"id": "M1"}}
            if url.endswith("/M1"):
                return {"json": {"permalink": "https://www.instagram.com/p/car/"}}
            return {"json": {"status_code": seq.pop(0) if seq else "FINISHED"}}

        pub._request = fake
        return pub, calls

    def images(self, n):
        d = Path(tempfile.mkdtemp())
        out = []
        for i in range(n):
            p = d / f"{i:02d}.jpg"
            p.write_bytes(JPEG)
            out.append(p)
        return out

    def test_children_then_carousel_then_publish(self):
        pub, calls = self.make([])
        res = pub.publish_many(images=self.images(3), caption="c", dry_run=False)
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.url, "https://www.instagram.com/p/car/")
        kinds = [c[2] for c in calls if c[1] == "media"]
        self.assertEqual(kinds, ["item", "item", "item", "CAROUSEL"])
        self.assertTrue(any(c[1] == "media_publish" for c in calls))

    def test_more_than_ten_is_refused_before_any_call(self):
        pub, calls = self.make([])
        res = pub.publish_many(images=self.images(11), caption="c", dry_run=False)
        self.assertFalse(res.ok)
        self.assertIn("10장", res.error)
        self.assertEqual(calls, [])

    def test_dry_run_sends_nothing(self):
        pub, calls = self.make([])
        res = pub.publish_many(images=self.images(3), caption="c", dry_run=True)
        self.assertTrue(res.ok and res.dry_run)
        self.assertEqual(calls, [])
        self.assertEqual([s["step"] for s in res.steps],
                         ["create_items", "create_carousel", "publish_media"])


if __name__ == "__main__":
    unittest.main()
