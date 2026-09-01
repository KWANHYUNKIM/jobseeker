#!/usr/bin/env python3
"""회사별 규모(대/중견/중소) 색인을 만든다 → public/company_meta.json

뷰어의 잡 리스트에서 "기업 규모"로 거르려면 공고마다 회사 규모를 알아야 한다.
company_stacks.json 에도 size 가 있지만 그 파일은 공고 2건 이상인 회사만 담고(17MB),
목록 화면이 규모 하나 보자고 통째로 읽을 파일이 아니다. 그래서 규모만 담은 얇은
색인을 따로 낸다 — 공고 1건짜리 회사까지 포함한다.

규모 판정 규칙의 소유자는 dashboard/classifier 하나다(화이트리스트 + 공고 본문의
사원수·매출액). 여기서는 그 함수를 부르기만 한다.

사용:
  python3 build_company_meta.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ENRICHED = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
OUTPUT = ROOT / "jd-viewer" / "public" / "company_meta.json"

sys.path.insert(0, str(ROOT / "catch_capture"))
from dashboard.classifier import (  # noqa: E402
    _norm_company,
    classify_company_size,
    extract_headcount,
    extract_revenue_eok,
)


def main() -> None:
    jobs = json.loads(ENRICHED.read_text(encoding="utf-8"))

    by_norm: dict[str, list[dict]] = defaultdict(list)
    name_votes: dict[str, Counter] = defaultdict(Counter)
    for j in jobs:
        name = (j.get("company") or "").strip()
        nk = _norm_company(name)
        if not nk:
            continue
        by_norm[nk].append(j)
        name_votes[nk][name] += 1

    # 키는 공고에 적힌 회사 이름 원문 그대로 둔다. 정규화 키로 내보내면 뷰어가
    # 같은 정규화 규칙을 TypeScript 로 한 벌 더 들고 있어야 하고, 그 두 벌은 반드시
    # 어긋난다. 이름 표기가 여럿이면 각 표기가 같은 규모를 가리키게 여러 줄로 낸다.
    sizes: dict[str, str] = {}
    for nk, group in by_norm.items():
        display = name_votes[nk].most_common(1)[0][0]
        hc_max: int | None = None
        rev_max: float | None = None
        for j in group:
            # 규모 신호는 공고 본문 전체에서 뽑는다 — 기업정보 표가 JD 뒤쪽에 붙는다.
            text = " ".join([
                j.get("full_jd") or "", j.get("benefits") or "",
                j.get("qualifications") or "", j.get("preferences") or "",
            ])
            hc = extract_headcount(text)
            if hc and (hc_max is None or hc > hc_max):
                hc_max = hc
            rev = extract_revenue_eok(text)
            if rev and (rev_max is None or rev > rev_max):
                rev_max = rev
        size, _alias = classify_company_size(display, hc_max, rev_max)
        for raw in name_votes[nk]:
            sizes[raw] = size

    counts = Counter(sizes.values())
    OUTPUT.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "company_count": len(by_norm),
                "sizes": sizes,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(sizes)} companies ({dict(counts)}) -> {OUTPUT}")


if __name__ == "__main__":
    main()
