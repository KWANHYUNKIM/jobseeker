"""통계 대시보드(8765): 모집중 공고를 분류해 data.json 을 만들고 정적 서버를 띄운다.

공고는 정본 DB(v_job, 모집중·사이트 간 중복 제외)에서 읽는다 — 뷰어·뷰어 API 와 같은
모집단이다. 직군·회사 규모도 뷰어 칩과 같은 값(job_facet)을 쓴다. DB 에 못 붙으면
예전처럼 가장 최근 크롤 스냅샷(screenshots/all_<키워드>_*/all_jobs.json)으로 물러선다.

사용법:
    python dashboard/serve.py                # 8765 포트, 키워드 자동
    python dashboard/serve.py --port 9000
    python dashboard/serve.py --keyword 백엔드
    python dashboard/serve.py --build-only   # 서버 안 띄움
"""
from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import sys
import webbrowser
from collections import Counter
from datetime import datetime
from pathlib import Path

DASHBOARD_DIR = Path(__file__).parent.resolve()
CATCH_DIR = DASHBOARD_DIR.parent
SCREENSHOTS_DIR = CATCH_DIR / "screenshots"

sys.path.insert(0, str(DASHBOARD_DIR))
from classifier import (
    classify_company_size,
    classify_dev_roles,
    extract_competencies,
    extract_headcount,
    extract_revenue_eok,
)


def find_latest_all_dir(keyword: str | None) -> Path | None:
    if not SCREENSHOTS_DIR.exists():
        return None
    pattern = f"all_{keyword}_*" if keyword else "all_*"
    matches = sorted(
        (p for p in SCREENSHOTS_DIR.glob(pattern)
         if p.is_dir() and not p.name.endswith("_latest")),  # all_<kw>_latest 심볼릭링크 제외
        key=lambda p: p.name,
        reverse=True,
    )
    return matches[0] if matches else None


def load_db_jobs() -> tuple[list[dict], dict[tuple[str, str], dict]] | None:
    """정본 DB 의 모집중 공고와 그 필터 축(직군·규모). 못 읽으면 None."""
    try:
        sys.path.insert(0, str(CATCH_DIR))
        from store.db import conn
        from store.jobs.export import fetch_jobs
        jobs = [j for j in fetch_jobs() if j.get("status") == "active"]
        with conn.cursor(autocommit=True) as cur:
            cur.execute("SELECT j.site::text AS site, j.pid, f.roles, f.company_size "
                        "FROM job j JOIN job_facet f ON f.job_id = j.id")
            facets = {(r["site"], r["pid"]): r for r in cur.fetchall()}
        return (jobs, facets) if jobs else None
    except Exception as e:                                          # noqa: BLE001
        print(f"[!] 정본 DB 를 못 읽어 크롤 스냅샷으로 물러섭니다: {e}", flush=True)
        return None


def enrich_jobs(jobs: list[dict], facets: dict[tuple[str, str], dict] | None = None) -> list[dict]:
    """규모·직군·역량을 단다. facets(job_facet)가 있으면 직군·규모는 그 값 — 뷰어와 같은 판정."""
    out = []
    for j in jobs:
        company = (j.get("company") or "").strip()
        size_text = " ".join([
            j.get("full_jd") or "", j.get("benefits") or "",
            j.get("qualifications") or "", j.get("preferences") or "",
        ])
        size, matched = classify_company_size(
            company,
            extract_headcount(size_text),
            extract_revenue_eok(size_text),
        )
        roles = classify_dev_roles(
            title=j.get("title") or "",
            tech_tags=j.get("tech_tags") or [],
            tech_stack=j.get("tech_stack") or [],
            extra_text=(j.get("qualifications") or "")[:500],
        )
        comp_text = " ".join([
            j.get("qualifications") or "",
            j.get("preferences") or "",
            j.get("main_tasks") or "",
        ])
        competencies = extract_competencies(comp_text)
        f = (facets or {}).get((j.get("site") or "", j.get("pid") or ""))
        if f:
            roles = list(f["roles"] or roles)
            if f["company_size"]:
                size, matched = f["company_size"], "job_facet"
        out.append({
            "site": j.get("site") or "",
            "company": company,
            "company_size": size,
            "company_size_matched": matched,
            "title": j.get("title") or "",
            "url": j.get("url") or j.get("href") or "",
            "career": j.get("career") or "",
            "location": j.get("location") or "",
            "dday": j.get("dday") or "",
            "tech_stack": j.get("tech_stack") or [],
            "tech_tags": j.get("tech_tags") or [],
            "roles": roles,
            "competencies": competencies,
            "qualifications": j.get("qualifications") or "",
            "preferences": j.get("preferences") or "",
            "main_tasks": j.get("main_tasks") or "",
            "benefits": j.get("benefits") or "",
        })
    return out


