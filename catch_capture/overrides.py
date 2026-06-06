"""주요업무/자격요건/우대사항을 사람이 직접 보정하는 overrides.json 관리 도구.

aggregate 가 overrides.json 의 (site:pid) 항목을 자동추출 값 위에 덮어쓴다.
→ 사람이 손으로 고친 값은 크롤을 다시 돌려도 유지된다(자동 추출에 안 먹힘).

overrides.json 구조:
    {
      "jobkorea:12345": {
        "_context": {"company": "...", "title": "...", "url": "..."},
        "main_tasks": "직접 정리한 주요 업무...",
        "qualifications": "자격요건...",
        "preferences": "우대사항..."
      }
    }
  - _context 는 사람이 보기 위한 참고용(aggregate 가 무시).
  - main_tasks/qualifications/preferences/tech_stack 중 비어있지 않은 값만 적용된다.

사용법:
    python overrides.py seed [keyword]   # 추출이 빈약한 공고의 편집용 stub 추가(기존 편집 보존)
    python overrides.py list             # 현재 보정 항목 요약
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).parent.resolve()
SCREENS = BASE / "screenshots"
OVR_PATH = BASE / "overrides.json"
EDIT_FIELDS = ("main_tasks", "qualifications", "preferences")


def _load() -> dict:
    if OVR_PATH.exists():
        try:
            return json.loads(OVR_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[!] overrides.json 파싱 실패: {e}", file=sys.stderr)
    return {}


def _save(d: dict) -> None:
    OVR_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_all(keyword: str) -> Path | None:
    cands = sorted(
        p for p in SCREENS.glob(f"all_{keyword}_*")
        if p.is_dir() and not p.name.endswith("_latest")
    )
    return cands[-1] if cands else None


def _empty(v) -> bool:
    return not (v and str(v).strip())


def seed(keyword: str) -> None:
    src = _latest_all(keyword)
    if not src:
        print(f"[!] all_{keyword}_* 폴더 없음", file=sys.stderr)
        return
    jobs = json.loads((src / "all_jobs.json").read_text(encoding="utf-8"))
    ovr = _load()
    added = 0
    for j in jobs:
        # 세 섹션 중 하나라도 비어있으면 편집 대상
        if not any(_empty(j.get(f)) for f in EDIT_FIELDS):
            continue
        key = f"{j.get('site')}:{j.get('pid')}"
        if key in ovr:  # 기존 편집 보존
            continue
        ovr[key] = {
            "_context": {
                "company": j.get("company", ""),
                "title": j.get("title", ""),
                "url": j.get("url", ""),
                # 참고용 현재 자동추출 값 (aggregate 는 _context 를 무시 → 얼어붙지 않음)
                "auto_main_tasks": j.get("main_tasks", "") or "",
                "auto_qualifications": j.get("qualifications", "") or "",
                "auto_preferences": j.get("preferences", "") or "",
            },
            # 아래 칸을 채우면 그 값만 자동추출 위에 덮어쓴다. 비워두면 자동값 유지.
            "main_tasks": "",
            "qualifications": "",
            "preferences": "",
        }
        added += 1
    _save(ovr)
    print(f"[*] {src.name} 기준 편집용 stub {added}건 추가 (총 {len(ovr)}건)")
    print(f"[*] 편집: {OVR_PATH}")
    print("[*] 편집 후 'python auto_crawl.py once' 또는 다음 자동 사이클에 반영됩니다.")


def show_list() -> None:
    ovr = _load()
    if not ovr:
        print("(보정 항목 없음)")
        return
    filled = 0
    for key, v in ovr.items():
        ctx = v.get("_context", {})
        done = [f for f in EDIT_FIELDS if v.get(f)]
        if done:
            filled += 1
        print(f"  {key}  {ctx.get('company','')} {ctx.get('title','')[:30]}  채움={done}")
    print(f"\n총 {len(ovr)}건 (내용 채워진 항목 {filled}건)")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "seed":
        seed(sys.argv[2] if len(sys.argv) > 2 else "개발자")
    elif cmd == "list":
        show_list()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
