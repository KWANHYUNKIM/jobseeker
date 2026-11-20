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
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE / "series.json"
LEC_NO = re.compile(r"\bLecture\s*(\d+)", re.I)


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
    nums = [int(m.group(1)) if (m := LEC_NO.search(v["title"])) else None for v in vids]
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
    entry["playlist_title"] = title
    entry["lectures"] = [{"no": i + 1, **v} for i, v in enumerate(order(vids))]
    return entry


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
    sub.add_parser("refresh")
    sub.add_parser("list")
    args = ap.parse_args()
    items = load()
    if args.cmd == "add":
        items = [s for s in items if s["key"] != args.key]
        e = build({"key": args.key, "playlist": args.playlist, "match": args.match, "title": args.title,
                   "school": args.school, "code": args.code, "term": args.term})
        e["title"] = e["title"] or e["playlist_title"]
        items.append(e)
        save(items)
        print(f"{e['key']}: {len(e['lectures'])}강 — {e['title']}")
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
