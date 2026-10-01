"""공고 목록·상세 — 질의 파라미터를 SQL 파라미터로, 행을 응답으로."""
from __future__ import annotations

from app.core.exceptions import BadRequest, NotFound
from app.features.jobs import repository
from app.features.jobs.constants import (
    COMPANY_SIZES, HEAVY_FIELDS, MAX_QUERY_CHARS, REGION_OPTIONS, SEMANTIC_HITS,
)
from app.features.jobs.mapping import row_to_job
from app.features.jobs.schemas import JobsQuery
from app.features.search import service as search_service
from app.utils.cache import cached
from app.utils.text import js_trim, like_pattern, split_multi


def to_job(r: dict) -> dict:
    job = row_to_job(r, 0)
    # 목록 화면이 브라우저에서 계산하던 값들을 실어 보낸다(본문 없이 그릴 수 있게).
    job["roles"] = list(r["f_roles"] or [])
    job["place"] = {"region": r["f_region"], "district": r["f_district"]}
    if r["f_company_size"]:
        job["company_size"] = r["f_company_size"]
    return job


def _slim(job: dict) -> dict:
    for k in HEAVY_FIELDS:
        job.pop(k, None)
    return job


def _counts(rows: list[dict], axis: str) -> list[dict]:
    items = [{"name": r["name"], "count": r["n"]} for r in rows if r["axis"] == axis]
    return sorted(items, key=lambda x: (-x["count"], x["name"]))


def list_jobs(q: JobsQuery) -> dict:
    return cached(("jobs", *q.cache_key()), lambda: _list_jobs(q))


def _list_jobs(q: JobsQuery) -> dict:
    query = js_trim(q.q)[:MAX_QUERY_CHARS].lower()
    regions = split_multi(q.region)
    params = {
        "sites": split_multi(q.site), "careers": split_multi(q.career), "roles": split_multi(q.role),
        "regions": regions, "districts": split_multi(q.district), "sizes": split_multi(q.size),
        "stacks": [s.lower() for s in split_multi(q.stack)],
        "q": query, "q_like": like_pattern(query),
        "closed": q.closed, "unverified_hide": q.unverified == "hide",
        # 시군구 칩은 지역을 딱 하나 골랐을 때만 뜻이 있다(Sidebar 와 같은 규칙).
        "one_region": regions[0] if len(regions) == 1 else None,
        "sem": False, "sem_ids": [],
        "limit": q.limit, "offset": (q.page - 1) * q.limit,
    }

    engines = None
    if q.semantic and query:
        # 의미 검색은 관련도 순서가 결과의 핵심이다. 후보를 먼저 뽑고 그 안에서 모든 축을 건다.
        hits = search_service.search(js_trim(q.q)[:MAX_QUERY_CHARS], limit=SEMANTIC_HITS,
                                     include_closed=q.closed != "hide")
        params.update(sem=True, sem_ids=[int(h["id"]) for h in hits["results"]])
        engines = hits["engines"]

    facet_rows, ids, rows, present = repository.list_page(params)

    total = next((r["n"] for r in facet_rows if r["axis"] == "total"), 0)
    region_count = {r["name"]: r["n"] for r in facet_rows if r["axis"] == "regions"}
    size_count = {r["name"]: r["n"] for r in facet_rows if r["axis"] == "sizes"}
    present_regions = set(present["regions"] or [])
    present_sizes = set(present["sizes"] or [])

    return {
        "total": total,                       # 필터를 건 결과 건수
        "all_total": present["all_total"],    # 전체 공고 수(모집중+마감, 중복 제외)
        "page": q.page,
        "limit": q.limit,
        "items": [_slim(to_job(rows[i])) for i in ids if i in rows],
        "engines": engines,
        "facets": {
            "siteCount": {r["name"]: r["n"] for r in facet_rows if r["axis"] == "sites"},
            "careerCount": {r["name"]: r["n"] for r in facet_rows if r["axis"] == "careers"},
            "regions": [{"name": n, "count": region_count.get(n, 0)}
                        for n in REGION_OPTIONS if n in present_regions],
            "districts": _counts(facet_rows, "districts"),
            "sizes": [{"name": n, "count": size_count.get(n, 0)}
                      for n in COMPANY_SIZES if n in present_sizes],
            "roles": _counts(facet_rows, "roles"),
            "stacks": _counts(facet_rows, "stacks"),
        },
    }


def split_key(key: str) -> tuple[str, str]:
    """뷰어 주소의 `/jobs/<사이트>-<번호>`. ats 의 번호에는 쌍점이 들어간다."""
    site, sep, pid = key.partition("-")
    if not sep or not pid:
        raise BadRequest("key 는 <사이트>-<번호>")
    return site, pid


def get_job(key: str) -> dict:
    site, pid = split_key(key)
    r = cached(("job", site, pid), lambda: repository.find_by_key(site, pid))
    if not r:
        raise NotFound(f"공고 {key} 을(를) 찾지 못했습니다")
    return to_job(r)


def lookup(url: str) -> dict:
    r = repository.find_key_by_url(url)
    if not r:
        raise NotFound("없는 공고")
    return {"key": f"{r['site']}-{r['pid']}", "site": r["site"], "pid": r["pid"]}


def fingerprint() -> str:
    """전량이 바뀌었는지의 지문 — /api/jobs/all 의 ETag."""
    return repository.fingerprint()


def all_jobs() -> list[dict]:
    """공고 전량(본문 포함·중복 제외·최신순) — all_jobs_enriched.json 과 같은 모양."""
    return [row_to_job(r, i) for i, r in enumerate(repository.all_rows(), start=1)]
