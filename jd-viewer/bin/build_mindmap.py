#!/usr/bin/env python3
"""기업 기술스택·잡 리스트 기반 커리어 마인드맵 (markmap markdown) 생성기.

입력: jd-viewer/public/all_jobs_enriched.json
출력: jd-viewer/public/mindmap.md  (markmap-lib 호환 markdown)

구조:  도메인 → 기업 → 직군 → (실관측 스택 + 실제 공고 링크)
모든 노드가 실제 크롤링 데이터(기업/직군/스택/공고)에서 나온다.
큐레이션 텍스트는 쓰지 않는다 — "현실감" 우선.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "catch_capture" / "dashboard"))
sys.path.insert(0, str(BIN))
from classifier import classify_company_size, classify_dev_roles, _norm_company  # noqa: E402
from build_company_stacks import canon_tech, infer_domains  # noqa: E402

INPUT = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
OUTPUT = ROOT / "jd-viewer" / "public" / "mindmap.md"
OUTPUT_TREE = ROOT / "jd-viewer" / "public" / "mindmap_tree.json"

MIN_POSTING = 2          # 공고 N건 이상인 기업만 (company_stacks 탭과 일치)
TOP_TECH_PER_ROLE = 6    # 직군 노드 옆에 인라인으로 붙일 스택 수
MAX_POSTINGS_PER_ROLE = 4
DOMAIN_FALLBACK = "기타/미상"

ROLE_ORDER = [
    "백엔드", "프론트엔드", "풀스택", "모바일", "AI/ML", "데이터",
    "DevOps/인프라", "펌웨어/임베디드", "보안", "게임", "QA",
]
ROLE_RANK = {r: i for i, r in enumerate(ROLE_ORDER)}


def md_inline(s: str) -> str:
    return s.replace("\n", " ").replace("[", "(").replace("]", ")").strip()


def build_companies(jobs: list[dict]) -> list[dict]:
    """회사별로 묶어 직군→스택→공고 까지 집계."""
    by_norm: dict[str, list[dict]] = defaultdict(list)
    name_votes: dict[str, Counter] = defaultdict(Counter)
    for j in jobs:
        name = (j.get("company") or "").strip()
        if not name:
            continue
        nk = _norm_company(name)
        if not nk:
            continue
        by_norm[nk].append(j)
        name_votes[nk][name] += 1

    companies: list[dict] = []
    for nk, group in by_norm.items():
        if len(group) < MIN_POSTING:
            continue
        display = name_votes[nk].most_common(1)[0][0]
        size, _alias = classify_company_size(display)

        # 직군별 스택/공고 집계
        role_tech: dict[str, Counter] = defaultdict(Counter)
        role_postings: dict[str, list[dict]] = defaultdict(list)
        role_count: Counter = Counter()
        text_parts: list[str] = []

        for j in group:
            text_parts.append(" ".join([
                j.get("title") or "", j.get("main_tasks") or "",
                j.get("qualifications") or "", j.get("preferences") or "",
                (j.get("full_jd") or "")[:1500],
            ]))
            roles = classify_dev_roles(
                title=j.get("title") or "",
                tech_stack=j.get("tech_stack") or [],
                extra_text=(j.get("qualifications") or "")[:500],
            )
            roles = [r for r in roles if r != "기타"] or ["기타"]
            canon: list[str] = []
            seen: set[str] = set()
            for t in j.get("tech_stack") or []:
                ct = canon_tech(t)
                if ct is None or ct[0] in seen:
                    continue
                seen.add(ct[0])
                canon.append(ct[0])
            posting = {
                "title": j.get("title") or "",
                "url": j.get("url") or "",
                "site": j.get("site") or "",
            }
            for r in roles:
                role_count[r] += 1
                for c in canon:
                    role_tech[r][c] += 1
                if posting["url"]:
                    role_postings[r].append(posting)

        domains = infer_domains("\n".join(text_parts), top=1)
        domain = domains[0]["name"] if domains else DOMAIN_FALLBACK

        # 직군 정렬: 표준 순서 → 공고수
        roles_sorted = sorted(
            role_count.keys(),
            key=lambda r: (ROLE_RANK.get(r, 99), -role_count[r]),
        )
        companies.append({
            "name": display,
            "size": size,
            "domain": domain,
            "posting_count": len(group),
            "roles": roles_sorted,
            "role_count": role_count,
            "role_tech": role_tech,
            "role_postings": role_postings,
        })

    companies.sort(key=lambda c: -c["posting_count"])
    return companies


def render_md(companies: list[dict], total_jobs: int) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 도메인별 그룹화
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for c in companies:
        by_domain[c["domain"]].append(c)
    # 도메인 정렬: 기업 수 많은 순 (미상은 맨 뒤)
    domain_order = sorted(
        by_domain.keys(),
        key=lambda d: (d == DOMAIN_FALLBACK, -len(by_domain[d])),
    )

    lines: list[str] = []
    lines.append("---")
    lines.append("markmap:")
    lines.append("  colorFreezeLevel: 2")
    lines.append("  maxWidth: 340")
    lines.append("  initialExpandLevel: 1")
    lines.append("---")
    lines.append("")
    lines.append("# 채용 기업 맵 · 실데이터")
    lines.append("")
    # 개요 (버튼에서 제외하기 위해 📊 prefix)
    lines.append("## 📊 데이터 개요")
    lines.append(f"- 총 **{total_jobs}건** 공고 · **{len(companies)}개 기업** · {len(domain_order)}개 도메인")
    lines.append(f"- 공고 {MIN_POSTING}건 이상 채용 기업만 · 생성 {now}")
    lines.append("- 도메인 → 기업 → 직군 → 스택·공고 (전부 실제 크롤링 데이터)")
    lines.append("- 직군 옆 `코드`는 그 회사·직군 공고에서 실제 관측된 스택")
    lines.append("")

    for domain in domain_order:
        comps = by_domain[domain]
        lines.append(f"## {md_inline(domain)} ({len(comps)}개사)")
        for c in comps:
            lines.append(f"### {md_inline(c['name'])} `{c['size']}` · {c['posting_count']}건")
            display_roles = [r for r in c["roles"] if r != "기타"] or c["roles"]
            for role in display_roles:
                if role == "기타":
                    continue
                n = c["role_count"][role]
                techs = [t for t, _ in c["role_tech"][role].most_common(TOP_TECH_PER_ROLE)]
                chips = " ".join(f"`{md_inline(t)}`" for t in techs)
                head = f"- **{role}** [{n}건]"
                if chips:
                    head += f" · {chips}"
                lines.append(head)
                # 공고 링크 (중복 url 제거)
                seen_urls: set[str] = set()
                shown = 0
                for p in c["role_postings"][role]:
                    if p["url"] in seen_urls:
                        continue
                    seen_urls.add(p["url"])
                    title = md_inline(p["title"]) or "(제목없음)"
                    lines.append(f"  - [{title} ↗]({p['url']})")
                    shown += 1
                    if shown >= MAX_POSTINGS_PER_ROLE:
                        break
            lines.append("")
        lines.append("")

    return "\n".join(lines)


def build_tree(companies: list[dict], total_jobs: int) -> dict:
    """원형 클러스터(circle packing)용 계층 JSON.

    루트 → 도메인 → 기업 → 직군(leaf). leaf value = 그 직군 공고수.
    직군 노드에 tech/postings 를 실어 상세 패널에서 쓴다.
    """
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for c in companies:
        by_domain[c["domain"]].append(c)
    domain_order = sorted(
        by_domain.keys(),
        key=lambda d: (d == DOMAIN_FALLBACK, -len(by_domain[d])),
    )

    domain_nodes = []
    for domain in domain_order:
        comps = by_domain[domain]
        comp_nodes = []
        for c in comps:
            display_roles = [r for r in c["roles"] if r != "기타"]
            role_nodes = []
            for role in display_roles:
                n = c["role_count"][role]
                techs = [t for t, _ in c["role_tech"][role].most_common(8)]
                seen_urls: set[str] = set()
                postings = []
                for p in c["role_postings"][role]:
                    if p["url"] in seen_urls:
                        continue
                    seen_urls.add(p["url"])
                    postings.append(p)
                    if len(postings) >= 6:
                        break
                role_nodes.append({
                    "name": role,
                    "type": "role",
                    "value": n,
                    "company": c["name"],
                    "size": c["size"],
                    "domain": domain,
                    "tech": techs,
                    "postings": postings,
                })
            if not role_nodes:
                continue
            comp_nodes.append({
                "name": c["name"],
                "type": "company",
                "size": c["size"],
                "domain": domain,
                "postings_total": c["posting_count"],
                "children": role_nodes,
            })
        domain_nodes.append({
            "name": domain,
            "type": "domain",
            "company_count": len(comp_nodes),
            "children": comp_nodes,
        })

    return {
        "name": "채용 기업 맵",
        "type": "root",
        "total_jobs": total_jobs,
        "company_count": len(companies),
        "domain_count": len(domain_nodes),
        "children": domain_nodes,
    }


def main() -> None:
    if not INPUT.exists():
        print(f"[!] 입력 파일 없음: {INPUT}", file=sys.stderr)
        sys.exit(1)
    jobs = json.loads(INPUT.read_text(encoding="utf-8"))
    print(f"[*] 입력 {len(jobs)}건 로드", flush=True)
    companies = build_companies(jobs)
    print(f"[*] {len(companies)}개 기업 집계 (공고 {MIN_POSTING}건 이상)", flush=True)
    doms = Counter(c["domain"] for c in companies)
    for d, n in doms.most_common():
        print(f"    {d}: {n}개사", flush=True)
    md = render_md(companies, total_jobs=len(jobs))
    OUTPUT.write_text(md, encoding="utf-8")
    print(f"[*] {OUTPUT.relative_to(ROOT)} 작성 ({len(md):,} bytes)", flush=True)

    tree = build_tree(companies, total_jobs=len(jobs))
    tree_json = json.dumps(tree, ensure_ascii=False, separators=(",", ":"))
    OUTPUT_TREE.write_text(tree_json, encoding="utf-8")
    print(f"[*] {OUTPUT_TREE.relative_to(ROOT)} 작성 ({len(tree_json):,} bytes)", flush=True)


if __name__ == "__main__":
    main()
