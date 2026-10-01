-- 013 — 사이트 'boards'(국내 채용 보드·공공기관 채용)
--
-- wanted·jumpit·jobkorea·saramin·catch 밖에서 공고를 받기 시작했다 — 랠릿·슈퍼루키·
-- 인크루트·잡알리오(crawlers/crawl_boards.py). 출처마다 사이트를 따로 두지 않고 ats·remote
-- 처럼 한 사이트 안에서 pid 의 provider 로 가른다('rallit:dev:1872').
-- 중복 대표 순서에서는 맨 뒤다 — 같은 공고가 회사 채용페이지(ats)나 기존 보드에 있으면
-- 그쪽이 대표가 된다(보드는 대개 옮겨 실은 것이다).
--
-- 적용:  docker exec -i jobseeker-db psql -U jobseeker -d jobseeker -v ON_ERROR_STOP=1 < db/migrations/013_site_boards.sql
-- 두 번 돌려도 안전하다. ADD VALUE 는 같은 트랜잭션에서 새 값을 못 쓰므로 BEGIN 밖에 둔다.

ALTER TYPE job_site ADD VALUE IF NOT EXISTS 'boards';

BEGIN;

CREATE OR REPLACE VIEW job_dup AS
WITH k AS (
    SELECT j.id, j.company_id,
           regexp_replace(lower(j.title), '\s+', '', 'g') AS title_key,
           s.status,
           array_position(ARRAY['wanted','jumpit','jobkorea','saramin','dev','remote','ats','boards'],
                          j.site::text) AS site_rank,
           j.first_seen_at
      FROM job j
      JOIN job_state s ON s.job_id = j.id
), r AS (
    SELECT id,
           first_value(id) OVER w AS canonical_id,
           row_number()    OVER w AS rn
      FROM k
    WINDOW w AS (PARTITION BY company_id, title_key
                 ORDER BY (status = 'active') DESC, site_rank, first_seen_at, id)
)
SELECT id AS job_id, canonical_id
  FROM r
 WHERE rn > 1;

COMMENT ON VIEW job_dup IS '사이트 간(또는 같은 사이트 안) 중복 공고 → 대표 공고. 사본만 담는다';

COMMIT;
