"""외주·프리 프로젝트 ↔ 정본 DB (db/migrations/005_freelance_project.sql).

쓰기:  crawl_freelance 가 모은 행을 project 에 upsert 하고, 목록의 모집 표시가 바뀐
       프로젝트만 project_check 에 한 행 남긴다. 기술은 job 과 같은 tech 사전으로 잇는다.
읽기:  v_project → public/freelance.json (뷰어가 읽는 모양 그대로).

크롤러는 지금 JSON 을 직접 쓰고 여기로 **이중 쓰기** 한다(DB_DUAL_WRITE=0 으로 끈다).
DB 가 없거나 실패해도 크롤 단계는 죽지 않는다 — job 쪽 ingest_crawl 과 같은 약속이다.

    python -m store.freelance ingest                 # public/freelance.json → DB (백필·복구)
    python -m store.freelance export [경로]          # DB → freelance.json
    python -m store.freelance stats
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import hashlib
import json
import os
import re
from datetime import date, datetime
from pathlib import Path

from store.conn import cursor
from store.upsert import upsert_tech

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
JSON_PATH = ROOT_DIR / "jd-viewer" / "public" / "freelance.json"
SITES = ("wanted_gigs", "freemoa", "elancer", "jobkorea", "saramin", "imjob", "sism")
DUR_RE = re.compile(r"(\d+)\s*(?:~\s*\d+\s*)?(일|개월|주)")


def enabled() -> bool:
    return os.environ.get("DB_DUAL_WRITE", "1") != "0"


def duration_days(text: str) -> int | None:
    """'6개월' → 180, '52일' → 52, '4~6개월' → 120(짧은 쪽). 모르면 None."""
    m = DUR_RE.search(text or "")
    if not m:
        return None
    n = int(m.group(1))
    days = n * {"일": 1, "주": 7, "개월": 30}[m.group(2)]
    return days if 1 <= days <= 3650 else None


def _date(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _hash(p: dict) -> str:
    keys = ("title", "category", "kind", "location", "budget", "duration", "start",
            "skills", "career", "summary", "deadline")
    raw = json.dumps({k: p.get(k) for k in keys}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _row(p: dict) -> dict:
    b = p.get("budget") or {}
    lo, hi = b.get("min"), b.get("max")
    if lo and hi and lo > hi:
        lo, hi = hi, lo
    return {
        "site": p["site"], "pid": str(p["pid"]), "url": p["url"], "title": p["title"],
        "category": p.get("category") or "",
        "work_mode": p.get("kind") or None,
        "location_text": p.get("location") or "",
        "budget_basis": b.get("type") if (lo or hi) else None,
        "budget_min": lo or hi, "budget_max": hi or lo,
        "duration_text": p.get("duration") or "",
        "duration_days": duration_days(p.get("duration") or ""),
        "start_text": p.get("start") or "",
        "career_text": p.get("career") or "",
        "summary": p.get("summary") or "",
        "tags": list(p.get("tags") or []),
        "applicants": p.get("applicants"),
        "deadline_on": _date(p.get("deadline")),
        "posted_on": _date(p.get("posted_date")),
        "source_open": p.get("status") != "closed",
        "content_hash": _hash(p),
        # 007 — pipeline/freelance_rates.classify 가 붙인 분류
        "grade": p.get("grade"), "grade_basis": p.get("grade_basis"), "domain": p.get("domain"),
        "work_type": p.get("work_type"), "role": p.get("role"),
        "seen_at": p.get("last_seen_at") or datetime.now().astimezone().isoformat(),
        "first_seen_at": p.get("first_seen_at") or p.get("last_seen_at"),
    }


UPSERT_SQL = """
INSERT INTO project (site, pid, url, title, category, work_mode, location_text,
                     budget_basis, budget_min, budget_max, duration_text, duration_days,
                     start_text, career_text, summary, tags, applicants, deadline_on, posted_on,
                     source_open, content_hash, first_seen_at, last_seen_at,
                     grade, grade_basis, domain, work_type, role)
