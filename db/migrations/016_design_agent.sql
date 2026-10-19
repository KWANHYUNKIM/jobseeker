-- 016 — 디자인 에이전트: 영감을 모으고(출처·모은 것), 교훈으로 뽑고, 시안에 써 보고, 사람이 판정한다.
--
-- 왜 DB 인가: 지금까지 디자인 판단은 .py·.json 을 손으로 고친 것이라 쌓이지 않았다(2026-10-19 사용자 지적 —
-- "py 나 json 을 백날 바꿔봤자 소용없다"). 교훈과 그 점수를 표로 두면 코드는 그대로이고, 판정이 쌓일수록
-- 교훈의 순위가 바뀐다. 점수는 사람만 매긴다 — 에이전트는 모으고, 뽑고, 써 볼 뿐이다.
--
--   design_source   어디서 배우나 — 유튜브 채널·인스타 계정·디자인 칼럼
--   design_ref      모은 것 하나 — 영상·게시물·글. 원본 링크와 요약, 저장한 화면(내부 참고용)
--   design_lesson   교훈 — 근거(design_lesson_ref)와 분야, 그리고 기계가 바로 쓸 수 있는 손잡이(apply)
--   design_trial    시안 묶음 하나 — 어느 코너를 어떤 교훈으로 찍었나. 올려도 되는지(release)는 사람이 정한다
--   design_verdict  장마다 사람이 매긴 판정(+1 좋다 / -1 별로)과 한 줄 이유
--   design_lesson_score  교훈마다 점수 = 그 교훈을 쓴 시안의 판정 합
BEGIN;

DO $$ BEGIN
    CREATE TYPE design_source_kind AS ENUM ('youtube', 'instagram', 'web');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    -- 배치 · 글자 · 색 · 사진 · 문구 · 장 순서 · 계절/때
    CREATE TYPE design_area AS ENUM ('layout', 'type', 'color', 'photo', 'copy', 'sequence', 'season');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS design_source (
    id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind       design_source_kind NOT NULL,
    handle     text        NOT NULL,              -- @rollstory · longblack.co · designcompass.org
    url        text        NOT NULL,
    name       text,
    region     text,                              -- 'kr' · 'global'
    followers  text,                              -- 본 날의 표기 그대로('23.8만')
    note       text,
    added_at   timestamptz NOT NULL DEFAULT now(),
    checked_at timestamptz,                       -- 마지막으로 모은 때
    UNIQUE (kind, handle)
);

CREATE TABLE IF NOT EXISTS design_ref (
    id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id    bigint      REFERENCES design_source(id) ON DELETE SET NULL,
    url          text        NOT NULL UNIQUE,
    title        text,
    summary      text,                            -- 설명·캡션을 짧게(원문을 길게 옮기지 않는다)
    published_at timestamptz,
    metrics      jsonb       NOT NULL DEFAULT '{}',   -- 조회·좋아요·팔로워 — 본 날의 값
    media        jsonb       NOT NULL DEFAULT '[]',   -- 저장한 화면 경로(design-lab/refs/agent/…) 또는 썸네일 주소
    collected_by text        NOT NULL,            -- 'youtube-api' · 'instagram-web' · 'web' · 'manual'
    collected_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS design_lesson (
    id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    area       design_area NOT NULL,
    rule       text        NOT NULL,              -- "표지는 질문 두 줄 + 실물 사진 한 장"
    how        text,                              -- 우리 판에 어떻게 옮기나
    apply      jsonb       NOT NULL DEFAULT '{}', -- 기계가 바로 쓰는 손잡이 — 예 {"layout": {"cover": "poster"}}
    origin     text        NOT NULL DEFAULT 'ref',   -- 'ref'(모은 것에서) · 'verdict'(사람의 판정 이유에서)
    status     text        NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'active', 'retired')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (area, rule)
);

CREATE TABLE IF NOT EXISTS design_lesson_ref (
    lesson_id bigint NOT NULL REFERENCES design_lesson(id) ON DELETE CASCADE,
    ref_id    bigint NOT NULL REFERENCES design_ref(id) ON DELETE CASCADE,
    PRIMARY KEY (lesson_id, ref_id)
);

CREATE TABLE IF NOT EXISTS design_trial (
    id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corner      text        NOT NULL,             -- deadline · numbers · board · brands …
    deck_path   text        NOT NULL,
    out_dir     text        NOT NULL,
    slides      integer     NOT NULL,
    direction   jsonb       NOT NULL DEFAULT '{}',
    rendered_at timestamptz NOT NULL DEFAULT now(),
    -- 올려도 되나 — 사람만 정한다. NULL = 아직 안 봄. true 가 아니면 발행 큐로 보내지 않는다
    release     boolean,
    release_note text,
    release_at  timestamptz
);

CREATE TABLE IF NOT EXISTS design_trial_lesson (
    trial_id  bigint NOT NULL REFERENCES design_trial(id) ON DELETE CASCADE,
    lesson_id bigint NOT NULL REFERENCES design_lesson(id) ON DELETE CASCADE,
    PRIMARY KEY (trial_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS design_verdict (
    id       bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trial_id bigint      NOT NULL REFERENCES design_trial(id) ON DELETE CASCADE,
    slide_no integer     NOT NULL,                -- 1 부터. 0 = 묶음 전체
    verdict  smallint    NOT NULL CHECK (verdict IN (-1, 1)),
    reason   text,
    at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (trial_id, slide_no)                   -- 다시 누르면 고친다
);

-- 교훈 점수 — 그 교훈을 쓴 시안들의 판정 합. 판정이 없는 교훈은 0.
CREATE OR REPLACE VIEW design_lesson_score AS
SELECT l.id AS lesson_id, l.area, l.rule, l.status,
       COALESCE(sum(v.verdict), 0)::int AS score,
       count(v.id)::int AS votes,
       count(DISTINCT tl.trial_id)::int AS trials
  FROM design_lesson l
  LEFT JOIN design_trial_lesson tl ON tl.lesson_id = l.id
  LEFT JOIN design_verdict v ON v.trial_id = tl.trial_id
 GROUP BY l.id;

COMMIT;
