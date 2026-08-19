"""채용공고 마감일(deadline/dday)을 파싱해 모집중(active)/마감(closed)을 판정.

사이트별 마감 표기가 제각각이라 통합 파서로 흡수한다:
  - jobkorea : "06/07(일) 마감"
  - saramin  : "~ 07/04(토)"
  - dev      : deadline "~ 06.28(일) 23시", dday "~06.28(일)"
  - jumpit   : dday "D-4" / "D-DAY"
  - wanted   : 마감일 필드 없음 → 정보없음(active 유지)

판정 규칙:
  - 상시/수시/채용시/충원시/미정 등 → active (상시채용)
  - 마감일 파싱 성공 & 오늘보다 과거 → closed
  - 그 외(파싱 실패/필드 없음) → active (정보없음)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트를 import 경로에 추가

import re
from datetime import date, timedelta

# 상시채용/마감일 미정 계열 → 항상 모집중으로 간주
ALWAYS_OPEN_RE = re.compile(
    r"상시|수시|채용\s*시|충원\s*시|채용시\s*마감|마감일\s*미정|미정|연중|정시채용"
)
DDAY_RE = re.compile(r"D-\s*(\d+)", re.IGNORECASE)
DDAY_TODAY_RE = re.compile(r"D-?\s*(?:DAY|day|0)\b")
# MM/DD 또는 MM.DD (연도 없음)
MD_RE = re.compile(r"(\d{1,2})\s*[./]\s*(\d{1,2})")


def today_date() -> date:
    return date.today()


def _collect_text(job: dict) -> str:
    parts = []
    for k in ("deadline", "dday"):
        v = job.get(k)
        if v:
            parts.append(str(v))
    return " ".join(parts).strip()


def parse_deadline(job: dict, today: date | None = None) -> tuple[date | None, bool]:
    """(마감일, 상시채용여부) 반환. 마감일을 못 구하면 (None, 상시여부)."""
    today = today or today_date()
    text = _collect_text(job)
    if not text:
        return None, False
    if ALWAYS_OPEN_RE.search(text):
        return None, True

    # D-DAY / D-0 → 오늘 마감
    if DDAY_TODAY_RE.search(text):
        return today, False
    m = DDAY_RE.search(text)
    if m:
        return today + timedelta(days=int(m.group(1))), False

    # MM/DD or MM.DD — 연도가 없으므로 어느 해인지 골라야 한다.
    #
    # 예전 규칙은 "60일 이상 과거면 내년으로 간주"였다. 연말(12월)에 본 '01/05'를
    # 내년 1월로 읽으려는 의도였지만, 조건에 연말이라는 단서가 없어서 **모든** 과거
    # 날짜에 걸렸다. 2026-08-19 에 본 '06/07' 은 2026-06-07(73일 전)을 건너뛰고
    # 2027-06-07 을 돌려주었고, 두 달 전에 끝난 공고가 '내년 마감'이라 모집중으로
    # 남았다. 마감 아카이브에는 이미 들어가 있는 공고가 활성 목록에도 계속 남는
    # 이유가 이것이다(같은 URL·같은 마감일로 1,178건).
    #
    # 오늘에서 가장 가까운 후보를 고른다. 연말→연초는 그대로 처리되고(12/28 에 본
    # 01/05 는 내년 쪽이 8일 뒤라 더 가깝다) 몇 달 지난 마감은 과거로 남는다.
    m = MD_RE.search(text)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            cands = []
            for year in (today.year - 1, today.year, today.year + 1):
                try:
                    cands.append(date(year, mm, dd))
                except ValueError:      # 2월 29일 등 그 해에 없는 날짜
                    continue
            if cands:
                return min(cands, key=lambda c: abs((c - today).days)), False
    return None, False


def classify_status(job: dict, today: date | None = None) -> tuple[str, str, str | None]:
    """(status, reason, deadline_iso) 반환. status는 'active' | 'closed'."""
    today = today or today_date()
    deadline, always_open = parse_deadline(job, today)
    if always_open:
        return "active", "상시/수시 채용", None
    if deadline is None:
        return "active", "마감일 정보 없음", None
    iso = deadline.isoformat()
    if deadline < today:
        return "closed", f"마감일 경과({iso})", iso
    return "active", f"마감 {iso}", iso
