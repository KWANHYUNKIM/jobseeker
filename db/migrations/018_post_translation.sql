-- 018: 블로그 글 번역 — 로컬 모델(5070 Ti, Ollama)로 한국어가 아닌 글을 한국어로.
--
-- post.lang 은 피드 설정에서 온 값이라 틀린다(일본 회사 블로그가 'en' 으로 들어온다).
-- 그래서 본문을 보고 다시 판정한 언어(src_lang)를 여기에 둔다. 한국어 글도 한 줄 남겨
-- "확인했다"를 기록한다(번역 칸은 비움).
-- source_hash 는 번역한 원문(제목·요약·본문·blog_content 본문)의 해시 — 원문이 바뀌면 다시 번역한다.
-- content_ko 는 blog_content/<id>.json 의 전체 본문 번역(그 파일이 있는 글만). 뷰어는 그 파일을 읽고,
-- 파일의 content_ko 도 같이 채운다.
CREATE TABLE IF NOT EXISTS post_translation (
    post_id       bigint      PRIMARY KEY REFERENCES post(id) ON DELETE CASCADE,
    src_lang      text        NOT NULL,                 -- 판정한 원문 언어: ko / en / ja / zh / de …
    title_ko      text        NOT NULL DEFAULT '',
    summary_ko    text        NOT NULL DEFAULT '',
    body_ko       text        NOT NULL DEFAULT '',
    content_ko    text        NOT NULL DEFAULT '',
    source_hash   text        NOT NULL,
    model         text        NOT NULL DEFAULT '',
    translated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS post_translation_lang_idx ON post_translation (src_lang);
