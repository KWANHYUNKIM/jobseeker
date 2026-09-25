-- 002 — DB 의 "오늘" 과 "지금" 을 한국 시각으로 맞춘다
--
-- 왜 필요한가. 컨테이너의 기본 시간대가 UTC 라서 두 가지가 어긋나 있었다.
--
--   (1) job_state 의 CURRENT_DATE 가 UTC 날짜다. 한국 시각 00:00~09:00 사이에는
--       DB 의 "오늘" 이 하루 전이라, 어제로 마감이 끝난 공고가 아침 9시까지
--       모집중으로 남는다(2026-09-26 07시 기준 108건). 파이썬 쪽(job_status)은
--       date.today() — 한국 날짜 — 를 쓰므로 같은 공고를 두 판정이 다르게 본다.
--   (2) close_check 는 확인 시각을 시간대 없는 한국 시각으로 넘겼고, UTC 세션은
--       그걸 UTC 로 읽었다. job_closure_check 의 close_check 행이 전부 9시간
--       미래로 저장돼 있다(26,010행). backfill 행은 DB now() 로 찍혀 멀쩡하다.
--
-- 고치는 것.
--   · 데이터베이스 기본 시간대를 Asia/Seoul 로 — 새 세션부터 CURRENT_DATE 가 한국
--     날짜가 되고, 시간대 없는 값도 한국 시각으로 읽힌다(psql 로 붙어도 같다).
--   · 이미 9시간 밀려 저장된 close_check 행을 한 번 되돌린다.
--
-- 전제: 그 행들을 쓴 머신이 한국 시각(KST)으로 돌고 있었다. UTC 로 도는 머신이
-- 쓴 DB 라면 (2) 는 돌리지 말 것 — 그쪽 값은 우연히 맞게 들어가 있다.
--
-- 두 번 돌려도 안전하다: 시간대가 이미 Asia/Seoul 로 걸려 있으면 되돌리기를
-- 건너뛴다(같은 행을 두 번 당기면 이번엔 9시간 과거로 틀어진다).
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/002_timezone_kst.sql

BEGIN;

DO $$
DECLARE
    already boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
          FROM pg_db_role_setting s
          JOIN pg_database d ON d.oid = s.setdatabase
         WHERE d.datname = current_database()
           AND s.setrole = 0
           AND 'TimeZone=Asia/Seoul' = ANY (s.setconfig)
    ) INTO already;

    IF NOT already THEN
        UPDATE job_closure_check
           SET checked_at = checked_at - interval '9 hours'
         WHERE checker = 'close_check';
        EXECUTE format('ALTER DATABASE %I SET "TimeZone" TO %L',
                       current_database(), 'Asia/Seoul');
    END IF;
END $$;

COMMIT;
