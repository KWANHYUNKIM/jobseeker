"""뷰어 API — 정본 DB 를 읽어 바로 답한다(8771, FastAPI).

지금까지 뷰어는 공고 전량(`all_jobs_enriched.json`, 184MB)을 첫 화면에서 받아 놓고
필터·칩 건수·정렬·페이지를 전부 브라우저에서 계산했다. 그 파일은 크롤 사이클마다
다시 구워졌으므로 DB 에서 공고가 닫혀도 화면은 다음 굽기까지 옛 상태였고, 파이프라인이
멈추면(2026-09-30 Docker 가 멎은 열 시간처럼) 그대로 굳었다.

여기서는 그 계산을 SQL 로 한다. 상태(status)는 `job_state` 뷰가 읽는 순간 계산하므로
화면이 DB 보다 늦을 수 없다. 필터 축(지역·직군·경력·규모·스택)은 뷰어 규칙을 옮긴
`store.jobs.facets` 가 `job_facet` 에 채워 둔 값을 쓴다.

    GET /api/jobs?region=서울&role=백엔드&closed=hide&page=1   목록 + 칩 건수
    GET /api/jobs/{site}-{pid}                                 공고 한 건(본문 포함)
    GET /api/jobs/lookup?url=...                               url → 주소 키
    GET /api/search?q=...                                      하이브리드 검색(형식 그대로)
    GET /api/health
    GET /api/docs                                              OpenAPI 문서

**응답 필드는 뷰어 `types.ts` 의 Job 그대로다** — 매핑은 `store.jobs.export.row_to_job`
하나를 파일 내보내기와 같이 쓴다. 두 벌로 두면 파일로 보던 화면과 API 로 보는 화면이
조용히 달라진다.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
from typing import Literal

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402

from store.db import conn as store_conn  # noqa: E402
from store.jobs.export import JOB_SELECT, row_to_job  # noqa: E402
from store.jobs.facets import REGION_OPTIONS, _js_trim  # noqa: E402

COMPANY_SIZES = ["대기업", "중견기업", "중소기업"]

# 한 요청이 통째로 DB 를 훑어가지 못하게 막는 상한.
MAX_LIMIT = 100
MAX_QUERY_CHARS = 200
PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 200
SEMANTIC_HITS = 100          # 의미 검색으로 먼저 뽑아 올 후보 수(그 안에서 필터를 건다)

# 목록에는 본문을 싣지 않는다. 184MB 중 90% 가 이 다섯 필드다(full_jd 만 115MB) —
# 상세 화면에서 한 건씩 받는다. 직군 배지는 자격요건 본문으로 계산하던 것을 서버가
# 계산해 `roles` 로 실어 보낸다.
HEAVY_FIELDS = ("full_jd", "main_tasks", "qualifications", "preferences", "benefits")

# ── 짧은 응답 캐시 ─────────────────────────────────────────────────────
# 이 맥(8GB)은 크롤·Docker·임베딩이 같이 돌면 스왑이 차고, 그때 DB 질의가 1~17초로
# 들쭉날쭉했다(2026-09-30 측정, 스왑 8.2/9.2GB). 같은 질의 — 특히 필터 없는 첫 화면 —
# 는 반복되므로 잠깐 들고 있다가 답한다. 상태가 늦어지는 폭은 TTL 만큼이다(예전 파일
# 방식은 다음 크롤 사이클까지, 한 시간 넘게 늦었다).
import threading as _threading
import time as _time

CACHE_TTL = float(__import__("os").environ.get("API_CACHE_TTL", "60"))
CACHE_MAX = 512
_cache: dict[tuple, tuple[float, object]] = {}
_cache_lock = _threading.Lock()


def _cached(key: tuple, compute):
    if CACHE_TTL <= 0:
        return compute()
    now = _time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
    value = compute()
    with _cache_lock:
        if len(_cache) >= CACHE_MAX:
            # 오래된 절반을 버린다 — LRU 를 정확히 지킬 만큼의 일은 아니다.
            for k, _ in sorted(_cache.items(), key=lambda kv: kv[1][0])[: CACHE_MAX // 2]:
                _cache.pop(k, None)
        _cache[key] = (now, value)
    return value


app = FastAPI(
    title="jobseeker 뷰어 API",
    description="정본 DB(PostgreSQL)를 읽어 공고 목록·상세·검색을 돌려준다.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
# 개발 중에는 뷰어(5173)와 API(8771)의 오리진이 다르다. 운영은 nginx 가 /api/ 를
# 같은 오리진으로 프록시한다. 읽기 전용 API 라 자격 증명은 받지 않는다.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])
app.add_middleware(GZipMiddleware, minimum_size=2048)


# ════════════════════════════════════════════════════════════════════
# 하이브리드 검색 — 예전 stdlib 서버의 /api/search 를 그대로 옮겼다(응답 형식 동일)
# ════════════════════════════════════════════════════════════════════

_JOB_DETAIL = """
    SELECT s.job_id AS id, s.rrf, s.fts_rank, s.vec_rank,
           v.url, v.site, v.company, v.title,
           v.career_text AS career, v.location_text AS location, v.tech_stack
      FROM search_jobs(%(q)s, %(emb)s, %(n)s, %(closed)s) s
      JOIN v_job v ON v.id = s.job_id
     ORDER BY s.rrf DESC
