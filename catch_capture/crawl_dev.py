"""캐치 채용공고 → 개발자 직무만 필터링하여 txt 생성 (스크린샷 없음).

- 검색 결과 페이지를 페이지네이션으로 넘기며 공고 링크 수집
- 개발자 카테고리 공고만 상세 페이지 방문
- 상세 iframe에서 JD 텍스트 추출, 이미지 전용일 경우 pytesseract OCR로 보완
- [기술스택]은 JD/OCR 텍스트에서 키워드 매칭

사용법(포그라운드):
    python crawl_dev.py 개발자
    python crawl_dev.py 개발자 20
    python crawl_dev.py 개발자 20 --no-ocr
    python crawl_dev.py 개발자 20 --reset-seen   # 이전 크롤링 기록 초기화

사용법(백그라운드 PID 관리):
    python crawl_dev.py start 개발자 20   # 백그라운드 실행
    python crawl_dev.py status            # 실행 중 여부
    python crawl_dev.py logs              # 최근 로그
    python crawl_dev.py logs 200          # 최근 200줄
    python crawl_dev.py stop              # 종료

이전에 크롤링한 공고는 `catch_capture/seen_jobs.json`에 누적 저장되며,
다음 실행 때 자동으로 제외된다(중복 크롤링 방지).
백그라운드 모드의 PID와 로그는 `catch_capture/crawl_dev.pid` / `crawl_dev.log`.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

SEEN_JOBS_FILE = Path(__file__).parent / "seen_jobs.json"
PID_FILE = Path(__file__).parent / "crawl_dev.pid"
LOG_FILE = Path(__file__).parent / "crawl_dev.log"

SEARCH_URL = "https://www.catch.co.kr/Search/SearchList?Keyword={kw}"
JOB_LINK_SELECTOR = "table.table2.type3 a.tdlink.al"
CATCH_IFRAME_URL = "https://www.catch.co.kr/controls/recruitDetail/{job_id}"
JOB_ID_RE = re.compile(r"/RecruitInfoDetails/(\d+)")
IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEV_PATTERNS = [
    re.compile(r"개발자", re.IGNORECASE),
    re.compile(r"프로그래머", re.IGNORECASE),
    re.compile(
        r"(시스템|네트워크|보안|데이터|머신러닝|클라우드|인프라|QA|테스트|임베디드|펌웨어|AI)\s*엔지니어",
        re.IGNORECASE,
    ),
    re.compile(r"시스템\s*엔지니어\(?SE\)?", re.IGNORECASE),
    re.compile(r"DevOps", re.IGNORECASE),
    re.compile(r"^\s*DBA\s*$", re.IGNORECASE),
    re.compile(r"^\s*QA\s*$", re.IGNORECASE),
    re.compile(r"시스템운영|시스템관리", re.IGNORECASE),
    re.compile(r"프론트엔드|백엔드|풀스택|웹\s*개발|앱\s*개발|모바일\s*개발|게임\s*개발", re.IGNORECASE),
    re.compile(r"^\s*(iOS|안드로이드|Android)\s*$", re.IGNORECASE),
    re.compile(
        r"^\s*(Java|Python|Go|Rust|Kotlin|Swift|PHP|Ruby|Scala|TypeScript|JavaScript|\.NET|Node\.js|C|C\+\+|C#|C/C\+\+)\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"정보보안|머신러닝|빅데이터|\bAI\b", re.IGNORECASE),
    re.compile(r"임베디드|펌웨어", re.IGNORECASE),
    re.compile(r"^\s*(SW|S/W|소프트웨어)", re.IGNORECASE),
    re.compile(r"데이터\s*사이언티스트", re.IGNORECASE),
]

TECH_KEYWORDS = [
    "Java", "Kotlin", "Python", "JavaScript", "TypeScript", "C++", "C#", "C/C++",
    "Go", "Golang", "Rust", "Ruby", "PHP", "Swift", "Scala", "MATLAB", "Dart", "Perl",
    "R Language",
    "React", "Vue", "Angular", "Next.js", "Nuxt", "Svelte", "jQuery",
    "HTML", "CSS", "SCSS", "SASS", "Tailwind",
    "Node.js", "Spring", "Spring Boot", "Django", "Flask", "FastAPI",
    "Express", "NestJS", "Rails", ".NET", "Laravel",
    "iOS", "Android", "Flutter", "React Native",
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Oracle", "MariaDB", "MSSQL",
    "Elasticsearch", "DynamoDB", "Cassandra",
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "K8s", "Jenkins",
    "GitLab", "GitHub Actions", "Terraform", "Ansible", "Nginx", "Apache",
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "OpenCV", "HuggingFace",
    "LangChain", "OpenAI",
    "Selenium", "Appium", "Cypress", "Jest", "JUnit", "Pytest", "Mocha", "BDD",
    "Kafka", "RabbitMQ",
    "Linux", "Unix", "Git", "SVN", "Jira", "Confluence", "GraphQL", "REST API",
    "gRPC", "MSA",
]


def _tech_pattern(kw: str) -> re.Pattern[str]:
    esc = re.escape(kw)
    return re.compile(rf"(?<![A-Za-z0-9가-힣]){esc}(?![A-Za-z0-9가-힣])", re.IGNORECASE)


TECH_REGEX = [(kw, _tech_pattern(kw)) for kw in TECH_KEYWORDS]


class HTMLToText(HTMLParser):
    SKIP_TAGS = {"script", "style"}
    BREAK_TAGS = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5"}

    def __init__(self) -> None:
        super().__init__()
        self.buf: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
        elif tag in self.BREAK_TAGS:
            self.buf.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
        elif tag in self.BREAK_TAGS:
            self.buf.append("\n")

    def handle_data(self, data):
        if self.skip_depth == 0:
            self.buf.append(data)

    def text(self) -> str:
        out = "".join(self.buf)
        out = out.replace("\xa0", " ")
        out = re.sub(r"[ \t]+", " ", out)
        out = re.sub(r" *\n *", "\n", out)
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out.strip()


def _http_get(url: str, timeout: int = 30) -> bytes:
    if url.startswith("//"):
        url = "https:" + url
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_iframe(job_id: str) -> tuple[str, str]:
    """iframe 본문 텍스트, 원본 HTML 반환."""
    url = CATCH_IFRAME_URL.format(job_id=job_id)
    raw = _http_get(url).decode("utf-8", errors="replace")
    parser = HTMLToText()
    parser.feed(raw)
    return parser.text(), raw


def extract_img_urls(html: str) -> list[str]:
    return [m.group(1) for m in IMG_SRC_RE.finditer(html)]


def ocr_images(img_urls: list[str], lang: str = "kor+eng") -> str:
    if not OCR_AVAILABLE or not img_urls:
        return ""
    chunks: list[str] = []
    for src in img_urls:
        try:
            data = _http_get(src, timeout=60)
            img = Image.open(io.BytesIO(data))
            if img.mode not in ("L", "RGB"):
                img = img.convert("RGB")
            text = pytesseract.image_to_string(img, lang=lang)
            text = text.strip()
            if text:
                chunks.append(text)
        except Exception as e:
            print(f"       (OCR 실패 {src[:60]}: {e})", flush=True)
    return "\n\n".join(chunks)


def extract_tech_stack(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for kw, regex in TECH_REGEX:
        if regex.search(text) and kw.lower() not in seen:
            seen.add(kw.lower())
            found.append(kw)
    return found


def is_developer_job(roles: list[str]) -> bool:
    return any(p.search(role or "") for p in DEV_PATTERNS for role in roles)


def seen_jobs_path() -> Path:
    """seen_jobs.json 경로. 통합 모드면 all_data/dev/seen_jobs.json, 아니면 기본."""
    base = os.environ.get("CRAWL_OUTPUT_BASE")
    if base:
        return Path(base).expanduser().resolve() / "dev" / "seen_jobs.json"
    return SEEN_JOBS_FILE


def load_seen_jobs() -> dict[str, dict]:
    path = seen_jobs_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[!] seen_jobs.json 로드 실패, 빈 상태로 시작: {e}", flush=True)
        return {}


def save_seen_jobs(seen: dict[str, dict]) -> None:
    path = seen_jobs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|\n\r\t]+', " ", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name[:80] or "untitled"


async def collect_search_anchors(page, max_pages: int) -> list[dict]:
    """페이지네이션을 넘기며 공고 링크 수집 (중복 제거)."""
    seen_hrefs: set[str] = set()
    all_jobs: list[dict] = []

    for page_num in range(1, max_pages + 1):
        await page.wait_for_timeout(1500)
        jobs = await page.evaluate(
            """() => {
                const anchors = Array.from(document.querySelectorAll('a[href*="/NCS/RecruitInfoDetails/"]'));
                const seen = new Set();
                const out = [];
                for (const a of anchors) {
                    const href = a.href || '';
                    if (seen.has(href)) continue;
                    seen.add(href);
                    const lines = (a.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
                    const company = lines[0] || '';
                    const title = lines[1] || '';
                    out.push({ href, company, title });
                }
                return out;
            }"""
        )
        new_count = 0
        for j in jobs:
            if j["href"] not in seen_hrefs:
                seen_hrefs.add(j["href"])
                all_jobs.append(j)
                new_count += 1
        print(f"  [page {page_num}] +{new_count}  누적 {len(all_jobs)}개", flush=True)

        if page_num >= max_pages:
            break

        clicked = False
        try:
            next_loc = page.locator("p.page a.next, p.page a.ico.next").first
            if await next_loc.count() > 0:
                cls = await next_loc.get_attribute("class") or ""
                if "disabled" in cls or "off" in cls:
                    print(f"  [page {page_num}] 다음 페이지 없음(disabled), 종료", flush=True)
                    break
                await next_loc.scroll_into_view_if_needed(timeout=3000)
                await next_loc.click(timeout=5000)
                clicked = True
        except Exception as e:
            print(f"  [page {page_num}→{page_num+1}] 다음 클릭 예외: {e}", flush=True)

        if not clicked:
            try:
                num_loc = page.locator(f"p.page a:has-text(\"{page_num + 1}\")").first
                if await num_loc.count() > 0:
                    await num_loc.scroll_into_view_if_needed(timeout=3000)
                    await num_loc.click(timeout=5000)
                    clicked = True
            except Exception:
                pass

        if not clicked:
            print(f"  [page {page_num}→{page_num+1}] 다음 페이지 클릭 실패, 종료", flush=True)
            break
        await page.wait_for_timeout(2500)

    return all_jobs


async def crawl(keyword: str, target: int, max_pages: int, use_ocr: bool) -> None:
    from jobs_common import build_jd_sections, compute_out_dir
    base_dir = Path(__file__).parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = compute_out_dir(base_dir, "dev", keyword, timestamp)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] 저장 경로: {out_dir}", flush=True)
    print(f"[*] OCR 사용: {use_ocr and OCR_AVAILABLE}", flush=True)

    from playwright.async_api import async_playwright

    seen_jobs = load_seen_jobs()
    print(f"[*] 기존 크롤링 기록: {len(seen_jobs)}건 (중복 자동 제외)", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="ko-KR",
            user_agent=USER_AGENT,
        )
        page = await context.new_page()

        target_url = SEARCH_URL.format(kw=quote(keyword))
        print(f"[*] 통합검색 진입: {target_url}", flush=True)
        await page.goto(target_url, wait_until="domcontentloaded", timeout=60_000)
        try:
            await page.wait_for_selector(JOB_LINK_SELECTOR, timeout=15_000)
        except Exception:
            pass
        await page.wait_for_timeout(1500)

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
            print("[!] '더보기' 클릭 실패", flush=True)
            await browser.close()
            return

        print(f"[*] 목록 페이지 진입: {page.url}", flush=True)
        await page.wait_for_timeout(2500)

        candidates = await collect_search_anchors(page, max_pages=max_pages)
        print(f"[*] 후보 공고 총 {len(candidates)}개 (목표 개발자 직무 {target}개)", flush=True)

        before = len(candidates)
        candidates = [c for c in candidates if c["href"] not in seen_jobs]
        already = before - len(candidates)
        if already:
            print(f"[*] 기존 크롤링 제외: {already}개 → 신규 후보 {len(candidates)}개", flush=True)

        if not candidates:
            print("[!] 신규로 크롤링할 공고가 없습니다.", flush=True)
            await browser.close()
            return

        collected: list[dict] = []
        scanned, skipped_nondev, failed = 0, 0, 0

        for job in candidates:
            if len(collected) >= target:
                break
            scanned += 1
            label = f"{job['company']}_{job['title']}".strip("_")
            print(f"  [{scanned:02d}] {label[:60]}", flush=True)
            detail = await context.new_page()
            try:
                await detail.goto(job["href"], wait_until="domcontentloaded", timeout=30_000)
                await detail.wait_for_timeout(1800)

                extracted = await detail.evaluate(
                    """() => {
                        const root = document.querySelector('div.recr_pop_left3') || document.body;
                        const txt = (el) => el ? el.innerText.trim() : '';
                        const pick = (sel) => txt(root.querySelector(sel));

                        const summary = pick('.recr_pop_summary');
                        const condLine = pick('.recr_pop_summary .group.bg1');
                        const deadline = pick('.recr_pop_dday p.t1');
                        const dday = pick('span.num_dday');

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
                        };
                    }"""
                )

                if not is_developer_job(extracted["roles"]):
                    skipped_nondev += 1
                    seen_jobs[job["href"]] = {
                        "status": "skipped_nondev",
                        "crawled_at": timestamp,
                        "company": job["company"],
                        "title": job["title"],
                        "roles": extracted["roles"],
                    }
                    print(f"       ↳ 비개발자, 스킵", flush=True)
                    continue

                m = JOB_ID_RE.search(extracted["url"])
                job_id = m.group(1) if m else None
                desc_text, raw_html = "", ""
                if job_id:
                    try:
                        desc_text, raw_html = fetch_iframe(job_id)
                    except Exception as e:
                        print(f"       ↳ JD fetch 실패: {e}", flush=True)

                has_img = "<img " in raw_html
                trimmed_len = len(re.sub(r"\s+", "", desc_text))
                image_only = has_img and trimmed_len < 30

                ocr_text = ""
                if image_only and use_ocr and OCR_AVAILABLE:
                    img_urls = extract_img_urls(raw_html)
                    print(f"       ↳ JD가 이미지({len(img_urls)}개), OCR 실행", flush=True)
                    ocr_text = ocr_images(img_urls)

                jd_text = desc_text or ""
                if ocr_text:
                    jd_text = (jd_text + "\n\n[이미지 OCR]\n" + ocr_text).strip()

                tech = extract_tech_stack(jd_text)
                jd_parts = build_jd_sections(None, jd_text)

                if jd_text:
                    jd_body = jd_text
                elif image_only:
                    jd_body = "(상세 내용이 이미지로만 제공됩니다. 캐치 사이트에서 직접 확인하세요.)"
                else:
                    jd_body = "(상세 내용을 가져오지 못함)"

                idx = len(collected) + 1
                base_name = f"{idx:02d}_{sanitize_filename(label)}"
                lines = [
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
                    "[기술스택]",
                    ", ".join(tech) if tech else "(JD에서 식별된 기술스택 없음)",
                    "",
                    "[마감]",
                    f"{extracted['deadline']}"
                    + (f"  ({extracted['dday']})" if extracted["dday"] else ""),
                    "",
                    "[채용 상세]",
                    jd_body,
                ]
                (out_dir / f"{base_name}.txt").write_text("\n".join(lines), encoding="utf-8")
                collected.append({
                    "idx": idx,
                    "pid": job_id or "",
                    "job_id": job_id or "",
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
                    "tech_stack": tech,
                    "main_tasks": jd_parts.get("main_tasks", ""),
                    "qualifications": jd_parts.get("qualifications", ""),
                    "preferences": jd_parts.get("preferences", ""),
                    "tech_stack_raw": jd_parts.get("tech_stack_raw", ""),
                    "benefits": jd_parts.get("benefits", ""),
                    "full_jd": jd_text,
                    "image_only_jd": image_only,
                    "ocr_used": bool(ocr_text),
                    "txt": f"{base_name}.txt",
                })
                seen_jobs[job["href"]] = {
                    "status": "collected",
                    "crawled_at": timestamp,
                    "company": job["company"],
                    "title": job["title"],
                    "txt": f"{base_name}.txt",
                }
                print(f"       ✔  ({len(collected)}/{target}) tech={tech[:8]}", flush=True)
            except Exception as e:
                print(f"       실패: {e}", flush=True)
                failed += 1
            finally:
                await detail.close()

        (out_dir / "jobs.json").write_text(
            json.dumps(collected, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        save_seen_jobs(seen_jobs)
        print(
            f"\n[완료] 수집 {len(collected)} / 비개발자 {skipped_nondev} / 실패 {failed} / 훑은 공고 {scanned}",
            flush=True,
        )
        print(f"[결과 위치] {out_dir}", flush=True)
        print(f"[중복 방지 누적: {len(seen_jobs)}건 → {seen_jobs_path()}]", flush=True)
        await browser.close()


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        PID_FILE.unlink(missing_ok=True)
        return None
    if _process_alive(pid):
        return pid
    PID_FILE.unlink(missing_ok=True)
    return None


def cmd_start(crawl_args: list[str]) -> None:
    existing = _read_pid()
    if existing:
        print(f"[!] 이미 실행 중: PID {existing} — 먼저 'stop' 후 다시 시작하세요.", flush=True)
        return
    script = Path(__file__).resolve()
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_fh = open(LOG_FILE, "ab", buffering=0)
    log_fh.write(f"\n===== START {started_at}  args={crawl_args} =====\n".encode("utf-8"))
    proc = subprocess.Popen(
        [sys.executable, "-u", str(script), *crawl_args],
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=script.parent,
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"[*] 백그라운드 시작: PID {proc.pid}", flush=True)
    print(f"    로그: {LOG_FILE}", flush=True)
    print(f"    상태: python {script.name} status", flush=True)
    print(f"    중지: python {script.name} stop", flush=True)


def cmd_stop() -> None:
    pid = _read_pid()
    if not pid:
        print("[*] 실행 중인 프로세스 없음", flush=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"[*] SIGTERM → PID {pid} (최대 10초 대기)", flush=True)
    except OSError as e:
        print(f"[!] SIGTERM 실패: {e}", flush=True)
        PID_FILE.unlink(missing_ok=True)
        return
    for _ in range(20):
        time.sleep(0.5)
        if not _process_alive(pid):
            break
    else:
        try:
            os.kill(pid, signal.SIGKILL)
            print(f"[*] SIGKILL → PID {pid}", flush=True)
        except OSError as e:
            print(f"[!] SIGKILL 실패: {e}", flush=True)
    PID_FILE.unlink(missing_ok=True)
    print("[*] 종료 완료", flush=True)


def cmd_status() -> None:
    pid = _read_pid()
    if pid:
        print(f"[*] 실행 중: PID {pid}", flush=True)
        print(f"    로그: {LOG_FILE}", flush=True)
    else:
        print("[*] 실행 중 아님", flush=True)


def cmd_logs(n: int) -> None:
    if not LOG_FILE.exists():
        print("[!] 로그 파일 없음", flush=True)
        return
    with open(LOG_FILE, "rb") as f:
        lines = f.readlines()[-n:]
    sys.stdout.write(b"".join(lines).decode("utf-8", errors="replace"))


def main() -> None:
    args = sys.argv[1:]

    if args and args[0] in {"start", "stop", "status", "logs"}:
        sub = args[0]
        rest = args[1:]
        if sub == "start":
            cmd_start(rest)
        elif sub == "stop":
            cmd_stop()
        elif sub == "status":
            cmd_status()
        elif sub == "logs":
            n = int(rest[0]) if rest and rest[0].isdigit() else 50
            cmd_logs(n)
        return

    use_ocr = True
    if "--no-ocr" in args:
        use_ocr = False
        args.remove("--no-ocr")
    if "--reset-seen" in args:
        args.remove("--reset-seen")
        path = seen_jobs_path()
        if path.exists():
            path.unlink()
            print(f"[*] {path} 삭제 — 중복 기록 초기화", flush=True)
    keyword = args[0] if len(args) > 0 else "개발자"
    target = int(args[1]) if len(args) > 1 else 20
    max_pages = int(args[2]) if len(args) > 2 else 5
    asyncio.run(crawl(keyword, target, max_pages, use_ocr))


if __name__ == "__main__":
    main()
