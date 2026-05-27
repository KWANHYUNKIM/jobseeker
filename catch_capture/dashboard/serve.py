"""대시보드: 최신 all_jobs.json을 찾아 분류해서 data.json 생성 후 정적 서버 띄우기.

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
)


def find_latest_all_dir(keyword: str | None) -> Path | None:
    if not SCREENSHOTS_DIR.exists():
        return None
    pattern = f"all_{keyword}_*" if keyword else "all_*"
    matches = sorted(
        (p for p in SCREENSHOTS_DIR.glob(pattern) if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )
    return matches[0] if matches else None


def enrich_jobs(jobs: list[dict]) -> list[dict]:
    out = []
    for j in jobs:
        company = (j.get("company") or "").strip()
        size, matched = classify_company_size(company)
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


def build_data(keyword: str | None) -> dict:
    src = find_latest_all_dir(keyword)
    if not src:
        print(f"[!] all_{keyword or '*'}_* 폴더를 찾을 수 없음 (아직 크롤 미완?)", flush=True)
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": None,
            "keyword": keyword,
            "jobs": [],
            "stats": compute_stats([]),
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
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}/"
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