"""

# Ollama 가 없을 때의 길. 벡터 없이 FTS 만으로 답한다.
_JOB_FTS_ONLY = """
    SELECT v.id, ts_rank_cd(j.search_tsv, websearch_to_tsquery('simple', %(q)s)) AS rrf,
           NULL::integer AS fts_rank, NULL::integer AS vec_rank,
           v.url, v.site, v.company, v.title,
           v.career_text AS career, v.location_text AS location, v.tech_stack
      FROM job j
      JOIN v_job v ON v.id = j.id
     WHERE (%(closed)s OR v.status = 'active')
       AND j.search_tsv @@ websearch_to_tsquery('simple', %(q)s)
     ORDER BY 2 DESC LIMIT %(n)s
"""

_POST_FTS = """
    SELECT p.id, ts_rank_cd(p.search_tsv, websearch_to_tsquery('simple', %(q)s)) AS rrf,
           NULL::integer AS fts_rank, NULL::integer AS vec_rank,
           p.url, 'post' AS site, COALESCE(c.display_name, p.blog_name) AS company,
           p.title, '' AS career, '' AS location, '{}'::text[] AS tech_stack
      FROM post p LEFT JOIN company c ON c.id = p.company_id
     WHERE p.search_tsv @@ websearch_to_tsquery('simple', %(q)s)
     ORDER BY 2 DESC LIMIT %(n)s
