#!/usr/bin/env python3
"""직군별 키워드/자격요건/우대 표 (Notion 복붙용 markdown) 생성기.

입력: jd-viewer/public/all_jobs_enriched.json
출력: jd-viewer/public/blog_keywords.md

형식 A: 직군 한 줄 = 한 행. 핵심 키워드는 마인드맵(build_mindmap)의 핵심 스택과
동일하게, 우대사항은 관측 상위 역량으로, 자격요건은 채용공고 qualifications에서
학력/경력/요구 경험을 추출해 채운다. Notion에 붙여넣으면 표 블록으로 변환된다.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "catch_capture" / "dashboard"))
sys.path.insert(0, str(ROOT / "jd-viewer" / "bin"))
from classifier import classify_dev_roles, extract_competencies  # noqa: E402
from build_mindmap import ROLE_PROFILE, ROLES_ORDER  # noqa: E402

INPUT = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
OUTPUT = ROOT / "jd-viewer" / "public" / "blog_keywords.md"

# ---------- 자격요건 추출 ----------
EDU_RULES = [
    ("학력무관", "학력 무관"),
    ("학력 : 무관", "학력 무관"),
    ("초대졸", "초대졸 이상"),
    ("대학졸업(2,3년)", "전문대졸 이상"),
    ("전문대", "전문대졸 이상"),
    ("대학교졸업(4년)", "대졸 이상"),
    ("학사", "대졸 이상"),
    ("석사", "석·박사 우대"),
    ("박사", "석·박사 우대"),
]
CAREER_NEW = re.compile(r"신입|경력\s*무관|경력무관|연차\s*무관|연수\s*무관")
CAREER_YEARS = re.compile(r"경력\s*(\d+)\s*년\s*이상|(\d+)\s*년\s*이상")

# "OO 경험 / 능력" 명사구 — 자격요건 고유의 요구 역량
EXP_PAT = re.compile(r"([가-힣A-Za-z0-9 /\+\.\-]{3,40}?)\s*(경험|능력|이해|지식)")
EXP_STOP = {
    "운영", "사용", "개발", "활용", "핵심 역량", "아래", "필요", "띠",
    "관련", "업무", "다양한", "이상", "경력", "해당", "기타", "위", "그", "본",
    "분석", "처리", "구현", "설계", "유지보수", "성공", "기여", "수행",
}
EXP_PREFIX = re.compile(r"^[\-•·ㆍ*\s]*(있는|있으신|보유한?|가능한|관련|또는|및|에서|위한|등의?|그|본|해당)?\s*")
EXP_DROP = re.compile(r"(해본|기여한|준하는|유의미|성공|회사의)")


def clean_exp(kw: str) -> str | None:
    base = re.sub(r"\s*(경험|능력|이해|지식)$", "", kw).strip()
    # 불완전 어미 정리: "~에 대한", "~에 대한 깊은/기본" 등
    base = re.sub(r"에\s*대한(\s*\S+)?$", "", base).strip()
    base = re.sub(r"(을|를|이|가|에|의|와|과|및|또는|등)$", "", base).strip()
    base = re.sub(r"^[\-•·ㆍ*\s]+", "", base).strip()
    base = re.sub(r"[,··/]+$", "", base).strip()
    if not (3 <= len(base) <= 22):
        return None
    if base in EXP_STOP or EXP_DROP.search(base):
        return None
    return base


def collect(jobs: list[dict]) -> dict[str, dict]:
    data: dict[str, dict] = {r: {
        "count": 0, "tech": Counter(), "comp": Counter(),
        "edu": Counter(), "career_new": 0, "years": Counter(), "exp": Counter(),
    } for r in ROLES_ORDER}

    for j in jobs:
        roles = classify_dev_roles(
            title=j.get("title") or "",
            tech_stack=j.get("tech_stack") or [],
            extra_text=(j.get("qualifications") or "")[:500],
        )
        if not roles or roles == ["기타"]:
            continue
        q = j.get("qualifications") or ""
        comps = extract_competencies(" ".join([
            q, j.get("preferences") or "", j.get("main_tasks") or "",
        ]))
        # 학력
        edus = set()
        for key, lab in EDU_RULES:
            if key in q:
                edus.add(lab)
        # 경력
        has_new = bool(CAREER_NEW.search(q))
        ymin = None
        m = re.search(r"경력\s*(\d+)\s*년\s*이상", q)
        if m:
            ymin = int(m.group(1))
        # 요구 경험 명사구
        exps = set()
        for mm in EXP_PAT.finditer(q):
            kw = (mm.group(1).strip() + " " + mm.group(2)).strip()
            kw = EXP_PREFIX.sub("", kw).strip()
            c = clean_exp(kw)
            if c:
                exps.add(c)

        for r in roles:
            if r not in data:
                continue
            d = data[r]
            d["count"] += 1
            for t in j.get("tech_stack") or []:
                d["tech"][t] += 1
            for c in comps:
                d["comp"][c] += 1
            for e in edus:
                d["edu"][e] += 1
            if has_new:
                d["career_new"] += 1
            if ymin is not None:
                d["years"][ymin] += 1
            for e in exps:
                d["exp"][e] += 1
    return data


# 학력 라벨 정렬 우선순위 (낮은→높은)
EDU_ORDER = ["학력 무관", "초대졸 이상", "전문대졸 이상", "대졸 이상", "석·박사 우대"]


def fmt_edu(edu: Counter) -> str:
    labs = [l for l in EDU_ORDER if edu.get(l, 0) >= 2]
    if not labs:
        labs = [l for l in EDU_ORDER if edu.get(l, 0) >= 1]
    if not labs:
        return "명시 없음 (대부분 무관)"
    msd = "석·박사 우대" in labs
    base = [l for l in labs if l != "석·박사 우대"]
    if not base:
        return "석·박사 우대"
    span = base[0] if len(base) == 1 else f"{base[0]} ~ {base[-1]}"
    return f"{span} (석·박사 우대)" if msd else span


def fmt_career(career_new: int, years: Counter, total: int) -> str:
    parts = []
    if career_new and total and career_new / total >= 0.1:
        parts.append("신입 지원 가능")
    if years:
        top_y = years.most_common(1)[0][0]
        parts.append(f"경력 {top_y}년 이상")
    return " · ".join(parts) if parts else "경력 무관"


def fmt_exp(exp: Counter, k: int = 5) -> str:
    # 짧은 것 우선 + 빈도 우선으로 중복 줄이기
    seen: list[str] = []
    for kw, _ in exp.most_common(30):
        if any(kw in s or s in kw for s in seen):
            continue
        seen.append(kw)
        if len(seen) >= k:
            break
    return " · ".join(seen) if seen else "—"


def cell(s: str) -> str:
    return s.replace("|", "/").replace("\n", " ").strip()


def render(data: dict[str, dict], total: int) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out: list[str] = []
    out.append("# 개발자 직군별 키워드 · 자격요건 · 우대 (Notion 복붙용)")
    out.append("")
    out.append(f"- 데이터: 총 **{total}건** 채용공고 · 생성 {now}")
    out.append("- 아래 표 전체를 복사해 Notion에 붙여넣으면 표 블록으로 변환됩니다.")
    out.append("- 핵심 키워드 = 마인드맵 핵심 스택, 우대사항 = 관측 상위 역량, "
               "자격요건 = 공고 원문에서 추출")
    out.append("")
    out.append("| 직군 | 핵심 키워드 | 자격요건(학력) | 자격요건(경력) | 요구 경험·역량 | 우대사항 |")
    out.append("|---|---|---|---|---|---|")
    for r in ROLES_ORDER:
        prof = ROLE_PROFILE.get(r, {})
        d = data.get(r, {})
        n = d.get("count", 0)
        core = prof.get("핵심스택", [])
        tech = cell(", ".join(core[:10]))
        edu = cell(fmt_edu(d.get("edu", Counter())))
        car = cell(fmt_career(d.get("career_new", 0), d.get("years", Counter()), n))
        exp = cell(fmt_exp(d.get("exp", Counter())))
        comp = cell(" · ".join(c for c, _ in d.get("comp", Counter()).most_common(6)))
        out.append(f"| **{r}** ({n}건) | {tech} | {edu} | {car} | {exp} | {comp} |")
    out.append("")
    return "\n".join(out)


def generate(jobs: list[dict]) -> str:
    """jobs 리스트 → blog_keywords.md 마크다운 문자열."""
    data = collect(jobs)
    return render(data, total=len(jobs))


def _today() -> str:
    return datetime.now().date().isoformat()


# render() 머리말의 "· 생성 YYYY-MM-DD HH:MM" 에서 날짜만 뽑는 패턴
_GEN_DATE = re.compile(r"생성\s*(\d{4}-\d{2}-\d{2})")


def _output_date() -> str | None:
    """기존 blog_keywords.md 안에 박힌 생성 날짜(YYYY-MM-DD). 없으면 None."""
    if not OUTPUT.exists():
        return None
    m = _GEN_DATE.search(OUTPUT.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def record(jobs: list[dict], force: bool = False) -> Path | None:
    """오늘 첫 호출에만 blog_keywords.md 갱신. 이미 오늘 생성됐으면 None.

    aggregate가 매 사이클 호출해도 하루 1회만 쓰도록, 파일에 박힌 생성
    날짜를 보고 같은 날이면 skip한다(별도 상태파일 없이 자기완결적).
    """
    if not force and _output_date() == _today():
        return None
    md = generate(jobs)
    OUTPUT.write_text(md, encoding="utf-8")
    return OUTPUT


def main() -> None:
    if not INPUT.exists():
        print(f"[!] 입력 없음: {INPUT}", file=sys.stderr)
        sys.exit(1)
    jobs = json.loads(INPUT.read_text(encoding="utf-8"))
    print(f"[*] {len(jobs)}건 로드", flush=True)
    md = generate(jobs)
    OUTPUT.write_text(md, encoding="utf-8")
    print(f"[*] {OUTPUT.relative_to(ROOT)} 작성 ({len(md):,} bytes)", flush=True)


if __name__ == "__main__":
    main()
