-- 007 — 외주 프로젝트의 등급·유형·분야·직무
--
-- 왜. 프리랜서 몸값은 '중간값 하나'로 말할 수 없다. SI/SM 시장은 등급(초급·중급·고급·특급)으로
-- 단가를 부르고, 같은 등급이어도 SI 인지 SM 인지, 금융인지 공공인지, 백엔드인지 PM 인지에
-- 따라 갈린다. 분류는 catch_capture/pipeline/freelance_rates.classify 가 한다(정규식이라 SQL 로
-- 옮기면 두 벌이 된다) — 여기는 그 결과를 싣고, 등급별로 나눠 세는 뷰만 둔다.
--
-- grade_basis 가 '경력 추정'인 등급은 원본에 적힌 게 아니라 경력 연수로 가른 것이다
-- (초급 <3 · 중급 3~6 · 고급 7~9 · 특급 10+). 뷰는 둘을 함께 세고 건수는 따로 낸다.
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/007_project_grade.sql   (두 번 돌려도 안전)
-- schema.sql 의 "16. 외주 프로젝트 등급" 과 글자 그대로 같다.

BEGIN;

ALTER TABLE project ADD COLUMN IF NOT EXISTS grade       text;
ALTER TABLE project ADD COLUMN IF NOT EXISTS grade_basis text;
ALTER TABLE project ADD COLUMN IF NOT EXISTS domain      text;
ALTER TABLE project ADD COLUMN IF NOT EXISTS work_type   text;
ALTER TABLE project ADD COLUMN IF NOT EXISTS role        text;

DO $$ BEGIN
    ALTER TABLE project ADD CONSTRAINT project_grade_known
        CHECK (grade IS NULL OR grade IN ('초급','중급','고급','특급','혼합'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE project ADD CONSTRAINT project_grade_basis_known
        CHECK (grade_basis IS NULL OR grade_basis IN ('표기','경력 추정'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE project ADD CONSTRAINT project_work_type_known
        CHECK (work_type IS NULL OR work_type IN ('SI','SM'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS project_grade_idx ON project (grade) WHERE grade IS NOT NULL;

-- 등급 × (유형·분야·직무·근무) 월 단가. '올라올 때 값'(첫 버전)으로 센다.
-- dim 이 축 이름, key 가 그 축의 값이다 — 축마다 뷰를 따로 두면 화면이 넷을 이어 붙여야 한다.
CREATE OR REPLACE VIEW project_pay_by_grade AS
WITH first_v AS (
    SELECT DISTINCT ON (project_id) project_id,
           (COALESCE(budget_min, budget_max) + COALESCE(budget_max, budget_min)) / 2.0 AS monthly
      FROM project_version
     WHERE budget_basis = 'monthly' AND COALESCE(budget_min, budget_max) IS NOT NULL
     ORDER BY project_id, seen_at
), base AS (
    SELECT p.grade, p.grade_basis, fv.monthly, p.work_type, p.domain, p.role,
           p.work_mode::text AS work_mode
      FROM project p JOIN first_v fv ON fv.project_id = p.id
     WHERE p.grade IN ('초급','중급','고급','특급') AND fv.monthly BETWEEN 150 AND 3000
), dims AS (
    SELECT 'all'       AS dim, '전체'      AS key, * FROM base
    UNION ALL SELECT 'work_type', work_type, * FROM base WHERE work_type IS NOT NULL
    UNION ALL SELECT 'domain',    domain,    * FROM base WHERE domain IS NOT NULL
    UNION ALL SELECT 'role',      role,      * FROM base WHERE role IS NOT NULL
    UNION ALL SELECT 'work_mode', work_mode, * FROM base WHERE work_mode IS NOT NULL
)
SELECT dim, key, grade,
       count(*)                                                      AS n,
       count(*) FILTER (WHERE grade_basis = '표기')                   AS n_explicit,
       percentile_cont(0.25) WITHIN GROUP (ORDER BY monthly)         AS p25,
       percentile_cont(0.5)  WITHIN GROUP (ORDER BY monthly)         AS median,
       percentile_cont(0.75) WITHIN GROUP (ORDER BY monthly)         AS p75
  FROM dims
 GROUP BY dim, key, grade;

COMMIT;
