"""임베딩 입력 텍스트 생성 — 저장소에 의존하지 않는다.

이 텍스트가 바뀌면 content_hash 가 바뀌어 다음 회차에 전량 재임베딩된다 — 규칙을
고칠 때는 그 비용(맥에서 한 시간 넘게)을 각오한다. 임베딩(store/vectors/embed.py)과
글 적재(store/ingest/posts.py)가 이 한 곳을 같이 쓴다.
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
