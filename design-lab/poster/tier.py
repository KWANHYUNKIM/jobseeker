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


#: 외주 분석은 카테고리('개발')만 보는데 사이트가 마케팅·기획 자리를 '개발' 에 넣기도 한다 — 제목으로 한 번 더 거른다
FL_NOT = re.compile(r"마케팅|홍보|디자인|디자이너|기획|영상|번역|회계|강사|교육|컨설팅|상담|운영자|PMO|\bPM\b", re.I)
#: '초, 중, 고급' 처럼 여러 등급을 한 공고에 적은 것은 등급을 정할 수 없다
FL_MULTI = re.compile(r"(초|중|고|특)\s*[,/·]\s*(초|중|고|특)")
GRADES = ["특급", "고급", "중급", "초급"]


def freelance_rates(days: int = 90) -> tuple[dict[str, list[tuple[float, dict]]], str, str]:
    """최근 days 일에 본 개발 외주의 등급별 월 단가(만원) — 외주 분석(pipeline.freelance_rates)과 같은 단가 규칙 + 제목 거르기."""
    import json
    from datetime import date, timedelta
    sys.path.insert(0, str(S.ROOT / "catch_capture"))
    from pipeline import freelance_rates as F
    doc = json.loads((S.ROOT / "jd-viewer" / "public" / "freelance.json").read_text(encoding="utf-8"))
    until = doc["analysis"]["current"]["until"]
    since = (date.fromisoformat(until) - timedelta(days=days)).isoformat()
    out: dict[str, list[tuple[float, dict]]] = {g: [] for g in GRADES}
    for p in doc["projects"]:
        v, g, title = F._first_monthly(p), p.get("grade"), p.get("title") or ""
        if v is None or g not in out or (p.get("last_seen_at") or "")[:10] < since:
            continue
        if FL_NOT.search(title) or FL_MULTI.search(title):
            continue
        out[g].append((v, p))
    return out, since, until


def build_freelance() -> dict:
    import statistics
    from .balance import _photo
    rates, since, until = freelance_rates()
    n = sum(len(v) for v in rates.values())
    bg, _ = _photo("startup.jpg")
    tiers, cap = [], []
    for g in GRADES:
        xs = sorted(v for v, _ in rates[g])
        med = round(statistics.median(xs))
        q = lambda f: round(xs[min(len(xs) - 1, int(round(f * (len(xs) - 1))))])  # noqa: E731
        est = sum(1 for _, p in rates[g] if p.get("grade_basis") != "표기")
        basis = "등급은 경력으로 추정" if est == len(xs) else f"표기 {len(xs) - est} · 추정 {est}"
        tiers.append({"g": g[0], "range": g, "names": f"한 달 {med:,}만원", "hide": g == "특급",
                      "note": (f"{len(xs)}건 · {basis}" if g == "특급" else f"가운데 절반 {q(.25):,}~{q(.75):,} · {len(xs)}건 · {basis}")})
        cap.append(f"{g} — 한 달 {med:,}만원 (가운데 절반 {q(.25):,}~{q(.75):,}만원, {len(xs)}건, {basis})")
    slide = {"type": "mag", "image": bg, "tiers": tiers, "rowh": 190, "head": ["프리랜서 개발자,", "**특급은 한 달에 얼마?**"],
             "sub": f"최근 90일 개발 외주 {n}건 · 월 단가 가운데 값",
             "foot": f"@devjobseeker 수집 외주(원티드 긱스·잡코리아·이랜서·프리모아·아임잡) · {S._dot(since)}~{S._dot(until)} 에 본 것 · "
                     "등급은 공고 표기, 없으면 경력으로 추정 · 여러 등급을 한 공고에 적은 것·비개발 제외"}
    caption = "\n\n".join([
        "프리랜서 개발자 한 달 단가 — 특급은 얼마일까요? 댓글로 맞혀 보세요 👇",
        "\n".join(cap[1:]),
        f"정답: {cap[0]}",
        f"세는 법: {S._dot(since)}~{S._dot(until)} 에 우리가 본 개발 외주 중 월 단가가 적힌 {n}건. 등급은 공고에 적힌 것, 없으면 요구 경력으로 "
        "추정했습니다(특급은 표기된 공고가 없어 모두 추정). 범위로 적힌 단가는 가운데 값. 마케팅·기획·디자인 자리와 '초·중·고급' 을 "
        "한 공고에 같이 적은 것은 뺐습니다. 실제 계약 단가가 아니라 공고에 적힌 금액입니다.",
        "저장해 두고 · 프리랜서 고민하는 친구에게 보내 주세요",
    ])
    return {"kind": "tier", "id": f"tier-freelance-rate-{until.replace('-', '')}", "slides": [slide], "caption": caption,
            "tags": ["프리랜서개발자", "개발자단가", "SI", "외주", "개발자연봉"]}


def main() -> int:
    ap = argparse.ArgumentParser(prog="poster.tier")
    ap.add_argument("name", choices=["pay", "freelance"])
    args = ap.parse_args()
    from .render import shutdown
    from .video import build as mp4
    post = build_pay() if args.name == "pay" else build_freelance()
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
