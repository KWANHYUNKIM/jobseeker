"""커리어 후기 API — 거르기·세기·열쇠 규칙(DB 없이 가짜 줄로)."""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.features.careers import repository, service


def _row(i, **kw):
    base = {"id": f"velog-{i}", "kind": "합격", "year": 2024, "period": None, "company": "토스", "company_key": "토스",
            "program": None, "company_type": "빅테크·플랫폼", "company_size": None, "role": "백엔드", "level": "신입",
            "years_before": None, "transition": None, "transition_cat": None, "origin": None, "education": "비전공 4년제",
            "age": 27, "source": "velog", "url": "https://velog.io/x", "title": "토스 합격", "posted_on": None,
            "data": {"summary": "요약", "spec": {"gpa": "4.0/4.5", "certs": ["정처기"], "language": ["오픽 IH"],
                                                 "algorithm": "백준 골드2"},
                     "path": [{"step": "SI 3년"}, {"step": "토스 합격"}],
                     "other_companies": [{"company": "카카오", "result": "불합격", "stage": "코테"}]}}
    return base | kw


ROWS = [_row(1), _row(2, year=2023, company="하나은행", company_key="하나은행", company_type="금융"),
        _row(3, level="경력", years_before=3, origin="SI·SM", kind="이직")]


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    monkeypatch.setattr(repository, "stories", lambda: ROWS)
    monkeypatch.setattr(repository, "counts", lambda: {"posts": 3, "stories": 3, "counted": 3, "updated_at": None})


def test_overview_filters_and_spec():
    o = service.overview({"year": 2024})
    assert o["n"] == 2 and [y["year"] for y in o["by_year"]] == [2024]
    assert o["spec"]["certs"][0] == ["정보처리기사", 2]          # 정처기 → 정보처리기사
    assert o["spec"]["language"][0][0] == "OPIc IH"
    assert o["spec"]["algorithm"][0][0] == "백준 골드"
    assert o["spec"]["gpa"]["median"] == 4.0
    assert o["facets"]["years"][0] == [2024, 2]                  # 거르기와 무관하게 전체 축
    assert service.overview({"type": "금융"})["n"] == 1


def test_moves_and_applied():
    m = service.overview({})["moves"]
    assert m["n"] == 1 and m["origins"][0][0] == "SI·SM"
    assert m["matrix"] == [{"origin": "SI·SM", "type": "빅테크·플랫폼", "n": 1}]
    assert next(y for y in m["years"] if y["band"] == "3~5년")["n"] == 1
    a = service.overview({})["applied"][0]
    assert a["company"] == "카카오" and a["fail"] == 3 and a["stages"][0] == ["코테", 3]


def test_gpa_needs_decimal():
    assert service._gpa("3점 후반") is None
    assert service._gpa("3.8 / 4.3") == pytest.approx(3.98, abs=0.01)


def test_body_needs_key(monkeypatch):
    monkeypatch.setattr(repository, "story", lambda pid: ROWS[0] | {"body": "원문", "tags": [], "collected_at": None})
    locked = service.story("velog-1", "아무거나")
    assert locked["body"] is None and locked["body_locked"] and locked["body_chars"] == 2
    object.__setattr__(settings, "careers_key", "k")
    try:
        assert service.story("velog-1", "k")["body"] == "원문"
        assert service.story("velog-1", "x")["body"] is None
    finally:
        object.__setattr__(settings, "careers_key", "")
