"""당근알바 IT 공고(crawl_daangn_alba) — 네트워크 없이 파서·분류·마감 판정만 본다."""
from __future__ import annotations

from pathlib import Path

import pytest

from crawlers import crawl_daangn_alba as da

FIXTURE = (Path(__file__).parent / "fixtures" / "daangn_alba_post.html").read_text(encoding="utf-8")
NOW = "2026-11-21T10:00:00+09:00"


# ── 상세 파서 ─────────────────────────────────────────────────────────

def test_parse_detail_summary_fields():
    d = da.parse_detail(FIXTURE)
    assert d["title"] == "홈페이지 제작"
    assert d["pay"] == {"amount": 40000, "unit": "건당", "text": "건당 40,000원"}
    assert (d["sido"], d["sigungu"]) == ("대전", "서구")        # 시/도 줄임 + 시/군/구
    assert d["employment"] == "알바"
    assert d["hours"] == "화·목 10:00~18:00 (협의)"
    assert d["posted_at"] == "2026-11-20T09:42:11.017Z"
    assert d["closed_reason"] is None and d["opt_out"] is False
    assert '"작은"' in d["content"]                             # 이스케이프된 따옴표를 푼다


def test_post_keeps_only_summary():
    """저장하는 공고에는 본문·상호·주소가 없다(약관 — 요약과 링크만)."""
    d = da.parse_detail(FIXTURE)
    p = da.make_post("abc123def456", "https://jobs.daangn.com/job-posts/x-abc123def456", d, "웹·앱 제작", NOW)
    blob = repr(p)
    for leak in ("문의 폼", "테스트상회", "가상동", "가상로", "36.0"):
        assert leak not in blob
    assert set(p) == {"id", "url", "category", "status", "first_seen_at", "last_seen_at", "checked_at",
                      "title", "pay", "sido", "sigungu", "employment", "hours", "posted_at", "history"}


@pytest.mark.parametrize("patch,reason", [
    ("closed:!1", "원본 확인: 모집 마감"),
    ("closedAt:null", "원본 확인: 모집 마감"),
    ("deleted:!1", "원본 삭제"),
    ("hidden:!1", "원본 확인: 숨김·비공개"),
    ('status:"ACCEPTED"', "원본 상태 REJECTED"),
])
def test_closed_flags(patch, reason):
    repl = {"closed:!1": "closed:!0", "closedAt:null": 'closedAt:"2026-11-21T01:00:00.000Z"',
            "deleted:!1": "deleted:!0", "hidden:!1": "hidden:!0",
            'status:"ACCEPTED"': 'status:"REJECTED"'}[patch]
    d = da.parse_detail(FIXTURE.replace(patch, repl, 1))
    assert d["closed_reason"] == reason


def test_opt_out_flag():
    d = da.parse_detail(FIXTURE.replace("webCrawlNotAllowed:!1", "webCrawlNotAllowed:!0"))
    assert d["opt_out"] is True


def test_unparseable_page_is_none():
    assert da.parse_detail("<html><body>점검 중</body></html>") is None


# ── 사이트맵 ──────────────────────────────────────────────────────────

def test_parse_sitemap_strips_id():
    xml = ("<urlset><url><loc>https://jobs.daangn.com/job-posts/%ED%99%88%ED%8E%98%EC%9D%B4%EC%A7%80-"
           "%EC%A0%9C%EC%9E%91-fx182nomj7x3</loc><lastmod>2026-11-20T09:42:11.017Z</lastmod></url>"
           "<url><loc>https://jobs.daangn.com/about</loc></url></urlset>")
    e = da.parse_sitemap(xml)
    assert list(e) == ["fx182nomj7x3"]
    assert e["fx182nomj7x3"]["slug"] == "홈페이지-제작"
    assert e["fx182nomj7x3"]["lastmod"].startswith("2026-11-20")


