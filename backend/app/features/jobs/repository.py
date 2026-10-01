"""공고 조회 SQL — 뷰어 filter.ts(applyFilter·computeFacets)를 SQL 로 옮긴 것.

필터 축(지역·직군·경력·규모·스택)은 파이프라인이 `job_facet` 에 미리 채운다
(`catch_capture/store/jobs/facets.py`). 모집 상태는 `job_state` 뷰가 읽는 순간 계산한다.
"""
from __future__ import annotations

from app.db.session import cursor, fetch_one
from app.features.jobs.mapping import JOB_SELECT

# 고를 수 있는 축과, 각 축이 "맞는다" 는 조건. 칩 건수는 **자기 축만 빼고** 센다 —
# 그래야 숫자가 "이걸 누르면 몇 건이 되는지" 를 뜻한다. 빈 배열이면 그 축은 걸지 않는다.
AXES: dict[str, str] = {
    "sites":     "(cardinality(%(sites)s::text[]) = 0 OR b.site = ANY(%(sites)s::text[]))",
    "regions":   "(cardinality(%(regions)s::text[]) = 0 OR b.region = ANY(%(regions)s::text[]))",
    "districts": "(cardinality(%(districts)s::text[]) = 0 OR b.district = ANY(%(districts)s::text[]))",
    "sizes":     "(cardinality(%(sizes)s::text[]) = 0 OR b.company_size = ANY(%(sizes)s::text[]))",
    "careers":   "(cardinality(%(careers)s::text[]) = 0 OR b.career_bucket = ANY(%(careers)s::text[]))",
    "roles":     "(cardinality(%(roles)s::text[]) = 0 OR b.roles && %(roles)s::text[])",
    "stacks":    "(b.stacks_lc @> %(stacks)s::text[])",
}


def _except(*skip: str) -> str:
    return " AND ".join(cond for k, cond in AXES.items() if k not in skip) or "true"


# 모집단 — 모집 상태·검색어·중복 제거. 어느 축의 건수를 세든 **언제나** 걸린다.
# v_job 대신 표를 직접 조인한다: v_job 은 공고마다 기술 스택을 모아 붙이는 무거운
# 뷰라 4만 건을 칩 건수용으로 훑기엔 비싸다. 본문은 페이지에 실릴 건만 v_job 에서 읽는다.
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


def _job_rows_sql(where: str) -> str:
    """v_job 의 Job 컬럼 + job_facet 의 화면용 값.

    v_job 에도 region·company_size 가 있어서(원본 표기·미분류) 바로 조인하면 이름이
    겹친다. v_job 쪽을 먼저 하위 쿼리로 닫고 facet 값은 f_ 접두어로 붙인다.
    """
    return ("SELECT x.*, f.roles AS f_roles, f.region AS f_region, f.district AS f_district,"
            "       f.company_size AS f_company_size"
            "  FROM (" + JOB_SELECT + ", v.id FROM v_job v WHERE " + where + ") x"
            "  LEFT JOIN job_facet f ON f.job_id = x.id")


def list_page(params: dict) -> tuple[list[dict], list[int], dict[int, dict], dict]:
    """칩 건수 행, 페이지의 공고 id(순서대로), id → 행, 존재하는 지역·규모."""
    with cursor() as cur:
        cur.execute(_FACETS, params)
        facet_rows = cur.fetchall()
        cur.execute(_PAGE_IDS, params)
        ids = [r["id"] for r in cur.fetchall()]
        rows: dict[int, dict] = {}
        if ids:
            cur.execute(_job_rows_sql("v.id = ANY(%(ids)s)"), {"ids": ids})
            rows = {r["id"]: r for r in cur.fetchall()}
        cur.execute(_PRESENT)
        present = cur.fetchone()
    return facet_rows, ids, rows, present


def find_by_key(site: str, pid: str) -> dict | None:
    return fetch_one(_job_rows_sql("v.site::text = %s AND v.pid = %s"), (site, pid))


def find_key_by_url(url: str) -> dict | None:
    return fetch_one("SELECT site::text AS site, pid FROM job WHERE url = %s", (url,))
