"""연차(경력 햇수) 매칭 — 규칙 기반(무료·정확).

"3년 이상" 같은 정량 요건은 임베딩으로 풀 수 없다(숫자 비교가 필요). 그래서 별도로
JD의 요구 연차를 파싱하고, 프로필 경력에서 총 햇수를 계산해 충족/미달을 판정한다.

JD 요구 연차의 1차 소스는 정제된 `career` 필드(예: '경력3년↑', '경력 3~10년',
'신입', '경력무관'). 비어 있으면 자격요건 텍스트에서 보수적으로 보충 추출한다.
('대졸 4년제' 같은 학력 표현을 연차로 오인하지 않도록 '경력 … N년 이상' 형태만.)
"""
from __future__ import annotations

import datetime
import re
from typing import Any

# 요구 연차 추출용. 범위(3~10년) → 하한, 'N년 이상/↑/+' → N, '경력 N년' → N.
_RANGE = re.compile(r"(\d+)\s*[~\-–]\s*\d+\s*년")
_MIN = re.compile(r"(\d+)\s*년\s*(?:이상|↑|\+)")
_PLAIN = re.compile(r"경력\s*(\d+)\s*년")
# 자격요건 텍스트 fallback: '경력' 문맥 안의 'N년 이상'만(학력 오인 방지).
_QUAL = re.compile(r"경력[^\n.]{0,12}?(\d+)\s*년\s*(?:이상|↑|\+)")

_YM = re.compile(r"(\d{4})\D{0,2}(\d{1,2})?")
_ONGOING = re.compile(r"현재|재직|진행|present|now", re.I)
_BUFFER = 0.5   # 반올림/공백기 흡수용 여유(년)


def _now_months() -> int:
    t = datetime.date.today()
    return t.year * 12 + t.month


def _to_months(s: str, now: int) -> int | None:
    s = str(s or "").strip()
    if not s:
        return None
    if _ONGOING.search(s):
        return now
    m = _YM.search(s)
    if not m:
        return None
    y = int(m.group(1))
    mo = int(m.group(2)) if m.group(2) else 6  # 월 미상 → 중간(6월) 근사
    if not (1 <= mo <= 12):
        mo = 6
    return y * 12 + mo


def profile_years(profile: dict[str, Any]) -> float:
    """프로필 경력의 총 햇수(중복 구간은 단순 합산, 진행중은 오늘까지)."""
    now = _now_months()
    total = 0
    for e in profile.get("experiences", []) or []:
        a = _to_months(e.get("start"), now)
        b = _to_months(e.get("end"), now)
        if a is None or b is None or b < a:
            continue
        total += b - a
    return round(total / 12, 1)


def required_years(job: dict[str, Any]) -> dict[str, Any]:
    """JD 요구 연차. min=하한(년, 없으면 None), any=무관, entry_ok=신입가능."""
    career = str(job.get("career", "") or "").strip()
    res: dict[str, Any] = {"min": None, "any": False, "entry_ok": False, "raw": career}
    text = career
    if "무관" in text:
        res["any"] = True
        return res
    if "신입" in text:
        res["entry_ok"] = True
        res["min"] = 0  # 신입/신입·경력 → 하한 없음
        return res
    m = _RANGE.search(text) or _MIN.search(text) or _PLAIN.search(text)
    if m:
        res["min"] = int(m.group(1))
        return res
    # career에 숫자가 없으면(예: '경력') 자격요건 텍스트에서 보수적 보충.
    qm = _QUAL.search(str(job.get("qualifications", "") or ""))
    if qm:
        res["min"] = int(qm.group(1))
    return res  # min None = 연차 요건 미상(감점 안 함)


def assess(my_years: float, req: dict[str, Any]) -> dict[str, Any]:
    """충족 판정 + 표시 라벨 + 감점치(penalty, 미달일 때만)."""
    if req.get("any"):
        return {"status": "any", "label": "경력무관", "req_min": None,
                "my_years": my_years, "penalty": 0}
    rmin = req.get("min")
    if rmin is None:
        return {"status": "unknown", "label": "연차 미상", "req_min": None,
                "my_years": my_years, "penalty": 0}
    if my_years + _BUFFER >= rmin:
        lab = "신입 가능" if rmin == 0 else f"{rmin}년+ 충족"
        return {"status": "ok", "label": lab, "req_min": rmin,
                "my_years": my_years, "penalty": 0}
    gap = round(rmin - my_years, 1)
    # 미달 폭에 비례해 감점(최대 30점). 1년 부족 ≈ 6점.
    penalty = min(30, round(gap * 6))
    return {"status": "under", "label": f"{rmin}년 요구·{gap}년 부족",
            "req_min": rmin, "my_years": my_years, "gap": gap, "penalty": penalty}
