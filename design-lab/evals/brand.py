"""회사 전용 판의 규칙 검사 — brands/<회사>.json 만 보고 판정한다.

회사 전용 판이 brand-poster 스킬의 규칙대로 만들어졌는지 본다. 규칙의 설명과 이유는
.claude/skills/brand-poster/ (각 검사의 ref 가 가리키는 절). 실패가 있으면 렌더하지 않는다.

    python -m evals.brand              # 전 회사
    python -m evals.brand 토스 컬리    # 몇 곳만
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
BRANDS = LAB_DIR / "brands"
MEDIUM_AXES = ("ground", "text_load", "hand")
IMAGE_MAX = 600 * 1024


def _sig(data: dict) -> dict:
    return data.get("signature") or {}


def points_max_2(name, data, others):
    n = len(data.get("points") or [])
    return n <= 2, f"{n}개"


def signature_evidence_url(name, data, others):
    ev = _sig(data).get("evidence") or []
    urls = [e for e in ev if "http" in str(e)]
    return bool(urls), f"근거 {len(ev)}개 중 주소 {len(urls)}개"


def signature_alternatives(name, data, others):
    alts = _sig(data).get("alternatives") or []
    reasoned = [a for a in alts if isinstance(a, dict) and a.get("why_not")]
    return bool(alts) and len(reasoned) == len(alts), f"후보 {len(alts)}개, 이유 {len(reasoned)}개"


def medium_unique(name, data, others):
    m = _sig(data).get("medium") or {}
    axes = tuple(m.get(k) for k in MEDIUM_AXES)
    if not all(axes):
        return False, "매체 세 칸이 비었다"
    same = [o for o, ax in others.items() if o != name and ax == axes]
    return not same, " · ".join(axes) + (f" — {', '.join(same)} 와 같다" if same else "")


def medium_chosen(name, data, others):
    """매체는 시그니처에서 고른다. 지금 판을 보고 적은 것(observed)은 '이렇다' 이지 '이래야 한다' 가 아니다."""
    m = _sig(data).get("medium") or {}
    if not m:
        return False, "매체 없음"
    return not m.get("observed"), ("렌더를 보고 적은 값 — 시그니처에서 다시 고른다" if m.get("observed") else "골랐다")


def cover_not_full(name, data, others):
    """표지에 공고 전문을 싣지 않는다 — full 이면 시그니처가 귀퉁이로 밀려 모든 판이 같은 문서가 된다."""
    load = (_sig(data).get("medium") or {}).get("text_load")
    return load in ("one-line", "one-word", "few"), f"text_load={load}"


def images_600kb(name, data, others):
    imgs = (data.get("ui") or {}).get("images") or data.get("images") or {}
    paths = imgs.values() if isinstance(imgs, dict) else imgs
    big = []
    for p in paths:
        f = LAB_DIR / str(p)
        if f.is_file() and f.stat().st_size > IMAGE_MAX:
            big.append(f"{f.name} {f.stat().st_size // 1024}KB")
    return not big, ", ".join(big) or "모두 600KB 이하"


#: id → 검사 · 규칙 · 스킬의 어느 절인가. 규칙을 더할 때는 tests/test_brand_checks.py 부터(RED → GREEN).
CHECKS = {
    "points-max-2": {"fn": points_max_2, "rule": "보조 포인트는 둘 이하 — 더 넣으면 다시 장식이 된다",
                     "ref": "references/signature.md 3절"},
    "signature-evidence-url": {"fn": signature_evidence_url, "rule": "시그니처 근거에 공식 주소가 있다",
                               "ref": "references/signature.md 2절 '공식이다'"},
    "signature-alternatives": {"fn": signature_alternatives, "rule": "탈락한 후보와 그 이유를 남긴다",
                               "ref": "references/signature.md 2절 '하나만 고른다'"},
    "medium-unique": {"fn": medium_unique, "rule": "매체(바탕·글 양·손) 세 칸이 다른 회사와 같으면 같은 판이다",
                      "ref": "references/signature.md 2-1절"},
    "medium-chosen": {"fn": medium_chosen, "rule": "매체는 시그니처에서 고른다(지금 판을 보고 적은 값은 통과가 아니다)",
                      "ref": "references/signature.md 2-1절"},
    "cover-not-full": {"fn": cover_not_full, "rule": "표지는 한 줄·한 단어 — 전문은 본문 장(full 갈래)으로",
                       "ref": "references/signature.md 2-1절 · history.md 2026-10-19"},
    "images-600kb": {"fn": images_600kb, "rule": "판에 넣는 이미지는 장당 600KB 이하",
                     "ref": "references/color-image.md 6절"},
}


def mediums() -> dict[str, tuple]:
    out = {}
    for p in sorted(BRANDS.glob("*.json")):
        m = _sig(json.loads(p.read_text(encoding="utf-8"))).get("medium") or {}
        out[p.stem] = tuple(m.get(k) for k in MEDIUM_AXES)
    return out


def run(name: str, data: dict, others: dict) -> list[dict]:
    out = []
    for cid, c in CHECKS.items():
        ok, detail = c["fn"](name, data, others)
        out.append({"id": cid, "ok": bool(ok), "detail": detail, "rule": c["rule"], "ref": c["ref"]})
    return out


def by_id(name: str, data: dict, cid: str, others: dict) -> dict:
    return next(r for r in run(name, data, others) if r["id"] == cid)


def main(argv: list[str]) -> int:
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    others = mediums()
    names = argv or list(others)
    bad = 0
    for n in names:
        rs = run(n, json.loads((BRANDS / f"{n}.json").read_text(encoding="utf-8")), others)
        fails = [r for r in rs if not r["ok"]]
        bad += len(fails)
        print(f"{n}: {len(rs) - len(fails)}/{len(rs)}" + ("" if fails else " 통과"))
        for r in fails:
            print(f"   실패  {r['id']:<24} {r['detail']}  — {r['rule']} ({r['ref']})")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
