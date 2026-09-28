-- jobseeker 정본 스키마 (PostgreSQL 16+ / pgvector 0.7+)
--
-- 지금까지의 원본은 `jd-viewer/public/all_jobs_enriched.json` 한 덩어리였다.
-- 매 사이클 통째로 다시 쓰는 99MB 배열이라 키도 제약도 없었고, 그래서
--   (1) `(주)클로봇` 과 `클로봇` 이 다른 회사로 남고 (표기 변형 1,383 그룹)
--   (2) 같은 공고가 wanted 에선 모집중, saramin 에선 마감으로 동시에 존재하고 (1,150건)
--   (3) 회사명 없는 공고 492건이 중복 검사를 그냥 통과하고
--   (4) `status`·`dday` 가 계산 시점에 박제돼 파일이 하루만 묵어도 틀렸다.
--
-- 이 스키마의 목표는 그 넷을 "코드가 조심해서" 가 아니라 "DB 가 거부해서" 막는 것이다.
--   (1) → company.norm UNIQUE + company_alias 로 표기를 정체성에서 분리
--   (2) → job.url UNIQUE, job(site,pid) UNIQUE — 공고의 정체성은 URL 이다
--   (3) → NOT NULL + CHECK. 회사 없는 공고는 애초에 들어오지 못한다
--   (4) → status 를 컬럼이 아니라 뷰로 만든다. 저장하지 않으면 낡을 수 없다
--
-- 그리고 지금 따로 도는 semantic.db(SQLite + sqlite-vec)를 이 DB 안으로 들인다.
-- 임베딩이 공고와 같은 트랜잭션 안에 있으면 "마감 공고를 검색에서 뺀다" 가
-- meta JSON 을 베끼는 일이 아니라 조인 한 줄이 된다.
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/schema.sql

BEGIN;

CREATE EXTENSION IF NOT EXISTS citext;    -- 대소문자 무시 비교 (기술명 별칭)
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- 한글 부분일치 / 유사 회사명 탐색
CREATE EXTENSION IF NOT EXISTS vector;    -- pgvector — sqlite-vec 를 대체한다

-- "오늘" 은 한국 날짜다. job_state 의 CURRENT_DATE 가 UTC 면 한국 시각 00~09시에
-- 어제 마감된 공고가 모집중으로 남는다(db/migrations/002).
DO $$ BEGIN
    EXECUTE format('ALTER DATABASE %I SET "TimeZone" TO %L', current_database(), 'Asia/Seoul');
END $$;

-- ════════════════════════════════════════════════════════════════════
-- 0. 도메인 타입
-- ════════════════════════════════════════════════════════════════════
-- ENUM 으로 두면 오타난 site 값이 INSERT 단계에서 죽는다. 새 소스를 붙일 때는
-- ALTER TYPE ... ADD VALUE 한 줄이면 되고, 그 강제성이 오탈자보다 싸다.
CREATE TYPE job_site        AS ENUM ('wanted','jumpit','jobkorea','saramin','dev','remote','ats');
CREATE TYPE job_status      AS ENUM ('active','closed');
CREATE TYPE status_source   AS ENUM ('override','ledger','deadline','always_open','unknown');
CREATE TYPE company_size    AS ENUM ('대기업','중견기업','중소기업','스타트업','공공','외국계','미분류');
CREATE TYPE employment_type AS ENUM ('정규직','계약직','인턴','프리랜서','파견','기타');
CREATE TYPE job_event_kind  AS ENUM ('appeared','updated','closed','reopened','disappeared','merged');
CREATE TYPE tech_kind       AS ENUM ('language','framework','library','database','infra','tool','platform','concept','role','noise');

-- ════════════════════════════════════════════════════════════════════
-- 1. 회사 — 표기(alias)와 정체성(norm)을 분리한다
-- ════════════════════════════════════════════════════════════════════
-- 측정치: 원본 회사명 표기 8,438개 중 1,383 그룹이 같은 회사의 다른 표기였다
-- (`메가존클라우드(주)` / `메가존클라우드㈜` / `메가존클라우드주식회사`).
-- 표기를 키로 쓰는 한 이 문제는 코드로 못 막는다. 표기는 alias 로 내리고,
-- 정규화 결과 norm 하나만 회사의 정체성으로 삼는다.
CREATE TABLE company (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- classifier._norm_company() 결과. NFKC + 법인격((주)/㈜/주식회사/Inc/Ltd) 제거
    -- + 공백·괄호 제거 + 소문자. 이 값이 곧 회사다.
    norm          text        NOT NULL UNIQUE,

    -- 주소에 나가는 ASCII 슬러그. companySlug.js 가 만들고, 한 번 정하면 안 바뀐다
    -- (바뀌면 /companies/<slug> 로 색인된 페이지가 통째로 404 가 된다).
    slug          text        NOT NULL UNIQUE,

    -- 화면에 쓰는 대표 표기. 보통 alias 중 가장 자주 온 것을 고르되 사람이 덮어쓸 수 있다.
    display_name  text        NOT NULL,
    name_locked   boolean     NOT NULL DEFAULT false,  -- true 면 자동 재선정이 건드리지 않는다

    size          company_size NOT NULL DEFAULT '미분류',
    homepage      text,
    description   text,
    domains       text[]      NOT NULL DEFAULT '{}',   -- 사업 도메인 태그(핀테크, 물류…)
    -- 홈페이지에서 긁힌 기술 흔적. crawl_company 가 채운다(company_profiles.json 대체).
    homepage_tech text[]      NOT NULL DEFAULT '{}',

    -- 나중에 같은 회사로 판명났을 때. 행을 지우면 job.company_id 가 끊기므로
    -- 지우는 대신 여기로 넘긴다 — 옛 슬러그 주소도 리다이렉트로 살릴 수 있다.
    merged_into   bigint      REFERENCES company(id) ON DELETE SET NULL,

    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT company_norm_not_blank    CHECK (btrim(norm) <> ''),
    CONSTRAINT company_slug_ascii        CHECK (slug ~ '^[a-z0-9][a-z0-9-]*$'),
    CONSTRAINT company_display_not_blank CHECK (btrim(display_name) <> ''),
    CONSTRAINT company_no_self_merge     CHECK (merged_into IS DISTINCT FROM id)
);

