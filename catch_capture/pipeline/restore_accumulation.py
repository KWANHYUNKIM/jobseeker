#!/usr/bin/env python3
"""고정 누적 폴더의 jobs.json 을 되살린다.

**무엇을 푸는가.** `screenshots/{site}_{keyword}/jobs.json` 은 이름대로라면 누적이어야
하는데(`jobs_common.load_existing_jobs` 가 이전 것을 읽어 합치도록 설계돼 있다) 실제로는
한 사이클치만 남는다. `auto_crawl.prune_snapshots` 의 주석이 그 사실을 이미 적어 뒀다 —
"크롤러가 계속 덮어쓰는 현재 상태".

그 결과 `aggregate` 가 세는 건수가 한 사이클치(~900건)로 떨어지고,
`refresh-data.sh` 의 급감 가드(기존 대비 50% 미만이면 중단)가 덮어쓰기를 막는다.
가드는 제 일을 한 것이다 — 누적 9천여 건을 날릴 뻔한 것을 세웠다. 다만 그 상태로
멈춰 있으면 파생 데이터(재공고·캘린더·기술스택·트렌드…)가 전부 얼어붙는다.

**어디서 되살리나.** `jd-viewer/public/all_jobs_enriched.json` 이 마지막으로 성공한
집계 결과(10,328건)를 들고 있고 레코드마다 `site` 가 붙어 있다. 이것을 사이트별로
갈라 고정 폴더의 jobs.json 에 **오늘 크롤분과 합쳐** 되돌린다.

**왜 합치나(덮어쓰지 않나).** 오늘 크롤분이 최신이다. 과거분으로 덮으면 오늘 새로
올라온 공고가 사라진다. 그래서 오늘 것을 우선하고 과거분을 뒤에 채운다.

기본은 실측만 하고 아무것도 쓰지 않는다(`--dry-run` 이 기본).
실제로 쓰려면 `--apply` 를 준다. 쓰기 전 기존 jobs.json 을 반드시 백업한다.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCREENS = ROOT / "catch_capture" / "screenshots"
ENRICHED = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
PIN_KEYWORD = "개발자"

# aggregate.SITES 와 같은 목록이어야 한다. 여기서 다시 적는 대신 읽어 온다.
sys.path.insert(0, str(ROOT / "catch_capture"))


def _sites() -> list[str]:
    try:
        from pipeline.aggregate import SITES  # type: ignore
        return list(SITES)
    except Exception:
        return ["wanted", "jumpit", "jobkorea", "saramin", "dev"]


def _norm(s: object) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _key(j: dict) -> tuple:
    """같은 공고인지 판정하는 키. URL 이 있으면 그것, 없으면 (회사, 제목)."""
    url = _norm(j.get("url"))
    if url:
        return ("u", url)
    return ("ct", _norm(j.get("company")), _norm(j.get("title")))


def load_json(p: Path) -> list:
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception as e:
        print(f"  ! {p} 읽기 실패: {e}")
        return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다(기본은 실측만)")
    ap.add_argument("--keyword", default=PIN_KEYWORD)
    args = ap.parse_args()

    if not ENRICHED.exists():
        print(f"✗ {ENRICHED} 가 없다 — 되살릴 원본이 없다")
        return 1

    hist = load_json(ENRICHED)
    print(f"원본(all_jobs_enriched): {len(hist)}건")
    if not hist:
        return 1

    by_site: dict[str, list[dict]] = {}
    for j in hist:
        by_site.setdefault(str(j.get("site") or "?"), []).append(j)
    print("사이트별 원본:", dict(Counter({k: len(v) for k, v in by_site.items()})))

    # 원본 레코드가 크롤러가 쓰는 모양과 얼마나 다른지 본다. 크게 다르면
    # 되돌린 뒤 파이프라인이 다르게 동작할 수 있어 먼저 눈으로 확인해야 한다.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    total_before = total_after = 0

    for site in _sites():
        fixed = SCREENS / f"{site}_{args.keyword}"
        if not fixed.is_dir():
            print(f"  [{site}] 고정 폴더 없음 — 건너뜀 ({fixed.name})")
            continue

        cur = load_json(fixed / "jobs.json")
        old = by_site.get(site, [])
        total_before += len(cur)

        if cur and old:
            ck = {tuple(_key(j)) for j in cur}
            sample_cur = set(cur[0].keys())
            sample_old = set(old[0].keys())
            only_old = sorted(sample_old - sample_cur)[:8]
            only_cur = sorted(sample_cur - sample_old)[:8]
        else:
            ck, only_old, only_cur = set(), [], []

        # 오늘 것을 앞에, 과거 것 중 겹치지 않는 것만 뒤에.
        merged = list(cur)
        added = 0
        for j in old:
            if tuple(_key(j)) in ck:
                continue
            ck.add(tuple(_key(j)))
            merged.append(j)
            added += 1
        total_after += len(merged)

        print(f"  [{site}] 현재 {len(cur)} + 복원 {added} → {len(merged)}건")
        if only_old or only_cur:
            print(f"      키 차이 — 원본에만: {only_old} / 현재에만: {only_cur}")

        if args.apply:
            jf = fixed / "jobs.json"
            if jf.exists():
                bak = fixed / f"jobs.json.bak-{stamp}"
                shutil.copy2(jf, bak)
                print(f"      백업 → {bak.name}")
            tmp = fixed / "jobs.json.tmp"
            tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(jf)
            print("      기록 완료")

    print(f"\n합계: {total_before}건 → {total_after}건")
    if not args.apply:
        print("실측만 했다. 실제로 쓰려면 --apply 를 준다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
