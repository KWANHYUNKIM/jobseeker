#!/usr/bin/env python3
"""채용 모집 캘린더 데이터 빌더.

각 공고의 **모집 시작일 · 마감일 · 상시채용 여부**를 뽑아
`public/job_calendar.json` 으로 낸다. 뷰어의 모집 캘린더 탭이 읽는다.

## 여기서 마감일을 다시 파싱하지 않는다

예전 이 파일은 `deadline`/`dday` 원문("~06/14(일)", "D-4")을 **스스로 다시**
파싱했다. `pipeline/job_status.parse_deadline` 과 같은 일을 하는 두 번째 파서였고,
둘은 결국 갈라졌다 — job_status 는 "오늘에서 가장 가까운 후보" 로 고쳤는데 여기에는
그 전 규칙("60일 이상 과거면 내년") 사본이 남아, 두 달 전에 끝난 06/14 를
**내년 6월 14일** 로 읽어 캘린더에 없는 일정을 만들었다.

이제 마감일은 `deadline_date` 를 그대로 쓴다. 그 값은 v_job(`job_state`)이
원장·override·크롤 텍스트를 순서대로 따져 **읽는 시점에** 계산한 것이라
여기서 손댈 이유가 없다. 파서는 한 벌이면 된다.

## 시작일은 어디서 오나

  ① `posted_date`  — 원본이 말한 등록일(JSON-LD datePosted / jumpit publishedAt).
                     `pipeline/close_check` 가 재확인하면서 같이 받아 온다.
  ② JD 본문의 "접수기간: 6.1 ~ 6.30" 의 앞쪽 — 공채에 많다.
  ③ `first_seen_at` — 위 둘이 없으면 "우리가 처음 본 날". 추정값이라
                     항목에 `start_estimated: true` 를 달아 화면이 구분할 수 있게 한다.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from jobs_filter import active_only, load_jobs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "public" / "all_jobs_enriched.json"
OUT = ROOT / "public" / "job_calendar.json"

# JD 본문의 접수/모집 기간 라인. 시작일을 얻는 데만 쓴다(마감일은 deadline_date 가 답한다).
PERIOD_RE = re.compile(r"(?:접수|모집|지원)\s*기간\s*[:：]?\s*(.+)")


def _to_iso(token: str, *, this_year: int) -> str | None:
    """'2026-06-30' / '2026.6.30' / '06/30' / '6.30' → ISO. 실패 시 None."""
    token = token.strip()
    m = re.match(r"^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", token)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.match(r"^(\d{1,2})[.\-/](\d{1,2})", token)
        if not m:
            return None
        mo, d = map(int, m.groups())
        y = this_year
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def jd_start(full_jd: str, *, this_year: int) -> str | None:
    """JD 본문 "접수기간: <시작> ~ <끝>" 의 시작일. 없으면 None.

    끝 쪽은 읽지 않는다 — 마감일은 deadline_date 가 이미 답했고, 본문 표기는
    연도가 없는 경우가 많아 다시 추측하는 자리가 된다.
    """
    if not full_jd:
        return None
    m = PERIOD_RE.search(full_jd)
    if not m:
        return None
    head = re.split(r"~|∼|〜|–|—", m.group(1)[:80], maxsplit=1)[0]
    return _to_iso(head, this_year=this_year)


def _date_part(value: str | None) -> str | None:
    """'2026-09-16T11:40:00+09:00' / '2026-09-16' → '2026-09-16'. 없으면 None."""
    if not value:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(value))
    return m.group(1) if m else None


def main() -> None:
    # 마감 공고는 뺀다. 공고 목록은 모집중과 마감을 함께 담는데(색인·과거 조회를
    # 살리려고) 이 빌더의 결과는 "지금 시장" 이라 만료 공고를 세면 수요가 과거에 눌린다.
    jobs = active_only(load_jobs(SRC))
    today = date.today()
    items = []
    dated = always_open = no_info = expired = 0
    start_exact = start_guessed = 0

    for j in jobs:
        deadline = _date_part(j.get("deadline_date"))
        # 마감일이 오늘보다 과거인데 목록에 남아 있다면 status 가 아직 안 따라온
        # 것이다(파일이 묵었거나 export 와 이 빌더 사이에 자정이 지났거나).
        # 캘린더는 "지금 지원할 수 있는 일정" 이므로 여기서 제외한다.
        if deadline and deadline < today.isoformat():
            expired += 1
            continue
        always = (j.get("status_source") == "always_open") and not deadline

        posted = _date_part(j.get("posted_date"))
        start = posted or jd_start(j.get("full_jd") or "", this_year=today.year)
        estimated = False
        if not start:
            start = _date_part(j.get("first_seen_at"))
            estimated = bool(start)
        if start and deadline and start > deadline:
            start, estimated = None, False     # 앞뒤가 뒤집힌 값은 싣지 않는다

        if deadline:
            dated += 1
        elif always:
            always_open += 1
        else:
            no_info += 1
        if start:
            if estimated:
                start_guessed += 1
            else:
                start_exact += 1

        if deadline or start or always:
            items.append({
                "company": j.get("company", ""),
                "title": j.get("title", ""),
                "url": j.get("url", ""),
                "site": j.get("site", ""),
                "career": j.get("career", ""),
                "tech_stack": (j.get("tech_stack") or [])[:8],
                "start": start,
                "start_estimated": estimated,
                "deadline": deadline,
                "always_open": always,
            })

    doc = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(jobs),
        "dated": dated,
        "always_open": always_open,
        "no_info": no_info,
        # 목록에는 모집중으로 있지만 마감일이 이미 지난 공고. status 가 아직
        # 안 따라온 것들이라 캘린더에서 뺐다. 이 숫자가 계속 크면 재확인
        # (pipeline.close_check)이 못 따라가고 있다는 신호다.
        "expired": expired,
        "items": items,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"[calendar] 총 {len(jobs)}건 → 마감일 {dated} · 상시 {always_open} · "
          f"정보없음 {no_info} · 마감일 지나 제외 {expired}")
    print(f"           시작일: 원본 등록일/접수기간 {start_exact} · 처음 본 날로 추정 {start_guessed}")
    print(f"           items {len(items)}건 저장 → {OUT}")


if __name__ == "__main__":
    main()
