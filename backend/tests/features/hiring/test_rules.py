"""채용 추이 규칙 — DB 없이 돈다."""
from __future__ import annotations

from datetime import date, datetime

from app.features.hiring import service


def test_week_starts_are_mondays_oldest_first():
    ws = service.week_starts(12, today=date(2026, 11, 27))   # 금요일
    assert len(ws) == 12
    assert all(d.weekday() == 0 for d in ws)
    assert ws[-1] == date(2026, 11, 23)
    assert ws == sorted(ws)


def test_summarize_skips_current_week():
    # 12주: 앞 3주 0, 이전 4주 각 1, 최근 4주 각 3, 이번 주 100(진행 중)
    s = [0, 0, 0, 1, 1, 1, 1, 3, 3, 3, 3, 100]
    assert service.summarize(s) == (12, 4)


def test_trend_label():
    assert service.trend_label(5, 0) == "new"
    assert service.trend_label(12, 4) == "up"
    assert service.trend_label(2, 1) == "flat", "1건→2건은 급증이 아니다"
    assert service.trend_label(1, 8) == "down"
    assert service.trend_label(0, 0) == "flat"


def test_fast_ratio_needs_min_n():
    assert service.fast_ratio(2, 2) is None
    assert service.fast_ratio(4, 1) == 0.25


def test_unreliable_weeks_give_unknown_trend():
    ws = service.week_starts(12, today=date(2026, 11, 27))
    started = datetime(2026, 11, 11, 9, tzinfo=service.KST)
    rel = service.reliable_weeks(ws, started)
    assert rel[-1] and rel[-2] and not rel[-3], "11-11 시작 +3일 → 11-16 주부터 믿는다"
    assert not service.comparable(rel)
    assert service.trend_label(10, 0, ok=False) == "unknown"


def test_long_coverage_is_comparable():
    ws = service.week_starts(12, today=date(2026, 11, 27))
    rel = service.reliable_weeks(ws, datetime(2026, 1, 1, tzinfo=service.KST))
    assert all(rel) and service.comparable(rel)


def test_recent_seats_sums_last_four_full_weeks():
    z = dict.fromkeys(service.HC_KEYS, 0)
    week = {**z, "hc_known": 2, "hc_exact": 1, "hc_one": 1, "seats_low": 3, "seats_high": 11}
    weeks = [z] * 6 + [week] * 4 + [{**z, "hc_known": 99, "seats_low": 999, "seats_high": 999}]
    s = service.recent_seats(weeks, of=10)
    assert (s["known"], s["low"], s["high"], s["exact"], s["one_digit"]) == (8, 12, 44, 4, 4)


def test_recent_seats_unknown_is_none():
    z = dict.fromkeys(service.HC_KEYS, 0)
    s = service.recent_seats([z] * 12, of=5)
    assert s["known"] == 0 and s["low"] is None and s["high"] is None
