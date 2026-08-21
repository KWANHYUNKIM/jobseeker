#!/usr/bin/env python3
"""
all_jobs.json 을 읽어 jobkorea 항목의 txt 파일을 파싱하여 구조화된 필드를 추가하고,
모든 사이트를 공통 스키마(career, location, tech_stack, main_tasks, qualifications,
preferences, benefits, full_jd)로 정규화한 enriched JSON 을 출력한다.

사용:
  python3 enrich_jobs.py
출력:
  jd-viewer/public/all_jobs_enriched.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "catch_capture" / "screenshots" / "all_개발자_latest"
INPUT = DATA_DIR / "all_jobs.json"
INPUT_CLOSED = DATA_DIR / "all_jobs_closed.json"
OUTPUT = Path(__file__).resolve().parent.parent / "public" / "all_jobs_enriched.json"

# 마감 판정 규칙의 소유자는 pipeline/job_status 하나다. 여기서 다시 부르는 이유는
# 규칙을 복제하려는 게 아니라, 스냅샷이 규칙 수정 이전에 만들어졌을 수 있기 때문이다.
# 같은 함수를 통과시키면 뷰어는 스냅샷이 낡았어도 항상 최신 규칙으로 보인다.
sys.path.insert(0, str(ROOT / "catch_capture"))
from pipeline.job_status import classify_status, today_date  # noqa: E402

SECTION_PATTERN = re.compile(r"^\[([^\]]+)\]\s*$")


HEADER_KEYS = {"회사", "제목", "URL", "경력", "고용형태", "학력", "위치"}


def parse_jobkorea_txt(text: str) -> dict:
    """jobkorea txt 의 [섹션] 헤더 기반 본문을 dict 로 변환."""
    lines = text.splitlines()
    header: dict[str, str] = {}
    sections: dict[str, list[str]] = {}

    current: str | None = None
    for line in lines:
        m = SECTION_PATTERN.match(line)
        if m:
            current = m.group(1).strip()
            sections.setdefault(current, [])
            continue

        if ":" in line:
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            if k in HEADER_KEYS and v:
                header[k] = v
                continue

        if current is not None:
            sections[current].append(line)

    def section(name: str) -> str:
        return "\n".join(sections.get(name, [])).strip()

    tech_raw = section("기술스택")
    tech_list: list[str] = []
    if tech_raw and tech_raw != "(추출 실패)":
        tech_list = [
            t.strip()
            for t in re.split(r"[,/·]", tech_raw)
            if t.strip() and "식별된 기술스택 없음" not in t
        ]

    return {
        "career": header.get("경력", ""),
        "location": header.get("위치", ""),
        "employment": header.get("고용형태", ""),
        "education": header.get("학력", ""),
        "tech_stack": tech_list,
        "main_tasks": section("주요업무"),
        "qualifications": section("자격요건"),
        "preferences": section("우대사항"),
        "benefits": section("복지/혜택"),
        "deadline": section("마감"),
        "full_jd": text,
    }


def normalize(job: dict) -> dict:
    site = job.get("site")
    out = {
        "site": site,
        "idx": job.get("idx"),
        "pid": str(job.get("pid", "")),
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "url": job.get("url", ""),
        "career": "",
        "location": "",
        "tech_stack": [],
        "main_tasks": "",
        "qualifications": "",
        "preferences": "",
        "benefits": "",
        "full_jd": "",
        # 마감 여부는 aggregate 의 job_status 가 이미 판정해 all_jobs.json 에 실어 보낸다.
        # normalize 가 새 dict 를 만들면서 이 세 필드를 안 옮겨서, 뷰어에 도착할 때는
        # 전부 None 이었다 — 화면이 마감을 표시할 방법 자체가 없었다.
        "status": job.get("status") or "active",
        "closed_reason": job.get("closed_reason") or "",
        "deadline_date": job.get("deadline_date") or "",
    }

    if site == "jobkorea":
        txt_name = job.get("txt")
        parsed_ok = False
        if txt_name:
            txt_path = DATA_DIR / "jobkorea" / txt_name
            if txt_path.exists():
                parsed = parse_jobkorea_txt(txt_path.read_text(encoding="utf-8"))
                out.update(parsed)
                parsed_ok = True
        if not parsed_ok:
            # txt 파일이 없는 입력(이미 enrich 된 레코드를 다시 넣는 경우)에서는
            # 레코드가 들고 있는 값을 그대로 쓴다. 그러지 않으면 본문과 기술스택이
            # 통째로 빈 채 나가서, 되돌리는 작업이 오히려 데이터를 깎는다.
            for k in ("tech_stack", "main_tasks", "qualifications", "preferences",
                      "benefits", "full_jd", "career", "location"):
                v = job.get(k)
                if v:
                    out[k] = v
        # 마감 캘린더용: 원본 마감 표기 보존(jobkorea 는 parsed 에 deadline 포함)
        out["dday"] = job.get("dday", "") or ""
        out.setdefault("deadline", job.get("deadline", "") or "")
        return out

    # wanted / jumpit / saramin / dev / remote / ats — already have most fields
    out["career"] = job.get("career") or job.get("location", "")
    if site in ("saramin", "dev", "jumpit"):
        out["location"] = job.get("location", "")
    elif site == "wanted":
        out["location"] = ""

    # 해외 보드(remote) / 회사 자체 채용페이지(ats): 위치·지역·해외여부 보존
    if site in ("remote", "ats"):
        out["location"] = job.get("location", "")
        out["career"] = ""  # 이 소스는 경력 표기가 없어 location 을 career 로 쓰지 않는다
        out["region"] = job.get("region", "") or ("global" if site == "remote" else "")
        out["source_board"] = job.get("source_board", "")
        out["overseas"] = out["region"] != "kr"

    stack = list(job.get("tech_stack") or [])
    for extra in (job.get("skills") or [], job.get("tech_tags") or []):
        for s in extra:
            if s not in stack:
                stack.append(s)
    out["tech_stack"] = stack
    out["main_tasks"] = job.get("main_tasks", "") or ""
    out["qualifications"] = job.get("qualifications", "") or ""
    out["preferences"] = job.get("preferences", "") or ""
    out["benefits"] = job.get("benefits", "") or ""
    out["full_jd"] = job.get("full_jd", "") or ""
    # 마감 캘린더용: 원본 마감 표기(deadline/dday) 보존 — 사이트별 형식은 build_calendar 가 흡수
    out["deadline"] = job.get("deadline", "") or ""
    out["dday"] = job.get("dday", "") or ""
    return out


def main() -> None:
    # 마감 공고도 함께 내보낸다. 숨기는 게 아니라 status 로 구분해서 내보내는 것이 요점이다 —
    # 뷰어는 기본적으로 모집중만 보여주되 '마감' 배지로 따로 볼 수 있고, 색인(semantic
    # ingest)·유사공고·트렌드는 이 파일 하나를 그대로 읽으므로 마감 공고도 계속 검색된다.
    # 마감을 파일에서 빼버리면 "예전에 이런 공고가 있었다"가 통째로 사라진다.
    today = today_date()
    raw = json.loads(INPUT.read_text(encoding="utf-8"))
    enriched = []
    regraded = 0
    for j in raw:
        e = normalize(j)
        st, reason, iso = classify_status(j, today)
        if st != e["status"]:
            regraded += 1
        e["status"], e["closed_reason"], e["deadline_date"] = st, reason, iso or ""
        enriched.append(e)
    if regraded:
        print(f"  [status] 스냅샷과 달라 재판정한 공고 {regraded:,}건 (마감 규칙 최신본 적용)")
    n_closed = sum(1 for e in enriched if e["status"] == "closed")
    if INPUT_CLOSED.exists():
        closed = json.loads(INPUT_CLOSED.read_text(encoding="utf-8"))
        seen = {(j.get("site"), j.get("url")) for j in enriched}
        for j in closed:
            if (j.get("site"), j.get("url")) in seen:
                continue
            e = normalize(j)
            e["status"] = "closed"
            enriched.append(e)
            n_closed += 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    active = sum(1 for e in enriched if e["status"] != "closed")
    print(f"wrote {len(enriched)} jobs (모집중 {active:,} / 마감 {len(enriched)-active:,}) -> {OUTPUT}")


if __name__ == "__main__":
    main()
