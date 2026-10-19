"""크롤러 전체 현황 — 8770 의 '크롤러 전체 현황' 칸(`/api/crawlers`).

사이트별 수집 칸은 run_state 의 이번 회차만 보여준다. 데몬이 죽으면 그 칸은 마지막 회차를
'완료'로 띄운 채 멈춰서, 2주 동안 안 돈 것도 정상처럼 보였다(2026-10-04 → 10-18).
여기는 **산출물이 스스로 적은 시각**(listed.json `at`, freelance.json `sources[*].at`,
prices/prebuilt `updated_at`, 마감 원장 mtime)으로 출처마다 나이를 잰다.

출처는 다섯 묶음이다 — 채용 보드 · 회사 채용페이지(ats, provider 별) · 국내 기타 보드(boards,
출처별) · 외주·프리 · 하드웨어. 스케줄러(launchd·auto_crawl)는 따로 실어 '왜 멈췄나'를 같이 보인다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from core.paths import CATCH_DIR, SCREENSHOTS_DIR, VIEWER_PUBLIC
from core.sites import BY_KEY, SITE_KEYS

# 기대 주기별 문턱(시간) — (정상 상한, 주의 상한). 넘으면 멈춤.
HOURLY = (3, 24)        # 크롤 회차는 1시간마다
DAILY = (30, 72)        # 하드웨어 가격·완제품은 하루 한 번
CLOSECHECK = (0.5, 3)   # 마감 재확인은 10분마다

ATS_BOARDS = CATCH_DIR / "crawlers" / "ats_boards.json"
CLOSURES = CATCH_DIR / "job_closures.json"
STATE_FILE = CATCH_DIR / "run_state.json"
PID_FILE = CATCH_DIR / "auto_crawl.pid"
LAUNCHD = ("com.jobseeker.crawler", "com.jobseeker.closecheck")

_CACHE: dict = {"at": 0.0, "data": None}


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _age_hours(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    now = datetime.now(timezone.utc) if dt.tzinfo else datetime.now()
    return round((now - dt).total_seconds() / 3600, 2)


def _state(age: float | None, limits: tuple[float, float], ok: bool = True) -> str:
    if not ok:
        return "error"
    if age is None:
        return "unknown"
    if age <= limits[0]:
        return "ok"
    return "warn" if age <= limits[1] else "stale"


def _listings(prefix: str) -> list[dict]:
    """`screenshots/<prefix>_<키워드>/listed.json` 전부. 키워드 폴더마다 하나씩 있다."""
    out = []
    for p in SCREENSHOTS_DIR.glob(f"{prefix}_*/listed.json"):
        d = _read_json(p)
        if isinstance(d, dict) and d.get("at"):
            out.append({"keyword": p.parent.name[len(prefix) + 1:], **d})
    return out


def _job_sites(cycle_sites: dict) -> list[dict]:
    rows = []
    for site in (k for k in SITE_KEYS if k not in ("ats", "boards")):   # 둘은 출처별 묶음이 따로 있다
        ls = _listings(site)
        last = max((l["at"] for l in ls), default=None)
        # 마지막 회차에 돈 키워드들(가장 최근 것에서 2시간 안)의 pid 를 합친다
        recent = [l for l in ls if last and _age_hours(l["at"]) - _age_hours(last) < 2]
        pids = set().union(*(l.get("pids") or [] for l in recent)) if recent else set()
        cyc = cycle_sites.get(site) or {}
        age = _age_hours(last)
        rows.append({
            "key": site, "name": BY_KEY[site].label, "at": last, "age_hours": age,
            "count": len(pids), "detail": f"키워드 {len(recent)}개" if recent else "",
            "error": cyc.get("reason") or (cyc.get("status") == "failed" and "지난 회차 실패") or None,
            "state": _state(age, HOURLY, ok=cyc.get("status") != "failed"),
        })
    return rows


def _by_prefix(listing: dict | None, scopes_key: str = "complete_scopes") -> dict[str, dict]:
    if not listing:
        return {}
    out: dict[str, dict] = {}
    for pid in listing.get("pids") or []:
        out.setdefault(pid.split(":", 1)[0], {"count": 0, "complete": 0})["count"] += 1
    for sc in listing.get(scopes_key) or []:
        out.setdefault(sc.split(":", 1)[0], {"count": 0, "complete": 0})["complete"] += 1
    return out


def _ats() -> list[dict]:
    listing = max(_listings("ats"), key=lambda l: l["at"], default=None)
    seen = _by_prefix(listing)
    boards = (_read_json(ATS_BOARDS) or {}).get("boards") or []
    configured: dict[str, int] = {}
    for b in boards:
        configured[b.get("provider")] = configured.get(b.get("provider"), 0) + 1
    at = listing and listing["at"]
    age = _age_hours(at)
    rows = []
    for prov in sorted(set(configured) | set(seen), key=lambda p: -(seen.get(p, {}).get("count", 0))):
        s = seen.get(prov, {"count": 0, "complete": 0})
        n = configured.get(prov, 0)
        # 끝까지 읽힌 보드가 없다 — 크롤러는 실패·0건·국내 몫 초과로 건너뜀을 같은 자리에 남긴다
        # (crawl_ats: 0건은 완전한 목록으로 치지 않는다). 실패로 단정하지 않고 표시만 한다.
        empty = n and s["complete"] == 0
        rows.append({
            "key": prov, "name": prov, "at": at, "age_hours": age, "count": s["count"],
            "detail": f"보드 {s['complete']}/{n}" if n else "",
            "error": "지난 회차 0건 — 공고 없음·실패·건너뜀 중 하나(크롤 로그 확인)" if empty else None,
            "state": _state(age, HOURLY),
        })
    return rows


def _boards() -> list[dict]:
    listing = max(_listings("boards"), key=lambda l: l["at"], default=None)
    seen = _by_prefix(listing)
    at = listing and listing["at"]
    age = _age_hours(at)
    return [{
        "key": src, "name": src, "at": at, "age_hours": age, "count": s["count"],
        "detail": "", "error": None if s["count"] else "0건",
        "state": _state(age, HOURLY, ok=bool(s["count"])),
    } for src, s in sorted(seen.items(), key=lambda kv: -kv[1]["count"])]


def _freelance() -> list[dict]:
    d = _read_json(VIEWER_PUBLIC / "freelance.json") or {}
    rows = []
    for src, v in (d.get("sources") or {}).items():
        at = v.get("at") or d.get("updated_at")
        age = _age_hours(at)
        err = None if v.get("ok") else re.sub(r"\s+", " ", str(v.get("error") or "실패"))[:160]
        rows.append({
            "key": src, "name": src, "at": at, "age_hours": age, "count": v.get("fetched"),
            "detail": f"{v['elapsed']}초" if v.get("elapsed") is not None else "",
            "error": err, "state": _state(age, HOURLY, ok=bool(v.get("ok"))),
        })
    return rows


def _hardware() -> list[dict]:
    rows = []
    for key, name, fname, count_key in (
        ("prices", "부품 가격(다나와)", "prices.json", "parts"),
        ("prebuilt", "완제품 조립PC", "prebuilt.json", "items"),
    ):
        d = _read_json(VIEWER_PUBLIC / "hardware" / fname) or {}
        at = d.get("updated_at")
        age = _age_hours(at)
        items = d.get(count_key)
        rows.append({
            "key": key, "name": name, "at": at, "age_hours": age,
            "count": len(items) if isinstance(items, (list, dict)) else None,
            "detail": f"{d.get('day')}" + ("" if d.get("complete", True) else " · 덜 받음"),
            "error": None if d else "파일 없음",
            "state": _state(age, DAILY, ok=bool(d)),
        })
    return rows


def _closecheck() -> list[dict]:
    if not CLOSURES.exists():
        return [{"key": "closures", "name": "마감 재확인 원장", "at": None, "age_hours": None,
                 "count": None, "detail": "", "error": "원장 없음", "state": "error"}]
    at = datetime.fromtimestamp(CLOSURES.stat().st_mtime).isoformat(timespec="seconds")
    age = _age_hours(at)
    return [{"key": "closures", "name": "마감 재확인 원장", "at": at, "age_hours": age,
             "count": None, "detail": "10분마다 100건", "error": None,
             "state": _state(age, CLOSECHECK)}]


def _launchd(label: str) -> dict:
    try:
        r = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{label}"],
                           capture_output=True, text=True, timeout=5)
    except Exception as e:  # launchctl 없음(리눅스 등)
        return {"label": label, "loaded": None, "error": str(e)}
    if r.returncode != 0:
        return {"label": label, "loaded": False}
    def grab(key):
        m = re.search(rf"^\s*{re.escape(key)} = (.+)$", r.stdout, re.M)
        return m.group(1).strip() if m else None
    return {"label": label, "loaded": True, "state": grab("state"), "runs": grab("runs"),
            "last_exit": grab("last exit code"), "interval": grab("run interval"), "pid": grab("pid")}


def _daemon() -> dict:
    pid = None
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        pid = None
    st = _read_json(STATE_FILE) or {}
    cyc = st.get("cycle") or {}
    return {"pid": pid, "phase": st.get("phase"), "updated_at": st.get("updated_at"),
            "cycle_started_at": cyc.get("started_at"), "cycle_finished_at": cyc.get("finished_at"),
            "last_error": st.get("last_error")}


def summary() -> dict:
    """출처별 나이·건수·상태. launchctl 을 부르므로 20초 재사용한다."""
    if _CACHE["data"] is not None and time.time() - _CACHE["at"] < 20:
        return _CACHE["data"]
    st = _read_json(STATE_FILE) or {}
    groups = [
        {"key": "jobs", "name": "채용 보드", "rows": _job_sites((st.get("cycle") or {}).get("sites") or {})},
        {"key": "ats", "name": "회사 채용페이지(ATS·그룹 포털)", "rows": _ats()},
        {"key": "boards", "name": "국내 기타 보드·공공", "rows": _boards()},
        {"key": "freelance", "name": "외주·프리랜서", "rows": _freelance()},
        {"key": "hardware", "name": "하드웨어", "rows": _hardware()},
        {"key": "closecheck", "name": "마감 재확인", "rows": _closecheck()},
    ]
    rows = [r for g in groups for r in g["rows"]]
    counts = {s: sum(r["state"] == s for r in rows) for s in ("ok", "warn", "stale", "error", "unknown")}
    data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": counts, "total": len(rows),
        "newest_at": max((r["at"] for r in rows if r["at"] and r["key"] != "closures"), default=None),
        "groups": groups,
        "scheduler": {"daemon": _daemon(), "launchd": [_launchd(l) for l in LAUNCHD]},
    }
    _CACHE.update(at=time.time(), data=data)
    return data


if __name__ == "__main__":
    print(json.dumps(summary(), ensure_ascii=False, indent=1))
