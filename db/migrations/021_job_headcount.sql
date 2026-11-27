-- 021 — 공고의 모집인원(몇 자리를 뽑나)을 job 에 둔다.
--
-- 왜. 공고 수는 채용의 크기가 아니다 — 한 건이 1명일 수도, 두 자릿수일 수도 있다. 개발 공고는
-- 인원을 숫자 대신 자릿수로 쓰는 일이 많다(○명 = 한 자릿수, ○○명 = 두 자릿수). 그 표기를 그대로
-- 남겨 '정확한 수'와 '자릿수 구간'을 같이 센다. 규칙은 `catch_capture/core/headcount.py`.
--
-- 어디서 오나.
--   page  잡코리아 공고 페이지의 '모집인원' 칸 — close_check 가 마감을 묻느라 이미 받는 페이지에서 읽는다
--   text  본문의 "모집인원 : ○명" 문구 — `python -m store.jobs.headcount` 가 채운다
-- page 가 text 를 이긴다(칸은 회사가 직접 고른 값이다). 0명·빈칸은 '밝히지 않음'이라 NULL 로 둔다.
--
-- 적용:  docker exec -i jobseeker-db psql -U jobseeker -d jobseeker -v ON_ERROR_STOP=1 < db/migrations/021_job_headcount.sql
--        (두 번 돌려도 안전하다)

BEGIN;

ALTER TABLE job ADD COLUMN IF NOT EXISTS headcount_raw    text;      -- 원문('○○명')
ALTER TABLE job ADD COLUMN IF NOT EXISTS headcount_n      smallint;  -- 정확한 수. 자릿수 표기면 NULL
ALTER TABLE job ADD COLUMN IF NOT EXISTS headcount_digits smallint;  -- 자릿수 — 1: 1~9명, 2: 10~99명
ALTER TABLE job ADD COLUMN IF NOT EXISTS headcount_source text;      -- 'page' | 'text'

DO $$ BEGIN
    ALTER TABLE job ADD CONSTRAINT job_headcount_sane
        CHECK ((headcount_n IS NULL OR headcount_n BETWEEN 1 AND 9999)
           AND (headcount_digits IS NULL OR headcount_digits BETWEEN 1 AND 4)
           AND (headcount_source IS NULL OR headcount_source IN ('page', 'text')));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

COMMENT ON COLUMN job.headcount_digits IS '모집인원의 자릿수. ○명=1(1~9명), ○○명=2(10~99명). 정확한 수가 있어도 채운다';

COMMIT;
