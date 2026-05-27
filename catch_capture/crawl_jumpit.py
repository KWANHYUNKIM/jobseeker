"""점핏 (jumpit.saramin.co.kr) → 개발자 검색 결과를 txt로 저장.

점핏은 개발자 전용 사이트라 모든 공고가 개발자 직무지만, 검색어를 그대로 전달.
무한 스크롤이라 max_scrolls로 로딩 수 조정.

사용법:
    python crawl_jumpit.py 개발자                # 기본 20개, 스크롤 8회
    python crawl_jumpit.py 개발자 30
    python crawl_jumpit.py 개발자 30 15
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

SEARCH_URL = "https://jumpit.saramin.co.kr/search?keyword={kw}"
POSITION_ID_RE = re.compile(r"/position/(\d+)")


async def collect_search_cards(page, max_scrolls: int) -> list[dict]:
    """무한 스크롤로 카드 수집."""
    seen_ids: set[str] = set()
    all_jobs: list[dict] = []

    for i in range(max_scrolls):
        cards = await page.evaluate(
            """() => {
                const anchors = Array.from(document.querySelectorAll('a[href*="/position/"]'));
                const out = [];
                const seen = new Set();
                for (const a of anchors) {
                    const href = a.href || '';
                    const m = href.match(/\\/position\\/(\\d+)/);
                    if (!m) continue;
                    const pid = m[1];
                    if (seen.has(pid)) continue;
                    seen.add(pid);
                    const raw = (a.innerText || '').trim();
                    const parts = raw.split('\\n').map(s => s.trim()).filter(Boolean);
                    out.push({ position_id: pid, href, parts });
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
            # parts pattern: ["D-21", "와탭랩스", "프론트엔드 개발자", "Git", "· React", "서울 서초구", "경력 3~10년"]
            parts = c["parts"]
            dday = parts[0] if parts and parts[0].startswith("D-") else ""
            non_d_parts = parts[1:] if dday else parts
            company = non_d_parts[0] if len(non_d_parts) > 0 else ""
            title = non_d_parts[1] if len(non_d_parts) > 1 else ""
            # tech parts start with · or no prefix; location/career at the end
            tech_tags: list[str] = []
            tail: list[str] = []
            for s in non_d_parts[2:]:
                if s.startswith("·"):
                    tech_tags.append(s.lstrip("·").strip())
                elif re.search(r"\d+년|신입|경력|인턴", s):
                    tail.append(s)
                elif re.match(r"^[가-힣]+\s", s):
                    tail.append(s)
                else:
                    tech_tags.append(s.strip())
            all_jobs.append({
                "position_id": pid,
                "href": c["href"],
                "company": company,
                "title": title,
                "dday": dday,
                "tech_tags": tech_tags,
                "tail": tail,
            })
            new_count += 1
        print(f"  [scroll {i+1}/{max_scrolls}] +{new_count}  누적 {len(all_jobs)}개", flush=True)
        await page.mouse.wheel(0, 3000)
        await page.wait_for_timeout(1200)

    return all_jobs


async def fetch_detail(ctx, href: str) -> dict:
    """상세 페이지에서 기술스택/주요업무/자격요건/우대사항 + 메타 추출."""
    detail = await ctx.new_page()
    try:
        await detail.goto(href, wait_until="commit", timeout=30_000)
        try:
            await detail.wait_for_selector(".position_info", timeout=10_000)
        except Exception:
            pass
        await detail.wait_for_timeout(1500)

        data = await detail.evaluate(
            """() => {
                const out = { sections: {}, tech_imgs: [], location: '', career: '' };
                const info = document.querySelector('.position_info');
                if (!info) return out;
                // tech stack images
                info.querySelectorAll('img[alt]').forEach(img => {
                    const a = (img.getAttribute('alt') || '').trim();
                    if (a && !out.tech_imgs.includes(a)) out.tech_imgs.push(a);
                });
                // dl/dt/dd sections
                info.querySelectorAll('dl').forEach(dl => {
                    const dt = dl.querySelector('dt');
                    const dd = dl.querySelector('dd');
                    if (!dt || !dd) return;
                    const key = (dt.innerText || '').trim();
                    const val = (dd.innerText || '').trim();
                    if (key && val) out.sections[key] = val;
                });
                // location/career — look around for typical labels
                document.querySelectorAll('dl').forEach(dl => {
                    const dt = (dl.querySelector('dt') || {}).innerText || '';
                    const dd = (dl.querySelector('dd') || {}).innerText || '';
                    if (/근무지|위치/.test(dt)) out.location = dd.trim();
                    if (/경력/.test(dt) && !out.career) out.career = dd.trim();
                });
                return out;
            }"""
        )
        return data
    finally:
        await detail.close()


async def crawl(keyword: str, target: int, max_scrolls: int) -> None:
    base_dir = Path(__file__).parent
    out_dir = fixed_out_dir(base_dir, "jumpit", keyword)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] 저장 경로(누적): {out_dir}", flush=True)

    collected: list[dict] = load_existing_jobs(out_dir)
    seen_prev = load_seen_pids(base_dir, "jumpit")
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
        await page.goto(target_url, wait_until="commit", timeout=30_000)
        try:
            await page.wait_for_selector("a[href*='/position/']", timeout=15_000)
        except Exception:
            print("[!] 검색 결과 미발견", flush=True)
            await browser.close()
            return
        await page.wait_for_timeout(1500)

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

            if not is_developer_job(job["title"]):
                skipped_nondev += 1
                print(f"       ↳ 비개발자, 스킵", flush=True)
                continue

            try:
                detail = await fetch_detail(ctx, job["href"])
            except Exception as e:
                print(f"       ↳ 상세 실패: {e}", flush=True)
                failed += 1
                continue

            sections = detail.get("sections", {}) or {}
            jd_parts = build_jd_sections(sections, None)
            full_jd_parts = []
            for label_kr, k in (("주요업무", "main_tasks"), ("자격요건", "qualifications"),
                                ("우대사항", "preferences"), ("기술스택", "tech_stack_raw"),
                                ("혜택 및 복지", "benefits")):
                v = jd_parts.get(k)
                if v:
                    full_jd_parts.append(f"[{label_kr}]\n{v}")
            full_jd = "\n\n".join(full_jd_parts)

            tech_pool = " ".join(detail.get("tech_imgs", []) + job.get("tech_tags", []))
            tech = extract_tech_stack(full_jd + "\n" + tech_pool)

            idx = len(collected) + 1
            base_name = f"{idx:02d}_{sanitize_filename(label)}"
            lines = [
                f"회사: {job['company']}",
                f"제목: {job['title']}",
                f"URL: {job['href']}",
                "",
                "[조건]",
                f"경력: {detail.get('career') or ''}",
                f"위치: {detail.get('location') or ''}",
                f"마감: {job['dday']}",
                "",
                "[직무 카테고리/태그]",
                ", ".join(job["tech_tags"]) if job["tech_tags"] else "(없음)",
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
                "career": detail.get("career", ""),
                "location": detail.get("location", ""),
                "dday": job["dday"],
                "tech_tags": job["tech_tags"],
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