COMMENT ON COLUMN company.norm IS '회사의 정체성. classifier._norm_company() 와 반드시 같은 규칙이어야 한다';
COMMENT ON COLUMN company.merged_into IS '중복 회사를 통합할 때 살아남는 쪽의 id. NULL 이면 자기 자신이 정본';

-- 크롤이 실제로 들고 온 표기. 정규화가 놓친 변형을 사람이 수동으로 이어붙이는 자리이기도 하다.
CREATE TABLE company_alias (
    raw           text        PRIMARY KEY,   -- '메가존클라우드㈜' 원문 그대로
    company_id    bigint      NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    n_seen        integer     NOT NULL DEFAULT 1,
    manual        boolean     NOT NULL DEFAULT false,  -- 정규화가 아니라 사람이 이어붙인 것
    first_seen_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT company_alias_raw_not_blank CHECK (btrim(raw) <> '')
);
CREATE INDEX company_alias_company_idx ON company_alias (company_id);
-- 새 표기가 들어왔을 때 "비슷한 이름이 이미 있나"를 묻기 위한 인덱스.
-- 정규화가 못 잡는 변형(오타·띄어쓰기 조합)을 사람이 찾아 붙이는 데 쓴다.
CREATE INDEX company_alias_trgm_idx ON company_alias USING gin (raw gin_trgm_ops);

-- ════════════════════════════════════════════════════════════════════
-- 2. 기술 용어 — tech_stack 배열을 정규화한다
-- ════════════════════════════════════════════════════════════════════
-- 지금은 공고마다 문자열 배열이라 "React 수요 추이"를 뽑으려면 17,584건을 전부
-- 훑어야 하고, 'react'/'React'/'React.js' 가 서로 다른 기술로 세어진다.
-- 측정치: 서로 다른 토큰 850개인데 그중 'dev','mobile' 처럼 기술이 아닌 것도 섞여 있다.
CREATE TABLE tech (
    id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug     text        NOT NULL UNIQUE,   -- 'react-native' — /wiki/<slug> 와 같은 값
    name     text        NOT NULL,          -- 'React Native' 표시용
    kind     tech_kind   NOT NULL DEFAULT 'tool',
    -- 'dev','mobile' 처럼 스택으로 세면 안 되는 토큰. 지우지 않고 표시만 한다 —
    -- 지우면 다음 크롤이 또 만들어낸다.
    is_noise boolean     NOT NULL DEFAULT false,

    CONSTRAINT tech_slug_ascii CHECK (slug ~ '^[a-z0-9][a-z0-9.+#-]*$')
);

CREATE TABLE tech_alias (
    alias   citext PRIMARY KEY,             -- citext 라 'React' 와 'react' 가 한 행이다
    tech_id bigint NOT NULL REFERENCES tech(id) ON DELETE CASCADE
);
CREATE INDEX tech_alias_tech_idx ON tech_alias (tech_id);

