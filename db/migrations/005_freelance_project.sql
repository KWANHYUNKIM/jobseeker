-- 005 — 외주·프리랜서 프로젝트
--
-- 무엇인가. SI/SM 상주, 외주 도급, 부업으로 할 만한 IT 프로젝트(원티드 긱스·프리모아·이랜서·
-- 잡코리아·사람인 프리랜서·아임잡·SISM). crawlers/crawl_freelance.py 가 모은다.
--
-- 왜 job 에 넣지 않나. 프로젝트의 핵심은 단가·기간·상주 여부이고 '회사'는 대개 중개
-- 에이전시다. job 에 섞으면 company 통계(에이전시가 상위를 차지한다)와 채용 기술 통계가
-- 흐려진다. 대신 tech 사전은 공유한다 — "이 기술을 쓰는 프리 자리의 월 단가"를 채용 쪽과
-- 같은 기술 이름으로 잇는 게 이 테이블의 쓸모 절반이다.
--
-- job 과 같은 원칙을 따른다.
--   · 정체성은 (site, pid) 와 url.
--   · 원문과 해석을 가른다 — duration_text/duration_days, budget 원문 대신 만원 단위 두 칸.
--   · 상태는 저장하지 않는다 — project_state 뷰가 오늘 날짜로 계산한다.
--   · 모집 상태의 변화는 덮어쓰지 않고 project_check 에 쌓는다.
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/005_freelance_project.sql
-- 두 번 돌려도 안전하다. schema.sql 의 "14. 외주·프리랜서 프로젝트" 와 글자 그대로 같다.

BEGIN;

DO $$ BEGIN
    CREATE TYPE project_site AS ENUM ('wanted_gigs','freemoa','elancer','jobkorea','saramin','imjob','sism');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    -- onsite = 고객사 상주(SI/SM 대부분), remote = 원격·도급, hybrid = 주 n일 상주
    CREATE TYPE project_mode AS ENUM ('onsite','remote','hybrid');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    -- monthly = 월 단가(상주), total = 총 계약금(도급). 서로 비교하지 않는다.
    CREATE TYPE budget_basis AS ENUM ('monthly','total');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    -- stale = 목록 앞쪽만 훑는 소스라 '안 보였다'를 마감으로 못 본다. 오래 안 보이면 따로 표시.
    CREATE TYPE project_status AS ENUM ('active','closed','stale');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS project (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site            project_site NOT NULL,
    pid             text         NOT NULL,
    url             text         NOT NULL,
    title           text         NOT NULL,

    category        text NOT NULL DEFAULT '',   -- 원본 분야 원문('개발,디자인,기획')
    work_mode       project_mode,
    location_text   text NOT NULL DEFAULT '',

    -- 단가. 원본은 전부 만원 단위로 준다. 한쪽만 알면 두 칸에 같은 값을 둔다.
    budget_basis    budget_basis,
    budget_min      integer,                    -- 만원
    budget_max      integer,                    -- 만원

    duration_text   text NOT NULL DEFAULT '',   -- '6개월' '52일' 원문
    duration_days   integer,                    -- 해석(개월 = 30일)
    start_text      text NOT NULL DEFAULT '',   -- '10월 4째주' '2026-10-05' 원문
    career_text     text NOT NULL DEFAULT '',
    summary         text NOT NULL DEFAULT '',   -- 연락처를 지운 본문 앞부분
    tags            text[] NOT NULL DEFAULT '{}',  -- 'SI' 'SM' '부업 가능'
    applicants      integer,

    deadline_on     date,
    posted_on       date,
    -- 마지막으로 본 목록이 '모집중'이라 했나. 판정의 한 재료일 뿐 status 가 아니다.
    source_open     boolean NOT NULL DEFAULT true,

    content_hash    text        NOT NULL,
    first_seen_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),

    search_tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(summary, '')), 'C')
    ) STORED,

    CONSTRAINT project_url_uniq       UNIQUE (url),
    CONSTRAINT project_site_pid_uniq  UNIQUE (site, pid),
    CONSTRAINT project_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT project_url_http       CHECK (url ~ '^https?://'),
    -- 단가 그물: 음수·뒤집힌 범위·자릿수 사고(원 단위를 만원 칸에 넣는 실수 — 월 60억)를 잡는다.
    CONSTRAINT project_budget_sane    CHECK (
        (budget_min IS NULL OR budget_min BETWEEN 1 AND 1000000) AND
        (budget_max IS NULL OR budget_max BETWEEN 1 AND 1000000) AND
        (budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max)
    ),
    CONSTRAINT project_duration_sane  CHECK (duration_days IS NULL OR duration_days BETWEEN 1 AND 3650),
    CONSTRAINT project_deadline_sane  CHECK (deadline_on IS NULL OR deadline_on BETWEEN DATE '2015-01-01' AND DATE '2100-01-01'),
    CONSTRAINT project_posted_sane    CHECK (posted_on IS NULL OR posted_on BETWEEN DATE '2015-01-01' AND DATE '2100-01-01'),
    CONSTRAINT project_seen_order     CHECK (last_seen_at >= first_seen_at)
);
COMMENT ON TABLE project IS '외주·프리 프로젝트 1건. job 과 따로 둔다(회사가 대개 에이전시라 통계를 흐린다)';
COMMENT ON COLUMN project.source_open IS '마지막 목록의 모집 표시. status 는 project_state 가 계산한다';

