"""환경변수 읽기 — 백엔드 설정의 단일 소스.

값은 프로세스가 뜰 때 한 번 읽는다. launchd(맥)·셸·테스트가 같은 이름을 쓴다 —
`.env.example` 에 전부 적어 둔다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_DSN = "postgresql://jobseeker:jobseeker@127.0.0.1:5433/jobseeker"


def _float(name: str, default: str) -> float:
    return float(os.environ.get(name, default))


def _int(name: str, default: str) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    # 정본 DB. 크롤 파이프라인(catch_capture)과 같은 DB 를 같은 이름으로 가리킨다.
    dsn: str = field(default_factory=lambda: os.environ.get("JOBSEEKER_DSN", DEFAULT_DSN))

    # SEARCH_HOST — setup-dashboards.sh 가 plist 에 이 이름으로 0.0.0.0 을 넣는다. 안 보면
    # launchd 로 뜬 서버가 loopback 에만 붙어 뷰어 nginx 컨테이너(host.docker.internal)가
    # 프록시하는 /api/ 가 전부 502 가 된다.
    host: str = field(default_factory=lambda: os.environ.get("SEARCH_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _int("API_PORT", "8771"))
    workers: int = field(default_factory=lambda: _int("API_WORKERS", "1"))

    # 같은 질의를 잠깐 들고 있는 시간(초). 0 이면 끈다(테스트).
    cache_ttl: float = field(default_factory=lambda: _float("API_CACHE_TTL", "60"))

    # 질의 임베딩 — 파이프라인이 공고를 임베딩한 것과 같은 모델·차원이어야 한다.
    ollama_url: str = field(default_factory=lambda: os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    embed_model: str = field(default_factory=lambda: os.environ.get("SEMANTIC_EMBED_MODEL", "bge-m3"))
    embed_dim: int = field(default_factory=lambda: _int("SEMANTIC_EMBED_DIM", "1024"))
    embed_timeout: float = field(default_factory=lambda: _float("API_EMBED_TIMEOUT", "20"))


settings = Settings()
