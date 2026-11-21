"""IT·디자인 공모전(crawl_contests) — 네트워크 없이 파서·분류·마감·중복 판정만 본다."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from crawlers import crawl_contests as cc

FIX = Path(__file__).parent / "fixtures"
NOW = "2026-11-21T10:00:00+09:00"
TODAY = date(2026, 11, 21)


def _fx(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


# ── 씽굿 ──────────────────────────────────────────────────────────────

def test_thinkcontest_list_keeps_summary_only():
    rows, total, per = cc.tc_parse_list(_fx("contests_thinkcontest_list.json"))
    assert (total, per, len(rows)) == (23, 10, 3)
    r = rows[0]
    assert r["sid"] == "112051" and r["title"] == "나무엑스 AI 숏폼 공모전"
    assert r["url"] == "https://www.thinkcontest.com/thinkgood/user/contest/view.do?contest_pk=112051"
    assert (r["host"], r["prize"], r["target"]) == ("SK인텔릭스(주)", "300만원", "대학생·대학원생·일반인")
    assert (r["period_start"], r["period_end"]) == ("2026-10-19", "2026-11-22")
    c = cc.make_contest("thinkcontest", r, r, "영상·콘텐츠", NOW)
    blob = repr(c)
    for leak in ("fake-contact", "01000000000", "홍길동", "가상회사", "요강 본문"):   # 연락처·담당자·요강은 버린다
        assert leak not in blob
    assert c["id"] == "thinkcontest-112051"


def test_thinkcontest_list_fallbacks():
    rows, _, _ = cc.tc_parse_list(_fx("contests_thinkcontest_list.json"))
    r = rows[2]
    assert r["host"] == "(재)테스트재단"                                    # HTML 엔티티를 푼다
    assert (r["period_start"], r["period_end"]) == ("2026-12-01", "2027-01-15")  # finish_dt 가 없으면 receive_period
    assert r["target"] == "초등학생·중학생·고등학생·동 연령대 청소년 외"
    assert rows[1]["target"] == "제한 없음"


def test_thinkcontest_list_failure_raises():
    with pytest.raises(RuntimeError):
        cc.tc_parse_list('{"msg":"데이타 호출에 실패하였습니다","status":"0"}')


def test_thinkcontest_detail():
    d = cc.tc_parse_detail(_fx("contests_thinkcontest_view.html"))
    assert d == {"title": "나무엑스 AI 숏폼 공모전", "host": "SK인텔릭스(주)", "fields": "기획/아이디어, 디자인, 영상/UCC",
                 "prize": "300만원", "target": "대학생·대학원생·일반인",
                 "period_start": "2026-10-19", "period_end": "2026-11-22"}


@pytest.mark.parametrize("parse,page", [
    (cc.tc_parse_detail, '<script>alert("없는 게시글이거나 이미 삭제된 게시글입니다.");</script>'),
    (cc.wv_parse_detail, "<script>window.alert('이미 삭제된 데이터입니다.\\n다시 시도하시기 바랍니다.');</script>"),
    (cc.ck_parse_detail, "<script language='javascript'>alert('자료가 존재하지 않습니다.');window.location.href='/';</script>"),
])
def test_removed_pages_are_gone(parse, page):
    with pytest.raises(cc.Gone):
        parse(page)


# ── 위비티 ────────────────────────────────────────────────────────────

def test_wevity_list():
    rows, pages = cc.wv_parse_list(_fx("contests_wevity_list.html"))
    assert [r["sid"] for r in rows] == ["112438", "112294"]          # 머리 줄(li.top)은 건너뛴다
    assert rows[1]["title"] == "2026 서울관광 프롬프톤"
    assert rows[1]["fields"] == "웹/모바일/IT" and rows[1]["host"] == "서울관광재단"
    assert rows[1]["state"] == "ing" and cc.dday_end(rows[1]["dday"], TODAY) == "2026-11-30"
    assert rows[0]["url"] == "https://www.wevity.com/?c=find&s=1&gbn=view&ix=112438"
    assert pages == [1, 2]


def test_wevity_detail():
    d = cc.wv_parse_detail(_fx("contests_wevity_view.html"))
    assert d["title"] == "2026년 서울교육 AI 활용 공모전"
    assert (d["period_start"], d["period_end"]) == ("2026-11-16", "2026-12-11")
    assert d["prize"] == "다양한 혜택"                 # 주석 처리된 칸(<!--li>참가조건</li-->)에 안 먹힌다
    assert d["host"] == "서울특별시동부교육지원청" and d["target"] == "기타"


# ── 콘테스트코리아 ────────────────────────────────────────────────────

def test_contestkorea_list():
    rows, last = cc.ck_parse_list(_fx("contests_contestkorea_list.html"))
    assert last == 4
    assert [r["state"] for r in rows] == ["접수중", "마감임박", "마감임박"]  # 스타일이 붙은 D-day 도 읽는다
    r = rows[0]
    assert r["sid"] == "202610010030" and r["title"] == "제1회 중앙일보 어린이 미술대회"
    assert r["fields"] == "미술•디자인•웹툰" and r["host"] == "중앙일보"
    assert r["url"].endswith("Txt_bcode=030610001&str_no=202610010030")
    assert cc.dday_end(rows[1]["dday"], TODAY) == "2026-11-22"


def test_contestkorea_detail():
    d = cc.ck_parse_detail(_fx("contests_contestkorea_view.html"))
    assert d["title"] == "2026 saaskr 게임 어워드"
    assert (d["period_start"], d["period_end"]) == ("2026-10-21", "2026-12-20")
    assert d["prize"] == "수상확인서 및 메인 배너"     # '기타 :' 머리를 뗀다
    assert d["target"] == "제한 없음" and d["host"] == "saaskr"


# ── 분류 ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("title,fields,cat", [
    ("2026 서울관광 프롬프톤", "", "해커톤"),
    ("2027 제 2회 Superb AI X BDAI Vision AI 해커톤", "", "해커톤"),
    ("2026 saaskr 게임 어워드 - AI로 만든 웹게임", "", "앱·게임"),
    ("2027 청소년 앱 개발 챌린지", "", "앱·게임"),
    ("나무엑스 AI 숏폼 공모전", "", "영상·콘텐츠"),               # AI 로 만드는 영상은 영상
    ("2026 SCENE AI·실사 웹드라마 공모전", "", "영상·콘텐츠"),
    ("대한민국 수목원·정원 숏폼 영상 공모전", "", "영상·콘텐츠"),    # 정원은 디자인에만 거부권
    ("2027 춘천마임축제 메인포스터 디자인 공모전", "", "디자인·UI"),
    ("쉽고 바른 정보통신기술(ICT) 공공언어 웹툰 공모전", "", "디자인·UI"),
    ("산돌구름 레터링 공모전", "", "디자인·UI"),
    ("제6회 플라이하이 AI 패션 디자인 고교 콘테스트", "", "디자인·UI"),  # AI 가 있으면 패션도 받는다
    ("2026년 서울교육 AI 활용 공모전", "", "개발·AI·데이터"),
    ("[한국체육산업개발(주)] 공공데이터 활용 경진대회", "", "개발·AI·데이터"),
    ("2027 MOBIS Robotics Challenge 현대모비스 로보틱스 경진대회", "", "개발·AI·데이터"),
    ("2026 대한민국 창작 어워드", "웹/모바일/IT", "기타 IT"),       # 제목이 모호해도 출처 분야가 IT 면
    ("2026 전남자치경찰 홍보 콘텐츠 공모전", "영상/UCC", "영상·콘텐츠"),
])
def test_classify_positive(title, fields, cat):
    assert cc.classify(title, fields) == cat


@pytest.mark.parametrize("title,fields", [
    ("제21회 2026년 한국공간디자인 전국공모전", ""),
    ("2026 의정부시 ‘Sign’-Up 간판디자인공모전", ""),
    ("제14회 한옥디자인 국제 공모전", ""),
    ("제1회 중앙일보 어린이 미술대회", ""),
    ("전국 어린이 에너지절약 그림 포스터 공모전", ""),               # 손으로 그리는 포스터
    ("2026 제43회 골든스케일디자인어워드", "건축, 디자인"),         # '디자인' 만 있고 분야가 건축
    ("제3회 너의 드론이 보여 사진 공모전", ""),
    ("2026 제천시장배 전국 e-스포츠 대회", "게임/소프트웨어"),       # 게임을 '하는' 대회
    ("2026년 유기농 생태마을 유튜브 크리에이터 활동 지원사업", ""),
    ("제 9 회 법학경시대회", "학문•과학•IT"),
    ("AI 서포터즈 3기 모집", ""),
    ("2026 국가유산 방재의 날 온라인 전시회", "디자인, 만화/캐릭터, 영상/UCC"),
])
def test_classify_negative(title, fields):
    assert cc.classify(title, fields) is None


# ── 마감 ──────────────────────────────────────────────────────────────

def _c(**o) -> dict:
    row = {"sid": "1", "url": "https://x/1", "title": "AI 공모전"}
    c = cc.make_contest("wevity", row, {"period_start": "2026-11-01", "period_end": "2026-11-30", **o}, "개발·AI·데이터", NOW)
    return c


def test_deadline_passed_closes_and_extension_reopens():
    c = _c(period_end="2026-11-20")
    assert cc.apply_deadline(c, TODAY, NOW) is True
    assert (c["status"], c["closed_reason"], c["closed_at"]) == ("closed", "접수 마감", "2026-11-20T23:59:59+09:00")
    assert cc.apply_deadline(c, TODAY, NOW) is False                # 두 번 닫지 않는다
    c["period_end"] = "2026-11-28"                                  # 마감 연장
    cc.apply_deadline(c, TODAY, NOW)
    assert c["status"] == "open" and "closed_at" not in c
    assert [h["status"] for h in c["history"]] == ["open", "closed", "open"]


def test_deadline_today_is_still_open():
    c = _c(period_end="2026-11-21")
    assert cc.apply_deadline(c, TODAY, NOW) is False and c["status"] == "open"


def test_removed_page_closes():
    c = _c()
    assert cc.apply_check(c, None, "원본 삭제(이미 삭제된 데이터)", NOW) == "closed"
    assert c["status"] == "closed" and c["closed_reason"].startswith("원본 삭제")
    # 다시 올라오면 연다
    assert cc.apply_check(c, {"title": "AI 공모전", "period_end": "2026-11-30"}, None, NOW) == "open"
    assert c["status"] == "open"


def test_unknown_check_keeps_status():
    c = _c()
    assert cc.apply_check(c, None, None, NOW) == "unknown" and c["status"] == "open"


def test_due_gate():
    now = datetime.fromisoformat("2026-11-21T10:00:00+09:00")
    assert cc.due({}, now)
    assert not cc.due({"last_ok_at": (now - timedelta(hours=3)).isoformat()}, now)
    assert cc.due({"last_ok_at": (now - timedelta(hours=13)).isoformat()}, now)


def test_dday_end():
    assert cc.dday_end("D-23 접수중", TODAY) == "2026-12-14"
    assert cc.dday_end("D-day", TODAY) == "2026-11-21"
    assert cc.dday_end("마감", TODAY) is None


# ── 중복 ──────────────────────────────────────────────────────────────

def test_mark_dups_across_sources():
    def mk(src, sid, title, end):
        return {"id": f"{src}-{sid}", "source": src, "title": title, "period_end": end, "first_seen_at": NOW}
    rows = [
        mk("contestkorea", "9", "[2026 서울관광 프롬프톤] 참가자모집", "2026-11-29"),
        mk("wevity", "5", "2026 서울관광 프롬프톤", "2026-11-29"),
        mk("thinkcontest", "1", "[2026 서울관광 프롬프톤] 참가자모집", "2026-11-29"),
        mk("wevity", "6", "제3회 매경 AI 광고 공모전", "2026-11-30"),
        mk("thinkcontest", "2", "[제3회] 매경 AI 광고 공모전", "2026-11-30"),
        mk("wevity", "7", "2026 서울관광 프롬프톤", "2026-12-05"),        # 마감일이 다르면 다른 회차
    ]
    assert cc.mark_dups(rows) == 3
    d = {r["id"]: r.get("dup_of") for r in rows}
    assert d["thinkcontest-1"] is None and d["thinkcontest-2"] is None   # 씽굿이 대표
    assert d["wevity-5"] == "thinkcontest-1"
    assert d["contestkorea-9"] == "thinkcontest-1"
    assert d["wevity-6"] == "thinkcontest-2"
    assert d["wevity-7"] is None
