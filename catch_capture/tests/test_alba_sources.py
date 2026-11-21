"""컴퓨터 알바 모음의 새 출처(알바천국·알바몬·사람인·잡코리아)와 출처 공통 동작 — 네트워크 없이 본다.

픽스처(tests/fixtures/alba/)는 2026-11-21 실제 응답을 줄인 것이다. 상호·주소·연락처는 가짜로 바꿨다
(알바몬 목록의 담당자 휴대폰 칸은 일부러 가짜 번호로 남겼다 — 저장되지 않는 것을 보려고).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from crawlers import crawl_alba as ca
from crawlers.alba import albacheonguk as ac
from crawlers.alba import albamon as am
from crawlers.alba import common as C
from crawlers.alba import jobkorea as jk
from crawlers.alba import saramin as sr

FX = Path(__file__).parent / "fixtures" / "alba"
NOW = "2026-11-21T10:00:00+09:00"
TODAY = "2026-11-21"


def fx(name: str) -> str:
    return (FX / name).read_text(encoding="utf-8")


# ── robots(가장 긴 규칙이 이긴다) ─────────────────────────────────────

ALBA_ROBOTS = """User-agent: *
Disallow: /

Allow: /$
Allow: /job/
Allow: /search/

User-agent: Yeti
Allow: /
"""
ALBAMON_ROBOTS = """User-agent: ClaudeBot
User-agent: GPTBot
Disallow: /

