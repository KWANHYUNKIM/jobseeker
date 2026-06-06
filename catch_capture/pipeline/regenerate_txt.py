"""기존 캡처 폴더의 txt를 재생성.

- 직무 카테고리에 개발자 관련 항목이 하나라도 있는 공고만 남기고, 나머지는 txt 삭제.
- 캐치 상세 페이지 iframe(`/controls/recruitDetail/{id}`)에서 JD 본문을 가져와
  [기술스택], [채용 상세] 섹션을 추가한다.

사용법:
    python regenerate_txt.py screenshots/개발자_20260518_201508
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

CATCH_IFRAME_URL = "https://www.catch.co.kr/controls/recruitDetail/{job_id}"
JOB_ID_RE = re.compile(r"/RecruitInfoDetails/(\d+)")

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
]

TECH_KEYWORDS = [
    "Java", "Kotlin", "Python", "JavaScript", "TypeScript", "C++", "C#", "C/C++",
    "Go", "Golang", "Rust", "Ruby", "PHP", "Swift", "Scala", "MATLAB", "Dart", "Perl",
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

    def handle_starttag(self, tag: str, attrs):
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
        elif tag in self.BREAK_TAGS:
            self.buf.append("\n")

    def handle_endtag(self, tag: str):
        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
        elif tag in self.BREAK_TAGS:
            self.buf.append("\n")

    def handle_data(self, data: str):
        if self.skip_depth == 0:
            self.buf.append(data)

    def text(self) -> str:
        out = "".join(self.buf)
        out = out.replace("\xa0", " ")
        out = re.sub(r"[ \t]+", " ", out)
        out = re.sub(r" *\n *", "\n", out)
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out.strip()


def fetch_description(job_id: str) -> tuple[str, bool]:
    """iframe 본문 텍스트와, 이미지 전용 공고인지 여부를 반환."""
    url = CATCH_IFRAME_URL.format(job_id=job_id)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    parser = HTMLToText()
    parser.feed(raw)
    text = parser.text()
    has_img = "<img " in raw
    # 본문에 의미 있는 텍스트가 거의 없고 이미지가 들어있으면 이미지 전용으로 간주
    image_only = has_img and len(re.sub(r"\s+", "", text)) < 30
    return text, image_only


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


def regenerate_folder(folder: Path) -> None:
    jobs_path = folder / "jobs.json"
    if not jobs_path.exists():
        raise SystemExit(f"jobs.json not found in {folder}")
    jobs = json.loads(jobs_path.read_text(encoding="utf-8"))

    kept: list[tuple[int, str]] = []
    removed: list[tuple[int, str]] = []
    for job in jobs:
        txt_path = folder / job["txt"]
        if not is_developer_job(job.get("roles", [])):
            if txt_path.exists():
                txt_path.unlink()
            removed.append((job["idx"], job["title"]))
            continue

        m = JOB_ID_RE.search(job["url"])
        if not m:
            print(f"[!] job id를 찾을 수 없음: {job['url']}", flush=True)
            continue
        job_id = m.group(1)

        image_only = False
        try:
            desc, image_only = fetch_description(job_id)
        except Exception as e:
            print(f"[!] {job['idx']:02d} JD fetch 실패: {e}", flush=True)
            desc = ""

        tech = extract_tech_stack(desc)
        if image_only:
            ref = f"{job['png']} 캡처를 " if job.get("png") else "캐치 사이트에서 "
            jd_body = f"(상세 내용이 이미지로만 제공됩니다. {ref}확인하세요.)"
        elif desc:
            jd_body = desc
        else:
            jd_body = "(상세 내용을 가져오지 못함)"

        lines = [
            f"회사: {job['company']}",
            f"제목: {job['title']}",
            f"URL: {job['url']}",
            "",
            "[조건]",
            f"경력: {job.get('career', '')}",
            f"고용형태: {job.get('employment', '')}",
            f"학력: {job.get('education', '')}",
            f"위치: {job.get('location', '')}",
            "",
            "[직무 카테고리]",
            ", ".join(job["roles"]) if job.get("roles") else "(없음)",
            "",
            "[기술스택]",
            ", ".join(tech) if tech else "(JD에서 식별된 기술스택 없음)",
            "",
            "[마감]",
            f"{job.get('deadline', '')}"
            + (f"  ({job['dday']})" if job.get("dday") else ""),
            "",
            "[채용 상세]",
            jd_body,
        ]
        txt_path.write_text("\n".join(lines), encoding="utf-8")
        kept.append((job["idx"], job["title"]))

    print(f"\n[완료] 재생성 {len(kept)}개 / 제외(txt 삭제) {len(removed)}개", flush=True)
    for idx, title in kept:
        print(f"  [keep]   {idx:02d}  {title}", flush=True)
    for idx, title in removed:
        print(f"  [remove] {idx:02d}  {title}", flush=True)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python regenerate_txt.py <screenshots_folder>")
    folder = Path(sys.argv[1])
    if not folder.exists():
        raise SystemExit(f"folder not found: {folder}")
    regenerate_folder(folder)


if __name__ == "__main__":
    main()
