"""쌓인 행동 기록 → 뷰어가 읽는 점수표(public/engagement.json).

**두 가지를 뽑는다.**

  items   항목별 관심도 — 얼마나 열렸고(views), 얼마나 머물렀고(중앙값 체류),
          원본으로 몇 명이 넘어갔나(outbound). 이 셋을 섞어 0~1 점수를 낸다.
  next    항목 사이의 이동 — 이 공고를 본 사람이 그다음 무엇을 눌렀나.
          '내용이 닮았다'(임베딩)와 다른 종류의 근거다. 추천을 섞을 때 이쪽이
          "사람들이 실제로 그다음에 본다"를 맡는다.
  traffic 얼마나 들어오고 어디서 오는가 — 방문 수, 순 방문자, 신규/재방문,
          유입 경로(referrer 호스트), 첫 화면(랜딩 경로), 날짜별 추이.

**평균이 아니라 중앙값을 쓴다.** 체류시간은 꼬리가 길다 — 탭을 띄워 놓고 점심을
먹고 온 한 사람이 평균을 통째로 끌어올린다. 그 한 명 때문에 엉뚱한 공고가 위로
올라오면 추천이 망가진다. 중앙값은 그 사람을 한 표로만 센다.

**적게 본 것은 점수를 믿지 않는다.** 한 번 열려서 5분 머문 공고와 백 번 열려서
5분 머문 공고는 같은 근거가 아니다. views 에 로그를 씌워 표본이 쌓일수록 점수가
따라 오르게 한다.

사용법:
    python -m engagement.score              # 최근 30일 기준으로 집계
    python -m engagement.score --days 7
    python -m engagement.score --dry-run    # 파일 안 쓰고 요약만
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import argparse
import json
import math
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent.parent
EVENTS = BASE_DIR / "events.jsonl"
OUT = ROOT_DIR / "jd-viewer" / "public" / "engagement.json"

WINDOW_DAYS = 30
MIN_VIEWS = 2          # 이보다 적게 열린 항목은 점수표에 넣지 않는다(노이즈)
NEXT_TOP = 5           # 항목당 보관할 '다음에 본 것' 개수
DWELL_CAP = 600        # 한 항목에 10분 넘게 머문 것은 10분으로 친다


def _median(xs: list[int]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return float(s[mid]) if n % 2 else (s[mid - 1] + s[mid]) / 2


def load(days: int) -> list[dict]:
    if not EVENTS.exists():
        return []
    cutoff = time.time() - days * 86400
    out = []
    with EVENTS.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (r.get("ts") or 0) >= cutoff:
                out.append(r)
    return out


def _traffic(events: list[dict], seen_before: set[str]) -> dict:
    """방문 통계. 'session' 사건(페이지 로드 1회)이 재료다.

    신규/재방문은 **이 집계 창 안에서** 처음 보이는 세션인지로 가른다. 창 밖에서
    왔던 사람은 신규로 잡히는데, 그 한계를 감추는 것보다 이름에 드러내는 게 낫다
    (new_in_window).
    """
    starts = [e for e in events if e.get("t") == "session"]
    sources: dict[str, int] = defaultdict(int)
    landings: dict[str, int] = defaultdict(int)
    daily: dict[str, int] = defaultdict(int)
    visitors: set[str] = set()
    new_ones: set[str] = set()
    for e in starts:
        sid = e.get("sid") or "?"
        visitors.add(sid)
        if sid not in seen_before:
            new_ones.add(sid)
        sources[str(e.get("from") or "unknown")] += 1
        landings[str(e.get("k") or "/")] += 1
        daily[datetime.fromtimestamp(e.get("ts") or 0).strftime("%Y-%m-%d")] += 1
    top = lambda d, n: sorted(d.items(), key=lambda kv: -kv[1])[:n]  # noqa: E731
    return {
        "visits": len(starts),
        "visitors": len(visitors),
        "new_in_window": len(new_ones),
        "sources": top(sources, 20),
        "landings": top(landings, 20),
        "daily": sorted(daily.items()),
    }


def build(events: list[dict]) -> dict:
    views: dict[str, int] = defaultdict(int)
    dwells: dict[str, list[int]] = defaultdict(list)
    outbound: dict[str, int] = defaultdict(int)
    from_reco: dict[str, int] = defaultdict(int)
    edges: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    sessions: dict[str, list[dict]] = defaultdict(list)

    for e in events:
        kind, key, src = e.get("t"), e.get("k"), e.get("from")
        if e.get("sid"):
            sessions[e["sid"]].append(e)
        if kind == "view" and key:
            views[key] += 1
            if src and src != "list":
                from_reco[key] += 1
        elif kind == "dwell" and key:
            dwells[key].append(min(int(e.get("s") or 0), DWELL_CAP))
        elif kind == "click" and key == "outbound" and src:
            outbound[src] += 1
        elif kind == "click" and key and src and key != "outbound":
            # 추천에서 다음 항목으로 넘어간 사건. 이게 'next' 의 재료다.
            edges[src][key] += 1

    # ── 점수 ────────────────────────────────────────────────────
    # 머문 시간(중앙값)이 본체이고, 표본이 많을수록 그 값을 더 믿는다.
    # 원본으로 넘어간 것은 '진짜 관심'의 가장 강한 신호라 따로 가산한다.
    raw: dict[str, float] = {}
    for key, v in views.items():
        if v < MIN_VIEWS:
            continue
        med = _median(dwells.get(key, []))
        raw[key] = med * math.log1p(v) + 30.0 * outbound.get(key, 0)
    top = max(raw.values()) if raw else 0.0

    items = {}
    for key, score in raw.items():
        items[key] = {
            "v": views[key],
            "d": round(_median(dwells.get(key, [])), 1),
            "o": outbound.get(key, 0),
            "r": from_reco.get(key, 0),
            "score": round(score / top, 4) if top else 0.0,
        }

    nxt = {
        src: sorted(tgts.items(), key=lambda kv: -kv[1])[:NEXT_TOP]
        for src, tgts in edges.items()
        if tgts
    }

    # ── 전체 지표 — '체류시간이 늘고 있나'를 볼 수 있는 최소한 ────
    lens, depths = [], []
    for evs in sessions.values():
        ts = [e.get("ts") or 0 for e in evs]
        lens.append(max(ts) - min(ts))
        depths.append(sum(1 for e in evs if e.get("t") == "view"))
    total_dwell = sum(sum(v) for v in dwells.values())

    # 창 시작 이전에도 있었던 세션인지 — 신규/재방문을 가르는 기준.
    # events 는 이미 창으로 잘려 있으므로, 창 안에서 session 이 아닌 사건으로
    # 먼저 나타난 세션은 '이어서 온 사람'이다.
    first_seen: dict[str, str] = {}
    for e in events:
        sid = e.get("sid")
        if sid and sid not in first_seen:
            first_seen[sid] = e.get("t") or ""
    returning = {sid for sid, kind in first_seen.items() if kind != "session"}

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "traffic": _traffic(events, returning),
        "totals": {
            "events": len(events),
            "sessions": len(sessions),
            "views": sum(views.values()),
            "outbound": sum(outbound.values()),
            "dwell_secs": total_dwell,
            "median_session_secs": round(_median([int(x) for x in lens]), 1),
            "median_views_per_session": round(_median(depths), 1),
            "scored_items": len(items),
        },
        "items": items,
        "next": nxt,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="행동 기록 집계 → engagement.json")
    ap.add_argument("--days", type=int, default=WINDOW_DAYS)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    events = load(args.days)
    doc = build(events)
    t = doc["totals"]
    print(f"[engagement] 최근 {args.days}일 · 이벤트 {t['events']:,} · 세션 {t['sessions']:,}")
    print(f"  열람 {t['views']:,} · 원본이동 {t['outbound']:,} · 총 체류 {t['dwell_secs']:,}초")
    print(f"  세션당 중앙값 — 길이 {t['median_session_secs']}초 · 열람 {t['median_views_per_session']}건")
    print(f"  점수 매긴 항목 {t['scored_items']:,} · 이동 경로 {len(doc['next']):,}")
    tr = doc["traffic"]
    print(f"  방문 {tr['visits']:,} · 순 방문자 {tr['visitors']:,} "
          f"(그중 신규 {tr['new_in_window']:,})")
    if tr["sources"]:
        print("  유입 경로: " + ", ".join(f"{k} {v}" for k, v in tr["sources"][:6]))
    if tr["landings"]:
        print("  첫 화면:   " + ", ".join(f"{k} {v}" for k, v in tr["landings"][:4]))
    if not events:
        print("  아직 쌓인 기록이 없습니다 — 수집 서버(engagement.collect)가 떠 있는지 확인하세요.")
    if args.dry_run:
        print("  [dry-run] 파일은 쓰지 않았습니다.")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"  → {OUT} ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv[1:]))