VALUES (%(site)s, %(pid)s, %(url)s, %(title)s, %(category)s, %(work_mode)s, %(location_text)s,
        %(budget_basis)s, %(budget_min)s, %(budget_max)s, %(duration_text)s, %(duration_days)s,
        %(start_text)s, %(career_text)s, %(summary)s, %(tags)s, %(applicants)s, %(deadline_on)s,
        %(posted_on)s, %(source_open)s, %(content_hash)s,
        COALESCE(%(first_seen_at)s::timestamptz, %(seen_at)s::timestamptz), %(seen_at)s,
        %(grade)s, %(grade_basis)s, %(domain)s, %(work_type)s, %(role)s)
ON CONFLICT (site, pid) DO UPDATE SET
    url = EXCLUDED.url, title = EXCLUDED.title, category = EXCLUDED.category,
    work_mode = EXCLUDED.work_mode, location_text = EXCLUDED.location_text,
    budget_basis = EXCLUDED.budget_basis, budget_min = EXCLUDED.budget_min,
    budget_max = EXCLUDED.budget_max, duration_text = EXCLUDED.duration_text,
    duration_days = EXCLUDED.duration_days, start_text = EXCLUDED.start_text,
    career_text = EXCLUDED.career_text, summary = EXCLUDED.summary, tags = EXCLUDED.tags,
    applicants = EXCLUDED.applicants,
    -- 목록이 마감일을 잠깐 빠뜨려도 알던 값을 지우지 않는다.
    deadline_on = COALESCE(EXCLUDED.deadline_on, project.deadline_on),
    posted_on = COALESCE(EXCLUDED.posted_on, project.posted_on),
    source_open = EXCLUDED.source_open, content_hash = EXCLUDED.content_hash,
    first_seen_at = LEAST(project.first_seen_at, EXCLUDED.first_seen_at),
    last_seen_at = GREATEST(project.last_seen_at, EXCLUDED.last_seen_at),
    grade = EXCLUDED.grade, grade_basis = EXCLUDED.grade_basis, domain = EXCLUDED.domain,
    work_type = EXCLUDED.work_type, role = EXCLUDED.role