"""


def _query_embedding(text: str):
    """질의 임베딩. Ollama 가 없으면 None — 그때는 FTS 만으로 답한다."""
    try:
        from store.vectors.embed import embed_batch
        return embed_batch([text])[0]
    except Exception as e:                                          # noqa: BLE001
        print(f"[search] 벡터 건너뜀: {e}", file=_sys.stderr)
        return None


def search(query: str, *, kind: str = "job", limit: int = 20,
           include_closed: bool = False) -> dict:
    vec = _query_embedding(query) if kind == "job" else None
    params = {"q": query, "n": limit, "closed": include_closed}

    with store_conn.cursor(autocommit=True) as cur:
        if kind == "post":
            cur.execute(_POST_FTS, params)
        elif vec is None:
            cur.execute(_JOB_FTS_ONLY, params)
        else:
            cur.execute(_JOB_DETAIL, {**params, "emb": str(vec)})
        rows = cur.fetchall()

    results = [{
        "id": str(r["id"]),
        "url": r["url"],
        "site": r["site"],
        "company": r["company"] or "",
        "title": r["title"],
        "career": r["career"] or "",
        "location": r["location"] or "",
        "tech_stack": list(r["tech_stack"] or []),
        "score": round(float(r["rrf"]), 6),
        # 이 결과가 어느 쪽에서 왔는지 — 가중치를 조정할 때 근거가 된다.
        "rank_fts": r["fts_rank"],
        "rank_vec": r["vec_rank"],
    } for r in rows]

    return {
        "query": query,
        "kind": kind,
        "total": len(results),
        "engines": {
            "fts": sum(1 for r in results if r["rank_fts"] is not None) or len(results),
            "vector": sum(1 for r in results if r["rank_vec"] is not None),
        },
        "results": results,
    }


def health() -> dict:
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute("""
            SELECT (SELECT count(*) FROM job) AS jobs,
                   (SELECT count(*) FROM job_state WHERE status='active') AS active,
                   (SELECT count(*) FROM post) AS posts,
                   (SELECT count(*) FROM job_embedding) AS job_vectors,
                   (SELECT count(*) FROM job_embed_pending) AS job_pending,
                   (SELECT count(*) FROM post_embedding) AS post_vectors,
                   (SELECT count(*) FROM job_facet) AS job_facets
        """)
        s = dict(cur.fetchone())
    # 벡터가 하나도 없으면 검색이 FTS 로만 돈다. 조용히 반쪽으로 도는 것보다
    # 건강 검사가 말해 주는 편이 낫다.
    s["vector_search"] = s["job_vectors"] > 0
    return s


@app.get("/")
@app.get("/api")
@app.get("/api/")
def root() -> dict:
    # setup-dashboards.sh 의 기동 확인이 / 를 찌른다. 다른 서버들과 같이 200 을 준다.
    return {"ok": True, "service": "store-api",
            "endpoints": ["/api/jobs", "/api/jobs/{site}-{pid}", "/api/jobs/lookup?url=",
                          "/api/search?q=", "/api/health", "/api/docs"]}


@app.get("/api/health")
def api_health() -> dict:
    try:
        return {"ok": True, "stats": health()}
    except Exception as e:                                          # noqa: BLE001
        raise HTTPException(500, {"ok": False, "error": str(e)}) from e


@app.get("/api/search")
def api_search(
    q: str = Query("", description="검색어"),
    kind: Literal["job", "post"] = "job",
    limit: int = 20,
    include_closed: str = "0",
) -> dict:
    query = q.strip()[:MAX_QUERY_CHARS]
    if not query:
        raise HTTPException(400, {"error": "q 파라미터가 필요하다"})
    closed = include_closed not in ("0", "", "false")
    return search(query, kind=kind, limit=max(1, min(limit, MAX_LIMIT)), include_closed=closed)


# ════════════════════════════════════════════════════════════════════
# 공고 목록 — 뷰어 filter.ts(applyFilter·computeFacets)를 SQL 로
# ════════════════════════════════════════════════════════════════════

# 고를 수 있는 축과, 각 축이 "맞는다" 는 조건. 칩 건수는 **자기 축만 빼고** 센다 —
# 그래야 숫자가 "이걸 누르면 몇 건이 되는지" 를 뜻한다(filter.ts computeFacets 와 같다).
# 빈 배열이면 그 축은 걸지 않는다.
_AXES: dict[str, str] = {
    "sites":     "(cardinality(%(sites)s::text[]) = 0 OR b.site = ANY(%(sites)s::text[]))",
    "regions":   "(cardinality(%(regions)s::text[]) = 0 OR b.region = ANY(%(regions)s::text[]))",
    "districts": "(cardinality(%(districts)s::text[]) = 0 OR b.district = ANY(%(districts)s::text[]))",
    "sizes":     "(cardinality(%(sizes)s::text[]) = 0 OR b.company_size = ANY(%(sizes)s::text[]))",
    "careers":   "(cardinality(%(careers)s::text[]) = 0 OR b.career_bucket = ANY(%(careers)s::text[]))",
    "roles":     "(cardinality(%(roles)s::text[]) = 0 OR b.roles && %(roles)s::text[])",
    "stacks":    "(b.stacks_lc @> %(stacks)s::text[])",
}


def _except(*skip: str) -> str:
    return " AND ".join(cond for k, cond in _AXES.items() if k not in skip) or "true"


# 모집단 — 모집 상태·검색어·중복 제거. 어느 축의 건수를 세든 **언제나** 걸린다.
# v_job 대신 표를 직접 조인한다: v_job 은 공고마다 기술 스택을 모아 붙이는 무거운
# 뷰라 4만 건을 칩 건수용으로 훑기엔 비싸다. 본문은 페이지에 실릴 50건만 v_job 에서 읽는다.
_BASE = """
    SELECT j.id, j.site::text AS site, j.first_seen_at, s.status::text AS status,
           f.region, f.district, f.company_size, f.career_bucket, f.roles, f.stacks,
           f.stacks_lc,
           CASE WHEN %(q)s = '' THEN 0
                WHEN strpos(lower(co.display_name), %(q)s) > 0 THEN 0
                WHEN strpos(lower(j.title), %(q)s) > 0 THEN 1
                ELSE 2 END AS q_rank
      FROM job j
      JOIN job_state s  ON s.job_id = j.id
      JOIN job_facet f  ON f.job_id = j.id
      JOIN company co   ON co.id = j.company_id
      LEFT JOIN mv_job_dup d ON d.job_id = j.id
     WHERE d.job_id IS NULL
       AND (%(closed)s = 'show' OR (%(closed)s = 'hide') = (s.status = 'active'))
       AND NOT (%(unverified_hide)s AND s.status = 'active' AND s.status_source = 'unknown')
       AND (%(sem)s OR %(q)s = '' OR f.hay LIKE %(q_like)s ESCAPE '\\')
       AND (NOT %(sem)s OR j.id = ANY(%(sem_ids)s::bigint[]))
