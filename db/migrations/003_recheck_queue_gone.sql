-- 003 — 목록에서 사라진 공고도 마감 재확인 대상에 넣는다
--
-- 왜 필요한가. job_recheck_queue 가 `WHERE j.gone_at IS NULL` 로 **목록에서 사라진
-- 공고를 빼고** 있었다. 그런데 목록에서 사라졌다는 것이야말로 마감의 가장 강한
-- 신호다. 빠진 공고는 원장에 답이 없으면 job_state 에서 영영 모집중이다
-- (2026-09-26 기준 767건, 그중 388건은 한 번도 확인받지 못했다).
--
-- gone_at 만으로 닫지 않는 이유는 CLAUDE.md 에 적힌 그대로다 — 크롤이 차단당한 것과
-- 공고가 내려간 것은 다르다. 그래서 닫는 건 여전히 원본에 물어본 답이고, 여기서는
-- "사라진 것부터 먼저 물어보라" 는 재료(gone_at)와, 주기를 정할 재료(원장의
-- 마감일)를 함께 내준다. 순서와 주기는 close_check 가 정한다.
--
-- CREATE OR REPLACE VIEW 는 컬럼을 **끝에만** 붙일 수 있다. schema.sql 도 같은 모양이다.
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/003_recheck_queue_gone.sql
-- 두 번 돌려도 안전하다.

BEGIN;

CREATE OR REPLACE VIEW job_recheck_queue AS
SELECT j.id, j.site, j.pid, j.url, co.display_name AS company, j.title,
       s.status, c.checked_at, COALESCE(c.closed, false) AS ledger_closed,
       j.gone_at, c.deadline_on AS ledger_deadline
  FROM job j
  LEFT JOIN company co ON co.id = j.company_id
  LEFT JOIN job_state s ON s.job_id = j.id
  LEFT JOIN job_closure_latest c ON c.job_id = j.id
 ORDER BY c.checked_at NULLS FIRST, j.last_seen_at DESC;

COMMIT;
