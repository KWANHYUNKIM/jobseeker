"""[둘 중 하나] 밸런스 게임 릴스 — "너라면 A? B?" 로 댓글을 부르는 짧은 영상.

한 편은 3~6 장면: 위 A · 아래 B 로 갈라 묻고(vs), 각 쪽의 조건·위치·현실 숫자를 한 장씩 보여 준 뒤
"댓글로 A or B" 로 닫는다. **숫자는 둘 중 하나다** — 우리가 모은 공고 원문(회사·직무·근무지·조건을
그대로)이거나 출처가 있는 통계(장면 안에 출처). 가정으로 세운 선택지("연봉 +500")는 판에 '가정' 이라고 쓴다.
사진은 Wikimedia Commons 의 CC·PD 사진(assets/photos/balance/credits.json, 판마다 작가·라이선스),
지도는 OpenStreetMap(poster.maps).

  python -m poster.balance            # 전 편을 릴스로 찍는다
  python -m poster.balance seoul      # 한 편만
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from . import maps, series as S

PH = S.PHOTOS / "balance"
#: 공고에 그 말을 직접 적었는지 — series.PERKS 와 같은 규칙에 몇 가지를 더한다
EXTRA = {
    "식사 제공": r"(중식|점심|석식|식사|조식)\s*(무료\s*)?(제공|지원)|구내\s*식당|사내\s*식당|식대\s*(지원|제공)",
    "장비 지원": r"맥북|MacBook|최신\s*장비|장비\s*지원|듀얼\s*모니터",
}
RENT = {  # 다방 '8월 다방여지도'(국토교통부 실거래가) — 헤럴드경제 2026-09-29
    "seoul": 67, "gangnam_pct": 131,
    "src": "다방 '8월 다방여지도'(국토부 실거래가 · 서울 전용 33㎡ 이하 연립·다세대 원룸 · 보증금 1,000만원 기준) · 헤럴드경제 2026.09.29",
}
COMMUTE = {"min": 82.0, "src": "통계청 '2024년 통근 근로자 이동 특성 분석'(수도권 하루 출·퇴근 평균) · KTV 2024.12.23"}


def _photo(name: str) -> tuple[str, str]:
    import base64
    c = json.loads((PH / "credits.json").read_text(encoding="utf-8"))[name]
    uri = "data:image/jpeg;base64," + base64.b64encode((PH / name).read_bytes()).decode()
    artist = re.sub(r"\s+", " ", c["artist"])[:40]
    return uri, f"{artist} · {c['license']} · Wikimedia Commons"


def _counts() -> tuple[int, dict[str, int], str]:
    """모집중 개발 공고에서 조건을 직접 적은 곳 수."""
    allj = S._source()
    rows = S._open_dev(allj)
    pats = {name: pat for name, pat in S.PERKS} | EXTRA
    return len(rows), {k: sum(1 for j in rows if re.search(p, S._text(j), re.I)) for k, p in pats.items()}, S._data_date(allj)


def _pct(c: int, n: int) -> str:
    return f"{100 * c / n:.1f}%"


def _cta(a_img: str, b_img: str, a: str, b: str, note: str) -> dict:
    """끝 장면 — 처음처럼 위 A · 아래 B 로 다시 갈라 놓고 고르게 한다."""
    return {"type": "mag", "vs": [{"image": a_img, "title": a.split(" · ")[0], "lines": [" · ".join(a.split(" · ")[1:])]},
                                  {"image": b_img, "title": b.split(" · ")[0], "lines": [" · ".join(b.split(" · ")[1:])]}],
            "q": ["당신이라면", "**A? B?** 댓글로 👇"], "credit": note}


# --- 편마다 ------------------------------------------------------------------
def ep_seoul() -> dict:
    """서울 강남 연봉 2,800 vs 충남 천안 4천 초중반 + 주거지원비 — 둘 다 실제 신입 공고."""
    g_uri, g_cr = _photo("gangnam.jpg")
    c_uri, c_cr = _photo("cheonan.jpg")
    a_xy, a_st = (37.4952945, 127.0294347), (37.5002304, 127.0268054)       # 강남대로 364 · 강남역
    b_xy, b_st = (36.8466136, 127.1116039), (36.8102804, 127.1468400)       # 3공단6로 140 · 천안역
    a_m, b_m = maps.meters(a_xy, a_st), maps.meters(b_xy, b_st)
    a_map = maps.data_uri(maps.render(*a_xy, zoom=16, label="강남대로 364", landmark=(*a_st, "강남역")))
    b_map = maps.data_uri(maps.render(*b_xy, zoom=13, label="3공단6로 140", landmark=(*b_st, "천안역")))
    gangnam_rent = round(RENT["seoul"] * RENT["gangnam_pct"] / 100)
    monthly = round(2800 / 12)
    slides = [
        {"type": "mag", "vs": [
            {"image": g_uri, "title": "서울 강남", "lines": ["연봉 **2,800만원**", "Java 백엔드 신입"]},
            {"image": c_uri, "title": "충남 천안", "lines": ["연봉 **4천만원 초중반**", "+ 주거지원비 월 40만원"]}],
         "q": ["신입 개발자,", "**어디로** 갈래?"], "credit": f"사진: {g_cr} / {c_cr}"},
        {"type": "mag", "image": a_map, "tag": "A · 서울 강남", "head": [f"강남역 **{round(a_m, -1):.0f}m**"],
         "rows": [["직무", "Java 백엔드 신입(경력 2년 이하)"], ["연봉", "**2,800만원** · 수습 3개월"],
                  ["근무지", "강남대로 364 미왕빌딩"], ["복지", "최신 장비 · 코드리뷰 · 교육 지원"]],
         "credit": f"펄포즌 · 사람인 공고(2026.09.30 마감) · {maps.CREDIT}"},
        {"type": "mag", "image": g_uri, "tag": "A 의 현실", "head": ["강남 원룸 월세", f"**약 {gangnam_rent}만원**"],
         "rows": [["서울 평균", f"{RENT['seoul']}만원(8월)"], ["강남구", f"서울 평균의 {RENT['gangnam_pct']}%"],
                  ["월급(세전)", f"약 {monthly}만원 → **{round(100 * gangnam_rent / monthly)}%** 가 월세"]],
         "credit": RENT["src"]},
        {"type": "mag", "image": b_map, "tag": "B · 충남 천안", "head": [f"천안역에서 **{b_m / 1000:.1f}km**"],
         "rows": [["직무", "SoC 응용 엔지니어 · ATE 테스트 프로그램(C/C++)"], ["연봉", "**4천만원 초중반** + 글로벌 보너스 연 2회"],
                  ["주거", "신입 주거지원비 **월 40만원**(1년)"], ["출퇴근", "통근버스 천안시내↔공장 · 운전면허 필수"]],
         "credit": f"아드반테스트코리아 · 사람인 공고(2026.07.19 마감 · 근무지 동탄/천안) · {maps.CREDIT}"},
        {"type": "mag", "image": c_uri, "tag": "B 의 조건", "head": ["재택은 주 2회,", "**1년 뒤부터**"],
         "rows": [["복지카드", "연 700~900만원(1년 이상)"], ["필수", "전자·컴퓨터공학 · 운전면허"],
                  ["근무지", "동탄 또는 천안 — 공고 원문"]],
         "credit": f"아드반테스트코리아 공고 원문 · 사진 {c_cr}"},
        _cta(g_uri, c_uri, f"강남 2,800 · 역 {round(a_m, -1):.0f}m · 월세 약 {gangnam_rent}만",
             "천안 4천 초중반 · 주거비 월 40만 · 통근버스", "둘 다 지난 공고 · 원문 링크는 캡션"),
    ]
    caption = "\n\n".join([
        "[둘 중 하나] 신입 개발자, 어디로 갈래? A 서울 강남 vs B 충남 천안",
        f"A 펄포즌 — Java 백엔드 신입, 연봉 2,800만원(수습 3개월), 강남대로 364(강남역 약 {round(a_m, -1):.0f}m). "
        "2026.09.30 마감 공고.",
        f"B 아드반테스트코리아 — SoC Application Engineer(ATE 테스트 프로그램, C/C++), 대졸 신입 4천만원 초중반 + 글로벌 보너스 연 2회, "
        f"신입 주거지원비 월 40만원(1년), 통근버스, 재택 주 최대 2회(1년 이상), 운전면허 필수. 근무지 동탄/천안(천안역에서 약 {b_m / 1000:.1f}km). "
        "2026.07.19 마감 공고.",
        f"강남 원룸 월세: 서울 평균 {RENT['seoul']}만원의 {RENT['gangnam_pct']}% ≈ {gangnam_rent}만원. 출처: {RENT['src']}.",
        "여러분이라면 A? B? 댓글로 이유까지 알려 주세요 👇",
        "공고 원문: 사람인 rec_idx=54626054 · rec_idx=54432891 · 사진 Wikimedia Commons(작가·라이선스는 각 장) · 지도 © OpenStreetMap contributors",
    ])
    return {"id": "balance-seoul", "slides": slides, "caption": caption, "tags": ["신입개발자", "개발자취업", "서울vs지방", "밸런스게임", "IT취업"]}


def ep_remote(n: int, c: dict, asof: str) -> dict:
    h_uri, h_cr = _photo("homeoffice.jpg")
    w_uri, w_cr = _photo("commute.jpg")
    hours = round(COMMUTE["min"] * 250 / 60)
    slides = [
        {"type": "mag", "vs": [
            {"image": h_uri, "title": "매일 재택", "lines": ["연봉 **4,000만원**", "출퇴근 0분"]},
            {"image": w_uri, "title": "매일 출근", "lines": ["연봉 **4,500만원**", "사무실·동료 옆자리"]}],
         "q": ["연봉 500,", "**재택이랑 바꿀래?**"], "credit": f"가정 상황 · 사진: {h_cr} / {w_cr}"},
        {"type": "mag", "image": w_uri, "tag": "B 의 현실", "head": ["수도권 출퇴근", f"**하루 {COMMUTE['min']:.0f}분**"],
         "rows": [["1년(250일)이면", f"약 **{hours}시간**"], ["= 하루 8시간 근무로", f"약 {hours // 8}일"]],
         "credit": COMMUTE["src"]},
        {"type": "mag", "image": h_uri, "tag": "A 의 현실", "head": ["재택을 적은 공고", f"**{_pct(c['재택·원격'], n)}**"],
         "rows": [["모집중 개발 공고", f"{n:,}건"], ["재택·원격", f"{c['재택·원격']:,}건"], ["주 4일·4.5일", f"{c['주 4일·4.5일']}건"]],
         "credit": f"@devjobseeker 수집 공고 · 공고 본문에 직접 적은 곳 · {S._dot(asof)}"},
        _cta(h_uri, w_uri, "재택 · 연봉 4,000", "출근 · 연봉 4,500", "연봉은 가정 · 통계와 공고 수는 실제"),
    ]
    caption = "\n\n".join([
        "[둘 중 하나] 연봉 500 더 받고 매일 출근 vs 연봉 덜 받고 매일 재택",
        f"수도권 직장인은 출·퇴근에 하루 평균 {COMMUTE['min']:.0f}분을 씁니다({COMMUTE['src']}). 1년 250일이면 약 {hours}시간이에요.",
        f"그런데 재택·원격을 공고에 적은 곳은 모집중 개발 공고 {n:,}건 중 {c['재택·원격']:,}건({_pct(c['재택·원격'], n)}), "
        f"주 4일·4.5일은 {c['주 4일·4.5일']}건뿐입니다({S._dot(asof)} 기준).",
        "연봉 4,000 / 4,500 은 고르기 위한 가정입니다. 여러분은 A? B? 👇",
    ])
    return {"id": "balance-remote", "slides": slides, "caption": caption, "tags": ["재택근무", "개발자", "밸런스게임", "개발자취업", "IT회사"]}


def ep_macbook(n: int, c: dict, asof: str) -> dict:
    m_uri, m_cr = _photo("macbook.jpg")
    k_uri, k_cr = _photo("coins.jpg")
    slides = [
        {"type": "mag", "vs": [
            {"image": m_uri, "title": "최신 맥북 지급", "lines": ["입사 첫날 **새 장비**", "연봉 그대로"]},
            {"image": k_uri, "title": "연봉 +200만원", "lines": ["장비는 **회사 재고**", "쓰던 노트북"]}],
         "q": ["첫 회사,", "**뭐가 더 끌려?**"], "credit": f"가정 상황 · 사진: {m_cr} / {k_cr}"},
        {"type": "mag", "image": m_uri, "tag": "현실 숫자", "head": ["장비를 공고에 적은 곳", f"**{_pct(c['장비 지원'], n)}**"],
         "rows": [["모집중 개발 공고", f"{n:,}건"], ["맥북·최신 장비·듀얼 모니터", f"{c['장비 지원']:,}건"],
                  ["면접에서", "**'장비 사양' 은 물어봐도 되는 것**"]],
         "credit": f"@devjobseeker 수집 공고 · 공고 본문에 직접 적은 곳 · {S._dot(asof)}"},
        _cta(m_uri, k_uri, "맥북 지급 · 연봉 그대로", "연봉 +200 · 쓰던 장비", "선택지는 가정 · 공고 수는 실제"),
    ]
    caption = "\n\n".join([
        "[둘 중 하나] 입사 첫날 최신 맥북 vs 연봉 200만원 더",
        f"맥북·최신 장비·듀얼 모니터를 공고에 직접 적은 곳은 모집중 개발 공고 {n:,}건 중 {c['장비 지원']:,}건({_pct(c['장비 지원'], n)})입니다({S._dot(asof)}).",
        "장비 사양은 면접에서 물어봐도 되는 것이에요. 여러분은 A? B? 👇",
    ])
    return {"id": "balance-macbook", "slides": slides, "caption": caption, "tags": ["맥북", "개발자", "밸런스게임", "신입개발자", "IT회사"]}


def ep_stock(n: int, c: dict, asof: str) -> dict:
    s_uri, s_cr = _photo("startup.jpg")
    t_uri, t_cr = _photo("corporate.jpg")
    slides = [
        {"type": "mag", "vs": [
            {"image": s_uri, "title": "스타트업", "lines": ["연봉 조금 낮게", "+ **스톡옵션**"]},
            {"image": t_uri, "title": "큰 회사", "lines": ["연봉 **높게**", "스톡옵션 없음"]}],
         "q": ["신입 첫 회사,", "**한 방? 안정?**"], "credit": f"가정 상황 · 사진: {s_cr} / {t_cr}"},
        {"type": "mag", "image": s_uri, "tag": "현실 숫자", "head": ["스톡옵션을 적은 공고", f"**{_pct(c['스톡옵션'], n)}**"],
         "rows": [["모집중 개발 공고", f"{n:,}건"], ["스톡옵션·RSU", f"{c['스톡옵션']:,}건"],
                  ["볼 것", "**행사가 · 베스팅 기간 · 회사 단계**"]],
         "credit": f"@devjobseeker 수집 공고 · 공고 본문에 직접 적은 곳 · {S._dot(asof)}"},
        _cta(s_uri, t_uri, "스타트업 + 스톡옵션", "큰 회사 + 높은 연봉", "선택지는 가정 · 공고 수는 실제"),
    ]
    caption = "\n\n".join([
        "[둘 중 하나] 스톡옵션 주는 스타트업 vs 연봉 높은 큰 회사",
        f"스톡옵션·RSU 를 공고에 적은 곳은 모집중 개발 공고 {n:,}건 중 {c['스톡옵션']:,}건({_pct(c['스톡옵션'], n)})입니다({S._dot(asof)}).",
        "스톡옵션은 행사가와 베스팅 기간이 핵심이에요. 여러분은 A? B? 👇",
    ])
    return {"id": "balance-stock", "slides": slides, "caption": caption, "tags": ["스톡옵션", "스타트업", "밸런스게임", "개발자취업", "IT회사"]}


def ep_lunch(n: int, c: dict, asof: str) -> dict:
    doc = json.loads((S.CONTENT / "lunch-pangyo.json").read_text(encoding="utf-8"))
    pl = doc["places"]
    l_uri, l_cr = S._photo("lunch", pl[7]["photo"])     # 딤섬 — 메뉴 예시 사진
    t_uri, t_cr = _photo("canteen.jpg")
    slides = [
        {"type": "mag", "vs": [
            {"image": l_uri, "title": "판교 맛집 점심", "lines": ["매일 **골라 먹기**", "한 끼 1.1만~1.9만원"]},
            {"image": t_uri, "title": "회사 밥 무료", "lines": ["구내식당 **0원**", "메뉴는 그날그날"]}],
         "q": ["점심,", "**뭐가 더 좋아?**"], "credit": f"사진(메뉴·식당 예시): {l_cr} / {t_cr}"},
        {"type": "mag", "image": t_uri, "tag": "현실 숫자", "head": ["식사 제공을 적은 공고", f"**{_pct(c['식사 제공'], n)}**"],
         "rows": [["모집중 개발 공고", f"{n:,}건"], ["점심·식사 제공·구내식당·식대", f"{c['식사 제공']:,}건"],
                  ["판교 점심 10곳", "1.1만~1.9만원(뷔페 제외)"]],
         "credit": f"@devjobseeker 수집 공고({S._dot(asof)}) · 판교 가격은 [점심 지도] 출처 기준"},
        _cta(l_uri, t_uri, "판교 맛집 · 매일 1~2만원", "구내식당 · 0원", "판교 점심 10곳은 프로필 [점심 지도] 릴스"),
    ]
    caption = "\n\n".join([
        "[둘 중 하나] 판교 맛집 골라 먹기 vs 회사 밥 무료",
        f"점심·식사 제공·구내식당·식대 지원을 공고에 적은 곳은 모집중 개발 공고 {n:,}건 중 {c['식사 제공']:,}건({_pct(c['식사 제공'], n)})입니다({S._dot(asof)}).",
        "판교 점심 10곳 가격(1.1만~1.9만원, 뷔페 제외)은 [점심 지도] 릴스의 출처 기준이에요. 사진은 메뉴·식당 예시입니다.",
        "여러분은 A? B? 👇",
    ])
    return {"id": "balance-lunch", "slides": slides, "caption": caption, "tags": ["판교맛집", "판교점심", "밸런스게임", "IT회사", "직장인점심"]}


EPISODES = ["seoul", "remote", "macbook", "stock", "lunch"]


def build(name: str) -> dict:
    if name == "seoul":
        return ep_seoul()
    n, c, asof = _counts()
    return {"remote": ep_remote, "macbook": ep_macbook, "stock": ep_stock, "lunch": ep_lunch}[name](n, c, asof)


def main() -> int:
    ap = argparse.ArgumentParser(prog="poster.balance")
    ap.add_argument("names", nargs="*", default=EPISODES)
    args = ap.parse_args()
    from .render import shutdown
    from .video import build as mp4
    from pathlib import Path
    try:
        for name in args.names:
            ep = build(name)
            post = {"kind": "balance", "id": ep["id"], "slides": ep["slides"]}
            paths = S.render(post, S.REEL)
            out = mp4(paths, paths[0].parent / "reel.mp4", hold=2.9, motion=0.05,
                      audio=Path(S.LAB_DIR / "assets" / "audio" / "bed_calm.wav"))
            (paths[0].parent / "caption.txt").write_text(
                ep["caption"] + "\n\n" + " ".join(f"#{t}" for t in ep["tags"]), encoding="utf-8")
            print(f"[balance] {ep['id']} {len(paths)}장 → {out}")
    finally:
        shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
