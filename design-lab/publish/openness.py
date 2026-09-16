"""이 공고, 지금도 모집중인가 — 올리기 직전에 원본 사이트에 다시 묻는다.

끝난 모집을 홍보하면 안 된다. 그런데 우리가 가진 근거는 셋 다 약하다.

  1. 색인의 `status` — 크롤이 목록에서 본 것이다. 마감 텍스트가 없는 공고(wanted 는 마감일
     필드가 아예 없다)는 영구 '모집중' 으로 남는다. 실제로 모집중 9,245건 중 3,050건(33%)이
     마감일이 이미 지난 공고였다.
  2. 마감 표기 — 연도가 없거나('~ 06.16(화) 18시') 아예 비어 있다.
  3. 색인을 만든 원본 파일 — 이 윈도우의 사본은 며칠 전 것일 수 있다(맥이 크롤한다).

그래서 올리기 직전에 원본에 다시 묻는다. 묻는 방법은 크롤 파이프라인이 이미 갖고 있으므로
(`catch_capture/pipeline/close_check.py` 의 사이트별 판정) 그것을 그대로 빌려 쓴다 —
같은 질문에 두 가지 답이 나오면 안 된다.

    from publish.openness import check
    state = check(job)        # ("open"|"closed"|"unknown", 이유)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
CATCH_DIR = LAB_DIR.parent / "catch_capture"
#: 원본 데이터(색인의 재료)가 이보다 오래되면 '모집중' 을 믿을 수 없다고 본다
STALE_SOURCE_DAYS = 3


CACHE = LAB_DIR / "state" / "openness.json"
#: 같은 공고를 몇 시간 안에 다시 묻지 않는다(차단 방지 + 속도). 마감은 한 번 닫히면 안 열린다.
TTL_HOURS = {"open": 8, "unknown": 2, "closed": 24 * 365}


def _cache_load() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _cache_get(key: str) -> tuple[str, str] | None:
    row = _cache_load().get(key)
    if not row:
        return None
    at = datetime.fromisoformat(row["at"])
    if (datetime.now() - at).total_seconds() / 3600 > TTL_HOURS.get(row["status"], 2):
        return None
    return row["status"], row["reason"]


def _cache_put(key: str, status: str, reason: str) -> None:
    data = _cache_load()
    data[key] = {"status": status, "reason": reason, "at": datetime.now().isoformat(timespec="seconds")}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, CACHE)


def _checkers():
    """close_check 의 사이트별 판정. 크롤 쪽 의존이 없으면 None."""
    if str(CATCH_DIR) not in sys.path:
        sys.path.insert(0, str(CATCH_DIR))
    try:
        from pipeline.close_check import CHECKERS
    except Exception:                       # noqa: BLE001 — 크롤 쪽이 없는 머신도 있다
        return None
    return CHECKERS


def source_age_days() -> float | None:
    """색인의 재료(all_jobs_enriched.json)가 며칠 전 것인가."""
    from poster.jobsource import SOURCE
    if not SOURCE.is_file():
        return None
    return (datetime.now() - datetime.fromtimestamp(SOURCE.stat().st_mtime)).total_seconds() / 86400


def local_verdict(job: dict, today: date | None = None) -> tuple[str, str]:
    """네트워크 없이 아는 것만으로 — 마감일이 지났으면 닫힌 것이다."""
    from poster.collection import _deadline, period_label
    today = today or date.today()
    if job.get("status") and job["status"] != "active":
        return "closed", f"색인 상태 {job['status']}"
    d = _deadline(job, today)
    if d and d < today:
        return "closed", f"마감 {d.isoformat()} 지남 ({period_label(job)})"
    return "unknown", "마감 표기로는 판정 못 함"


def check(job: dict, today: date | None = None, *, network: bool = True) -> tuple[str, str]:
    """("open"|"closed"|"unknown", 이유).

    먼저 아는 것으로 닫힌 게 확인되면 거기서 끝낸다(네트워크를 쓸 이유가 없다). 아니면 원본
    사이트에 묻는다 — 답을 못 얻으면 'unknown' 이고, 그때는 부르는 쪽이 정한다(승인은 막고,
    사람이 --force 로만 넘긴다).
    """
    today = today or date.today()
    state, why = local_verdict(job, today)
    if state == "closed":
        return state, why
    if not network:
        return state, why
    if hit := _cache_get(job.get("key", "")):
        return hit
    checkers = _checkers()
    site = job.get("site") or ""
    if not checkers or site not in checkers:
        return "unknown", f"이 사이트({site})는 재확인 방법이 없음"
    try:
        status, reason, iso = checkers[site](job, today, {})
    except Exception as e:                  # noqa: BLE001 — 차단·타임아웃도 '모름' 이다
        return "unknown", f"재확인 실패: {type(e).__name__}: {e}"
    if status == "active":
        got = ("open", f"원본 확인: {reason}" + (f" (마감 {iso})" if iso else ""))
    elif status == "closed":
        got = ("closed", f"원본 확인: {reason}")
    else:
        got = ("unknown", f"원본이 답을 안 줌: {reason}")
    if job.get("key"):
        _cache_put(job["key"], *got)
    return got


def describe(job: dict) -> str:
    """사람이 읽는 한 줄 — 승인 화면에 그대로 찍는다."""
    from poster.collection import period_label
    state, why = check(job)
    mark = {"open": "모집중", "closed": "마감됨", "unknown": "확인 불가"}[state]
    age = source_age_days()
    stale = f" · 색인 재료 {age:.0f}일 전" if age and age > STALE_SOURCE_DAYS else ""
    return f"{mark} — {period_label(job)} · {why}{stale}"
