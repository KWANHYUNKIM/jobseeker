"""카드뉴스 시안 — 같은 원고를 틀 여러 개로 찍어 한 장에 나란히 놓는다. 고른 틀만 발행으로 간다.

series.py 는 틀이 series.html 하나이고 시리즈마다 색만 다르다. 그래서 피드가 한 종류로 보였다.
여기서는 **구조가 다른 틀**(templates/newscard/*.html)에 같은 원고를 넣고, 장마다 사진을 깐다.
사진은 무료 라이선스(위키미디어 공용 — CC0·CC BY·CC BY-SA)만, 출처는 assets/photos/newscard/credits.json.

    python -m poster.newscard weekly                         # 이번 주 신규 공고 → 틀 전부
    python -m poster.newscard weekly --styles magazine paper # 고른 틀만

결과: out/newscard/<원고 id>/<틀>/NN.jpg · _board.jpg(틀 × 장) · _feed.jpg(피드 3×3 미리보기)
고르기 전에는 inbox 로 아무것도 넣지 않는다.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

LAB_DIR = Path(__file__).resolve().parent.parent
TPL_DIR = Path(__file__).resolve().parent / "templates" / "newscard"
PHOTOS = LAB_DIR / "assets" / "photos" / "newscard"
OUT = LAB_DIR / "out" / "newscard"
SIZE = (1080, 1350)

#: 틀 이름 → 설명. 파일은 templates/newscard/<이름>.html
STYLES = {
    "magazine": "잡지 — 사진을 판 전체에, 명조 제목",
    "paper": "신문 1면 — 제호·단 나눔·흑백 사진",
    "poster": "포스터 — 원색 면 + 이중톤 사진 + 아주 큰 숫자",
    "scrap": "스크랩 — 종이 위 폴라로이드·형광펜",
    "brandmag": "회사 잡지 — 장마다 그 회사의 색·서체·대표 물건",
}

#: 틀이 쓰는 글꼴. 렌더러는 file:// 을 못 읽어서 data: URI 로 박는다(carousel._font_faces 와 같은 이유).
FONTS = {
    "Pretendard": [(800, "assets/companies/당근/fonts/compare/Pretendard-ExtraBold.woff2"),
                   (700, "assets/companies/당근/fonts/compare/Pretendard-Bold.woff2"),
                   (600, "assets/companies/쏘카/fonts/compare/Pretendard-SemiBold.woff2"),
                   (500, "assets/companies/당근/fonts/compare/Pretendard-Medium.woff2")],
    "Paperlogy": [(900, "assets/companies/올리브영/fonts/Paperlogy-9Black.woff2"),
                  (700, "assets/companies/당근/fonts/compare/Paperlogy-7Bold.woff2")],
    "GothicA1": [(900, "assets/companies/네이버웹툰/fonts/GothicA1-Black.ttf")],
    "NanumMyeongjo": [(700, "assets/companies/롯데카드/fonts/body/NanumMyeongjo-Bold.ttf")],
    "GowunBatang": [(700, "assets/companies/롯데카드/fonts/body/GowunBatang-Bold.ttf"),
                    (400, "assets/companies/롯데카드/fonts/body/GowunBatang-Regular.ttf")],
    "SpaceMono": [(700, "assets/companies/카카오뱅크/fonts/body/SpaceMono-Bold.ttf")],
}
#: 틀마다 필요한 글꼴만 — 다 박으면 한 장이 30MB 가 된다.
STYLE_FONTS = {
    "magazine": ["Pretendard", "NanumMyeongjo"],
    "paper": ["Pretendard", "GothicA1", "NanumMyeongjo"],
    "poster": ["Pretendard", "Paperlogy", "SpaceMono"],
    "scrap": ["Pretendard", "GowunBatang"],
    "brandmag": ["Pretendard", "NanumMyeongjo"],
}
#: 원고마다 기본으로 찍을 틀
DEFAULT_STYLES = {"weekly": ["magazine", "paper", "poster", "scrap"], "brands": ["brandmag"], "finance": ["magazine"], "intern": ["magazine"], "midlevel": ["magazine"]}


#: 회사 자산(assets/companies/…)이 없는 기계에서 쓰는 공용 글꼴 — 공식 배포본(OFL), 라이선스는 같은 폴더.
SHARED_FONTS = LAB_DIR / "assets" / "fonts"


def _font_faces(families: list[str]) -> str:
    """틀이 쓰는 글꼴을 data URI 로 — 회사 경로에 없으면 공용 폴더(assets/fonts)의 같은 이름, 거기도 없으면 그 굵기만
    건너뛴다(브라우저가 다음 굵기·대체 글꼴로 그린다). 회사 자산은 판을 만드는 PC 에만 있어서 다른 기계에서 죽었다."""
    out = []
    for fam in families:
        for weight, rel in FONTS[fam]:
            p = LAB_DIR / rel
            if not p.exists():
                p = SHARED_FONTS / Path(rel).name
            if not p.exists():
                print(f"[newscard] 글꼴 없음, 건너뜀: {rel}", file=sys.stderr)
                continue
            fmt, mime = ("woff2", "font/woff2") if p.suffix == ".woff2" else ("truetype", "font/ttf")
            b64 = base64.b64encode(p.read_bytes()).decode()
            out.append(f"@font-face{{font-family:'{fam}';font-weight:{weight};"
                       f"src:url(data:{mime};base64,{b64}) format('{fmt}');}}")
    return "\n".join(out)


def _photo(name: str) -> tuple[str, str]:
    """사진 → (data URI, 출처 한 줄). 출처는 판마다 적는다(CC BY·BY-SA 조건)."""
    credits = json.loads((PHOTOS / "credits.json").read_text(encoding="utf-8"))
    c = credits[name]
    artist = c["artist"].removeprefix("User:")
    uri = "data:image/jpeg;base64," + base64.b64encode((PHOTOS / name).read_bytes()).decode()
    return uri, f"사진 {artist} · {c['license']} · Wikimedia Commons"


# --- 원고 ---------------------------------------------------------------
def _dsn() -> str:
    return os.environ.get("JOBSEEKER_DSN", "postgresql://jobseeker:jobseeker@127.0.0.1:5433/jobseeker")


#: 이번 주에 처음 수집한 모집중 공고(사이트 간 사본은 대표만). 등록일은 대부분 비어 있어 '처음 수집한 날'로 센다.
_WEEK = """
    SELECT j.id, c.display_name AS co, j.title, j.deadline_on, f.roles, f.career_bucket,
           f.company_size, f.stacks
      FROM job j
      JOIN company c ON c.id = j.company_id
      JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
      LEFT JOIN job_dup d ON d.job_id = j.id
      JOIN job_facet f ON f.job_id = j.id
     WHERE j.first_seen_at >= %s AND (d.canonical_id IS NULL OR d.canonical_id = j.id)
