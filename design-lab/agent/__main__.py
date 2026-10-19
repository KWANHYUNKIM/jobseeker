"""python -m agent <명령> — 디자인 에이전트. 설명은 agent/__init__.py."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import db

LAB_DIR = Path(__file__).resolve().parent.parent
RESEARCH = LAB_DIR / "research"

#: 처음 볼 출처. 'followers' 는 본 날의 표기 — 본 적 없는 곳은 비워 두고 루프가 확인한다.
SEED_SOURCES = [
    # 유튜브 — 사용자가 짚은 곳
    ("youtube", "@rollstory", "https://www.youtube.com/@rollstory", "롤스토리디자인연구소", "kr", None, "사용자 추천(2026-10-19)"),
    ("youtube", "@UXUIDesign", "https://www.youtube.com/@UXUIDesign", None, None, None, "사용자 추천(2026-10-19)"),
]


def seed() -> None:
    """출처 + 인스타 관찰 + 지금까지 사람이 내린 판정을 교훈으로. 교훈 점수는 0 에서 시작한다(점수는 사람이 매긴다)."""
    for kind, handle, url, name, region, followers, note in SEED_SOURCES:
        db.upsert_source(kind, handle, url, name=name, region=region, followers=followers, note=note)
    # 인스타 — 2026-10-19 로그인한 웹에서 직접 본 것(research/ig_trends_2026-10.json)
    trends = json.loads((RESEARCH / "ig_trends_2026-10.json").read_text(encoding="utf-8"))
    ref_of = {}
    for a in trends["accounts"]:
        sid = db.upsert_source("instagram", a["handle"], f"https://www.instagram.com/{a['handle']}/",
                               region="kr", followers=a["followers"], note=a["note"])
        ref_of[a["handle"]] = db.upsert_ref(f"https://www.instagram.com/{a['handle']}/", source_id=sid,
                                            title=f"@{a['handle']} 프로필 피드", summary=a["note"],
                                            metrics={"followers": a["followers"], "observed_at": trends["observed_at"]},
                                            collected_by="instagram-web")
    area = {"weekly-corner": "sequence", "question-title": "copy", "real-photo": "photo",
            "one-object": "layout", "color-per-post": "color"}
    for key, r in trends["rules"].items():
        db.upsert_lesson(area[key], r["rule"], origin="ref", status="active",
                         refs=[ref_of[h] for h in r["from"] if h in ref_of])
    # 사람의 판정 — 지금까지 사용자가 직접 한 말(근거는 대화 날짜). 이것이 가장 무겁다
    said = [
        ("color", "검정 바탕을 기본으로 쓰지 않는다 — 어둠은 사진이 어두울 때만",
         "2026-10-19 '너무 까매', '그냥 어둡고 끝난 거 같아'", {}),
        ("season", "디자인은 날짜·계절과 맞아야 한다 — 사진 소재와 강조색이 그 철의 것",
         "2026-10-19 '내용이 일치해야 하며 계절과도 비슷해야'", {}),
        ("photo", "사진은 그 장의 내용과 같은 말을 해야 한다 — 일반 풍경·장식 사진 금지",
         "2026-10-19 '지금 이미지랑 글자랑 너무 매칭이 안 돼'", {}),
        ("photo", "회사가 나오는 장은 그 회사의 색·대표 이미지·추구미로",
         "2026-10-19 '회사마다 컨셉이나 원하는 추구미… 그래야 색깔이 맞거든'", {}),
        ("sequence", "목록은 센 만큼 전부 싣는다 — 숫자는 372인데 12건만 보이면 안 된다",
         "2026-10-19 '372건인데 12개만 나옴'", {"always": True, "corner": "deadline", "layout": {"list": "dense"}}),
        ("layout", "AI 티 금지 — 장식 도형·수치 카드·색만 바꾼 판 금지, 대표 물건 하나를 원본 이미지로",
         "2026-09-15 '너무 AI 스럽다', 대표 물건 중심 v3 에 '훨씬 좋아졌다'", {}),
        ("layout", "카드뉴스는 잡지 형식이 좋다 — 장마다 디자인이 바뀌되 내용과 맞게",
         "2026-10-19 '잡지 형식이 좋은데…'", {}),
    ]
    for area_, rule, how, apply in said:
        db.upsert_lesson(area_, rule, how=f"근거: {how}", apply=apply, origin="verdict", status="active")
    print(f"출처 {len(db.sources())}곳 · 교훈 {len(db.lessons())}개")


def show_lessons() -> None:
    for l in db.lessons():
        a = l["apply"] or {}
        tag = "늘 건다" if a.get("always") else f"코드에 이미 있다({a['baked']})" if a.get("baked") else ("손잡이 " + json.dumps({k: v for k, v in a.items() if k != "corner"}, ensure_ascii=False)
                                                if any(a.get(e) for e in db.EFFECTS) else "글로만 — 시안에 안 걸린다")
        print(f"#{l['id']:<3} [{l['score']:+d} / {l['votes']}표 · 시안 {l['trials']}] {l['area']:<8} {l['rule']}  ({l['status']}) — {tag}")


def eval_decks(corners: list[str]) -> int:
    """지금 원고들을 표지 검사에 건다(evals/checks.py). 실패가 있으면 1 — TDD 의 RED 를 보는 명령."""
    import yaml
    sys.path.insert(0, str(LAB_DIR))
    from evals import checks
    from poster.corners import CORNERS
    bad = 0
    for c in corners or list(CORNERS):
        deck = yaml.safe_load((LAB_DIR / "out" / "corners" / c / "deck.yaml").read_text(encoding="utf-8"))
        rs = checks.run(deck)
        bad += sum(not r["ok"] for r in rs)
        print(f"{c}: {sum(r['ok'] for r in rs)}/{len(rs)}")
        for r in rs:
            print(f"   {'통과' if r['ok'] else '실패'}  {r['id']:<16} {r['detail']}  — {r['lesson']}")
    return 1 if bad else 0


def show_knobs() -> None:
    """코너마다 다음 시안에 걸릴 손잡이 — 무엇을 시험할지 미리 본다."""
    sys.path.insert(0, str(LAB_DIR))
    from poster.corners import CORNERS
    for c in CORNERS:
        k = db.knobs(c)
        print(f"{c}: 시험 #{k['trying']} · 계속 {[i for i in k['lessons'] if i != k['trying']]} · 늘 {k['always']}"
              f" · layout {k['layout']} kit {k['kit']} copy {k['copy']} photo_tags {k['photo_tags']}")


def log_round(corners: list[str]) -> Path:
    """회차 한 줄 — 루프 상태(automation/loops.py)는 커밋된 이 파일의 나이로 본다(out/ 은 git 밖이다)."""
    import datetime
    rows = [t for t in db.trials(len(corners)) if t["corner"] in corners]
    line = {"at": datetime.datetime.now().isoformat(timespec="minutes"),
            "trials": [{"id": t["id"], "corner": t["corner"], "slides": t["slides"],
                        "trying": (t["direction"] or {}).get("trying"),
                        "lessons": [l["id"] for l in (t["lessons"] or [])]} for t in rows]}
    out = RESEARCH / "design-rounds.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return out


def trial(corner: str) -> None:
    """찍은 코너를 시안으로 기록 — 그 코너를 만들 때 따른 교훈을 같이 묶는다."""
    import yaml
    base = LAB_DIR / "out" / "corners" / corner
    deck = yaml.safe_load((base / "deck.yaml").read_text(encoding="utf-8"))
    shots = sorted((base / "out" / corner).glob("*.jpg"))
    if not shots:
        raise SystemExit(f"{corner}: 아직 안 찍었다 — cardpress render 먼저")
    sys.path.insert(0, str(LAB_DIR))
    from evals import checks
    deck.setdefault("direction", {})["eval"] = checks.run(deck)          # 기계 검사 — 사람 판정 옆에 보인다
    # 결과를 실제로 바꾼 교훈만 묶는다 — 다 묶으면 판정이 모든 교훈에 똑같이 가서 무엇이 좋았는지 못 가른다
    direction = deck.get("direction") or {}
    used = direction.get("lessons") or []
    tid = db.record_trial(corner, str(base / "deck.yaml"), str(base / "out" / corner), len(shots), direction, used)
    trying = f" · 이번에 시험한 교훈 #{direction['trying']}" if direction.get("trying") else ""
    print(f"시안 #{tid} — {corner} {len(shots)}장, 교훈 {len(used)}개{trying} → 8780 /design 에서 판정")


def note(url: str, text: str, area: str | None) -> None:
    """사람이 영상·글을 보고 남기는 한 줄 — 모은 것 + (분야를 주면) 교훈 후보."""
    rid = db.upsert_ref(url, summary=text, collected_by="manual")
    if area:
        db.upsert_lesson(area, text, origin="ref", status="candidate", refs=[rid])
    print(f"기록 #{rid}")


def status() -> None:
    src = db.sources()
    print(f"출처 {len(src)}곳 — " + ", ".join(f"{s['kind']}:{s['handle']}" for s in src[:12]) + (" …" if len(src) > 12 else ""))
    ls = db.lessons()
    print(f"교훈 {len(ls)}개 — 점수 매겨진 것 {sum(1 for l in ls if l['votes'])}개")
    for t in db.trials(5):
        v = t["verdicts"] or []
        rel = {None: "안 봄", True: "올려도 됨", False: "안 됨"}[t["release"]]
        print(f"시안 #{t['id']} {t['corner']} {t['slides']}장 · 판정 {len(v)}장 · 릴리즈 {rel}")


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    sub.add_parser("lessons")
    sub.add_parser("status")
    t = sub.add_parser("trial"); t.add_argument("corner")
    r = sub.add_parser("render"); r.add_argument("corners", nargs="*")
    y = sub.add_parser("youtube"); y.add_argument("--limit", type=int, default=15)
    n = sub.add_parser("note"); n.add_argument("url"); n.add_argument("text"); n.add_argument("--area")
    k = sub.add_parser("knob", help="교훈에 손잡이를 단다 — 예: knob 12 '{\"kit\": {\"fonts\": {\"display\": \"serif\"}}}'")
    k.add_argument("lesson", type=int); k.add_argument("apply")
    sub.add_parser("knobs", help="다음 시안에 걸릴 손잡이를 코너마다 본다")
    e = sub.add_parser("eval", help="원고 표지를 자동 검사(evals/checks.py)"); e.add_argument("corners", nargs="*")
    a = ap.parse_args()
    if a.cmd == "seed":
        seed()
    elif a.cmd == "lessons":
        show_lessons()
    elif a.cmd == "status":
        status()
    elif a.cmd == "trial":
        trial(a.corner)
    elif a.cmd == "render":
        from . import render
        sys.path.insert(0, str(LAB_DIR))
        from poster.corners import CORNERS
        done = render.run(a.corners or list(CORNERS), after=trial)
        if done:
            from poster.corners import gallery
            print(gallery())
            print(log_round(done))
        return 0 if len(done) == len(a.corners or CORNERS) else 1
    elif a.cmd == "note":
        note(a.url, a.text, a.area)
    elif a.cmd == "knob":
        apply = json.loads(a.apply)
        if not any(apply.get(e) for e in db.EFFECTS) and not apply.get("baked"):
            raise SystemExit(f"손잡이가 없다 — {db.EFFECTS} 중 하나는 있어야 시안에 걸린다")
        db.set_apply(a.lesson, apply)
        print(f"교훈 #{a.lesson} 손잡이 → {json.dumps(apply, ensure_ascii=False)}")
    elif a.cmd == "knobs":
        show_knobs()
    elif a.cmd == "eval":
        return eval_decks(a.corners)
    elif a.cmd == "youtube":
        from . import youtube
        for s in db.sources("youtube"):
            try:
                print(f"{s['handle']}: {youtube.collect(s['handle'], s['id'], a.limit)}편")
            except Exception as e:
                print(f"{s['handle']}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
