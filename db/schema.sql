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
    CONSTRAINT job_region_known    CHECK (region IS NULL OR region IN ('kr','global')),
    CONSTRAINT job_seen_order      CHECK (last_seen_at >= first_seen_at)
);

COMMENT ON TABLE  job IS '공고 1건. 정체성은 url — (회사명,제목) 이 아니다';
COMMENT ON COLUMN job.gone_at IS '목록에서 사라진 시각. 사라짐≠마감이라 status 를 직접 바꾸지 않고 close_check 의 입력이 된다';
COMMENT ON COLUMN job.dday_text_raw IS '표시에 쓰지 말 것. 크롤 시점 문자열이라 하루만 지나도 틀린다';

CREATE INDEX job_company_idx    ON job (company_id);
CREATE INDEX job_site_idx       ON job (site);
CREATE INDEX job_deadline_idx   ON job (deadline_on) WHERE deadline_on IS NOT NULL;
CREATE INDEX job_last_seen_idx  ON job (last_seen_at DESC);
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
    http_status smallint,
    evidence    text,                       -- 판단 근거가 된 페이지 문구
    checker     text        NOT NULL DEFAULT 'close_check'
);
CREATE INDEX job_closure_latest_idx ON job_closure_check (job_id, checked_at DESC);

-- 공고별 최신 재확인 1건
CREATE VIEW job_closure_latest AS
SELECT DISTINCT ON (job_id) job_id, checked_at, closed, deadline_on, evidence, checker
  FROM job_closure_check
 ORDER BY job_id, checked_at DESC;

-- 재확인 대기열: 원장이 아예 없거나 오래된 순. close_check 가 매 사이클 400건씩 가져간다.
CREATE VIEW job_recheck_queue AS
SELECT j.id, j.site, j.url, c.checked_at
  FROM job j
  LEFT JOIN job_closure_latest c ON c.job_id = j.id
 WHERE j.gone_at IS NULL
   AND (c.job_id IS NULL OR (NOT c.closed AND c.checked_at < now() - interval '7 days'))
 ORDER BY c.checked_at NULLS FIRST, j.last_seen_at DESC;

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
    COALESCE(t.techs, '{}'::text[]) AS tech_stack
FROM job j
JOIN company co ON co.id = j.company_id
JOIN job_state s ON s.job_id = j.id
LEFT JOIN LATERAL (
    SELECT array_agg(te.name ORDER BY te.name) AS techs
      FROM job_tech jt JOIN tech te ON te.id = jt.tech_id
     WHERE jt.job_id = j.id AND NOT te.is_noise
) t ON true;

COMMENT ON VIEW v_job IS '뷰어/검색 API 가 읽는 정본. all_jobs_enriched.json 은 이 뷰의 덤프로 강등된다';

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

-- 기술별 일자 스냅샷. 지금은 trends_reports/*.md 파일로 쌓이는 것.
CREATE TABLE tech_daily (
    day      date    NOT NULL,
    tech_id  bigint  NOT NULL REFERENCES tech(id) ON DELETE CASCADE,
    n_active integer NOT NULL,
    PRIMARY KEY (day, tech_id)
);

COMMIT;
