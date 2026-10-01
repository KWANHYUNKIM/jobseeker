"""Anthropic 래퍼 — 사실기반 이력서 생성 / JD 적합도 분석.

환각 방지가 핵심 설계 원칙:
  * 생성/분석의 유일한 근거는 사용자의 '사실 프로필'이다.
  * 프로필에 없는 경력·수치·기술은 절대 지어내지 않는다.
  * JD가 원하지만 프로필에 없는 항목은 'gap'으로 표시한다(거짓 주장 금지).

모델: claude-opus-4-8 (adaptive thinking). 출력은 structured outputs(JSON schema)로 강제.
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

from . import store

MODEL = "claude-opus-4-8"

# 사실 위반을 막는 공통 규칙 — 모든 호출의 system 앞부분에 둔다.
_GROUNDING = (
    "너는 구직자의 이력서 작성을 돕는다. 절대 규칙:\n"
    "1. 아래 '사실 프로필'에 명시된 사실만 사용한다. 회사명·기간·직책·수치·"
    "성과·기술스택을 추측하거나 지어내지 않는다.\n"
    "2. 프로필에 근거가 없는 주장은 작성하지 않는다. 과장·미화도 금지.\n"
    "3. JD가 요구하지만 프로필에 근거가 없는 항목은 본문에 거짓으로 채우지 말고 "
    "별도의 'gaps'로 보고한다.\n"
    "4. 한국어로 작성한다.\n"
)


def _client() -> anthropic.Anthropic:
    key = store.get_api_key()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY 없음")
    return anthropic.Anthropic(api_key=key)


def _profile_text(profile: dict[str, Any]) -> str:
    """프로필을 모델이 읽기 좋은 텍스트로 직렬화(빈 값은 생략)."""
    return json.dumps(profile, ensure_ascii=False, indent=2)


def _job_text(job: dict[str, Any]) -> str:
    keep = ("company", "title", "career", "location", "tech_stack",
            "main_tasks", "qualifications", "preferences", "benefits")
    slim = {k: job.get(k) for k in keep if job.get(k)}
    return json.dumps(slim, ensure_ascii=False, indent=2)


def _parse(response) -> dict[str, Any]:
    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)


# ── JD 적합도 분석 ───────────────────────────────────────────
_FIT_SCHEMA = {
    "type": "object",
    "properties": {
        "fit_score": {"type": "integer", "description": "0~100 적합도 점수"},
        "summary": {"type": "string", "description": "한 문단 종합 평가"},
        "matched": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string"},
                    "evidence": {"type": "string", "description": "프로필 내 근거"},
                },
                "required": ["requirement", "evidence"],
                "additionalProperties": False,
            },
        },
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["requirement", "note"],
                "additionalProperties": False,
            },
        },
        "missing_skills": {"type": "array", "items": {"type": "string"}},
        "recommendation": {"type": "string", "description": "지원 전 보완 제안"},
    },
    "required": ["fit_score", "summary", "matched", "gaps",
                 "missing_skills", "recommendation"],
    "additionalProperties": False,
}


def analyze_fit(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    client = _client()
    system = (
        _GROUNDING
        + "\n작업: 내 프로필과 채용공고(JD)를 비교해 적합도를 분석한다. "
        "matched는 JD 요구사항 중 프로필에 근거가 있는 것만, gaps는 근거가 없는 것만 넣는다.\n\n"
        f"[사실 프로필]\n{_profile_text(profile)}"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": f"[채용공고]\n{_job_text(job)}"}],
        output_config={"format": {"type": "json_schema", "schema": _FIT_SCHEMA}},
    )
    return _parse(response)


# ── 맞춤 이력서/자기소개서 생성 ──────────────────────────────
_DOC_SCHEMA = {
    "type": "object",
    "properties": {
        "document": {"type": "string", "description": "마크다운 본문(사실기반)"},
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "wanted": {"type": "string", "description": "JD가 원하는 것"},
                    "note": {"type": "string", "description": "프로필에 근거가 없어 비운 이유"},
                },
                "required": ["wanted", "note"],
                "additionalProperties": False,
            },
        },
        "facts_used": {
            "type": "array",
            "items": {"type": "string"},
            "description": "본문에 사용한 프로필 사실 목록",
        },
    },
    "required": ["document", "gaps", "facts_used"],
    "additionalProperties": False,
}

_KIND_GUIDE = {
    "resume": "JD에 맞춰 강조점을 조정한 '이력서' 초안. 경력/프로젝트/스킬을 JD 요구와 연결.",
    "cover_letter": "JD에 맞춘 '자기소개서/지원동기' 초안. 사실기반 경험으로 적합성 서술.",
}


def generate_document(profile: dict[str, Any], job: dict[str, Any],
                      kind: str = "resume") -> dict[str, Any]:
    client = _client()
    guide = _KIND_GUIDE.get(kind, _KIND_GUIDE["resume"])
    system = (
        _GROUNDING
        + f"\n작업: {guide}\n"
        "본문(document)은 마크다운. JD가 원하지만 프로필에 근거가 없는 항목은 "
        "본문에 넣지 말고 gaps에 적는다. facts_used에는 실제로 활용한 프로필 사실을 나열한다.\n\n"
        f"[사실 프로필]\n{_profile_text(profile)}"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": f"[채용공고]\n{_job_text(job)}"}],
        output_config={"format": {"type": "json_schema", "schema": _DOC_SCHEMA}},
    )
    return _parse(response)


# ── 지원 폼 문항별 답안 생성 ─────────────────────────────────
_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "원래 문항"},
                    "answer": {"type": "string", "description": "사실기반 답안(글자수 제한 준수)"},
                    "char_count": {"type": "integer", "description": "답안 글자수"},
                    "maxlen": {"type": "integer", "description": "이 문항의 글자수 제한(없으면 0)"},
                    "gap": {"type": "string", "description": "근거가 부족해 비웠거나 보완이 필요하면 설명, 없으면 빈 문자열"},
                },
                "required": ["q", "answer", "char_count", "maxlen", "gap"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string", "description": "전반 참고사항"},
    },
    "required": ["answers", "notes"],
    "additionalProperties": False,
}


def generate_answers(profile: dict[str, Any], capture: dict[str, Any],
                     job: dict[str, Any] | None = None) -> dict[str, Any]:
    """수집한 지원 폼의 문항별로 사실기반 답안 생성."""
    client = _client()
    fields = capture.get("fields") or []
    field_lines = []
    for f in fields:
        ml = f.get("maxlen")
        limit = f" (최대 {ml}자)" if ml else ""
        field_lines.append(f"- {f.get('q')}{limit}")
    job_ctx = f"\n\n[참고 채용공고]\n{_job_text(job)}" if job else ""
    system = (
        _GROUNDING
        + "\n작업: 아래 지원 폼의 각 '문항'에 대해 답안을 작성한다. "
        "글자수 제한이 있으면 그 안에 맞춘다(char_count로 길이 보고). "
        "프로필에 근거가 없는 문항은 답안을 지어내지 말고 answer를 비우거나 골격만 쓰고 gap에 무엇이 필요한지 적는다.\n\n"
        f"[사실 프로필]\n{_profile_text(profile)}"
    )
    user = (
        f"지원처: {capture.get('title') or capture.get('host')}\n"
        f"[지원 폼 문항]\n" + "\n".join(field_lines) + job_ctx
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _ANSWER_SCHEMA}},
    )
    return _parse(response)