# ── 분류 ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("title,cat", [
    ("홈페이지 제작", "웹·앱 제작"),
    ("홈페이지 수정가능한 개인 프리랜서 재택 구합니다", "웹·앱 제작"),
    ("대학교 졸업작품 컴퓨터 공학과", "개발·프로그래밍"),
    ("aws 클라우딩 컴퓨터 서비스 코딩 도와주실 분", "개발·프로그래밍"),
    ("유아 코딩교육 강사님 모집합니다", "코딩·IT 강사"),
    ("실무 엑셀 및 워드 및 파워포인트 과외", "코딩·IT 강사"),
    ("fivem 코딩 가르쳐 주실 선생님 구해요", "코딩·IT 강사"),
    ("쇼핑몰-md-겸-웹디자이너", "디자인·영상"),
    ("유튜브 촬영 및 편집", "디자인·영상"),
    ("스마트스토어 쿠팡 관리경력자구함", "홈페이지·쇼핑몰 운영"),
    ("문서정리 및 ai활용 제안서 작업", "데이터·사무자동화"),
    ("컴퓨터 재조립 및 선정리", "PC·기기 지원"),
])
def test_classify_it(title, cat):
    assert da.classify(title) == cat


@pytest.mark.parametrize("title", [
    "활기차고 밝은 홀서빙 구해요",            # '서버' 가 아니라 서빙
    "홀-서버-구합니다",
    "온라인 쇼핑몰 택배 포장 물품정리 알바 구합니다",
    "창고정리 엑셀가능하신분",
    "삼성전자 화성캠퍼스 자동화설비 구인공고",
    "의류 쇼핑몰 촬영 알바 초보환영",
    "전산응용건축제도기능사 실기 도와주실 분 구합니다",
    "홈레코딩세트 연결해주실분",
    "방문 자바라 문 설치해주실 분 구합니다",
    "2020 bmw x2 f39 코딩해주실분",
    "크라우드pc방 야간알바구합니다",
    "엑셀 방송 1:1 춤선생님 구해요",
    "신문편집자 건당지급",
    "세종시교육청평생교육원 ai 체험존 단기알바",
])
def test_classify_not_it(title):
    assert da.classify(title) is None


def test_slug_id_noise_is_ignored():
    """슬러그 끝의 무작위 id 에 'it'·'ai'·'gpt' 가 들어 있어도 후보가 아니다."""
    e = da.parse_sitemap("<loc>https://jobs.daangn.com/job-posts/%ED%99%80%EC%84%9C%EB%B9%99-5ufgptwxm3pn</loc>")
    assert not da.is_candidate(e["5ufgptwxm3pn"]["slug"])


def test_ambiguous_title_uses_content_only_in_memory():
    assert da.classify("컴퓨터 잘 다루시는 분") == "PC·기기 지원"
    assert da.classify("컴퓨터 사무 직원") is None
    assert da.classify("컴퓨터 사무 직원", "네이버 스마트스토어 상품 등록과 관리를 맡아요") == "홈페이지·쇼핑몰 운영"
    # 본문으로 '강사'는 정하지 않는다('교육'·'선생님'은 어느 본문에나 있다).
    assert da.classify("AI 시대 함께할 분", "AI 교육 플랫폼에서 선생님을 모십니다") is None
    # '온라인'만으로는 본문까지 보지 않는다.
    assert da.classify("온라인 쇼핑몰 정직원 모집", "스마트스토어 상품 등록 관리") is None
    assert da.is_candidate("컴퓨터-작업")                      # 모호하면 상세까지 본다
    assert not da.is_candidate("주방보조-구합니다")


# ── 마감·재확인 ───────────────────────────────────────────────────────

def _post(**kw):
    d = da.parse_detail(FIXTURE)
    p = da.make_post("abc123def456", "https://jobs.daangn.com/job-posts/x-abc123def456", d, "웹·앱 제작",
                     "2026-11-20T10:00:00+09:00")
    p.update(kw)
    return p


def test_apply_check_closes_and_keeps_history():
    p = _post()
    d = da.parse_detail(FIXTURE.replace("closed:!1", "closed:!0", 1))
    assert da.apply_check(p, d, None, NOW) == "closed"
    assert p["status"] == "closed" and p["closed_at"] == NOW and p["closed_reason"] == "원본 확인: 모집 마감"
    assert [h["status"] for h in p["history"]] == ["open", "closed"]
    # 다시 물어도 마감 시각은 그대로, 이력도 더 안 쌓인다.
    assert da.apply_check(p, d, None, "2026-11-22T10:00:00+09:00") == "closed"
    assert p["closed_at"] == NOW and len(p["history"]) == 2


