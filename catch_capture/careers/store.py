"""커리어 데이터의 자리와 읽고 쓰기 — 전부 `var/careers/` 아래(코드 폴더 밖 런타임 데이터)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.paths import ROOT_DIR, VAR_DIR

DIR = VAR_DIR / "careers"
RAW = DIR / "raw"            # 글 하나 = 파일 하나 ({id}.json: source·url·title·date·body)
INBOX = DIR / "inbox"        # 사람이 넣는 글(.txt/.md). 첫 줄에 원문 URL 을 적어 두면 출처로 쓴다
PATHS = DIR / "paths.jsonl"  # 추출 결과 — 글 하나 = 줄 하나
REPORT_JSON = DIR / "report.json"
REPORT_HTML = DIR / "report.html"
SEEN = DIR / "seen.json"     # 검색에서 본 글(본문을 받았든 걸렀든) — 다시 받지 않는다
JOBS = ROOT_DIR / "jd-viewer" / "public" / "all_jobs_enriched.json"


def ensure() -> None:
    for d in (RAW, INBOX):
        d.mkdir(parents=True, exist_ok=True)


def rid(source: str, key: str) -> str:
    return f"{source}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:12]}"


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def raw_items() -> list[dict]:
    return [load_json(f, {}) for f in sorted(RAW.glob("*.json"))]


def read_paths() -> list[dict]:
    if not PATHS.exists():
        return []
    return [json.loads(l) for l in PATHS.read_text(encoding="utf-8").splitlines() if l.strip()]


def companies() -> list[str]:
    """지금 공고가 있는 회사 이름(표시명). 검색어와 회사 연결에 쓴다."""
    jobs = load_json(JOBS, [])
    return sorted({j["company"].strip() for j in jobs if j.get("company")})
