-- 019 — 커리어 경로(합격·이직·전환 후기): 원문과 구조화한 경험담을 DB 에 둔다.
--
-- 왜. `catch_capture/careers/` 가 모은 후기는 `var/careers/` 파일(raw/*.json · paths.jsonl ·
-- application.jsonl · age.jsonl · roster/rows.jsonl)로만 있었고, 화면은 admin(8910)의 보고서 한 장이
-- 원문 링크로 나가는 것뿐이었다. 연도·회사·회사 유형으로 잘라 보려면 질의할 수 있는 표가 필요하고,
-- 원문이 지워지거나 바뀌어도 우리가 읽은 판이 남아야 한다 — 그래서 원문도 같이 담는다.
--
-- 무엇을 담나.
--   career_post   글 한 편의 원문(텍스트). 글쓴이 이름·아이디·사진은 처음부터 받지 않았다(careers/__init__.py).
--                 **본문은 공개 API 로 나가지 않는다** — 남의 글이라 화면에 그대로 다시 싣지 않는다.
--                 뷰어 API 는 CAREERS_KEY 를 아는 요청(사용자 본인)에게만 본문을 준다.
--   career_story  그 글에서 뽑은 경험담 한 줄 — 걸러진 글(is_story=false)도 행을 남긴다(다시 묻지 않게).
--                 자르는 축(연도·회사·회사 유형·직무·경력·전환·출발지)은 열로, 나머지는 data(jsonb).
--   career_roster 인스타 '합격자 명단' 게시물 하나 — 이름 없이 학교·전공 → 합격처 표.
--
-- 쓰는 쪽은 `python -m store.ingest.careers`(careers.cycle 이 회차 끝에 부른다). 같은 내용이면
-- content_hash 로 건너뛴다. 읽는 쪽은 backend `features/careers`.
--
-- 적용:  docker exec -i jobseeker-db psql -U jobseeker -d jobseeker -v ON_ERROR_STOP=1 < db/migrations/019_career.sql
--        (두 번 돌려도 안전하다)

BEGIN;

CREATE TABLE IF NOT EXISTS career_post (
    id            text        PRIMARY KEY,            -- careers.store.rid — '<출처>-<해시>'
    source        text        NOT NULL,               -- velog · instagram · devto · medium · tistory · inbox
    url           text,
    title         text,
    posted_on     date,
    tags          text[]      NOT NULL DEFAULT '{}',
    query         text,                               -- 어떤 검색어로 찾았나
    body          text        NOT NULL DEFAULT '',
    collected_at  timestamptz,
    content_hash  text        NOT NULL,
    stored_at     timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS career_post_source_idx ON career_post (source);

CREATE TABLE IF NOT EXISTS career_story (
    post_id         text        PRIMARY KEY REFERENCES career_post(id) ON DELETE CASCADE,
    is_story        boolean     NOT NULL,             -- 커리어 경험담인가(아니면 아래는 비어 있다)
    counted         boolean     NOT NULL DEFAULT false, -- 집계에 넣나(경험담 + IT 이야기 — report.py 와 같은 규칙)
    kind            text,                             -- 합격·이직·첫취업·불합격·교육과정·직무전환·회고…
    year            int,                              -- 사건 연도(글에 밝힌 것, 없으면 게시 연도)
    period          text,                             -- '2024 상반기'
    company         text,                             -- 간 곳(대표 표기)
    company_key     text,                             -- core.normalize.company
    program         text,                             -- 회사가 아니라 교육과정·동아리면 그 이름
    company_type    text,                             -- 빅테크·플랫폼 · 대기업 · 금융 · 공공 · 게임 · 외국계 · 중견·중소 · 스타트업 · 교육과정 · 미분류
    company_size    text,                             -- core.classifier 화이트리스트(대기업·중견기업) — 모르면 NULL
    role            text,
    level           text,                             -- 신입·경력·인턴…
    years_before    numeric,                          -- 그 일 전 경력(년)
    transition      text,                             -- 모델이 적은 원래 문장
    transition_cat  text,                             -- 비개발→개발 · SI→서비스 · 스타트업→대기업 …
    origin          text,                             -- 경력직이 떠나 온 곳의 갈래(SI·SM · 스타트업 · 대기업 …)
    education       text,                             -- 원문 근거가 없으면 '확인되지 않음'
    age             int,
    data            jsonb       NOT NULL,             -- 추출 결과 전체(spec·path·selection·application·advice…)
    extracted_by    text,
    content_hash    text        NOT NULL,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS career_story_year_idx    ON career_story (year)         WHERE counted;
CREATE INDEX IF NOT EXISTS career_story_company_idx ON career_story (company_key)  WHERE counted;
CREATE INDEX IF NOT EXISTS career_story_type_idx    ON career_story (company_type) WHERE counted;
CREATE INDEX IF NOT EXISTS career_story_level_idx   ON career_story (level)        WHERE counted;

CREATE TABLE IF NOT EXISTS career_roster (
    post          text        PRIMARY KEY,            -- 캡처 폴더 이름
    url           text,
    tag           text,
    posted_on     date,
    poster        text,                               -- 학원 · 대학·학과 · 개인 …
    list_kind     text,
    it            boolean     NOT NULL DEFAULT false,
    rows          jsonb       NOT NULL DEFAULT '[]',  -- [{school, major, major_cs, org, org_type, role, it, age, year, count}]
    content_hash  text        NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now()
);

COMMIT;
