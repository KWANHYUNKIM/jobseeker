"""모집인원(core.headcount) — 정확한 수와 자릿수 표기(○명·○○명). 사원수(test_headcount)와 다르다."""
from __future__ import annotations

from datetime import date

import pytest

from core.headcount import Headcount, from_jobkorea_page, from_text, parse


@pytest.mark.parametrize("raw, n, digits", [
    ("1명", 1, 1),
    ("3 명", 3, 1),
    ("12명", 12, 2),
    ("○명", None, 1),
    ("○○명", None, 2),
    ("OO명", None, 2),
    ("00명", None, 2),
    ("약 20여 명", 20, 2),
    ("1○명", None, 2),
])
def test_parse(raw, n, digits):
    hc = parse(raw)
    assert hc is not None and (hc.n, hc.digits) == (n, digits)


@pytest.mark.parametrize("raw", ["0명", "", None, "미정", "-", "명"])
def test_parse_unspecified(raw):
    assert parse(raw) is None


def test_range():
    assert (Headcount("○명", None, 1).low, Headcount("○명", None, 1).high) == (1, 9)
    assert (Headcount("○○명", None, 2).low, Headcount("○○명", None, 2).high) == (10, 99)
    assert (Headcount("3명", 3, 1).low, Headcount("3명", 3, 1).high) == (3, 3)


def test_jobkorea_field_with_react_comment():
    html = ('<div data-sentry-element="RecruitmentItem"><span class="min-w-[80px]">모집인원</span>'
            '<span class="text-[#222222]">○○<!-- -->명</span></div>')
    assert from_jobkorea_page(html) == "○○명"
    assert from_jobkorea_page("<html>칸 없음</html>") is None


@pytest.mark.parametrize("text, want", [
    ("· 모집인원 : ○명\n· 학력무관", "○명"),
    ("채용 인원 2명 · 경력 3년", "2명"),
    ("선발인원: 00명", "00명"),
    ("모집 인원은 1명이다.", "1명"),
    ("채용 인원은 공고에 별도로 명시되지 않았다.", None),
    ("1500명 규모 축제", None),
])
def test_from_text(text, want):
    assert from_text(text) == want


def test_close_check_reads_headcount():
    from pipeline.close_check import verdict_jobkorea
    html = ('<script type="application/ld+json">{"datePosted": "2026-11-20", '
            '"validThrough": "2026-12-20T23:59"}</script>'
            '<span>모집인원</span><span>○<!-- -->명</span>')
    v = verdict_jobkorea(html, date(2026, 11, 27))
    assert v.status == "active" and v.headcount == "○명"
