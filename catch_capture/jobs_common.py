"""채용 사이트 크롤러 공통 유틸리티.

- HTML → 텍스트 변환
- 이미지 OCR (pytesseract)
- 기술스택 키워드 추출
- 개발자 직무 판정
- 파일명 sanitize / 다운로드 헬퍼
- 이전 실행본의 PID 로딩 (중복 스킵)
"""
from __future__ import annotations

import io
import json
import os
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

DEV_PATTERNS = [
    re.compile(r"개발자", re.IGNORECASE),
    re.compile(r"개발$", re.IGNORECASE),
    re.compile(r"프로그래머", re.IGNORECASE),
    re.compile(
        r"(시스템|네트워크|보안|데이터|머신러닝|클라우드|인프라|QA|테스트|임베디드|펌웨어|AI|소프트웨어|SW|S/W)\s*엔지니어",
        re.IGNORECASE,
    ),
    re.compile(r"DevOps", re.IGNORECASE),
    re.compile(r"\bDBA\b", re.IGNORECASE),
    re.compile(r"\bSRE\b", re.IGNORECASE),
    re.compile(r"\bMLOps\b", re.IGNORECASE),
    re.compile(r"시스템운영|시스템관리", re.IGNORECASE),
    re.compile(r"프론트엔드|백엔드|풀스택|웹\s*개발|앱\s*개발|모바일\s*개발|게임\s*개발|서버\s*개발|클라이언트\s*개발", re.IGNORECASE),
    re.compile(r"^\s*(iOS|안드로이드|Android)\s*$", re.IGNORECASE),
    re.compile(
        r"^\s*(Java|Python|Go|Rust|Kotlin|Swift|PHP|Ruby|Scala|TypeScript|JavaScript|\.NET|Node\.js|C|C\+\+|C#|C/C\+\+)\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"정보보안|머신러닝|빅데이터|\bAI\b|데이터\s*분석|데이터\s*엔지니어", re.IGNORECASE),
    re.compile(r"임베디드|펌웨어|반도체\s*설계", re.IGNORECASE),
    re.compile(r"데이터\s*사이언티스트", re.IGNORECASE),
    re.compile(r"블록체인", re.IGNORECASE),
]

TECH_KEYWORDS = [
    "Java", "Kotlin", "Python", "JavaScript", "TypeScript", "C++", "C#", "C/C++",
    "Go", "Golang", "Rust", "Ruby", "PHP", "Swift", "Scala", "MATLAB", "Dart", "Perl",
    "R Language",
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


def html_to_text(html: str) -> str:
    parser = HTMLToText()
    parser.feed(html)
    return parser.text()


def http_get(url: str, timeout: int = 30, referer: str | None = None) -> bytes:
    if url.startswith("//"):
        url = "https:" + url
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def extract_img_urls(html: str) -> list[str]:
    return [m.group(1) for m in IMG_SRC_RE.finditer(html)]


def ocr_images(img_urls: list[str], lang: str = "kor+eng", referer: str | None = None) -> str:
    if not OCR_AVAILABLE or not img_urls:
        return ""
    chunks: list[str] = []
    for src in img_urls:
        try:
            data = http_get(src, timeout=60, referer=referer)
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


def is_developer_job(*fields: str | list[str] | None) -> bool:
    """직무 카테고리, 제목, 부서명 등 어떤 텍스트든 받아 개발자 여부 판정."""
    texts: list[str] = []
    for f in fields:
        if f is None:
            continue
        if isinstance(f, list):
            texts.extend([s for s in f if s])
        else:
            texts.append(f)
    blob = " | ".join(texts)
    return any(p.search(blob) for p in DEV_PATTERNS)


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|\n\r\t]+', " ", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name[:80] or "untitled"


def is_image_only(html: str, text: str, min_text_len: int = 30) -> bool:
    """JD가 사실상 이미지로만 구성됐는지 판정."""
    has_img = "<img " in (html or "").lower()
    trimmed_len = len(re.sub(r"\s+", "", text or ""))
    return has_img and trimmed_len < min_text_len


BROWSER_STATE_FILE = Path(__file__).parent / ".browser_state.json"


def _browser_state() -> dict | None:
    if not BROWSER_STATE_FILE.exists():
        return None
    try:
        return json.loads(BROWSER_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _is_pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        import os as _os
        _os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


async def connect_browser(
    p,
    *,
    headless: bool = False,
    viewport: dict | None = None,
    locale: str = "ko-KR",
    user_agent: str = USER_AGENT,
):
    """browser_daemon이 띄운 Chromium에 붙거나, 없으면 새로 launch.

    반환: (browser, context, owns_browser)
        owns_browser=True  → 크롤러가 직접 띄웠음. 끝낼 때 browser.close() 필수.
        owns_browser=False → 데몬 브라우저에 붙음. browser.close() 금지(다른 크롤러도 쓰는 중).
                             context도 데몬 소유라 새 page만 열고 끝낼 때 page.close()만.

    사용 예:
        async with async_playwright() as p:
            browser, ctx, owns = await connect_browser(p)
            page = await ctx.new_page()
            try:
                ...
            finally:
                await page.close()
                if owns:
                    await browser.close()
    """
    state = _browser_state()
    if state and _is_pid_alive(state.get("pid", 0)):
        cdp = state.get("cdp_endpoint")
        if cdp:
            try:
                browser = await p.chromium.connect_over_cdp(cdp)
                ctx = browser.contexts[0] if browser.contexts else await browser.new_context(
                    viewport=viewport or {"width": 1440, "height": 900},
                    locale=locale,
                    user_agent=user_agent,
                )
                print(f"[*] 데몬 브라우저에 연결 (PID {state['pid']}, {cdp})", flush=True)
                return browser, ctx, False
            except Exception as e:
                print(f"[!] 데몬 연결 실패({e}) — 새 브라우저로 폴백", flush=True)

    # Anti-bot 차단 회피: 자동화 시그널 숨김 (saramin 같은 사이트가 headless를 감지해
    # body 없는 stub HTML을 내주는 케이스 대응).
    launch_args = [
        "--disable-blink-features=AutomationControlled",
    ]
    browser = await p.chromium.launch(headless=headless, args=launch_args)
    ctx = await browser.new_context(
        viewport=viewport or {"width": 1440, "height": 900},
        locale=locale,
        user_agent=user_agent,
    )
    await ctx.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """
    )
    print("[*] 신규 브라우저 launch (데몬 미실행)", flush=True)
    return browser, ctx, True


def get_unified_base() -> Path | None:
    """`CRAWL_OUTPUT_BASE` 환경변수가 설정돼 있으면 그 경로를 반환, 아니면 None."""
    v = os.environ.get("CRAWL_OUTPUT_BASE")
    return Path(v).expanduser().resolve() if v else None


def compute_out_dir(base_dir: Path, site: str, keyword: str, timestamp: str) -> Path:
    """크롤러 출력 경로를 결정.

    - 환경변수 `CRAWL_OUTPUT_BASE`가 있으면: <CRAWL_OUTPUT_BASE>/<site>/<keyword>_<timestamp>/
    - 없으면(기존 동작): <base_dir>/screenshots/<site>_<keyword>_<timestamp>/
    """
    unified = get_unified_base()
    safe_kw = sanitize_filename(keyword)
    if unified:
        return unified / site / f"{safe_kw}_{timestamp}"
    return base_dir / "screenshots" / f"{site}_{safe_kw}_{timestamp}"


def fixed_out_dir(base_dir: Path, site: str, keyword: str) -> Path:
    """타임스탬프 없이 사이트+키워드만으로 결정되는 누적 폴더 경로.

    재실행 시 같은 폴더에 이어 쌓도록 설계. jobs.json을 통한 dedup과 짝.
    """
    unified = get_unified_base()
    safe_kw = sanitize_filename(keyword)
    if unified:
        return unified / site / safe_kw
    return base_dir / "screenshots" / f"{site}_{safe_kw}"


def load_existing_jobs(out_dir: Path) -> list[dict]:
    """누적 폴더의 jobs.json을 로드. 없거나 깨졌으면 빈 리스트."""
    p = out_dir / "jobs.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_jobs_json(out_dir: Path, collected: list[dict]) -> None:
    """수집 리스트를 jobs.json에 원자적으로 저장(임시→rename)."""
    p = out_dir / "jobs.json"
    tmp = out_dir / "jobs.json.tmp"
    tmp.write_text(json.dumps(collected, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def load_seen_pids(
    base_dir: Path,
    site_prefix: str,
    pid_keys: tuple[str, ...] = ("pid", "position_id", "rec_idx", "gno", "job_id"),
) -> set[str]:
    """이전 실행본의 jobs.json을 훑어 수집된 PID 집합을 반환.

    스캔 대상:
      - `base_dir/screenshots/{site_prefix}_*/jobs.json`  (기존 위치)
      - `<CRAWL_OUTPUT_BASE>/<site_prefix>/*/jobs.json`    (통합 폴더)
    사이트별로 PID 필드명이 다를 수 있어 `pid_keys`에 명시된 모든 키를 시도한다.
    """
    seen: set[str] = set()

    def _scan(glob_root: Path, pattern: str) -> None:
        if not glob_root.exists():
            return
        for run_dir in glob_root.glob(pattern):
            jobs_json = run_dir / "jobs.json"
            if not jobs_json.exists():
                continue
            try:
                data = json.loads(jobs_json.read_text(encoding="utf-8"))
            except Exception:
                continue
            for j in data:
                for k in pid_keys:
                    v = j.get(k)
                    if v:
                        seen.add(str(v).strip())
                        break

    _scan(base_dir / "screenshots", f"{site_prefix}_*")
    unified = get_unified_base()
    if unified:
        _scan(unified / site_prefix, "*")
    return seen


SECTION_HEADERS = {
    "main_tasks": [
        "주요업무", "주요 업무", "담당업무", "담당 업무", "업무내용", "업무 내용",
        "수행업무", "수행 업무", "직무내용", "직무 내용", "주요 담당업무", "주요 수행업무",
        "What you’ll do", "What you will do", "Responsibilities", "Role",
    ],
    "qualifications": [
        "자격요건", "자격 요건", "필수요건", "필수 요건", "필수사항", "필수 사항",
        "지원자격", "지원 자격", "지원대상", "지원 대상", "참가자격", "참가 자격",
        "참가대상", "참가 대상", "교육대상", "교육 대상", "응시자격", "응시 자격",
        "필요역량", "필요 역량", "필요기술", "필요 기술", "요구사항", "요구 사항",
        "Requirements", "Qualifications", "Must have",
    ],
    "preferences": [
        "우대사항", "우대 사항", "우대요건", "우대 요건", "우대조건", "우대 조건",
        "Preferred", "Nice to have", "Plus",
    ],
    "tech_stack_raw": [
        "기술스택", "기술 스택", "사용기술", "사용 기술", "기술환경", "기술 환경",
        "개발환경", "개발 환경", "Tech stack", "Stack",
    ],
    "benefits": [
        "혜택 및 복지", "복지 및 혜택", "복지", "혜택", "복리후생", "복지/혜택",
        "Benefits", "Perks", "Welfare",
    ],
}

_HEADER_TO_KEY: list[tuple[str, str]] = [
    (h, key) for key, headers in SECTION_HEADERS.items() for h in headers
]
_HEADER_TO_KEY.sort(key=lambda kv: len(kv[0]), reverse=True)


def _header_match(line: str) -> str | None:
    """라인이 섹션 헤더인 경우 정규화된 key 반환, 아니면 None."""
    s = line.strip().strip("[]【】■◆●▶▷-·•:：").strip()
    # leading/trailing 이모지·기호 제거 (예: "📋 주요업무" → "주요업무", "🔥자격요건:" → "자격요건")
    s = re.sub(r"^\W+", "", s, flags=re.UNICODE)
    s = re.sub(r"\W+$", "", s, flags=re.UNICODE)
    if not s or len(s) > 40:
        return None
    s_low = s.lower()
    for header, key in _HEADER_TO_KEY:
        h_low = header.lower()
        if s_low == h_low or s_low.startswith(h_low + " ") or s_low.rstrip(":：") == h_low:
            return key
    # OCR로 prefix가 깨진 경우 (예: "를 자격요건"): "짧은 prefix + 공백 + 헤더" 패턴 인정
    parts = s.split()
    if len(parts) == 2 and len(parts[0]) <= 2:
        last = parts[1].rstrip(":：").lower()
        for header, key in _HEADER_TO_KEY:
            if last == header.lower():
                return key
    return None


_STOP_HEADERS = [
    "근무조건", "근무 조건", "근무환경", "근무 환경",
    "근무지", "근무 지", "근무지역", "근무 지역", "근무형태", "근무 형태",
    "고용형태", "고용 형태", "급여", "연봉",
    "채용절차", "전형절차", "전형 절차",
    "접수방법", "접수기간", "접수 방법", "접수 기간", "지원방법", "지원 방법",
    "유의사항", "유의 사항", "기타사항", "기타 사항",
    "제출서류", "제출 서류", "첨부서류", "첨부 서류",
    "회사소개", "회사 소개", "기업소개", "기업 소개",
]


def _is_stop_header(line: str) -> bool:
    s = line.strip().strip("[]【】■◆●▶▷-·•:：").strip()
    s = re.sub(r"^\W+", "", s, flags=re.UNICODE)
    s = re.sub(r"\W+$", "", s, flags=re.UNICODE)
    if not s or len(s) > 40:
        return False
    s_low = s.lower()
    for h in _STOP_HEADERS:
        h_low = h.lower()
        if s_low == h_low or s_low.startswith(h_low + " ") or s_low.rstrip(":：") == h_low:
            return True
    return False


def split_jd_sections(text: str) -> dict[str, str]:
    """JD 본문 텍스트에서 주요업무/자격요건/우대사항/기술스택/혜택 섹션을 best-effort로 분리.

    헤더 라인(예: "주요업무", "자격요건") 다음부터 다음 헤더 직전까지를 해당 섹션 본문으로 본다.
    어떤 사이트는 dl/dt/dd로 이미 분리돼 있고, 어떤 사이트는 한 덩어리 텍스트라 이 함수가 후자 케이스를 처리한다.
    """
    out = {k: "" for k in SECTION_HEADERS}
    if not text:
        return out
    lines = text.splitlines()
    current: str | None = None
    buf: dict[str, list[str]] = {k: [] for k in SECTION_HEADERS}
    inline_re = re.compile(r"^\s*[\[【(]([^\]\)】]{1,30})[\]\)】]\s*(.*)$")
    for raw in lines:
        # "[헤더] 본문" 또는 "(헤더) 본문" 처럼 한 줄에 헤더+본문이 있는 경우 분리 (사람인/캐치)
        m = inline_re.match(raw)
        if m:
            cand, rest = m.group(1).strip(), m.group(2).strip()
            inline_key = _header_match(cand)
            if inline_key:
                current = inline_key
                if rest:
                    buf[current].append(rest)
                continue
            if _is_stop_header(cand):
                current = None
                continue
        key = _header_match(raw)
        if key:
            current = key
            continue
        if _is_stop_header(raw):
            current = None
            continue
        if current:
            buf[current].append(raw)
    for k, ls in buf.items():
        body = "\n".join(ls).strip("\n").strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        out[k] = body
    return out


def build_jd_sections(
    structured: dict[str, str] | None,
    full_text: str | None,
) -> dict[str, str]:
    """사이트가 dl/dt/dd 등으로 이미 키-값 분리한 결과(`structured`)를 우선,
    없으면 `full_text`에서 헤더 기반 분리를 시도한다.

    반환: {main_tasks, qualifications, preferences, tech_stack_raw, benefits}
    """
    result = {k: "" for k in SECTION_HEADERS}
    if structured:
        for raw_key, val in structured.items():
            if not val:
                continue
            key = _header_match(raw_key)
            if key and not result[key]:
                result[key] = val.strip()
    # full_text 기반 보완: 비어있는 키만 채움
    if full_text and any(not v for v in result.values()):
        parsed = split_jd_sections(full_text)
        for k, v in parsed.items():
            if v and not result[k]:
                result[k] = v
    return result
