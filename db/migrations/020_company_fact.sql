-- 020 — 회사 사실(연봉·인원·주소·복지 태그)·공고에 적힌 연봉·연차별 시장 시세를 DB 에 둔다.
--
-- 왜. `crawlers/crawl_company_facts.py` 가 AI 없이 모은 값(국민연금 가입 사업장·원티드 회사 페이지·
-- 공고 본문의 연봉 줄·KOSIS 고용형태별노동실태조사)을 처음에는 public/roles/company/<회사>.json 3천여 개로
-- 구워 git 에 실었다. 크롤 산출물은 회차마다 바뀌어 이력을 데이터로 덮는다 — 수집 중간물(JSON)은
-- `catch_capture/var/roles/` 에만 두고(커밋 안 함), 정본은 여기 표다. 화면 모양은 backend
-- `features/company_facts` 가 이 표에서 만든다.
--
-- 무엇을 담나.
--   company_fact            회사 하나(키 = 회사명 정규화, engine/roles/validate.py co_norm 과 같다).
--                           원티드 값과 국민연금 값을 따로 둔다(기준이 달라 섞지 않는다).
--   company_posting_salary  공고 한 건에 회사가 적은 연봉(최저·최고·이상/범위/고정·경력 조건·원문 구절).
--   market_wage             직종(한국표준직업분류 7차) × 경력년수 연봉(전국, 만원).
--   market_wage_size        회사 규모 × 연령(대졸 이상, 전 직종) 연봉·평균 근속.
--
-- 쓰는 쪽: `python -m store.ingest.company_facts`(crawl_company_facts build·wage 가 끝에 부른다).
-- 같은 내용이면 content_hash 로 건너뛴다. 읽는 쪽: backend `/api/company-facts`, `/api/market-wage`.
--
-- 적용:  docker exec -i jobseeker-db psql -U jobseeker -d jobseeker -v ON_ERROR_STOP=1 < db/migrations/020_company_fact.sql
--        (두 번 돌려도 안전하다)

BEGIN;

CREATE TABLE IF NOT EXISTS company_fact (
    company_key         text        PRIMARY KEY,
    name                text        NOT NULL,              -- 화면에 쓰는 이름(원티드 표기 → 공고 표기)
    names               text[]      NOT NULL DEFAULT '{}', -- 공고에 나온 표기 전부
    employees           integer,                           -- 원티드(국민연금 기준) → 없으면 국민연금 가입자 수
    industry            text,
    founded             integer,
    address             text,                              -- 원티드 도로명(번지까지) → 없으면 국민연금(길 이름까지)
    address_source      text,                              -- 'wanted' | 'nps'
    benefit_tags        text[]      NOT NULL DEFAULT '{}', -- 원티드 복지 태그(규모·연봉 순위 태그는 뺐다)
    wanted_url          text,
    wanted_avg_pay      integer,                           -- 만원, 원티드가 국민연금으로 계산한 회사 평균
    wanted_pay_updated  date,
    nps_members         integer,
    nps_annual_est      integer,                           -- 만원, 고지금액 ÷ 가입자 ÷ 보험료율 × 12
    nps_month           text,                              -- 'YYYY-MM' 자료 기준월
    nps_biz6            text,                              -- 사업자등록번호 앞 6자리
    nps_address         text,
    content_hash        text        NOT NULL,
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS company_posting_salary (
    job_key       text        PRIMARY KEY,                 -- '<사이트>-<pid>'
    company_key   text        NOT NULL,
    title         text,
    url           text,
    pay_min       integer     NOT NULL,                    -- 만원
    pay_max       integer,                                 -- 만원, 범위일 때만
    kind          text        NOT NULL,                    -- '고정' | '범위' | '이상'
    career        text,                                    -- '신입' · '3~10년' · 공고의 경력 칸
    quote         text,                                    -- 공고 원문의 그 구절(100자 안)
    seen_on       date,
    content_hash  text        NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS company_posting_salary_company ON company_posting_salary (company_key);

CREATE TABLE IF NOT EXISTS market_wage (
    year          integer     NOT NULL,
    occ_code      text        NOT NULL,                    -- 한국표준직업분류 7차(222 = 컴퓨터 시스템 및 소프트웨어 전문가)
    occ_name      text        NOT NULL,
    career        text        NOT NULL,                    -- '전경력' · '1년미만' · '1~3년미만' · … · '10년이상'
    annual_pay    integer,                                 -- 만원, 월임금총액 × 12
    workers       integer,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (year, occ_code, career)
);

CREATE TABLE IF NOT EXISTS market_wage_size (
    year          integer     NOT NULL,
    size          text        NOT NULL,                    -- '전규모5인이상' · '5~9인' · … · '500인이상'
    age           text        NOT NULL,                    -- '전체' · '25~29' · …
    annual_pay    integer,                                 -- 만원, 대졸 이상
    tenure_years  real,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (year, size, age)
);

COMMIT;