"""

_FACETS = f"""
    WITH b AS MATERIALIZED ({_BASE})
    SELECT 'total' AS axis, NULL AS name, count(*) AS n FROM b WHERE {_except()}
    UNION ALL
    SELECT 'sites', site, count(*) FROM b WHERE {_except('sites')} GROUP BY site
    UNION ALL
    SELECT 'careers', career_bucket, count(*) FROM b WHERE {_except('careers')} GROUP BY career_bucket
    UNION ALL
    -- 지역을 셀 때는 시군구도 같이 뺀다 — 시군구는 지역에 딸린 축이라 '서울 강남구' 를
    -- 고른 채로 다른 시도를 세면 전부 0 이 된다.
    SELECT 'regions', region, count(*) FROM b WHERE {_except('regions', 'districts')} GROUP BY region
    UNION ALL
    SELECT 'districts', district, count(*) FROM b
     WHERE {_except('districts')} AND %(one_region)s::text IS NOT NULL
       AND b.region = %(one_region)s::text AND b.district IS NOT NULL
     GROUP BY district
    UNION ALL
    SELECT 'sizes', company_size, count(*) FROM b
     WHERE {_except('sizes')} AND company_size IS NOT NULL GROUP BY company_size
    UNION ALL
    SELECT 'roles', r, count(*) FROM b, unnest(b.roles) r WHERE {_except('roles')} GROUP BY r
    UNION ALL
    SELECT 'stacks', t, count(*) FROM b, unnest(b.stacks) t WHERE {_except('stacks')} GROUP BY t
"""

_PAGE_IDS = f"""
    WITH b AS ({_BASE})
    SELECT id FROM b WHERE {_except()}
     ORDER BY CASE WHEN %(sem)s THEN array_position(%(sem_ids)s::bigint[], id) END,
              q_rank, first_seen_at DESC, id DESC
     LIMIT %(limit)s OFFSET %(offset)s
"""

# 칩을 0건이어도 자리에 남겨 두는 축(지역·규모)은 "데이터에 존재하는 값" 이 따로
# 필요하다 — 모집 상태를 바꿀 때 칩이 나타났다 사라지며 자리가 흔들리지 않게.
_PRESENT = """
    SELECT count(*) AS all_total,
           array_agg(DISTINCT f.region) AS regions,
           array_agg(DISTINCT f.company_size) FILTER (WHERE f.company_size IS NOT NULL) AS sizes
      FROM job j
      JOIN job_facet f ON f.job_id = j.id
      LEFT JOIN mv_job_dup d ON d.job_id = j.id
     WHERE d.job_id IS NULL
