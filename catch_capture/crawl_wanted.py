"""원티드 (wanted.co.kr) → 개발자 검색 결과를 txt로 저장.

원티드는 SPA + 무한 스크롤. data-* 속성에서 메타 추출, JD는 article.JobDescription_*.

사용법:
    python crawl_wanted.py 개발자
    python crawl_wanted.py 개발자 30
    python crawl_wanted.py 개발자 30 15
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
    USER_AGENT,
    build_jd_sections,
    fixed_out_dir,
    extract_tech_stack,
    is_developer_job,
    load_existing_jobs,
    load_seen_pids,
    sanitize_filename,
    save_jobs_json,
)

SEARCH_URL = "https://www.wanted.co.kr/search?query={kw}&tab=position"


async def collect_search_cards(page, max_scrolls: int) -> list[dict]:
    seen_ids: set[str] = set()
    all_jobs: list[dict] = []

    for i in range(max_scrolls):
        cards = await page.evaluate(
            """() => {
                const anchors = Array.from(document.querySelectorAll('a[href*="/wd/"][data-position-id]'));
                const out = [];
                for (const a of anchors) {
                    const pid = a.getAttribute('data-position-id') || '';
                    if (!pid) continue;
                    out.push({
                        position_id: pid,
                        href: a.href,
                        title: a.getAttribute('data-position-name') || '',
                        company: a.getAttribute('data-company-name') || '',
                        category: a.getAttribute('data-job-category') || '',
                        location: ((a.querySelector('[class*=\"location\"]') || {}).innerText || '').trim(),
                        reward: ((a.querySelector('[class*=\"reward\"]') || {}).innerText || '').trim(),
                    });
                }
                return out;
            }"""
        )
        new_count = 0
        for c in cards:
            pid = c["position_id"]
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            all_jobs.append(c)
            new_count += 1
        print(f"  [scroll {i+1}/{max_scrolls}] +{new_count}  누적 {len(all_jobs)}개", flush=True)
        await page.mouse.wheel(0, 3000)
        await page.wait_for_timeout(1200)

    return all_jobs


async def fetch_detail(ctx, href: str) -> dict:
    detail = await ctx.new_page()
    try:
        await detail.goto(href, wait_until="commit", timeout=30_000)
        try:
            await detail.wait_for_selector("article[class*='JobDescription_JobDescription']", timeout=15_000)
        except Exception:
            pass
        # 더보기 버튼 있으면 클릭 (JD 접혀있을 수 있음)
        try:
            btn = detail.locator("button:has-text('상세 정보 더 보기')").first
            if await btn.count() > 0:
                await btn.click(timeout=3000)
                await detail.wait_for_timeout(800)
        except Exception:
            pass
        await detail.wait_for_timeout(1200)

        return await detail.evaluate(
            """() => {
                const art = document.querySelector("article[class*='JobDescription_JobDescription']");
                const sections = {};
                let full = '';
                if (art) {
                    full = (art.innerText || '').trim();
                    // try to split by h3 headers
                    art.querySelectorAll('h3').forEach(h3 => {
                        const key = (h3.innerText || '').trim();
                        const dd = h3.nextElementSibling;
                        if (dd && key) sections[key] = (dd.innerText || '').trim();
                    });
                }
                // sidebar meta
                const meta = {};
                document.querySelectorAll('[class*=\"JobHeader_JobHeader__Tools\"], [class*=\"JobHeader\"]').forEach(el => {
                    const t = (el.innerText || '').trim();
                    if (t) meta.header = (meta.header || '') + '\\n' + t;
                });
                // skill chips
                const skillSet = new Set();
                document.querySelectorAll('[class*=\"SkillTagItem_SkillTagItem__\"], [class*=\"JobSkillTags_JobSkillTags__\"] li, [class*=\"JobSkillTags_JobSkillTags__\"] span').forEach(s => {
                    const t = (s.innerText || '').trim();
                    if (t && t.length < 40) skillSet.add(t);
                });
                const skills = Array.from(skillSet);
                return { full_text: full, sections, meta, skills };
            }"""
        )
    finally:
        await detail.close()


async def crawl(keyword: str, target: int, max_scrolls: int) -> None:
    base_dir = Path(__file__).parent
    out_dir = fixed_out_dir(base_dir, "wanted", keyword)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] 저장 경로(누적): {out_dir}", flush=True)

    collected: list[dict] = load_existing_jobs(out_dir)
    seen_prev = load_seen_pids(base_dir, "wanted")
    for j in collected:
        for k in ("pid", "position_id"):
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
        target_url = SEARCH_URL.format(kw=quote(keyword))
        print(f"[*] 검색 진입: {target_url}", flush=True)
        await page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)
        # wait for hydration — JobCardSkeleton replaced by real cards
        hydrated = False
        try:
            await page.wait_for_selector("a[href*='/wd/']", state="attached", timeout=25_000)
            count = await page.locator("a[href*='/wd/']").count()
            hydrated = count > 0
            print(f"[*] hydrated, {count} cards visible", flush=True)
        except Exception as e:
            print(f"[!] hydration wait failed: {e}", flush=True)
        if not hydrated:
            print("[!] 검색 결과 미발견 (hydration timeout) — 페이지 덤프 저장", flush=True)
            dump = await page.content()
            (out_dir / "wanted_fail.html").write_text(dump, encoding="utf-8")
            print(f"     dump: {out_dir / 'wanted_fail.html'} ({len(dump)} chars)", flush=True)
            await browser.close()
            return

        candidates = await collect_search_cards(page, max_scrolls=max_scrolls)
        print(f"[*] 후보 공고 총 {len(candidates)}개 (목표 {target}개, 이미 보유 {len(collected)}개)", flush=True)

        scanned = skipped_nondev = skipped_dup = failed = 0
        for job in candidates:
            if len(collected) >= target:
                break
            scanned += 1
            label = f"{job['company']}_{job['title']}".strip("_")
            print(f"  [{scanned:02d}] {label[:60]}", flush=True)

            if job["position_id"] in seen_prev:
                skipped_dup += 1
                print(f"       ↳ 이전 수집 중복(pid={job['position_id']}), 스킵", flush=True)
                continue

            if not is_developer_job(job["title"], job["category"]):
                skipped_nondev += 1
                print(f"       ↳ 비개발자 (category={job['category']}), 스킵", flush=True)
                continue

            try:
                detail = await fetch_detail(ctx, job["href"])
            except Exception as e:
                print(f"       ↳ 상세 실패: {e}", flush=True)
                failed += 1
                continue

            full_jd = detail.get("full_text") or ""
            skills = detail.get("skills") or []
            tech = extract_tech_stack(full_jd + "\n" + " ".join(skills))
            jd_parts = build_jd_sections(detail.get("sections") or {}, full_jd)

            idx = len(collected) + 1
            base_name = f"{idx:02d}_{sanitize_filename(label)}"
            lines = [
                f"회사: {job['company']}",
                f"제목: {job['title']}",
                f"URL: {job['href']}",
                "",
                "[조건]",
                f"위치/경력: {job.get('location', '')}",
                f"보상금: {job.get('reward', '')}",
                "",
                "[직무 카테고리]",
                job.get("category", "") or "(없음)",
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
                "pid": job["position_id"],
                "position_id": job["position_id"],
                "company": job["company"],
                "title": job["title"],
                "url": job["href"],
                "category": job["category"],
                "location": job.get("location"),
                "reward": job.get("reward"),
                "skills": skills,
                "tech_stack": tech,
                "main_tasks": jd_parts.get("main_tasks", ""),
                "qualifications": jd_parts.get("qualifications", ""),
                "preferences": jd_parts.get("preferences", ""),
                "tech_stack_raw": jd_parts.get("tech_stack_raw", ""),
                "benefits": jd_parts.get("benefits", ""),
                "full_jd": full_jd,
                "txt": f"{base_name}.txt",
            })
            seen_prev.add(str(job["position_id"]).strip())
            save_jobs_json(out_dir, collected)
            print(f"       ✔  ({len(collected)}/{target}) tech={tech[:6]}", flush=True)

        save_jobs_json(out_dir, collected)
        print(
            f"\n[완료] 수집 {len(collected)} / 중복 {skipped_dup} / 비개발자 {skipped_nondev} / 실패 {failed} / 훑은 공고 {scanned}",
            flush=True,
        )
        print(f"[결과 위치] {out_dir}", flush=True)
        await browser.close()


def main() -> None:
    args = sys.argv[1:]
    keyword = args[0] if len(args) > 0 else "개발자"
    target = int(args[1]) if len(args) > 1 else 20
    max_scrolls = int(args[2]) if len(args) > 2 else 8
    asyncio.run(crawl(keyword, target, max_scrolls))


if __name__ == "__main__":
    main()
