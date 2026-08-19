#!/usr/bin/env python3
"""개발 트렌드 시계열 빌더.

입력: catch_capture/trends_history.jsonl  (pipeline.trends 가 하루 한 줄씩 적재)
출력: jd-viewer/public/trends.json

**왜 스냅샷 폴더를 읽지 않는가.**
이 빌더는 원래 screenshots/all_통합_<날짜>_<시각>/ 을 날짜별로 훑어 시계열을 만들었다.
그런데 auto_crawl 은 매 사이클 `prune_snapshots()` 로 계열별 최신 8개만 남기고 지운다.
크롤 주기가 30분이므로 스냅샷은 약 4시간치만 살아남고, 그 위에서 만든 시계열은 늘
'하루'였다 (실제로 span.days = 1, movers 가 빈 배열이었다). 트렌드 빌더가 의존하던
히스토리를 정리 작업이 매 사이클 삭제하고 있었던 셈이다.

반면 pipeline/trends.py 는 aggregate 사이클마다 trends_history.jsonl 에 하루 한 줄을
append 해 왔고, 이 파일은 prune 대상이 아니다. 같은 크롤에서 나온 같은 집계인데
내구성만 다르다. 그래서 입력을 이쪽으로 옮긴다 — 하루치가 50일치가 된다.

덤으로 히스토리에는 뷰어가 한 번도 못 봤던 축이 들어 있다: 경력 밴드, 직군, 개념
키워드(협업·클라우드·대용량 같은 비-기술 요구). 스키마를 확장해 함께 내보낸다.

핵심 원칙은 그대로다: 크롤 커버리지가 늘면 절대 건수도 늘기 때문에 트렌드는 '비중(%)'
으로 봐야 한다. 건수와 일별 총계를 함께 저장하고, 비중과 급상승/급하락은 여기서 계산한다.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HISTORY = ROOT / "catch_capture" / "trends_history.jsonl"
OUT = ROOT / "jd-viewer" / "public" / "trends.json"

TRACK_TOP = 40      # 추적할 상위 기술 수(최신일 기준)
TOP_CONCEPTS = 24   # 함께 내보낼 개념 키워드 수
TOP_TECH_PER_ROLE = 12  # 직군별 시계열에 실을 기술 수(최신일 기준)
MOVER_WINDOW = 7    # 급상승/급하락 비교 창(일). 단일 일자 비교는 그날 크롤 편차를 그대로 먹는다.
MOVER_MIN_PCT = 0.5 # 최신 창에서 이 비중 미만인 기술은 movers 에서 뺀다(꼬리 잡음 제거)
MOVERS_N = 8


def _pairs(v) -> dict[str, int]:
    """히스토리의 집계 필드는 {name: n} 과 [[name, n], ...] 두 모양으로 쓰였다.

    적재 시점의 json 직렬화 방식이 달라 섞여 있으므로 둘 다 받아 dict 로 맞춘다.
    모양을 하나로 가정하면 오래된 줄에서 조용히 빈 집계가 나온다.
    """
    if isinstance(v, dict):
        return {str(k): int(n) for k, n in v.items()}
    if isinstance(v, list):
        out: dict[str, int] = {}
        for item in v:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                out[str(item[0])] = int(item[1])
        return out
    return {}


def _load_days() -> tuple[list[dict], str, list[str]]:
    """(일별 레코드, 채택한 keyword, 제외 사유 메모)."""
    if not HISTORY.exists():
        raise SystemExit(f"[trends] 히스토리가 없습니다: {HISTORY}")

    rows = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    # keyword 별로 크롤 범위가 다르다('개발자' 673건 vs '통합' 5349건). 비중의 분모가
    # 달라지므로 한 시계열에 섞으면 안 된다 — 줄 수가 가장 많은 keyword 하나만 쓴다.
    kw_counts = Counter(r.get("keyword") for r in rows)
    keyword = kw_counts.most_common(1)[0][0]
    dropped = [f"{k}({n}일)" for k, n in kw_counts.items() if k != keyword]

    # 같은 날짜가 여러 줄이면 마지막 것이 그날의 최종 집계다.
    by_date: dict[str, dict] = {}
    for r in rows:
        if r.get("keyword") != keyword:
            continue
        d = r.get("date")
        if d and int(r.get("total") or 0) > 0:
            by_date[d] = r

    days = [by_date[d] for d in sorted(by_date)]
    return days, keyword, dropped


def _pct(count: int, total: int) -> float:
    return round(100 * count / total, 2) if total else 0.0


def _window_pct(days_out: list[dict], tech: str, lo: int, hi: int) -> tuple[float, int]:
    """days_out[lo:hi] 구간의 '비중 평균'과 그 평균이 몇 일에서 나왔는지.

    구간 합계가 아니라 일별 비중의 평균을 쓴다. 일별 총계가 크게 다를 때
    합계 방식은 공고가 많았던 날에 사실상 가중치를 몰아준다.

    그날 상위 N 밖으로 밀려 기록이 없는 날은 건너뛴다 — 0 으로 세면 그 기술이
    실제로 사라진 것처럼 보이고, 관측 공백이 곧장 가짜 급락으로 둔갑한다.
    """
    vals = [
        _pct(d["tech"][tech], d["total"])
        for d in days_out[lo:hi]
        if tech in d["tech"] and d["total"]
    ]
    if not vals:
        return 0.0, 0
    return round(sum(vals) / len(vals), 2), len(vals)


def main() -> None:
    days, keyword, dropped = _load_days()
    if not days:
        raise SystemExit("[trends] 유효한 일자가 없습니다.")

    latest_tech = _pairs(days[-1].get("tech_overall"))
    tracked = [t for t, _ in Counter(latest_tech).most_common(TRACK_TOP)]

    latest_concepts = _pairs(days[-1].get("concepts_overall"))
    concepts_tracked = [c for c, _ in Counter(latest_concepts).most_common(TOP_CONCEPTS)]

    # 직군별 축. 히스토리의 roles = {직군: {count, bands, tech, concepts}} 로, 전체 집계만
    # 보면 안 보이는 것을 잡는다 — 예를 들어 Kubernetes 전체 비중이 내려가도 그게 수요
    # 감소인지 백엔드 공고 비중 감소인지는 직군을 갈라야 구분된다.
    latest_roles = days[-1].get("roles") or {}
    roles_tracked = sorted(
        latest_roles.keys(),
        key=lambda r: -int((latest_roles[r] or {}).get("count") or 0),
    )
    role_tech_tracked: dict[str, list[str]] = {}
    for r in roles_tracked:
        tech = _pairs((latest_roles.get(r) or {}).get("tech"))
        role_tech_tracked[r] = [t for t, _ in Counter(tech).most_common(TOP_TECH_PER_ROLE)]

    days_out: list[dict] = []
    for r in days:
        total = int(r.get("total") or 0)
        tech = _pairs(r.get("tech_overall"))
        concepts = _pairs(r.get("concepts_overall"))
        bands = _pairs(r.get("bands"))
        roles = _pairs(r.get("by_role"))
        # 부재를 0으로 채우면 안 된다. 히스토리는 그날 상위 N개만 저장하므로, 어떤 기술이
        # 그날 목록에 없다는 것은 "0건"이 아니라 "그날 컷오프 미만"이라는 뜻이다.
        # 0으로 메우면 Android 처럼 6%대에서 꾸준한 기술이 며칠만 0.0 으로 찍히고,
        # 그 구멍이 그대로 급상승/급하락 1위로 올라온다(실제로 +2.81%p 로 잡혔다).
        # 없는 키는 없는 채로 두고, 그날의 컷오프를 tech_floor 로 함께 남긴다.
        days_out.append({
            "date": r["date"],
            "total": total,
            "tech": {t: tech[t] for t in tracked if t in tech},
            "tech_floor": min(tech.values()) if tech else 0,
            "concepts": {c: concepts[c] for c in concepts_tracked if c in concepts},
            "bands": bands,
            "roles": roles,
        })

    # 급상승/급하락: 최근 MOVER_WINDOW 일 평균 비중 ↔ 그 직전 같은 길이 창의 평균 비중.
    # 첫날↔마지막날 단일 비교는 그날 크롤이 어디까지 돌았는지에 그대로 휘둘린다.
    n = len(days_out)
    w = min(MOVER_WINDOW, max(1, n // 2))
    movers: list[dict] = []
    if n >= 2:
        for t in tracked:
            to_pct, to_n = _window_pct(days_out, t, n - w, n)
            from_pct, from_n = _window_pct(days_out, t, max(0, n - 2 * w), n - w)
            # 양쪽 창 모두 절반 이상의 날에서 실제로 관측돼야 비교할 자격이 있다.
            # 한쪽이 한두 날짜뿐이면 그건 추세가 아니라 표본이다.
            if to_n * 2 < w or from_n * 2 < w:
                continue
            if to_pct < MOVER_MIN_PCT and from_pct < MOVER_MIN_PCT:
                continue
            movers.append({
                "tech": t,
                "from_pct": from_pct,
                "to_pct": to_pct,
                "delta": round(to_pct - from_pct, 2),
                "observed_days": [from_n, to_n],
            })
    movers.sort(key=lambda m: m["delta"])
    up = [m for m in reversed(movers) if m["delta"] > 0][:MOVERS_N]
    down = [m for m in movers if m["delta"] < 0][:MOVERS_N]

    # 직군별 시계열 (직군 → 일자별 {date, count, tech})
    role_days: dict[str, list[dict]] = {r: [] for r in roles_tracked}
    for r in days:
        day_roles = r.get("roles") or {}
        for role in roles_tracked:
            entry = day_roles.get(role) or {}
            count = int(entry.get("count") or 0)
            if not count:
                continue
            tech = _pairs(entry.get("tech"))
            role_days[role].append({
                "date": r["date"],
                "count": count,
                "tech": {t: tech[t] for t in role_tech_tracked.get(role, []) if t in tech},
            })

    doc = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "trends_history.jsonl",
        "keyword": keyword,
        "span": {"from": days_out[0]["date"], "to": days_out[-1]["date"], "days": n},
        "mover_window_days": w,
        "tracked": tracked,
        "concepts_tracked": concepts_tracked,
        "days": days_out,
        "movers": {"up": up, "down": down},
        "roles_tracked": roles_tracked,
        "role_tech_tracked": role_tech_tracked,
        "role_days": role_days,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    print(f"[trends] {n}일({days_out[0]['date']}~{days_out[-1]['date']}) · "
          f"keyword={keyword} · 추적 {len(tracked)}개 기술 → {OUT}")
    if dropped:
        print(f"  (다른 keyword 제외: {', '.join(dropped)} — 크롤 범위가 달라 분모가 맞지 않음)")
    print(f"  최신일 공고 {days_out[-1]['total']:,}건 · 비교창 {w}일 · "
          f"직군 {len(roles_tracked)}개 시계열")
    if up:
        print("  급상승:", ", ".join(f"{m['tech']}(+{m['delta']}%p)" for m in up[:5]))
    if down:
        print("  급하락:", ", ".join(f"{m['tech']}({m['delta']}%p)" for m in down[:5]))


if __name__ == "__main__":
    main()
