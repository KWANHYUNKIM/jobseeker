"""고정 코너 — 매주 같은 자리에 돌아오는 카드뉴스. 원고(YAML)와 키트만 만들고 찍기는 cardpress 가 한다.

채용 포털 인스타(링커리어·인크루트·원티드·리멤버)에서 저장을 부르는 건 '매주 같은 코너' 였다.
코너마다 틀(판 구성)은 고정하고, 사진과 색은 그 주의 날짜·계절과 내용으로 poster/direction.py 가 정한다.

    deadline   [이번 주 마감]      이번 주에 닫히는 개발 공고 — 회사·공고·남은 날
    numbers    [개발 채용 숫자]     VOL.n — 직군·기술·신입 비율·마감 방식
    board      [지금 많이 뽑는 직군]  직군마다 숫자판 한 장 — 모집 수·찾는 기술·많이 연 회사
    (이번 주의 회사는 poster/newscard.py brands — 회사 색·대표 물건)

    python -m poster.corners            # out/corners/<코너>/deck.yaml + kit.yaml
    python -m poster.corners gallery    # 찍은 뒤 — out/corners/index.html (방향과 결과를 한 장에)
    cardpress render out/corners/deadline/deck.yaml -k out/corners/deadline/kit.yaml

흐름 (8780 '프로세스' 칸이 이 그림을 그대로 보여 준다 — 바꾸면 화면도 바뀐다):

    정본 DB ── 모집중 공고(사이트 간 사본은 대표만)
       │
       ▼  python -m poster.corners
    방향 정하기  날짜·계절 × 내용 × 회사 이미지 × 인스타 트렌드 → 사진 한 장 (poster/direction.py)
                 색은 그 사진의 픽셀에서 — 종이·잉크·강조색, 대비는 여기서 맞춘다
    deck.yaml   장마다 '역할'과 내용만 (표지·숫자·목록·비교·끝) + 정한 방향과 이유
    kit.yaml    사진에서 뽑은 색 · 서체 · 사진 처리
       │
       ▼  cardpress render  (Playwright · Chromium)
    판 고르기   역할마다 판 하나 — 이미지 유무·항목 수·앞 장과 겹침을 보고
    찍기        판 HTML → 1080×1350 이미지
    검사        글 넘침 · 본문 20px 미만 · 글자/바탕 대비 4.5:1 미만 → report.json
       │
       ▼
    out/corners/<코너>/out/<코너>/NN.jpg · _board.jpg · _feed.jpg
       │
       ▼  (사람이 고른 것만) publish.cli approve-collection → 발행 큐

숫자는 '지금 모집중' 으로만 센다. '이번 주 새로 열린' 은 이 DB 가 수집을 거른 기간이 있으면 부풀려진다.
"""
from __future__ import annotations

import collections
import copy
import os
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

import yaml

from . import direction

LAB_DIR = Path(__file__).resolve().parent.parent
OUT = LAB_DIR / "out" / "corners"
HANDLE = "@devjobseeker"

_ACTIVE = """
    SELECT j.id, c.display_name AS co, c.logo_url, j.title, j.deadline_on, j.always_open, f.roles, f.career_bucket,
           f.company_size, f.stacks
      FROM job j
      JOIN company c ON c.id = j.company_id
      JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
      LEFT JOIN job_dup d ON d.job_id = j.id
      JOIN job_facet f ON f.job_id = j.id
     WHERE d.canonical_id IS NULL OR d.canonical_id = j.id
"""

#: 코너마다 고정인 것 — 내용 태그(사진을 고르는 말)와 따르는 트렌드 규칙(research/ig_trends_*.json 의 키)
CORNERS = {
    "deadline": {"tags": ["마감", "시간", "한 주"], "trend": ["weekly-corner", "real-photo"], "shape": {"margin": 72, "rule": 3}},
    "numbers": {"tags": ["숫자", "흐름", "길"], "trend": ["weekly-corner", "question-title", "real-photo"], "shape": {"margin": 76, "rule": 2}},
    "board": {"tags": ["직군", "순위", "가장 많은"], "trend": ["weekly-corner", "one-object"], "shape": {"margin": 72, "rule": 3}},
}
END_TAGS = ["끝", "저장", "다음 주"]


