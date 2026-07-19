"""해외/원격 채용 보드 통합 크롤러 → 표준 jobs.json 스키마로 누적 저장.

세 소스를 순수 HTTP(jobs_common.http_get)로 긁는다(브라우저 불필요):
  - RemoteOK       : 공개 JSON API (https://remoteok.com/api)
  - We Work Remotely : 프로그래밍 카테고리 RSS
  - Himalayas      : 공개 JSON API (https://himalayas.app/jobs/api)

기존 국내 크롤러와 동일한 계약을 따른다:
  - 인자:   python -m crawlers.crawl_remote <keyword> <target> [depth]
            (keyword 는 폴더명 통일을 위해 받되, 해외 보드는 영어라 개발직군
             필터 is_developer_job 으로 거른다. keyword 자체로는 검색하지 않음)
  - 출력:   screenshots/remote_<keyword>/  (fixed_out_dir, 누적)
  - dedup:  pid = "<source>:<id>" 로 이전 수집분과 중복 스킵
  - 종료 코드/차단: HTTP 실패는 block_detect 로 백오프 신호

사용법:
    python -m crawlers.crawl_remote 개발자 50
    python -m crawlers.crawl_remote 개발자 100 3     # depth=소스당 추가 페이지(himalayas)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from crawlers import block_detect
from crawlers.jobs_common import (
    build_jd_sections,
    extract_tech_stack,
    fixed_out_dir,
    html_to_text,
    http_get,
    is_developer_job,
    jitter,
    load_existing_jobs,
    load_seen_pids,
    sanitize_filename,
    save_jobs_json,
)

SITE = "remote"
# 이 소스들은 키워드와 무관(영어 보드 전체를 훑음)하므로 출력 폴더를 고정한다.
# crawl_all 이 키워드마다 호출해도 항상 같은 누적 폴더(remote_개발자)에 쌓인다.
PIN_KEYWORD = "개발자"
FRESH_SECS = 1200  # 최근 이 시간 내 갱신됐으면 이번 호출은 스킵(멀티키워드 중복 호출 방지)

REMOTEOK_API = "https://remoteok.com/api"
WWR_RSS = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
HIMALAYAS_API = "https://himalayas.app/jobs/api?limit=100&offset={offset}"
HIMALAYAS_PAGE = 20  # API가 요청 limit과 무관하게 페이지당 최대 ~20건만 반환


def _clean(text: str, limit: int = 12000) -> str:
    return (text or "").strip()[:limit]


def _fetch_json(url: str) -> object:
    raw = http_get(url, timeout=30)
    return json.loads(raw.decode("utf-8", "ignore"))


# ---------------------------------------------------------------- RemoteOK
def fetch_remoteok() -> list[dict]:
    """RemoteOK API → 정규화 후보 리스트. 첫 원소는 법적 고지라 건너뛴다."""
    rows = _fetch_json(REMOTEOK_API)
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict) or "position" not in r:
            continue  # legal notice row
        tags = r.get("tags") or []
        desc = html_to_text(r.get("description") or "")
        out.append({
            "source": "remoteok",
            "ext_id": str(r.get("id") or r.get("slug") or ""),
            "title": (r.get("position") or "").strip(),
            "company": (r.get("company") or "").strip(),
            "url": r.get("url") or r.get("apply_url") or "",
            "location": (r.get("location") or "").strip() or "Remote",
            "category": ", ".join(tags[:6]),
            "tags": tags,
            "full_jd": _clean(desc),
        })
    return out


# ---------------------------------------------------------- We Work Remotely
def fetch_wwr() -> list[dict]:
    """We Work Remotely 프로그래밍 RSS → 정규화 후보 리스트."""
    raw = http_get(WWR_RSS, timeout=30).decode("utf-8", "ignore")
    root = ET.fromstring(raw)
    out: list[dict] = []
    for item in root.iter("item"):
        title_raw = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = html_to_text(item.findtext("description") or "")
        region = (item.findtext("region") or "").strip()
        # WWR 제목 형식: "Company: Job Title"
        if ":" in title_raw:
            company, title = title_raw.split(":", 1)
        else:
            company, title = "", title_raw
        guid = (item.findtext("guid") or link).strip()
        out.append({
            "source": "wwr",
            "ext_id": guid.rsplit("/", 1)[-1] or guid,
            "title": title.strip(),
            "company": company.strip(),
            "url": link,
            "location": region or "Remote",
            "category": "programming",
            "tags": [],
            "full_jd": _clean(desc),
        })
    return out


# ---------------------------------------------------------------- Himalayas
def fetch_himalayas(pages: int) -> list[dict]:
    """Himalayas API → 정규화 후보 리스트. pages 만큼 offset 페이지네이션."""
    out: list[dict] = []
    for p in range(max(1, pages)):
        data = _fetch_json(HIMALAYAS_API.format(offset=p * HIMALAYAS_PAGE))
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not jobs:
            break
        for j in jobs:
            cats = j.get("categories") or []
            locs = j.get("locationRestrictions") or []
            desc = html_to_text(j.get("description") or j.get("excerpt") or "")
            out.append({
                "source": "himalayas",
                "ext_id": str(j.get("guid") or j.get("applicationLink") or "").rsplit("/", 1)[-1],
                "title": (j.get("title") or "").strip(),
                "company": (j.get("companyName") or "").strip(),
                "url": j.get("applicationLink") or "",
                "location": ", ".join(locs) if locs else "Remote",
                "category": ", ".join(cats[:6]),
                "tags": cats,
                "full_jd": _clean(desc),
            })
        if len(jobs) < HIMALAYAS_PAGE:
            break
        time.sleep(jitter(800) / 1000)
    return out


SOURCES = {
    "remoteok": lambda depth: fetch_remoteok(),
    "wwr": lambda depth: fetch_wwr(),
    "himalayas": lambda depth: fetch_himalayas(pages=max(1, depth or 1)),
}


def crawl(keyword: str, target: int, depth: int) -> None:
    base_dir = Path(__file__).resolve().parent.parent
    out_dir = fixed_out_dir(base_dir, SITE, PIN_KEYWORD)  # 키워드 무관, 고정 폴더
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] 저장 경로(누적): {out_dir}", flush=True)

    # 멀티키워드 사이클에서 같은 해외 보드를 반복 호출하지 않도록 신선도 가드.
    jobs_json = out_dir / "jobs.json"
    if jobs_json.exists() and (time.time() - jobs_json.stat().st_mtime) < FRESH_SECS:
        age = int(time.time() - jobs_json.stat().st_mtime)
        print(f"[*] 최근 {age}s 전 갱신됨(<{FRESH_SECS}s) — 이번 호출 스킵", flush=True)
        return

    collected: list[dict] = load_existing_jobs(out_dir)
    base_count = len(collected)
    seen = load_seen_pids(base_dir, SITE)
    for j in collected:
        if j.get("pid"):
            seen.add(str(j["pid"]).strip())
    print(f"[*] 기존 수집 {base_count}건 / 이전 PID {len(seen)}개(중복 스킵 대상)", flush=True)

    blocked_any = False
    scanned = skipped_dup = skipped_nondev = 0
    for name, fetch in SOURCES.items():
        if len(collected) - base_count >= target:
            break
        print(f"\n----- 소스: {name} -----", flush=True)
        try:
            candidates = fetch(depth)
        except Exception as exc:
            reason, code = block_detect.from_http_error(exc)
            if reason:
                block_detect.report(SITE, reason, code, detail=name)
                print(f"[!] {name} 차단/실패({reason}) → 스킵", flush=True)
                blocked_any = True
            else:
                print(f"[!] {name} 실패: {exc}", flush=True)
            continue
        print(f"[*] {name} 후보 {len(candidates)}건", flush=True)

        for c in candidates:
            if len(collected) - base_count >= target:
                break
            scanned += 1
            pid = f"{c['source']}:{c['ext_id']}"
            if not c["ext_id"] or pid in seen:
                skipped_dup += 1
                continue
            # 제목만으로 개발직 판정 — RemoteOK 등은 태그가 부정확해 오탐을 유발한다.
            if not is_developer_job(c["title"]):
                skipped_nondev += 1
                continue

            full_jd = c["full_jd"]
            tech = extract_tech_stack(f"{c['title']}\n{full_jd}\n{' '.join(c.get('tags') or [])}")
            jd_parts = build_jd_sections(None, full_jd)

            idx = len(collected) + 1
            label = f"{c['company']}_{c['title']}".strip("_")
            base_name = f"{idx:02d}_{sanitize_filename(label)}"
            lines = [
                f"회사: {c['company']}",
                f"제목: {c['title']}",
                f"URL: {c['url']}",
                f"출처: {c['source']}",
                "",
                "[조건]",
                f"위치: {c['location']}",
                "",
                "[직무 카테고리]",
                c.get("category") or "(없음)",
                "",
                "[기술스택]",
                ", ".join(tech) if tech else "(JD에서 식별된 기술스택 없음)",
                "",
                "[채용 상세]",
                full_jd or "(상세 내용을 가져오지 못함)",
            ]
            (out_dir / f"{base_name}.txt").write_text("\n".join(lines), encoding="utf-8")
            collected.append({
                "idx": idx,
                "pid": pid,
                "position_id": pid,
                "source_board": c["source"],
                "company": c["company"],
                "title": c["title"],
                "url": c["url"],
                "category": c.get("category", ""),
                "location": c["location"],
                "reward": "",
                "skills": c.get("tags") or [],
                "tech_stack": tech,
                "main_tasks": jd_parts.get("main_tasks", ""),
                "qualifications": jd_parts.get("qualifications", ""),
                "preferences": jd_parts.get("preferences", ""),
                "tech_stack_raw": jd_parts.get("tech_stack_raw", ""),
                "benefits": jd_parts.get("benefits", ""),
                "full_jd": full_jd,
                "txt": f"{base_name}.txt",
                "overseas": True,
            })
            seen.add(pid)
            save_jobs_json(out_dir, collected)
        print(f"[*] {name} 완료 — 누적 {len(collected)}건 (이번 신규 {len(collected) - base_count})", flush=True)

    save_jobs_json(out_dir, collected)
    if not blocked_any:
        block_detect.note_success(SITE)
    print(
        f"\n[완료] 수집 {len(collected)} (신규 {len(collected) - base_count}) / "
        f"중복 {skipped_dup} / 비개발 {skipped_nondev} / 훑음 {scanned}",
        flush=True,
    )
    print(f"[결과 위치] {out_dir}", flush=True)


def main() -> None:
    args = sys.argv[1:]
    keyword = args[0] if len(args) > 0 else "개발자"
    target = int(args[1]) if len(args) > 1 else 50
    depth = int(args[2]) if len(args) > 2 else 2
    crawl(keyword, target, depth)


if __name__ == "__main__":
    main()
