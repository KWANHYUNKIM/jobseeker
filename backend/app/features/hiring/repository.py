"""채용 추이 SQL — 회사마다 주별로 새 공고를 몇 건 냈고, 낸 공고가 얼마 만에 닫혔나.

'언제 올라왔나'(opened_at)는 원본이 말한 등록일(posted_on)이 먼저고, 없으면 우리가 처음 본
시각(first_seen_at)이다. 처음 본 시각만 믿으면 **사이트를 새로 붙인 주**에 그 사이트의 묵은
공고가 한꺼번에 '새 공고'로 잡힌다 — 그래서 등록일이 없고 사이트의 첫 수집 3일 안에 처음 본
공고는 추이에서 뺀다(BACKFILL_DAYS).

'언제 닫혔나'(closed_at)는 셋 중 가장 이른 것: 목록에서 사라진 시각(gone_at), 원본에 다시
물어 마감이라고 들은 첫 시각, 마감으로 판정된 공고의 마감일. 모집중이면 NULL 이다.

대상은 메인과 같은 'IT 공고' — 중복 사본·해외·직군이 '기타' 하나뿐인 공고를 뺀 것.
"""
from __future__ import annotations

from app.db.session import cursor

BACKFILL_DAYS = 3

_JOBS = """
    WITH site_start AS (
        SELECT site, min(first_seen_at) AS started FROM job GROUP BY site
    ),
    j AS (
        SELECT j.id, j.company_id, j.site::text AS site, f.roles, f.company_size,
               {hc_n} AS hc_n, {hc_digits} AS hc_digits,
               COALESCE(j.posted_on::timestamptz, j.first_seen_at) AS opened_at,
               s.status::text AS status,
               LEAST(j.gone_at, cl.closed_at,
                     CASE WHEN s.status = 'closed' THEN s.effective_deadline::timestamptz END) AS closed_at
          FROM job j
          JOIN job_state s     ON s.job_id = j.id
          JOIN job_facet f     ON f.job_id = j.id
          JOIN site_start ss   ON ss.site = j.site
          LEFT JOIN mv_job_dup d ON d.job_id = j.id
          LEFT JOIN LATERAL (
              SELECT min(c.checked_at) AS closed_at
                FROM job_closure_check c
               WHERE c.job_id = j.id AND c.closed
          ) cl ON true
         WHERE d.job_id IS NULL
           AND NOT j.overseas
           AND NOT (f.roles <@ ARRAY['기타']::text[])
           AND NOT (j.posted_on IS NULL
                    AND j.first_seen_at < ss.started + make_interval(days => %(backfill)s))
           AND COALESCE(j.posted_on::timestamptz, j.first_seen_at) >= %(since)s
    )
"""

# 회사 × 주 — 주는 월요일 시작(DB 시간대 Asia/Seoul 기준, db/migrations/002).
# 자리 수 — 정확한 수(hc_n)는 그대로, 자릿수 표기는 구간(○ = 1~9, ○○ = 10~99)으로 센다.
_WEEKLY = _JOBS + """
    SELECT j.company_id, date_trunc('week', j.opened_at)::date AS week, count(*) AS n,
           count(*) FILTER (WHERE j.hc_digits IS NOT NULL)                     AS hc_known,
           count(*) FILTER (WHERE j.hc_n IS NOT NULL)                          AS hc_exact,
           count(*) FILTER (WHERE j.hc_n IS NULL AND j.hc_digits = 1)          AS hc_one,
           count(*) FILTER (WHERE j.hc_n IS NULL AND j.hc_digits >= 2)         AS hc_two,
           COALESCE(sum(COALESCE(j.hc_n, (10 ^ (j.hc_digits - 1))::int)), 0)   AS seats_low,
           COALESCE(sum(COALESCE(j.hc_n, (10 ^ j.hc_digits)::int - 1)), 0)     AS seats_high
      FROM j
     GROUP BY 1, 2
"""

# 회사 하나의 합계. 닫힌 공고의 '열려 있던 날 수' 중앙값과, 2주 안에 닫힌 건수.
_COMPANY = _JOBS + """
    SELECT c.id AS company_id, c.display_name AS company, c.slug, c.logo_url,
           -- 규모는 company.size 가 아니라 뷰어 칩과 같은 job_facet 값(공고마다 같다, 가장 많은 것)
           mode() WITHIN GROUP (ORDER BY j.company_size) AS size,
           count(*) AS total,
           count(*) FILTER (WHERE j.status = 'active') AS active,
           count(*) FILTER (WHERE j.closed_at IS NOT NULL) AS closed,
           count(*) FILTER (WHERE j.closed_at IS NOT NULL
                              AND j.closed_at - j.opened_at <= make_interval(days => %(fast_days)s)) AS closed_fast,
           percentile_cont(0.5) WITHIN GROUP (
               ORDER BY extract(epoch FROM j.closed_at - j.opened_at) / 86400.0
           ) FILTER (WHERE j.closed_at IS NOT NULL AND j.closed_at >= j.opened_at) AS median_open_days,
           array_agg(DISTINCT j.site) AS sites
      FROM j
      JOIN company c ON c.id = j.company_id
     GROUP BY c.id
"""

# 회사마다 많이 뽑는 직군
_ROLES = _JOBS + """
    SELECT j.company_id, r AS role, count(*) AS n
      FROM j, unnest(j.roles) r
     WHERE r <> '기타'
     GROUP BY 1, 2
"""


# 수집을 시작한 날. 그 전에 올라온 공고는 '그날까지 살아남은 것'만 잡혀 있어서(닫힌 건 못 봤다)
# 그 주들의 건수는 실제보다 적다 — 서비스가 비교에서 뺀다.
_COVERAGE = "SELECT min(first_seen_at) AS started FROM job"


def coverage_start():
    with cursor() as cur:
        cur.execute(_COVERAGE)
        return cur.fetchone()["started"]


def _cols(cur) -> dict:
    """모집인원 컬럼(021)이 없는 DB 에서도 추이는 답한다 — 자리 수만 비어서 나간다."""
    cur.execute("SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'job' AND column_name = 'headcount_digits'")
    if cur.fetchone():
        return {"hc_n": "j.headcount_n", "hc_digits": "j.headcount_digits"}
    return {"hc_n": "NULL::smallint", "hc_digits": "NULL::smallint"}


def window_rows(since, fast_days: int) -> tuple[list[dict], list[dict], list[dict], bool]:
    """(회사 합계, 회사 × 주, 회사 × 직군, 모집인원 컬럼 있음) — since 이후에 올라온 공고 기준."""
    params = {"since": since, "backfill": BACKFILL_DAYS, "fast_days": fast_days}
    with cursor() as cur:
        cols = _cols(cur)
        cur.execute(_COMPANY.format(**cols), params)
        companies = cur.fetchall()
        cur.execute(_WEEKLY.format(**cols), params)
        weekly = cur.fetchall()
        cur.execute(_ROLES.format(**cols), params)
        roles = cur.fetchall()
    return companies, weekly, roles, cols["hc_n"] != "NULL::smallint"
