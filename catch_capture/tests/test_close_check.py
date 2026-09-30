"""마감 재확인(pipeline.close_check) — 원본을 두드리지 않는 판정 규칙들."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pipeline import close_check as cc
from pipeline import job_status


def test_selftests_pass():
    # 사이트별 파서·등록일·재확인 주기·일시적 실패 규칙 48건
    assert cc._selftest() == 0
    assert job_status._selftest() == 0


@pytest.mark.parametrize("reason, transient", [
    ("확인 실패(http=429)", True),
    ("확인 실패(http=403)", True),
    ("확인 실패(http=502)", True),
    ("확인 실패(http=None)", True),
    ("예외: TimeoutError()", True),
    ("확인 실패(http=404)", False),         # 404 는 '내려갔다' 는 답이다(여기 올 일도 없다)
    ("마감일 표기를 찾지 못함", False),
    ("페이지 생존(http=200) — 마감 여부 불명", False),
])
def test_transient_failures_are_not_recorded(reason, transient):
    assert cc.is_transient(cc.Verdict("unknown", reason)) is transient


def test_transient_only_for_unknown():
    assert not cc.is_transient(cc.Verdict("closed", "확인 실패(http=429)"))


def test_age_mixes_aware_and_naive():
    now = datetime(2026, 9, 30, 12, 0).astimezone()
    aware = (now - timedelta(days=2)).isoformat()
    naive = (now - timedelta(days=2)).replace(tzinfo=None).isoformat()
    assert cc._age_days(aware, now) == pytest.approx(2.0)
    assert cc._age_days(naive, now) == pytest.approx(2.0)
    assert cc._age_days("", now) == 1e9
    assert cc._age_days("쓰레기", now) == 1e9


def test_gone_jobs_come_first():
    now = datetime(2026, 9, 30, 12, 0).astimezone()
    d = lambda n: (now - timedelta(days=n)).isoformat()   # noqa: E731
    jobs = [
        {"site": "wanted", "pid": "old", "_checked_at": d(3), "_ledger_closed": False},
        {"site": "wanted", "pid": "gone", "_checked_at": d(0.5), "_gone_at": d(0.1),
         "_ledger_closed": False},
    ]
    order = [j["pid"] for j in cc.due_jobs(jobs, {}, now, sites=None, recheck_days=None,
                                           recheck_closed=False)]
    assert order == ["gone", "old"]


def test_ledger_lock_is_exclusive(tmp_path, monkeypatch):
    # 두 회차가 겹치면 뒤에 온 쪽이 건너뛴다(원장 파일을 서로 덮어쓰지 않게).
    monkeypatch.setattr(cc, "LOCK_PATH", tmp_path / "job_closures.lock")
    with open(cc.LOCK_PATH, "a+") as a, open(cc.LOCK_PATH, "a+") as b:
        assert cc._try_lock(a) is True
        assert cc._try_lock(b) is False
