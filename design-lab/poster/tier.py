"""[티어표] 한 장짜리 릴스 — 5~8초, 맨 위 칸은 가려 두고 댓글로 맞히게 한다(planning/02-format 2-2 'T').

  python -m poster.tier pay        # 신입 연봉 적어 둔 개발 공고 티어
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import series as S

NL = "\n"

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
    base = {"type": "mag", "image": bg, "head": ["신입 개발자 연봉,", "**S티어는 어디?**"],
            "sub": f"공고 기준 · 신입 연봉을 숫자로 적은 {n}곳 · 만원",
            "foot": f"@devjobseeker 수집 개발 공고(마감 포함) · 회사마다 가장 높은 공고 · 범위는 하한 · 인턴·전환형 제외 · {S._dot(asof)}"}
    # 한 칸씩 채운다 — 아래(E)부터 위로, S 는 끝까지 가린다. 결과를 늦게 보여 줘야 끝까지 본다(playbook '끝까지 보게')
    order = [i for i, t in enumerate(tiers) if not t["hide"]][::-1]
    slides = []
    for k in range(len(order) + 1):
        shown = set(order[:k])
        slides.append({**base, "tiers": [{**t, "wait": (not t["hide"]) and i not in shown} for i, t in enumerate(tiers)]})
    slides[-1]["ask"] = ["S티어는 **어느 회사?** 댓글로 👇"]   # 바닥글 위 한 줄 — '당신 회사는 몇 티어?' 는 캡션 첫 줄에
    holds = [1.4] + [0.7] * (len(slides) - 2) + [4.5]   # 마지막 판은 다시 보게 오래 — 표를 한 번에 다 못 읽는다
    caption = "\n\n".join([
        "신입 개발자 연봉 티어 — S티어는 어디일까요? 당신 회사는 몇 티어인지도 댓글로 👇",
        "\n".join(cap_lines[1:]),
        f"정답(S티어): {S._company(s_top[0])} — 공고 원문 \"{S._snip(s_top[1]['text'], 40)}\"",
        f"세는 법: 우리가 모은 개발 공고 중 경력 칸에 '신입'이 있고 신입 연봉을 숫자로 적은 {n}곳. 회사마다 가장 높은 공고 하나, "
        "범위는 하한(신입·경력 공통 범위는 신입이 아래쪽), 인턴·채용전환형 월급과 영업·기획·컨설팅 직무는 뺐습니다. "
        f"마감된 공고 포함, 최신 공고 {S._dot(asof)}. 큰 회사일수록 숫자를 안 적어서 이 표에 없다고 낮은 건 아닙니다.",
        "저장해 두고 · 연봉 협상 앞둔 친구에게 보내 주세요",
    ])
    return {"kind": "tier", "id": f"tier-newgrad-pay-{asof.replace('-', '')}", "slides": slides, "holds": holds, "caption": caption,
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


def _med(xs: list[float]) -> int | None:
    import statistics
    return round(statistics.median(xs)) if xs else None


def build_freelance() -> dict:
    """릴스: 질문(특급 가림) → 정답 → 산출 → 이유 둘. 게시물(캐러셀): 같은 주제를 7장으로 자세히."""
    from .balance import _photo
    rates, since, until = freelance_rates()
    n = sum(len(v) for v in rates.values())
    bg, _ = _photo("startup.jpg")
    period = f"{S._dot(since)}~{S._dot(until)}"
    st: dict[str, dict] = {}
    for g in GRADES:
        rows = rates[g]
        xs = sorted(v for v, _ in rows)
        q = lambda f, xs=xs: round(xs[min(len(xs) - 1, int(round(f * (len(xs) - 1))))])  # noqa: E731
        st[g] = {"n": len(xs), "med": _med(xs), "p25": q(.25), "p75": q(.75),
                 "label": _med([v for v, p in rows if p.get("grade_basis") == "표기"]),
                 "est": _med([v for v, p in rows if p.get("grade_basis") != "표기"]),
                 "n_label": sum(1 for _, p in rows if p.get("grade_basis") == "표기"),
                 "si": _med([v for v, p in rows if p.get("work_type") == "SI"]),
                 "sm": _med([v for v, p in rows if p.get("work_type") == "SM"]),
                 "n_si": sum(1 for _, p in rows if p.get("work_type") == "SI"),
                 "n_sm": sum(1 for _, p in rows if p.get("work_type") == "SM")}

    def basis(g):
        x = st[g]
        return "등급은 경력으로 추정" if x["n_label"] == 0 else f"표기 {x['n_label']} · 추정 {x['n'] - x['n_label']}"

    def tiers(hide: bool):
        return [{"g": g[0], "range": g, "names": f"한 달 {st[g]['med']:,}만원", "hide": hide and g == "특급", "hl": (not hide) and g == "특급",
                 "note": (f"{st[g]['n']}건 · {basis(g)}" if hide and g == "특급"
                          else f"가운데 절반 {st[g]['p25']:,}~{st[g]['p75']:,} · {st[g]['n']}건 · {basis(g)}")} for g in GRADES]

    sp, go = st["특급"], st["고급"]
    gap = sp["med"] - go["med"]
    top = sorted(((v, p) for g in GRADES for v, p in rates[g]), key=lambda r: -r[0])[:4]
    foot = f"@devjobseeker 수집 외주 · {period} 에 본 개발 외주 · 공고에 적힌 월 단가(계약 단가 아님)"
    how = {"type": "mag", "image": bg, "pic": False, "tag": "어떻게 셌나", "head": ["공고 142건의", "**가운데 값**"] if n == 142 else [f"공고 {n}건의", "**가운데 값**"],
           "rows": [["모은 곳", "원티드 긱스·잡코리아·이랜서·프리모아·아임잡"], ["기간", f"{period} · {n}건"],
                    ["등급", "공고에 적힌 등급, 없으면 경력(3·7·10년)"], ["값", "월 단가 · 범위면 가운데 · 줄 세운 가운데"],
                    ["뺀 것", "마케팅·기획·디자인, '초·중·고급' 한꺼번에"]]}
    why1 = {"type": "mag", "image": bg, "pic": False, "tag": "왜 고급보다 +50뿐?",
            "head": ["'특급' 이라고 적은", "공고는 **0건**"],
            "rows": [["특급 11건", "전부 '경력 10년↑' 으로 추정"],
                     ["고급 · 등급을 적은 공고", f"**{go['label']:,}만원** ({go['n_label']}건)"],
                     ["고급 · 경력으로 추정", f"{go['est']:,}만원 ({go['n'] - go['n_label']}건)"],
                     ["그래서", "**등급을 적는 자리가 더 준다**"]]}
    why2 = {"type": "mag", "image": bg, "pic": False, "tag": "어디가 더 주나",
            "head": ["같은 고급이라도", f"**SI {go['si']:,} vs SM {go['sm']:,}**"],
            "rows": [["SI(새로 구축)", f"{go['si']:,}만원 · {go['n_si']}건"], ["SM(유지보수)", f"{go['sm']:,}만원 · {go['n_sm']}건"],
                     ["가장 높은 공고", f"{round(top[0][0]):,}만원 — {S._snip(top[0][1]['title'], 22)}"],
                     ["표본", "SI·SM 을 제목에 적은 것만 · 작다"]]}
    reel = [
        {"type": "mag", "image": bg, "tiers": tiers(True), "rowh": 190, "head": ["프리랜서 개발자,", "**특급은 한 달에 얼마?**"],
         "sub": f"최근 90일 개발 외주 {n}건 · 월 단가 가운데 값", "foot": foot},
        {"type": "mag", "image": bg, "tiers": tiers(False), "rowh": 190, "head": [f"특급 **{sp['med']:,}만원**", f"고급보다 +{gap}만원뿐"],
         "sub": f"최근 90일 개발 외주 {n}건 · 월 단가 가운데 값", "foot": foot},
        how, why1, {**why2, "ask": ["여러분이 본 **특급 단가는?**", "댓글로 👇"]},
    ]
    post = [
        {"type": "mag", "image": bg, "tiers": tiers(True), "rowh": 150, "head": ["프리랜서 개발자,", "**특급은 한 달에 얼마?**"],
         "sub": f"최근 90일 개발 외주 {n}건 · 월 단가 가운데 값 · 넘겨서 정답", "foot": foot},
        {"type": "mag", "image": bg, "tiers": tiers(False), "rowh": 150, "head": ["등급별 월 단가", f"특급 **{sp['med']:,}만원**"],
         "sub": f"{period} · {n}건 · 만원", "foot": foot},
        how,
        {"type": "mag", "image": bg, "pic": False, "tag": "등급은 이렇게", "head": ["공고 표기 먼저,", "**없으면 경력**"],
         "rows": [["초급", "경력 3년 미만"], ["중급", "3~6년"], ["고급", "7~9년"], ["특급", "10년 이상"],
                  ["주의", "시장에서 흔히 쓰는 구분 · KOSA 공식 등급과 다르다"]]},
        why1, why2,
        {"type": "mag", "image": bg, "pic": False, "tag": "단가가 높았던 공고", "head": ["월 단가", "**상위 4곳**"],
         "rows": [[f"{round(v):,}만원", S._snip(p['title'], 26)] for v, p in top]},
    ]
    caption_reel = (NL * 2).join([
        f"프리랜서 개발자 특급은 한 달에 얼마? — 정답 {sp['med']:,}만원, 고급({go['med']:,})보다 +{gap}만원뿐",
        f"왜 차이가 작을까요? '특급' 이라고 적은 공고가 하나도 없어서 11건 모두 경력 10년↑ 으로 추정했어요. 같은 고급이라도 등급을 적은 공고는 "
        f"{go['label']:,}만원, 경력으로 추정한 건 {go['est']:,}만원이었습니다.",
        f"전체 표·산출 방법·단가 높은 공고는 프로필의 [프리랜서 단가] 게시물에 정리했어요. 여러분이 본 특급 단가는? 댓글로 👇",
    ])
    caption_post = (NL * 2).join([
        f"[프리랜서 개발자 단가] 등급별 한 달 얼마? — {period} 개발 외주 {n}건",
        NL.join(f"{g} {st[g]['med']:,}만원 (가운데 절반 {st[g]['p25']:,}~{st[g]['p75']:,}, {st[g]['n']}건, {basis(g)})" for g in GRADES),
        f"특급이 고급보다 {gap}만원밖에 높지 않은 이유: '특급' 을 적은 공고가 0건이라 모두 경력 10년↑ 로 추정했고, 고급 안에서도 등급을 적은 공고({go['label']:,})가 "
        f"추정한 공고({go['est']:,})보다 높았습니다. 같은 고급이라도 SI(새로 구축) {go['si']:,} · SM(유지보수) {go['sm']:,}만원(제목에 SI·SM 을 적은 공고만, 표본 작음).",
        "단가가 높았던 공고: " + " · ".join(f"{S._snip(p['title'], 30)} {round(v):,}만원" for v, p in top),
        "세는 법: 원티드 긱스·잡코리아·이랜서·프리모아·아임잡에서 본 개발 외주 중 월 단가가 적힌 것. 등급은 공고 표기, 없으면 요구 경력"
        "(3년 미만 초급·3~6 중급·7~9 고급·10↑ 특급 — 시장 관행, KOSA 공식 등급과 다름). 범위는 가운데 값. 마케팅·기획·디자인과 여러 등급을 한꺼번에 "
        "적은 공고는 뺐습니다. 공고에 적힌 금액이고 실제 계약 단가는 협상으로 달라집니다.",
        "저장해 두고 · 프리랜서 고민하는 친구에게 보내 주세요",
    ])
    return {"kind": "tier", "id": f"tier-freelance-rate-{until.replace('-', '')}", "slides": reel, "post": post,
            "caption": caption_reel, "caption_post": caption_post,
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
        if post.get("post"):   # 같은 주제의 캐러셀 게시물(4:5) — 자세한 표·산출·이유
            feed = S.render({**post, "id": post["id"] + "-post", "slides": post["post"]})
            (feed[0].parent / "caption.txt").write_text(
                post["caption_post"] + NL * 2 + " ".join(f"#{t}" for t in post["tags"]), encoding="utf-8")
            print(f"[tier] 게시물 {len(feed)}장 → {feed[0].parent}")
    finally:
        shutdown()
    hold = post.get("holds") or 3.2   # 정보 장면(산출·이유)은 읽을 시간이 필요하다
    # 한 칸씩 채우는 판은 다가가기를 끈다 — 장마다 확대가 처음으로 돌아가 표가 튄다
    out = mp4(paths, paths[0].parent / "reel.mp4", hold=hold, motion=0.0 if post.get("holds") else 0.03,
              audio=Path(S.LAB_DIR / "assets" / "audio" / "bed_calm.wav"))
    (paths[0].parent / "caption.txt").write_text(
        post["caption"] + "\n\n" + " ".join(f"#{t}" for t in post["tags"]), encoding="utf-8")
    print(f"[tier] {post['id']} → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
