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

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright

from crawlers.jobs_common import (
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
    jitter,
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
            await page.wait_for_timeout(jitter(2500))

        try:
            await page.wait_for_selector("a[href*='/Recruit/GI_Read/']", timeout=15_000)
        except Exception:
            print(f"  [page {page_num}] 결과 미발견", flush=True)
            break
        await page.wait_for_timeout(jitter(1000))

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


# 카드 메타 한 칸에 들어갈 만한 길이. 이보다 길면 공고 제목이나 본문 한 줄이
# 흘러들어온 것이다("[국비최대무료/기숙사무료/취업연계]AI/빅데이터/풀스택/KDT단기심화").
META_MAX = 20

# 길이만으로는 부족하다. "프리랜서 Java 백엔드 개발자 모집"(19자)처럼 짧은 제목은
# 키워드로 시작하고 길이도 통과한다. 메타 칸에는 절대 안 들어가는 낱말로 한 겹 더 건다.
# 마감 칸에는 적용하지 않는다 — "채용시 마감"이 정상 값이다.
TITLEISH = re.compile(r"채용|모집|개발자|엔지니어|인재|담당자|Pool", re.I)


def parse_raw_meta(raw_text: str) -> dict:
    """카드 raw_text에서 위치/경력/학력/고용형태/마감 추정.

    **줄이 값을 담고 있기만 하면 안 되고, 값 자체여야 한다.** 예전 규칙은 키워드가
    줄 안 어디에 있기만 하면 그 줄 전체를 값으로 썼다. 그래서 제목에 '단기'가 든
    'KDT단기심화' 공고는 제목이 통째로 고용형태 칸에 들어앉았고, 실제로 고용형태가
    채워진 242건 중 225건(92%)이 그런 쓰레기였다 — 217건은 제목과 글자 하나까지 같았다.
    경력도 3,398건 중 704건(20%), 학력도 71건 중 17건이 같은 꼴이었다.

    근무지(re_loc)는 이미 같은 이유로 `^` 앵커가 붙어 있었다. 나머지 세 칸에도
    같은 규칙을 적용한다 — 줄 **머리**에서 시작하고 메타 칸 길이를 넘지 않을 것.
    못 잡으면 빈 칸으로 둔다. 틀린 값보다 빈 값이 낫다.
    """
    out = {"location": "", "career": "", "education": "", "employment": "", "deadline": ""}
    lines = [s.strip() for s in raw_text.splitlines() if s.strip()]
    re_career = re.compile(r"^(신입|경력|인턴|경력무관)")
    re_emp = re.compile(r"^(정규직|계약직|인턴|파견|프리랜서|단기|아르바이트|위촉직|"
                        r"전문연구요원|산업기능요원|병역특례)")
    re_edu = re.compile(r"^(학력|대졸|대학원|대학|고졸|초대졸|석사|박사|학사)")
    # 시도로 **시작하는** 줄만 근무지로 본다. 예전 규칙은 시도 이름이 줄 안 어디에
    # 있기만 하면 잡아서, "[울산] 제조 시스템 개발자 모집" 같은 공고 제목이 근무지
    # 칸에 들어앉았다(그런 공고가 87건 있었다). 못 잡으면 빈 칸으로 두고,
    # pipeline/backfill_location 이 공고 페이지의 JSON-LD 에서 진짜 주소를 받아온다 —
    # 틀린 값보다 빈 값이 낫다.
    re_loc = re.compile(r"^(서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)")
    re_dday = re.compile(r"^D-|채용시|상시|마감|~\d+/\d+")
    for s in lines:
        # 메타 칸에 들어갈 수 없는 길이면 어느 칸에도 넣지 않는다. 마감 표기만
        # 예외다 — "~ 06/14(일) 23시 마감" 처럼 길어질 수 있고 파서가 따로 흡수한다.
        short = len(s) <= META_MAX and not TITLEISH.search(s)
        if not out["career"] and short and re_career.match(s):
            out["career"] = s
        elif not out["employment"] and short and re_emp.match(s):
            out["employment"] = s
        elif not out["education"] and short and re_edu.match(s):
            out["education"] = s
        elif not out["deadline"] and re_dday.search(s):
            out["deadline"] = s
        elif not out["location"] and short and re_loc.match(s):
            out["location"] = s
    return out


def _selftest() -> int:
    """`python -m crawlers.crawl_jobkorea --selftest` — 메타 칸 오염 회귀 방지.

    아래 '거부' 항목은 전부 실제 데이터에서 그 칸에 들어앉아 있던 값이다.
    """
    ok_cases = [
        ("정규직", "employment"), ("정규직/계약직", "employment"),
        ("정규직(수습 3개월)", "employment"), ("병역특례", "employment"),
        ("신입", "career"), ("경력3년↑", "career"), ("경력무관", "career"),
        ("신입 지원 가능", "career"), ("신입·경력", "career"),
        ("학력무관", "education"), ("대졸이상", "education"),
        ("석사 이상 (전공 무관)", "education"),
        ("서울 강남구", "location"), ("경기 성남시 분당구", "location"),
    ]
    reject = [
        "[국비최대무료/기숙사무료/취업연계]AI/빅데이터/풀스택/KDT단기심화",
        "[아이모비] 웹 풀스택 개발자(정규직/신입)",
        "SK하이닉스(SK Hynix) React/Java 개발자(정규직/계약직/프리랜서) 채용",
        "㈜서일엔지니어링 2026년 정규직 채용(웹 개발자 프론트엔드/백엔드)",
        "SI 및 웹 개발자 채용(프리랜서)",
        "[ICB] 기업부설연구소 시스템엔지니어 정규직(5년 이상) 채용",
        "정보보안솔루션 경력개발자",
        "PC 애플리케이션 개발자 모집(경력직)",
        "수습기간 3개월, 수습기간 근무평가 후, 정규직으로 채용",
        "대학(2,3년) 이상 (졸업 예정자 가능) 소프트웨어 공학, 컴퓨터 공학 등 관련학과 전공자",
        "[울산] 제조 시스템 개발자 모집",
    ]
    failed = 0
    for text, field in ok_cases:
        got = parse_raw_meta(text)
        if got.get(field) != text:
            failed += 1
            print(f"FAIL 받아들여야 함 {text!r} → {field}, 실제 {got}")
    for text in reject:
        got = parse_raw_meta(text)
        dirty = {k: v for k, v in got.items() if v and k != "deadline"}
        if dirty:
            failed += 1
            print(f"FAIL 거부해야 함 {text[:40]!r} → {dirty}")
    total = len(ok_cases) + len(reject)
    print(f"crawl_jobkorea selftest: {total - failed}/{total} 통과")
    return 1 if failed else 0


DETAIL_URL = "https://www.jobkorea.co.kr/Recruit/GI_Read/{gno}"
_LD_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)


