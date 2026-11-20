"""마감·수집 점검 — '접수마감이 제때 접수마감으로 적히는가'와 '공고가 제대로 들어오는가'를 센다.

마감은 세 군데가 따로 정한다 — 크롤러가 목록에서 읽은 표기, 재확인(close_check · 외주 recheck)이
원본에 다시 물은 답, 화면이 읽는 순간의 날짜 비교. 하나가 조용히 고장 나도 나머지가 덮어서 눈에
안 띈다(jumpit 은 내려간 공고에 400 을 줘서 몇 주를 '확인 실패'로 남겼다). 그래서 이 모듈은 고치지
않고 **세기만** 한다. 닫는 일은 close_check·crawl_freelance 가 한다.

세 갈래:
  consistency  (네트워크 없음) 모집중으로 적힌 것 중 마감일이 지난 것·오래 안 보인 것·재확인이
               밀린 것을 사이트별로 센다. 0 이 아니면 어딘가 접수마감을 못 적고 있다.
  intake       (네트워크 없음) 사이트별 마지막 수집 시각·건수. 0건·실패·오래 멈춤을 잡는다.
  probe        (--probe) 외주 소스마다 목록 1쪽을 실제로 받아 본다(저장하지 않는다). 채용 크롤러는
               브라우저를 띄우므로 여기서 돌리지 않고, 회차마다 남기는 listed.json 의 나이·건수로 본다.
  live         (--live N) 사이트마다 모집중 N건·마감 N건을 원본에 다시 물어 우리 기록과 대조한다.
               답을 하나도 못 얻는 사이트 = 판정기가 깨졌다(원본 모양이 바뀌었다).

    python -m pipeline.close_audit                 # 정합성 + 수집 상태
    python -m pipeline.close_audit --live 3        # + 원본 대조(사이트당 최대 6요청)
    python -m pipeline.close_audit --probe         # + 외주 목록 1쪽씩 실제 수집
    python -m pipeline.close_audit --json          # 보고서를 JSON 으로 출력
    python -m pipeline.close_audit --strict        # 실패(FAIL)가 있으면 종료 코드 1

보고서는 var/audit/close_audit.json(최신) 과 var/audit/history.jsonl(요약 한 줄씩)에 남는다.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import json
import random
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from core.paths import SCREENSHOTS_DIR, VAR_DIR

CATCH = Path(__file__).resolve().parent.parent
PUBLIC = CATCH.parent / "jd-viewer" / "public"
FREELANCE = PUBLIC / "freelance.json"
ENRICHED = PUBLIC / "all_jobs_enriched.json"
HEALTH_LATEST = CATCH / "health_latest.json"
AUDIT_DIR = VAR_DIR / "audit"

STALE_DAYS = 14          # 뷰어·project_state 와 같은 값 — 이만큼 안 보이면 화면은 접수마감으로 본다
INTAKE_STALE_HOURS = 12  # 이보다 오래 수집이 없으면 멈춘 것으로 본다(사이클은 1시간)
OVERDUE_FACTOR = 2.0     # 재확인 주기의 이 배수를 넘겨 안 물어본 공고는 '밀림'


def _now() -> datetime:
    return datetime.now().astimezone()


def _age_days(iso: str | None, now: datetime) -> float | None:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return (now - (t if t.tzinfo else t.astimezone())).total_seconds() / 86400


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ── 정합성 ───────────────────────────────────────────────────────────────

def freelance_consistency(projects: list[dict], today: str, now: datetime) -> dict[str, dict]:
    """사이트별: 모집중으로 적혔는데 마감일이 지난 것(past_deadline)·14일 넘게 안 보인 것(stale)·
    마감인데 근거가 없는 것(closed_no_reason). 앞의 둘은 화면이 접수마감으로 덮지만 JSON·DB 를
    읽는 다른 쪽(agent-mcp·단가 분석)은 모집중으로 센다."""
    out: dict[str, dict] = defaultdict(lambda: {"active": 0, "closed": 0, "past_deadline": 0,
                                                "stale": 0, "closed_no_reason": 0, "examples": []})
    for p in projects:
        s = out[p.get("site") or "?"]
        if p.get("status") == "closed":
            s["closed"] += 1
            if not p.get("closed_reason"):
                s["closed_no_reason"] += 1
            continue
        s["active"] += 1
        dl = p.get("deadline")
        age = _age_days(p.get("last_seen_at"), now)
        if dl and dl < today:
            s["past_deadline"] += 1
            if len(s["examples"]) < 3:
                s["examples"].append({"id": p.get("id"), "why": f"마감일 {dl} 지남", "url": p.get("url")})
        elif age is not None and age > STALE_DAYS:
            s["stale"] += 1
            if len(s["examples"]) < 3:
                s["examples"].append({"id": p.get("id"), "why": f"{age:.0f}일 안 보임", "url": p.get("url")})
    return dict(out)


def jobs_consistency(jobs: list[dict], ledger: dict, today: str) -> dict[str, dict]:
    """사이트별: 화면 파일에서 모집중인데 마감일이 지난 것·원장은 닫았는데 파일은 모집중인 것(내보내기 지연)."""
    out: dict[str, dict] = defaultdict(lambda: {"active": 0, "closed": 0, "past_deadline": 0,
                                                "ledger_closed_but_active": 0, "examples": []})
    for j in jobs:
        s = out[j.get("site") or "?"]
        if j.get("status") == "closed":
            s["closed"] += 1
            continue
        s["active"] += 1
        dl = j.get("deadline_date")
        key = f"{j.get('site')}:{j.get('pid') or j.get('position_id') or ''}"
        if dl and dl < today and j.get("status_source") != "override":
            s["past_deadline"] += 1
            if len(s["examples"]) < 3:
                s["examples"].append({"id": key, "why": f"마감일 {dl} 지남", "url": j.get("url")})
        elif (ledger.get(key) or {}).get("status") == "closed":
            s["ledger_closed_but_active"] += 1
            if len(s["examples"]) < 3:
                s["examples"].append({"id": key, "why": "원장은 마감", "url": j.get("url")})
    return dict(out)


def recheck_backlog(jobs: list[dict], ledger: dict, now: datetime) -> dict[str, dict]:
    """사이트별 재확인 밀림 — 모집중인데 한 번도 안 물어본 것, 주기의 2배를 넘긴 것, 원장의 '불명' 비율."""
    from pipeline.close_check import _recheck_policy
    out: dict[str, dict] = defaultdict(lambda: {"active": 0, "never": 0, "overdue": 0, "unknown": 0})
    for j in jobs:
        if j.get("status") == "closed" or j.get("_ledger_closed"):
            continue
        site = j.get("site") or "?"
        s = out[site]
        s["active"] += 1
        key = f"{site}:{j.get('pid') or ''}"
        entry = ledger.get(key)
        checked = j.get("_checked_at") if "_checked_at" in j else (entry or {}).get("checked_at")
        if (entry or {}).get("status") == "unknown":
            s["unknown"] += 1
        if not checked:
            s["never"] += 1
            continue
        _, every = _recheck_policy(j, entry, now.date())
        age = _age_days(checked, now)
        if age is not None and every and age > every * OVERDUE_FACTOR:
            s["overdue"] += 1
    return dict(out)


# ── 수집 ─────────────────────────────────────────────────────────────────

def freelance_intake(sources: dict, now: datetime) -> dict[str, dict]:
    out = {}
    for site, r in (sources or {}).items():
        age = _age_days(r.get("at"), now)
        out[site] = {"ok": bool(r.get("ok")), "fetched": r.get("fetched") or 0,
                     "age_hours": None if age is None else round(age * 24, 1),
                     "error": r.get("error")}
    return out


def jobs_intake(health: dict | None, now: datetime) -> dict:
    if not health:
        return {"ts": None, "age_hours": None, "site_counts": {}, "anomalies": ["health_latest.json 없음"]}
    age = _age_days(health.get("ts"), now)
    return {"ts": health.get("ts"), "age_hours": None if age is None else round(age * 24, 1),
            "site_counts": health.get("site_counts") or {}, "active": health.get("active"),
            "closed": health.get("closed"), "anomalies": health.get("anomalies") or []}


def crawler_listings(now: datetime, keyword: str = "개발자") -> dict[str, dict]:
    """채용 크롤러가 회차마다 남기는 listed.json(그 회차에 목록에서 본 pid). 나이와 건수가 곧
    '목록을 받아 왔나'다 — 누적본 jobs.json 은 크롤이 죽어도 줄지 않아서 이걸로는 모른다."""
    out = {}
    for d in sorted(SCREENSHOTS_DIR.glob(f"*_{keyword}")):
        doc = _load_json(d / "listed.json")
        if not d.is_dir() or d.name.startswith("all_"):
            continue
        if not isinstance(doc, dict):
            out[d.name.split("_")[0]] = {"listed": 0, "age_hours": None, "note": "listed.json 없음"}
            continue
        age = _age_days(doc.get("at"), now)
        out[d.name.split("_")[0]] = {"listed": len(doc.get("pids") or []),
                                     "age_hours": None if age is None else round(age * 24, 1)}
    return out


def probe_freelance(only: set[str] | None = None) -> dict[str, dict]:
    """외주 소스마다 목록 1쪽을 실제로 받는다. 파일·DB 에는 아무것도 쓰지 않는다."""
    import time
    from crawlers import crawl_freelance as cf
    out = {}
    for site, fetch in cf.SOURCES.items():
        if only and site not in only:
            continue
        t0 = time.time()
        try:
            rows = fetch(1, {})
            ok_fields = sum(1 for r in rows if r.get("title") and r.get("url"))
            out[site] = {"ok": True, "fetched": len(rows), "with_title_url": ok_fields,
                         "active": sum(1 for r in rows if r.get("status") == "active"),
                         "elapsed": round(time.time() - t0, 1)}
        except Exception as e:                                      # noqa: BLE001
            out[site] = {"ok": False, "fetched": 0, "error": f"{e!r}"[:200],
                         "elapsed": round(time.time() - t0, 1)}
    return out


# ── 원본 대조 ────────────────────────────────────────────────────────────

def _sample(rows: list[dict], n: int, rnd: random.Random) -> list[dict]:
    return rnd.sample(rows, n) if len(rows) > n else list(rows)


def summarize_live(results: list[dict]) -> dict:
    """results: {stored: active|closed, got: active|closed|unknown, ...}.
    missed = 우리는 모집중인데 원본은 마감(접수마감을 못 적은 것), wrong_close = 그 반대."""
    asked = len(results)
    answered = [r for r in results if r["got"] in ("active", "closed")]
    return {
        "asked": asked,
        "answered": len(answered),
        "agree": sum(1 for r in answered if r["got"] == r["stored"]),
        "missed": [r for r in answered if r["stored"] == "active" and r["got"] == "closed"],
        "wrong_close": [r for r in answered if r["stored"] == "closed" and r["got"] == "active"],
        "unanswered": [r for r in results if r["got"] not in ("active", "closed")][:5],
    }


# 원본이 마감을 말해 주지 않는 출처 — 판정기는 삭제(404)만 잡는다. 대조해도 '답 없음'만 나온다.
NO_ANSWER_SITES = {"remote": "원본이 마감을 말해 주지 않는다(remoteok·himalayas·wwr) — 삭제(404)만 닫는다"}


def live_jobs(jobs: list[dict], n: int, rnd: random.Random) -> dict[str, dict]:
    from pipeline import close_check as cc
    today = date.today()
    by_site: dict[str, list[dict]] = defaultdict(list)
    for j in jobs:
        by_site[j.get("site") or "?"].append(j)
    out = {}
    for site, rows in sorted(by_site.items()):
        check = cc.CHECKERS.get(site)
        if not check:
            out[site] = {"asked": 0, "note": "판정기 없음"}
            continue
        if site in NO_ANSWER_SITES:
            out[site] = {"asked": 0, "note": NO_ANSWER_SITES[site]}
            continue
        cache: dict = {}
        results = []
        picks = (_sample([j for j in rows if j.get("status") != "closed"], n, rnd)
                 + _sample([j for j in rows if j.get("status") == "closed"], n, rnd))
        for j in picks:
            try:
                v = check(j, today, cache)
                got, reason = v.status, v.reason
            except Exception as e:                                  # noqa: BLE001
                got, reason = "unknown", f"예외: {e!r}"[:120]
            results.append({"id": f"{site}:{j.get('pid')}", "url": j.get("url"),
                            "stored": "closed" if j.get("status") == "closed" else "active",
                            "got": got, "reason": reason})
            cc._sleep()
        out[site] = summarize_live(results)
    return out


def live_freelance(projects: list[dict], n: int, rnd: random.Random) -> dict[str, dict]:
    from crawlers import crawl_freelance as cf
    today = date.today()
    by_site: dict[str, list[dict]] = defaultdict(list)
    for p in projects:
        by_site[p.get("site") or "?"].append(p)
    out = {}
    for site, rows in sorted(by_site.items()):
        if site in ("sism", "freemoa"):
            # SISM 은 약관상 상세를 안 받고(목록에서 빠지면 닫는다), 프리모아는 목록이 마감을 같이 준다.
            out[site] = {"asked": 0, "note": "원본 재확인 없음 — 목록 표기·게재 기간으로 닫는다"}
            continue
        cache: dict = {}
        results = []
        picks = (_sample([p for p in rows if p.get("status") == "active"], n, rnd)
                 + _sample([p for p in rows if p.get("status") == "closed"], n, rnd))
        for p in picks:
            try:
                res = cf._check(dict(p), today, cache)       # 사본 — 점검은 기록을 바꾸지 않는다
                got, reason = (res or ("unknown", "판정 보류"))
            except Exception as e:                                  # noqa: BLE001
                got, reason = "unknown", f"예외: {e!r}"[:120]
            results.append({"id": p.get("id"), "url": p.get("url"), "stored": p.get("status"),
                            "got": got, "reason": reason})
            cf._sleep()
        out[site] = summarize_live(results)
    return out


# ── 판정 ─────────────────────────────────────────────────────────────────

def findings(report: dict) -> list[dict]:
    """보고서에서 사람이 봐야 할 것만 뽑는다. level: FAIL(고장) · WARN(밀림·지연)."""
    f: list[dict] = []

    def add(level: str, area: str, site: str, msg: str) -> None:
        f.append({"level": level, "area": area, "site": site, "msg": msg})

    for area in ("freelance", "jobs"):
        for site, s in (report.get("consistency", {}).get(area) or {}).items():
            if s.get("past_deadline"):
                add("WARN", area, site, f"모집중으로 적혔는데 마감일 지난 것 {s['past_deadline']}건")
            if s.get("stale"):
                add("WARN", area, site, f"모집중인데 {STALE_DAYS}일 넘게 안 보인 것 {s['stale']}건")
            if s.get("ledger_closed_but_active"):
                add("WARN", area, site, f"원장은 마감인데 화면 파일은 모집중 {s['ledger_closed_but_active']}건(내보내기 지연)")
    for site, s in (report.get("consistency", {}).get("recheck") or {}).items():
        if s["active"] and (s["never"] + s["overdue"]) / s["active"] > 0.3:
            add("WARN", "jobs", site, f"재확인 밀림 — 안 물어본 것 {s['never']}·주기 넘긴 것 {s['overdue']} / 모집중 {s['active']}")
        if s["active"] >= 10 and s["unknown"] / s["active"] > 0.5:
            add("WARN", "jobs", site, f"원본이 답을 안 주는 공고 {s['unknown']}/{s['active']} — 접수마감을 못 적는다")

    for site, s in (report.get("intake", {}).get("freelance") or {}).items():
        if not s["ok"]:
            add("FAIL", "freelance", site, f"수집 실패: {s.get('error') or '?'}")
        elif s["fetched"] == 0:
            add("FAIL", "freelance", site, "수집 0건")
        elif s["age_hours"] is not None and s["age_hours"] > INTAKE_STALE_HOURS:
            add("WARN", "freelance", site, f"마지막 수집 {s['age_hours']:.0f}시간 전")
    ji = report.get("intake", {}).get("jobs") or {}
    if ji.get("age_hours") is not None and ji["age_hours"] > INTAKE_STALE_HOURS:
        add("WARN", "jobs", "*", f"마지막 크롤 기록 {ji['age_hours']:.0f}시간 전")
    for site, n in (ji.get("site_counts") or {}).items():
        if not n:
            add("FAIL", "jobs", site, "수집 0건")
    for site, s in (ji.get("listings") or {}).items():
        if not s.get("listed"):
            add("FAIL", "jobs", site, f"마지막 회차에 목록에서 본 공고 0건 ({s.get('note') or '파서·차단 확인'})")
        elif s.get("age_hours") is not None and s["age_hours"] > INTAKE_STALE_HOURS:
            add("WARN", "jobs", site, f"목록을 마지막으로 받은 지 {s['age_hours']:.0f}시간")
    for site, s in (report.get("probe") or {}).items():
        if not s["ok"]:
            add("FAIL", "freelance", site, f"지금 받아 보니 실패: {s.get('error')}")
        elif s["fetched"] == 0:
            add("FAIL", "freelance", site, "지금 받아 보니 0건 — 파서가 깨졌거나 막혔다")
        elif s["with_title_url"] < s["fetched"]:
            add("WARN", "freelance", site, f"제목·링크 빠진 행 {s['fetched'] - s['with_title_url']}/{s['fetched']}")
    for a in ji.get("anomalies") or []:
        add("WARN", "jobs", "*", f"헬스 이상: {a if isinstance(a, str) else json.dumps(a, ensure_ascii=False)}")

    for area in ("freelance", "jobs"):
        for site, s in (report.get("live", {}).get(area) or {}).items():
            if not s.get("asked"):
                continue
            if s["answered"] == 0:
                add("FAIL", area, site, f"원본 대조 {s['asked']}건 모두 답 없음 — 판정기 점검 필요"
                    f" ({(s['unanswered'] or [{}])[0].get('reason', '')})")
            if s.get("missed"):
                add("WARN", area, site, f"원본은 마감인데 우리는 모집중 {len(s['missed'])}건 (예: {s['missed'][0]['id']})")
            if s.get("wrong_close"):
                add("WARN", area, site, f"원본은 모집중인데 우리는 마감 {len(s['wrong_close'])}건 (예: {s['wrong_close'][0]['id']})")
    return f


# ── 실행 ─────────────────────────────────────────────────────────────────

def _jobs_source() -> tuple[list[dict], list[dict], str]:
    """(재확인 대상 = DB 우선, 화면 파일, 출처). 화면 파일은 마감일 비교에 쓴다 — DB 의 job_state 는
    읽는 순간 계산하므로 '마감일 지났는데 모집중'이 생길 수 없고, 생기는 곳은 구워 둔 파일이다."""
    from pipeline.close_check import _source_jobs
    queue, src = _source_jobs(include_closed=True)
    viewer = _load_json(ENRICHED) or []
    return queue, viewer if isinstance(viewer, list) else [], src


def run(live: int = 0, *, probe: bool = False, seed: int | None = None, save: bool = True) -> dict:
    from pipeline.job_status import load_closures
    now = _now()
    today = now.date().isoformat()
    rnd = random.Random(seed)
    fl = _load_json(FREELANCE) or {}
    projects = fl.get("projects") or []
    ledger = (load_closures(force=True) or {}).get("checked") or {}
    queue, viewer_jobs, src = _jobs_source()

    report: dict = {
        "at": now.isoformat(timespec="seconds"),
        "sources": {"jobs_queue": src, "jobs_viewer": str(ENRICHED), "freelance": str(FREELANCE),
                    "freelance_updated_at": fl.get("updated_at")},
        "consistency": {
            "freelance": freelance_consistency(projects, today, now),
            "jobs": jobs_consistency(viewer_jobs, ledger, today),
            "recheck": recheck_backlog(queue, ledger, now),
        },
        "intake": {
            "freelance": freelance_intake(fl.get("sources") or {}, now),
            "jobs": {**jobs_intake(_load_json(HEALTH_LATEST), now), "listings": crawler_listings(now)},
        },
        "live": {},
    }
    if probe:
        report["probe"] = probe_freelance()
    if live > 0:
        report["live"]["jobs"] = live_jobs(queue, live, rnd)
        report["live"]["freelance"] = live_freelance(projects, live, rnd)
    report["findings"] = findings(report)
    report["ok"] = not any(x["level"] == "FAIL" for x in report["findings"])
    if save:
        _save(report)
    return report


def _save(report: dict) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = AUDIT_DIR / "close_audit.json.tmp"
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(AUDIT_DIR / "close_audit.json")
    line = {"at": report["at"], "ok": report["ok"],
            "fail": sum(1 for x in report["findings"] if x["level"] == "FAIL"),
            "warn": sum(1 for x in report["findings"] if x["level"] == "WARN"),
            "live": bool(report["live"])}
    with (AUDIT_DIR / "history.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def print_report(r: dict) -> None:
    print(f"마감·수집 점검 {r['at']}  (공고 대상: {r['sources']['jobs_queue']}, 외주 갱신: {r['sources']['freelance_updated_at']})")
    print("\n[외주] 사이트      모집중  마감  마감일지남  오래안보임 | 마지막 수집")
    intake = r["intake"]["freelance"]
    for site, s in sorted(r["consistency"]["freelance"].items()):
        i = intake.get(site) or {}
        got = f"{i.get('fetched', '-')}건 {i.get('age_hours', '-')}h전" + ("" if i.get("ok", True) else " 실패")
        print(f"  {site:<12} {s['active']:>6} {s['closed']:>5} {s['past_deadline']:>10} {s['stale']:>10} | {got}")
    print("\n[채용] 사이트      모집중  마감  마감일지남  원장마감·파일모집중 | 재확인: 안물음 밀림 불명")
    rc = r["consistency"]["recheck"]
    for site in sorted(set(r["consistency"]["jobs"]) | set(rc)):
        s = r["consistency"]["jobs"].get(site) or {"active": 0, "closed": 0, "past_deadline": 0, "ledger_closed_but_active": 0}
        b = rc.get(site) or {"never": 0, "overdue": 0, "unknown": 0}
        print(f"  {site:<12} {s['active']:>6} {s['closed']:>5} {s['past_deadline']:>10} {s['ledger_closed_but_active']:>18} |"
              f" {b['never']:>6} {b['overdue']:>4} {b['unknown']:>4}")
    ji = r["intake"]["jobs"]
    print(f"  마지막 크롤 기록: {ji.get('ts')} ({ji.get('age_hours')}h 전)")
    print("  목록 수집(listed.json): " + ", ".join(
        f"{k} {v['listed']}건/{v['age_hours']}h" for k, v in (ji.get("listings") or {}).items()))
    if r.get("probe"):
        print("\n[외주 지금 받아 보기] " + ", ".join(
            f"{k} {v['fetched']}건({v['elapsed']}s)" if v["ok"] else f"{k} 실패" for k, v in r["probe"].items()))
    for area, sites in (r.get("live") or {}).items():
        print(f"\n[원본 대조 · {area}] 사이트      물음 답함 일치 놓침 잘못닫음")
        for site, s in sites.items():
            if not s.get("asked"):
                print(f"  {site:<12} {s.get('note', '')}")
                continue
            print(f"  {site:<12} {s['asked']:>4} {s['answered']:>4} {s['agree']:>4} {len(s['missed']):>4} {len(s['wrong_close']):>8}")
    print()
    if not r["findings"]:
        print("이상 없음")
    for x in r["findings"]:
        print(f"  {x['level']:<4} [{x['area']}/{x['site']}] {x['msg']}")
    print(f"\n보고서: {AUDIT_DIR / 'close_audit.json'}")


def main() -> None:
    args = _sys.argv[1:]
    live = int(args[args.index("--live") + 1]) if "--live" in args else 0
    r = run(live, probe="--probe" in args)
    if "--json" in args:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print_report(r)
    raise SystemExit(1 if ("--strict" in args and not r["ok"]) else 0)


if __name__ == "__main__":
    main()
