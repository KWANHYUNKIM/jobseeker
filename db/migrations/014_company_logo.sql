-- 014: 회사 로고.
--
-- 메인 화면이 공고를 회사별로 묶어 로고 카드로 보여준다(뷰어 `/`, backend `/api/home`).
-- 로고는 공고 원문이 이미 주는 것을 쓴다 — 캐치 공고 페이지의 JSON-LD hiringOrganization.logo 처럼
-- 마감 재확인(close_check)·로고 수집이 원본에 물을 때 같이 받아 둔다. 없는 회사는 뷰어가
-- 알려진 도메인의 파비콘, 그다음 이름 첫 글자로 물러선다.
--
-- 적용: docker exec -i jobseeker-db psql -U jobseeker -d jobseeker -v ON_ERROR_STOP=1 < db/migrations/014_company_logo.sql

BEGIN;

ALTER TABLE company
  ADD COLUMN IF NOT EXISTS logo_url        text,          -- 원본이 준 로고 이미지 주소
  ADD COLUMN IF NOT EXISTS logo_source     text,          -- 어디서 받았나 (dev·jumpit·saramin·manual …)
  ADD COLUMN IF NOT EXISTS logo_checked_at timestamptz;   -- 마지막으로 찾아본 때(못 찾았어도 찍는다)

COMMIT;