-- ════════════════════════════════════════════════════════════════════
-- 3. 공고 — 정체성은 URL 이다
-- ════════════════════════════════════════════════════════════════════
-- 지금 파이프라인의 중복 키는 (회사명, 제목) 문자열 쌍이다(aggregate.py:126).
-- 그래서 같은 회사가 같은 제목으로 낸 다른 팀 공고가 뭉개지고, 반대로 표기가
-- 갈리면 같은 공고가 1,150건 살아남았다. 공고를 특정하는 건 URL 이지 제목이 아니다.
CREATE TABLE job (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    site            job_site NOT NULL,
    pid             text     NOT NULL,      -- 사이트 안의 공고 번호
    url             text     NOT NULL,
    company_id      bigint   NOT NULL REFERENCES company(id) ON DELETE RESTRICT,
    title           text     NOT NULL,

    -- ── 조건 ────────────────────────────────────────────────────────
    career_text     text     NOT NULL DEFAULT '',  -- '경력3년↑' 원문
    career_min      smallint,                      -- 파싱된 최소 연차. 신입이면 0, 모르면 NULL
    accepts_entry   boolean,                       -- 신입 지원 가능 여부. 모르면 NULL
    location_text   text     NOT NULL DEFAULT '',  -- '서울 강남구' 원문
    sido            text,                          -- 정규화된 시·도
    sigungu         text,                          -- 정규화된 시·군·구
    region          text,                          -- 'kr' | 'global'
    overseas        boolean  NOT NULL DEFAULT false,
    employment      employment_type,
    education       text,
    source_board    text,                          -- remote/ats 의 원 보드명

    -- ── 본문 ────────────────────────────────────────────────────────
    main_tasks      text NOT NULL DEFAULT '',
    qualifications  text NOT NULL DEFAULT '',
    preferences     text NOT NULL DEFAULT '',
    benefits        text NOT NULL DEFAULT '',
    full_jd         text NOT NULL DEFAULT '',

    -- ── 마감 ────────────────────────────────────────────────────────
    -- 원문과 해석을 갈라 둔다. deadline_text 는 사이트가 말한 그대로 보존하고
    -- (파서를 고쳤을 때 다시 돌릴 재료가 된다), deadline_on 은 해석 결과다.
    deadline_text   text     NOT NULL DEFAULT '',
    deadline_on     date,
    always_open     boolean  NOT NULL DEFAULT false,   -- 상시/수시 채용

    -- ── 등록일 ──────────────────────────────────────────────────────
    -- 공고가 **언제 올라왔는지**. 어느 크롤러도 수집하지 않던 값이라 목록을
    -- 최신순으로 줄 세울 수도, "올라온 지 3일" 을 보여줄 수도 없었다.
    -- `pipeline.close_check` 가 마감을 재확인하면서 같이 받아 온다(JSON-LD
    -- datePosted / jumpit publishedAt). 크롤 경로는 이 칸을 건드리지 않는다 —
    -- 매 사이클 NULL 로 덮이면 애써 알아낸 값이 지워진다.
    --
    -- saramin 은 원본에 등록일 표기가 없어 영영 NULL 이다. 그 자리는
    -- first_seen_at(우리가 처음 본 날)이 대신하고, 화면이 추정값으로 표시한다.
    posted_on       date,

    -- dday 는 저장하지 않는다. 지금까지 'D-4' 문자열을 크롤 시점 그대로 실어
    -- 보냈기 때문에 마감일 2026-08-23 인 공고가 며칠 뒤에도 D-4 로 보였다.
    -- 남은 일수는 v_job 이 CURRENT_DATE 로 계산한다.
    dday_text_raw   text     NOT NULL DEFAULT '',      -- 파서 디버깅용 원문 보존

    -- ── 수명 ────────────────────────────────────────────────────────
    -- content_hash 는 임베딩 입력(제목+회사+스택+자격요건…)의 해시다.
    -- job_embedding.content_hash 와 다르면 그 공고는 재임베딩 대상이다.
    content_hash    text        NOT NULL,
    first_seen_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),  -- 목록에서 마지막으로 본 시각
    last_crawled_at timestamptz NOT NULL DEFAULT now(),  -- 본문을 마지막으로 받아온 시각
    gone_at         timestamptz,                         -- 목록에서 사라진 시각

    -- ── 검색(FTS) ───────────────────────────────────────────────────
    -- 생성 컬럼이라 본문이 바뀌면 자동으로 따라 바뀐다. 한국어는 기본 파서가
    -- 형태소를 모르므로 'simple' 로 토큰만 쪼개고(기술명·회사명 같은 고유명사가
    -- 목적이다), 한글 부분일치는 아래 trgm 인덱스가 맡는다.
    search_tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(qualifications, '') || ' ' || coalesce(preferences, '')), 'B') ||
        setweight(to_tsvector('simple', coalesce(main_tasks, '') || ' ' || coalesce(full_jd, '')), 'C')
    ) STORED,

    -- 정체성 제약 — 이 두 줄이 (site,pid) 중복 7건과 URL 중복을 원천 차단한다
    CONSTRAINT job_url_uniq      UNIQUE (url),
    CONSTRAINT job_site_pid_uniq UNIQUE (site, pid),

    -- 결측 차단 — 회사명 없는 jobkorea 공고 492건, 제목 없는 25건이 여기서 걸린다
    CONSTRAINT job_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT job_pid_not_blank   CHECK (btrim(pid) <> ''),
    CONSTRAINT job_url_http        CHECK (url ~ '^https?://'),
    -- 상한을 고정값으로 둔다. CHECK 에는 CURRENT_DATE 같은 비-immutable 함수를 못 쓴다.
    -- "몇 년 뒤 마감" 같은 파싱 사고(연도 없는 06/07 을 내년으로 읽던 옛 버그)를 잡는 그물이다.
    CONSTRAINT job_deadline_sane   CHECK (deadline_on IS NULL OR deadline_on BETWEEN DATE '2015-01-01' AND DATE '2100-01-01'),
    -- 등록일도 같은 그물에 건다. 미래의 등록일은 파싱 사고다.
    CONSTRAINT job_posted_sane     CHECK (posted_on IS NULL OR posted_on BETWEEN DATE '2015-01-01' AND DATE '2100-01-01'),
    CONSTRAINT job_region_known    CHECK (region IS NULL OR region IN ('kr','global')),
    CONSTRAINT job_seen_order      CHECK (last_seen_at >= first_seen_at)
);

COMMENT ON TABLE  job IS '공고 1건. 정체성은 url — (회사명,제목) 이 아니다';
COMMENT ON COLUMN job.gone_at IS '목록에서 사라진 시각. 사라짐≠마감이라 status 를 직접 바꾸지 않고 close_check 의 입력이 된다';
COMMENT ON COLUMN job.dday_text_raw IS '표시에 쓰지 말 것. 크롤 시점 문자열이라 하루만 지나도 틀린다';
COMMENT ON COLUMN job.posted_on IS '원본이 말한 등록일. close_check 만 쓴다(COALESCE 로 덮어쓰지 않는다). saramin 은 NULL';

CREATE INDEX job_company_idx    ON job (company_id);
CREATE INDEX job_site_idx       ON job (site);
CREATE INDEX job_deadline_idx   ON job (deadline_on) WHERE deadline_on IS NOT NULL;
CREATE INDEX job_last_seen_idx  ON job (last_seen_at DESC);
-- 목록 "최신순" — 등록일이 없는 공고는 뒤로 민다
CREATE INDEX job_posted_idx     ON job (posted_on DESC NULLS LAST);
CREATE INDEX job_search_idx     ON job USING gin (search_tsv);
-- 한글 부분일치("백엔드", "재택"). FTS 가 형태소를 모르는 자리를 메운다.
CREATE INDEX job_title_trgm_idx ON job USING gin (title gin_trgm_ops);

-- 공고 ↔ 기술 (N:M)
CREATE TABLE job_tech (
    job_id  bigint NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    tech_id bigint NOT NULL REFERENCES tech(id) ON DELETE CASCADE,
    -- 어디서 뽑았나. 'crawl'(사이트가 준 태그) / 'jd_parse'(본문에서 추출) / 'manual'
    source  text   NOT NULL DEFAULT 'crawl',
    PRIMARY KEY (job_id, tech_id)
);
CREATE INDEX job_tech_tech_idx ON job_tech (tech_id);