def _rows() -> list[dict]:
    import psycopg
    from psycopg.rows import dict_row
    dsn = os.environ.get("JOBSEEKER_DSN", "postgresql://jobseeker:jobseeker@127.0.0.1:5433/jobseeker")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(_ACTIVE).fetchall()


def _co(name: str) -> str:
    return re.sub(r"\(주\)|㈜|주식회사|\(유\)", "", name).strip()


def _short(title: str, n: int = 30) -> str:
    t = re.sub(r"\s+", " ", re.sub(r"^\[[^\]]{1,24}\]\s*", "", title)).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _image(dest: Path, d: dict) -> dict:
    """방향이 고른 사진을 코너 폴더로 옮기고 원고의 image 칸을 만든다."""
    (dest / "photos").mkdir(parents=True, exist_ok=True)
    shutil.copy(d["photo"]["path"], dest / "photos" / d["photo"]["file"])
    return {"src": d["photo"]["src"], "credit": d["photo"]["credit"], "focus": d["photo"]["focus"]}


def _knobs(corner: str) -> dict:
    """디자인 에이전트의 교훈 손잡이(design_lesson.apply, agent/db.py pick_knobs) — 판정이 쌓이면 결과가 바뀐다.
    DB 에 못 붙으면 손잡이 없이(교훈 없이) 간다."""
    try:
        import sys
        sys.path.insert(0, str(LAB_DIR))
        from agent import db as agent_db
        return agent_db.knobs(corner)
    except Exception as e:  # noqa: BLE001
        print(f"[corners] 교훈을 못 읽었다 — 원고 그대로: {e}")
        return {"layout": {}, "kit": {}, "copy": {}, "photo_tags": [], "lessons": [], "always": [], "trying": None}


