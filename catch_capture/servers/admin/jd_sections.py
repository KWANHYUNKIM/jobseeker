"""JD를 우선순위 3섹션으로 추출 — 지원자격(필수) / 주요업무 / 우대(가산점).

채용 배점은 보통 '지원자격 > 주요업무 > 우대(가산점)' 순이다. 이 우선순위를
점수 가중에 반영하려면 먼저 JD를 세 덩어리로 나눠야 한다. 사이트마다 형태가 다르다:
- wanted/jumpit/saramin: qualifications/main_tasks/preferences 필드가 분리돼 있음 → 그대로.
- jobkorea: 전부 full_jd 한 덩어리. 본문에 '자격요건/지원자격', '담당/주요업무',
  '우대' 헤더가 다수 존재 → 헤더 위치로 쪼갠다. 헤더가 없으면 전체를 required로 둔다.

이 3분할(+기술스택/제목)을 embed(가중 벡터)·생성(ai)에서 공통으로 쓴다.
"""
from __future__ import annotations

import re
from typing import Any

# full_jd 본문에서 섹션 헤더를 찾기 위한 패턴 → 버킷 매핑.
_HDR_BUCKET = [
    (re.compile(r"지원\s*자격|자격\s*요건|자격\s*조건|필수\s*요건|필수\s*자격"), "required"),
    (re.compile(r"주요\s*업무|담당\s*업무|업무\s*내용|수행\s*업무|하실\s*업무|업무\s*소개"), "tasks"),
    (re.compile(r"우대\s*사항|우대\s*조건|이런\s*분"), "preferred"),
    (re.compile(r"우대"), "preferred"),  # 마지막 보루(짧은 '우대')
]
# 본문 머리의 메타 블록([조건]/[기술스택]/[마감]/[이미지 OCR] 등)은 섹션 판단에서 잡음.


def _find_headers(text: str) -> list[tuple[int, int, str]]:
    """본문에서 (시작, 끝, 버킷) 헤더 위치 목록. 같은 위치 중복은 첫 매칭 우선."""
    hits: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []
    for rx, bucket in _HDR_BUCKET:
        for m in rx.finditer(text):
            s, e = m.start(), m.end()
            if any(s < te and e > ts for ts, te in taken):  # 이미 더 강한 헤더가 점유
                continue
            taken.append((s, e))
            hits.append((s, e, bucket))
    hits.sort(key=lambda x: x[0])
    return hits


def _parse_full_jd(text: str) -> dict[str, str] | None:
    """헤더 기준으로 full_jd를 required/tasks/preferred로 분할(없으면 None)."""
    hits = _find_headers(text)
    if not hits:
        return None
    out: dict[str, list[str]] = {"required": [], "tasks": [], "preferred": []}
    for i, (s, e, bucket) in enumerate(hits):
        nxt = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        body = text[e:nxt].strip(" :：]\n\t")
        if body:
            out[bucket].append(body)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def _flat(v: Any) -> str:
    if isinstance(v, list):
        return "\n".join(_flat(x) for x in v)
    if isinstance(v, dict):
        return " ".join(_flat(x) for x in v.values())
    return str(v or "")


def sections(job: dict[str, Any]) -> dict[str, str]:
    """JD → {'required','tasks','preferred'} 텍스트.

    required에는 지원자격 + 기술스택 + 제목(필수 맥락)을, tasks/preferred는 각 섹션을 담는다.
    구조화 필드가 비어 있고 full_jd가 있으면(jobkorea) 헤더 파싱으로 보충한다.
    """
    qual = _flat(job.get("qualifications")).strip()
    tasks = _flat(job.get("main_tasks")).strip()
    pref = _flat(job.get("preferences")).strip()

    if not (qual or tasks or pref):  # 구조화 안 됨 → full_jd 헤더 파싱 시도
        parsed = _parse_full_jd(_flat(job.get("full_jd")))
        if parsed:
            qual, tasks, pref = parsed["required"], parsed["tasks"], parsed["preferred"]
        elif _flat(job.get("full_jd")).strip():
            qual = _flat(job.get("full_jd")).strip()  # 헤더조차 없으면 전체를 필수로

    tech = _flat(job.get("tech_stack")).strip()
    title = _flat(job.get("title")).strip()
    required = "\n".join(p for p in (title, tech, qual) if p).strip()
    return {"required": required, "tasks": tasks, "preferred": pref}
