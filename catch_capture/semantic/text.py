"""임베딩 입력 텍스트 생성 — 저장소에 의존하지 않는다.

`ingest.py` 안에 있던 것을 떼어냈다. 이유는 하나다: 저장소를 SQLite 에서
PostgreSQL 로 옮기는 동안 **두 경로가 같은 텍스트를 만들어야** 한다. ingest 에
그대로 두면 `store.embed` 가 그 모듈을 import 하면서 sqlite_vec 까지 끌고 들어오고,
그게 싫어서 규칙을 베끼는 순간 임베딩 입력이 두 벌이 된다 — 그러면 같은 공고의
벡터가 경로에 따라 달라지고, content_hash 도 갈려서 증분 임베딩이 영원히 안 끝난다.

ingest.py 는 여기서 re-export 해 쓰므로 기존 import 경로는 그대로 동작한다.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .config import MAX_EMBED_CHARS

# 섹션 하나가 입력 전체를 먹어치우지 않게 잘라 쓰는 상한.
SECTION_CHARS = 700

_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_CODE_FENCE = re.compile(r"```.*?```", re.S)
_WS = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")


def as_list(v: Any) -> list[str]:
    """tech_stack 등은 보통 list 지만 문자열로 굳어 들어온 스냅샷도 있다."""
    if isinstance(v, list):
        return [str(x) for x in v if x]
    if isinstance(v, str) and v.strip():
        s = v.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s.replace("'", '"'))
                if isinstance(parsed, list):
                    return [str(x) for x in parsed if x]
            except Exception:
                pass
        return [s]
    return []


def clean(text: Any, limit: int | None = None) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    s = _CODE_FENCE.sub(" ", s)
    s = _MD_IMAGE.sub("", s)
    s = _MD_LINK.sub(r"\1", s)
    s = _WS.sub(" ", s)
    s = _BLANKS.sub("\n\n", s)
    s = s.strip()
    if limit and len(s) > limit:
        s = s[:limit].rstrip() + "…"
    return s


def job_embed_text(job: dict) -> str:
    """공고 임베딩 입력. 복지/전체 JD 원문은 뺀다 — 변별력 대비 길이만 늘린다."""
    tech = ", ".join(as_list(job.get("tech_stack")))
    head = [job.get("title") or ""]
    facts = [job.get("company"), job.get("career"), job.get("location")]
    head.append(" | ".join(f for f in facts if f))
    if tech:
        head.append(f"기술스택: {tech}")
    parts = [p for p in head if p.strip()]
    for label, key in (
        ("주요업무", "main_tasks"),
        ("자격요건", "qualifications"),
        ("우대사항", "preferences"),
    ):
        body = clean(job.get(key), SECTION_CHARS)
        if body:
            parts.append(f"[{label}]\n{body}")
    return clean("\n".join(parts), MAX_EMBED_CHARS)


def post_embed_text(post: dict, content: str | None) -> str:
    """블로그 글 임베딩 입력. 번역본(content_ko)이 있으면 그쪽을 우선한다."""
    parts = [post.get("title") or ""]
    facts = [post.get("company"), post.get("country")]
    tags = as_list(post.get("tech_stack")) + as_list(post.get("categories"))
    if tags:
        facts.append(", ".join(dict.fromkeys(tags)))
    joined = " | ".join(f for f in facts if f)
    if joined:
        parts.append(joined)
    summary = clean(post.get("summary"), SECTION_CHARS)
    if summary:
        parts.append(summary)
    if content:
        parts.append(clean(content, MAX_EMBED_CHARS))
    return clean("\n".join(p for p in parts if p.strip()), MAX_EMBED_CHARS)
