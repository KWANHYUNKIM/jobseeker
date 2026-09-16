-- 001 — 공고 등록일(posted_on)
--
-- `db/schema.sql` 은 **새로 까는 DB** 의 정본이다. 이미 돌고 있는 DB 는 그 파일을
-- 다시 돌릴 수 없으므로(테이블이 이미 있다) 같은 결과를 내는 ALTER 를 여기 둔다.
-- 둘은 반드시 같은 모양을 만들어야 한다 — 특히 v_job 의 **컬럼 순서**가 그렇다.
--
-- 왜 필요한가. 공고가 언제 올라왔는지를 어디에도 저장하지 않고 있었다. 그래서
-- 목록을 최신순으로 줄 세울 수도, "올라온 지 3일" 을 보여줄 수도 없었고, 모집
-- 캘린더의 시작일 칸이 늘 비어 있었다. 값 자체는 원본이 이미 주고 있다 —
-- wanted·jobkorea·catch 의 JSON-LD `datePosted`, jumpit 의 `publishedAt`.
-- `pipeline.close_check` 가 마감을 재확인하면서 같이 받아 와 여기 채운다.
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/001_posted_on.sql
-- 두 번 돌려도 안전하다.

BEGIN;

-- ── 1. 공고 ─────────────────────────────────────────────────────────
ALTER TABLE job ADD COLUMN IF NOT EXISTS posted_on date;

COMMENT ON COLUMN job.posted_on IS
  '원본이 말한 등록일. close_check 만 쓴다(COALESCE 로 덮어쓰지 않는다). saramin 은 NULL';

-- 미래의 등록일은 파싱 사고다. deadline_on 이 쓰는 것과 같은 그물.
-- NOT VALID 로 붙였다가 검증한다 — 기존 행이 많아도 긴 잠금을 잡지 않는다.
DO $$
BEGIN
    ALTER TABLE job ADD CONSTRAINT job_posted_sane
        CHECK (posted_on IS NULL OR posted_on BETWEEN DATE '2015-01-01' AND DATE '2100-01-01')
        NOT VALID;
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;
ALTER TABLE job VALIDATE CONSTRAINT job_posted_sane;

-- 목록 "최신순" — 등록일이 없는 공고는 뒤로 민다
CREATE INDEX IF NOT EXISTS job_posted_idx ON job (posted_on DESC NULLS LAST);

-- ── 2. 재확인 원장 ──────────────────────────────────────────────────
-- "언제 물어봤더니 뭐라 답했나" 에 등록일도 포함시킨다. job.posted_on 이 지워져도
-- 여기서 다시 세울 수 있어야 한다.
ALTER TABLE job_closure_check ADD COLUMN IF NOT EXISTS posted_on date;

CREATE OR REPLACE VIEW job_closure_latest AS
SELECT DISTINCT ON (job_id) job_id, checked_at, closed, deadline_on, evidence, checker, posted_on
  FROM job_closure_check
 ORDER BY job_id, checked_at DESC;

-- ── 3. 화면이 읽는 뷰 ───────────────────────────────────────────────
-- posted_on 을 **맨 끝에** 붙인다. CREATE OR REPLACE VIEW 는 기존 컬럼의 순서와
-- 타입을 바꾸지 못하고, 중간에 끼우면 v_job 을 DROP 해야 한다 — 그러면 이 뷰에
-- 매달린 것들까지 같이 내려간다. schema.sql 도 같은 자리에 두었다.
CREATE OR REPLACE VIEW v_job AS
SELECT
    j.id,
    j.site,
    j.pid,
    j.site || '-' || j.pid AS job_key,
    j.url,
    co.slug         AS company_slug,
    co.display_name AS company,
    co.size         AS company_size,
    j.title,
    j.career_text, j.career_min, j.accepts_entry,
    j.location_text, j.sido, j.sigungu, j.region, j.overseas,
    j.employment, j.education, j.source_board,
    j.main_tasks, j.qualifications, j.preferences, j.benefits, j.full_jd,
    j.deadline_text,
    s.status, s.status_source, s.effective_deadline AS deadline_on, s.dday, s.last_verified_at,
    j.first_seen_at, j.last_seen_at,
    COALESCE(t.techs, '{}'::text[]) AS tech_stack,
    j.posted_on
FROM job j
JOIN company co ON co.id = j.company_id
JOIN job_state s ON s.job_id = j.id
LEFT JOIN LATERAL (
    SELECT array_agg(te.name ORDER BY te.name) AS techs
      FROM job_tech jt JOIN tech te ON te.id = jt.tech_id
     WHERE jt.job_id = j.id AND NOT te.is_noise
) t ON true;

-- ── 4. 이미 쌓인 원장에서 되살리기 ──────────────────────────────────
-- 이 마이그레이션 이전의 확인 기록에는 등록일이 없으므로 대개 0건이다.
-- 마이그레이션을 두 번 돌리거나, 원장만 먼저 채운 경우를 위해 남겨 둔다.
UPDATE job j
   SET posted_on = c.posted_on
  FROM job_closure_latest c
 WHERE c.job_id = j.id
   AND c.posted_on IS NOT NULL
   AND j.posted_on IS NULL;

COMMIT;
