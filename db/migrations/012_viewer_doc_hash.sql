-- 012 — 화면용 문서(viewer_doc)에 내용 해시를 둔다
--
-- 뷰어가 정적 파일로만 받던 화면(역설계·취업 브리핑·기술도서·레이더·트렌드·캘린더·재공고·
-- 마인드맵·커리어 맵·학습 경로·부품 스펙·데이터센터 …)도 뷰어 API(/api/docs/<경로>)로
-- 받게 한다. 그 파일들은 빌더나 조사 엔진이 쓰는 문서라 계산은 그대로 두고, 파이프라인의
-- `store.ingest.docs` 가 회차마다 DB 로 옮긴다(kind='file', key=public 기준 경로).
-- 2천 개 남짓이라 매번 다 쓰지 않도록 내용 해시로 바뀐 것만 쓴다.
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/012_viewer_doc_hash.sql
-- 두 번 돌려도 안전하다.

BEGIN;

ALTER TABLE viewer_doc ADD COLUMN IF NOT EXISTS content_hash text;

COMMIT;
