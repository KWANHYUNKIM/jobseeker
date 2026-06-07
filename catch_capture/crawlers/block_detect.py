"""크롤러 차단/레이트리밋/캡차 감지 공용 모듈.

크롤러는 서브프로세스로 실행되므로, 차단을 감지하면 catch_capture 루트의
`.blocks/<site>.json` 마커를 남긴다. 부모(crawl_all)가 사이트 종료 시 이 마커를 읽어
`site_done` 이벤트에 reason 을 붙이고, 즉시 이벤트 로그에도 `site_block` 을 emit 한다.

감지 한계:
  - Playwright goto 는 응답객체를 안 받으므로 순수 HTTP 429/403(빈 본문)은 못 본다.
    대신 진입 직후 페이지 제목/본문/URL 로 캡차·차단 인터스티셜을 감지한다(scan_page).
  - urllib 경로(saramin 검색, dev 상세)는 HTTPError.code 로 429/403/503 을 직접 감지한다.
모든 함수는 본 크롤을 방해하지 않도록 예외를 삼킨다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

CATCH_DIR = Path(__file__).resolve().parent.parent
BLOCK_DIR = CATCH_DIR / ".blocks"

# 차단 감지 시 자동 백오프(쿨다운) 설정 — 연속 차단마다 지수적으로 늘어난다.
COOLDOWN_BASE_SEC = 600          # 첫 차단: ~10분
COOLDOWN_MAX_SEC = 6 * 3600      # 상한: 6시간

# reason 식별자 (프런트 라벨과 1:1)
R_429 = "rate_limited_429"
R_403 = "forbidden_403"
R_503 = "unavailable_503"
R_HTTP = "http_error"
R_CAPTCHA = "captcha_or_block_page"

# 차단/캡차 인터스티셜에서만 나오는 강한 신호 (검색결과 본문 오탐 방지로 다어절 위주)
_BLOCK_HINTS = [
    "로봇이 아닙", "자동입력 방지", "보안문자", "캡차", "captcha", "recaptcha",
    "비정상적인 접근", "비정상적인 트래픽", "비정상적 트래픽",
    "too many requests", "unusual traffic", "access denied",
    "request blocked", "접근이 차단", "이용이 제한", "차단되었습니다",
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def reason_for_http_status(code: int | None) -> str | None:
    if code == 429:
        return R_429
    if code == 403:
        return R_403
    if code == 503:
        return R_503
    if code and code >= 400:
        return R_HTTP
    return None


def from_http_error(exc: Exception) -> tuple[str | None, int | None]:
    """urllib.error.HTTPError 등에서 (reason, status code) 추출. 아니면 (None, None)."""
    code = getattr(exc, "code", None)
    try:
        code = int(code) if code is not None else None
    except (TypeError, ValueError):
        code = None
    return (reason_for_http_status(code), code)


def looks_blocked_text(text: str | None) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(h.lower() in low for h in _BLOCK_HINTS)


def report(site: str, reason: str, http_status: int | None = None, detail: str = "") -> None:
    """차단 마커 기록 + 이벤트 로그 emit + stdout 출력."""
    detail = (detail or "")[:300]
    try:
        BLOCK_DIR.mkdir(exist_ok=True)
        rec = {"site": site, "reason": reason, "http_status": http_status,
               "detail": detail, "ts": _now()}
        tmp = BLOCK_DIR / f"{site}.json.tmp"
        tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, BLOCK_DIR / f"{site}.json")
    except Exception:
        pass
    try:
        from monitoring import orchestration as orch
        orch.emit("site_block", site=site, reason=reason,
                  http_status=http_status, detail=detail[:200])
    except Exception:
        pass
    suffix = f" (HTTP {http_status})" if http_status else ""
    print(f"  [⛔ block] {site}: {reason}{suffix}", flush=True)


def read(site: str) -> dict | None:
    try:
        return json.loads((BLOCK_DIR / f"{site}.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def clear(site: str) -> None:
    try:
        (BLOCK_DIR / f"{site}.json").unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


# ── 자동 백오프(쿨다운) ────────────────────────────────────────────────
# 차단 마커(`<site>.json`)는 사이클마다 지워지지만, 쿨다운 상태는
# `<site>.cooldown.json` 에 따로 보관해 사이클을 넘겨 유지된다.
# crawl_all 이 크롤러 실행 전 쿨다운 중인 사이트를 건너뛰고,
# 차단 없이 성공하면 쿨다운을 해제한다.

def _cooldown_path(site: str) -> Path:
    return BLOCK_DIR / f"{site}.cooldown.json"


def cooldown_info(site: str) -> dict | None:
    try:
        return json.loads(_cooldown_path(site).read_text(encoding="utf-8"))
    except Exception:
        return None


def cooldown_remaining(site: str) -> int:
    """쿨다운 잔여 초. 쿨다운이 없거나 만료됐으면 0."""
    info = cooldown_info(site)
    if not info:
        return 0
    try:
        until = datetime.fromisoformat(info["until"])
    except Exception:
        return 0
    rem = (until - datetime.now()).total_seconds()
    return int(rem) if rem > 0 else 0


def note_block(site: str, reason: str | None = None, http_status: int | None = None) -> dict:
    """차단 1건을 반영해 쿨다운을 지수적으로 늘린다(사이클당 1회 호출 의도).

    level N → 대기 = min(BASE * 2^(N-1), MAX). 연속 차단일수록 더 오래 쉰다.
    """
    prev = cooldown_info(site) or {}
    level = int(prev.get("level", 0)) + 1
    secs = min(COOLDOWN_BASE_SEC * (2 ** (level - 1)), COOLDOWN_MAX_SEC)
    until = datetime.now() + timedelta(seconds=secs)
    rec = {
        "site": site, "level": level, "cooldown_sec": secs,
        "until": until.isoformat(timespec="seconds"),
        "reason": reason, "http_status": http_status, "ts": _now(),
    }
    try:
        BLOCK_DIR.mkdir(exist_ok=True)
        tmp = _cooldown_path(site).with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _cooldown_path(site))
    except Exception:
        pass
    print(f"  [⏳ backoff] {site}: level {level} → {secs}s 쿨다운 (until {rec['until']})", flush=True)
    return rec


def clear_cooldown(site: str) -> None:
    try:
        _cooldown_path(site).unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def note_success(site: str) -> None:
    """차단 없이 깨끗하게 끝난 사이클 → 쿨다운 해제(회복)."""
    clear_cooldown(site)


async def scan_page(page, site: str) -> bool:
    """Playwright 페이지 진입 직후 호출 — 캡차/차단 인터스티셜 감지.
    차단으로 판단되면 report() 후 True. 본 크롤 흐름을 막지 않도록 예외는 전부 삼킨다."""
    try:
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        url = ""
        try:
            url = page.url or ""
        except Exception:
            pass
        snippet = ""
        try:
            snippet = (await page.content())[:6000]
        except Exception:
            pass

        blocked = looks_blocked_text(title) or looks_blocked_text(snippet)
        if not blocked and url:
            lu = url.lower()
            if any(k in lu for k in ("/captcha", "/blocked", "access-denied", "/login?")):
                blocked = True
        if blocked:
            report(site, R_CAPTCHA, detail=f"title={title!r} url={url}")
            return True
    except Exception:
        pass
    return False
