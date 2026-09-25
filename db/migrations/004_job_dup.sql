-- 004 — 사이트 간 중복 공고를 한 건으로 접는다
--
-- 왜 필요한가. 같은 공고가 saramin·jobkorea·jumpit 에 같이 올라온다. 파일 파이프라인은
-- aggregate 가 (회사명+제목)으로 첫 등장만 남겼는데(한 사이클 9,235건), 정본 DB 는
-- URL 로 공고를 식별하므로 그 셋을 다 들고 있다. 뷰어 JSON 을 DB 에서 뽑기 시작하자
-- (store.export) 목록이 28.9k → 38.7k 로 불었고 모집중만 2,031건이 겹쳤다.
--
-- 지우지 않는다. 사이트마다 마감 판정·등록일이 따로 오고, 어느 한 곳의 답이 다른
-- 곳의 답을 대신할 수 없다. 대신 "이 공고는 저 공고의 사본" 이라고 가리키는 뷰를
-- 두고, 읽는 쪽(store.export → 뷰어·빌더)이 사본을 걸러 낸다.
--
-- 대표를 고르는 순서: 모집중인 것 → aggregate 의 사이트 순서(wanted 가 먼저) →
-- 먼저 본 것. 회사는 company_id 로 묶는다 — 원본 표기가 달라도((주)클로봇 ≠ 클로봇)
-- 같은 회사다. aggregate 보다 조금 더 많이 접히는 이유가 이것이다.
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/004_job_dup.sql
-- 두 번 돌려도 안전하다.

BEGIN;

CREATE OR REPLACE VIEW job_dup AS
WITH k AS (
    SELECT j.id, j.company_id,
           regexp_replace(lower(j.title), '\s+', '', 'g') AS title_key,
           s.status,
           array_position(ARRAY['wanted','jumpit','jobkorea','saramin','dev','remote','ats'],
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
