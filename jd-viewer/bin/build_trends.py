#!/usr/bin/env python3
"""개발 트렌드 시계열 빌더.

크롤이 날짜별 타임스탬프 폴더(screenshots/all_통합_YYYYMMDD_HHMMSS)에 스냅샷을 쌓아두므로,
날짜별 '최신 스냅샷'에서 기술 수요를 집계해 시계열(public/trends.json)을 만든다.
매 실행마다 전체 일자를 다시 집계하므로(일별 1개 파일만 읽어 가벼움) 데이터가 쌓일수록
트렌드가 자동으로 길어진다.

핵심: 크롤 커버리지가 늘면 절대 건수도 늘기 때문에, 트렌드는 '비중(%)'으로 봐야 한다.
이 빌더는 건수와 일별 총계를 함께 저장하고, 비중·급상승/급하락은 빌더와 뷰어가 계산한다.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

CATCH = Path(__file__).resolve().parent.parent.parent / "catch_capture"
SNAP_DIR = CATCH / "screenshots"
OUT = Path(__file__).resolve().parent.parent / "public" / "trends.json"

TRACK_TOP = 40            # 추적할 상위 기술 수(최신일 기준)
DATE_RE = re.compile(r"all_통합_(\d{8})_(\d{6})$")


def _latest_per_day() -> list[tuple[str, Path]]:
    """YYYYMMDD → 그날의 가장 늦은 스냅샷 폴더. (정렬된 [(YYYY-MM-DD, folder)])."""
    by_day: dict[str, tuple[str, Path]] = {}
    for p in SNAP_DIR.glob("all_통합_*"):
        if not p.is_dir():
            continue
        m = DATE_RE.search(p.name)
        if not m:
            continue
        day, hms = m.group(1), m.group(2)
        if day not in by_day or hms > by_day[day][0]:
            by_day[day] = (hms, p)
    out = []
    for day in sorted(by_day):
        iso = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        out.append((iso, by_day[day][1]))
    return out


def _count_techs(folder: Path) -> tuple[int, Counter]:
    f = folder / "all_jobs.json"
    if not f.exists():
        return 0, Counter()
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return 0, Counter()
    jobs = data if isinstance(data, list) else data.get("jobs", [])
    c = Counter()
    for j in jobs:
        seen = set()
        for t in (j.get("tech_stack") or []):
            if t and t not in seen:      # 공고당 기술 중복 카운트 방지
                c[t] += 1
                seen.add(t)
    return len(jobs), c


def main() -> None:
    days = _latest_per_day()
    if not days:
        print("[trends] 스냅샷 폴더가 없습니다.")
        return

    per_day = []
    for iso, folder in days:
        total, counts = _count_techs(folder)
        if total == 0:
            continue
        per_day.append({"date": iso, "total": total, "counts": counts})

    # 추적 기술: 최신일 기준 상위 TRACK_TOP
    latest_counts = per_day[-1]["counts"]
    tracked = [t for t, _ in latest_counts.most_common(TRACK_TOP)]

    days_out = []
    for d in per_day:
        days_out.append({
            "date": d["date"],
            "total": d["total"],
            "tech": {t: d["counts"].get(t, 0) for t in tracked},
        })

    # 급상승/급하락: 첫 유효일 ↔ 최신일 비중(%) 차이
    def pct(day, t):
        return round(100 * day["tech"].get(t, 0) / day["total"], 2) if day["total"] else 0.0

    movers = []
    if len(days_out) >= 2:
        a, b = days_out[0], days_out[-1]
        for t in tracked:
            pa, pb = pct(a, t), pct(b, t)
            movers.append({"tech": t, "from_pct": pa, "to_pct": pb, "delta": round(pb - pa, 2)})
    movers.sort(key=lambda m: m["delta"])
    up = [m for m in reversed(movers) if m["delta"] > 0][:8]
    down = [m for m in movers if m["delta"] < 0][:8]

    doc = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "span": {"from": days_out[0]["date"], "to": days_out[-1]["date"], "days": len(days_out)},
        "tracked": tracked,
        "days": days_out,
        "movers": {"up": up, "down": down},
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"[trends] {len(days_out)}일({days_out[0]['date']}~{days_out[-1]['date']}) · 추적 {len(tracked)}개 기술 → {OUT}")
    if up:
        print("  급상승:", ", ".join(f"{m['tech']}(+{m['delta']}%p)" for m in up[:5]))
    if down:
        print("  급하락:", ", ".join(f"{m['tech']}({m['delta']}%p)" for m in down[:5]))


if __name__ == "__main__":
    main()