"""


def build_weekly(today: date | None = None) -> dict:
    import collections

    import psycopg
    from psycopg.rows import dict_row

    today = today or date.today()
    since = today - timedelta(days=6)
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        rows = conn.execute(_WEEK, (since,)).fetchall()
    n = len(rows)
    roles = collections.Counter(r for j in rows for r in j["roles"] if r != "기타").most_common(5)
    stacks = collections.Counter(s for j in rows for s in set(j["stacks"])).most_common(5)
    entry = [j for j in rows if j["career_bucket"] == "신입/무관"]
    soon = [j for j in rows if j["deadline_on"] and 0 <= (j["deadline_on"] - today).days <= 7]
    # 눈에 띄는 공고: 대기업·중견의 신입 가능 공고, 마감 가까운 순
    picks = sorted((j for j in entry if j["company_size"] in ("대기업", "중견기업") and j["deadline_on"]),
                   key=lambda j: j["deadline_on"])
    seen, pick_rows = set(), []
    for j in picks:
        if j["co"] in seen:
            continue
        seen.add(j["co"])
        pick_rows.append({"co": _co(j["co"]), "title": _short(j["title"]),
                          "meta": f"신입 가능 · ~{j['deadline_on']:%m.%d} 마감"})
        if len(pick_rows) == 4:
            break
    span = f"{since:%m.%d}~{today:%m.%d}"
    note = f"@devjobseeker 가 {span} 처음 수집한 모집중 개발 공고 {n:,}건 · 사이트 간 중복 제외"
    slides = [
        {"type": "cover", "photo": "seoul.jpg", "kicker": f"WEEKLY · {today:%Y.%m.%d}",
         "big": f"{n:,}", "unit": "건", "title": ["이번 주 새로 열린", "개발 공고"],
         "sub": "어디가 사람을 뽑고, 무엇을 원하나"},
        {"type": "bars", "photo": "code.jpg", "kicker": "직군", "title": "백엔드와 AI 가 절반",
         "sub": "직군별 신규 공고 수 (한 공고가 여러 직군에 걸칠 수 있다)",
         "rows": [{"label": k, "value": v} for k, v in roles]},
        {"type": "bars", "photo": "css.jpg", "kicker": "기술", "title": f"가장 많이 찾은 기술, {stacks[0][0]}",
         "sub": "신규 공고에 적힌 횟수",
         "rows": [{"label": k, "value": v, "pct": round(100 * v / n)} for k, v in stacks]},
        {"type": "picks", "photo": "pangyo.jpg", "kicker": "눈여겨볼 곳", "title": "신입도 넣을 수 있는 큰 회사",
         "sub": "대기업·중견기업의 신입 가능 신규 공고, 마감 가까운 순", "rows": pick_rows},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "마감", "title": "일주일 안에 닫힌다",
         "items": [{"num": f"{len(soon):,}", "unit": "건", "label": "7일 안에 마감되는 신규 공고"},
                   {"num": f"{len(entry):,}", "unit": "건", "label": "신입 가능 신규 공고"}],
         "explain": "마감일을 적지 않은 공고도 많아, 실제로 닫히는 공고는 이보다 많다."},
        {"type": "end", "photo": "typing.jpg", "kicker": "다음 주 월요일", "title": "저장해 두고\n한 주씩 비교해 보세요",
         "lines": ["이번 주에 이직을 고민하는 동료에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for s in slides:
        s["image"], s["credit"] = _photo(s.pop("photo"))
        s["note"] = note
    caption = "\n\n".join([
        f"[주간 리포트] 이번 주 새로 열린 개발 공고 {n:,}건",
        "직군: " + " · ".join(f"{k} {v}" for k, v in roles),
        "기술: " + " · ".join(f"{k} {v}" for k, v in stacks),
        "신입 넣을 수 있는 큰 회사: " + " · ".join(f"{r['co']} {r['title']}" for r in pick_rows),
        f"7일 안에 마감 {len(soon):,}건 · 신입 가능 {len(entry):,}건",
        note + ".",
        "사진: " + " / ".join(dict.fromkeys(s["credit"].removeprefix("사진 ") for s in slides)),
    ])
    return {"id": f"weekly-{today:%Y%m%d}", "title": "주간 리포트", "series": "[주간 리포트]",
            "slides": slides, "caption": caption}


def _co(name: str) -> str:
    import re
    return re.sub(r"\(주\)|㈜|주식회사|\(유\)|\s+$", "", name).strip()


def _short(title: str, n: int = 34) -> str:
    import re
    t = re.sub(r"\s+", " ", re.sub(r"^\[[^\]]{1,20}\]\s*", "", title)).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


#: 회사 장의 얼굴 — 색은 brands/*.json 의 조사값에서, 면을 무엇으로 칠할지만 여기서 정한다.
#: band = 대표 이미지를 판 위쪽 띠로(가로 사진) · object = 브랜드 색 면 위에 물건 하나(카드·봉투)
COMPANY_LOOK = {
    "네이버": {"bg": "#03c75a", "ink": "#ffffff", "sub": "#e3f8eb", "accent": "#17181a", "image": "atrium", "mode": "band"},
    "카카오뱅크": {"bg": "#ffe300", "ink": "#1e1e1e", "sub": "#4a4430", "accent": "#1e1e1e", "image": "card_black",
              "mode": "object", "object_bg": "#1e1e1e"},
    "쿠팡": {"bg": "#ffffff", "ink": "#111111", "sub": "#4f5660", "accent": "#0090c0", "image": "waybill", "mode": "band"},
    "올리브영": {"bg": "#82dc28", "ink": "#0b2a08", "sub": "#24451c", "accent": "#ffffff", "image": "store", "mode": "band"},
    "카카오페이": {"bg": "#fedf85", "ink": "#1a1a1a", "sub": "#5a4a24", "accent": "#ff6868", "image": "envelope3d",
              "mode": "object"},
    "쏘카": {"bg": "#050a5a", "ink": "#ffffff", "sub": "#b9c3ff", "accent": "#66b0ff", "image": "road", "mode": "band"},
}

#: 회사마다 지금 모집중인 개발 공고(사이트 간 사본은 대표만). 마감 가까운 순, 상시는 뒤로.
_COMPANY_JOBS = """
    SELECT j.title, j.deadline_on, f.career_bucket, j.first_seen_at
      FROM job j
      JOIN company c ON c.id = j.company_id
      JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
      LEFT JOIN job_dup d ON d.job_id = j.id
      JOIN job_facet f ON f.job_id = j.id
     WHERE c.display_name = ANY(%s) AND (d.canonical_id IS NULL OR d.canonical_id = j.id)
     ORDER BY j.first_seen_at DESC, j.deadline_on NULLS LAST
