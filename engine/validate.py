#!/usr/bin/env python3
"""역설계 산출물 검증 — 사이트가 읽기 전에 형식이 깨졌는지 본다.

index.json 은 공개 사이트 메인이 통째로 읽는다. 한 글자 깨지면 회사 목록이 아니라
빈 화면이 뜨므로, 엔진이 매 사이클 끝에 이걸 돌린다.

    python engine/validate.py            # 전체 검사
    python engine/validate.py toss       # 회사 하나만

검사하는 것:
  - JSON 파싱, 필수 필드, enum 값(country/category/status/confidence)
  - index.companies 와 companies/*.json 의 불일치(누락·고아·필드 어긋남)
  - confidence=confirmed 인데 sources 가 비어 있는 주장 (PROMPT.md 5단계 규칙)
  - decisions 의 tradeoff 누락 (품질 규칙: 트레이드오프 없는 설명 금지)
  - connections 가 가리키는 feature key 가 실재하는지
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVENG = ROOT / "jd-viewer" / "public" / "reveng"
INDEX = REVENG / "index.json"
COMPANIES = REVENG / "companies"

COUNTRIES = {"KR", "US", "CN", "JP", "EU", "CA", "기타"}
CATEGORIES = {"핀테크", "커머스", "소셜", "메시징", "스트리밍", "검색",
              "모빌리티", "게임", "SaaS", "기타"}
STATUSES = {"in_progress", "done"}
CONFIDENCE = {"confirmed", "inferred", "unknown"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# index.companies[] 가 회사 파일과 일치해야 하는 필드. 사이트 메인이 이 값만 보고
# 카드를 그리므로, 상세와 어긋나면 목록과 상세가 다른 말을 하게 된다.
MIRRORED = ("name", "name_en", "country", "category", "status", "updated_at")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


def _load(path: Path, r: Report) -> dict | None:
    if not path.exists():
        r.err(str(path.relative_to(ROOT)), "파일 없음")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        r.err(str(path.relative_to(ROOT)), f"JSON 파싱 실패 — {e}")
        return None


def _check_sources(node: dict, where: str, r: Report) -> None:
    """confirmed 주장에는 링크가 반드시 있어야 한다(PROMPT.md 5단계)."""
    conf = node.get("confidence")
    if conf is not None and conf not in CONFIDENCE:
        r.err(where, f"confidence 값이 이상하다: {conf!r}")
    if conf == "confirmed" and not node.get("sources"):
        r.err(where, "confirmed 인데 sources 가 비어 있다")
    for i, s in enumerate(node.get("sources") or []):
        if not s.get("url"):
            r.err(f"{where}.sources[{i}]", "url 없음")
        if not s.get("summary"):
            r.warn(f"{where}.sources[{i}]", "한 줄 요약 없음")


def check_company(data: dict, r: Report) -> None:
    slug = data.get("slug", "?")
    w = f"companies/{slug}.json"

    for f in ("slug", "name", "name_en", "country", "category", "status",
              "updated_at", "business_model", "products", "one_liner"):
        if not data.get(f):
            r.err(w, f"필수 필드 없음: {f}")
    if not SLUG_RE.match(str(data.get("slug", ""))):
        r.err(w, f"slug 형식 위반(영문 소문자·숫자·하이픈): {data.get('slug')!r}")
    if data.get("country") not in COUNTRIES:
        r.err(w, f"country 값이 이상하다: {data.get('country')!r}")
    if data.get("category") not in CATEGORIES:
        r.err(w, f"category 값이 이상하다: {data.get('category')!r}")
    if data.get("status") not in STATUSES:
        r.err(w, f"status 값이 이상하다: {data.get('status')!r}")
    if not DATE_RE.match(str(data.get("updated_at", ""))):
        r.err(w, f"updated_at 형식(YYYY-MM-DD) 위반: {data.get('updated_at')!r}")

    for i, rs in enumerate(data.get("revenue_streams") or []):
        _check_sources(rs, f"{w}.revenue_streams[{i}]", r)

    domain_names = {d.get("name") for d in (data.get("domains") or [])}
    if not domain_names:
        r.warn(w, "domains 가 비어 있다 — 3단계(회사 프로파일)가 아직 안 끝났다")

    keys: set[str] = set()
    for i, feat in enumerate(data.get("features") or []):
        fw = f"{w}.features[{feat.get('key', i)}]"
        key = feat.get("key")
        if not key or not SLUG_RE.match(str(key)):
            r.err(fw, f"key 형식 위반: {key!r}")
        elif key in keys:
            r.err(fw, f"key 중복: {key}")
        else:
            keys.add(key)
        if feat.get("domain") not in domain_names:
            r.err(fw, f"domains 에 없는 도메인: {feat.get('domain')!r}")
        if not (feat.get("business") or {}).get("why"):
            r.err(fw, "business.why 없음 — 왜 존재하는 기능인지가 이 데이터의 핵심이다")

        for j, m in enumerate((feat.get("business") or {}).get("metrics") or []):
            _check_sources(m, f"{fw}.business.metrics[{j}]", r)

        impl = feat.get("implementation") or {}
        if not impl.get("flow"):
            r.warn(fw, "implementation.flow 가 비어 있다")
        decisions = impl.get("decisions") or []
        if not decisions:
            r.err(fw, "decisions 없음 — 의사결정 없는 기술 나열은 이 엔진의 산출물이 아니다")
        for j, d in enumerate(decisions):
            dw = f"{fw}.decisions[{j}]"
            if not d.get("tradeoff"):
                r.err(dw, "tradeoff 없음 (품질 규칙: 트레이드오프 없는 설명 금지)")
            _check_sources(d, dw, r)
        for j, s in enumerate(impl.get("stack") or []):
            sw = f"{fw}.stack[{j}]"
            if not s.get("role"):
                r.err(sw, "role 없음 — 기술 이름만 나열하지 않는다")
            _check_sources(s, sw, r)

        _check_sources(feat, fw, r)

    # 연결이 실재하는 기능을 가리키는지. 오타 하나로 그래프가 끊긴다.
    for feat in data.get("features") or []:
        for c in feat.get("connections") or []:
            to = c.get("to")
            if to in keys or to is None:
                continue
            if not c.get("via"):
                r.err(f"{w}.features[{feat.get('key')}].connections", f"via 없음 (to={to!r})")
            # 외부 시스템이면 feature key 가 아니어도 된다 — 경고로만 남긴다.
            if SLUG_RE.match(str(to)) and to not in keys:
                r.warn(f"{w}.features[{feat.get('key')}].connections",
                       f"feature key 처럼 생겼는데 그런 기능이 없다: {to!r}")


def check_index(index: dict, companies: dict[str, dict], r: Report) -> None:
    w = "index.json"
    if not DATE_RE.match(str(index.get("updated_at", ""))):
        r.err(w, f"updated_at 형식(YYYY-MM-DD) 위반: {index.get('updated_at')!r}")
    if not isinstance(index.get("countries"), dict) or not index["countries"]:
        r.err(w, "countries 맵이 없다 — 사이트가 국가 필터를 못 그린다")

    listed = set()
    for i, c in enumerate(index.get("companies") or []):
        slug = c.get("slug")
        cw = f"{w}.companies[{slug or i}]"
        if not slug:
            r.err(cw, "slug 없음")
            continue
        listed.add(slug)
        if not c.get("one_liner"):
            r.err(cw, "one_liner 없음 — 디렉토리 카드가 빈 칸이 된다")
        if not isinstance(c.get("features_done"), int):
            r.err(cw, f"features_done 이 정수가 아니다: {c.get('features_done')!r}")
        full = companies.get(slug)
        if full is None:
            r.err(cw, f"목록에 있는데 companies/{slug}.json 이 없다")
            continue
        for f in MIRRORED:
            if c.get(f) != full.get(f):
                r.err(cw, f"{f} 가 상세와 다르다: {c.get(f)!r} vs {full.get(f)!r}")
        n = len(full.get("features") or [])
        if c.get("features_done") != n:
            r.err(cw, f"features_done={c.get('features_done')} 인데 상세엔 {n}개")

    for slug in companies:
        if slug not in listed:
            r.err(w, f"companies/{slug}.json 이 index 에 없다 — 사이트에 안 뜬다")

    known = {d.get("name") for c in companies.values() for d in (c.get("domains") or [])}
    missing = known - set(index.get("domains") or [])
    if missing:
        r.err(w, f"domains 배열에 빠진 도메인: {sorted(missing)}")


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    r = Report()

    companies: dict[str, dict] = {}
    for path in sorted(COMPANIES.glob("*.json")):
        if only and path.stem != only:
            continue
        data = _load(path, r)
        if data is None:
            continue
        companies[path.stem] = data
        if data.get("slug") != path.stem:
            r.err(f"companies/{path.name}", f"파일명과 slug 불일치: {data.get('slug')!r}")
        check_company(data, r)

    index = _load(INDEX, r)
    if index is not None and not only:
        check_index(index, companies, r)

    for line in r.warnings:
        print(f"  ! {line}")
    for line in r.errors:
        print(f"  ✗ {line}")
    n = len(companies)
    if r.errors:
        print(f"\n실패 — 회사 {n}개 · 오류 {len(r.errors)}건 · 경고 {len(r.warnings)}건")
        return 1
    print(f"\n통과 — 회사 {n}개 · 경고 {len(r.warnings)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
