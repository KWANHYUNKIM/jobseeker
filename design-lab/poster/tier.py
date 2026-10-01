"""[티어표] 한 장짜리 릴스 — 5~8초, 맨 위 칸은 가려 두고 댓글로 맞히게 한다(planning/02-format 2-2 'T').

  python -m poster.tier pay        # 신입 연봉 적어 둔 개발 공고 티어
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import series as S

#: 개발 직무로 보는 공고 제목 — 공고 사이트의 '개발' 분류는 기획·영업·컨설팅까지 섞여 들어온다
DEV_TITLE = re.compile(r"개발|엔지니어|engineer|developer|백엔드|프론트|풀스택|소프트웨어|\bSW\b|알고리즘|프로그래머|데브옵스|devops|클라우드", re.I)
#: 신입 정규 연봉으로 보면 안 되는 것 — 인턴 월급을 연봉으로 바꾸면 부풀려진다
NOT_TITLE = re.compile(r"인턴|전환형|영업|기획|\bPM\b|매니저|컨설턴트|consultant|마케팅|디자이너|교대근무", re.I)
TIERS = [("S", 5000, "5,000+"), ("A", 4500, "4,500+"), ("B", 4000, "4,000+"), ("C", 3500, "3,500+"), ("D", 3000, "3,000+"), ("E", 0, "3,000 미만")]


def newgrad_pay() -> tuple[list[tuple[dict, dict, int]], str]:
    """신입 연봉을 숫자로 적은 개발 공고 — 회사마다 가장 높은 공고 하나, 범위면 하한."""
    parse = S._parse_pay()
    allj = S._source()
    best: dict[str, tuple[dict, dict, int]] = {}
    for j in allj:
        if "신입" not in (j.get("career") or "") or S._not_dev(j):
            continue
        title = j.get("title") or ""
        if not DEV_TITLE.search(title) or NOT_TITLE.search(title):
            continue
        p = parse("\n".join(j.get(k) or "" for k in ("benefits", "full_jd")))
        if not p or re.search(r"\$|USD|달러|환율", p["text"]):
            continue
        if "신입" not in p["text"] and not re.fullmatch(r"\s*신입(/무관)?\s*", j.get("career") or ""):
            continue
        co = S._company(j)
        if co == S.NO_CO:
            continue
        low = p["low"]
        if co not in best or best[co][2] < low:
            best[co] = (j, p, low)
    return sorted(best.values(), key=lambda r: -r[2]), S._data_date(allj)


def build_pay() -> dict:
    rows, asof = newgrad_pay()
    n = len(rows)
    from .balance import _photo
    bg, _ = _photo("corporate.jpg")   # 흐린 바탕으로만 쓴다(사진 출처는 바탕이 흐려 판에 적지 않는다 — 캡션에)
    tiers, cap_lines = [], []
    for i, (g, lo, label) in enumerate(TIERS):
        hi = TIERS[i - 1][1] if i else 10 ** 9
        grp = [r for r in rows if lo <= r[2] < hi]
        if not grp:
            continue
        names = " · ".join(S._company(j) for j, _, _ in grp[:3]) + (f" 외 {len(grp) - 3}곳" if len(grp) > 3 else "")
        opened = sum(1 for j, _, _ in grp if j.get("status") == "active")
        note = f"{len(grp)}곳" + (f" · 지금 모집중 {opened}" if opened else "")
        tiers.append({"g": g, "range": label, "names": names, "note": note, "hide": g == "S"})
        cap_lines.append(f"{g} ({label}) — " + " · ".join(f"{S._company(j)} {m:,}" for j, _, m in grp))
    s_top = rows[0]
    slide = {"type": "mag", "image": bg, "tiers": tiers, "head": ["신입 개발자 연봉,", "**S티어는 어디?**"],
             "sub": f"공고에 신입 연봉을 숫자로 적은 {n}곳 · 만원",
             "foot": f"@devjobseeker 수집 개발 공고(마감 포함) · 회사마다 가장 높은 공고 · 범위는 하한 · 인턴·전환형 제외 · {S._dot(asof)}"}
    caption = "\n\n".join([
        "신입 개발자 연봉 티어 — S티어는 어디일까요? 댓글로 맞혀 보세요 👇",
        "\n".join(cap_lines[1:]),
        f"정답(S티어): {S._company(s_top[0])} — 공고 원문 \"{S._snip(s_top[1]['text'], 40)}\"",
        f"세는 법: 우리가 모은 개발 공고 중 경력 칸에 '신입'이 있고 신입 연봉을 숫자로 적은 {n}곳. 회사마다 가장 높은 공고 하나, "
        "범위는 하한(신입·경력 공통 범위는 신입이 아래쪽), 인턴·채용전환형 월급과 영업·기획·컨설팅 직무는 뺐습니다. "
        f"마감된 공고 포함, 최신 공고 {S._dot(asof)}. 큰 회사일수록 숫자를 안 적어서 이 표에 없다고 낮은 건 아닙니다.",
        "저장해 두고 · 연봉 협상 앞둔 친구에게 보내 주세요",
    ])
    return {"kind": "tier", "id": f"tier-newgrad-pay-{asof.replace('-', '')}", "slides": [slide], "caption": caption,
            "tags": ["신입연봉", "개발자연봉", "초봉", "신입개발자", "연봉티어"], "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser(prog="poster.tier")
    ap.add_argument("name", choices=["pay"])
    args = ap.parse_args()
    from .render import shutdown
    from .video import build as mp4
    post = build_pay()
    try:
        paths = S.render(post, S.REEL)
    finally:
        shutdown()
    out = mp4(paths, paths[0].parent / "reel.mp4", hold=7.0, motion=0.03,
              audio=Path(S.LAB_DIR / "assets" / "audio" / "bed_calm.wav"))
    (paths[0].parent / "caption.txt").write_text(
        post["caption"] + "\n\n" + " ".join(f"#{t}" for t in post["tags"]), encoding="utf-8")
    print(f"[tier] {post['id']} → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