-- ════════════════════════════════════════════════════════════════════
-- 4. 마감 재확인 원장 — 덮어쓰지 않고 쌓는다
-- ════════════════════════════════════════════════════════════════════
-- 지금은 job_closures.json 이 site:pid → 최신 결과 하나만 담는 맵이고,
-- git 추적도 안 돼서 운영 맥에 사본이 하나뿐이다. 그 파일이 날아가면 재확인
-- 이력이 통째로 사라진다. 여기서는 확인할 때마다 한 행을 남긴다 —
-- "언제 물어봤더니 뭐라 답했나"가 남아야 파서를 고친 뒤 재해석이 가능하다.
CREATE TABLE job_closure_check (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id      bigint      NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    checked_at  timestamptz NOT NULL DEFAULT now(),
    closed      boolean     NOT NULL,       -- 사이트가 마감이라고 답했나
    deadline_on date,                       -- 연도까지 확정된 마감일(알아냈다면)
    posted_on   date,                       -- 원본이 말한 등록일(알아냈다면)
    http_status smallint,
    evidence    text,                       -- 판단 근거가 된 페이지 문구
    checker     text        NOT NULL DEFAULT 'close_check'
);
CREATE INDEX job_closure_latest_idx ON job_closure_check (job_id, checked_at DESC);

