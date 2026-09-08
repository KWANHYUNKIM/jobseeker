#!/usr/bin/env python3
"""책 데이터 검사 + 차례 상태 동기화.

절을 하나 쓸 때마다 손으로 toc.json 의 status 와 index.json 의 written 을 고치면
반드시 어긋난다. 어긋나면 화면이 조용히 망가진다 — 차례에는 '예정' 인데 본문은 있고,
'다음' 버튼이 빈 페이지로 간다. 그래서 **파일 목록을 진실로 삼아** 매번 다시 계산한다.

같이 검사하는 것:
  - 모든 JSON 이 파싱되는가
  - 차례에 없는 본문 파일 / 본문 없는 done 절이 있는가
  - ASCII 그림이 규칙을 지키는가 (아래)

그림 규칙: **상자 테두리 왼쪽에 한글을 두지 않는다.**
한글 글리프는 등폭 폰트에서도 정확히 2칸이 아니라서, 테두리 앞에 한글이 있으면
그 줄만 밀려 그림이 깨진다. 한글은 줄 끝(테두리 바깥)에만 둔다.
마크다운 표식(**)도 figure 안에서는 글자 그대로 나오므로 금지한다.

    python3 jd-viewer/scripts/book_check.py           # 검사 + 동기화
    python3 jd-viewer/scripts/book_check.py --check   # 검사만 (고치지 않음)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BOOK = Path(__file__).resolve().parent.parent / "public" / "book"
BOX = set("┌┐└┘├┤┬┴┼─│╔╗╚╝║═")
FIX = "--check" not in sys.argv


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def dump(p: Path, data: dict) -> None:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_figures(pages_dir: Path) -> list[str]:
    """상자 테두리 앞에 한글이 오는 줄과, 그림 안의 마크다운 표식을 찾는다."""
    bad: list[str] = []
    for f in sorted(pages_dir.glob("*.json")):
        for b in load(f).get("blocks", []):
            if b.get("type") != "figure":
                continue
            cap = b.get("caption", "(무제)")
            if "**" in b["ascii"]:
                bad.append(f"{f.name} · {cap} · 그림 안에 ** 가 있다")
            for ln, line in enumerate(b["ascii"].split("\n"), 1):
                seen_ko = False
                for ch in line:
                    if "가" <= ch <= "힣":
                        seen_ko = True
                    elif ch in BOX and seen_ko:
                        bad.append(f"{f.name} · {cap} · {ln}행: 테두리 왼쪽에 한글")
                        break
    return bad


def main() -> int:
    problems: list[str] = []
    shelf_path = BOOK / "index.json"
    shelf = load(shelf_path)

    for book in shelf["books"]:
        bid = book["id"]
        toc_path = BOOK / bid / "toc.json"
        pages_dir = BOOK / bid / "pages"
        toc = load(toc_path)

        have = {f.stem for f in pages_dir.glob("*.json")}
        sections = [s for c in toc["chapters"] for s in c["sections"]]
        ids = {s["id"] for s in sections}

        orphan = have - ids
        if orphan:
            problems.append(f"{bid}: 차례에 없는 본문 파일 {sorted(orphan)}")

        # 파일이 진실이다. 있으면 done, 없으면 todo. (draft 는 손으로 유지)
        changed = 0
        for s in sections:
            want = "done" if s["id"] in have else "todo"
            if s.get("status") not in (want, "draft"):
                if FIX:
                    s["status"] = want
                    changed += 1
                else:
                    problems.append(f"{bid}: {s['no']} 상태가 {s.get('status')} 인데 파일은 {'있음' if s['id'] in have else '없음'}")

        written = sum(1 for s in sections if s["status"] != "todo")
        if book.get("written") != written or book.get("sections") != len(sections):
            if FIX:
                book["written"] = written
                book["sections"] = len(sections)
                book["chapters"] = len(toc["chapters"])
                changed += 1
            else:
                problems.append(f"{bid}: 서가의 written/sections 가 실제와 다르다")

        if FIX and changed:
            dump(toc_path, toc)
            dump(shelf_path, shelf)

        problems += check_figures(pages_dir)

        done = [s["no"] for s in sections if s["status"] == "done"]
        print(f"[{bid}] {len(toc['chapters'])}장 {len(sections)}절 · 본문 {written}")
        for c in toc["chapters"]:
            d = [s["no"] for s in c["sections"] if s["status"] == "done"]
            mark = "✓" if len(d) == len(c["sections"]) else " "
            print(f"  {mark} {c['no']:>2}장 {c['title'][:26]:28s} {len(d)}/{len(c['sections'])}")
        del done

    if problems:
        print("\n문제:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\n이상 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