def test_apply_check_closed_at_from_source():
    p = _post()
    d = da.parse_detail(FIXTURE.replace("closedAt:null", 'closedAt:"2026-11-21T01:00:00.000Z"', 1))
    da.apply_check(p, d, None, NOW)
    assert p["closed_at"] == "2026-11-21T01:00:00.000Z"


def test_apply_check_gone_and_reopen():
    p = _post()
    assert da.apply_check(p, None, "원본 삭제(HTTP 404)", NOW) == "closed"
    assert p["closed_reason"] == "원본 삭제(HTTP 404)"
    d = da.parse_detail(FIXTURE)
    assert da.apply_check(p, d, None, "2026-11-22T10:00:00+09:00") == "open"
    assert p["status"] == "open" and "closed_at" not in p


def test_apply_check_opt_out_drops_and_unknown_keeps():
    p = _post()
    d = da.parse_detail(FIXTURE.replace("webCrawlNotAllowed:!1", "webCrawlNotAllowed:!0"))
    assert da.apply_check(p, d, None, NOW) == "drop"
    q = _post()
    assert da.apply_check(q, None, None, NOW) == "unknown" and q["status"] == "open"


def test_apply_check_updates_pay_history():
    p = _post()
    d = da.parse_detail(FIXTURE.replace("건당 40,000원", "건당 50,000원").replace("salary:40000", "salary:50000"))
    da.apply_check(p, d, None, NOW)
    assert p["pay"]["amount"] == 50000
    assert [h["pay"] for h in p["history"]] == ["건당 40,000원", "건당 50,000원"]


def test_plan_recheck_order():
    posts = {
        "gone00000001": _post(id="gone00000001"),
        "chg000000001": _post(id="chg000000001", status="closed"),
        "old000000001": _post(id="old000000001", checked_at="2026-11-01T00:00:00+09:00"),
        "new000000001": _post(id="new000000001", checked_at="2026-11-20T00:00:00+09:00"),
        "closed000001": _post(id="closed000001", status="closed"),
    }
    entries = {k: {"url": "u", "slug": "s", "lastmod": "2026-11-20"} for k in posts if k != "gone00000001"}
    entries["chg000000001"]["lastmod"] = "2026-11-21"
    seen = {k: "2026-11-20" for k in posts}
    order = da.plan_recheck(posts, entries, seen, sitemap_ok=True, skip=set(), limit=2)
    # 사라진 것 → lastmod 바뀐 것(마감 포함) → 오래 안 물어본 모집중. 마감·변화 없는 것은 묻지 않는다.
    assert order == ["gone00000001", "chg000000001", "old000000001"]
    # 사이트맵이 깨져 보이면 '사라짐' 으로 묻지 않는다.
    assert "gone00000001" not in da.plan_recheck(posts, entries, seen, sitemap_ok=False, skip=set())


# ── 회차 사이 재확인(launchd albacheck) ───────────────────────────────

def test_run_skips_when_another_holds_the_lock(tmp_path, monkeypatch):
    """회차 안과 회차 사이가 겹치면 뒤에 온 쪽이 건너뛴다 — alba.json 을 덮어 마감 판정을 지우지 않게."""
    lock = tmp_path / "alba.lock"
    monkeypatch.setattr(da, "LOCK_PATH", lock)
    monkeypatch.setattr(da, "_run", lambda *a, **k: pytest.fail("잠금을 못 잡았는데 돌았다"))
    with open(lock, "a+") as fh:
        assert da._try_lock(fh)
        res = da.run()
    assert res["skipped"] is True and res["ok"] is True


def test_check_fetches_no_new_posts(tmp_path, monkeypatch):
    """--check 는 새 공고를 받지 않고(new_limit=0) 재확인만 한다."""
    seen = {}
    monkeypatch.setattr(da, "LOCK_PATH", tmp_path / "alba.lock")
    monkeypatch.setattr(da, "_run", lambda new_limit, recheck_limit: seen.update(new=new_limit, re=recheck_limit)
                        or {"ok": True, "total": 1, "open": 1, "new": 0, "closed_now": 0})
    import store.ingest.docs as docs
    monkeypatch.setattr(docs, "sync", lambda *a, **k: {})
    da.check(42)
    assert seen == {"new": 0, "re": 42}
