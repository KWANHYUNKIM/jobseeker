"""회사 API — 빌더가 viewer_doc 에 쓴 프로필을 목록·상세로 나눠 준다."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.db


def _index(client):
    r = client.get("/api/companies")
    if r.status_code == 404:
        pytest.skip("회사 프로필 문서 없음(build_company_stacks.py 를 DB 에 대고 돌릴 것)")
    assert r.status_code == 200
    return r.json()


def test_index_is_slim_and_sorted(client):
    d = _index(client)
    assert {"generated_at", "total_jobs", "company_count", "companies", "detail_fields"} <= set(d)
    cs = d["companies"]
    assert cs and not set(d["detail_fields"]) & set(cs[0]), "목록에는 상세 필드를 싣지 않는다"
    counts = [c["posting_count"] for c in cs]
    assert counts == sorted(counts, reverse=True)


def test_detail_has_everything(client):
    c = _index(client)["companies"][0]
    r = client.get(f"/api/companies/{c['norm']}")
    assert r.status_code == 200
    full = r.json()
    assert full["norm"] == c["norm"] and "postings" in full


def test_missing_company(client):
    _index(client)
    assert client.get("/api/companies/없는회사___").status_code == 404
