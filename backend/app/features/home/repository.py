"""메인 화면 SQL — 모집중인 국내 IT 공고를 회사별로 묶기 전의 행.

묶기·업종 가르기·정렬은 service 가 파이썬으로 한다(1만여 행이라 한 번 읽고 캐시한다).
'IT 공고' 는 직군이 '기타' 하나뿐인 공고를 뺀 것이다(job_facet.roles — 뷰어 칩과 같은 규칙).
"""
from __future__ import annotations

from app.db.session import cursor

_ROWS = """
    SELECT j.site::text AS site, j.pid, j.url, j.title, j.career_text, j.first_seen_at,
           s.dday, s.effective_deadline,
           f.region, f.district, f.career_bucket, f.roles, f.company_size, f.stacks,
           co.id AS company_id, co.display_name AS company, co.slug AS company_slug, co.logo_url
      FROM job j
      JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
      JOIN job_facet f ON f.job_id = j.id
      JOIN company co  ON co.id = j.company_id
      LEFT JOIN mv_job_dup d ON d.job_id = j.id
     WHERE d.job_id IS NULL
       AND NOT j.overseas
       AND NOT (f.roles <@ ARRAY['기타']::text[])
"""


def active_it_rows() -> list[dict]:
    with cursor() as cur:
        cur.execute(_ROWS)
        return cur.fetchall()
