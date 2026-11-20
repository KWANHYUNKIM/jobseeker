"""jd-viewer/bin/build_reposts.py — 재공고 짝짓기와 '왜 다시 올렸나'."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_P = Path(__file__).resolve().parents[2] / "jd-viewer" / "bin" / "build_reposts.py"
_spec = importlib.util.spec_from_file_location("build_reposts", _P)
br = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(br)


def job(**kw) -> dict:
    base = {
        "company": "클로봇", "title": "백엔드 개발자", "site": "wanted", "pid": "1",
        "url": "https://x/1", "status": "active", "career": "경력3년↑",
        "location": "서울 강남구", "deadline": "", "deadline_date": "", "dday": "",
        "posted_date": "", "first_seen_at": "2026-10-01", "tech_stack": ["Java", "Spring"],
        "qualifications": "Java 3년 이상\nSpring 실무 경험", "preferences": "",
        "main_tasks": "API 개발", "benefits": "",
    }
    base.update(kw)
    return base


def codes(reasons):
    return [r["code"] for r in reasons]


def test_career_years():
    assert br.career_years("경력3년↑") == 3
    assert br.career_years("신입") == 0
    assert br.career_years("신입~3년") == 0
    assert br.career_years("경력무관") == 0
    assert br.career_years("") is None


def test_pair_finds_repost_hidden_behind_dup_and_explains_career_drop():
    old = job(pid="1", status="closed", first_seen_at="2026-09-01", deadline_date="2026-09-30")
    new = job(pid="2", url="https://x/2", first_seen_at="2026-10-20", career="경력1년↑")
    out = br.pair_reposts([old, new])
    (r,) = out.values()
    assert r["url"] == "https://x/2" and r["prev_url"] == "https://x/1"
    assert r["gap_days"] == 20
    assert codes(r["reasons"])[0] == "career_down"
    assert "경력3년↑ → 경력1년↑" in r["reasons"][0]["label"]


def test_same_day_cross_site_copy_is_not_a_repost():
    old = job(pid="1", site="saramin", status="closed", first_seen_at="2026-10-01")
    new = job(pid="2", site="wanted", first_seen_at="2026-10-01")
    assert br.pair_reposts([old, new]) == {}


def test_unchanged_quick_repost_reads_as_extension():
    old = job(pid="1", status="closed", first_seen_at="2026-09-01", deadline_date="2026-10-01")
    new = job(pid="2", url="https://x/2", first_seen_at="2026-10-03")
    (r,) = br.pair_reposts([old, new]).values()
    assert codes(r["reasons"]) == ["same_quick"]


def test_unchanged_late_repost_says_how_long():
    old = job(pid="1", status="closed", first_seen_at="2026-08-01", deadline_date="2026-08-31")
    new = job(pid="2", url="https://x/2", first_seen_at="2026-10-30")
    (r,) = br.pair_reposts([old, new]).values()
    assert codes(r["reasons"]) == ["same_later"]
    assert "60일 만에" in r["reasons"][0]["label"]


def test_third_round_and_text_lines():
    a = job(pid="1", status="closed", first_seen_at="2026-07-01")
    b = job(pid="2", status="closed", first_seen_at="2026-08-15")
    c = job(pid="3", url="https://x/3", first_seen_at="2026-10-01",
            qualifications="Java 3년 이상\nSpring 실무 경험\nKafka 운영 경험\nAWS 운영 경험",
            tech_stack=["Java", "Spring", "Kafka"])
    (r,) = br.pair_reposts([a, b, c]).values()
    assert r["rounds"] == 3
    got = codes(r["reasons"])
    assert "repeat" in got and "stack_added" in got and "qualifications_grown" in got
    q = next(ch for ch in r["changes"] if ch["field"] == "qualifications")
    assert q["added_lines"] == ["Kafka 운영 경험", "AWS 운영 경험"] and q["removed_lines"] == []


def test_missing_body_is_not_a_reason():
    changes = [{"field": "qualifications", "kind": "text", "missing": True,
                "from_len": 0, "to_len": 300, "to_excerpt": ""}]
    assert codes(br.explain(changes, gap_days=30)) == ["same_later"]