def _prepare(key: str, today: date) -> tuple[Path, dict, dict]:
    c = CORNERS[key]
    k = _knobs(key)
    d = direction.decide(key, c["tags"] + k["photo_tags"], c["trend"], today)
    d["knobs"] = k
    end = direction.decide(key + "-end", END_TAGS, [], today, exclude={d["photo"]["file"]})
    dest = OUT / key
    dest.mkdir(parents=True, exist_ok=True)
    kit = copy.deepcopy(k["kit"])                               # 교훈이 이긴다 — 기본값은 빈 자리만 채운다
    from agent.db import _merge
    _merge(kit, {"name": key, "fonts": {"display": "sans", "body": "sans"}, "colors": d["palette"],
                 "image": {"treat": "photo", "scrim": 0.6}, "shape": c["shape"]})
    (dest / "kit.yaml").write_text(yaml.safe_dump(kit, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return dest, d, end


def _apply_lessons(k: dict, deck: dict) -> list[int]:
    """판(layout)과 문구(copy) 손잡이를 원고에 건다. 시안에 묶을 교훈 — 결과를 실제로 바꾼 것만(always 제외)."""
    seen = set()
    for sl in deck["slides"]:
        if sl["role"] in k["layout"]:
            sl["layout"] = k["layout"][sl["role"]]
        if sl["role"] in k["copy"] and sl["role"] not in seen:   # 그 역할의 첫 장만
            sl.update(k["copy"][sl["role"]])
        seen.add(sl["role"])
    return list(k["lessons"])


def _write(dest: Path, deck: dict, d: dict, end: dict) -> Path:
    k = d.pop("knobs")
    lesson_ids = _apply_lessons(k, deck)
    deck["direction"] = {k_: v for k_, v in d.items() if k_ != "photo"} | {
        "lessons": lesson_ids, "always": k["always"], "trying": k["trying"]} | {
        "photo": {k: v for k, v in d["photo"].items() if k != "path"},
        "end_photo": {k: v for k, v in end["photo"].items() if k != "path"}}
    p = dest / "deck.yaml"
    p.write_text(yaml.safe_dump(deck, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


#: 인스타 캐러셀은 한 게시물에 20장까지 — 표지·끝을 빼면 목록은 18장
MAX_SLIDES = 20
LOGOS = LAB_DIR.parent / "jd-viewer" / "public"
WEEKDAY = "월화수목금토일"


def _logo(dest: Path, logo_url: str | None) -> str | None:
    """우리 서버가 내주는 /logos/c/<해시>.png 만 쓴다(바깥 주소는 쓰지 않는다 — fix(security) 커밋과 같은 규칙)."""
    if not logo_url or not logo_url.startswith("/logos/"):
        return None
    src = (LOGOS / logo_url.lstrip("/")).resolve()
    if not src.is_file():
        return None
    (dest / "logos").mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest / "logos" / src.name)
    return f"logos/{src.name}"


def deadline(rows: list[dict], today: date) -> Path:
    """이번 주에 닫히는 공고를 **전부** 마감 순서대로. 같은 날 안에서는 큰 회사부터."""
    dest, d, end = _prepare("deadline", today)
    size_rank = {"대기업": 0, "중견기업": 1}
    soon = sorted((j for j in rows if j["deadline_on"] and 0 <= (j["deadline_on"] - today).days <= 7),
                  key=lambda j: (j["deadline_on"], size_rank.get(j["company_size"], 2), _co(j["co"]), j["title"]))
    entry = sum(1 for j in soon if j["career_bucket"] == "신입/무관")
    pages = MAX_SLIDES - 2
    per = max(16, -(-len(soon) // pages))                       # 올림 — 18장에 다 들어가게
    shown = soon[:pages * per]
    items = []
    for j in shown:
        dd = (j["deadline_on"] - today).days
        items.append({"label": _co(j["co"]), "meta": _short(j["title"], 34) + (" · 신입 가능" if j["career_bucket"] == "신입/무관" else ""),
                      "value": f"{j['deadline_on']:%m.%d}({WEEKDAY[j['deadline_on'].weekday()]})" + (" 오늘" if dd == 0 else ""),
                      "group": j["deadline_on"].isoformat(), "logo": _logo(dest, j.get("logo_url"))})
    moment = d["season"]["moments"][0]
    slides = [{"role": "cover", "layout": "poster", "kicker": f"{moment} · {today:%m.%d} — {today + timedelta(days=7):%m.%d}",
               "title": "이번 주에\n닫히는 개발 공고", "number": f"{len(soon):,}", "unit": "건",
               "sub": f"넘기면 {len(shown):,}건 전부, 마감 순서대로 · 신입도 넣을 수 있는 곳 *{entry:,}건*",
               "image": _image(dest, d)}]
    for k in range(0, len(items), per):
        chunk = items[k:k + per]
        first, last = chunk[0]["value"].split(" ")[0], chunk[-1]["value"].split(" ")[0]
        slides.append({"role": "list", "layout": "dense", "kicker": f"{k + 1}–{k + len(chunk)} / {len(soon)}",
                       "title": f"{first} 마감" if first == last else f"{first} — {last} 마감", "items": chunk})
    if len(shown) < len(soon):
        slides[-1]["more"] = f"외 {len(soon) - len(shown):,}건은 프로필 링크에서"
    slides.append({"role": "end", "layout": "cta", "title": "잎 지기 전에\n저장해 두세요", "image": _image(dest, end),
                   "lines": ["이번 주에 지원할 친구에게 보내 주세요", "매주 월요일, 그 주에 닫히는 공고를 전부 모읍니다"]})
    return _write(dest, {
        "title": "이번 주 마감", "series": "[이번 주 마감]", "handle": HANDLE, "size": "portrait",
        "source": f"{today:%Y.%m.%d} 기준 모집중 개발 공고 · 마감일을 적은 공고만 · 로고는 채용 사이트가 올린 것",
        "slides": slides}, d, end)


def numbers(rows: list[dict], today: date, vol: int = 1) -> Path:
    dest, d, end = _prepare("numbers", today)
    n = len(rows)
    roles = collections.Counter(r for j in rows for r in j["roles"] if r != "기타").most_common(5)
    stacks = collections.Counter(s for j in rows for s in set(j["stacks"])).most_common(6)
    entry = sum(1 for j in rows if j["career_bucket"] == "신입/무관")
    always = sum(1 for j in rows if j["always_open"] or not j["deadline_on"])
    return _write(dest, {
        "title": "개발 채용 숫자", "series": "[개발 채용 숫자]", "handle": HANDLE, "size": "portrait",
        "source": f"{today:%Y.%m.%d} 기준 모집중 개발 공고 {n:,}건 · 사이트 간 중복 제외",
        "slides": [
            # 질문형 표지 — 답은 다음 장(트렌드 question-title)
            {"role": "cover", "layout": "issue", "kicker": f"{d['season']['name']}, {d['season']['moments'][0]}",
             "number": f"VOL.{vol:02d}", "title": "지금 개발자를 가장\n많이 찾는 *직군*은?",
             "sub": f"모집중 개발 공고 {n:,}건을 셌습니다", "image": _image(dest, d)},
            {"role": "stat", "layout": "bars", "kicker": "정답", "title": f"*{roles[0][0]}*",
             "sub": "직군별 모집중 공고 — 한 공고가 여러 직군에 걸칠 수 있다",
             "items": [{"label": k, "value": f"{v:,}"} for k, v in roles]},
            {"role": "list", "layout": "ranked", "kicker": "기술", "title": "공고에 가장 많이 적힌 기술",
             "items": [{"label": k, "value": f"{v:,}", "meta": f"공고 {round(100 * v / n)}%"} for k, v in stacks]},
            {"role": "compare", "layout": "sidebyside", "kicker": "경력", "title": "신입이 넣을 수 있는 공고는?",
             "a": {"name": "신입 가능", "value": f"{entry:,}", "unit": "건", "lines": [f"전체의 {round(100 * entry / n)}%"]},
             "b": {"name": "경력만", "value": f"{n - entry:,}", "unit": "건", "lines": [f"전체의 {round(100 * (n - entry) / n)}%"]}},
            {"role": "stat", "layout": "giant", "kicker": "마감", "title": "마감일을 안 적은 공고는?",
             "items": [{"value": f"{round(100 * always / n)}", "unit": "%", "label": "상시·수시 채용 — 마감일 없음"},
                       {"value": f"{n - always:,}", "unit": "건", "label": "마감일을 적은 공고"}]},
            {"role": "end", "layout": "cta", "title": "다음 호에서\n또 셉니다", "image": _image(dest, end),
             "lines": ["저장해 두고 지난 호와 비교해 보세요", "궁금한 숫자를 댓글로 남겨 주세요 — 다음 호에 셉니다"]},
        ]}, d, end)


def board(rows: list[dict], today: date) -> Path:
    dest, d, end = _prepare("board", today)
    n = len(rows)
    roles = collections.Counter(r for j in rows for r in j["roles"] if r != "기타").most_common(4)
    slides = [{"role": "cover", "layout": "fullbleed", "kicker": f"{today:%Y.%m.%d} · {d['season']['name']}",
               "title": "지금 가장 짙게\n물든 직군은?", "sub": f"모집중 개발 공고 {n:,}건을 직군별로 셌습니다. 넘기면 직군마다 한 장.",
               "image": _image(dest, d)}]
    for i, (role, cnt) in enumerate(roles, 1):
        js = [j for j in rows if role in j["roles"]]
        st = collections.Counter(s for j in js for s in set(j["stacks"])).most_common(3)
        cos = collections.Counter(_co(j["co"]) for j in js).most_common(3)
        entry = sum(1 for j in js if j["career_bucket"] == "신입/무관")
        slides.append({"role": "stat", "layout": "flap", "kicker": f"{i}위", "title": role,
                       "items": [{"label": f"{role} 모집중", "value": f"{cnt:,}", "unit": "건"},
                                 {"label": "찾는 기술", "value": " · ".join(k for k, _ in st)},
                                 {"label": "많이 연 회사", "value": " · ".join(k for k, _ in cos)},
                                 {"label": "신입 가능", "value": f"{round(100 * entry / cnt)}%"}]})
    slides.append({"role": "end", "layout": "cta", "title": "내 직군은\n몇 위였나요", "image": _image(dest, end),
                   "lines": ["같은 직군 동료에게 보내 주세요", "매주 숫자판을 다시 돌립니다"]})
    return _write(dest, {"title": "지금 많이 뽑는 직군", "series": "[직군 숫자판]", "handle": HANDLE, "size": "portrait",
                         "source": f"{today:%Y.%m.%d} 기준 모집중 개발 공고 · 사이트 간 중복 제외", "slides": slides}, d, end)


def main() -> int:
    import sys
    if sys.argv[1:] == ["gallery"]:
        print(gallery())
        return 0
    today = date.today()
    rows = _rows()
    for p in (deadline(rows, today), numbers(rows, today), board(rows, today)):
        print(p)
    return 0



def gallery() -> Path:
    """찍은 장과 '왜 이렇게 됐나' 를 한 장의 HTML 로 — out/corners/index.html.

    방향(계절·내용·사진의 뜻·사진에서 뽑은 색·트렌드 규칙)은 deck.yaml 의 direction 에서 읽는다.
    """
    import html as H
    secs = []
    for key in CORNERS:
        deck = yaml.safe_load((OUT / key / "deck.yaml").read_text(encoding="utf-8"))
        d = deck["direction"]
        shots = sorted((OUT / key / "out" / key).glob("*.jpg"))
        chips = "".join(f'<span class="chip"><i style="background:{v}"></i>{k} {v}</span>' for k, v in d["palette"].items())
        trend = "".join(f'<li>{H.escape(t["rule"])} <small>— {", ".join("@" + a for a in t["from"])}</small></li>' for t in d["trend"])
        cards = "".join(f'<a href="{key}/out/{key}/{p.name}" target="_blank"><img src="{key}/out/{key}/{p.name}" loading="lazy"></a>'
                        for p in shots)
        secs.append(f"""<section><h2>{H.escape(deck['series'])}</h2>
<div class="why">
 <div><b>날짜·계절</b>{d['date']} · {d['season']['name']} — {' · '.join(d['season']['moments'])}</div>
 <div><b>내용</b>코너가 찾는 말 {' · '.join(d['content']['tags'])} → 사진과 겹친 말 {' · '.join(d['content']['matched']) or '없음'}</div>
 <div><b>사진</b><img class="th" src="{key}/{d['photo']['src']}">{H.escape(d['photo']['subject'])} — {H.escape(d['photo']['means'])}
   <small>{H.escape(d['photo']['credit'])}</small></div>
 <div><b>색</b>{chips}<small>{H.escape(d['color_why'])}</small></div>
 <div><b>트렌드</b><ul>{trend}</ul><small>{H.escape(d['trend_source'])}</small></div>
 <div><b>우선순위</b>{H.escape(d['priority'])}</div>
</div><div class="row">{cards}</div></section>""")
    page = OUT / "index.html"
    page.write_text(f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>고정 코너 — 방향과 결과</title>
<style>body{{margin:0;background:#f3f1ec;color:#1d1b17;font-family:'Malgun Gothic',sans-serif}}
header{{padding:26px 34px 8px}}h1{{margin:0;font-size:26px}}header p{{color:#6b665c;margin:6px 0 0}}
section{{padding:10px 34px 28px;border-top:1px solid #ddd8cc}}h2{{font-size:22px;margin:16px 0 10px}}
.why{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px 22px;font-size:14px;line-height:1.55;margin-bottom:14px}}
.why b{{display:block;font-size:12px;color:#8a8478;letter-spacing:.06em;margin-bottom:2px}}.why small{{display:block;color:#8a8478}}
.why ul{{margin:0;padding-left:18px}}.th{{width:84px;height:56px;object-fit:cover;float:left;margin:2px 10px 0 0;border-radius:3px}}
.chip{{display:inline-flex;align-items:center;gap:5px;margin:0 8px 4px 0;font-family:monospace;font-size:12px}}
.chip i{{width:14px;height:14px;border:1px solid #0002;display:inline-block}}
.row{{display:flex;gap:14px;overflow-x:auto;padding-bottom:8px}}.row img{{height:520px;display:block;box-shadow:0 1px 0 #0001}}a{{flex:0 0 auto}}</style></head>
<body><header><h1>@devjobseeker 고정 코너 — 이번 주 방향과 결과</h1>
<p>장마다 사진과 색은 날짜·계절 × 내용 × 회사 이미지 × 인스타 트렌드로 정했다(poster/direction.py). 맨 아래는 피드 3×3.</p></header>
{''.join(secs)}<section><h2>피드 미리보기</h2><img src="_all_feed.jpg" style="height:860px"></section></body></html>""", encoding="utf-8")
    return page


if __name__ == "__main__":
    raise SystemExit(main())
