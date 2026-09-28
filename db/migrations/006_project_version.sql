-- 006 — 외주 프로젝트 단가 이력과 시장 추이
--
-- 왜. "단가가 얼마나 떨어졌나"는 두 질문이다.
--   ① 한 프로젝트가 올라온 뒤 단가를 내렸나(사람이 안 구해져서 올렸나/내렸나)
--   ② 시장 전체에서 새로 올라오는 자리의 단가가 주마다 어떻게 움직이나
-- project 는 최신 값 하나만 들고 있어서 둘 다 답하지 못한다. 지난 값은 다시 받아
-- 올 수도 없다 — 그래서 바뀐 순간을 쌓는다(job_version 과 같은 생각).
--
-- project_version : 단가·기간·모집 표시가 바뀐 순간 한 행. 처음 본 순간도 한 행(출발점).
-- project_pay_weekly : 주별로 새로 올라온 자리의 월 단가 중앙값. '올라올 때 값'(첫 버전)으로
--                      센다 — 나중에 내린 값으로 세면 추이가 이중으로 내려 보인다.
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/006_project_version.sql   (두 번 돌려도 안전)
-- schema.sql 의 "15. 외주 프로젝트 이력" 과 글자 그대로 같다.

BEGIN;

CREATE TABLE IF NOT EXISTS project_version (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id    bigint      NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    seen_at       timestamptz NOT NULL,
    budget_basis  budget_basis,
    budget_min    integer,
    budget_max    integer,
    duration_days integer,
    source_open   boolean     NOT NULL,
    applicants    integer,
    reason        text                    -- 닫힌 근거 등(재확인에서 왔을 때)
);
CREATE INDEX IF NOT EXISTS project_version_idx ON project_version (project_id, seen_at);

-- 한 프로젝트의 첫 값과 마지막 값. 단가를 바꾼 자리만 뽑을 때 쓴다.
CREATE OR REPLACE VIEW project_budget_move AS
WITH v AS (
    SELECT project_id, seen_at, budget_basis,
           (COALESCE(budget_min, budget_max) + COALESCE(budget_max, budget_min)) / 2.0 AS mid,
           row_number() OVER (PARTITION BY project_id ORDER BY seen_at)      AS rn_first,
           row_number() OVER (PARTITION BY project_id ORDER BY seen_at DESC) AS rn_last
      FROM project_version
     WHERE budget_basis = 'monthly' AND COALESCE(budget_min, budget_max) IS NOT NULL
)
SELECT f.project_id, f.mid AS first_monthly, l.mid AS last_monthly,
       round((l.mid - f.mid) / f.mid * 100, 1) AS pct, f.seen_at AS first_at, l.seen_at AS last_at
  FROM v f JOIN v l ON l.project_id = f.project_id AND l.rn_last = 1
 WHERE f.rn_first = 1 AND l.mid <> f.mid;

CREATE OR REPLACE VIEW project_pay_weekly AS
WITH first_v AS (
    SELECT DISTINCT ON (project_id) project_id, budget_min, budget_max
      FROM project_version
     WHERE budget_basis = 'monthly' AND COALESCE(budget_min, budget_max) IS NOT NULL
     ORDER BY project_id, seen_at
)
SELECT date_trunc('week', COALESCE(p.posted_on, p.first_seen_at::date))::date AS week,
       p.work_mode,
       count(*) AS n,
       percentile_cont(0.5) WITHIN GROUP (
           ORDER BY (COALESCE(fv.budget_min, fv.budget_max) + COALESCE(fv.budget_max, fv.budget_min)) / 2.0
       ) AS median_monthly
  FROM project p JOIN first_v fv ON fv.project_id = p.id
 -- 등록일이 없는 곳은 '처음 본 날'로 센다. 첫 수집 날 한꺼번에 들어온 것은 그 주에 올라온
 -- 자리가 아니라 이미 있던 자리라 뺀다(넣으면 첫 주만 수백 건으로 부푼다).
 WHERE p.posted_on IS NOT NULL
    OR p.first_seen_at::date > (SELECT min(first_seen_at)::date FROM project)
 GROUP BY 1, 2;

COMMIT;
