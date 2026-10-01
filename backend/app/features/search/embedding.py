"""질의문 임베딩 — Ollama(bge-m3).

공고 쪽 벡터는 파이프라인(`catch_capture/store/vectors/embed.py`)이 같은 모델로 만들어
`job_embedding` 에 넣는다. 여기는 검색어 한 줄만 임베딩한다. 정규화 방식(L2)이
같아야 `<=>`(코사인 거리) 순서가 맞는다.
"""
from __future__ import annotations

import json
import math
import sys
import urllib.request

from app.core.config import settings


def embed_query(text: str) -> list[float] | None:
    """임베딩. Ollama 가 없거나 느리면 None — 그때는 FTS 만으로 답한다."""
    try:
        req = urllib.request.Request(
            f"{settings.ollama_url}/api/embed",
            data=json.dumps({"model": settings.embed_model, "input": [text]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=settings.embed_timeout) as resp:
            vec = (json.loads(resp.read().decode("utf-8")).get("embeddings") or [None])[0]
        if not vec or len(vec) != settings.embed_dim:
            raise ValueError(f"임베딩 차원 {len(vec) if vec else 0} ≠ {settings.embed_dim}")
    except Exception as e:                                          # noqa: BLE001
        print(f"[search] 벡터 건너뜀: {e}", file=sys.stderr)
        return None
    norm = math.sqrt(sum(v * v for v in vec))
    return list(vec) if norm == 0 else [v / norm for v in vec]
