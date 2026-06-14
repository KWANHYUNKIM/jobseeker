#!/usr/bin/env python3
"""기술 관계/맥락 빌더 — 개발 트렌드의 '세부' 층.

채용 공고의 tech_stack 동시출현을 계산해 '어떤 기술이 어떤 기술과 함께(파생되어) 쓰이는지'를
스택 레이어(언어/프레임워크/DB/인프라 등)와 함께 보여준다. 기술의 '맥락·이유'(예: 웹에서
Python·Java를 많이 쓰는 이유, Java가 금융권에 많은 이유)는 LLM(build_company_tech_radar 와
유사한 claude CLI)로 채우는 context 슬롯을 둔다 — 여기서는 데이터 부분(동시출현·레이어)을 만든다.

출력: public/tech_relations.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "public" / "all_jobs_enriched.json"
OUT = ROOT / "public" / "tech_relations.json"
CATCH = ROOT.parent / "catch_capture"

# 기술 → 레이어(언어/프론트엔드/백엔드/DB/인프라/임베디드 …). tech_taxonomy 가 단일 소스.
sys.path.insert(0, str(CATCH))
try:
    from crawlers.tech_taxonomy import CATEGORY_OF  # type: ignore
except Exception:
    CATEGORY_OF = {}


def layer_of(tech: str) -> str:
    return CATEGORY_OF.get(tech, "기타")


TOP_N = 60          # 관계를 만들 상위 기술 수
RELATED_N = 12      # 기술당 함께 쓰이는 상위 기술 수


def main() -> None:
    jobs = json.loads(SRC.read_text(encoding="utf-8"))
    # 기술 출현 수 + 동시출현
    count = Counter()
    stacks = []
    for j in jobs:
        ts = {t for t in (j.get("tech_stack") or []) if t}
        if ts:
            stacks.append(ts)
            count.update(ts)

    top = [t for t, _ in count.most_common(TOP_N)]
    topset = set(top)
    co: dict[str, Counter] = {t: Counter() for t in top}
    for ts in stacks:
        present = [t for t in ts if t in topset]
        for t in present:
            for x in ts:
                if x != t:
                    co[t][x] += 1

    techs = []
    for t in top:
        base = count[t]
        related = []
        for name, n in co[t].most_common(RELATED_N):
            related.append({
                "name": name,
                "layer": layer_of(name),
                "count": n,
                "pct": round(100 * n / base, 1) if base else 0.0,  # 이 기술 공고 중 함께 쓰인 비율
            })
        techs.append({
            "name": t,
            "layer": layer_of(t),
            "count": base,
            "pct_jobs": round(100 * base / len(jobs), 1),
            "related": related,
            "context": None,   # LLM 채움: 어디서·왜 쓰이는지(마크다운)
        })

    # LLM 으로 채운 context/domains 는 매 사이클 재집계 시에도 보존(동시출현만 갱신).
    prev_ctx: dict[str, str] = {}
    prev_domains = []
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
            prev_ctx = {t["name"]: t.get("context") for t in old.get("techs", []) if t.get("context")}
            prev_domains = old.get("domains", [])
        except Exception:
            pass
    for t in techs:
        if t["name"] in prev_ctx:
            t["context"] = prev_ctx[t["name"]]

    doc = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "total_jobs": len(jobs),
        "techs": techs,
        "domains": prev_domains,   # LLM 채움: 도메인별 인사이트(보존)
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"[relations] 상위 {len(techs)}개 기술 동시출현 → {OUT}")
    for t in techs[:4]:
        rel = ", ".join(f"{r['name']}({r['pct']}%)" for r in t["related"][:5])
        print(f"  {t['name']}[{t['layer']}] {t['pct_jobs']}% · 함께: {rel}")


if __name__ == "__main__":
    main()
