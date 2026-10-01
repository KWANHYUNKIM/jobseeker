"""공고 API — 정본 DB 에 붙어 실제로 답을 받아 본다."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

pytestmark = pytest.mark.db

HEAVY = {"full_jd", "main_tasks", "qualifications", "preferences", "benefits"}


def jobs(client, **params):
    r = client.get("/api/jobs", params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ── 형식 ────────────────────────────────────────────────────────────────

def test_list_shape(client):
    d = jobs(client)
    assert set(d) >= {"total", "all_total", "page", "limit", "items", "facets", "engines"}
    assert 0 < d["total"] <= d["all_total"]
    assert 0 < len(d["items"]) <= d["limit"] == 50
    assert set(d["facets"]) == {"siteCount", "careerCount", "regions", "districts",
                                "sizes", "roles", "stacks"}


def test_list_items_are_slim_and_carry_server_facets(client):
    for j in jobs(client, limit=20)["items"]:
        assert not HEAVY & set(j), "목록에는 본문을 싣지 않는다"
        assert j["roles"], "직군은 서버가 계산해 싣는다"
        assert j["place"]["region"]
        assert {"site", "pid", "company", "title", "url", "status"} <= set(j)


# ── 상태는 읽는 순간의 것 ───────────────────────────────────────────────

def test_open_list_has_no_passed_deadline(client):
    """이번 작업의 핵심: 모집중 목록에 마감일이 지난 공고가 없다(한국 날짜 기준)."""
    today = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    for page in (1, 2):
        for j in jobs(client, page=page, limit=200)["items"]:
            assert j["status"] == "active"
            assert not j["deadline_date"] or j["deadline_date"] >= today, j["url"]


def test_closed_modes_partition_everything(client):
    hide = jobs(client, closed="hide")["total"]
    only = jobs(client, closed="only")["total"]
    show = jobs(client, closed="show")
    assert hide + only == show["total"] == show["all_total"]
    assert all(j["status"] == "closed" for j in jobs(client, closed="only", limit=50)["items"])


# ── 필터 ────────────────────────────────────────────────────────────────

def test_region_filter(client):
    base = jobs(client)["total"]
    d = jobs(client, region="서울", limit=100)
    assert 0 < d["total"] < base
    assert all(j["place"]["region"] == "서울" for j in d["items"])
    # 지역을 하나만 고르면 시군구 칩이 뜬다
    assert d["facets"]["districts"]
    district = d["facets"]["districts"][0]
    d2 = jobs(client, region="서울", district=district["name"])
    assert d2["total"] == district["count"]


def test_chip_count_means_result_count(client):
    """칩 숫자 = 그걸 눌렀을 때의 건수(자기 축만 빼고 센다)."""
    d = jobs(client, role="백엔드")
    for chip in d["facets"]["regions"][:3]:
        assert jobs(client, role="백엔드", region=chip["name"])["total"] == chip["count"]
    for site, n in list(d["facets"]["siteCount"].items())[:3]:
        assert jobs(client, role="백엔드", site=site)["total"] == n


def test_stack_filter_requires_all_case_insensitive(client):
    a = jobs(client, stack=["java", "SPRING"], limit=100)
    b = jobs(client, stack="Java,Spring")
    assert a["total"] == b["total"] > 0
    for j in a["items"]:
        lower = {t.lower() for t in j["tech_stack"]}
        assert {"java", "spring"} <= lower


def test_role_filter_is_any_of(client):
    one = jobs(client, role="QA")["total"]
    both = jobs(client, role=["QA", "보안"])["total"]
    assert both >= one
    for j in jobs(client, role=["QA", "보안"], limit=100)["items"]:
        assert {"QA", "보안"} & set(j["roles"])


def test_text_query_ranks_company_matches_first(client):
    # 마감 포함으로 본다 — 정렬 규칙을 시험하는 것이지, 지금 모집중인 현대자동차 공고가
    # 있는지(데이터 상태)를 시험하는 게 아니다.
    d = jobs(client, q="현대자동차", limit=5, closed="show")
    assert d["total"] > 0
    assert "현대자동차" in d["items"][0]["company"].lower() + d["items"][0]["title"].lower()


@pytest.mark.parametrize("q", ["100%", "a_b", "'; DROP TABLE job; --", "\\"])
def test_text_query_is_literal(client, q):
    # LIKE 의 %·_ 는 글자 그대로. SQL 은 매개변수로만 들어간다.
    assert client.get("/api/jobs", params={"q": q}).status_code == 200


# ── 쪽 ────────────────────────────────────────────────────────────────

def test_pages_do_not_overlap(client):
    p1 = {j["url"] for j in jobs(client, page=1, limit=20)["items"]}
    p2 = {j["url"] for j in jobs(client, page=2, limit=20)["items"]}
    assert len(p1) == len(p2) == 20 and not p1 & p2


def test_page_past_the_end_is_empty(client):
    d = jobs(client, site="none", page=9999)
    assert d["items"] == []


@pytest.mark.parametrize("params", [{"closed": "bogus"}, {"limit": 0}, {"limit": 201},
                                    {"page": 0}, {"unverified": "x"}])
def test_bad_params_are_422(client, params):
    assert client.get("/api/jobs", params=params).status_code == 422


# ── 상세·조회 ───────────────────────────────────────────────────────────

def test_detail_and_lookup_roundtrip(client):
    item = jobs(client, limit=1)["items"][0]
    key = f"{item['site']}-{item['pid']}"
    d = client.get(f"/api/jobs/{key}").json()
    assert (d["site"], d["pid"], d["url"]) == (item["site"], item["pid"], item["url"])
    assert "full_jd" in d and d["roles"] == item["roles"]
    assert client.get("/api/jobs/lookup", params={"url": item["url"]}).json()["key"] == key


def test_detail_key_with_colons(client):
    # ats 의 pid 는 'greenhouse:toast:123' 처럼 쌍점이 들어간다
    d = jobs(client, site="ats", limit=1, closed="show")
    if not d["items"]:
        pytest.skip("ats 공고 없음")
    j = d["items"][0]
    assert client.get(f"/api/jobs/{j['site']}-{j['pid']}").status_code == 200


@pytest.mark.parametrize("path, code", [
    ("/api/jobs/wanted-999999999999", 404),
    ("/api/jobs/nokey", 400),
    ("/api/jobs/lookup?url=https://example.com/none", 404),
])
def test_missing(client, path, code):
    assert client.get(path).status_code == code


# ── 파일 내보내기와 같은 모집단 ─────────────────────────────────────────

def test_same_population_as_export(client):
    """전체 수 = 파일 내보내기(all_jobs_enriched.json)가 싣는 수(사이트 간 중복 제외, job_dup 뷰 기준)."""
    from app.db.session import cursor
    with cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW mv_job_dup")
        cur.execute("SELECT count(*) AS n FROM v_job v "
                    "WHERE NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = v.id)")
        n = cur.fetchone()["n"]
    assert jobs(client, closed="show")["all_total"] == n


# ── 응답 캐시 ───────────────────────────────────────────────────────────

def test_cache_serves_repeat_queries(client, monkeypatch):
    from app.features.jobs import service
    from app.utils import cache
    monkeypatch.setattr(cache, "ttl_override", 60.0)
    cache.clear()
    calls = []
    real = service._list_jobs
    monkeypatch.setattr(service, "_list_jobs", lambda q: calls.append(1) or real(q))
    a = jobs(client, region="서울", limit=5)
    b = jobs(client, region="서울", limit=5)
    c = jobs(client, region="부산", limit=5)
    assert a == b and a != c
    assert len(calls) == 2, "같은 질의는 한 번만 계산한다"
    cache.clear()
