"""회사 조사 결과 — 포스터가 그 회사답게 보이도록 쓰는 색·한 줄 소개·공개 수치·모티프.

    brands/<회사>.json     names(별칭) / about / facts / stats / palette / motif / sources

없는 회사는 None 이고 포스터는 직군 계열 팔레트로 그린다. 수치는 반드시 sources 에서
확인한 것만 적는다 — 포스터에 박힌 숫자는 그 회사의 주장으로 읽힌다.
"""
from __future__ import annotations

import json
from pathlib import Path

from .assets import slug

BRANDS = Path(__file__).resolve().parent.parent / "brands"


def find(company: str) -> dict | None:
    want = slug(company).lower()
    for path in sorted(BRANDS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if want in {slug(n).lower() for n in [path.stem, *data.get("names", [])]}:
            return data
    return None
