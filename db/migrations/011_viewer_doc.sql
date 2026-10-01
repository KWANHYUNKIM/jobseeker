-- 011 — 빌더가 계산한 화면용 문서를 DB 에 둔다(viewer_doc) · 하드웨어 매물 순위 · 글 시각
--
-- 왜 필요한가. 공고처럼 표로 가진 데이터는 뷰어 API(backend)가 SQL 로 바로 답한다.
-- 그런데 회사 프로필(company_stacks.json, 15MB)·외주 단가 분석은 파이썬 휴리스틱
-- 수백 줄(build_company_stacks.py · pipeline/freelance_rates.py)이 만드는 결과라 SQL 로
-- 옮기면 세 번째 사본이 생긴다. 그래서 계산은 그대로 빌더가 하고, **결과를 여기에 쓴다**.
-- API 는 회사 한 곳씩(또는 목록 요약만) 잘라서 돌려준다 — 뷰어가 회사 탭을 열 때마다
-- 15MB 를 받던 것이 수 KB 가 된다. 정적 파일은 사전 렌더링·API 없는 배포용으로 남는다.
--
-- kind 별 key:
--   company        회사 이름(norm)       — 회사 하나의 전체 프로필(CompanyStack)
--   company_index  ''                    — 목록 메타(generated_at·total_jobs …)
--   freelance      'meta'                — 추이·분석·단가 기록·프로젝트별 분류
--   blog           'meta'                — 태그 → 주제 대응표 등 글 목록의 메타
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/011_viewer_doc.sql
-- 두 번 돌려도 안전하다.

BEGIN;

CREATE TABLE IF NOT EXISTS viewer_doc (
    kind      text        NOT NULL,
    key       text        NOT NULL DEFAULT '',
    payload   jsonb       NOT NULL,
    built_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (kind, key)
);
COMMENT ON TABLE viewer_doc IS '빌더가 계산한 화면용 문서. 원본 데이터가 아니라 다시 계산할 수 있는 결과다';

-- 하드웨어 매물의 다나와 인기상품순 순위. 화면이 '대표 제품'(가장 많이 팔리는 것)을
-- 고를 때 쓴다 — prices.json 에만 있고 DB 에는 없어서 API 가 같은 모양을 못 만들었다.
ALTER TABLE hw_offer_day ADD COLUMN IF NOT EXISTS rank integer;

-- 글이 올라온 시각. published_on(날짜)만으로는 같은 날 글의 순서와 화면의 published_ts 를
-- 만들 수 없다 — 글 목록은 이 시각의 역순이다(crawl_techblog 가 파일을 그렇게 정렬한다).
ALTER TABLE post ADD COLUMN IF NOT EXISTS published_at timestamptz;

COMMIT;
