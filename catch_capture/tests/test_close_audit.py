"""마감·수집 점검(pipeline/close_audit.py)과 그 점검이 잡아낸 구멍 둘(jumpit 400 · 외주 마감일)의 회귀 방지."""
from datetime import datetime

from crawlers.crawl_freelance import expire
from pipeline.close_audit import findings, freelance_consistency, jobs_consistency, summarize_live
from pipeline.close_check import jumpit_gone

NOW = datetime.fromisoformat("2026-11-20T12:00:00+09:00")
TODAY = "2026-11-20"


def _p(**kw):
    base = {"id": "jobkorea:1", "site": "jobkorea", "status": "active", "deadline": None,
            "last_seen_at": "2026-11-20T09:00:00+09:00", "url": "u"}
    return {**base, **kw}


def test_외주_마감일_지난_모집중을_센다():
    got = freelance_consistency([_p(deadline="2026-11-19"), _p(deadline=TODAY), _p(), _p(status="closed")],
                                TODAY, NOW)["jobkorea"]
    assert (got["active"], got["closed"], got["past_deadline"], got["stale"]) == (3, 1, 1, 0)
    assert got["closed_no_reason"] == 1


def test_외주_오래_안_보인_모집중을_센다():
    got = freelance_consistency([_p(last_seen_at="2026-11-01T09:00:00+09:00")], TODAY, NOW)["jobkorea"]
    assert got["stale"] == 1


def test_채용_원장은_닫았는데_파일은_모집중():
    jobs = [{"site": "wanted", "pid": "1", "status": "active"},
            {"site": "wanted", "pid": "2", "status": "active", "deadline_date": "2026-11-01"},
            {"site": "wanted", "pid": "3", "status": "active", "deadline_date": "2026-11-01",
             "status_source": "override"}]
    got = jobs_consistency(jobs, {"wanted:1": {"status": "closed"}}, TODAY)["wanted"]
    assert got["ledger_closed_but_active"] == 1
    assert got["past_deadline"] == 1      # 수동 보정은 사람이 정한 답이라 세지 않는다


def test_원본_대조_요약():
    s = summarize_live([
        {"id": "a", "stored": "active", "got": "closed"},
        {"id": "b", "stored": "closed", "got": "active"},
        {"id": "c", "stored": "active", "got": "active"},
        {"id": "d", "stored": "active", "got": "unknown", "reason": "확인 실패(http=503)"},
    ])
    assert (s["asked"], s["answered"], s["agree"]) == (4, 3, 1)
    assert [r["id"] for r in s["missed"]] == ["a"]
    assert [r["id"] for r in s["wrong_close"]] == ["b"]


def test_판정기가_하나도_답을_못_얻으면_FAIL():
    report = {"live": {"jobs": {"jumpit": summarize_live([
        {"id": "x", "stored": "active", "got": "unknown", "reason": "확인 실패(http=400)"}])}}}
    f = findings(report)
    assert f and f[0]["level"] == "FAIL" and f[0]["site"] == "jumpit"


def test_수집_0건과_실패는_FAIL():
    report = {"intake": {"freelance": {"imjob": {"ok": True, "fetched": 0, "age_hours": 1},
                                       "sism": {"ok": False, "fetched": 0, "age_hours": 1, "error": "403"}},
                         "jobs": {"listings": {"wanted": {"listed": 0, "age_hours": 1}}}}}
    levels = {(x["area"], x["site"]): x["level"] for x in findings(report)}
    assert levels == {("freelance", "imjob"): "FAIL", ("freelance", "sism"): "FAIL", ("jobs", "wanted"): "FAIL"}


def test_jumpit_400_C003_은_내려간_공고():
    assert jumpit_gone(400, '{"message":" Entity Not Found","status":400,"errors":[],"code":"C003"}')
    assert not jumpit_gone(400, '{"message":"Bad Request"}')
    assert not jumpit_gone(503, "Entity Not Found")


def test_외주_마감일_지나면_접수마감으로_닫는다():
    p = _p(deadline="2026-11-19")
    assert expire(p, TODAY, "2026-11-20T12:00:00+09:00")
    assert (p["status"], p["closed_reason"]) == ("closed", "마감일 경과(2026-11-19)")
    # 이미 닫은 시각은 그대로 둔다 — 매 회차 열었다 닫으면 closed_at 이 흔들린다
    q = _p(deadline="2026-11-19", closed_at="2026-11-19T23:00:00+09:00")
    expire(q, TODAY, "2026-11-20T12:00:00+09:00")
    assert q["closed_at"] == "2026-11-19T23:00:00+09:00"
    assert not expire(_p(deadline=TODAY), TODAY, "x")      # 당일은 아직 받는다
    assert not expire(_p(), TODAY, "x")                    # 마감일 모름 → 재확인 몫
