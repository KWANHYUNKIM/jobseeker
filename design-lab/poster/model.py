"""공고 → 포스터 원고. 렌더링 직전의 '무엇을 어디에 쓸지'를 여기서 다 정한다.

원칙은 refs.json 의 synthesis 그대로다.
  - 주인공은 직군명. 회사명은 조연으로 내린다.
  - 항목 이름을 바꾸지 않는다. 지원자격 / 우대사항 / 담당업무.
  - 없는 정보는 지어내지 않는다. 마감일이 없으면 '상시 채용'이라고 쓰지 않고 비운다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import datetime

# detail-01 이 슬라이드에 코드까지 박아 둔 습관 — 팔레트는 4칸으로 못 박고 시작한다.
PALETTES: dict[str, dict[str, str]] = {
    "navy":   {"bg": "#000714", "ink": "#f2f7ff", "accent": "#3aa8c1", "soft": "#0a2233"},
    "ink":    {"bg": "#101014", "ink": "#f7f7f5", "accent": "#c8ff4d", "soft": "#1d1d24"},
    "paper":  {"bg": "#f4f2ed", "ink": "#14140f", "accent": "#1a4fd6", "soft": "#e2ded4"},
    "forest": {"bg": "#0c1a14", "ink": "#eef7f1", "accent": "#5fd08a", "soft": "#12301f"},
    "clay":   {"bg": "#1a1411", "ink": "#f6efe8", "accent": "#ff8a4c", "soft": "#2c211a"},
}

# 직군 계열 → 팔레트. 색을 공고마다 굴리면 계정 피드가 흩어진다. 계열로 묶어 고정한다.
ROLE_FAMILY = [
    ("frontend", ("프론트", "front", "react", "웹퍼블", "ui 개발"), "clay"),
    ("data",     ("데이터", "data", "머신러닝", "ml", "ai", "분석"), "forest"),
    ("infra",    ("devops", "데브옵스", "sre", "인프라", "클라우드", "플랫폼"), "ink"),
    ("mobile",   ("android", "안드로이드", "ios", "flutter", "모바일"), "paper"),
    ("backend",  ("백엔드", "backend", "서버", "java", "python", "node"), "navy"),
]

FORMATS: dict[str, dict] = {
    "ig_portrait":  {"w": 1080, "h": 1350, "label": "인스타 세로 4:5"},
    "ig_square":    {"w": 1080, "h": 1080, "label": "인스타 정사각"},
    "ig_story":     {"w": 1080, "h": 1920, "label": "스토리/릴스 커버"},
    "li_landscape": {"w": 1200, "h": 627,  "label": "링크드인 가로"},
    "fb_landscape": {"w": 1200, "h": 630,  "label": "페이스북 가로"},
}

# 직군명 앞뒤로 붙는 군더더기. 히어로에 넣으면 글자만 작아진다.
_TITLE_NOISE = re.compile(
    r"(\[[^\]]*\]|\([^)]*\)|【[^】]*】|경력\s*무관|신입\s*/?\s*경력|정규직|채용|공고|모집|수시)",
)


def clean_role(title: str) -> str:
    """공고 제목에서 '자리 이름'만 꺼낸다."""
    t = _TITLE_NOISE.sub(" ", title or "")
    t = re.sub(r"\s*[/·,|]\s*", " / ", t)
    t = re.sub(r"\s+", " ", t).strip(" /-·")
    return t or (title or "").strip()


def pick_palette(job: dict) -> tuple[str, str]:
    """(계열, 팔레트 이름). 제목 → 기술스택 순으로 본다."""
    hay = f"{job.get('title','')} {' '.join(job.get('stack') or [])}".lower()
    for family, needles, palette in ROLE_FAMILY:
        if any(n in hay for n in needles):
            return family, palette
    return "general", "navy"


def _deadline_line(job: dict) -> str:
    """마감 표기. 없으면 빈 문자열 — 여기서 '상시'라고 지어내지 않는다."""
    raw = (job.get("deadline") or "").strip()
    if not raw:
        return ""
    m = re.search(r"(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})", raw)
    if m:
        y, mo, d = m.groups()
        return f"~ {y}.{int(mo):02d}.{int(d):02d}"
    return raw[:24]


@dataclass
class PosterSpec:
    """템플릿에 그대로 부어 넣는 원고. 템플릿은 이 사전 밖의 값을 모른다."""

    key: str
    role: str
    company: str
    url: str
    site: str
    family: str
    palette_name: str
    palette: dict[str, str]
    deadline: str = ""
    meta: list[str] = field(default_factory=list)
    stack: list[str] = field(default_factory=list)
    qualifications: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    mark: str = ""            # 회사 로고 URL(또는 data:). 없으면 이니셜로 대체한다.
    initial: str = ""
    generated_at: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def build_spec(job: dict, *, mark: str = "", palette: str = "") -> PosterSpec:
    family, palette_name = pick_palette(job)
    if palette:
        palette_name = palette if palette in PALETTES else palette_name
    meta = [m for m in (job.get("career"), job.get("location")) if m]
    company = job.get("company", "")
    return PosterSpec(
        key=job["key"],
        role=clean_role(job.get("title", "")),
        company=company,
        url=job.get("url", ""),
        site=job.get("site", ""),
        family=family,
        palette_name=palette_name,
        palette=PALETTES[palette_name],
        deadline=_deadline_line(job),
        meta=meta[:3],
        stack=(job.get("stack") or [])[:5],
        qualifications=(job.get("qualifications") or [])[:3],
        preferences=(job.get("preferences") or [])[:2],
        tasks=(job.get("tasks") or [])[:3],
        mark=mark,
        initial=(company[:1] or "?"),
        generated_at=datetime.now().strftime("%Y-%m-%d"),
    )
