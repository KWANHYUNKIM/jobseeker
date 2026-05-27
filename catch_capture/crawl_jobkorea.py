"""잡코리아 (jobkorea.co.kr) → 개발자 검색 결과를 txt로 저장.

잡코리아 JD는 iframe(GI_Read_Comt_Ifrm)에 들어있음. 사람인과 유사 구조.
이미지 JD가 많으므로 OCR 사용.

사용법:
    python crawl_jobkorea.py 개발자
    python crawl_jobkorea.py 개발자 30
    python crawl_jobkorea.py 개발자 30 5
    python crawl_jobkorea.py 개발자 30 5 --no-ocr
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright

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

SEARCH_URL = (
    "https://www.jobkorea.co.kr/Search/?stext={kw}&tabType=recruit&Page_No={page}"
)
DETAIL_IFRAME_URL = (
    "https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm"
    "?Gno={gno}&isHiringCenter=false&hideMapView=false"
)
GNO_RE = re.compile(r"GI_Read/(\d+)")


async def collect_search_cards(page, keyword: str, max_pages: int) -> list[dict]:
    seen_ids: set[str] = set()
    all_jobs: list[dict] = []
    encoded_kw = quote(keyword)

    for page_num in range(1, max_pages + 1):
        if page_num > 1:
            url = SEARCH_URL.format(kw=encoded_kw, page=page_num)
            try:
                await page.goto(url, wait_until="commit", timeout=30_000)
            except Exception as e:
                print(f"  [page {page_num}] 이동 실패: {e}", flush=True)
                break
            await page.wait_for_timeout(2500)

        try:
            await page.wait_for_selector("a[href*='/Recruit/GI_Read/']", timeout=15_000)
        except Exception:
            print(f"  [page {page_num}] 결과 미발견", flush=True)
            break
        await page.wait_for_timeout(1000)

        cards = await page.evaluate(
            """() => {
                const seen = new Set();
                const out = [];
                document.querySelectorAll('[data-sentry-component="CardJob"]').forEach(card => {
                    const link = card.querySelector('a[href*="/Recruit/GI_Read/"]');
                    if (!link) return;
                    const m = (link.href || '').match(/GI_Read\\/(\\d+)/);
                    if (!m) return;
                    const gno = m[1];
                    if (seen.has(gno)) return;
                    seen.add(gno);
                    // title is in a span inside title link
                    const titleEl = card.querySelector('a[href*="/Recruit/GI_Read/"] span');
                    const title = ((titleEl || {}).innerText || '').trim();
                    // company name is in alt of logo image
                    const logoImg = card.querySelector('img[alt*="로고"]');
                    let company = '';
                    if (logoImg) {
                        company = (logoImg.getAttribute('alt') || '').replace(/\\s*로고\\s*$/, '').trim();
                    }
                    // fallback: another link with company name
                    if (!company) {
                        const anyCompany = card.querySelector('a[href*="/Corp/"]');
                        if (anyCompany) company = (anyCompany.innerText || '').trim();
                    }
                    // condition spans — gather all text snippets in the card
                    const allText = (card.innerText || '').trim();
                    out.push({ gno, href: link.href, title, company, raw_text: allText });
                });
                return out;
            }"""
        )

        new_count = 0
        for c in cards:
            gno = c["gno"]
            if gno in seen_ids:
                continue
            seen_ids.add(gno)
            all_jobs.append(c)
            new_count += 1
        print(f"  [page {page_num}] +{new_count}  누적 {len(all_jobs)}개", flush=True)

        if new_count == 0:
            break

    return all_jobs


def parse_raw_meta(raw_text: str) -> dict:
    """카드 raw_text에서 위치/경력/학력/고용형태/마감 추정."""
    out = {"location": "", "career": "", "education": "", "employment": "", "deadline": ""}
    lines = [s.strip() for s in raw_text.splitlines() if s.strip()]
    re_career = re.compile(r"신입|경력|인턴|경력무관")
    re_emp = re.compile(r"정규직|계약직|인턴|파견|프리랜서|단기|아르바이트")
    re_edu = re.compile(r"학력|대졸|대학원|고졸|초대졸|석사|박사|학사|학력무관")
    re_loc = re.compile(r"^[가-힣]+(특별시|광역시|시|도)|서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주")
    re_dday = re.compile(r"^D-|채용시|상시|마감|~\d+/\d+")
    for s in lines:
        if not out["career"] and re_career.search(s):
            out["career"] = s
        elif not out["employment"] and re_emp.search(s):
            out["employment"] = s
        elif not out["education"] and re_edu.search(s):
            out["education"] = s
        elif not out["deadline"] and re_dday.search(s):
            out["deadline"] = s
        elif not out["location"] and re_loc.search(s):
            out["location"] = s
    return out


def fetch_jd(gno: str, referer: str) -> tuple[str, str]:
    url = DETAIL_IFRAME_URL.format(gno=gno)
    raw = http_get(url, referer=referer).decode("utf-8", errors="replace")
    # 본문은 #detail-content 안에 있음; 못 찾으면 전체 HTML 사용
    m = re.search(r'id="detail-content"[^>]*>(.*?)</div>\s*</td>', raw, re.DOTALL | re.IGNORECASE)
    body = m.group(1) if m else raw
    return body, html_to_text(body)


async def crawl(keyword: str, target: int, max_pages: int, use_ocr: bool) -> None:
    base_dir = Path(__file__).parent
    out_dir = fixed_out_dir(base_dir, "jobkorea", keyword)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] 저장 경로(누적): {out_dir}", flush=True)
    print(f"[*] OCR 사용: {use_ocr and OCR_AVAILABLE}", flush=True)

    collected: list[dict] = load_existing_jobs(out_dir)
    seen_prev = load_seen_pids(base_dir, "jobkorea")
    for j in collected:
        for k in ("pid", "gno"):
            if j.get(k):
                seen_prev.add(str(j[k]).strip())
                break
    if collected:
        print(f"[*] 누적 폴더에 기존 수집 {len(collected)}건 발견 → 인덱스 이어서 진행", flush=True)
    if seen_prev:
        print(f"[*] 이전 수집 PID {len(seen_prev)}개 → 중복 스킵 대상", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="ko-KR",
            user_agent=USER_AGENT,
        )
        page = await ctx.new_page()
        target_url = SEARCH_URL.format(kw=quote(keyword), page=1)
        print(f"[*] 검색 진입: {target_url}", flush=True)
        await page.goto(target_url, wait_until="commit", timeout=30_000)
        await page.wait_for_timeout(2500)

        candidates = await collect_search_cards(page, keyword=keyword, max_pages=max_pages)
        print(f"[*] 후보 공고 총 {len(candidates)}개 (목표 {target}개, 이미 보유 {len(collected)}개)", flush=True)

        scanned = skipped_nondev = skipped_dup = failed = 0
        for job in candidates:
            if len(collected) >= target:
                break
            scanned += 1
            label = f"{job['company']}_{job['title']}".strip("_")
            print(f"  [{scanned:02d}] {label[:60]}", flush=True)

            if job["gno"] in seen_prev:
                skipped_dup += 1
                print(f"       ↳ 이전 수집 중복(pid={job['gno']}), 스킵", flush=True)
                continue

            if not is_developer_job(job["title"]):
                skipped_nondev += 1
                print(f"       ↳ 비개발자, 스킵", flush=True)
                continue

            meta = parse_raw_meta(job.get("raw_text", ""))

            jd_html, jd_text = "", ""
            try:
                jd_html, jd_text = fetch_jd(job["gno"], referer=job["href"])
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

            tech = extract_tech_stack(full_jd)
            jd_parts = build_jd_sections(None, full_jd)

            if full_jd:
                jd_body = full_jd
            elif image_only:
                jd_body = "(상세 내용이 이미지로만 제공되며 OCR로도 추출 실패.)"
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
                f"경력: {meta['career']}",
                f"고용형태: {meta['employment']}",
                f"학력: {meta['education']}",
                f"위치: {meta['location']}",
                "",
                "[기술스택]",
                ", ".join(tech) if tech else "(JD에서 식별된 기술스택 없음)",
                "",
                "[마감]",
                meta["deadline"] or "(미상)",
                "",
                "[채용 상세]",
                jd_body,
            ]
            (out_dir / f"{base_name}.txt").write_text("\n".join(lines), encoding="utf-8")
            collected.append({
                "idx": idx,
                "pid": job["gno"],
                "gno": job["gno"],
                "company": job["company"],
                "title": job["title"],
                "url": job["href"],
                **meta,
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
            seen_prev.add(str(job["gno"]).strip())
            save_jobs_json(out_dir, collected)
            print(f"       ✔  ({len(collected)}/{target}) image_only={image_only} tech={tech[:6]}", flush=True)

        save_jobs_json(out_dir, collected)
        print(
            f"\n[완료] 수집 {len(collected)} / 중복 {skipped_dup} / 비개발자 {skipped_nondev} / 실패 {failed} / 훑은 공고 {scanned}",
            flush=True,
        )
        print(f"[결과 위치] {out_dir}", flush=True)
        await browser.close()


def main() -> None:
    args = sys.argv[1:]
    use_ocr = True
    if "--no-ocr" in args:
        use_ocr = False
        args.remove("--no-ocr")
    keyword = args[0] if len(args) > 0 else "개발자"
    target = int(args[1]) if len(args) > 1 else 20
    max_pages = int(args[2]) if len(args) > 2 else 5
    asyncio.run(crawl(keyword, target, max_pages, use_ocr))


if __name__ == "__main__":
    main()
