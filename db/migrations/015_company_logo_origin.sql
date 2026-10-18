-- 015: 회사 로고를 우리 서버에 둔다.
--
-- 014 의 logo_url 은 원본 이미지 서버 주소였다 — 방문자 브라우저가 캐치·점핏 서버에서 직접 받아
-- 그쪽 서버 상태와 접근 기록에 묶였다. 이제 수집기(crawlers/crawl_logos.py)가 이미지를 한 번 받아
-- 확인·재인코딩(PNG 128px)해 jd-viewer/public/logos/c/ 에 두고, logo_url 에는 우리 경로
-- (/logos/c/<이름>.png)를, 원본 주소는 logo_origin 에 남긴다.
--
-- 적용: docker exec -i jobseeker-db psql -U jobseeker -d jobseeker -v ON_ERROR_STOP=1 < db/migrations/015_company_logo_origin.sql

BEGIN;

ALTER TABLE company
  ADD COLUMN IF NOT EXISTS logo_origin text;   -- 로고를 받아 온 원본 주소(어디서 왔는지 남긴다)

COMMIT;
