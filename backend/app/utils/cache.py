"""짧은 응답 캐시.

운영 맥(8GB)은 크롤·Docker·임베딩이 같이 돌면 스왑이 차고, 그때 DB 질의가 1~17초로
들쭉날쭉했다(2026-09-30 측정, 스왑 8.2/9.2GB). 같은 질의 — 특히 필터 없는 첫 화면 —
는 반복되므로 잠깐 들고 있다가 답한다. 상태가 늦어지는 폭은 TTL 만큼이다.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, TypeVar

from app.core.config import settings

T = TypeVar("T")

CACHE_MAX = 512
_cache: dict[tuple, tuple[float, object]] = {}
_lock = threading.Lock()
# 테스트가 TTL 을 바꿔 볼 수 있게 모듈 변수로 둔다(None = 설정값).
ttl_override: float | None = None


def _ttl() -> float:
    return settings.cache_ttl if ttl_override is None else ttl_override


def cached(key: tuple, compute: Callable[[], T]) -> T:
    ttl = _ttl()
    if ttl <= 0:
        return compute()
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]  # type: ignore[return-value]
    value = compute()
    with _lock:
        if len(_cache) >= CACHE_MAX:
            # 오래된 절반을 버린다 — LRU 를 정확히 지킬 만큼의 일은 아니다.
            for k, _ in sorted(_cache.items(), key=lambda kv: kv[1][0])[: CACHE_MAX // 2]:
                _cache.pop(k, None)
        _cache[key] = (now, value)
    return value


def clear() -> None:
    with _lock:
        _cache.clear()