CREATE INDEX IF NOT EXISTS project_last_seen_idx ON project (last_seen_at DESC);
CREATE INDEX IF NOT EXISTS project_deadline_idx  ON project (deadline_on) WHERE deadline_on IS NOT NULL;
CREATE INDEX IF NOT EXISTS project_posted_idx    ON project (posted_on DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS project_search_idx    ON project USING gin (search_tsv);
CREATE INDEX IF NOT EXISTS project_title_trgm_idx ON project USING gin (title gin_trgm_ops);

-- 기술 — job 과 같은 tech 사전을 쓴다.
CREATE TABLE IF NOT EXISTS project_tech (
    project_id bigint NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    tech_id    bigint NOT NULL REFERENCES tech(id)    ON DELETE CASCADE,
    PRIMARY KEY (project_id, tech_id)
);
CREATE INDEX IF NOT EXISTS project_tech_tech_idx ON project_tech (tech_id);

-- 모집 상태 원장. 목록이 말한 상태가 **바뀔 때만** 한 행을 쌓는다(매 크롤마다 쌓으면
-- 하루 수백 행이 같은 말을 반복한다). "언제 닫혔나"와 "닫혔다 다시 열렸나"가 여기 남는다.
CREATE TABLE IF NOT EXISTS project_check (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id  bigint      NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    checked_at  timestamptz NOT NULL DEFAULT now(),
    closed      boolean     NOT NULL,
    deadline_on date,
    evidence    text,
    checker     text        NOT NULL DEFAULT 'crawl_freelance'
);
CREATE INDEX IF NOT EXISTS project_check_latest_idx ON project_check (project_id, checked_at DESC);

CREATE OR REPLACE VIEW project_check_latest AS
SELECT DISTINCT ON (project_id) project_id, checked_at, closed, deadline_on, evidence, checker
  FROM project_check
 ORDER BY project_id, checked_at DESC;

-- 상태는 계산한다(job_state 와 같은 이유 — 저장하면 낡는다).
--   원장이 마감 > 확정 마감일 경과 > 목록이 마감 표시 > 14일 넘게 안 보임(stale) > 모집중
-- 14일을 뷰에 굳힌 이유: 재확인 주기(job_recheck_queue 가 굳히지 않은 값)와 달리 이건
-- 화면의 뜻이다 — "2주째 안 보이는 자리는 내려갔을 공산이 크다". 화면(FreelanceView)도 같은 값.
CREATE OR REPLACE VIEW project_state AS
SELECT
    p.id AS project_id,
    CASE
        WHEN c.closed                                               THEN 'closed'::project_status
        WHEN COALESCE(c.deadline_on, p.deadline_on) < CURRENT_DATE  THEN 'closed'::project_status
        WHEN NOT p.source_open                                      THEN 'closed'::project_status
        WHEN p.last_seen_at < now() - interval '14 days'            THEN 'stale'::project_status
        ELSE 'active'::project_status
    END AS status,
    COALESCE(c.deadline_on, p.deadline_on) AS effective_deadline,
    (COALESCE(c.deadline_on, p.deadline_on) - CURRENT_DATE) AS dday,
    c.checked_at AS last_checked_at
FROM project p
LEFT JOIN project_check_latest c ON c.project_id = p.id;

-- 화면이 읽는 모양 — public/freelance.json 의 한 행과 같은 이름을 쓴다.
CREATE OR REPLACE VIEW v_project AS
SELECT p.id, p.site, p.pid, p.url, p.title, p.category, p.work_mode, p.location_text,
       p.budget_basis, p.budget_min, p.budget_max,
       p.duration_text, p.duration_days, p.start_text, p.career_text, p.summary, p.tags,
       p.applicants, p.posted_on,
       s.effective_deadline AS deadline_on, s.dday, s.status,
       COALESCE((SELECT array_agg(t.name ORDER BY t.name)
                   FROM project_tech pt JOIN tech t ON t.id = pt.tech_id
                  WHERE pt.project_id = p.id AND NOT t.is_noise), '{}') AS skills,
       p.first_seen_at, p.last_seen_at
  FROM project p
  JOIN project_state s ON s.project_id = p.id;

COMMIT;