RETURNING id, (xmax = 0) AS inserted
"""


def ingest(projects: list[dict]) -> dict:
    """행 목록 → DB. 반환: {'upserted','inserted','checks','skipped'}."""
    stats = {"upserted": 0, "inserted": 0, "checks": 0, "skipped": 0}
    tech_cache: dict = {}
    with cursor() as cur:
        for p in projects:
            if p.get("site") not in SITES or not (p.get("title") or "").strip():
                stats["skipped"] += 1
                continue
            row = _row(p)
            # 한 행이 제약에 걸려도 회차 전체를 되돌리지 않는다(ingest_crawl 과 같은 약속).
            # 걸린 행은 세고 넘긴다 — 파서 사고의 신호라 숫자로 남아야 한다.
            try:
                with cur.connection.transaction():
                    cur.execute(UPSERT_SQL, row)
                    r = cur.fetchone()
            except Exception as e:                                   # noqa: BLE001
                stats["rejected"] = stats.get("rejected", 0) + 1
                if stats["rejected"] <= 3:
                    print(f"  [freelance] 거부 {p['site']}:{p['pid']} — {str(e).splitlines()[0][:120]}", flush=True)
                continue
            pid, inserted = r["id"], r["inserted"]
            stats["upserted"] += 1
            stats["inserted"] += int(inserted)

            # 기술 — 이번 목록이 말한 집합으로 바꾼다.
            ids = {t for t in (upsert_tech(cur, s, cache=tech_cache) for s in p.get("skills") or []) if t}
            cur.execute("DELETE FROM project_tech WHERE project_id = %s", (pid,))
            for tid in ids:
                cur.execute("INSERT INTO project_tech (project_id, tech_id) VALUES (%s, %s) "
                            "ON CONFLICT DO NOTHING", (pid, tid))

            # 모집 표시가 바뀐 때만 원장에 남긴다(처음 본 것도 한 줄 — 출발점).
            # 재확인(목록에서 빠진 것을 원본에 물음)에서 왔으면 그 시각과 근거를 쓴다.
            closed = not row["source_open"]
            at = max(p.get("checked_at") or "", row["seen_at"])     # ISO 문자열 — 사전순이 곧 시간순
            reason = p.get("closed_reason") if closed else None
            cur.execute("SELECT closed FROM project_check_latest WHERE project_id = %s", (pid,))
            last = cur.fetchone()
            if last is None or last["closed"] != closed:
                cur.execute(
                    "INSERT INTO project_check (project_id, checked_at, closed, deadline_on, evidence) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (pid, at, closed, row["deadline_on"],
                     reason or ("목록 모집 표시: " + ("마감" if closed else "모집중"))),
                )
                stats["checks"] += 1

            # 단가 이력(006). 단가·기간·모집 표시가 직전 버전과 다를 때만 한 행.
            cur.execute("SELECT budget_basis::text AS b, budget_min, budget_max, duration_days, source_open "
                        "FROM project_version WHERE project_id = %s ORDER BY seen_at DESC LIMIT 1", (pid,))
            lv = cur.fetchone()
            cur_v = (row["budget_basis"], row["budget_min"], row["budget_max"],
                     row["duration_days"], row["source_open"])
            if lv is None or (lv["b"], lv["budget_min"], lv["budget_max"],
                              lv["duration_days"], lv["source_open"]) != cur_v:
                cur.execute(
                    "INSERT INTO project_version (project_id, seen_at, budget_basis, budget_min, budget_max, "
                    "duration_days, source_open, applicants, reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (pid, at, *cur_v[:4], row["source_open"], row["applicants"], reason),
                )
                stats["versions"] = stats.get("versions", 0) + 1
    return stats


def dual_write(projects: list[dict]) -> dict | None:
    """크롤러가 부른다. 꺼져 있거나 실패하면 None — 사이클은 계속 간다."""
    if not enabled():
        return None
    try:
        return ingest(projects)
    except Exception as e:                                           # noqa: BLE001
        print(f"  [freelance] DB 기록 실패 — JSON 에는 남았습니다: {str(e)[:160]}", flush=True)
        return None


def write_snapshot(snap: dict) -> int:
    """그날의 현재 단가표(freelance_rates.snapshot) → project_rate_snapshot(008). 같은 날이면 바꾼다."""
    rows = [(snap["date"], g, c, s["n"], s.get("p25"), s.get("median"), s.get("p75"))
            for g, cols in (snap.get("cells") or {}).items() for c, s in cols.items()]
    with cursor() as cur:
        cur.execute("DELETE FROM project_rate_snapshot WHERE day = %s", (snap["date"],))
        for r in rows:
            cur.execute("INSERT INTO project_rate_snapshot (day, grade, col, n, p25, median, p75) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s)", r)
    return len(rows)


def dual_write_snapshot(snap: dict) -> int | None:
    if not enabled():
        return None
    try:
        return write_snapshot(snap)
    except Exception as e:                                           # noqa: BLE001
        print(f"  [freelance] 단가표 스냅숏 DB 기록 실패: {str(e)[:160]}", flush=True)
        return None


def export(path: Path = JSON_PATH) -> int:
    """v_project → 뷰어 JSON. 크롤러가 쓰는 것과 같은 모양(site·pid·budget{…}·status…)."""
    with cursor(autocommit=True) as cur:
        cur.execute("SELECT * FROM v_project ORDER BY COALESCE(posted_on, first_seen_at::date) DESC, id DESC")
        rows = cur.fetchall()
        # 세부 내역(화면의 '세부 내역' 표)과 닫힌 근거.
        cur.execute("SELECT project_id, seen_at, budget_basis::text AS b, budget_min, budget_max, "
                    "duration_days, source_open, applicants FROM project_version ORDER BY project_id, seen_at")
        hist: dict = {}
        for v in cur.fetchall():
            hist.setdefault(v["project_id"], []).append({
                "at": v["seen_at"].isoformat(),
                "budget": {"type": v["b"], "min": v["budget_min"], "max": v["budget_max"]} if v["b"] else None,
                "status": "active" if v["source_open"] else "closed",
                "duration": f"{v['duration_days']}일" if v["duration_days"] else "",
                "applicants": v["applicants"],
            })
        cur.execute("SELECT project_id, evidence FROM project_check_latest WHERE closed")
        reasons = {r["project_id"]: r["evidence"] for r in cur.fetchall()}
    projects = []
    for r in rows:
        budget = ({"type": r["budget_basis"], "min": r["budget_min"], "max": r["budget_max"]}
                  if r["budget_basis"] else None)
        projects.append({
            "id": f"{r['site']}:{r['pid']}", "site": r["site"], "pid": r["pid"], "url": r["url"],
            "title": r["title"], "category": r["category"], "kind": r["work_mode"] or "",
            "location": r["location_text"], "budget": budget, "duration": r["duration_text"],
            "start": r["start_text"], "skills": list(r["skills"] or []), "career": r["career_text"],
            "posted_date": r["posted_on"].isoformat() if r["posted_on"] else None,
            "deadline": r["deadline_on"].isoformat() if r["deadline_on"] else None,
            "applicants": r["applicants"], "summary": r["summary"], "tags": list(r["tags"] or []),
            # 화면은 active/closed 만 안다. stale 은 last_seen_at 으로 화면이 다시 가린다.
            "status": "closed" if r["status"] == "closed" else "active",
            "closed_reason": reasons.get(r["id"]),
            "history": hist.get(r["id"], [])[-30:],
            "first_seen_at": r["first_seen_at"].isoformat(), "last_seen_at": r["last_seen_at"].isoformat(),
        })
    prev = {}
    try:
        prev = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    out = {"updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "sources": prev.get("sources") or {}, "started_at": prev.get("started_at"),
           # 추이는 크롤러가 계산해 둔 것을 잇는다(DB 판은 project_pay_weekly·project_budget_move).
           "trend": prev.get("trend"), "source_of_truth": "db", "projects": projects}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return len(projects)


def stats() -> dict:
    with cursor(autocommit=True) as cur:
        cur.execute("SELECT s.status::text AS status, p.site::text AS site, count(*) AS n "
                    "FROM project p JOIN project_state s ON s.project_id = p.id GROUP BY 1, 2 ORDER BY 2, 1")
        by = [dict(r) for r in cur.fetchall()]
        cur.execute("""
            SELECT t.name, count(*) AS n,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY (p.budget_min + p.budget_max) / 2.0) AS median_monthly
              FROM project p JOIN project_state s ON s.project_id = p.id
              JOIN project_tech pt ON pt.project_id = p.id JOIN tech t ON t.id = pt.tech_id
             WHERE s.status = 'active' AND p.budget_basis = 'monthly' AND NOT t.is_noise
             GROUP BY t.name HAVING count(*) >= 3 ORDER BY n DESC LIMIT 15""")
        pay = [dict(r) for r in cur.fetchall()]
    return {"by_status": by, "monthly_pay_by_tech": pay}


def main() -> None:
    args = _sys.argv[1:]
    cmd = args[0] if args else "stats"
    if cmd == "ingest":
        src = Path(args[1]) if len(args) > 1 else JSON_PATH
        doc = json.loads(src.read_text(encoding="utf-8"))
        print(ingest(doc.get("projects") or []))
    elif cmd == "export":
        n = export(Path(args[1]) if len(args) > 1 else JSON_PATH)
        print(f"{n}건 → {args[1] if len(args) > 1 else JSON_PATH}")
    elif cmd == "stats":
        print(json.dumps(stats(), ensure_ascii=False, indent=1, default=str))
    else:
        print(__doc__)
        _sys.exit(2)


if __name__ == "__main__":
    main()
