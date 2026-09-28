-- 008 — 외주 단가표 일별 스냅숏
--
-- 왜. "지금 단가표"는 매일 달라지고, 지난날의 단가표는 다시 계산할 수 없다 — 목록에서
-- 내려간 자리는 다시 보이지 않고, 최근 90일이라는 창도 날마다 움직인다. 그래서 크롤이
-- 돌 때마다 그날의 현재 단가표(등급 × 전체·SI·SM)를 한 줄씩 남긴다. 같은 날 여러 번 돌면
-- 마지막 값으로 바꾼다(PK 가 날짜·등급·열이다).
--
-- 월별 추이(그 달에 올라온 자리의 단가)는 project + project_version 에서 언제든 다시 셀 수
-- 있어 저장하지 않는다. 여기는 '그날 시장이 어땠나'만 담는다.
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/008_project_rate_snapshot.sql   (두 번 돌려도 안전)
-- schema.sql 의 "17. 외주 단가표 스냅숏" 과 글자 그대로 같다.

BEGIN;

CREATE TABLE IF NOT EXISTS project_rate_snapshot (
    day     date     NOT NULL,
    grade   text     NOT NULL,
    col     text     NOT NULL,          -- '전체' | 'SI' | 'SM'
    n       integer  NOT NULL,
    p25     integer,
    median  integer,
    p75     integer,
    PRIMARY KEY (day, grade, col),
    CONSTRAINT project_rate_snapshot_grade CHECK (grade IN ('초급','중급','고급','특급')),
    CONSTRAINT project_rate_snapshot_col   CHECK (col IN ('전체','SI','SM'))
);

COMMIT;