"""


def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _slim(job: dict) -> dict:
    for k in HEAVY_FIELDS:
        job.pop(k, None)
    return job


def _job_rows_sql(where: str) -> str:
    """v_job 의 Job 컬럼 + job_facet 의 화면용 값.

    v_job 에도 region·company_size 가 있어서(원본 표기·미분류) 바로 조인하면 이름이
    겹친다. v_job 쪽을 먼저 하위 쿼리로 닫고 facet 값은 f_ 접두어로 붙인다.
    """
    return ("SELECT x.*, f.roles AS f_roles, f.region AS f_region, f.district AS f_district,"
            "       f.company_size AS f_company_size"
            "  FROM (" + JOB_SELECT + ", v.id FROM v_job v WHERE " + where + ") x"
            "  LEFT JOIN job_facet f ON f.job_id = x.id")


def _to_job(r: dict) -> dict:
    job = row_to_job(r, 0)
    # 목록 화면이 브라우저에서 계산하던 값들을 실어 보낸다(본문 없이 그릴 수 있게).
    job["roles"] = list(r["f_roles"] or [])
    job["place"] = {"region": r["f_region"], "district": r["f_district"]}
    if r["f_company_size"]:
        job["company_size"] = r["f_company_size"]
    return job


def _fetch_jobs_by_id(cur, ids: list[int]) -> dict[int, dict]:
    """페이지에 실을 공고를 v_job 에서 읽는다(순서는 호출부가 ids 로 정한다)."""
    if not ids:
        return {}
    cur.execute(_job_rows_sql("v.id = ANY(%(ids)s)"), {"ids": ids})
    return {r["id"]: _to_job(r) for r in cur.fetchall()}


def _split(values: list[str]) -> list[str]:
    """?site=a&site=b 와 ?site=a,b 를 둘 다 받는다."""
    out: list[str] = []
    for v in values:
        for part in v.split(","):
            part = part.strip()
            if part and part not in out:
                out.append(part)
    return out


def _counts(rows: list[dict], axis: str) -> list[dict]:
    items = [{"name": r["name"], "count": r["n"]} for r in rows if r["axis"] == axis]
    return sorted(items, key=lambda x: (-x["count"], x["name"]))


@app.get("/api/jobs")
def api_jobs(
    site: list[str] = Query([], description="사이트(wanted, saramin …). 여러 번 또는 쉼표"),
    career: list[str] = Query([], description="경력 구간(신입/무관, 1-2년 …)"),
    stack: list[str] = Query([], description="기술 스택 — 고른 것을 **전부** 가진 공고"),
    role: list[str] = Query([], description="직군(백엔드 …) — 하나라도 맞으면"),
    region: list[str] = Query([], description="시도(서울 …)"),
    district: list[str] = Query([], description="시군구(지역을 하나 골랐을 때)"),
    size: list[str] = Query([], description="회사 규모(대기업·중견기업·중소기업)"),
    q: str = Query("", description="검색어 — 회사·제목·본문 부분일치"),
    semantic: bool = Query(False, description="검색어를 의미 검색(하이브리드)으로"),
    closed: Literal["hide", "show", "only"] = "hide",
    unverified: Literal["show", "hide"] = "show",
    page: int = Query(1, ge=1),
    size_per_page: int = Query(PAGE_SIZE_DEFAULT, alias="limit", ge=1, le=PAGE_SIZE_MAX),
) -> dict:
    key = ("jobs", tuple(sorted(_split(site))), tuple(sorted(_split(career))),
           tuple(sorted(_split(stack))), tuple(sorted(_split(role))), tuple(sorted(_split(region))),
           tuple(sorted(_split(district))), tuple(sorted(_split(size))), q, semantic, closed,
           unverified, page, size_per_page)
    return _cached(key, lambda: _jobs_payload(site, career, stack, role, region, district, size,
                                              q, semantic, closed, unverified, page, size_per_page))


def _jobs_payload(site, career, stack, role, region, district, size, q, semantic, closed,
                  unverified, page, size_per_page) -> dict:
    query = _js_trim(q)[:MAX_QUERY_CHARS].lower()
    regions = _split(region)
    params = {
        "sites": _split(site), "careers": _split(career), "roles": _split(role),
        "regions": regions, "districts": _split(district), "sizes": _split(size),
        "stacks": [s.lower() for s in _split(stack)],
        "q": query, "q_like": _like(query),
        "closed": closed, "unverified_hide": unverified == "hide",
        # 시군구 칩은 지역을 딱 하나 골랐을 때만 뜻이 있다(Sidebar 와 같은 규칙).
        "one_region": regions[0] if len(regions) == 1 else None,
        "sem": False, "sem_ids": [],
        "limit": size_per_page, "offset": (page - 1) * size_per_page,
    }

    engines = None
    if semantic and query:
        # 의미 검색은 관련도 순서가 결과의 핵심이다. 후보를 먼저 뽑고 그 안에서 모든
        # 축을 건다(예전에는 사이트·경력·스택을 API 가 무시하고 지역·규모만 화면이 걸렀다).
        hits = search(_js_trim(q)[:MAX_QUERY_CHARS], limit=SEMANTIC_HITS,
                      include_closed=closed != "hide")
        ids = [int(h["id"]) for h in hits["results"]]
        params.update(sem=True, sem_ids=ids)
        engines = hits["engines"]

    with store_conn.cursor(autocommit=True) as cur:
        cur.execute(_FACETS, params)
        facet_rows = cur.fetchall()
        cur.execute(_PAGE_IDS, params)
        ids = [r["id"] for r in cur.fetchall()]
        by_id = _fetch_jobs_by_id(cur, ids)
        cur.execute(_PRESENT)
        present = cur.fetchone()

    total = next((r["n"] for r in facet_rows if r["axis"] == "total"), 0)
    region_count = {r["name"]: r["n"] for r in facet_rows if r["axis"] == "regions"}
    size_count = {r["name"]: r["n"] for r in facet_rows if r["axis"] == "sizes"}
    present_regions = set(present["regions"] or [])
    present_sizes = set(present["sizes"] or [])

    return {
        "total": total,                 # 필터를 건 결과 건수
        "all_total": present["all_total"],   # 전체 공고 수(모집중+마감, 중복 제외)
        "page": page,
        "limit": size_per_page,
        "items": [_slim(by_id[i]) for i in ids if i in by_id],
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


@app.get("/api/jobs/lookup")
def api_job_lookup(url: str = Query(..., description="공고 원문 URL")) -> dict:
    """추천 목록은 url 만 들고 있다 — 그 공고의 주소 키를 돌려준다."""
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute("SELECT site::text AS site, pid FROM job WHERE url = %s", (url,))
        r = cur.fetchone()
    if not r:
        raise HTTPException(404, {"error": "없는 공고"})
    return {"key": f"{r['site']}-{r['pid']}", "site": r["site"], "pid": r["pid"]}


@app.get("/api/jobs/{key}")
def api_job(key: str) -> dict:
    """공고 한 건(본문 포함). key 는 뷰어 주소의 `/jobs/<사이트>-<번호>` 그 부분이다."""
    site, sep, pid = key.partition("-")
    if not sep or not pid:
        raise HTTPException(400, {"error": "key 는 <사이트>-<번호>"})

    def load():
        with store_conn.cursor(autocommit=True) as cur:
            cur.execute(_job_rows_sql("v.site::text = %s AND v.pid = %s"), (site, pid))
            return cur.fetchone()

    r = _cached(("job", site, pid), load)
    if not r:
        raise HTTPException(404, {"error": f"공고 {key} 을(를) 찾지 못했습니다"})
    return _to_job(r)
