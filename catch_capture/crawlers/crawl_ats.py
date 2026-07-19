"""회사 자체 채용페이지(ATS) 통합 크롤러 → 표준 jobs.json 스키마로 누적 저장.

대기업/스타트업 다수가 채용을 Greenhouse·Lever·Ashby 같은 ATS의 공개 JSON
API로 노출한다. `ats_boards.json` 의 (provider, slug, company) 목록을 받아
각 보드에서 개발직군만 골라 수집한다. 브라우저 불필요(순수 HTTP).

기존 국내 크롤러와 동일한 계약:
  - 인자:   python -m crawlers.crawl_ats <keyword> <target> [per_board]
            keyword 는 폴더명 통일용(영어 공고라 is_developer_job 으로 거른다).
            target = 이번 실행에서 수집할 신규 공고 총량(전 보드 합산).
            per_board = 회사당 이번 실행 신규 상한(기본 6, 다양성 확보용).
  - 출력:   screenshots/ats_<keyword>/  (fixed_out_dir, 누적)
  - dedup:  pid = "<provider>:<slug>:<job_id>"

보드는 매 실행 무작위 순서로 돌아, 사이클마다 다른 회사들이 우선 채워진다.

사용법:
    python -m crawlers.crawl_ats 개발자 100
    python -m crawlers.crawl_ats 개발자 200 10
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import html as _html
import json
import random
import sys
import time
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

SITE = "ats"
CONFIG = Path(__file__).resolve().parent / "ats_boards.json"
# 키워드 무관(회사 보드 전체를 훑음) → 출력 폴더 고정 + 신선도 가드.
PIN_KEYWORD = "개발자"
FRESH_SECS = 1200

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER = "https://api.lever.co/v0/postings/{slug}?mode=json"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def _clean(text: str, limit: int = 16000) -> str:
    return (text or "").strip()[:limit]


def _fetch_json(url: str) -> object:
    return json.loads(http_get(url, timeout=30).decode("utf-8", "ignore"))


# ---- provider 별 파서: 공통 후보 dict 리스트로 정규화 --------------------
def _from_greenhouse(slug: str, company: str) -> list[dict]:
    data = _fetch_json(GREENHOUSE.format(slug=slug))
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        depts = ", ".join(d.get("name", "") for d in (j.get("departments") or []))
        content = html_to_text(_html.unescape(j.get("content") or ""))
        out.append({
            "ext_id": str(j.get("id")),
            "title": (j.get("title") or "").strip(),
            "company": company,
            "url": j.get("absolute_url") or "",
            "location": loc or "—",
            "category": depts,
            "full_jd": _clean(content),
        })
    return out


def _from_lever(slug: str, company: str) -> list[dict]:
    data = _fetch_json(LEVER.format(slug=slug))
    out = []
    for j in data:
        cat = j.get("categories") or {}
        desc = j.get("descriptionPlain") or html_to_text(j.get("description") or "")
        extra = j.get("additionalPlain") or ""
        out.append({
            "ext_id": str(j.get("id")),
            "title": (j.get("text") or "").strip(),
            "company": company,
            "url": j.get("hostedUrl") or j.get("applyUrl") or "",
            "location": cat.get("location") or j.get("country") or "—",
            "category": ", ".join(x for x in (cat.get("department"), cat.get("team")) if x),
            "full_jd": _clean((desc + "\n\n" + extra).strip()),
        })
    return out


def _from_ashby(slug: str, company: str) -> list[dict]:
    data = _fetch_json(ASHBY.format(slug=slug))
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        desc = j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml") or "")
        loc = j.get("location") or ""
        if j.get("isRemote") and "remote" not in loc.lower():
            loc = (loc + " (Remote)").strip()
        out.append({
            "ext_id": str(j.get("id")),
            "title": (j.get("title") or "").strip(),
            "company": company,
            "url": j.get("jobUrl") or j.get("applyUrl") or "",
            "location": loc or "—",
            "category": ", ".join(x for x in (j.get("department"), j.get("team")) if x),
            "full_jd": _clean(desc),
        })
    return out


PARSERS = {"greenhouse": _from_greenhouse, "lever": _from_lever, "ashby": _from_ashby}


def _load_boards() -> list[dict]:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    boards = cfg.get("boards", [])
    return [b for b in boards if b.get("provider") in PARSERS and b.get("slug")]


def crawl(keyword: str, target: int, per_board: int) -> None:
    base_dir = Path(__file__).resolve().parent.parent
    out_dir = fixed_out_dir(base_dir, SITE, PIN_KEYWORD)  # 키워드 무관, 고정 폴더
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] 저장 경로(누적): {out_dir}", flush=True)

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

    boards = _load_boards()
    # 국내(kr) 보드는 수가 적어 무작위 순서면 상한에 밀려 누락될 수 있다.
    # 항상 kr 보드를 먼저 돌고, 해외(global)만 무작위 순서로 섞는다.
    kr = [b for b in boards if b.get("region") == "kr"]
    others = [b for b in boards if b.get("region") != "kr"]
    random.shuffle(others)
    boards = kr + others
    print(f"[*] 보드 {len(boards)}개 / 기존 수집 {base_count}건 / 이전 PID {len(seen)}개", flush=True)
    print(f"[*] 목표 신규 {target}건 (회사당 상한 {per_board})", flush=True)

    scanned = skipped_dup = skipped_nondev = failed_boards = 0
    for bi, b in enumerate(boards, 1):
        if len(collected) - base_count >= target:
            break
        provider, slug, company = b["provider"], b["slug"], b["company"]
        try:
            candidates = PARSERS[provider](slug, company)
        except Exception as exc:
            reason, code = block_detect.from_http_error(exc)
            note = reason or type(exc).__name__
            print(f"  [{bi}/{len(boards)}] {company:22s} ({provider}:{slug}) 실패: {note}", flush=True)
            failed_boards += 1
            continue

        board_new = 0
        for c in candidates:
            if len(collected) - base_count >= target or board_new >= per_board:
                break
            scanned += 1
            pid = f"{provider}:{slug}:{c['ext_id']}"
            if not c["ext_id"] or pid in seen:
                skipped_dup += 1
                continue
            if not is_developer_job(c["title"], c.get("category")):
                skipped_nondev += 1
                continue

            full_jd = c["full_jd"]
            tech = extract_tech_stack(f"{c['title']}\n{c.get('category','')}\n{full_jd}")
            jd_parts = build_jd_sections(None, full_jd)

            idx = len(collected) + 1
            label = f"{company}_{c['title']}".strip("_")
            base_name = f"{idx:02d}_{sanitize_filename(label)}"
            lines = [
                f"회사: {company}",
                f"제목: {c['title']}",
                f"URL: {c['url']}",
                f"출처: {provider}:{slug} (자체 채용페이지)",
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
                "source_board": f"{provider}:{slug}",
                "company": company,
                "title": c["title"],
                "url": c["url"],
                "category": c.get("category", ""),
                "location": c["location"],
                "reward": "",
                "skills": [],
                "tech_stack": tech,
                "main_tasks": jd_parts.get("main_tasks", ""),
                "qualifications": jd_parts.get("qualifications", ""),
                "preferences": jd_parts.get("preferences", ""),
                "tech_stack_raw": jd_parts.get("tech_stack_raw", ""),
                "benefits": jd_parts.get("benefits", ""),
                "full_jd": full_jd,
                "txt": f"{base_name}.txt",
                "company_page": True,
                "region": b.get("region", ""),
            })
            seen.add(pid)
            board_new += 1
        if board_new:
            save_jobs_json(out_dir, collected)
            print(f"  [{bi}/{len(boards)}] {company:22s} ({provider}:{slug}) +{board_new} "
                  f"→ 누적 {len(collected)}", flush=True)
        time.sleep(jitter(600) / 1000)

    save_jobs_json(out_dir, collected)
    if failed_boards < len(boards):
        block_detect.note_success(SITE)
    print(
        f"\n[완료] 수집 {len(collected)} (신규 {len(collected) - base_count}) / "
        f"중복 {skipped_dup} / 비개발 {skipped_nondev} / 훑음 {scanned} / 실패보드 {failed_boards}",
        flush=True,
    )
    print(f"[결과 위치] {out_dir}", flush=True)


def main() -> None:
    args = sys.argv[1:]
    keyword = args[0] if len(args) > 0 else "개발자"
    target = int(args[1]) if len(args) > 1 else 100
    per_board = int(args[2]) if len(args) > 2 else 6
    crawl(keyword, target, per_board)


if __name__ == "__main__":
    main()