-- 공고별 최신 재확인 1건.
-- posted_on 이 컬럼 순서상 어색한 끝자리에 있는 이유: 이 뷰에는 job_state 와
-- job_recheck_queue 가 매달려 있어 DROP 할 수 없고, CREATE OR REPLACE VIEW 는
-- 기존 컬럼 이름을 밀어낼 수 없다(중간에 끼우면 "cannot change name of view
-- column" 으로 거부한다). 그래서 새 컬럼은 늘 맨 끝에 붙인다 —
-- db/migrations/ 가 만드는 모양과 여기가 글자 그대로 같아야 하기 때문이다.
CREATE VIEW job_closure_latest AS
SELECT DISTINCT ON (job_id) job_id, checked_at, closed, deadline_on, evidence, checker, posted_on
  FROM job_closure_check
 ORDER BY job_id, checked_at DESC;

-- 재확인 대기열: 원장이 아예 없거나 오래된 순. close_check 가 매 사이클 400건씩 가져간다.
-- ════════════════════════════════════════════════════════════════════
-- 5. 수동 보정 — overrides.json 의 자리
-- ════════════════════════════════════════════════════════════════════
-- 사람이 고친 값은 크롤을 반복해도 살아남아야 한다. 필드 단위로 두면
-- "제목만 고치고 본문은 자동" 같은 부분 보정이 가능하다.
CREATE TABLE job_override (
    job_id     bigint      NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    field      text        NOT NULL,
    value      jsonb       NOT NULL,
    reason     text,
    author     text        NOT NULL DEFAULT 'manual',
    created_at timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (job_id, field),
    CONSTRAINT job_override_field_known CHECK (field IN (
        'title','main_tasks','qualifications','preferences','benefits',
        'tech_stack','deadline_on','always_open','status','company_id'
    )),
    -- status 보정은 두 값만 허용한다. 오타가 들어가면 뷰가 조용히 틀린다.
    CONSTRAINT job_override_status_valid CHECK (
        field <> 'status' OR value #>> '{}' IN ('active','closed')
    )
);

-- ════════════════════════════════════════════════════════════════════
-- 6. 상태는 저장하지 않고 계산한다  ★ 핵심
-- ════════════════════════════════════════════════════════════════════
-- 지금까지 status 는 aggregate/enrich 가 계산해 파일에 굽는 값이었다. 그래서
-- 파일이 17일 묵은 시점에 'active' 9,458건 중 2,373건은 마감일이 이미 과거였다.
-- 저장하지 않으면 낡을 수 없다. 우선순위는 job_status.py 의 규칙 그대로:
--   사람이 정한 값 > 사이트에 물어본 원장 > 상시채용 > 마감일 > 모름(모집중 유지)
CREATE VIEW job_state AS
SELECT
    j.id AS job_id,
    CASE
        WHEN o.value IS NOT NULL                       THEN (o.value #>> '{}')::job_status
        WHEN c.closed                                  THEN 'closed'::job_status
        WHEN c.deadline_on IS NOT NULL
             AND c.deadline_on < CURRENT_DATE          THEN 'closed'::job_status
        WHEN j.always_open                             THEN 'active'::job_status
        WHEN j.deadline_on IS NOT NULL
             AND j.deadline_on < CURRENT_DATE          THEN 'closed'::job_status
        ELSE 'active'::job_status
    END AS status,

    -- 이 판정을 무엇이 근거로 했는지. 'unknown' 은 "모집중"이 아니라
    -- "마감을 알 방법이 없어 열어둔 것"이다 — active 9,458건 중 5,615건(59%)이 여기였다.
    -- 화면에서 '모집중(확인됨)' 과 '모집중(미확인)' 을 갈라 보여줄 근거가 된다.
    CASE
        WHEN o.value IS NOT NULL        THEN 'override'::status_source
        WHEN c.job_id IS NOT NULL       THEN 'ledger'::status_source
        WHEN j.always_open              THEN 'always_open'::status_source
        WHEN j.deadline_on IS NOT NULL  THEN 'deadline'::status_source
        ELSE 'unknown'::status_source
    END AS status_source,

    COALESCE(c.deadline_on, j.deadline_on) AS effective_deadline,
    -- D-day 도 지금 계산한다. 음수면 이미 지난 것이고, NULL 이면 마감일을 모른다.
    (COALESCE(c.deadline_on, j.deadline_on) - CURRENT_DATE) AS dday,
    c.checked_at AS last_verified_at
FROM job j
LEFT JOIN job_closure_latest c ON c.job_id = j.id
LEFT JOIN job_override o ON o.job_id = j.id AND o.field = 'status';

-- 마감 재확인 대상. `pipeline.close_check` 가 이걸 읽는다.
--
-- 임계값(며칠 지나면 다시 볼 것인가)을 뷰에 굳히지 않는다 — close_check 의
-- --recheck-days 가 그 값이고, 여기에 interval '7 days' 를 박아 두면 그 옵션이
-- 거짓말이 된다. 뷰는 "무엇을 언제 마지막으로 봤나"까지만 답하고 자르는 것은
-- 부르는 쪽이 한다.
--
-- 확인하려면 site·pid·url·회사·제목이 다 필요하다(사이트별 판정기가 쓴다).
-- 지금까지 close_check 는 이걸 크롤 스냅샷 JSON 에서 읽었고, 그래서 **다른
-- 머신이 모아 온 공고는 재확인 대상에 아예 들어오지 못했다.**
--
-- 목록에서 사라진 공고(gone_at)도 넣는다 — 사라졌다는 게 마감의 가장 강한 신호라
-- close_check 가 그것부터 묻는다. 닫는 건 여전히 원본의 답이다(db/migrations/003).
CREATE VIEW job_recheck_queue AS
SELECT j.id, j.site, j.pid, j.url, co.display_name AS company, j.title,
       s.status, c.checked_at, COALESCE(c.closed, false) AS ledger_closed,
       j.gone_at, c.deadline_on AS ledger_deadline
  FROM job j
  LEFT JOIN company co ON co.id = j.company_id
  LEFT JOIN job_state s ON s.job_id = j.id
  LEFT JOIN job_closure_latest c ON c.job_id = j.id
 ORDER BY c.checked_at NULLS FIRST, j.last_seen_at DESC;

-- ════════════════════════════════════════════════════════════════════
-- 7. 화면이 읽는 뷰 — all_jobs_enriched.json 을 대체한다
-- ════════════════════════════════════════════════════════════════════
CREATE VIEW v_job AS
SELECT
    j.id,
    j.site,
    j.pid,
    j.site || '-' || j.pid AS job_key,     -- /jobs/<site>-<pid> 주소 그대로
    j.url,
    co.slug         AS company_slug,        -- /companies/<slug>
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
    -- 새 컬럼은 **맨 끝에** 붙인다. CREATE OR REPLACE VIEW 는 기존 컬럼의
    -- 순서·타입을 바꾸지 못하므로, 중간에 끼우면 운영 DB 에서 마이그레이션이
    -- 뷰를 통째로 DROP 해야 한다(그 뷰에 매달린 것들까지 같이).
    j.posted_on
FROM job j
JOIN company co ON co.id = j.company_id
JOIN job_state s ON s.job_id = j.id
LEFT JOIN LATERAL (
    SELECT array_agg(te.name ORDER BY te.name) AS techs
      FROM job_tech jt JOIN tech te ON te.id = jt.tech_id
     WHERE jt.job_id = j.id AND NOT te.is_noise
) t ON true;

COMMENT ON VIEW v_job IS '뷰어/검색 API 가 읽는 정본. all_jobs_enriched.json 은 이 뷰의 덤프로 강등된다';

-- 사이트 간 중복 → 대표 공고. 지우지 않고 가리키기만 한다 — 사이트마다 마감 판정이
-- 따로 오기 때문이다. store.export 가 사본을 걸러 뷰어·빌더에 한 건만 보낸다.
-- 대표: 모집중 → aggregate 의 사이트 순서 → 먼저 본 것. 근거는 migrations/004.
CREATE VIEW job_dup AS
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

-- ════════════════════════════════════════════════════════════════════
-- 8. 운영 이력 — health/history.jsonl, reposts.json 의 자리
-- ════════════════════════════════════════════════════════════════════
CREATE TABLE crawl_run (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label      text        NOT NULL,
    keywords   text[]      NOT NULL DEFAULT '{}',
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at   timestamptz,
    ok         boolean,
    n_raw      integer,
    n_upserted integer,
    n_new      integer,
    n_closed   integer,
    detail     jsonb       NOT NULL DEFAULT '{}'
);

CREATE TABLE crawl_run_site (
    crawl_run_id bigint   NOT NULL REFERENCES crawl_run(id) ON DELETE CASCADE,
    site         job_site NOT NULL,
    n_raw        integer  NOT NULL DEFAULT 0,
    n_new        integer  NOT NULL DEFAULT 0,
    ok           boolean  NOT NULL DEFAULT true,
    note         text,
    PRIMARY KEY (crawl_run_id, site)
);

-- 공고에 일어난 일. 재공고 탐지(reposts)와 "언제 마감됐나"가 여기서 나온다.
-- 매 사이클 전량 스냅샷을 남기지 않고 변화만 기록한다 — 17,584건 × 사이클은 감당이 안 된다.
CREATE TABLE job_event (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id       bigint         NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    kind         job_event_kind NOT NULL,
    at           timestamptz    NOT NULL DEFAULT now(),
    crawl_run_id bigint         REFERENCES crawl_run(id) ON DELETE SET NULL,
    detail       jsonb          NOT NULL DEFAULT '{}'
);
CREATE INDEX job_event_job_idx  ON job_event (job_id, at DESC);
CREATE INDEX job_event_kind_idx ON job_event (kind, at DESC);

-- ════════════════════════════════════════════════════════════════════
-- 9. 벡터 — semantic.db(SQLite + sqlite-vec)를 pgvector 로 들인다
-- ════════════════════════════════════════════════════════════════════
-- 지금 구조: 별도 SQLite 파일에 documents(kind='job'|'post') 한 테이블 +
-- vec_documents(sqlite-vec) + fts_documents(FTS5). 공고와 다른 파일에 있으니
-- 색인이 마감 여부를 알 수 없어서 meta JSON 에 status 를 베껴 담고 있었고,
-- 그 사본은 공고가 마감돼도 다음 ingest 전까지 낡은 채로 남는다.
--
-- 여기서는 임베딩이 job 의 자식이다. "마감 공고는 색인에 남기되 검색에서 뺀다"가
-- meta 를 베끼는 일이 아니라 `JOIN job_state s ... WHERE s.status='active'` 한 줄이 된다.
-- 증분 임베딩 규칙은 그대로다 — job.content_hash 와 job_embedding.content_hash 가
-- 어긋나면 재임베딩 대상.

-- 기술블로그 글. semantic 의 kind='post' 에 해당한다.
CREATE TABLE post (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url           text        NOT NULL UNIQUE,
    content_id    text        UNIQUE,        -- blogKey() 가 쓰는 값. 없으면 URL 해시로 대체
    company_id    bigint      REFERENCES company(id) ON DELETE SET NULL,
    blog_name     text        NOT NULL DEFAULT '',
    title         text        NOT NULL,
    body          text        NOT NULL DEFAULT '',
    published_on  date,
    content_hash  text        NOT NULL,

    -- 분류 축. `tech_blogs.json` 이 들고 있던 것을 그대로 옮긴다 — 이게 없으면
    -- build_company_stacks 의 블로그 추천(어떤 기술·주제의 글인가)이 성립하지
    -- 않아서, 그 빌더가 DB 를 두고 파일을 다시 읽어야 했다.
    country       text        NOT NULL DEFAULT '',   -- 'KR' / 'US' / 'JP' …
    lang          text        NOT NULL DEFAULT '',
    summary       text        NOT NULL DEFAULT '',
    tags          text[]      NOT NULL DEFAULT '{}',
    tech_stack    text[]      NOT NULL DEFAULT '{}',
    categories    text[]      NOT NULL DEFAULT '{}',  -- 한국어 주제 분류('보안' 등)

    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now(),

    search_tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(body, '')), 'C')
    ) STORED,

    CONSTRAINT post_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT post_url_http        CHECK (url ~ '^https?://')
);
CREATE INDEX post_search_idx  ON post USING gin (search_tsv);
CREATE INDEX post_company_idx ON post (company_id);

