"""
캐치(catch.co.kr) "채용공고" 검색 결과의 각 공고 상세 페이지를 자동 캡처.

사용법:
    python capture.py 개발자
    python capture.py 개발자 20
"""
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright


SEARCH_URL = "https://www.catch.co.kr/Search/SearchList?Keyword={kw}"
JOB_LINK_SELECTOR = "table.table2.type3 a.tdlink.al"


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|\n\r\t]+', " ", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name[:80] or "untitled"


async def capture_jobs(keyword: str, max_jobs: int = 20) -> None:
    base_dir = Path(__file__).parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = base_dir / "screenshots" / f"{sanitize_filename(keyword)}_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] 저장 경로: {out_dir}", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="ko-KR",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        target_url = SEARCH_URL.format(kw=quote(keyword))
        print(f"[*] 통합검색 진입: {target_url}", flush=True)
        await page.goto(target_url, wait_until="domcontentloaded", timeout=60_000)
        try:
            await page.wait_for_selector(JOB_LINK_SELECTOR, timeout=15_000)
        except Exception:
            print("[!] 통합검색에서 채용공고 미리보기를 찾지 못했습니다.", flush=True)
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(out_dir / "_00_통합검색.png"), full_page=True)

        print("[*] 채용공고 '더보기' 클릭", flush=True)
        clicked = False
        for locator in [
            page.locator("div.search_tit2").filter(has_text="채용공고").locator("a", has_text="더보기").first,
            page.locator("div.search_tit2 p.bt_detail a").first,
        ]:
            try:
                await locator.wait_for(state="visible", timeout=3000)
                async with page.expect_navigation(wait_until="domcontentloaded", timeout=15_000):
                    await locator.click()
                clicked = True
                break
            except Exception:
                continue

        if not clicked:
            print("[!] '더보기' 클릭 실패. 통합검색 결과만 사용합니다.", flush=True)
        else:
            print(f"[*] 이동 완료: {page.url}", flush=True)
            await page.wait_for_timeout(2500)
            for _ in range(3):
                await page.mouse.wheel(0, 4000)
                await page.wait_for_timeout(800)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)

        await page.screenshot(path=str(out_dir / "_01_채용공고목록.png"), full_page=True)
        print("[*] 채용공고 목록 페이지 캡처: _01_채용공고목록.png", flush=True)

        jobs = await page.evaluate(
            """() => {
                const anchors = Array.from(document.querySelectorAll('a'));
                const seen = new Set();
                const out = [];
                for (const a of anchors) {
                    const href = a.href || '';
                    if (!/\\/NCS\\/RecruitInfoDetails\\//.test(href)) continue;
                    if (seen.has(href)) continue;
                    seen.add(href);
                    const lines = (a.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
                    const company = lines[0] || '';
                    const title = lines[1] || '';
                    out.push({ href, company, title, raw: a.innerText.trim() });
                }
                return out;
            }"""
        )

        targets = jobs[:max_jobs]
        print(f"[*] 채용공고 {len(jobs)}개 발견, 캡처 대상 {len(targets)}개", flush=True)

        if not targets:
            print("[!] 캡처할 공고가 없습니다.", flush=True)
            await browser.close()
            return

        success, failed = 0, 0
        collected: list[dict] = []
        for idx, job in enumerate(targets, 1):
            label = f"{job['company']}_{job['title']}".strip("_")
            print(f"  [{idx:02d}/{len(targets)}] {label[:60]}", flush=True)
            detail = await context.new_page()
            try:
                await detail.goto(job["href"], wait_until="domcontentloaded", timeout=30_000)
                await detail.wait_for_timeout(2500)

                base_name = f"{idx:02d}_{sanitize_filename(label)}"
                await detail.screenshot(path=str(out_dir / f"{base_name}.png"), full_page=True)

                extracted = await detail.evaluate(
                    """() => {
                        const root = document.querySelector('div.recr_pop_left3') || document.body;
                        const txt = (el) => el ? el.innerText.trim() : '';
                        const pick = (sel) => txt(root.querySelector(sel));

                        const summary = pick('.recr_pop_summary');
                        const condLine = pick('.recr_pop_summary .group.bg1');
                        const deadline = pick('.recr_pop_dday p.t1');
                        const dday = pick('span.num_dday');
                        const companyHeader = pick('.recr_pop_floating_top') || '';

                        let career = '', employment = '', education = '', loc = '';
                        if (condLine) {
                            const parts = condLine.split('|').map(s => s.trim()).filter(Boolean);
                            const reCareer = /신입|경력|인턴십|경력무관/;
                            const reEmp = /정규직|계약직|인턴|파견|프리랜서|단기|아르바이트|병역특례/;
                            const reEdu = /학력|대졸|대학원|고졸|초대졸|석사|박사|학사|중졸/;
                            for (const part of parts) {
                                if (!career && reCareer.test(part)) { career = part; continue; }
                                if (!employment && reEmp.test(part)) { employment = part; continue; }
                                if (!education && reEdu.test(part)) { education = part; continue; }
                                if (!loc) { loc = part; continue; }
                                loc = loc + ' | ' + part;
                            }
                        }

                        let roles = [];
                        if (summary && condLine) {
                            const tail = summary.slice(summary.indexOf(condLine) + condLine.length).trim();
                            if (tail) {
                                roles = tail.split(/[,，、]/).map(s => s.trim()).filter(Boolean);
                            }
                        }

                        return {
                            url: window.location.href,
                            career, employment, education, location: loc,
                            roles, deadline, dday,
                            summary_raw: summary,
                        };
                    }"""
                )

                txt_lines = [
                    f"회사: {job['company']}",
                    f"제목: {job['title']}",
                    f"URL: {extracted['url']}",
                    "",
                    "[조건]",
                    f"경력: {extracted['career']}",
                    f"고용형태: {extracted['employment']}",
                    f"학력: {extracted['education']}",
                    f"위치: {extracted['location']}",
                    "",
                    "[직무 카테고리]",
                    ", ".join(extracted["roles"]) if extracted["roles"] else "(없음)",
                    "",
                    "[마감]",
                    f"{extracted['deadline']}" + (f"  ({extracted['dday']})" if extracted["dday"] else ""),
                ]
                (out_dir / f"{base_name}.txt").write_text("\n".join(txt_lines), encoding="utf-8")

                collected.append({
                    "idx": idx,
                    "company": job["company"],
                    "title": job["title"],
                    "url": extracted["url"],
                    "career": extracted["career"],
                    "employment": extracted["employment"],
                    "education": extracted["education"],
                    "location": extracted["location"],
                    "roles": extracted["roles"],
                    "deadline": extracted["deadline"],
                    "dday": extracted["dday"],
                    "png": f"{base_name}.png",
                    "txt": f"{base_name}.txt",
                })
                success += 1
            except Exception as e:
                print(f"     실패: {e}", flush=True)
                failed += 1
            finally:
                await detail.close()

        (out_dir / "jobs.json").write_text(
            json.dumps(collected, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[완료] 성공 {success} / 실패 {failed}", flush=True)
        print(f"[결과 위치] {out_dir}", flush=True)
        print(f"[메타 인덱스] {out_dir / 'jobs.json'}", flush=True)
        await browser.close()


def main() -> None:
    keyword = sys.argv[1] if len(sys.argv) > 1 else "개발자"
    max_jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    asyncio.run(capture_jobs(keyword, max_jobs))


if __name__ == "__main__":
    main()
