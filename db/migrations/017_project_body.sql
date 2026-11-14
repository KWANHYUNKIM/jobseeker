-- 017 — 외주 프로젝트 본문: 목록 행(project)과 따로 둔 상세 본문.
--
-- 왜 따로 두나. 뷰어의 외주 목록은 클릭하면 원본 사이트로 나갔다 — 우리 화면에서 내용을
-- 읽을 수 없었다. 본문은 프로젝트당 수 KB 라 project 에 넣으면 목록 API(전량)가 무거워진다.
-- 그래서 한 건씩 읽는 상세(`GET /api/freelance/projects/{site}/{pid}`)만 이 표를 붙인다.
--
-- 무엇을 담나. crawl_freelance 가 원본 상세(원티드 긱스 상세 API·프리모아 목록 본문·이랜서
-- JSON-LD·잡코리아/사람인 상세 iframe·아임잡 상세)에서 받은 글을 **텍스트로**, 이메일·전화를
-- 지워서 담는다. SISM 은 약관(복제·제3자 제공 금지)이라 받지 않는다 — 이 표에 행이 없고
-- 화면은 목록 요약과 원문 링크만 보인다.
--
-- 적용:  psql "$JOBSEEKER_DSN" -f db/migrations/017_project_body.sql   (두 번 돌려도 안전하다)

BEGIN;

CREATE TABLE IF NOT EXISTS project_body (
    project_id   bigint      PRIMARY KEY REFERENCES project(id) ON DELETE CASCADE,
    body         text        NOT NULL,
    fetched_at   timestamptz NOT NULL DEFAULT now(),
    content_hash text        NOT NULL,              -- 같은 본문이면 다시 쓰지 않는다
    CONSTRAINT project_body_not_blank CHECK (btrim(body) <> '')
);

COMMIT;
