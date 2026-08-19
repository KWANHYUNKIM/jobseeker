#!/usr/bin/env python3
"""재공고 탐지 + 변경 로그.

입력: jd-viewer/public/all_jobs_enriched.json      (모집중 + 마감, status 포함)
      catch_capture/screenshots/closed_<label>.json (누적 마감 아카이브)
저장: catch_capture/job_history.jsonl               (append-only 버전 기록)
출력: jd-viewer/public/reposts.json

**무엇을 푸는가.** 같은 회사가 같은 자리를 마감했다가 다시 올린다. 채용 사이트는 그때
새 URL 을 발급하므로 겉으로는 완전히 새로운 공고로 보이고, 무엇이 달라졌는지는 아무도
말해주지 않는다. 그런데 바로 그 '무엇이 달라졌는지'가 시장 신호다 — 한 곳은
`경력3년↑` 을 `경력1년↑` 로 낮춰서 다시 올렸다. 사람을 못 구했다는 뜻이다.

**동일성 판정.** URL 은 재발급되므로 쓸 수 없다. (회사, 제목) 정규화 키를 쓴다.
회사명이 비어 있는 소스가 있어 그때는 (사이트, 제목) 으로 대체한다. 제목까지 바꾼
재공고는 놓치는데, 그건 잡으려다 서로 다른 자리를 한 자리로 합치는 쪽이 더 나쁘다.

**히스토리.** 아카이브는 (회사,제목) 으로 중복 제거를 하므로 같은 자리가 세 번
올라와도 한 줄만 남는다. 즉 아카이브만으로는 '이전 버전'이 하나뿐이다. 그래서 여기서
job_history.jsonl 에 버전을 append 한다. 내용 해시가 직전 기록과 다를 때만 한 줄
쌓으므로, 사이클마다 돌려도 변화가 없으면 파일이 자라지 않는다. 회차가 쌓일수록
"이 자리는 네 번째 재공고이고 매번 경력 요구가 내려갔다" 같은 것이 보이게 된다.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ENRICHED = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
ARCHIVE_GLOB = "closed_*.json"
ARCHIVE_DIR = ROOT / "catch_capture" / "screenshots"
HISTORY = ROOT / "catch_capture" / "job_history.jsonl"
OUT = ROOT / "jd-viewer" / "public" / "reposts.json"

# 변경 로그에 올릴 필드. 긴 본문은 '바뀜/안 바뀜'과 길이 변화만 본다 — 전문을 담으면
# 파일이 수십 MB 가 되고, 읽는 사람이 궁금한 것도 대개 '바뀌었나' 까지다.
SHORT_FIELDS = ["career", "location", "deadline", "dday", "title", "url", "site"]
LIST_FIELDS = ["tech_stack"]
LONG_FIELDS = ["qualifications", "preferences", "main_tasks", "benefits"]


def nk(s: str | None) -> str:
    return re.sub(r"\s+", "", (s or "")).lower()


def key_of(j: dict) -> tuple[str, str]:
    comp = nk(j.get("company")) or f"site:{nk(j.get('site'))}"
    return comp, nk(j.get("title"))


def content_hash(j: dict) -> str:
    payload = json.dumps(
        {f: j.get(f) for f in SHORT_FIELDS + LIST_FIELDS + LONG_FIELDS if f != "url"},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def diff(old: dict, new: dict) -> list[dict]:
    changes: list[dict] = []
    for f in SHORT_FIELDS:
        a, b = (old.get(f) or ""), (new.get(f) or "")
        if a != b:
            changes.append({"field": f, "kind": "value", "from": str(a)[:120], "to": str(b)[:120]})
    for f in LIST_FIELDS:
        a, b = set(old.get(f) or []), set(new.get(f) or [])
        if a != b:
            changes.append({
                "field": f, "kind": "list",
                "added": sorted(b - a)[:12], "removed": sorted(a - b)[:12],
            })
    for f in LONG_FIELDS:
        a, b = (old.get(f) or ""), (new.get(f) or "")
        if a == b:
            continue
        # 한쪽이 0자면 '요구가 사라졌다'가 아니라 그 판의 본문을 못 긁은 것이다.
        # jobkorea 는 본문을 별도 txt 로 받아오는데 갓 올라온 공고는 아직 없을 수 있다.
        # 실제로 텍스트 변경 121건 중 81건(66%)이 이 경우였다 — 그대로 세면
        # "재공고하면서 자격요건을 통째로 지웠다"는 잘못된 트렌드가 만들어진다.
        missing = (len(a) == 0) != (len(b) == 0)
        changes.append({
            "field": f, "kind": "text", "missing": missing,
            "from_len": len(a), "to_len": len(b),
            "to_excerpt": b[:180],
        })
    return changes


def load_history() -> dict[str, list[dict]]:
    hist: dict[str, list[dict]] = {}
    if not HISTORY.exists():
        return hist
    # split("\n") 이지 splitlines() 가 아니다. splitlines() 는 \n 외에 U+2028,
    # U+2029, U+0085, \x0b, \x0c 에서도 자르는데, json.dumps(ensure_ascii=False) 는
    # 그 문자들을 이스케이프하지 않고 그대로 흘려보낸다. 크롤한 JD 본문에 그런 문자가
    # 섞여 있으면 한 레코드가 두 조각으로 쪼개지고 둘 다 파싱에 실패해, 그 자리는
    # 히스토리에서 통째로 사라진 것처럼 보인다. 그러면 매 실행마다 같은 판이 다시
    # append 되어 파일만 자란다 — 새 해시는 하나도 없는데 줄 수만 느는 증상이었다.
    # (JSON 문자열 안의 U+2028 자체는 적법하므로 json.loads 는 문제없이 읽는다.)
    bad = 0
    for line in HISTORY.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        hist.setdefault(r["key"], []).append(r)
    if bad:
        print(f"  [history] 파싱 실패 {bad}줄 — 건너뜀")
    return hist


def snapshot(j: dict, status: str) -> dict:
    rec = {f: j.get(f) for f in SHORT_FIELDS}
    rec["tech_stack"] = list(j.get("tech_stack") or [])
    for f in LONG_FIELDS:
        rec[f] = j.get(f) or ""
    rec["status"] = status
    return rec


def main() -> None:
    jobs = json.loads(ENRICHED.read_text(encoding="utf-8"))
    today = datetime.now().strftime("%Y-%m-%d")

    # 아카이브의 옛 버전을 히스토리 부트스트랩으로 쓴다. 히스토리가 비어 있는 첫 실행에서도
    # 과거 한 판은 확보된다 — 없으면 재공고를 "지금부터" 만 볼 수 있다.
    archived: dict[tuple[str, str], dict] = {}
    for f in sorted(ARCHIVE_DIR.glob(ARCHIVE_GLOB)):
        try:
            for a in json.loads(f.read_text(encoding="utf-8")):
                archived.setdefault(key_of(a), a)
        except (json.JSONDecodeError, OSError):
            continue

    hist = load_history()
    appended = 0
    lines: list[str] = []

    def remember(k: tuple[str, str], j: dict, status: str, seen: str,
                 bootstrap: bool = False) -> None:
        nonlocal appended
        ks = f"{k[0]}\t{k[1]}"
        h = content_hash(j)
        prev = hist.get(ks)
        # 부트스트랩(아카이브)은 그 자리의 기록이 아예 없을 때만 넣는다. 조건 없이 넣으면
        # 매 실행마다 [아카이브판, 현재판] 이 번갈아 append 되어 파일이 실행할 때마다
        # 두 배로 자란다 — 직전 해시만 보고 판단하면 A→B→A 를 새 변경으로 오해한다.
        if bootstrap and prev:
            return
        # 직전 판이 아니라 그 자리의 **모든** 기록과 비교한다. 직전만 보면 한 자리가
        # 이미 기록된 두 상태 사이를 오갈 때(A→B→A) 매 실행마다 줄이 하나씩 쌓인다.
        # 실제로 그렇게 20개 자리가 실행마다 파일을 늘리고 있었다 — 새 해시는 하나도
        # 없는데 줄만 늘어나는, 눈으로는 안 보이는 종류의 증식이었다.
        # 대가: 공고가 예전 상태로 정확히 되돌아가면 그 회귀는 새 판으로 남지 않는다.
        # 재공고 추적이 보려는 것은 '서로 다른 상태들' 이므로 이 쪽이 맞다.
        if prev and any(p["hash"] == h for p in prev):
            return
        rec = {"key": ks, "hash": h, "seen": seen, "data": snapshot(j, status)}
        hist.setdefault(ks, []).append(rec)
        lines.append(json.dumps(rec, ensure_ascii=False))
        appended += 1

    for k, a in archived.items():
        remember(k, a, "closed", a.get("_archived_at") or "bootstrap", bootstrap=True)
    # 한 실행에서 자리당 한 판만 기록한다. enriched 에는 같은 자리가 모집중과 마감 두
    # 판으로 들어 있을 수 있고(재공고된 자리의 옛 판이 아직 마감 목록에 남아 있는 경우),
    # 그대로 두 번 remember 하면 실행마다 두 해시가 번갈아 append 되어 파일이 계속 자란다.
    # '지금' 을 대표하는 것은 살아 있는 판이므로 모집중을 우선한다.
    best: dict[tuple[str, str], dict] = {}
    for j in jobs:
        k = key_of(j)
        cur = best.get(k)
        if cur is None or ((j.get("status") or "active") == "active"
                           and (cur.get("status") or "active") == "closed"):
            best[k] = j
    for k, j in best.items():
        remember(k, j, j.get("status") or "active", today)

    if lines:
        with HISTORY.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    # ── 재공고 판정 ────────────────────────────────────────────────
    # 마감된 판이 있고, 그 뒤에 다시 모집중인 판이 있는 자리.
    by_key_now = {}
    for j in jobs:
        by_key_now.setdefault(key_of(j), []).append(j)

    reposts = []
    for ks, versions in hist.items():
        if len(versions) < 2:
            continue
        comp, title = ks.split("\t", 1)
        live = [v for v in versions if v["data"].get("status") == "active"]
        closed = [v for v in versions if v["data"].get("status") == "closed"]
        if not live or not closed:
            continue
        latest = versions[-1]
        if latest["data"].get("status") != "active":
            continue                    # 지금 살아 있는 자리만 '재공고'다
        # 직전의 마감 판과 비교한다
        prev_closed = closed[-1]
        changes = diff(prev_closed["data"], latest["data"])
        if not changes:
            continue
        cur = by_key_now.get((comp, title), [{}])[0]
        reposts.append({
            "company": cur.get("company") or prev_closed["data"].get("site") or "",
            "title": cur.get("title") or latest["data"].get("title") or "",
            "url": latest["data"].get("url") or "",
            "site": latest["data"].get("site") or "",
            "rounds": len(versions),
            "prev_deadline": prev_closed["data"].get("deadline") or "",
            "now_deadline": latest["data"].get("deadline") or "",
            "prev_seen": prev_closed.get("seen") or "",
            "now_seen": latest.get("seen") or "",
            "changes": changes,
            "tech_stack": latest["data"].get("tech_stack") or [],
        })

    # 변화가 많은 순 — 읽을 가치가 큰 순서다
    reposts.sort(key=lambda r: (-sum(1 for c in r["changes"] if not c.get("missing")),
                                -r["rounds"]))

    # 집계: 무엇이 자주 바뀌는가 (트렌드 분석의 재료)
    field_counts: dict[str, int] = {}
    career_moves = {"낮춤": 0, "높임": 0, "동일": 0}
    YEARS = re.compile(r"(\d+)\s*년")
    for r in reposts:
        for c in r["changes"]:
            if c.get("missing"):
                continue        # 비교 불가는 '바뀐 항목'으로 세지 않는다
            field_counts[c["field"]] = field_counts.get(c["field"], 0) + 1
            if c["field"] == "career" and c["kind"] == "value":
                fa, fb = YEARS.search(c["from"] or ""), YEARS.search(c["to"] or "")
                if fa and fb:
                    a, b = int(fa.group(1)), int(fb.group(1))
                    career_moves["낮춤" if b < a else "높임" if b > a else "동일"] += 1

    doc = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "history_versions": sum(len(v) for v in hist.values()),
        "tracked_positions": len(hist),
        "reposts": reposts,
        "summary": {
            "count": len(reposts),
            "changed_fields": sorted(field_counts.items(), key=lambda kv: -kv[1]),
            "career_moves": career_moves,
        },
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"[reposts] 히스토리 +{appended:,}줄 (누적 {doc['history_versions']:,}판 / 자리 {len(hist):,})")
    print(f"[reposts] 재공고 {len(reposts):,}건 → {OUT} ({OUT.stat().st_size:,} bytes)")
    if field_counts:
        top = ", ".join(f"{k} {v}" for k, v in sorted(field_counts.items(), key=lambda kv: -kv[1])[:6])
        print(f"  자주 바뀐 필드: {top}")
    print(f"  경력 요구: 낮춤 {career_moves['낮춤']} · 높임 {career_moves['높임']} · 동일 {career_moves['동일']}")


if __name__ == "__main__":
    main()
