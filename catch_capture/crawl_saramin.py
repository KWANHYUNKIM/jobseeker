"""사람인 (saramin.co.kr) → 개발자 직무 검색 결과를 txt로 저장.

saramin은 Playwright/headless Chromium을 감지해서 빈 페이지를 내주기 때문에
검색 페이지/상세 모두 http_get + BeautifulSoup으로 처리한다 (브라우저 불필요).

사용법:
    python crawl_saramin.py 개발자                # 기본 20개 수집, 최대 5페이지
    python crawl_saramin.py 개발자 30
    python crawl_saramin.py 개발자 30 10
    python crawl_saramin.py 개발자 30 10 --no-ocr
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from jobs_common import (
    OCR_AVAILABLE,
    USER_AGENT,
    build_jd_sections,
    fixed_out_dir,
    extract_img_urls,
    extract_tech_stack,
    html_to_text,
    http_get,
    is_developer_job,
    is_image_only,
    load_existing_jobs,
    load_seen_pids,
    ocr_images,
    sanitize_filename,
    save_jobs_json,
)

SARAMIN_BASE = "https://www.saramin.co.kr"

SEARCH_URL = (
    "https://www.saramin.co.kr/zf_user/search/recruit"
    "?searchType=search&searchword={kw}"
    "&recruitPage={page}&recruitSort=relation&recruitPageCount=40"
)
DETAIL_IFRAME_URL = (
    "https://www.saramin.co.kr/zf_user/jobs/relay/view-detail"
    "?rec_idx={rec_idx}&rec_seq=0"
)
REC_IDX_RE = re.compile(r"rec_idx=(\d+)")


def collect_search_anchors(keyword: str, max_pages: int) -> list[dict]:
    """페이지를 넘기며 모든 공고 카드 정보 수집 (HTTP만 사용, 브라우저 불필요)."""
    seen_ids: set[str] = set()
    all_jobs: list[dict] = []
    encoded_kw = quote(keyword)

    for page_num in range(1, max_pages + 1):
        url = SEARCH_URL.format(kw=encoded_kw, page=page_num)
        try:
            html = http_get(url, timeout=30).decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  [page {page_num}] 가져오기 실패: {e}", flush=True)
            break

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".item_recruit")
        if not cards:
            print(f"  [page {page_num}] item_recruit 미발견, 종료", flush=True)
            break

        new_count = 0
        for card in cards:
            rec_idx = (card.get("value") or "").strip()
            a = card.select_one(".area_job h2.job_tit a")
            if not a:
                continue
            href_raw = a.get("href") or ""
            href = urljoin(SARAMIN_BASE, href_raw) if href_raw else ""
            title = (a.get("title") or a.get_text(strip=True) or "").strip()
            corp = card.select_one(".area_corp .corp_name a, .area_corp .corp_name")
            company = corp.get_text(strip=True) if corp else ""
            cond_spans = [
                s.get_text(strip=True) for s in card.select(".area_job .job_condition > span")
            ]
            sectors = [
                sa.get_text(strip=True) for sa in card.select(".area_job .job_sector a")
            ]
            deadline_el = card.select_one(".job_date .date")
            deadline = deadline_el.get_text(strip=True) if deadline_el else ""

            if not rec_idx or rec_idx in seen_ids:
                continue
            seen_ids.add(rec_idx)
            all_jobs.append({
                "rec_idx": rec_idx,
                "href": href,
                "title": title,
                "company": company,
                "cond": cond_spans,
                "sectors": sectors,
                "deadline": deadline,
            })
            new_count += 1

        print(f"  [page {page_num}] +{new_count}  누적 {len(all_jobs)}개", flush=True)
        if new_count == 0:
            break

    return all_jobs


def parse_condition(cond_spans: list[str]) -> dict:
    """job_condition span 리스트를 (위치/경력/학력/고용형태)로 분리."""
    out = {"location": "", "career": "", "education": "", "employment": ""}
    re_career = re.compile(r"신입|경력|인턴|경력무관|병역특례")
    re_emp = re.compile(r"정규직|계약직|인턴|파견|프리랜서|단기|아르바이트|위촉직|연수생")
    re_edu = re.compile(r"학력|대졸|대학원|고졸|초대졸|석사|박사|학사|중졸|학력무관")
    locs: list[str] = []
    for s in cond_spans:
        if not s:
            continue
        if not out["career"] and re_career.search(s):
            out["career"] = s
        elif not out["employment"] and re_emp.search(s):
            out["employment"] = s
        elif not out["education"] and re_edu.search(s):
            out["education"] = s
        else:
            locs.append(s)
    out["location"] = " | ".join(locs)
    return out


def fetch_jd(rec_idx: str, referer: str) -> tuple[str, str]:
    """iframe HTML과 텍스트 반환."""
    url = DETAIL_IFRAME_URL.format(rec_idx=rec_idx)
    raw = http_get(url, referer=referer).decode("utf-8", errors="replace")
    # .user_content 영역만 잘라내기 (가능한 경우)
    m = re.search(
        r'<div[^>]*class="[^"]*user_content[^"]*"[^>]*>(.*?)</div>\s*<script',
        raw,
        re.DOTALL | re.IGNORECASE,
    )
    body = m.group(1) if m else raw
    return body, html_to_text(body)


def crawl(keyword: str, target: int, max_pages: int, use_ocr: bool) -> None:
    base_dir = Path(__file__).parent
    out_dir = fixed_out_dir(base_dir, "saramin", keyword)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] 저장 경로(누적): {out_dir}", flush=True)
    print(f"[*] OCR 사용: {use_ocr and OCR_AVAILABLE}", flush=True)

    collected: list[dict] = load_existing_jobs(out_dir)
    seen_prev = load_seen_pids(base_dir, "saramin")
    for j in collected:
        for k in ("pid", "rec_idx"):
            if j.get(k):
                seen_prev.add(str(j[k]).strip())
                break
    if collected:
        print(f"[*] 누적 폴더에 기존 수집 {len(collected)}건 발견 → 인덱스 이어서 진행", flush=True)
    if seen_prev:
        print(f"[*] 이전 수집 PID {len(seen_prev)}개 → 중복 스킵 대상", flush=True)

    print(f"[*] 검색 (HTTP) keyword={keyword!r}, max_pages={max_pages}", flush=True)
    candidates = collect_search_anchors(keyword=keyword, max_pages=max_pages)
    print(f"[*] 후보 공고 총 {len(candidates)}개 (목표 개발자 직무 {target}개, 이미 보유 {len(collected)}개)", flush=True)

    if not candidates:
        print("[!] 후보 공고가 없습니다.", flush=True)
        return

    scanned = skipped_nondev = skipped_dup = failed = 0

    for job in candidates:
        if len(collected) >= target:
            break
        scanned += 1
        label = f"{job['company']}_{job['title']}".strip("_")
        print(f"  [{scanned:02d}] {label[:60]}", flush=True)

        if job["rec_idx"] in seen_prev:
            skipped_dup += 1
            print(f"       ↳ 이전 수집 중복(pid={job['rec_idx']}), 스킵", flush=True)
            continue

        # 개발자 직무 판정 — title + sectors 기준
        if not is_developer_job(job["title"], job["sectors"]):
            skipped_nondev += 1
            print(f"       ↳ 비개발자, 스킵 (sectors={job['sectors'][:3]})", flush=True)
            continue

        cond = parse_condition(job["cond"])

        # JD fetch
        jd_html, jd_text = "", ""
        try:
            jd_html, jd_text = fetch_jd(job["rec_idx"], referer=job["href"])
        except Exception as e:
            print(f"       ↳ JD fetch 실패: {e}", flush=True)
            failed += 1
            continue

        image_only = is_image_only(jd_html, jd_text)
        ocr_text = ""
        if image_only and use_ocr and OCR_AVAILABLE:
            img_urls = extract_img_urls(jd_html)
            print(f"       ↳ JD가 이미지({len(img_urls)}개), OCR 실행", flush=True)
            ocr_text = ocr_images(img_urls, referer=job["href"])

        full_jd = jd_text or ""
        if ocr_text:
            full_jd = (full_jd + "\n\n[이미지 OCR]\n" + ocr_text).strip()

        tech = extract_tech_stack(full_jd + "\n" + " ".join(job["sectors"]))
        jd_parts = build_jd_sections(None, full_jd)

        if full_jd:
            jd_body = full_jd
        elif image_only:
            jd_body = "(상세 내용이 이미지로만 제공되며 OCR로도 추출 실패. 원본 링크에서 확인하세요.)"
        else:
            jd_body = "(상세 내용을 가져오지 못함)"

        idx = len(collected) + 1
        base_name = f"{idx:02d}_{sanitize_filename(label)}"
        lines = [
            f"회사: {job['company']}",
            f"제목: {job['title']}",
            f"URL: {job['href']}",
            "",
            "[조건]",
            f"경력: {cond['career']}",
            f"고용형태: {cond['employment']}",
            f"학력: {cond['education']}",
            f"위치: {cond['location']}",
            "",
            "[직무 카테고리]",
            ", ".join(job["sectors"]) if job["sectors"] else "(없음)",
            "",
            "[기술스택]",
            ", ".join(tech) if tech else "(JD에서 식별된 기술스택 없음)",
            "",
            "[마감]",
            job["deadline"] or "(미상)",
            "",
            "[주요업무]",
            jd_parts.get("main_tasks") or "(추출 실패)",
            "",
            "[자격요건]",
            jd_parts.get("qualifications") or "(추출 실패)",
            "",
            "[우대사항]",
            jd_parts.get("preferences") or "(없음)",
            "",
            "[복지/혜택]",
            jd_parts.get("benefits") or "(없음)",
            "",
            "[채용 상세 원문]",
            jd_body,
        ]
        (out_dir / f"{base_name}.txt").write_text("\n".join(lines), encoding="utf-8")
        collected.append({
            "idx": idx,
            "pid": job["rec_idx"],
            "rec_idx": job["rec_idx"],
            "company": job["company"],
            "title": job["title"],
            "url": job["href"],
            **cond,
            "sectors": job["sectors"],
            "deadline": job["deadline"],
            "tech_stack": tech,
            "main_tasks": jd_parts.get("main_tasks", ""),
            "qualifications": jd_parts.get("qualifications", ""),
            "preferences": jd_parts.get("preferences", ""),
            "tech_stack_raw": jd_parts.get("tech_stack_raw", ""),
            "benefits": jd_parts.get("benefits", ""),
            "full_jd": full_jd,
            "image_only_jd": image_only,
            "ocr_used": bool(ocr_text),
            "txt": f"{base_name}.txt",
        })
        seen_prev.add(str(job["rec_idx"]).strip())
        save_jobs_json(out_dir, collected)
        print(f"       ✔  ({len(collected)}/{target}) image_only={image_only} tech={tech[:6]}", flush=True)

    save_jobs_json(out_dir, collected)
    print(
        f"\n[완료] 수집 {len(collected)} / 중복 {skipped_dup} / 비개발자 {skipped_nondev} / 실패 {failed} / 훑은 공고 {scanned}",
        flush=True,
    )
    print(f"[결과 위치] {out_dir}", flush=True)


def main() -> None:
    args = sys.argv[1:]
    use_ocr = True
    if "--no-ocr" in args:
        use_ocr = False
        args.remove("--no-ocr")
    keyword = args[0] if len(args) > 0 else "개발자"
    target = int(args[1]) if len(args) > 1 else 20
    max_pages = int(args[2]) if len(args) > 2 else 5
    crawl(keyword, target, max_pages, use_ocr)


if __name__ == "__main__":
    main()
