"""디자인 에이전트 표 읽기·쓰기 — 016_design_agent.sql. SQL 은 여기에만 둔다."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager

DSN = os.environ.get("JOBSEEKER_DSN", "postgresql://jobseeker:jobseeker@127.0.0.1:5433/jobseeker")


@contextmanager
def cursor():
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            yield cur
        conn.commit()


def _j(v) -> str:
    return json.dumps(v, ensure_ascii=False)


# --- ① 모으기 ---------------------------------------------------------------
def upsert_source(kind: str, handle: str, url: str, *, name=None, region=None, followers=None, note=None) -> int:
    with cursor() as c:
        c.execute("""INSERT INTO design_source (kind, handle, url, name, region, followers, note)
                     VALUES (%s,%s,%s,%s,%s,%s,%s)
                     ON CONFLICT (kind, handle) DO UPDATE SET
                       url = EXCLUDED.url, name = COALESCE(EXCLUDED.name, design_source.name),
                       region = COALESCE(EXCLUDED.region, design_source.region),
                       followers = COALESCE(EXCLUDED.followers, design_source.followers),
                       note = COALESCE(EXCLUDED.note, design_source.note)
                     RETURNING id""", (kind, handle, url, name, region, followers, note))
        return c.fetchone()["id"]


def sources(kind: str | None = None) -> list[dict]:
    with cursor() as c:
        c.execute("SELECT * FROM design_source WHERE %s::text IS NULL OR kind::text = %s ORDER BY kind, id", (kind, kind))
        return c.fetchall()


def touch_source(source_id: int) -> None:
    with cursor() as c:
        c.execute("UPDATE design_source SET checked_at = now() WHERE id = %s", (source_id,))


def upsert_ref(url: str, *, source_id=None, title=None, summary=None, published_at=None, metrics=None,
               media=None, collected_by="manual") -> int:
    with cursor() as c:
        c.execute("""INSERT INTO design_ref (source_id, url, title, summary, published_at, metrics, media, collected_by)
                     VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
                     ON CONFLICT (url) DO UPDATE SET
                       title = COALESCE(EXCLUDED.title, design_ref.title),
                       summary = COALESCE(EXCLUDED.summary, design_ref.summary),
                       metrics = design_ref.metrics || EXCLUDED.metrics,
                       media = CASE WHEN EXCLUDED.media = '[]'::jsonb THEN design_ref.media ELSE EXCLUDED.media END
                     RETURNING id""",
                  (source_id, url, title, summary, published_at, _j(metrics or {}), _j(media or []), collected_by))
        return c.fetchone()["id"]


# --- ② 배우기 ---------------------------------------------------------------
def upsert_lesson(area: str, rule: str, *, how=None, apply=None, origin="ref", status="candidate",
                  refs: list[int] = ()) -> int:
    with cursor() as c:
        c.execute("""INSERT INTO design_lesson (area, rule, how, apply, origin, status)
                     VALUES (%s,%s,%s,%s::jsonb,%s,%s)
                     ON CONFLICT (area, rule) DO UPDATE SET how = COALESCE(EXCLUDED.how, design_lesson.how)
                     RETURNING id""", (area, rule, how, _j(apply or {}), origin, status))
        lid = c.fetchone()["id"]
        for r in refs:
            c.execute("INSERT INTO design_lesson_ref VALUES (%s,%s) ON CONFLICT DO NOTHING", (lid, r))
        return lid


def lessons(status: tuple[str, ...] = ("active", "candidate")) -> list[dict]:
    """점수 순. 같은 점수면 사람 판정에서 나온 것(verdict) 먼저, 그다음 오래된 것."""
    with cursor() as c:
        c.execute("""SELECT l.*, s.score, s.votes, s.trials,
                            (SELECT json_agg(json_build_object('url', r.url, 'title', r.title))
                               FROM design_lesson_ref lr JOIN design_ref r ON r.id = lr.ref_id
                              WHERE lr.lesson_id = l.id) AS evidence
                       FROM design_lesson l JOIN design_lesson_score s ON s.lesson_id = l.id
                      WHERE l.status = ANY(%s)
                      ORDER BY s.score DESC, (l.origin = 'verdict') DESC, l.id""", (list(status),))
        return c.fetchall()


#: 원고·키트를 실제로 바꾸는 손잡이. 이 중 하나도 없는 교훈은 '글로만 있는 교훈'이다 — 시안에 안 걸리고 점수도 안 받는다.
#:   layout      {"<역할>": "<판>"}                       cover·list·stat… 의 판 이름(cardpress layouts/)
#:   kit         {"fonts": {"display": "serif"}, "image": {"scrim": 0.45}, "shape": {...}}   kit.yaml 에 겹쳐 쓴다
#:   copy        {"<역할>": {"title": "...", "kicker": "..."}}   그 역할의 첫 장 문구를 바꾼다
#:   photo_tags  ["물건", ...]                             사진 고를 때 태그를 더한다
#: 그 밖의 키: corner(그 코너에만) · always(늘 건다 — 지켜야 할 규칙이라 시험·점수 대상이 아니다)
EFFECTS = ("layout", "kit", "copy", "photo_tags")


def _merge(dst: dict, src: dict) -> bool:
    """src 를 dst 에 겹친다 — 이미 있는 값은 그대로(앞선 교훈이 이긴다). 하나라도 들어갔으면 True."""
    used = False
    for k, v in src.items():
        if isinstance(v, dict):
            used |= _merge(dst.setdefault(k, {}), v)
        elif k not in dst:
            dst[k] = v
            used = True
    return used


def pick_knobs(rows: list[dict], corner: str) -> dict:
    """교훈 목록(점수 순) → 이번 시안에 걸 손잡이. DB 없이 시험할 수 있게 순수 함수로 둔다.

    판정이 어느 교훈 덕인지 가르려면 한 시안에 새것을 여럿 섞으면 안 된다. 그래서
      - always       늘 건다(점수 대상 아님)
      - 점수 > 0     사람이 좋다고 한 것 — 계속 건다
      - 점수 < 0     뺀다
      - 나머지       (아직 판정 없음·찬반 반반) 그중 **하나만** — 시안에 가장 덜 걸려 본 것부터 돌아가며 시험한다
    """
    out: dict = {"layout": {}, "kit": {}, "copy": {}, "photo_tags": [], "lessons": [], "always": [], "trying": None}
    mine = [l for l in rows if (l.get("apply") or {}).get("corner") in (None, corner)
            and any((l.get("apply") or {}).get(e) for e in EFFECTS)]
    always = [l for l in mine if l["apply"].get("always")]
    kept = [l for l in mine if not l["apply"].get("always") and l["score"] > 0]
    untried = sorted((l for l in mine if not l["apply"].get("always") and l["score"] == 0),
                     key=lambda l: (l["trials"], l["id"]))
    for group, l in [("always", l) for l in always] + [("lessons", l) for l in kept + untried[:1]]:
        a, used = l["apply"], False
        for e in ("layout", "kit", "copy"):
            used |= _merge(out[e], a.get(e) or {})
        for t in a.get("photo_tags") or []:
            if t not in out["photo_tags"]:
                out["photo_tags"].append(t)
                used = True
        if used:
            out[group].append(l["id"])
    if untried and untried[0]["id"] in out["lessons"]:
        out["trying"] = untried[0]["id"]
    return out


def knobs(corner: str) -> dict:
    # 후보(candidate)도 시험 대상이다 — 루프가 새로 뽑은 교훈은 시안에 걸려 봐야 판정을 받는다
    return pick_knobs(lessons(("active", "candidate")), corner)


def set_apply(lesson_id: int, apply: dict) -> None:
    """교훈에 손잡이를 단다(루프가 글로만 있는 교훈을 기계가 쓸 수 있게 옮길 때)."""
    with cursor() as c:
        c.execute("UPDATE design_lesson SET apply = %s::jsonb WHERE id = %s", (_j(apply), lesson_id))


# --- ③ 써 보기 · ④ 판정 -------------------------------------------------------
def record_trial(corner: str, deck_path: str, out_dir: str, slides: int, direction: dict, lesson_ids: list[int]) -> int:
    with cursor() as c:
        c.execute("""INSERT INTO design_trial (corner, deck_path, out_dir, slides, direction)
                     VALUES (%s,%s,%s,%s,%s::jsonb) RETURNING id""", (corner, deck_path, out_dir, slides, _j(direction)))
        tid = c.fetchone()["id"]
        for lid in lesson_ids:
            c.execute("INSERT INTO design_trial_lesson VALUES (%s,%s) ON CONFLICT DO NOTHING", (tid, lid))
        return tid


def trials(limit: int = 20) -> list[dict]:
    with cursor() as c:
        c.execute("""SELECT t.*,
                       (SELECT json_agg(json_build_object('slide', v.slide_no, 'verdict', v.verdict, 'reason', v.reason)
                                        ORDER BY v.slide_no) FROM design_verdict v WHERE v.trial_id = t.id) AS verdicts,
                       (SELECT json_agg(json_build_object('id', l.id, 'area', l.area, 'rule', l.rule))
                          FROM design_trial_lesson tl JOIN design_lesson l ON l.id = tl.lesson_id
                         WHERE tl.trial_id = t.id) AS lessons
                     FROM design_trial t ORDER BY t.id DESC LIMIT %s""", (limit,))
        return c.fetchall()


def verdict(trial_id: int, slide_no: int, value: int, reason: str | None) -> None:
    """사람만 부른다(8780 /design 의 버튼). 같은 장을 다시 누르면 고친다."""
    if value not in (-1, 1):
        raise ValueError("verdict 는 1(좋다) 또는 -1(별로)")
    with cursor() as c:
        c.execute("""INSERT INTO design_verdict (trial_id, slide_no, verdict, reason) VALUES (%s,%s,%s,%s)
                     ON CONFLICT (trial_id, slide_no) DO UPDATE SET verdict = EXCLUDED.verdict,
                       reason = EXCLUDED.reason, at = now()""", (trial_id, slide_no, value, reason or None))


def release(trial_id: int, ok: bool, note: str | None) -> None:
    """올려도 되나 — 사람만 정한다."""
    with cursor() as c:
        c.execute("UPDATE design_trial SET release = %s, release_note = %s, release_at = now() WHERE id = %s",
                  (ok, note or None, trial_id))


def new_reasons(since_id: int = 0) -> list[dict]:
    """에이전트가 회차 처음에 읽는다 — 사람이 남긴 이유는 다음 교훈 후보가 된다."""
    with cursor() as c:
        c.execute("""SELECT v.*, t.corner FROM design_verdict v JOIN design_trial t ON t.id = v.trial_id
                      WHERE v.id > %s AND v.reason IS NOT NULL ORDER BY v.id""", (since_id,))
        return c.fetchall()