def compute_stats(jobs: list[dict]) -> dict:
    """대시보드용 사전 집계 (모든 차트는 클라이언트에서 다시 계산하지만,
    기본 카드용 숫자만 미리 뽑아둠)."""
    total = len(jobs)
    by_size: Counter = Counter()
    by_role: Counter = Counter()
    by_site: Counter = Counter()
    tech_counter: Counter = Counter()
    for j in jobs:
        by_size[j["company_size"]] += 1
        for r in j["roles"]:
            by_role[r] += 1
        by_site[j["site"] or "unknown"] += 1
        for t in j["tech_stack"]:
            tech_counter[t] += 1
    return {
        "total": total,
        "by_size": dict(by_size),
        "by_role": dict(by_role),
        "by_site": dict(by_site),
        "top_tech": tech_counter.most_common(30),
    }


def load_history(limit: int = 200) -> list[dict]:
    """수집 이력 — 정본 DB(crawl_run) 우선, 못 읽으면 health_history.jsonl.

    읽기는 monitoring.health.history 하나로 한다(8770 운영 대시보드와 같은 값).
    같은 ts 가 여러 줄이면 마지막 것만 남기고, 차트·표에 필요한 필드만 추린다.
    """
    sys.path.insert(0, str(CATCH_DIR))
    from monitoring.health import history

    by_ts: dict[str, dict] = {}
    for r in history(None, 0):
        ts = r.get("ts")
        if not ts:
            continue
        by_ts[ts] = {
            "ts": ts,
            "keyword": r.get("keyword"),
            "raw_total": r.get("raw_total", 0),
            "deduped": r.get("deduped", 0),
            "active": r.get("active", 0),
            "closed": r.get("closed", 0),
            "site_counts": r.get("site_counts", {}),
            "anomalies": r.get("anomalies", []),
        }
    rows = sorted(by_ts.values(), key=lambda r: r["ts"])
    return rows[-limit:]


def build_data(keyword: str | None) -> dict:
    db = load_db_jobs()
    if db:
        jobs = enrich_jobs(*db)
        print(f"[*] 원본: 정본 DB — 모집중 {len(jobs):,}건", flush=True)
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": "정본 DB(v_job)",
            "keyword": None,
            "jobs": jobs,
            "stats": compute_stats(jobs),
            "history": load_history(),
        }

    src = find_latest_all_dir(keyword)
    if not src:
        print(f"[!] all_{keyword or '*'}_* 폴더를 찾을 수 없음 (아직 크롤 미완?)", flush=True)
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": None,
            "keyword": keyword,
            "jobs": [],
            "stats": compute_stats([]),
            "history": load_history(),
        }
    all_jobs_file = src / "all_jobs.json"
    if not all_jobs_file.exists():
        print(f"[!] {all_jobs_file} 없음", flush=True)
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(src.relative_to(CATCH_DIR)),
            "keyword": keyword,
            "jobs": [],
            "stats": compute_stats([]),
            "history": load_history(),
        }
    raw = json.loads(all_jobs_file.read_text(encoding="utf-8"))
    jobs = enrich_jobs(raw)
    print(f"[*] 원본: {all_jobs_file.relative_to(CATCH_DIR)}", flush=True)
    print(f"[*] {len(jobs)}건 enrich 완료", flush=True)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_dir": str(src.relative_to(CATCH_DIR)),
        "keyword": keyword,
        "jobs": jobs,
        "stats": compute_stats(jobs),
        "history": load_history(),
    }


def write_data(data: dict) -> Path:
    out = DASHBOARD_DIR / "data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def serve(port: int) -> None:
    handler = http.server.SimpleHTTPRequestHandler
    handler.extensions_map.update({".json": "application/json; charset=utf-8"})
    socketserver.TCPServer.allow_reuse_address = True
    import os
    os.chdir(str(DASHBOARD_DIR))
    # 기본은 loopback(안전). 터널 컨테이너가 붙는 배포에서는 DASH_HOST=0.0.0.0.
    host = os.environ.get("DASH_HOST", "127.0.0.1")
    with socketserver.TCPServer((host, port), handler) as httpd:
        url = f"http://{host}:{port}/"
        print(f"\n[*] 대시보드: {url}", flush=True)
        print("[*] Ctrl+C 로 종료", flush=True)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[*] 종료", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", default=None, help="키워드 필터 (없으면 모든 all_* 중 최신)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--build-only", action="store_true")
    args = ap.parse_args()

    data = build_data(args.keyword)
    out = write_data(data)
    print(f"[*] data.json 작성: {out.relative_to(CATCH_DIR)}", flush=True)
    print(f"    총 {data['stats']['total']}건  /  규모 {data['stats']['by_size']}", flush=True)
    print(f"    직군 {data['stats']['by_role']}", flush=True)

    if args.build_only:
        return
    serve(args.port)


if __name__ == "__main__":
    main()
