"""규칙 기반 적합도 스코어러 — 프로필 ↔ JD 기술 매칭(무료·즉시).

전체 공고를 AI로 분석하면 비용·시간이 폭발하므로, 먼저 규칙 기반으로 전체를
점수화·랭킹하고 상위만 AI 정밀 분석(ai.analyze_fit)에 넘기는 구조.

핵심: 기술 어휘(TECH_VOCAB)를 양쪽(프로필/JD)에서 동일하게 추출 → 교집합/차집합으로
matched(보유)·missing(부족) 산출. 양쪽을 같은 어휘로 정규화하므로 오탐이 적다.
"""
from __future__ import annotations

import re
from typing import Any

# 정규화된 기술 어휘(소문자). 멀티워드는 긴 것이 먼저 매칭되도록 길이순 정렬에 의존.
TECH_VOCAB = [
    # 언어
    "java", "kotlin", "scala", "python", "javascript", "typescript", "golang", "go",
    "rust", "c++", "c#", "c", "php", "ruby", "swift", "objective-c", "dart", "r",
    "verilog", "vhdl",
    # 백엔드/프레임워크
    "spring boot", "spring cloud", "spring webflux", "spring", "egovframe",
    "전자정부프레임워크", "mybatis", "jpa", "hibernate", "querydsl", "node.js", "nodejs",
    "express", "nestjs", "django", "fastapi", "flask", "laravel", "rails", ".net",
    "grpc", "graphql", "rest",
    # 프론트엔드
    "react native", "react", "next.js", "nextjs", "vue", "nuxt", "angular", "svelte",
    "redux", "recoil", "jquery", "html", "css", "sass", "tailwind", "webpack", "vite",
    # DB/메시징/검색
    "mysql", "mariadb", "postgresql", "postgres", "oracle", "mssql", "mongodb",
    "redis", "elasticsearch", "kafka", "rabbitmq", "mqtt", "dbeaver",
    # 인프라/클라우드/DevOps
    "docker", "kubernetes", "k8s", "jenkins", "github actions", "gitlab ci",
    "terraform", "ansible", "aws", "gcp", "azure", "nginx", "apache", "linux",
    "prometheus", "grafana", "kibana", "git",
    # 데이터/AI
    "hadoop", "spark", "airflow", "flink", "tensorflow", "pytorch", "pandas",
    "numpy", "scikit-learn", "llm", "opencv",
    # 임베디드/IoT/하드웨어
    "atmega", "atmega128", "embedded", "firmware", "rtos", "uart", "spi", "i2c",
    "can", "arm", "esp32", "raspberry pi", "fpga",
    # 모바일/기타
    "android", "ios", "flutter", "unity", "unreal", "junit", "jest", "selenium",
]

# 긴 항목 우선(부분 겹침 방지) + 정규식 결합
_VOCAB_SORTED = sorted(set(TECH_VOCAB), key=len, reverse=True)
_BND = r"(?<![a-z0-9+#.가-힣])(%s)(?![a-z0-9+#.가-힣])"
_VOCAB_RE = re.compile(_BND % "|".join(re.escape(t) for t in _VOCAB_SORTED), re.I)

_JOB_FIELDS = ("tech_stack", "qualifications", "preferences", "main_tasks", "title", "skills")
_PROFILE_TEXT_KEYS = ("skills", "summary", "headline")


def _as_text(v: Any) -> str:
    if isinstance(v, list):
        return " ".join(_as_text(x) for x in v)
    if isinstance(v, dict):
        return " ".join(_as_text(x) for x in v.values())
    return str(v or "")


def extract_terms(text: str) -> set[str]:
    return {m.lower() for m in _VOCAB_RE.findall(text or "")}


def profile_terms(profile: dict[str, Any]) -> set[str]:
    parts = [_as_text(profile.get(k)) for k in _PROFILE_TEXT_KEYS]
    for exp in profile.get("experiences", []) or []:
        parts.append(_as_text(exp.get("bullets")))
    for pr in profile.get("projects", []) or []:
        parts.append(_as_text(pr.get("stack")))
        parts.append(_as_text(pr.get("bullets")))
    return extract_terms(" ".join(parts))


def job_terms(job: dict[str, Any]) -> set[str]:
    return extract_terms(" ".join(_as_text(job.get(k)) for k in _JOB_FIELDS))


def score(profile_have: set[str], job: dict[str, Any]) -> dict[str, Any]:
    """profile_have는 profile_terms()로 미리 계산해 전달(루프 최적화)."""
    jt = job_terms(job)
    matched = sorted(jt & profile_have)
    missing = sorted(jt - profile_have)
    pct = round(100 * len(matched) / len(jt)) if jt else 0
    return {
        "score": pct,
        "matched": matched,
        "missing": missing,
        "n_job_terms": len(jt),
        "low_confidence": len(jt) < 3,  # JD에 기술 정보가 적으면 신뢰도 낮음
    }