def fetch_company(gno: str, referer: str) -> str:
    """검색 카드에서 회사명을 못 얻었을 때만 상세 페이지에서 한 번 더 시도한다.

    카드는 로고 이미지의 alt 와 /Corp/ 링크 두 가지로 회사명을 읽는데, 일부 카드
    변종에는 둘 다 없어 회사명이 빈 채로 저장돼 왔다(전체의 약 2.8%, 492건).
    빈 회사명은 재공고 추적의 동일성 키를 (사이트, 제목) 으로 떨어뜨리고 기업별
    집계에서도 통째로 빠지므로, 값 하나가 없는 것 이상의 손해가 난다.

    상세 페이지는 schema.org JobPosting 을 서버 HTML 에 그대로 실어 보낸다. 이쪽이
    DOM 클래스명보다 훨씬 안정적이라 1순위로 쓰고, 실패하면 <title> 의
    '<회사> 채용 - <제목> | 잡코리아' 형태를 판다.

    카드에서 이미 얻었으면 부르지 않으므로 추가 요청은 36건에 1번 꼴이다.
    """
    try:
        raw = http_get(DETAIL_URL.format(gno=gno), referer=referer).decode("utf-8", errors="replace")
    except Exception:
        return ""
    m = _LD_RE.search(raw)
    if m:
        try:
            data = json.loads(m.group(1))
            name = ((data or {}).get("hiringOrganization") or {}).get("name")
            if name:
                return str(name).strip()
        except (json.JSONDecodeError, AttributeError):
            pass
    t = _TITLE_RE.search(raw)
    if t:
        head = t.group(1).split("채용 -")[0].strip()
        if head and len(head) <= 60:
            return head
    return ""


def fetch_jd(gno: str, referer: str) -> tuple[str, str]:
    url = DETAIL_IFRAME_URL.format(gno=gno)
    raw = http_get(url, referer=referer).decode("utf-8", errors="replace")
    # 본문은 #detail-content 안에 있음; 못 찾으면 전체 HTML 사용
    m = re.search(r'id="detail-content"[^>]*>(.*?)</div>\s*</td>', raw, re.DOTALL | re.IGNORECASE)
    body = m.group(1) if m else raw
    return body, html_to_text(body)


async def crawl(keyword: str, target: int, max_pages: int, use_ocr: bool) -> None:
    base_dir = Path(__file__).resolve().parent.parent
    out_dir = fixed_out_dir(base_dir, "jobkorea", keyword)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] 저장 경로(누적): {out_dir}", flush=True)
    print(f"[*] OCR 사용: {use_ocr and OCR_AVAILABLE}", flush=True)

    collected: list[dict] = load_existing_jobs(out_dir)
    base_count = len(collected)  # 이번 회차 신규 target건만 수집(상한 없이 누적)
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
        from crawlers import block_detect
        if await block_detect.scan_page(page, "jobkorea"):
            print("[!] 차단/캡차 감지 — 이번 런 조기 종료(백오프는 crawl_all이 처리)", flush=True)
            await browser.close()
            return
        await page.wait_for_timeout(jitter(2500))

        candidates = await collect_search_cards(page, keyword=keyword, max_pages=max_pages)
        print(f"[*] 후보 공고 총 {len(candidates)}개 (목표 {target}개, 이미 보유 {len(collected)}개)", flush=True)

        scanned = skipped_nondev = skipped_dup = failed = 0
        for job in candidates:
            if len(collected) - base_count >= target:
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
                # 카드에서 회사명을 못 얻었으면 상세 페이지에서 보충한다. JD 를 받기
                # 직전에 하는 이유는, 여기까지 온 공고만 실제로 저장되기 때문이다
                # (중복·비개발 공고는 위에서 이미 걸러졌다).
                if not (job.get("company") or "").strip():
                    got = fetch_company(job["gno"], referer=job["href"])
                    if got:
                        job["company"] = got
                        print(f"       ↳ 회사명 보충: {got}", flush=True)
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
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    main()
