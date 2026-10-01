"""v_job 한 행 → 뷰어의 Job. 필드 이름은 `jd-viewer/src/types.ts` 를 따른다.

**공고 한 건이 뷰어에 어떻게 보이는가의 단일 소스다.** 이 API 와, 크롤 파이프라인의
파일 내보내기(`catch_capture/store/jobs/export.py` → `all_jobs_enriched.json`)가 이
모듈을 같이 쓴다 — 두 벌로 두면 파일로 보던 화면과 API 로 보는 화면이 조용히 달라진다.
그래서 이 파일은 fastapi·DB 연결을 import 하지 않는다(파이프라인이 그대로 읽는다).
"""
from __future__ import annotations

# 뷰어 Job 한 건을 만드는 데 필요한 v_job 컬럼.
JOB_SELECT = """
            SELECT site, pid, company, company_slug, title, url,
                   career_text, location_text, tech_stack,
                   main_tasks, qualifications, preferences, benefits, full_jd,
                   status, status_source, deadline_on, dday, last_verified_at,
                   region, source_board, overseas, deadline_text,
                   employment, education, posted_on, first_seen_at
"""


def row_to_job(r: dict, idx: int) -> dict:
    job = {
        "site": r["site"],
        "idx": idx,
        "pid": r["pid"],
        "company": r["company"],
        "title": r["title"],
        "url": r["url"],
        "career": r["career_text"] or "",
        "location": r["location_text"] or "",
        "tech_stack": list(r["tech_stack"] or []),
        "main_tasks": r["main_tasks"] or "",
        "qualifications": r["qualifications"] or "",
        "preferences": r["preferences"] or "",
        "benefits": r["benefits"] or "",
        "full_jd": r["full_jd"] or "",
        "status": r["status"],
        "deadline_date": r["deadline_on"].isoformat() if r["deadline_on"] else "",
        "deadline": r["deadline_text"] or "",
        # dday 는 저장값이 아니라 **지금 다시 계산한** 값이다. build_calendar.py 와
        # build_reposts.py 가 이 필드를 파싱하므로 형식은 유지한다(빈 문자열 = 모르거나 지남).
        "dday": dday_text(r["dday"]),
        # 'unknown' 은 "모집중"이 아니라 "마감을 알 방법이 없어 열어둔 것"이다.
        "status_source": r["status_source"],
        "closed_reason": closed_reason(r),
        # 원본이 말한 등록일(없을 수 있다 — saramin)과, 그 대타인 "우리가 처음 본 날".
        # 추정값이라 화면이 둘을 구분해 보여준다 — 그래서 둘 다 싣는다.
        "posted_date": r["posted_on"].isoformat() if r["posted_on"] else "",
        "first_seen_at": r["first_seen_at"].date().isoformat() if r["first_seen_at"] else "",
        "company_slug": r["company_slug"],
    }
    if r["education"]:
        job["education"] = r["education"]
    if r["employment"]:
        job["employment"] = r["employment"]
    if r["region"]:
        job["region"] = r["region"]
    if r["source_board"]:
        job["source_board"] = r["source_board"]
    if r["overseas"]:
        job["overseas"] = True
    return job


def dday_text(dday: int | None) -> str:
    """남은 일수 → 'D-4' / 'D-DAY'. 모르거나 이미 지났으면 빈 문자열.

    지난 마감을 'D+3' 으로 내보내지 않는 이유: build_calendar 는 이 문자열을 미래
    날짜로 되돌려 읽으므로, 지난 값을 주면 캘린더에 없는 일정이 생긴다.
    """
    if dday is None or dday < 0:
        return ""
    return "D-DAY" if dday == 0 else f"D-{dday}"


def closed_reason(r: dict) -> str:
    src, status, dl = r["status_source"], r["status"], r["deadline_on"]
    if src == "override":
        return "수동 보정"
    if src == "always_open":
        return "상시/수시 채용"
    if src == "unknown":
        return "마감일 정보 없음"
    if src == "ledger":
        return f"원본 확인: {'마감' if status == 'closed' else '모집중'}"
    iso = dl.isoformat() if dl else ""
    return f"마감일 경과({iso})" if status == "closed" else f"마감 {iso}"
