-- 010 — 공고의 필터 축(지역·시군구·직군·경력 구간·회사 규모)을 DB 에 둔다
--
-- 왜 필요한가. 뷰어는 지금까지 공고 전량(all_jobs_enriched.json, 184MB)을 받아 놓고
-- 이 다섯 축을 브라우저에서 계산해 필터와 칩 건수를 셌다. 파일이 사이클마다 새로
-- 구워져야 화면이 바뀌므로 DB 에서 공고가 닫혀도 화면은 다음 굽기까지 옛 상태였고,
-- 파이프라인이 멈추면 그대로 굳었다. 필터를 서버(store.api.main)로 옮기려면 같은 축이
-- SQL 로 걸려야 한다.
--
-- 값은 계산해서 저장한다(뷰로 두지 않는다). 규칙이 정규식 수십 개와 회사별 사원수·
-- 매출액 추출이라 SQL 로 옮기면 세 번째 사본이 생긴다. 규칙은 뷰어 TS 가 원본이고
-- store/jobs/facets.py 가 그 파이썬 판이다(실데이터 전량 대조: python -m store.jobs.facets --parity).
-- store.jobs.facets.refresh() 가 매 크롤 사이클(ingest_crawl) 끝에 전량을 다시 채운다.
--
-- status 는 여기 두지 않는다 — 그건 job_state 가 읽는 순간 계산한다(낡을 수 없게).
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/010_job_facet.sql
-- 두 번 돌려도 안전하다.

BEGIN;

CREATE TABLE IF NOT EXISTS job_facet (
    job_id        bigint      PRIMARY KEY REFERENCES job(id) ON DELETE CASCADE,
    region        text        NOT NULL,           -- 17개 시도 + '해외·원격' + '정보없음'
    district      text,                           -- 시군구(시도 아래 첫 시/군/구)
    roles         text[]      NOT NULL,           -- 멀티라벨 직군. 없으면 {'기타'}
    career_bucket text        NOT NULL,           -- '신입/무관' | '1-2년' | … | '정보없음'
    company_size  text,                           -- '대기업' | '중견기업' | '중소기업'
    -- 기술 스택 필터·칩. 칩은 원문 표기(앞뒤 공백만 벗기고 중복 제거)로 세고, 필터는
    -- 대소문자를 무시하고 "고른 스택을 전부 가진 공고" 다(뷰어 규칙 그대로).
    stacks        text[]      NOT NULL DEFAULT '{}',
    stacks_lc     text[]      NOT NULL DEFAULT '{}',
    -- 목록 검색어가 뒤지는 문자열: 회사·제목·본문을 소문자로 이어 붙인 것. 뷰어의
    -- hayOf() 와 같은 모양이다. 회사명은 company 표에 있어서 job 에 식 색인을 걸 수
    -- 없으므로 여기 한 번 만들어 둔다(본문 사본이라 크지만 검색이 글자 조각 일치라
    -- 이게 가장 싸다).
    hay           text        NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS job_facet_region_idx ON job_facet (region, district);
CREATE INDEX IF NOT EXISTS job_facet_roles_idx  ON job_facet USING gin (roles);
CREATE INDEX IF NOT EXISTS job_facet_career_idx ON job_facet (career_bucket);
CREATE INDEX IF NOT EXISTS job_facet_size_idx   ON job_facet (company_size);
CREATE INDEX IF NOT EXISTS job_facet_stacks_idx ON job_facet USING gin (stacks_lc);

-- 목록 검색어(부분일치). 뷰어가 하던 includes() 를 옮긴 것이라 형태소가 아니라
-- 글자 조각으로 찾는다 — pg_trgm 이 그 일을 한다.
CREATE INDEX IF NOT EXISTS job_facet_hay_trgm_idx ON job_facet USING gin (hay gin_trgm_ops);

-- 사이트 간 중복(job_dup, 004)을 구체화한다. job_dup 은 공고 전량에 윈도 함수를 거는
-- 뷰라 한 번에 250ms 가 들고, 목록 API 는 요청마다 그걸 세 번 읽었다(칩·페이지·전체 수).
-- 대표를 고르는 기준에 모집 상태가 들어가므로 영영 굳힐 수는 없다 — 상태를 바꾸는
-- 쪽(크롤 사이클의 store.jobs.facets.refresh, 10분마다 도는 close_check)이 끝에 갱신한다.
-- 공고의 모집 상태 자체는 여전히 job_state 에서 읽는 순간 계산한다.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_job_dup AS
SELECT job_id, canonical_id FROM job_dup;
CREATE UNIQUE INDEX IF NOT EXISTS mv_job_dup_pk ON mv_job_dup (job_id);

COMMIT;