User-agent: *
Disallow: /jobs/detail/*?*keyword
Disallow: /jobs/detail-content
Disallow: /jobs/apply/
"""


def test_robots_longest_match_allows_under_disallow_all():
    """`Disallow: /` 아래에 연 Allow 가 이긴다 — robotparser(첫 줄 우선)는 이걸 전부 막힌 것으로 읽는다."""
    r = C.Robots(ALBA_ROBOTS)
    assert r.allowed("https://www.alba.co.kr/job/occupation/List?jobKind=18000000&page=2")
    assert r.allowed("https://www.alba.co.kr/job/Detail?adid=148300527")
    assert r.allowed("https://www.alba.co.kr/")
    assert not r.allowed("https://www.alba.co.kr/person/resume/Regist")
    assert not r.allowed("https://www.alba.co.kr/Main")            # '/$' 는 첫 화면만 연다


def test_robots_wildcards_and_named_agents_ignored():
    """우리는 `*` 묶음만 따른다(이름 붙은 AI 수집기 묶음은 우리 얘기가 아니다). `*` 와 `?` 가 섞인 규칙도 본다."""
    r = C.Robots(ALBAMON_ROBOTS)
    assert r.allowed("https://www.albamon.com/jobs/part?parts=9000&page=2")
    assert r.allowed("https://www.albamon.com/jobs/detail/120411457")
    assert not r.allowed("https://www.albamon.com/jobs/detail/120411457?keyword=개발")
    assert not r.allowed("https://www.albamon.com/jobs/detail-content/1")
    assert not r.allowed("https://www.albamon.com/jobs/apply/1")


# ── 알바천국 ──────────────────────────────────────────────────────────

def test_albacheonguk_list_rows():
    rows, total = ac.parse_list(fx("albacheonguk_list.html"))
    assert total == 1185
    e = rows["148300527"]
    assert e["title"] == "프로그램 설정 파일 수정 및 적용"
    assert (e["sido"], e["sigungu"]) == ("충남", "천안시 서북구")
    assert e["pay"] == {"amount": 2156880, "unit": "월급", "text": "월급 2,156,880원"}
    assert e["url"] == "https://www.alba.co.kr/job/Detail?adid=148300527"
    assert "테스트회사" not in json.dumps(rows, ensure_ascii=False)   # 상호는 읽지 않는다


def test_albacheonguk_detail_summary_and_parts():
    d = ac.parse_detail(fx("albacheonguk_detail.html"), TODAY)
    assert d["title"] == "프로그램 설정 파일 수정 및 적용"
    assert d["posted_at"] == "2026-11-20T21:01" and d["deadline"] == "2026-12-03"
    assert d["parts"] == ["프로그래머", "QA·테스터·검증"]
    assert d["employment"] == "알바" and d["closed_reason"] is None
    assert d["pay"]["amount"] == 2156880 and d["pay"]["unit"] == "월급"
    # 보드가 단 직종이 전부 컴퓨터 일이면 제목 규칙이 못 정해도 분류된다.
    assert C.classify("설정 파일 적용", d["content"], d["parts"]) == "개발·프로그래밍"


def test_albacheonguk_closed_states():
    html = fx("albacheonguk_detail.html")
    assert ac.parse_detail(html.replace("init('진행'", "init('마감'"), TODAY)["closed_reason"] == "원본 확인: 마감"
    # validThrough 는 여기서 진짜 접수 마감일이다 — 지나면 닫는다.
    assert "마감일 경과(2026-12-03)" in ac.parse_detail(html, "2026-12-04")["closed_reason"]
    with pytest.raises(C.Gone):
        ac.parse_detail('<html><head><title>삭제된 공고입니다.</title></head><body><script>'
                        'alert("삭제된 공고입니다");</script></body></html>', TODAY)


def test_albacheonguk_post_has_no_company_or_street():
    src = ac.AlbaCheonguk()
    rows, _ = ac.parse_list(fx("albacheonguk_list.html"))
    d = ac.parse_detail(fx("albacheonguk_detail.html"), TODAY)
    for k in ("sido", "sigungu", "hours"):
        d[k] = rows["148300527"][k]
    p = C.make_post(src.name, "148300527", rows["148300527"]["url"], d, "개발·프로그래밍", NOW)
    blob = json.dumps(p, ensure_ascii=False)
    for leak in ("테스트회사", "가상구", "가상로", "010-0000-0000", "모집직종"):
        assert leak not in blob
    assert p["id"] == "albacheonguk-148300527" and p["sigungu"] == "천안시 서북구"


# ── 알바몬 ────────────────────────────────────────────────────────────

def test_albamon_list_never_keeps_manager_phone():
    """목록 JSON 에 담당자 휴대폰(managerPhoneNumber)이 그대로 실려 온다 — entry 에도 공고에도 남지 않는다."""
    rows, total = am.parse_list(fx("albamon_list.html"))
    assert total == 2 and set(rows) == {"120411457", "120000001"}
    e = rows["120411457"]
    assert e["title"] == "웹 퍼블리셔 단기 아르바이트 (재택 가능)" and e["parts"] == ["HTML코딩", "웹·모바일디자인"]
    assert (e["sido"], e["sigungu"]) == ("서울", "강남구") and e["deadline"] == "2026-12-04"
    assert e["pay"] == {"amount": 12000, "unit": "시급", "text": "시급 12,000원"}
    assert e["hours"] == "월~금 10:00~16:00"
    d = am.parse_detail(fx("albamon_detail.html"), TODAY)
    p = C.make_post("albamon", "120411457", e["url"], {**e, **d}, "웹·앱 제작", NOW)
    blob = json.dumps([rows, p], ensure_ascii=False)
    for leak in ("010-1234-5678", "010-9876-5432", "managerPhone", "테스트회사", "테스트담당", "가상로",
                 "hr@example.com", "02-000-0000", "37.5"):
        assert leak not in blob


def test_albamon_detail_fields_and_flags():
    html = fx("albamon_detail.html")
    d = am.parse_detail(html, TODAY)
    assert d["title"] == "웹 퍼블리셔 단기 아르바이트 (재택 가능)"
    assert d["posted_at"] == "2026-11-20T18:09:00+09:00" and d["deadline"] == "2026-12-04"
    assert d["parts"] == ["HTML코딩", "웹·모바일디자인"] and d["employment"] == "계약직"
    assert d["opt_out"] is False and d["closed_reason"] is None
    # 작성자가 수집을 막은 공고(crawlingBlock)는 싣지 않는다 — 당근 webCrawlNotAllowed 와 같게.
    assert am.parse_detail(html.replace('"crawlingBlock": false', '"crawlingBlock": true'), TODAY)["opt_out"] is True
    closed = html.replace('"key": "OPEN"', '"key": "CLOSE"').replace("게재중인 공고", "마감된 공고")
    assert am.parse_detail(closed, TODAY)["closed_reason"] == "원본 확인: 마감된 공고"
    assert am.parse_detail(html.replace('"closeStat": false', '"closeStat": true'), TODAY)["closed_reason"]
    assert "마감일 경과" in am.parse_detail(html, "2026-12-05")["closed_reason"]
    with pytest.raises(C.Gone):
        am.parse_detail(fx("albamon_gone.html"), TODAY)


# ── 사람인 ────────────────────────────────────────────────────────────

def test_saramin_list_keeps_only_alba_rows():
    rows = sr.parse_list(fx("saramin_list.html"), date(2026, 11, 21))
    assert list(rows) == ["55557961"]                            # 계약직 광고 줄은 버린다
    e = rows["55557961"]
    assert e["title"] == "기능테스트 - 소프트웨어 기능 테스트 (QA / 테스터)"
    assert (e["sido"], e["sigungu"]) == ("서울", "영등포구") and e["employment"] == "아르바이트"
    assert e["deadline"] == "2026-11-25"
    assert "테스트회사" not in json.dumps(rows, ensure_ascii=False)
    d = sr.Saramin().detail("55557961", e)                       # 새로 받을 때는 원본에 묻지 않는다
    assert C.classify(d["title"], d["content"]) == "개발·프로그래밍" and d["closed_reason"] is None


def test_saramin_recheck_uses_close_check_verdict(monkeypatch):
    s = sr.Saramin()
    monkeypatch.setattr(s.http, "get", lambda url, referer=None: (200, url, "<meta content='마감일:2026-11-01, 홈페이지'>"))
    d = s.recheck({"pid": "1", "url": "u"})
    assert d["closed_reason"].startswith("원본 확인: 마감일 경과")
    monkeypatch.setattr(s.http, "get", lambda url, referer=None: (200, url, "<html>본문만</html>"))
    assert s.recheck({"pid": "1", "url": "u"}) is None          # 판정 불가는 그대로 둔다


# ── 잡코리아 ──────────────────────────────────────────────────────────

def _jk_row(**kw):
    r = {"id": "50360464", "title": "[평일] 시안 제작 디자인 보조 알바 모집", "employmentTypeCodeList": ["7/0"],
         "payTypeCode": 5, "payRange": {"start": "10320", "end": "0"}, "createdAt": "2026-11-13T09:00:00+09:00",
         "applicationPeriod": {"start": "2026-11-13T00:00:00+09:00", "end": "2026-12-13T23:59:00+09:00"},
         "jobClassificationOrIndustry": ",그래픽디자이너,", "postingCompanyName": "테스트회사", "memberId": "test"}
    r.update(kw)
    return r


def test_jobkorea_list_entry_filters_and_pay():
    pid, e = jk.list_entry(_jk_row())
    assert pid == "50360464" and e["deadline"] == "2026-12-13"
    assert e["pay"] == {"amount": 10320, "unit": "시급", "text": "시급 10,320원"}
    assert "테스트회사" not in json.dumps(e, ensure_ascii=False)
    assert jk.list_entry(_jk_row(employmentTypeCodeList=["1/0", "2/1"])) is None      # 아르바이트가 안 붙은 광고
    # 월급·연봉은 만원 단위로 온다.
    assert jk.list_entry(_jk_row(payTypeCode=2, payRange={"start": "230", "end": "500"}))[1]["pay"]["amount"] == 2300000
    assert jk.list_entry(_jk_row(payTypeCode=0, payRange={"start": "0", "end": "0"}))[1]["pay"] is None


def test_jobkorea_detail_region_and_verdict():
    d = jk.parse_detail(fx("jobkorea_detail.html"), date(2026, 11, 21))
    assert (d["sido"], d["sigungu"]) == ("전북", "전주시 덕진구")
    assert d["deadline"] == "2026-12-13" and d["closed_reason"] is None and d["employment"] == "아르바이트"
    assert d["posted_at"] == "2026-11-13"
    late = jk.parse_detail(fx("jobkorea_detail.html"), date(2026, 12, 14))
    assert late["closed_reason"].startswith("원본 확인: 마감일 경과")


# ── 분류(보드 제목) ───────────────────────────────────────────────────
# 2026-11-21 실제 목록에서 고른 제목. 보드 제목은 당근보다 형식적이다('…채용', '…모집').

@pytest.mark.parametrize("title, cat", [
    ("기능테스트 - 소프트웨어 기능 테스트 (QA / 테스터) 단기 아르바이트", "개발·프로그래밍"),
    ("웹프로그래머 모잡(asp,php,jsp,앱등,경력자우대,재택가능)", "개발·프로그래밍"),
    ("[울산 고사동/SK계열사] PC 단순 장애/오류 처리 OA 헬프데스크", "개발·프로그래밍"),
    ("(용인) 글로벌자동차 IT Helpdesk 초/중급", "개발·프로그래밍"),
    ("[국회의사당역인근/중견기업/주5일/성과급지급] 웹퍼블리셔 채용", "웹·앱 제작"),
    ("[LG U+]웹 디자이너 아르바이트 채용/마곡사옥/주5회 출근/재택X", "디자인·영상"),
    ("광고디자이너 모집", "디자인·영상"),
    ("[노량진] 공단기 강의 편집/인코딩 아르바이트 모집", "디자인·영상"),
    ("[iMBC/콘텐츠제작팀] SMR 클립제작 부문 채용 (신입 가능)", "디자인·영상"),
    ("IBM 아래한글 교재편집자 알바생 모집합니다", "디자인·영상"),
    ("[프리랜서] 교통표지판 바운딩박스 및 속성 입력 작업자 모집", "데이터·사무자동화"),
    ("11/23(월) 동덕여자대학교 PC 설치 아르바이트 모집", "PC·기기 지원"),
    ("교육기관 컴퓨터 유지보수 및 학내망 관리 사원을 모집합니다.", "PC·기기 지원"),
    ("초,중,고 코딩 강사 급구(시급 4만, 주부, 신입 환영)", "코딩·IT 강사"),
    ("카페24 홈페이지 관리 및 상품등록 및 스마트스토어 관리", "홈페이지·쇼핑몰 운영"),
])
def test_classify_board_titles(title, cat):
    assert C.classify(title) == cat


@pytest.mark.parametrize("title", [
    "[업무선택가능] 카카오 지갑/구독서비스 이용 관련 문의 상담 QKZa",       # 콜센터 — IT·인터넷 분류에 섞여 온다
    "[재택/프리랜서] SNS 바이럴 단순 알바 (부업/마케팅/비용X/초보O)",
    "[부업 / 투잡 / 재택] 어플 테스트 체험단 인원 모집 합니다",
    "[국비지원/기숙사무료]AI심화/데이터분석/인공지능/풀스택 개발자 과정",   # 학원 광고
    "채용연계형 첨단의료+AI 부트캠프 모집",
    "[역삼역] AI 단순 데이터수집 보조 다수 채용(주간)",                      # 로봇 동작 수집 — 현장 일
    "[대전 유성구] AI로봇 데이터수집 오퍼레이터",
    "[CJ올리브영 본사] 매거진 업무 지원 + 사무보조 채용(3개월)",
    "실내 인테리어 설계 디자이너 경력 모집",
    "[SBS A&T/일산] 무대디자인팀 세트디자이너 3명 채용",
    "식품제조 품질관리(QA) HACCP 해썹 경력사원",
    "11/17(화) 경희대학교(서울) PC장비 철수/상차 아르바이트",
    "[프리캐스트콘크리트(PC) 몰드 제작업체] 관리자",
    "[단기 전화 아르바이트 모집(전화,엑셀입력)]",
    "가죽공예 핸드백 디자인 가방 제작보조",
    "lifestyle curation어플 개발 참여자 모집(최대 10만원)",
    "[대전/MBN미디어텍] 영상취재부 VJ 채용(뉴스/취재현장/촬영)",
])
def test_classify_board_noise(title):
    assert C.classify(title) is None


def test_teaching_needs_a_teaching_role():
    """3판 — '교육'·'강의'·'수업'만으로는 강사가 아니다(회사명 '디딤돌교육', '수업 모니터링')."""
    assert C.classify("[디딤돌교육] 디자인팀 편집디자인(인디자인, 포토샵) 보조 아르바이트") == "디자인·영상"
    assert C.classify("[재택가능] AI 기반 실시간 수업 모니터링 파트타이머 모집") != "코딩·IT 강사"
    assert C.classify("엑셀 수업 해 주실 분 구해요") == "코딩·IT 강사"


def test_board_parts_rule():
    """보드 직종은 전부 컴퓨터 일이고 그중 강한 것이 있을 때만 쓴다. 순서가 우선순위다."""
    assert C.classify("서비스 운영 담당", parts=["프로그래머", "사이트관리·기술지원"]) == "개발·프로그래밍"
    assert C.classify("보안모니터링 직원 채용", parts=["HTML코딩", "QA·테스터·검증", "시스템·네트워크·보안"]) == "개발·프로그래밍"
    assert C.classify("신용사업부 사무업무", parts=["사이트관리·기술지원"]) is None           # 약한 직종 하나
    assert C.classify("행사 진행 요원", parts=["프로그래머", "전시·컨벤션·세미나"]) is None     # 컴퓨터 일이 아닌 직종이 섞였다


# ── 지역·중복·이관·마감일 ─────────────────────────────────────────────

@pytest.mark.parametrize("addr, want", [
    ("경기 화성시 만세구", ("경기", "화성시 만세구")),
    ("서울 강남구 테헤란로 509", ("서울", "강남구")),
    ("전남광주 동구", ("광주·전남", "동구")),
    ("서울특별시 마포구", ("서울", "마포구")),
    ("전국 전체", ("", "")),
    ("충남 천안시 서북구", ("충남", "천안시 서북구")),
])
def test_split_region(addr, want):
    assert C.split_region(addr) == want


def _p(source, pid, title, sido="서울", sigungu="강남구", status="open", first="2026-11-20T00:00:00+09:00"):
    return {"id": f"{source}-{pid}", "source": source, "pid": pid, "title": title, "sido": sido, "sigungu": sigungu,
            "status": status, "first_seen_at": first}


def test_mark_dups_keeps_both_and_points_to_representative():
    rows = [_p("albamon", "1", "[급구] 웹 퍼블리셔 단기 아르바이트"), _p("jobkorea", "2", "웹 퍼블리셔 단기 아르바이트"),
            _p("daangn", "x", "웹 퍼블리셔 단기 아르바이트", status="closed"),
            _p("saramin", "3", "웹 퍼블리셔 단기 아르바이트", sido="부산", sigungu="중구")]
    assert C.mark_dups(rows) == 2
    by = {p["id"]: p for p in rows}
    # 대표는 모집중 → 출처 순서(당근이 앞이지만 마감) — 알바몬. 지역이 다른 사람인은 다른 공고다.
    assert "dup_of" not in by["albamon-1"]
    assert by["jobkorea-2"]["dup_of"] == by["daangn-x"]["dup_of"] == "albamon-1"
    assert "dup_of" not in by["saramin-3"]
    assert len(rows) == 4                                        # 지우지 않는다


def test_migrate_daangn_ids_once():
    doc = {"posts": [{"id": "abc123def456", "title": "홈페이지 제작"}]}
    state = {"rejected": {"zzz": "슬러그"}, "lastmod": {"abc123def456": "2026-11-20"}, "sitemap_count": 40000,
             "rules_version": 2}
    posts, st = ca.migrate(doc, state)
    assert posts[0]["id"] == "daangn-abc123def456" and posts[0]["pid"] == "abc123def456"
    assert st["sources"]["daangn"]["listing_count"] == 40000 and st["sources"]["daangn"]["rejected"] == {"zzz": "슬러그"}
    again, st2 = ca.migrate({"posts": posts}, st)                # 두 번 돌려도 그대로
    assert again[0]["id"] == "daangn-abc123def456" and st2 is st


def test_expire_by_deadline():
    p = {"status": "open", "deadline": "2026-11-20", "history": []}
    assert C.expire_by_deadline(p, TODAY, NOW) and p["status"] == "closed" and p["closed_reason"] == "마감일 경과(2026-11-20)"
    q = {"status": "open", "deadline": "2026-11-21", "history": []}
    assert not C.expire_by_deadline(q, TODAY, NOW) and q["status"] == "open"     # 그날까지는 연다


# ── 출처마다 따로: 하나가 실패해도 나머지는 돈다 ───────────────────────

class _Fake(C.Source):
    name = "fake"
    label = "가짜"

    def __init__(self, rows=None, boom=False, detail_boom=False):
        super().__init__()
        self.rows, self.boom, self.detail_boom = rows or {}, boom, detail_boom
        self.rechecked = []

    def listing(self):
        if self.boom:
            raise RuntimeError("목록 깨짐")
        self.complete = True
        return self.rows

    def detail(self, pid, e):
        if self.detail_boom:
            raise RuntimeError("상세 깨짐")
        return {"title": e["title"], "sido": "서울", "sigungu": "강남구", "closed_reason": None, "opt_out": False}

    def recheck(self, p):
        self.rechecked.append(p["pid"])
        return {"closed_reason": None}


def test_run_source_listing_failure_still_rechecks():
    src = _Fake(boom=True)
    posts = {"1": C.make_post("fake", "1", "u", {"title": "웹 디자이너"}, "디자인·영상", "2026-11-01T00:00:00+09:00")}
    rep = C.run_source(src, posts, {}, NOW, new_limit=10, recheck_limit=10)
    assert rep["ok"] is False and "목록 깨짐" in rep["error"]
    assert src.rechecked == ["1"] and posts["1"]["status"] == "open"   # 목록이 없어도 '사라짐'으로 닫지 않는다


def test_run_source_new_and_rejected_signature():
    src = _Fake(rows={"1": {"url": "u1", "title": "웹 디자이너 아르바이트"}, "2": {"url": "u2", "title": "홀서빙 구해요"},
                      "3": {"url": "u3", "title": "컴퓨터 사무 직원"}})
    posts, st = {}, {}
    rep = C.run_source(src, posts, st, NOW, new_limit=10, recheck_limit=10)
    assert rep["new"] == 1 and set(posts) == {"1"} and posts["1"]["id"] == "fake-1"
    assert st["rejected"] == {"3": "컴퓨터 사무 직원"}                  # 2 는 1차 후보도 아니다
    assert st["rules_version"] == C.RULES_VERSION


def test_crawl_run_isolates_failing_source(tmp_path, monkeypatch):
    """한 출처가 통째로 터져도(예외) 다른 출처의 신규는 실리고, 실패 출처는 failed 에 남는다."""
    class Good(_Fake):
        name = "good"

        def __init__(self):
            super().__init__(rows={"7": {"url": "u7", "title": "유튜브 영상 편집 알바"}})

    class Bad(_Fake):
        name = "bad"

        def listing(self):
            raise MemoryError("통째로 터짐")

    monkeypatch.setattr(C, "OUT_PATH", tmp_path / "alba.json")
    monkeypatch.setattr(C, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(C, "LOCK_PATH", tmp_path / "alba.lock")
    monkeypatch.setattr(ca, "SOURCES", {"good": Good, "bad": Bad})
    monkeypatch.setattr(ca, "LABELS", {"good": "좋음", "bad": "나쁨"})
    stats = ca.run(new_limit=5, recheck_limit=5)
    assert stats["ok"] is True and stats["failed"] == ["bad"] and stats["new"] == 1
    out = json.loads((tmp_path / "alba.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in out["posts"]] == ["good-7"] and out["sources"]["bad"]["ok"] is False
    assert out["source_labels"] == {"good": "좋음", "bad": "나쁨"}


def test_open_only_listing_reasks_closed_posts_seen_again():
    """알바천국·알바몬 목록에는 모집중만 실린다 — 마감일 경과로 닫은 공고가 목록에 다시 보이면(연장) 다시 묻는다."""
    posts = {"1": {"status": "closed", "checked_at": "2026-11-20"}, "2": {"status": "closed", "checked_at": "2026-11-20"}}
    entries = {"1": {"url": "u"}}
    assert C.plan_recheck(posts, entries, {}, listing_ok=True, skip=set(), limit=5, open_only=True) == ["1"]
    assert C.plan_recheck(posts, entries, {}, listing_ok=True, skip=set(), limit=5) == []


@pytest.mark.parametrize("title", [
    "디자이너가행복한 헤어샵 (매곡점신규.풍암.운남점 )", "미용실 경력 디자이너", "콘택트렌즈 디자이너 구해요!",
    "리폼 의류 해체 및 디자인 작업 가능하신분 구합니다", "배달전문점 외계인피자 야간직원 모집합니다(상세페이지",
])
def test_rules_v4_hair_and_shop_designers(title):
    """4판 — 맨 '디자이너'는 모호한 쪽이고, 헤어·렌즈·수선은 막는다. 제목에 상세페이지가 '참고'로만 있는 것도."""
    assert C.classify(title) is None


def test_rules_v4_bare_designer_needs_content_or_board():
    assert C.classify("디자이너 모집") is None
    assert C.is_candidate("디자이너 모집")                       # 본문·보드 직종까지 본다
    assert C.classify("디자이너 모집", parts=["웹·모바일디자인"]) == "디자인·영상"
    assert C.classify("디자이너 모집", "포토샵·일러스트로 상세페이지 제작") == "디자인·영상"
    assert C.classify("광고디자이너 모집") == C.classify("편집 디자이너 구인") == "디자인·영상"


def test_rules_change_purges_vetoed_titles_and_recheck_drops_unclassified():
    src = _Fake()
    posts = {"1": C.make_post("fake", "1", "u", {"title": "미용실 경력 디자이너"}, "디자인·영상", NOW),
             "2": C.make_post("fake", "2", "u", {"title": "웹 디자이너"}, "디자인·영상", NOW)}
    rep = C.run_source(src, posts, {"rules_version": C.RULES_VERSION - 1}, "2026-11-22T10:00:00+09:00", 0, 0)
    assert rep["purged"] == 1 and set(posts) == {"2"}
    p = C.make_post("fake", "3", "u", {"title": "디자이너 모집"}, "디자인·영상", NOW)
    assert C.apply_check(p, {"title": "디자이너 모집", "content": "커트·펌 가능하신 분"}, None, NOW) == "drop"


def test_albacheonguk_detail_without_jsonld_falls_back_to_page():
    """JSON-LD 가 없는 공고 — <title> 의 제목과 화면의 모집마감만 읽는다(상호는 버린다)."""
    html = ("<html><head><title>테스트회사 채용정보 : [아르바이트] 상세페이지편집 - 알바천국</title></head>"
            "<body onload=\"init('진행', '')\"><dl><dt class=\"detail-def__term\">모집마감</dt>\n"
            "<dd class=\"detail-def__data\"><div class=\"detail-period\">\n 2026.11.26(목)\n</div></dd></dl></body></html>")
    d = ac.parse_detail(html, TODAY)
    assert d["title"] == "[아르바이트] 상세페이지편집" and d["deadline"] == "2026-11-26" and d["closed_reason"] is None
    assert "테스트회사" not in json.dumps(d, ensure_ascii=False)
    assert ac.parse_detail(html, "2026-11-27")["closed_reason"] == "원본 확인: 마감일 경과(2026-11-26)"
    assert ac.parse_detail("<html><title>점검 중</title></html>", TODAY) is None
