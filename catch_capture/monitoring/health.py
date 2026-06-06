"""크롤 파이프라인 헬스 기록 + 규칙 기반 이상 탐지.

매 aggregate 사이클마다 record() 가 호출되어:
  - 사이트별 수집량, active/closed, 필드 채움률, 교차중복, override 수를 계산
  - health_history.jsonl 에 한 줄씩 누적 기록 (시간순 이력 = "정확히 되고 있는지"의 근거)
  - health_latest.json 에 최신 스냅샷 + 이상 목록 저장
  - 직전 기록과 비교해 이상(0건/급감/채움률 하락/사이트 소실 등)을 탐지

규모가 커지면 동일 개념을 Great Expectations·Soda(데이터 품질),
Prometheus+Grafana·Monte Carlo(옵저버빌리티)로 이관할 수 있다.

CLI:
    python health.py report [n]   # 최근 n개 사이클 헬스 요약 (기본 12)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.resolve()
HISTORY = BASE / "health_history.jsonl"
LATEST = BASE / "health_latest.json"

FIELDS = ("main_tasks", "qualifications", "preferences", "tech_stack")


def _empty(v) -> bool:
    return not (v and str(v).strip())


def _fill_rates(jobs: list[dict]) -> dict:
    n = len(jobs) or 1
    return {f: round(sum(1 for j in jobs if not _empty(j.get(f))) / n, 3) for f in FIELDS}


def _last_record(keyword: str) -> dict | None:
    if not HISTORY.exists():
        return None
    last = None
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("keyword") == keyword:
            last = r
    return last


def detect_anomalies(cur: dict, prev: dict | None) -> list[str]:
    out: list[str] = []
    cs = cur["site_counts"]
    for s, n in cs.items():
        if n == 0:
            out.append(f"[{s}] 수집 0건 — 크롤 실패/사이트 구조변경 의심")
    if prev:
        ps = prev.get("site_counts", {})
        for s, n in cs.items():
            p = ps.get(s)
            if p and p > 0 and n < p * 0.5:
                out.append(f"[{s}] 직전 {p} → 현재 {n}건 (50%+ 급감)")
        pa, ca = prev.get("active"), cur["active"]
        if pa and ca < pa * 0.7:
            out.append(f"모집중 {pa} → {ca}건 (30%+ 급감)")
        for f, r in cur["fill_rates"].items():
            pr = prev.get("fill_rates", {}).get(f)
            if pr is not None and r < pr - 0.2:
                out.append(f"채움률 {f} {pr:.0%} → {r:.0%} (20%p+ 하락)")
        for s in ps:
            if s not in cs:
                out.append(f"[{s}] 사이트 사라짐")
    return out


def record(keyword, site_counts, all_jobs, active_jobs, closed_jobs,
           cross_dups, failures=None) -> tuple[dict, list[str]]:
    cur = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "keyword": keyword,
        "site_counts": dict(site_counts),
        "raw_total": sum(site_counts.values()),
        "deduped": len(all_jobs),
        "cross_dups": cross_dups,
        "active": len(active_jobs),
        "closed": len(closed_jobs),
        "overridden": sum(1 for j in all_jobs if j.get("_overridden")),
        "fill_rates": _fill_rates(active_jobs),
        "fill_rates_by_site": {
            s: _fill_rates([j for j in active_jobs if j.get("site") == s])
            for s in site_counts
        },
        "failures": list(failures or []),
    }
    prev = _last_record(keyword)
    cur["anomalies"] = detect_anomalies(cur, prev)
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(cur, ensure_ascii=False) + "\n")
    LATEST.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    return cur, cur["anomalies"]


def report(n: int = 12) -> None:
    if not HISTORY.exists():
        print("(헬스 기록 없음 — 아직 사이클이 안 돌았거나 health 미적용)")
        return
    lines = [l for l in HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()][-n:]
    print(f"{'시각':19}  {'모집중':>5} {'마감':>4}  주요업무  | 사이트별")
    for l in lines:
        r = json.loads(l)
        sc = " ".join(f"{s}={c}" for s, c in r["site_counts"].items())
        fr = r["fill_rates"].get("main_tasks", 0)
        flag = f"  ⚠️{len(r['anomalies'])}" if r.get("anomalies") else ""
        print(f"{r['ts']:19}  {r['active']:>5} {r['closed']:>4}  {fr:>6.0%}  | {sc}{flag}")
    last = json.loads(lines[-1])
    if last.get("anomalies"):
        print("\n[최근 사이클 이상]")
        for a in last["anomalies"]:
            print(f"  - {a}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "report":
        report(int(args[1]) if len(args) > 1 and args[1].isdigit() else 12)
    else:
        report()
