"""문서 하나 — 경로 검증.

응답 캐시(utils/cache)는 쓰지 않는다: 역설계 회사 한 곳이 수 MB 라 512개를 들고 있으면
8GB 맥에서 수백 MB 가 된다. 기본키 조회 한 번이라 DB 에서 바로 읽어도 빠르다.
"""
from __future__ import annotations

import re

from app.core.exceptions import BadRequest, NotFound
from app.features.docs import repository

# public 기준 상대 경로만 받는다(…/·절대 경로·이상한 글자 차단). 키가 DB 에 있을 때만 답하므로
# 파일 시스템에 닿지는 않지만, 엉뚱한 키로 DB 를 두드리는 것도 막는다.
_PATH = re.compile(r"^[\w가-힣][\w가-힣.\-/]*\.(json|md)$")


def get(path: str) -> dict:
    if not _PATH.match(path) or ".." in path or "//" in path:
        raise BadRequest("경로는 public 기준 상대 경로(*.json·*.md)")
    doc = repository.find(path)
    if not doc:
        raise NotFound(f"{path} 없음")
    return doc
