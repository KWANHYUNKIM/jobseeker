"""채용 사이트 크롤러 공통 유틸리티.

- HTML → 텍스트 변환
- 이미지 OCR (pytesseract)
- 기술스택 키워드 추출
- 개발자 직무 판정
- 파일명 sanitize / 다운로드 헬퍼
- 이전 실행본의 PID 로딩 (중복 스킵)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

import io
import json
import os
import random
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


def jitter(base_ms: int, ratio: float = 0.35, floor_ms: int = 250) -> int:
    """고정 대기시간(ms)에 ±ratio 범위의 랜덤 지터를 더한다.

    봇 탐지는 '정확히 일정한 간격'의 요청을 의심하므로, 페이지 대기마다
    값을 흔들어 사람의 불규칙한 호흡을 흉내낸다. 예: jitter(1200) → 약 780~1620.
    """
    if base_ms <= 0:
        return 0
    delta = base_ms * ratio
    return max(floor_ms, int(random.uniform(base_ms - delta, base_ms + delta)))

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
    # --- 영어 공고(해외/ATS) 대응 ---
    re.compile(r"\b(developer|programmer)\b", re.IGNORECASE),
    re.compile(r"\b(data\s*scientist|data\s*engineer|site\s*reliability|devops|sre|mlops)\b",
               re.IGNORECASE),
]

# 영어 "... Engineer" 중 개발직이 아닌 것(세일즈/지원/하드웨어 등)을 걸러내는 배제 규칙.
# is_developer_job 의 영어 fallback 에서만 사용한다.
NON_DEV_EN = re.compile(
    r"\b(sales|solutions?|pre-?sales|support|customer|field|hardware|mechanical|"
    r"electrical|civil|chemical|industrial|manufacturing|process|biomedical|"
    r"account|marketing|recruit|talent|people|finance|legal|design|business|"
    r"counsel|attorney|paralegal|advocate|evangelist|relations)\b",
    re.IGNORECASE,
)
# is_developer_job 에서 "강한 개발 신호"로 취급하는 토큰(영어 fallback 가드용).
# 단, "Developer Relations/Advocate/Marketing/Product ..." 같은 DevRel·마케팅 직군은
# 코딩 직무가 아니므로 강한 신호에서 제외한다.
_STRONG_DEV_EN = re.compile(
    r"\b(developer|programmer)\b"
    r"(?!\s+(relations?|advocate|marketing|product|experience|community|evangelist|success))"
    r"|\b(devops|sre|mlops)\b",
    re.IGNORECASE,
)
# 개발직임을 강하게 시사하는 영어 "Engineer" 앞 수식어.
DEV_EN_ENGINEER = re.compile(
    r"\b(software|backend|back-?end|frontend|front-?end|full-?stack|web|mobile|"
    r"ios|android|game|systems?|embedded|firmware|platform|data|ml|ai|cloud|"
    r"infrastructure|infra|security|network|blockchain|qa|test|automation|api|"
    r"application|staff|senior|principal|lead|junior|react|node|java|python|"
    r"golang|go|rust|kotlin|swift|scala|ruby|php|\.net|c\+\+)\b[\w\s/,+-]*\bengineer(ing)?\b",
    re.IGNORECASE,
)

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
    out = []
    for m in IMG_SRC_RE.finditer(html):
        url = m.group(1)
        # 원문 HTML 에 주소 앞부분이 두 번 붙은 경우가 있다("https://pds…/https://pds…/x.jpg") — 마지막 완전한 주소만
        last = max(url.rfind("https://"), url.rfind("http://"))
        out.append(url[last:] if last > 0 else url)
    return out


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
    strong_engineer = bool(DEV_EN_ENGINEER.search(blob))  # 개발 수식어 + Engineer
    # 영어 "... Engineer" fallback: 개발 수식어가 붙어 있고 세일즈/지원 등
    # 비개발 키워드가 없을 때만 개발직으로 인정한다("Sales Engineer" 배제).
    if strong_engineer and not NON_DEV_EN.search(blob):
        return True
    if any(p.search(blob) for p in DEV_PATTERNS):
        # 약한 매치(예: 'AI' 단독)가 영어 비개발 제목("AI ... Marketing/Sales")에
        # 오탐되는 것 차단: 비개발 키워드가 있고 강한 개발 신호가 없으면 제외.
        if (NON_DEV_EN.search(blob) and not strong_engineer
                and not _STRONG_DEV_EN.search(blob)):
            return False
        return True
    return False


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|\n\r\t]+', " ", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name[:80] or "untitled"


def is_image_only(html: str, text: str, min_text_len: int = 30) -> bool:
    """JD 내용이 사실상 이미지에 있는지 판정 — 그러면 OCR 을 돌린다.

    예전에는 글자가 30자 미만일 때만 이미지 공고로 봤다. 그런데 포스터 한 장에 '유의사항'·검색 키워드·
    블로그 주소 같은 짧은 글이 붙은 공고가 많아(사람인 본문 60~160자) OCR 을 건너뛰었고, 주요업무·
    자격요건·우대사항이 통째로 비었다. 그림이 있고 글이 짧은데(400자 미만) 그 글에서 세 칸 중
    하나도 안 나뉘면 내용은 그림 안에 있다고 본다.
    """
    if "<img " not in (html or "").lower():
        return False
    trimmed_len = len(re.sub(r"\s+", "", text or ""))
    if trimmed_len < min_text_len:
        return True
    if trimmed_len < 400:
        parts = split_jd_sections(text or "")
        return not any(parts[k] for k in ("main_tasks", "qualifications", "preferences"))
    return False


BROWSER_STATE_FILE = Path(__file__).resolve().parent.parent / ".browser_state.json"


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


# ── 이번 회차에 목록에서 본 것 ─────────────────────────────────────────
# jobs.json 은 **누적본**이다 — 한 번 수집한 공고는 원본에서 내려가도 남는다.
# 그래서 jobs.json 만 보고는 "지금 올라와 있나"를 알 수 없고, 정본 DB 는 누적본의
# 모든 공고를 매 사이클 "방금 봤다"로 찍어 gone_at 이 평소 사이클에서 한 번도
# 찍히지 않았다(9/8·9/20 일괄 작업 때만 찍혔다). 목록 단계에서 본 pid 를 따로 남긴다.
LISTING_FILE = "listed.json"


def save_listing(out_dir: Path, pids, *, complete_scopes=None) -> None:
    """이번 회차 목록에서 본 pid 들을 `listed.json` 에 남긴다(덮어쓰기).

    `complete_scopes` 는 **목록을 끝까지 본 범위**다. ats 는 보드 API 가 그 회사의
    공고 전부를 주므로 받아 온 보드마다 "여기 없으면 내려간 것" 이라고 말할 수 있다.
    검색 결과 앞 몇 쪽만 보는 사이트는 None — 안 보인 건 뒤쪽 쪽에 있을 수도 있다.
    중복 스킵한 공고도 pid 에 넣는다. 목록에 **있었다**는 사실이 중요하다.
    """
    from datetime import datetime as _dt
    payload = {
        "at": _dt.now().isoformat(timespec="seconds"),
        "pids": sorted({str(p).strip() for p in pids if str(p or "").strip()}),
    }
    if complete_scopes is not None:
        payload["complete_scopes"] = sorted(set(complete_scopes))
    p = out_dir / LISTING_FILE
    tmp = out_dir / (LISTING_FILE + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def load_listing(out_dir: Path) -> dict | None:
    """`listed.json` 을 읽는다. 없거나 깨졌으면 None."""
    p = out_dir / LISTING_FILE
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("pids"), list) else None
    except Exception:
        return None


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


# 머리말을 말로 쓰는 공고 — "이런 업무를 해요", "# 이런 분과 함께하고 싶어요"(토스),
# "✔ 이런 역량을 갖춘 분을 찾습니다"(그리팅), "You will:", "Bonus Points"(Greenhouse) 따위.
# 정확히 같은 낱말만 알아보던 때는 이런 공고의 주요업무·자격요건·우대사항이 통째로 비었다
# (2026-10: 토스 100%·Lever 93%·NHN 89%·Greenhouse 46% 가 셋 다 빈 공고). 위에서부터 처음 맞는 줄이 이긴다 —
# '우대'·'더 좋아요' 가 '자격'보다 먼저 와야 "자격요건 및 우대사항" 이 아닌 "이런 분이면 더 좋아요" 가 우대로 간다.
_HEADER_PATTERNS: list[tuple[str, re.Pattern]] = [(k, re.compile(rx, re.I)) for k, rx in [
    # 끊는 머리말(지원 절차·회사 소개·급여…) — 키 None. 아래 어느 것보다 먼저 본다.
    (None, r"합류\s*여정|채용\s*(절차|프로세스|과정)|전형\s*(절차|과정)|지원\s*(방법|서류|시|하는\s*방법)|"
           r"이력서는|지원서는|유의\s*(사항|해)|꼭\s*확인|접수|제출\s*서류|회사\s*소개|기업\s*소개|팀\s*소개|"
           r"합류하게\s*될\s*팀|우리\s*팀은|동료를\s*위한\s*한마디|근무\s*(조건|환경|지|형태|요일|장소)|고용\s*형태|"
           r"급여|연봉|처우|^about\s+(us|the\s+team|the\s+company|[a-z][\w.&' -]{0,30})$|^who\s+we\s+are|"
           r"^our\s+(story|mission|values|commitment|culture|team)|diversity|equal\s+opportunity|"
           r"salary|pay\s+(range|transparency)|compensation|interview\s+process|how\s+to\s+apply|"
           r"^location|^the\s+team$|^your\s+future\s+team|accommodation|privacy|#li-"),
    ("preferences", r"우대|더\s*좋아요|더욱?\s*좋(습니다|아요|겠)|이면\s*좋|있다면\s*좋|있으면\s*좋|"
                    r"preferred|nice[- ]to[- ]have|bonus|we\s+prefer|(it'?s\s+a\s+)?plus(es)?:?$|good\s+to\s+have|"
                    r"extra\s+credit|stand\s+out"),
    # 기술 스택은 머리말 전체가 그 말일 때만 — "[실무 경험 및 기술 스택]" 같은 우대사항 안의 소제목이
    # 우대사항을 통째로 기술 스택 칸으로 끌고 가지 않게.
    ("tech_stack_raw", r"^((기술|개발)\s*(스택|환경)|사용\s*(하는\s*)?기술|.{0,12}에서\s*사용하는\s*기술|이런\s*기술이\s*필요해요|"
                       r"tech(nology)?\s*stack|our\s+stack(\s*&\s*practices)?|tools\s+we\s+use)$"),
    ("benefits", r"복지|혜택|복리\s*후생|좋은\s*점|이런\s*점들?이\s*좋|benefits|perks|what\s+we\s+offer|we\s+offer"),
    ("qualifications", r"자격|필수\s*(요건|사항|기준|역량|조건)|지원\s*(자격|대상)|요구\s*(사항|역량|조건)|"
                       r"필요\s*(역량|기술|경험)|이런\s*분(을|과|들을|들과)?\s*(찾|함께|기다|모십|모셔)|이런\s*역량|"
                       r"이런\s*동료를|찾고\s*있어요|모십니다|이런\s*경험을\s*가진|"
                       r"requirements|qualifications|must[- ]haves?|^you\s+have|^about\s+you|who\s+you\s+are|"
                       r"what\s+(you|we)('|’)?\s*(ll\s+)?(bring|need|look\s+for|re\s+looking\s+for|are\s+looking\s+for)|"
                       r"you('|’)?ll\s+(bring|need)|your\s+(background|experience|skills|profile)|"
                       r"to\s+be\s+successful|kind\s+of\s+(person|builder)"),
    ("main_tasks", r"주요\s*업무|담당\s*업무|업무\s*내용|수행\s*업무|직무\s*(내용|소개)|역할과\s*책임|"
                   r"이런\s*(업무|일)|합류하면.*(업무|일)|함께\s*할\s*업무|하게\s*될\s*(업무|일)|담당하게|담당합니다|"
                   r"업무를\s*해요|하는\s*일|"
                   r"what\s+you('|’)?ll\s+(do|own|be\s+doing|work\s+on)|what\s+you\s+will\s+(do|be\s+doing|own)|"
                   r"^you\s+will|in\s+this\s+role|responsibilit|day[- ]to[- ]day|your\s+(role|impact|mission)|"
                   r"the\s+role\s+involves|key\s+duties|tasks\s+and\s+deliverables"),
]]
# 줄글 공고의 문단 첫마디 → 칸
_PROSE_LEADS: list[tuple[str, re.Pattern]] = [(k, re.compile(rx)) for k, rx in [
    ("preferences", r"^(우대\s*(사항|조건|요건)|.{0,40}(우대한다|우대된다|우대하며|우대 대상))"),
    ("qualifications", r"^(자격\s*요건|지원\s*자격|필수\s*(요건|조건|자격)|.{0,20}(요구된다|요구하며|필요하다|갖춘\s*인재|지원할\s*수\s*있다))"),
    ("main_tasks", r"^(주요\s*업무|담당\s*업무|맡게\s*될\s*업무|.{0,30}(업무는|역할은|일을\s*맡|담당하게|맡는다|수행한다))"),
]]
# "About the Role" 류는 역할 소개 문단이라 업무와 겹친다 — 주요업무가 따로 없을 때만 그 자리에 쓴다.
_ABOUT_ROLE = re.compile(r"^(about\s+(the|this)\s+(role|position|job|opportunity)|the\s+role|the\s+opportunity|"
                         r"role\s+overview|position\s+overview|포지션\s*소개|직무\s*개요)$", re.I)


def _clean_header(line: str) -> str:
    s = line.strip()
    s = re.sub(r"^#{1,6}\s*", "", s)                      # 마크다운 머리말(토스 "# 이런 분과…")
    s = s.strip("[]【】■◆●▶▷✔✓☑-·•:：*_ ").strip()
    s = re.sub(r"^\W+", "", s, flags=re.UNICODE)
    s = re.sub(r"\W+$", "", s, flags=re.UNICODE)
    return s


def _looks_like_header(raw: str, s: str) -> bool:
    """본문 문장이 아니라 머리말 모양인가 — 짧고, 글머리표로 시작하지 않고, 문장으로 끝나지 않는다."""
    t = raw.strip()
    if not s or len(s) > 60 or len(s.split()) > 9:
        return False
    # 글머리표로 시작하는 줄은 본문이다(한국 공고의 'ㆍ'·'○'·'1.' 포함)
    if re.match(r"^([-•·ㆍ○◦▪▸→*]|\d+[.)]|[①-⑳])\s*", t) and not t.startswith("**"):
        return False
    # "자격증 : 정보처리기사" 처럼 항목 : 값 꼴은 본문이다(머리말은 콜론 뒤가 비어 있다)
    if re.search(r"[:：]\s*\S", t):
        return False
    if re.search(r"[.。]$|(니다|어요|해요|세요|습니다)\.$", t):
        return False
    # 느낌표·물음표는 짧으면 머리말이다 — 당근 "이런 분이면 더 좋아요!"(2026-10-19 우대사항이 자격요건에 붙었다)
    if re.search(r"[!?]$", t) and len(s) > 25:
        return False
    return True


def _header_match(line: str) -> str | None:
    """라인이 섹션 헤더인 경우 정규화된 key 반환, 아니면 None. (끊는 머리말은 _is_stop_header 가 본다)"""
    s = line.strip().strip("[]【】■◆●▶▷-·•:：").strip()
    # leading/trailing 이모지·기호 제거 (예: "📋 주요업무" → "주요업무", "🔥자격요건:" → "자격요건")
    s = re.sub(r"^\W+", "", s, flags=re.UNICODE)
    s = re.sub(r"\W+$", "", s, flags=re.UNICODE)
    if not s or len(s) > 60:
        return None
    s_low = s.lower()
    for header, key in _HEADER_TO_KEY:
        h_low = header.lower()
        if s_low == h_low or s_low.startswith(h_low + " ") or s_low.rstrip(":：") == h_low:
            return key
    c = _clean_header(line)
    if _looks_like_header(line, c):
        for key, rx in _HEADER_PATTERNS:
            if rx.search(c):
                return key            # None(끊는 머리말)이면 여기서 None — _is_stop_header 가 따로 잡는다
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
    c = _clean_header(line)
    if _looks_like_header(line, c) and _HEADER_PATTERNS[0][1].search(c):
        return True
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
    # 인라인 대괄호 마커(예: "...경력 3년 [우대사항] 도메인 이해...")를 줄머리로 끌어내려
    # 한 줄에 눌린 표/문단형 JD(잡코리아 등)에서도 헤더가 인식되게 한다.
    text = re.sub(r"\s*([\[【][^\]\n】]{1,30}[\]】])", r"\n\1", text)
    lines = text.splitlines()
    current: str | None = None
    buf: dict[str, list[str]] = {k: [] for k in SECTION_HEADERS}
    about_role: list[str] = []
    # 괄호 종류마다 짝을 맞춘다 — "[이런 업무를 해요 (주요 업무)]" 안의 ')' 에서 끊기면 ']' 가 본문으로 샌다
    inline_re = re.compile(r"^\s*(?:\[([^\]]{1,60})\]|【([^】]{1,60})】|\(([^)]{1,60})\))\s*(.*)$")
    for raw in lines:
        if _ABOUT_ROLE.match(_clean_header(raw)):
            current = "_about_role"
            continue
        # "[헤더] 본문" 또는 "(헤더) 본문" 처럼 한 줄에 헤더+본문이 있는 경우 분리 (사람인/캐치)
        m = inline_re.match(raw)
        if m:
            cand = (m.group(1) or m.group(2) or m.group(3)).strip()
            rest = m.group(4).strip()
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
        if current == "_about_role":
            about_role.append(raw)
        elif current:
            buf[current].append(raw)
    if not any(x.strip() for x in buf["main_tasks"]) and about_role:
        buf["main_tasks"] = about_role
    # 머리말이 하나도 없는 줄글 공고(인크루트 등 기사체: "주요 업무는 …이다. 자격 요건은 …") —
    # 문단 첫마디로 가른다. 머리말로 나눈 결과가 하나라도 있으면 쓰지 않는다.
    if not any(any(x.strip() for x in buf[k]) for k in ("main_tasks", "qualifications", "preferences")):
        for para in lines:
            p = para.strip()
            for key, rx in _PROSE_LEADS:
                if rx.match(p):
                    buf[key].append(p)
                    break
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
