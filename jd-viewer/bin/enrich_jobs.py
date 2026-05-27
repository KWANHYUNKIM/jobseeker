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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "catch_capture" / "screenshots" / "all_개발자_latest"
INPUT = DATA_DIR / "all_jobs.json"
OUTPUT = Path(__file__).resolve().parent.parent / "public" / "all_jobs_enriched.json"

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
    }

    if site == "jobkorea":
        txt_name = job.get("txt")
        if txt_name:
            txt_path = DATA_DIR / "jobkorea" / txt_name
            if txt_path.exists():
                parsed = parse_jobkorea_txt(txt_path.read_text(encoding="utf-8"))
                out.update(parsed)
        return out

    # wanted / jumpit / saramin / dev — already have most fields
    out["career"] = job.get("career") or job.get("location", "")
    if site in ("saramin", "dev", "jumpit"):
        out["location"] = job.get("location", "")
    elif site == "wanted":
        out["location"] = ""

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
    return out


def main() -> None:
    raw = json.loads(INPUT.read_text(encoding="utf-8"))
    enriched = [normalize(j) for j in raw]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(enriched)} jobs -> {OUTPUT}")


if __name__ == "__main__":
    main()