"""


def _data_uri(path: Path) -> str:
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}[path.suffix.lower()]
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def _career(bucket: str) -> str:
    return {"신입/무관": "신입 가능", "정보없음": "경력 무관(표기 없음)", "8년+": "경력 8년+"}.get(bucket, f"경력 {bucket}")


def build_brands(today: date | None = None) -> dict:
    """[이번 주의 회사] 회사 한 곳에 한 장 — 그 회사가 스스로 쓰는 색·서체·대표 물건으로 판을 칠한다."""
    import psycopg
    from psycopg.rows import dict_row

    from . import brands as brandmod
    from .carousel import _font_faces as brand_fonts

    today = today or date.today()
    pages, index = [], []
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        for name, look in COMPANY_LOOK.items():
            b = brandmod.find(name)
            names = list({*b.get("names", []), name})
            jobs = conn.execute(_COMPANY_JOBS, (names,)).fetchall()
            if not jobs:
                continue
            img = LAB_DIR / b["images"][look["image"]]
            rows = [{"title": _short(j["title"], 56),
                     "meta": _career(j["career_bucket"]) + (f" · ~{j['deadline_on']:%m.%d} 마감" if j["deadline_on"] else " · 상시")}
                    for j in jobs[:3]]
            ui = b.get("ui", {})
            pages.append({
                "type": "company", "name": name, "wordmark": b.get("wordmark") or name,
                "slogan": (b.get("slogan") or b.get("about") or "").strip(), "about": (b.get("about") or "").strip(),
                "look": look, "font": ui.get("display_font") or ui.get("font"), "body_font": ui.get("font"),
                "fonts": brand_fonts(b), "image": _data_uri(img),
                "img_ratio": round(Image.open(img).width / Image.open(img).height, 3),
                "jobs": rows, "more": max(0, len(jobs) - len(rows)), "total_jobs": len(jobs),
                "credit": "이미지 " + (b.get("credit") or "").replace("사진: ", "").split(" · ")[0]
                          if (b.get("credit") or "").startswith("사진") else f"이미지 {name} 공식 자료",
            })
            index.append({"name": name, "accent": look["bg"], "ink": look["ink"], "n": len(jobs), "top": rows[0]["title"]})
    total = sum(p["total_jobs"] for p in pages)
    note = f"@devjobseeker 수집 · {today:%Y.%m.%d} 기준 모집중 개발 공고 · 사이트 간 중복 제외"
    cover = {"type": "cover", "kicker": f"WEEKLY · {today:%Y.%m.%d}",
             "title": ["지금 개발자를", "찾는 회사들"], "sub": f"{len(pages)}곳 · 모집중 {total}건 — 넘기면 회사마다 한 장",
             "tiles": [{"image": p["image"], "bg": p["look"].get("object_bg") or p["look"]["bg"], "mode": p["look"]["mode"],
                        "name": p["name"]} for p in pages], "index": index}
    end = {"type": "end", "title": "저장해 두고\n지원 전에 다시 보세요", "index": index,
           "lines": ["이 회사에 가고 싶은 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]}
    slides = [cover, *pages, end]
    for s in slides:
        s["note"] = note
    caption = "\n\n".join([
        "[이번 주의 회사] 지금 개발자를 찾는 회사들",
        *(f"{p['name']} — {p['slogan'].splitlines()[0]}\n" + "\n".join(f"· {r['title']} ({r['meta']})" for r in p["jobs"])
          + (f"\n· 외 {p['more']}건" if p["more"] else "") for p in pages),
        note + ".",
        "이미지: 각 회사 공식 자료(" + " · ".join(p["credit"].removeprefix("이미지 ") for p in pages) + ")",
    ])
    return {"id": f"brands-{today:%Y%m%d}", "title": "이번 주의 회사", "series": "[이번 주의 회사]",
            "slides": slides, "caption": caption}


def _home(path: str) -> dict:
    """뷰어 API(정본 DB) — 메인 화면과 같은 숫자."""
    import urllib.request
    base = os.environ.get("VIEWER_API", "http://127.0.0.1:8771")
    with urllib.request.urlopen(base + path, timeout=30) as r:
        return json.loads(r.read())


_NOT_JOB = re.compile(r"국비|교육생|훈련생|부트캠프|아카데미|수강생|무료\s*취업")


def build_finance(today: date | None = None) -> dict:
    """[카드뉴스] 금융권 IT — 은행 공채 보도(몇 명·짧은 접수)와 우리 메인의 '은행·금융' 구역(상시 공고)을 견준다.
    바깥 보도는 요약과 출처만, 숫자는 만들 때 API 에서 다시 센다. 교육과정 모집은 공고가 아니라 뺀다."""
    from urllib.parse import quote
    today = today or date.today()
    board = _home("/api/home?industry=" + quote("금융") + "&limit=200")
    # 국내 금융권만 — 업종 필터에는 해외 핀테크(Stripe·Robinhood…)도 들어온다
    cos = [c for c in board["companies"] if not _NOT_JOB.search(c["name"]) and c["size"] != "해외 기업"]
    sec = _home("/api/home/section/" + quote("ind:금융"))
    names = {c["name"] for c in cos}
    jobs = [j for j in sec["jobs"] if not _NOT_JOB.search(j["title"] + j["company"]) and j["size"] != "해외 기업"]
    total = sum(c["active"] for c in cos)
    entry = [j for j in jobs if j["career_bucket"] == "신입/무관"]
    top = sorted(cos, key=lambda c: -c["active"])[:6]
    picks = []
    for j in entry:
        if j["company"] in {p["co"] for p in picks}:
            continue
        meta = "신입 가능" + (f" · D-{j['dday']}" if j.get("dday") is not None and j["dday"] >= 0 else " · 상시")
        picks.append({"co": j["company"], "title": _short(j["title"]), "meta": meta})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 공고 · {today:%Y.%m.%d} · 업종은 회사 이름으로 가른 추정"
    slides = [
        {"type": "cover", "photo": "seoul.jpg", "kicker": f"금융권 IT · {today:%Y.%m.%d}",
         "big": f"{total:,}", "unit": "건", "title": ["지금 열려 있는", "금융권 IT 자리"],
         "sub": f"국내 은행·증권·카드·핀테크 {len(cos)}곳"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "공채는", "title": "적게, 짧게 뽑는다",
         "items": [{"num": "6", "unit": "명", "label": "IBK기업은행 하반기 디지털·IT 채용(9/4~9/21 접수)"},
                   {"num": f"{total:,}", "unit": "건", "label": "같은 때 상시로 열려 있는 금융권 IT 공고(우리 사이트)"}],
         "explain": "공채만 기다리면 기회가 몇 번 안 온다. 핀테크·증권 쪽은 수시로 연다."},
        {"type": "bars", "photo": "typing.jpg", "kicker": "어디가", "title": f"가장 많이 뽑는 곳, {top[0]['name']}",
         "sub": "회사별 모집중 IT 공고 수", "rows": [{"label": c["name"], "value": c["active"]} for c in top]},
        {"type": "picks", "photo": "pangyo.jpg", "kicker": "신입이라면", "title": "신입도 넣을 수 있는 금융 IT",
         "sub": f"금융권 IT 공고 중 신입 가능 {len(entry)}건에서", "rows": picks},
        {"type": "end", "photo": "seoul.jpg", "kicker": "저장해 두기", "title": "공채 공지만 보지 말고\n상시 공고도 같이 보세요",
         "lines": ["금융권 취업을 준비하는 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    caption = "\n\n".join([
        f"국내 금융권 IT 자리, 지금 {total:,}건이 열려 있습니다({len(cos)}곳).",
        "은행 공채는 적게, 짧게 뽑습니다 — IBK기업은행 하반기 디지털·IT 채용은 6명, 접수는 9월 4일~21일이었습니다"
        "(파이낸셜뉴스·스마트투데이 보도). 우리은행도 하반기 신입행원 TECH 부문을 따로 뽑았습니다.",
        "가장 많이 뽑는 곳: " + " · ".join(f"{c['name']} {c['active']}건" for c in top[:5]),
        "신입 가능: " + " · ".join(f"{p['co']}" for p in picks),
        "출처\nhttps://www.fnnews.com/news/202609071416059562\nhttps://www.smarttoday.co.kr/ko-kr/articles/111273",
        f"{today:%Y.%m.%d} JD Viewer 모집중 공고 기준. 업종은 회사 이름으로 가른 추정이고 교육과정 모집은 뺐습니다. 전체는 프로필 링크에서.",
    ])
    return {"id": f"finance-{today:%Y%m%d}", "series": "[금융권 IT]", "title": "금융권 IT 자리", "slides": slides, "caption": caption}


def build_intern(today: date | None = None) -> dict:
    """[카드뉴스] 인턴·교육생 — 채용연계형 인턴 보도(교보증권 IT 인턴, 아시아경제)와 메인 '인턴·교육생' 구역을 견준다.
    '전환형'·'채용연계' 는 공고 본문에서 찾은 건수라 그 말 그대로 적는다(인턴만 센 것이 아니다)."""
    from urllib.parse import quote, urlencode
    today = today or date.today()
    sec = _home("/api/home/section/intern")
    jobs = [j for j in sec["jobs"] if not _NOT_JOB.search(j["title"] + j["company"]) and j["size"] != "해외 기업"]
    conv = _home("/api/jobs?" + urlencode({"q": "전환형", "limit": 1}))["total"]
    link = _home("/api/jobs?" + urlencode({"q": "채용연계", "limit": 1}))["total"]
    big = [j for j in jobs if j["size"] in ("대기업", "중견기업")]
    picks, seen = [], set()
    for j in big + jobs:
        if j["company"] in seen:
            continue
        seen.add(j["company"])
        d = j.get("dday")
        when = "오늘 마감" if d == 0 else f"D-{d}" if d is not None and d > 0 else "상시"
        meta = when + (f" · {j['size']}" if j.get("size") else "")
        picks.append({"co": j["company"], "title": _short(j["title"]), "meta": meta})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 IT 공고 · {today:%Y.%m.%d}"
    slides = [
        {"type": "cover", "photo": "pangyo.jpg", "kicker": f"인턴·교육생 · {today:%Y.%m.%d}",
         "big": f"{sec['total']:,}", "unit": "건", "title": ["지금 열린", "IT 인턴·교육생 자리"],
         "sub": "제목에 인턴·교육생·체험형·채용연계가 적힌 IT 공고"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "전환되는 자리", "title": "인턴 뒤에 정규직이 있나",
         "items": [{"num": f"{conv}", "unit": "건", "label": "공고에 '전환형' 을 적은 곳"},
                   {"num": f"{link}", "unit": "건", "label": "공고에 '채용연계' 를 적은 곳"}],
         "explain": "교보증권은 IT 부문 채용연계형 인턴을 6주 동안 돌린 뒤 최종면접으로 정규직을 뽑았다(보도). 인턴 공고는 '전환' 여부부터 확인하자."},
        {"type": "picks", "photo": "typing.jpg", "kicker": "눈여겨볼 곳", "title": "큰 회사의 IT 인턴",
         "sub": "대기업·중견기업 먼저, 회사마다 한 건", "rows": picks},
        {"type": "end", "photo": "seoul.jpg", "kicker": "저장해 두기", "title": "인턴 공고는 짧게 열린다\n보면 바로 넣으세요",
         "lines": ["인턴 찾는 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    caption = "\n\n".join([
        f"지금 열린 IT 인턴·교육생 자리 {sec['total']:,}건.",
        f"공고에 '전환형' 을 적은 곳 {conv}건, '채용연계' 를 적은 곳 {link}건 — 인턴 공고는 정규직 전환 여부부터 보세요.",
        "교보증권은 IT 부문(시스템·DevOps·클라우드·보안) 채용연계형 인턴을 6주 동안 진행한 뒤 최종면접으로 정규직을 뽑았습니다"
        "(아시아경제 보도, 2026.1).",
        "큰 회사의 IT 인턴: " + " · ".join(p["co"] for p in picks),
        "출처\nhttps://core.asiae.co.kr/article/2026011610121895195",
        f"{today:%Y.%m.%d} JD Viewer 모집중 IT 공고 기준. '전환형'·'채용연계' 는 공고 본문에서 찾은 건수입니다. 전체는 프로필 링크에서.",
    ])
    return {"id": f"intern-{today:%Y%m%d}", "series": "[인턴·교육생]", "title": "IT 인턴·교육생", "slides": slides,
            "caption": caption}


def _is_mid(career: str) -> bool:
    """3~7년차 자리로 볼 경력 표기 — 첫 숫자(최소 연차)가 3~7. '2~5년'·'5년↓'(이하)는 아니다."""
    m = re.search(r"\d+", career or "")
    return bool(m) and 3 <= int(m.group()) <= 7 and not re.search(r"↓|이하", career)


def build_midlevel(today: date | None = None) -> dict:
    """[카드뉴스] 3~8년차 — 잡코리아 '미들급 편' 설문(체감 난이도·TO 있어도 안 뽑는다·서류 탈락)과
    지금 경력 조건이 3~7년인 국내 공고 수를 견준다. 설문 숫자는 출처를 적고 원문을 옮기지 않는다."""
    import psycopg
    from psycopg.rows import dict_row
    from .collection import _DEV_SIGNAL
    today = today or date.today()
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        rows = conn.execute("""
            SELECT f.career_bucket AS b, count(*) AS n
              FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
              JOIN job_facet f ON f.job_id = j.id
             WHERE coalesce(f.region, '') <> '해외·원격'
               AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)
             GROUP BY 1""").fetchall()
    c = {r["b"]: r["n"] for r in rows}
    stated = sum(n for b, n in c.items() if b != "정보없음")
    mid = c.get("3-4년", 0) + c.get("5-7년", 0)
    entry = c.get("신입/무관", 0)
    pct = lambda a: round(100 * a / stated) if stated else 0
    sec = _home("/api/home/section/experienced")
    picks, seen = [], set()
    for j in sec["jobs"]:
        t = j["title"]
        if (j["company"] in seen or j["size"] not in ("대기업", "중견기업") or not _is_mid(j.get("career"))
                or not _DEV_SIGNAL.search(t) or re.search(r"\bPM\b|기획|함정", t)):
            continue
        seen.add(j["company"])
        d = j.get("dday")
        when = "오늘 마감" if d == 0 else f"D-{d}" if d is not None and 0 < d <= 365 else "상시"
        picks.append({"co": j["company"], "title": _short(re.sub(r"^\[[^\]]*\]\s*", "", t)),
                      "meta": f"{when} · {j['career']}"})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 · {today:%Y.%m.%d}"
    slides = [
        {"type": "cover", "photo": "seoul.jpg", "kicker": f"3~8년차 · {today:%Y.%m.%d}",
         "big": f"{mid:,}", "unit": "건", "title": ["어렵다는 3~8년차", "지금 열린 자리"],
         "sub": "경력 조건이 3~7년인 국내 IT 모집중 공고"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "설문", "title": "3~8년차가 느끼는 시장",
         "items": [{"num": "93", "unit": "%", "label": "2년 전보다 어려워졌다"},
                   {"num": "48", "unit": "%", "label": "자리가 있어도 안 뽑는다"},
                   {"num": "56", "unit": "%", "label": "서류에서 막힌다"}],
         "explain": "잡코리아가 3~8년차 개발자 1,000명에게 물었다(2026.7). 주니어·시니어보다 '어려워졌다' 가 많았다."},
        {"type": "stat", "photo": "code.jpg", "kicker": "공고로 보면", "title": "자리는 경력자 쪽에 더 많다",
         "items": [{"num": f"{pct(mid)}", "unit": "%", "label": f"경력 3~7년 공고 {mid:,}건"},
                   {"num": f"{pct(entry)}", "unit": "%", "label": f"신입 가능 공고 {entry:,}건"}],
         "explain": f"경력 조건을 적은 {stated:,}건 기준. 문은 열려 있다 — 막히는 곳은 서류다."},
        {"type": "picks", "photo": "typing.jpg", "kicker": "눈여겨볼 곳", "title": "큰 회사의 3~7년차 자리",
         "sub": "대기업·중견기업, 회사마다 한 건", "rows": picks},
        {"type": "end", "photo": "pangyo.jpg", "kicker": "저장해 두기", "title": "서류에서 막힌다면\n공고 문장부터 맞추자",
         "lines": ["이직 준비하는 동료에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    slides[1]["note"] = "잡코리아 '2026 하반기 개발자 취업 현황 리포트 · 미들급 편'(2026.7.30) 요약"
    caption = "\n\n".join([
        f"3~8년차는 어렵다고 합니다. 그런데 지금 경력 조건이 3~7년인 국내 IT 공고는 {mid:,}건입니다.",
        f"· 경력 조건을 적은 {stated:,}건 중 3~7년 {mid:,}건({pct(mid)}%), 신입 가능 {entry:,}건({pct(entry)}%)",
        "잡코리아가 3~8년차 개발자 1,000명에게 물었더니 93%가 2년 전보다 어려워졌다고 했고, 48%는 자리가 있어도 "
        "안 뽑는다고 느꼈으며, 가장 많이 막히는 단계는 서류(56%)였습니다.",
        "큰 회사의 3~7년차 자리: " + " · ".join(p["co"] for p in picks),
        "출처\nhttps://www.jobkorea.co.kr/recruit/careers/articles/midlevel-developer",
        f"{today:%Y.%m.%d} JD Viewer 모집중 IT 공고(국내 근무, 사이트 간 중복 제외) 기준. 경력은 공고에 적힌 최소 연차로 나눴습니다.",
    ])
    return {"id": f"midlevel-{today:%Y%m%d}", "series": "[3~8년차]", "title": "3~8년차 자리", "slides": slides,
            "caption": caption}


BUILDERS = {"weekly": build_weekly, "brands": build_brands, "finance": build_finance, "intern": build_intern, "midlevel": build_midlevel}


# --- 렌더 ---------------------------------------------------------------
def render(post: dict, style: str) -> list[Path]:
    from .render import _page_maker

    tpl = (TPL_DIR / f"{style}.html").read_text(encoding="utf-8")
    common = (TPL_DIR / "_common.js").read_text(encoding="utf-8")
    tpl = tpl.replace("/*__COMMON__*/", common)
    base_fonts = _font_faces(STYLE_FONTS[style])
    dest = OUT / post["id"] / style
    dest.mkdir(parents=True, exist_ok=True)
    paths, n = [], len(post["slides"])
    for i, s in enumerate(post["slides"], 1):
        data = {"series": post["series"], "page": i, "total": n, "slide": s, "size": list(SIZE)}
        # 회사 장은 그 회사 서체를 더 박는다(carousel._font_faces 가 만든 @font-face)
        faces = base_fonts + "\n" + s.get("fonts", "")
        data["slide"] = {k: v for k, v in s.items() if k != "fonts"}
        html = tpl.replace("/*__FONTS__*/", faces).replace(
            "/*__DATA__*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
        page = _page_maker().new_page(viewport={"width": SIZE[0], "height": SIZE[1]})
        try:
            page.set_content(html, wait_until="load")
            page.wait_for_function("window.__ready === true", timeout=30000)
            bad, small = page.evaluate("[window.__overflow, window.__minBody]")
            if bad or small < 18:
                print(f"[newscard] {style} {i}장: 넘침={bad} 최소 글자 {small:.0f}px")
            p = dest / f"{i:02d}.jpg"
            page.query_selector(".sheet").screenshot(path=str(p), type="jpeg", quality=92)
            paths.append(p)
        finally:
            page.close()
    return paths


def _label_font(size: int) -> ImageFont.FreeTypeFont:
    for f in ("assets/companies/네이버웹툰/fonts/GothicA1-Black.ttf", "C:/Windows/Fonts/malgunbd.ttf"):
        if (LAB_DIR / f).is_file() or Path(f).is_file():
            return ImageFont.truetype(str(LAB_DIR / f) if (LAB_DIR / f).is_file() else f, size)
    return ImageFont.load_default()


def board(post: dict, shots: dict[str, list[Path]]) -> Path:
    """틀 × 장 한 장. 한 줄이 한 틀이다 — 줄끼리 견주면 된다."""
    tw, th, gap, head = 360, 450, 24, 70
    cols = max(len(v) for v in shots.values())
    W = 260 + cols * (tw + gap)
    H = 40 + len(shots) * (th + head + gap)
    sheet = Image.new("RGB", (W, H), "#ececea")
    d = ImageDraw.Draw(sheet)
    f_big, f_small = _label_font(34), _label_font(20)
    y = 40
    for style, paths in shots.items():
        d.text((30, y + 10), style, fill="#111", font=f_big)
        d.text((30, y + 54), STYLES[style].split(" — ")[0], fill="#555", font=f_small)
        for k, p in enumerate(paths):
            im = Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS)
            sheet.paste(im, (260 + k * (tw + gap), y))
        y += th + head + gap
    out = OUT / post["id"] / "_board.jpg"
    sheet.save(out, quality=88)
    return out


def feed(post: dict, shots: dict[str, list[Path]]) -> Path:
    """피드 3×3 — 틀마다 표지 한 장씩 번갈아 올렸을 때. 프로필 격자는 4:5 를 3:4 로 자른다(2025~)."""
    # 틀이 하나면 그 틀의 장들을 차례로 — 회사 장이 피드에서 어떻게 번갈아 보이나
    covers = [paths[0] for paths in shots.values()] if len(shots) > 1 else next(iter(shots.values()))
    cells = [covers[i % len(covers)] for i in range(9)]
    cw, ch, g = 360, 480, 4
    sheet = Image.new("RGB", (cw * 3 + g * 2, ch * 3 + g * 2), "#fff")
    for i, p in enumerate(cells):
        im = Image.open(p).convert("RGB")
        w, h = im.size
        crop_h = int(w * 4 / 3)
        top = (h - crop_h) // 2
        im = im.crop((0, top, w, top + crop_h)).resize((cw, ch), Image.LANCZOS)
        sheet.paste(im, ((i % 3) * (cw + g), (i // 3) * (ch + g)))
    out = OUT / post["id"] / "_feed.jpg"
    sheet.save(out, quality=88)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=sorted(BUILDERS))
    ap.add_argument("--styles", nargs="*", choices=list(STYLES))
    ap.add_argument("--approve", metavar="STYLE", help="이 틀로 찍은 장을 승인함(inbox)에 넣는다 — 고른 뒤에만")
    a = ap.parse_args()
    from .render import shutdown

    post = BUILDERS[a.what]()
    (OUT / post["id"]).mkdir(parents=True, exist_ok=True)
    (OUT / post["id"] / "caption.txt").write_text(post["caption"], encoding="utf-8")
    try:
        shots = {s: render(post, s) for s in (a.styles or DEFAULT_STYLES[a.what])}
    finally:
        shutdown()
    print(board(post, shots))
    print(feed(post, shots))
    if a.approve:
        print(f"[newscard] 승인함 → {approve(post, shots[a.approve])}")
    return 0


def approve(post: dict, paths: list[Path]) -> Path:
    """고른 틀의 장들을 승인함에 넣는다 — series.approve 와 같은 모양(발행 데몬·'이미 낸 것' 판단이 이 모양을 읽는다)."""
    import shutil
    import socket
    import uuid
    from datetime import datetime
    item = uuid.uuid4().hex[:8]
    d = LAB_DIR / "inbox" / item
    d.mkdir(parents=True)
    shutil.copyfile(paths[0], d / "poster.jpg")
    for i, p in enumerate(paths[1:], 1):
        shutil.copyfile(p, d / f"slide_{i:02d}.jpg")
    cap = post["caption"]
    (d / "caption_instagram.txt").write_text(cap, encoding="utf-8")
    bundle = {"id": item, "job_key": f"collection:{post['id']}", "company": post["series"], "role": post["title"],
              "template": "newscard", "platforms": ["instagram"], "captions": {"instagram": cap}, "caption": cap,
              "note": "newscard", "force": False,
              "collection": {"id": post["id"], "kind": "newscard", "title": post["title"], "count": 0, "jobs": []},
              "format": "carousel", "approved_on": socket.gethostname(),
              "approved_at": datetime.now().isoformat(timespec="seconds")}
    (d / "bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


if __name__ == "__main__":
    raise SystemExit(main())
