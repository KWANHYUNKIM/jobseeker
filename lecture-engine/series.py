"""과목(시리즈) 등록부 — 공식 재생목록을 '1강부터 N강까지' 순서로 굳힌다.

    python lecture-engine/series.py add <재생목록 id> <키> [--match V6] [--title "..."]
    python lecture-engine/series.py refresh          # 등록된 과목의 재생목록을 다시 읽어 새 강의를 덧붙인다
    python lecture-engine/series.py list

결과는 `lecture-engine/series.json`(커밋한다). validate.py 가 이걸 읽어 index.json 에 과목별 차례를
싣고(아직 노트가 없는 강의도 '준비 중'으로), `--gaps` 는 앞 과목의 빈 강의부터 일감으로 낸다.
순서: 제목의 'Lecture N' 번호 → 없으면 재생목록 순서(최신이 위면 뒤집는다).
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE / "series.json"
# 'Lecture 3' 만 보던 것을 국내 재생목록 표기까지 — '[포토샵 기초 강좌15]' '8강' '[1일차' 'Chapter 50' '#4' 'Lec 02'.
# 국내 목록은 최신이 위인 경우가 많아서 번호를 읽어야 1강부터 줄 세울 수 있다.
LEC_NO = re.compile(r"(?:\bLecture|\bLec|\bUnit|\bChapter|\bLesson|\bClass|\bTutorial|\bPart|\bDay|강좌|강의|입문|#)\s*(\d{1,3})(?!\d)"
                    r"|(?<!\d)(\d{1,3})\s*(?:강|편|일차|탄)", re.I)


def lec_no(title: str) -> int | None:
    m = LEC_NO.search(title)
    return int(m.group(1) or m.group(2)) if m else None


def load() -> list[dict]:
    return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else []


def save(items: list[dict]) -> None:
    FILE.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def playlist(pl: str) -> tuple[str, list[dict]]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--no-warnings", "--flat-playlist",
                        "--dump-single-json", f"https://www.youtube.com/playlist?list={pl}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if r.returncode != 0:
        sys.exit(r.stderr[-400:])
    raw = json.loads(r.stdout)
    vids = [{"id": e["id"], "title": e.get("title") or "", "duration": int(e.get("duration") or 0)}
            for e in raw.get("entries") or [] if e.get("id") and e.get("title") and e.get("title") not in ("[Private video]", "[Deleted video]")]
    return raw.get("title") or pl, vids


def order(vids: list[dict]) -> list[dict]:
    nums = [lec_no(v["title"]) for v in vids]
    known = [n for n in nums if n is not None]
    if len(known) >= 2 and known[0] > known[-1]:  # 최신이 위 — 뒤집어 오래된 것부터
        vids, nums = vids[::-1], nums[::-1]
    # 번호가 있는 강의는 번호순, 번호 없는 특강은 재생목록에서 놓인 자리 근처에 남긴다(안정 정렬).
    keyed, last = [], 0.0
    for i, (v, n) in enumerate(zip(vids, nums)):
        k = float(n) if n is not None else last + 0.001 * (i + 1)
        last = k if n is not None else last
        keyed.append((k, i, v))
    return [v for _, _, v in sorted(keyed)]


def build(entry: dict) -> dict:
    title, vids = playlist(entry["playlist"])
    if entry.get("match"):
        vids = [v for v in vids if re.search(entry["match"], v["title"])]
    if entry.get("max"):                      # 100편 넘는 채널 목록(StatQuest 등)은 앞 N편만 — 입문 부분
        vids = vids[: entry["max"]]
    entry["playlist_title"] = title
    # keep_order: 번호 표기가 섞여 읽으면 오히려 뒤엉키는 목록(웹디자인 입문의 '#1' 과 'Tutorial 2-3')은 재생목록 순서 그대로
    entry["lectures"] = [{"no": i + 1, **v} for i, v in enumerate(vids if entry.get("keep_order") else order(vids))]
    return entry


def video_meta(vid: str) -> dict:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--no-warnings", "--skip-download",
                        "--dump-single-json", f"https://www.youtube.com/watch?v={vid}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}


def quality(entry: dict) -> None:
    """품질 근거 — 1강과 마지막 강의 지표. 1강 대비 마지막 강 조회수(끝까지 본 비율의 대리값)가 낮으면
    사람들이 중간에 떠난 목록이다. 숫자는 받은 날짜와 함께 남긴다(조회수는 늘어난다)."""
    lec = entry.get("lectures") or []
    if not lec:
        return
    first, last = video_meta(lec[0]["id"]), video_meta(lec[-1]["id"]) if len(lec) > 1 else {}
    if not first:
        return
    views, likes = first.get("view_count") or 0, first.get("like_count") or 0
    up = first.get("upload_date") or ""
    stats = {
        "checked": datetime.now().strftime("%Y-%m-%d"),
        "channel": first.get("channel"),
        "channel_followers": first.get("channel_follower_count"),
        "first_views": views,
        "first_likes": likes,
        "like_per_1k_views": round(likes * 1000 / views, 1) if views else None,
        "first_uploaded": f"{up[:4]}-{up[4:6]}-{up[6:]}" if up else None,
        "last_views": last.get("view_count"),
        "stay_ratio": round(last["view_count"] / views, 3) if last.get("view_count") and views else None,
        "subtitles": sorted(set((first.get("subtitles") or {}).keys()) & {"ko", "en"}),
        "auto_subtitles": "ko" in (first.get("automatic_captions") or {}),
    }
    entry.setdefault("quality", {})["stats"] = stats


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("playlist")
    a.add_argument("key")
    a.add_argument("--match", help="제목 정규식으로 거른다(CS25 처럼 여러 학기가 한 목록에 섞인 경우)")
    a.add_argument("--title")
    a.add_argument("--school", default="Stanford")
    a.add_argument("--code")
    a.add_argument("--term")
    a.add_argument("--track", default="ai", help="paths.json 의 학습 트랙(ai·coding-test·backend·frontend·design·detail-page·toeic)")
    a.add_argument("--max", type=int, help="재생목록 앞 N편만")
    # 무엇을 배우는 과목인지 — 화면이 '백엔드' 하나로 뭉뚱그리지 않고 기술·내용으로 가른다(2026-11-23 사용자 요청).
    a.add_argument("--stack", required=True, help="쓰는 기술 — 'Java · Spring Boot', 'Python · Django', '언어 무관'")
    a.add_argument("--subject", required=True, help="내용 갈래 — '네트워크·HTTP', '웹 프레임워크', '데이터베이스'")
    a.add_argument("--why", required=True, help="이 재생목록을 고른 이유 한 줄(PROMPT.md 의 품질 기준으로)")
    q = sub.add_parser("quality", help="유튜브 지표(구독자·조회수·좋아요·올린 해)를 받아 quality.stats 에 적는다")
    q.add_argument("keys", nargs="*", help="과목 키(없으면 stats 없는 과목 전부)")
    sub.add_parser("refresh")
    sub.add_parser("list")
    args = ap.parse_args()
    items = load()
    if args.cmd == "add":
        items = [s for s in items if s["key"] != args.key]
        e = build({"key": args.key, "playlist": args.playlist, "match": args.match, "title": args.title,
                   "school": args.school, "code": args.code, "term": args.term, "track": args.track, "max": args.max,
                   "stack": args.stack, "subject": args.subject, "quality": {"why": args.why}})
        e["title"] = e["title"] or e["playlist_title"]
        items.append(e)
        save(items)
        print(f"{e['key']}: {len(e['lectures'])}강 — {e['title']}")
        quality(e)
        save(items)
        print(f"  품질 {e['quality'].get('stats')}")
    elif args.cmd == "quality":
        for e in items:
            if (args.keys and e["key"] not in args.keys) or (not args.keys and (e.get("quality") or {}).get("stats")):
                continue
            quality(e)
            save(items)  # 한 과목씩 — 중간에 끊겨도 받은 만큼 남는다
            print(f"{e['key']:<20} {e['quality'].get('stats')}")
    elif args.cmd == "refresh":
        for e in items:
            before = len(e["lectures"])
            build(e)
            print(f"{e['key']}: {before} → {len(e['lectures'])}강")
        save(items)
    else:
        for e in items:
            print(f"{e['key']:<14} {len(e['lectures']):>3}강  {e['title']}")


if __name__ == "__main__":
    main()
