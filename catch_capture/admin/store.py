"""비공개 데이터 저장 — 사실 프로필 / 지원 현황 / 생성 이력서.

모든 파일은 admin/data/ 아래(.gitignore)에 둔다. 공개되면 안 되는 개인정보다.
원자적 쓰기(temp→replace)로 크롤 데몬/동시 요청과의 경합에서 파일 손상을 막는다.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

ADMIN_DIR = Path(__file__).resolve().parent          # catch_capture/admin/
DATA_DIR = ADMIN_DIR / "data"                          # 비공개 데이터 (gitignore)
RESUME_DIR = DATA_DIR / "resumes"                      # 생성 이력서 보관
SECRETS_FILE = ADMIN_DIR / ".secrets.json"             # API 키 등 (gitignore)

PROFILE_FILE = DATA_DIR / "profile.json"
APPLICATIONS_FILE = DATA_DIR / "applications.json"
CAPTURES_FILE = DATA_DIR / "captures.json"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"

_lock = threading.Lock()

# ── 기본 스키마 ─────────────────────────────────────────────
DEFAULT_PROFILE: dict[str, Any] = {
    "name": "",
    "headline": "",            # 한 줄 소개
    "contact": {"email": "", "phone": "", "location": ""},
    "links": [],                # [{"label": "GitHub", "url": "..."}]
    "summary": "",             # 자기소개 사실 요약
    "experiences": [],          # [{"company","role","start","end","bullets":[...]}]
    "projects": [],             # [{"name","role","period","stack":[...],"bullets":[...],"url"}]
    "skills": [],               # ["Python", "React", ...]
    "education": [],            # [{"school","degree","major","start","end"}]
    "certifications": [],       # [{"name","issuer","date"}]
    "updated_at": "",
}


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESUME_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data: Any) -> None:
    _ensure_dirs()
    # 같은 디렉토리에 임시파일 생성 후 원자적 교체
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ── 프로필 ──────────────────────────────────────────────────
def get_profile() -> dict[str, Any]:
    data = _read_json(PROFILE_FILE, None)
    if not isinstance(data, dict):
        return dict(DEFAULT_PROFILE)
    # 누락 키 보강(앞으로 스키마 늘려도 안전)
    merged = dict(DEFAULT_PROFILE)
    merged.update(data)
    return merged


def save_profile(profile: dict[str, Any], now: str) -> dict[str, Any]:
    with _lock:
        merged = dict(DEFAULT_PROFILE)
        merged.update(profile or {})
        merged["updated_at"] = now
        _write_json(PROFILE_FILE, merged)
        return merged


# ── 지원 현황 ────────────────────────────────────────────────
# application = {
#   "id", "job": {"site","idx","company","title","url"},
#   "status": "관심|작성중|지원완료|서류합격|면접|최종합격|불합격",
#   "applied_at","note","resume_id","created_at","updated_at"
# }
STATUSES = ["관심", "작성중", "지원완료", "서류합격", "면접", "최종합격", "불합격"]


def list_applications() -> list[dict[str, Any]]:
    data = _read_json(APPLICATIONS_FILE, [])
    return data if isinstance(data, list) else []


def _save_applications(apps: list[dict[str, Any]]) -> None:
    _write_json(APPLICATIONS_FILE, apps)


def add_application(app: dict[str, Any], now: str) -> dict[str, Any]:
    with _lock:
        apps = list_applications()
        # id = 단조 증가 정수 문자열
        next_id = str(max([int(a.get("id", 0)) for a in apps] + [0]) + 1)
        record = {
            "id": next_id,
            "job": app.get("job", {}),
            "status": app.get("status", "관심"),
            "applied_at": app.get("applied_at", ""),
            "note": app.get("note", ""),
            "resume_id": app.get("resume_id", ""),
            "created_at": now,
            "updated_at": now,
        }
        apps.append(record)
        _save_applications(apps)
        return record


def update_application(app_id: str, patch: dict[str, Any], now: str) -> dict[str, Any] | None:
    with _lock:
        apps = list_applications()
        for a in apps:
            if str(a.get("id")) == str(app_id):
                for k in ("status", "applied_at", "note", "resume_id", "job"):
                    if k in patch:
                        a[k] = patch[k]
                a["updated_at"] = now
                _save_applications(apps)
                return a
        return None


def delete_application(app_id: str) -> bool:
    with _lock:
        apps = list_applications()
        new = [a for a in apps if str(a.get("id")) != str(app_id)]
        if len(new) == len(apps):
            return False
        _save_applications(new)
        return True


# ── 생성 이력서 보관 ─────────────────────────────────────────
def save_resume(content: dict[str, Any], now: str) -> str:
    """생성된 이력서를 파일로 저장하고 resume_id 반환."""
    with _lock:
        _ensure_dirs()
        existing = [int(p.stem) for p in RESUME_DIR.glob("*.json") if p.stem.isdigit()]
        rid = str(max(existing + [0]) + 1)
        payload = dict(content)
        payload["id"] = rid
        payload["created_at"] = now
        _write_json(RESUME_DIR / f"{rid}.json", payload)
        return rid


def get_resume(rid: str) -> dict[str, Any] | None:
    return _read_json(RESUME_DIR / f"{rid}.json", None)


def list_resumes() -> list[dict[str, Any]]:
    out = []
    if RESUME_DIR.is_dir():
        for p in sorted(RESUME_DIR.glob("*.json"), key=lambda x: int(x.stem) if x.stem.isdigit() else 0):
            d = _read_json(p, None)
            if d:
                # 목록엔 메타만(본문 제외) — 가벼움
                out.append({k: d.get(k) for k in ("id", "job", "kind", "created_at")})
    return out


# ── 지원 폼 수집 ─────────────────────────────────────────────
# capture = {
#   "id", "url", "host", "title",
#   "fields": [{"q": 질문/라벨, "type": "textarea|text|select|...", "maxlen": int|None}],
#   "created_at"
# }
def list_captures() -> list[dict[str, Any]]:
    data = _read_json(CAPTURES_FILE, [])
    return data if isinstance(data, list) else []


def add_capture(cap: dict[str, Any], now: str) -> dict[str, Any]:
    with _lock:
        caps = list_captures()
        next_id = str(max([int(c.get("id", 0)) for c in caps] + [0]) + 1)
        fields = []
        for f in (cap.get("fields") or []):
            if not isinstance(f, dict):
                continue
            q = str(f.get("q", "")).strip()
            if not q:
                continue
            ml = f.get("maxlen")
            fields.append({
                "q": q[:500],
                "type": str(f.get("type", "textarea"))[:20],
                "maxlen": int(ml) if isinstance(ml, (int, float)) and ml else None,
            })
        record = {
            "id": next_id,
            "url": str(cap.get("url", ""))[:1000],
            "host": str(cap.get("host", ""))[:200],
            "title": str(cap.get("title", ""))[:300],
            "fields": fields,
            "created_at": now,
            "year": (now or "")[:4],   # 년도별 보관/조회용
        }
        caps.append(record)
        _write_json(CAPTURES_FILE, caps)
        return record


def get_capture(cap_id: str) -> dict[str, Any] | None:
    for c in list_captures():
        if str(c.get("id")) == str(cap_id):
            return c
    return None


def delete_capture(cap_id: str) -> bool:
    with _lock:
        caps = list_captures()
        new = [c for c in caps if str(c.get("id")) != str(cap_id)]
        if len(new) == len(caps):
            return False
        _write_json(CAPTURES_FILE, new)
        return True


# ── 재공고 추적 (워치리스트) ─────────────────────────────────
# watch = {
#   "id", "company", "keyword"(직무/기술), "note",
#   "snapshot": {key,title,url,tech_stack,qualifications,preferences} | None,  # 추가 시점 JD 보관
#   "created_at", "year"
# }
def list_watchlist() -> list[dict[str, Any]]:
    data = _read_json(WATCHLIST_FILE, [])
    return data if isinstance(data, list) else []


def add_watch(data: dict[str, Any], snapshot: dict[str, Any] | None, now: str) -> dict[str, Any]:
    with _lock:
        items = list_watchlist()
        next_id = str(max([int(w.get("id", 0)) for w in items] + [0]) + 1)
        record = {
            "id": next_id,
            "company": str(data.get("company", "")).strip()[:200],
            "keyword": str(data.get("keyword", "")).strip()[:200],
            "note": str(data.get("note", ""))[:1000],
            "snapshot": snapshot,
            "created_at": now,
            "year": (now or "")[:4],
        }
        items.append(record)
        _write_json(WATCHLIST_FILE, items)
        return record


def get_watch(watch_id: str) -> dict[str, Any] | None:
    for w in list_watchlist():
        if str(w.get("id")) == str(watch_id):
            return w
    return None


def delete_watch(watch_id: str) -> bool:
    with _lock:
        items = list_watchlist()
        new = [w for w in items if str(w.get("id")) != str(watch_id)]
        if len(new) == len(items):
            return False
        _write_json(WATCHLIST_FILE, new)
        return True


# ── 비밀값 ──────────────────────────────────────────────────
def get_api_key() -> str:
    """ANTHROPIC_API_KEY: 환경변수 우선, 없으면 .secrets.json."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    secrets = _read_json(SECRETS_FILE, {})
    if isinstance(secrets, dict):
        return str(secrets.get("anthropic_api_key", "")).strip()
    return ""


def save_api_key(key: str) -> None:
    with _lock:
        secrets = _read_json(SECRETS_FILE, {})
        if not isinstance(secrets, dict):
            secrets = {}
        secrets["anthropic_api_key"] = key.strip()
        _write_json(SECRETS_FILE, secrets)
        try:
            os.chmod(SECRETS_FILE, 0o600)  # 본인만 읽기
        except OSError:
            pass
