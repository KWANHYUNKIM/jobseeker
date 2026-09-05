"""회사 이미지 보관소 — '진짜 회사 이미지'가 들어올 자리.

로고 한 장을 여러 포스터가 공유하므로 회사 이름으로만 찾는다.
    assets/companies/<슬러그>/logo.png     대표 마크(정사각 권장)
    assets/companies/<슬러그>/bg.jpg       히어로 배경(선택)
    assets/index.json                      슬러그 ↔ 회사명 사전(별칭 포함)

렌더러는 브라우저에 file:// 접근을 안 시키려고 data: URI 로 심는다. 랩 UI 는
/assets/... 경로로 그냥 받아 본다.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
ASSETS = LAB_DIR / "assets" / "companies"
INDEX = LAB_DIR / "assets" / "index.json"
KINDS = ("logo", "bg")
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".svg": "image/svg+xml"}


def slug(company: str) -> str:
    """(주)·㈜ 같은 접두사와 공백을 털어 회사 하나에 폴더 하나가 되게 만든다."""
    s = re.sub(r"\(주\)|㈜|주식회사|\(유\)|Inc\.?|Corp\.?", "", company or "", flags=re.I)
    s = re.sub(r"\s+", "", s).strip("._-")
    return s or "unknown"


def _aliases() -> dict:
    if INDEX.is_file():
        return json.loads(INDEX.read_text(encoding="utf-8"))
    return {}


def dir_for(company: str) -> Path:
    return ASSETS / (_aliases().get(company) or slug(company))


def find(company: str, kind: str = "logo") -> Path | None:
    d = dir_for(company)
    if not d.is_dir():
        return None
    for ext in MIME:
        p = d / f"{kind}{ext}"
        if p.is_file():
            return p
    return None


def data_uri(path: Path | None) -> str:
    if not path or not path.is_file():
        return ""
    mime = MIME.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def mark(company: str, *, inline: bool = True) -> str:
    """포스터에 박을 마크. inline=True 면 data: URI, 아니면 랩 서버 경로."""
    p = find(company, "logo")
    if not p:
        return ""
    if inline:
        return data_uri(p)
    return f"/assets/companies/{p.parent.name}/{p.name}"


def put(company: str, src: Path, kind: str = "logo") -> Path:
    """회사 이미지를 보관소에 넣는다. 같은 종류가 있으면 덮어쓴다."""
    if kind not in KINDS:
        raise ValueError(f"kind 는 {KINDS} 중 하나여야 합니다")
    ext = src.suffix.lower()
    if ext not in MIME:
        raise ValueError(f"지원하지 않는 형식: {ext}")
    d = dir_for(company)
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob(f"{kind}.*"):
        old.unlink()
    dest = d / f"{kind}{ext}"
    shutil.copyfile(src, dest)
    alias = _aliases()
    alias.setdefault(company, d.name)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(alias, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def have() -> list[dict]:
    """지금 보관 중인 회사 목록. UI 의 '이미지 있음' 배지 재료."""
    if not ASSETS.is_dir():
        return []
    rows = []
    for d in sorted(ASSETS.iterdir()):
        if not d.is_dir():
            continue
        files = [f.name for f in d.iterdir() if f.suffix.lower() in MIME]
        if files:
            rows.append({"slug": d.name, "files": files})
    return rows