-- 임베딩. bge-m3 = 1024차원. 차원이 다른 모델로 갈아탈 때는 새 테이블을 만들어
-- 양쪽을 동시에 채운 뒤 스위치한다 — vector(n) 은 차원이 타입의 일부다.
CREATE TABLE job_embedding (
    job_id       bigint       PRIMARY KEY REFERENCES job(id) ON DELETE CASCADE,
    model        text         NOT NULL,          -- 'bge-m3'
    content_hash text         NOT NULL,          -- 임베딩한 시점의 job.content_hash
    embedding    vector(1024) NOT NULL,
    embedded_at  timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE post_embedding (
    post_id      bigint       PRIMARY KEY REFERENCES post(id) ON DELETE CASCADE,
    model        text         NOT NULL,
    content_hash text         NOT NULL,
    embedding    vector(1024) NOT NULL,
    embedded_at  timestamptz  NOT NULL DEFAULT now()
);

-- HNSW. 17,584건 × 1024차원 float4 ≈ 72MB — 8GB M1 에서도 인덱스가 메모리에 든다.
-- 코사인 거리(`<=>`)를 쓴다. 임베딩을 L2 정규화해 넣으면 내적과 순서가 같아진다.
-- m/ef_construction 은 기본값. 빌드 중 메모리가 빠듯하면 maintenance_work_mem 을
-- 올리는 대신 ef_construction 을 낮춘다.
CREATE INDEX job_embedding_hnsw_idx  ON job_embedding  USING hnsw (embedding vector_cosine_ops);
CREATE INDEX post_embedding_hnsw_idx ON post_embedding USING hnsw (embedding vector_cosine_ops);

-- 재임베딩 대기열. embed 배치가 이 뷰만 읽으면 된다.
-- (Ollama 가 꺼져 있으면 이 뷰가 계속 차오르므로 그대로 모니터링 지표가 된다.)
CREATE VIEW job_embed_pending AS
SELECT j.id, j.content_hash
  FROM job j LEFT JOIN job_embedding e ON e.job_id = j.id
 WHERE e.job_id IS NULL OR e.content_hash <> j.content_hash;

CREATE VIEW post_embed_pending AS
SELECT p.id, p.content_hash
  FROM post p LEFT JOIN post_embedding e ON e.post_id = p.id
 WHERE e.post_id IS NULL OR e.content_hash <> p.content_hash;

-- 유사 공고 top-K. similar_jobs.json(4MB)이 하던 것을 테이블로 굳힌다.
-- 사이클 끝에 semantic.similar 이 계산해 넣는다 — 매 요청마다 HNSW 를 도는 대신
-- 미리 굳혀 두는 지금 방식을 그대로 옮긴 것이다(뷰어가 정적으로 소비하므로).
CREATE TABLE job_similar (
    job_id      bigint   NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    similar_id  bigint   NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    rank        smallint NOT NULL,
    score       real     NOT NULL,
    computed_at timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (job_id, similar_id),
    CONSTRAINT job_similar_not_self  CHECK (job_id <> similar_id),
    -- 코사인 유사도의 정의역만 강제한다. 실제 컷(config.py 의 MIN_SCORE 0.55,
    -- DUP_SCORE 0.985, MAX_PER_COMPANY 2)은 튜닝 대상이라 쓰는 쪽이 적용한다 —
    -- 환경변수로 조정하는 값을 CHECK 에 박으면 튜닝할 때마다 INSERT 가 깨진다.
    CONSTRAINT job_similar_score_range CHECK (score > 0 AND score <= 1)
);
CREATE INDEX job_similar_rank_idx ON job_similar (job_id, rank);

CREATE TABLE post_similar (
    post_id     bigint   NOT NULL REFERENCES post(id) ON DELETE CASCADE,
    similar_id  bigint   NOT NULL REFERENCES post(id) ON DELETE CASCADE,
    rank        smallint NOT NULL,
    score       real     NOT NULL,
    computed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (post_id, similar_id),
    CONSTRAINT post_similar_not_self CHECK (post_id <> similar_id)
);

-- ════════════════════════════════════════════════════════════════════
-- 10. 하이브리드 검색 — FTS5+sqlite-vec RRF 를 SQL 하나로
-- ════════════════════════════════════════════════════════════════════
-- search.py 가 지금 파이썬에서 두 결과를 합치는 RRF 를 DB 안에서 한다.
-- 마감 제외가 조인 조건이라 meta 사본이 필요 없다(`--include-closed` 는 인자 하나).
--   SELECT * FROM search_jobs('재택 되는 백엔드', <query embedding>, 20, false);
CREATE FUNCTION search_jobs(
    q             text,
    q_embedding   vector(1024),
    n             integer DEFAULT 20,
    include_closed boolean DEFAULT false,
    k             integer DEFAULT 60     -- RRF 상수
) RETURNS TABLE (job_id bigint, rrf real, fts_rank integer, vec_rank integer)
LANGUAGE sql STABLE AS $$
    WITH pool AS (
        SELECT j.id, j.search_tsv
          FROM job j JOIN job_state s ON s.job_id = j.id
         WHERE include_closed OR s.status = 'active'
    ),
    fts AS (
        SELECT p.id,
               row_number() OVER (ORDER BY ts_rank_cd(p.search_tsv, websearch_to_tsquery('simple', q)) DESC) AS r
          FROM pool p
         WHERE p.search_tsv @@ websearch_to_tsquery('simple', q)
         LIMIT 200
    ),
    vec AS (
        SELECT e.job_id AS id,
               row_number() OVER (ORDER BY e.embedding <=> q_embedding) AS r
          FROM job_embedding e JOIN pool p ON p.id = e.job_id
         ORDER BY e.embedding <=> q_embedding
         LIMIT 200
    )
    SELECT COALESCE(f.id, v.id)                                   AS job_id,
           (COALESCE(1.0 / (k + f.r), 0) + COALESCE(1.0 / (k + v.r), 0))::real AS rrf,
           f.r::integer, v.r::integer
      FROM fts f FULL OUTER JOIN vec v ON v.id = f.id
     ORDER BY 2 DESC
     LIMIT n;
$$;

COMMENT ON FUNCTION search_jobs IS 'FTS + 벡터 RRF 하이브리드. q_embedding 은 호출부가 Ollama 로 만들어 넘긴다';

-- ════════════════════════════════════════════════════════════════════
-- 11. 손으로 쓴 산출물 색인 — engine / guide-engine / study-engine
-- ════════════════════════════════════════════════════════════════════
-- 본문은 git 에 있는 JSON 그대로 둔다(사람이 쓴 글이고 리뷰 대상이다).
-- DB 에는 "무엇이 무엇에 붙어 있나"만 넣어 `validate.py --gaps` 를 SQL 로 만든다.
CREATE TABLE company_guide (
    company_id bigint      PRIMARY KEY REFERENCES company(id) ON DELETE CASCADE,
    slug       text        NOT NULL UNIQUE,   -- guide/companies/<slug>.json
    updated_at timestamptz NOT NULL DEFAULT now(),
    n_postings integer     NOT NULL DEFAULT 0,
    n_items    integer     NOT NULL DEFAULT 0
);

CREATE TABLE reveng_doc (
    company_id bigint      PRIMARY KEY REFERENCES company(id) ON DELETE CASCADE,
    slug       text        NOT NULL UNIQUE,   -- reveng/companies/<slug>.json
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- 기술 백과사전(study-engine)은 여기에 색인을 두지 않는다. 문서가 전부 파일에
-- 있고(jd-viewer/public/study/), 대기열은 tech_relations.json 과 끊긴 related
-- 링크에서 나온다 — study-engine/validate.py --gaps 가 파일만 읽고 답한다.
-- DB 사본은 아무도 안 읽으면서 갱신만 필요했으므로 없앴다.

-- 모집중 공고는 많은데 브리핑이 없는 회사 = guide-engine 대기열
CREATE VIEW guide_gap AS
SELECT co.id, co.slug, co.display_name, count(*) AS n_active
  FROM job j
  JOIN company co ON co.id = j.company_id
  JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
  LEFT JOIN company_guide g ON g.company_id = co.id
 WHERE g.company_id IS NULL
 GROUP BY co.id, co.slug, co.display_name
 ORDER BY count(*) DESC;

-- ════════════════════════════════════════════════════════════════════
-- 12. 집계 — 매번 17,584건을 훑는 대신 갱신한다
-- ════════════════════════════════════════════════════════════════════
-- company_stacks.json(15MB) / trends.json 이 하던 계산. 크롤 사이클 끝에
-- REFRESH MATERIALIZED VIEW CONCURRENTLY 한 줄로 갱신한다.
CREATE MATERIALIZED VIEW mv_company_stack AS
SELECT co.id AS company_id, co.slug, co.display_name,
       te.id AS tech_id, te.name AS tech,
       count(*) AS n_jobs,
       max(j.last_seen_at) AS last_seen_at
  FROM job j
  JOIN company co ON co.id = j.company_id
  JOIN job_tech jt ON jt.job_id = j.id
  JOIN tech te ON te.id = jt.tech_id AND NOT te.is_noise
 GROUP BY co.id, co.slug, co.display_name, te.id, te.name;
-- CONCURRENTLY 갱신에는 UNIQUE 인덱스가 필수다.
CREATE UNIQUE INDEX mv_company_stack_pk ON mv_company_stack (company_id, tech_id);

-- 기술별 일자 스냅샷. `ingest_crawl.record_tech_daily` 가 job_state 에서 센다.
-- 아래 trend_day/trend_metric 과 세는 모집단이 다르다 — 이쪽은 키워드를 가리지 않는
-- DB 전체이고, 저쪽은 크롤 키워드('개발자')별이다. 분모가 다르니 섞으면 안 된다.
CREATE TABLE tech_daily (
    day      date    NOT NULL,
    tech_id  bigint  NOT NULL REFERENCES tech(id) ON DELETE CASCADE,
    n_active integer NOT NULL,
    PRIMARY KEY (day, tech_id)
);

-- ════════════════════════════════════════════════════════════════════
-- 13. 원장 — 파일로 쌓이던 시계열
-- ════════════════════════════════════════════════════════════════════
-- 여기 둘은 "지난 일"이라 다시 계산할 수 없다. 공고 집계는 언제든 job 을 다시
-- 훑으면 되지만, 3개월 전 그날 무엇이 몇 건이었는지는 그때 세어 둔 것 말고는
-- 복원할 방법이 없다. 그래서 파일(trends_history.jsonl / job_history.jsonl)로
-- 쌓고 있었고, 그 파일이 사라지면 시계열도 사라진다. DB 로 옮긴다.

-- ── 일자별 트렌드 스냅샷 (trends_history.jsonl) ───────────────────
-- 축이 넷이다: 기술 / 개념 키워드 / 경력 밴드 / 직군. 축마다 표를 만들면 넷이
-- 같은 모양으로 네 번 반복되므로 axis 한 컬럼으로 합친다. role 은 그 축을 직군별로
-- 쪼갠 것이고(''=전체), 그래서 (axis='tech', role='백엔드') 는 "백엔드 공고 안에서
-- 그 기술이 몇 건" 이 된다.
CREATE TYPE trend_axis AS ENUM ('tech', 'concept', 'band', 'role');

-- 그날의 분모. 크롤 키워드마다 훑은 범위가 달라('개발자' 673건 vs '통합' 5,349건)
-- 비중의 분모가 달라진다. 한 시계열에 섞으면 안 되므로 keyword 가 PK 에 들어간다.
CREATE TABLE trend_day (
    day     date        NOT NULL,
    keyword text        NOT NULL,
    total   integer     NOT NULL,
    at      timestamptz,
    PRIMARY KEY (day, keyword)
);

CREATE TABLE trend_metric (
    day     date       NOT NULL,
    keyword text       NOT NULL,
    axis    trend_axis NOT NULL,
    role    text       NOT NULL DEFAULT '',   -- '' = 전체, 아니면 직군별 분해
    name    text       NOT NULL,
    n       integer    NOT NULL,
    PRIMARY KEY (day, keyword, axis, role, name),
    FOREIGN KEY (day, keyword) REFERENCES trend_day(day, keyword) ON DELETE CASCADE
);
-- 한 기술의 시계열을 뽑는 질의가 기본이다.
CREATE INDEX trend_metric_series_idx ON trend_metric (keyword, axis, role, name, day);

-- ── 행동 기록 (engagement/events.jsonl) ───────────────────────────
-- 누가 무엇을 열어 얼마나 머물렀나. 이것도 다시 계산할 수 없다 — 게다가 파일
-- 쪽에는 64MB 를 넘으면 .jsonl.1 로 밀어내는 회전이 있어서, 오래된 기록이
-- **조용히 버려진다**(밀려난 파일은 아무도 안 읽는다).
--
-- `at` 은 브라우저가 준 절대 시각이 아니라 서버 시계 위에 올린 값이다. 이벤트는
-- 10초마다 묶여서 오므로 받은 시각을 그대로 쓰면 한 묶음이 전부 같은 시각이 되고
-- 체류시간이 통째로 사라진다. 그 보정은 collect._timeline 이 한다.
CREATE TYPE engagement_kind AS ENUM ('session', 'view', 'click', 'dwell', 'search', 'filter');

CREATE TABLE engagement_event (
    id      bigint          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sid     text            NOT NULL,       -- 브라우저 세션. 사람을 특정하지 않는다
    kind    engagement_kind NOT NULL,
    at      timestamptz     NOT NULL,
    item    text,                           -- 공고 URL 또는 화면 경로 (파일의 `k`)
    source  text,                           -- 유입 경로 호스트 또는 'direct' (`from`)
    dwell_s integer                         -- kind='dwell' 일 때만. 1~3600
);
-- 집계는 늘 "최근 N일"이다.
CREATE INDEX engagement_event_at_idx  ON engagement_event (at DESC);
-- '이 공고를 본 사람이 그다음 무엇을 눌렀나' 는 세션 안의 순서를 훑는다.
CREATE INDEX engagement_event_sid_idx ON engagement_event (sid, at);

-- ── 공고 판본 이력 (job_history.jsonl) ────────────────────────────
-- 같은 자리가 마감됐다 다시 올라올 때 URL 이 재발급되므로 (회사,제목) 정규화 키로
-- 묶는다. 그래서 job(id) 를 참조하지 않는다 — 참조하면 판본마다 다른 공고가 된다.
--
-- **UNIQUE (job_key, hash) 가 이 표의 핵심이다.** 빌더는 "그 자리의 모든 기록과
-- 비교해 같은 해시가 있으면 넣지 않는다"는 규칙을 파이썬으로 지키고 있었다.
-- 직전 판만 보던 시절 A→B→A 를 오가는 20개 자리가 실행마다 파일을 늘렸다.
-- 제약으로 옮기면 빌더가 잊어도 DB 가 거절한다.
--
-- id 순서가 곧 판본 순서다(versions[-1] = 최신). 그래서 identity 를 쓴다.
CREATE TABLE job_version (
    id      bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_key text        NOT NULL,          -- '회사\t제목' 정규화 키
    hash    text        NOT NULL,          -- 내용 해시 16자
    seen    text        NOT NULL,          -- 'bootstrap' 또는 YYYY-MM-DD
    data    jsonb       NOT NULL,          -- snapshot() 이 남기는 최소 형태
    at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (job_key, hash)
);
CREATE INDEX job_version_key_idx ON job_version (job_key, id);

-- ════════════════════════════════════════════════════════════════════
-- 14. 외주·프리랜서 프로젝트 — job 과 따로, tech 사전은 공유
-- ════════════════════════════════════════════════════════════════════
-- db/migrations/005_freelance_project.sql 과 글자 그대로 같다(설계 근거는 그쪽 머리말).
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

-- ════════════════════════════════════════════════════════════════════
-- 15. 외주 프로젝트 이력 — 단가가 얼마나 내려갔나
-- ════════════════════════════════════════════════════════════════════
-- db/migrations/006_project_version.sql 과 글자 그대로 같다(설계 근거는 그쪽 머리말).
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
