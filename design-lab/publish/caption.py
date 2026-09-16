"""캡션 — 같은 공고라도 플랫폼마다 읽는 태도가 다르다.

  인스타: 첫 두 줄에서 승부가 난다. 링크가 안 걸리니 '프로필 링크' 로 넘긴다. 해시태그 다수.
  링크드인: 문장으로 읽는다. 링크가 걸리고, 해시태그는 서너 개면 충분하다.
  페이스북: 그 중간. 링크 미리보기가 붙으므로 본문은 짧게.
포스터에 이미 박힌 문장을 캡션에 또 쓰지 않는다(직군·회사는 짧게만 반복).
"""
from __future__ import annotations

import re

_TAG_CLEAN = re.compile(r"[^0-9A-Za-z가-힣]+")

BASE_TAGS = ["개발자채용", "채용공고", "IT채용", "경력직채용"]


def hashtags(spec: dict, limit: int = 12) -> list[str]:
    tags = []
    for t in spec.get("stack", []):
        t = _TAG_CLEAN.sub("", t)
        if 1 < len(t) <= 18:
            tags.append(t)
    family = {"backend": "백엔드개발자", "frontend": "프론트엔드개발자", "data": "데이터엔지니어",
              "infra": "데브옵스", "mobile": "앱개발자"}.get(spec.get("family", ""), "")
    if family:
        tags.append(family)
    for t in BASE_TAGS:
        if t not in tags:
            tags.append(t)
    out, seen = [], set()
    for t in tags:
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out[:limit]


def _lines(spec: dict) -> list[str]:
    """캡션 본문에 쓸 항목 — 포스터에 안 들어간 것 위주로."""
    out = []
    for label, key, n in (("담당업무", "tasks", 2), ("지원자격", "qualifications", 2),
                          ("우대사항", "preferences", 1)):
        items = spec.get(key) or []
        for item in items[:n]:
            out.append(f"· [{label}] {item}")
    return out


def build(spec: dict, platform: str) -> str:
    role, company = spec.get("role", ""), spec.get("company", "")
    deadline = spec.get("deadline", "")
    meta = " · ".join(spec.get("meta", []))
    tags = hashtags(spec)

    if platform == "instagram":
        head = f"{company} — {role}"
        sub = " / ".join(x for x in (meta, deadline) if x)
        body = "\n".join(_lines(spec)[:4])
        # 채용 사이트 주소는 캡션에도 적지 않는다(판과 같은 이유 — poster/carousel.py compose 주석).
        tail = "지원 안내는 프로필 링크에서 볼 수 있어요."
        tagline = " ".join(f"#{t}" for t in tags)
        return "\n\n".join(x for x in (head, sub, body, tail, tagline) if x)

    if platform == "linkedin":
        head = f"{company}에서 {role}를 찾습니다."
        sub = " · ".join(x for x in (meta, deadline) if x)
        body = "\n".join(_lines(spec))
        tagline = " ".join(f"#{t}" for t in tags[:4])
        return "\n\n".join(x for x in (head, sub, body, tagline) if x)

    # facebook: 링크 미리보기가 붙으니 본문은 짧게
    head = f"{company} · {role}"
    sub = " / ".join(x for x in (meta, deadline) if x)
    body = "\n".join(_lines(spec)[:3])
    tagline = " ".join(f"#{t}" for t in tags[:6])
    return "\n\n".join(x for x in (head, sub, body, tagline) if x)


def preview(spec: dict) -> dict:
    return {p: build(spec, p) for p in ("instagram", "facebook", "linkedin")}


#: 묶음 카테고리 → 캡션 해시태그에 얹을 말
COLLECTION_TAGS = {
    "week": ["이번주채용", "채용속보"], "deadline": ["마감임박", "지원마감"],
    "role": ["직군별채용"], "size": ["대기업채용"], "stack": ["기술스택"],
    "newgrad": ["신입채용", "신입개발자"],
}


def build_collection(col: dict, platform: str) -> str:
    """묶음 캡션 — 표지에 있는 목록을 글로도 준다(검색·저장은 글에서 걸린다).

    표지 이미지를 못 읽는 사람(스크린 리더·미리보기)도 어디가 들어 있는지 알게 회사 이름을
    본문에 그대로 쓴다. 공고 주소는 넣지 않는다(판과 같은 규칙).
    """
    head = f"{col['kicker']} · {col['title']}"
    lines = [f"{i:02d}. {j['company']} — {j['role']}"
             + (f" ({j['career'].replace('경력 ', '')})" if j.get("career") else "")
             for i, j in enumerate(col.get("jobs") or [], 1)]

    stacks: list[str] = []
    for j in col.get("jobs") or []:
        for s in j.get("stack") or []:
            t = _TAG_CLEAN.sub("", s)
            if 1 < len(t) <= 18 and t not in stacks:
                stacks.append(t)
    tags = COLLECTION_TAGS.get(col.get("kind", ""), []) + stacks[:5] + BASE_TAGS
    seen, out = set(), []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)

    if platform == "instagram":
        # 릴스에서는 넘기는 사람이 없다 — 장면이 알아서 지나간다. 표지 문구
        # (collection_cover/hook)와 같은 규칙을 캡션에도 적용한다. 한쪽만 고치면
        # 판은 "이어서 나옵니다" 라는데 캡션은 "넘겨서 보세요" 라고 말하게 된다.
        tail = ("각 회사 공고 전문이 영상에 이어서 나옵니다. 지원 안내는 프로필 링크에서."
                if col.get("shape") == "reel" else
                "각 회사 공고 전문은 넘겨서 보세요. 지원 안내는 프로필 링크에서.")
        return "\n\n".join([head, f"{col['count']}곳", "\n".join(lines), tail,
                            " ".join(f"#{t}" for t in out[:12])])
    if platform == "linkedin":
        return "\n\n".join([f"{head} — {col['count']}곳", "\n".join(lines),
                            " ".join(f"#{t}" for t in out[:4])])
    return "\n\n".join([f"{head} — {col['count']}곳", "\n".join(lines),
                        " ".join(f"#{t}" for t in out[:6])])
