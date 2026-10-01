"""뷰어 API(backend, 8771) 클라이언트 — 같은 머신의 서버들(agent-mcp·admin)이 데이터를 읽는 길.

뷰어 화면과 같은 출처(정본 DB 를 읽는 순간의 상태)를 보게 하려고 API 를 먼저 부른다. 파일
(`jd-viewer/public/*`)은 크롤 회차마다 구운 사본이라 마감이 최대 한 회차 늦다. API 가 없거나
실패하면 그 파일로 물러선다 — 둘 다 없으면 마지막으로 받은 값을 쓴다.

큰 응답(공고 전량)이 있어서 TTL 동안은 다시 묻지 않고, TTL 이 지나면 ETag 로 물어 바뀌었을 때만
받는다(304 면 그대로 쓴다).
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from core.paths import VIEWER_PUBLIC

API_URL = os.environ.get("VIEWER_API_URL", "http://127.0.0.1:8771").rstrip("/")
TTL = float(os.environ.get("VIEWER_API_TTL", "300"))
TIMEOUT = float(os.environ.get("VIEWER_API_TIMEOUT", "60"))

_lock = threading.Lock()
# 키 → (받은 시각, etag, 출처 표시, 가공한 값)
_cache: dict[str, tuple[float, str | None, str, Any]] = {}


def _request(path: str, etag: str | None) -> tuple[int, str | None, Any]:
    req = urllib.request.Request(f"{API_URL}{path}", headers={"Accept-Encoding": "gzip"})
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            if "json" not in (r.headers.get("Content-Type") or ""):
                raise ValueError("JSON 이 아닌 응답")
            return r.status, r.headers.get("ETag"), json.loads(raw)
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return 304, etag, None
        raise


def get(path: str, *, file: str | None = None, build: Callable[[Any], Any] | None = None,
        key: str | None = None) -> Any | None:
    """API 의 path 를 받아 (build 로 가공해) 돌려준다. 실패하면 public/file 로 물러선다."""
    key = key or path
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
    if hit and now - hit[0] < TTL:
        return hit[3]

    try:
        status, etag, data = _request(path, hit[1] if hit and hit[2] == "api" else None)
        if status == 304 and hit:
            value = hit[3]
        else:
            value = build(data) if build else data
        with _lock:
            _cache[key] = (now, etag, "api", value)
        return value
    except Exception as e:                                          # noqa: BLE001
        print(f"[api] {path} 실패 — 파일로 물러섬: {e}", file=sys.stderr)

    if file:
        p: Path = VIEWER_PUBLIC / file
        try:
            mtime = p.stat().st_mtime
            if hit and hit[2] == f"file:{mtime}":
                with _lock:
                    _cache[key] = (now, None, hit[2], hit[3])
                return hit[3]
            raw = json.loads(p.read_text(encoding="utf-8"))
            value = build(raw) if build else raw
            with _lock:
                _cache[key] = (now, None, f"file:{mtime}", value)
            return value
        except (OSError, json.JSONDecodeError):
            pass
    return hit[3] if hit else None


def clear() -> None:
    with _lock:
        _cache.clear()
