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
import collections
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
DEFAULT_STYLES = {"weekly": ["magazine", "paper", "poster", "scrap"], "brands": ["brandmag"], "finance": ["magazine"], "intern": ["magazine"], "midlevel": ["magazine"], "japan": ["magazine"], "military": ["magazine"], "region": ["magazine"], "sme": ["magazine"], "fourday": ["magazine"], "secneed": ["magazine"], "db": ["magazine"], "k8s": ["magazine"], "linux": ["magazine"], "nextjs": ["magazine"], "vue": ["magazine"]}


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


#: 근무지가 일본인 공고 — 지역 칸에 일본 지명이 있거나 제목에 '도쿄 근무'·'근무지 일본' 처럼 적은 것.
#: '일본 IP 프로젝트'(서울 근무) 처럼 일본이 근무지가 아닌 제목은 뺀다.
_JP_LOC = re.compile(r"일본|도쿄|東京|tokyo|japan|오사카|osaka|후쿠오카|fukuoka|사이타마|가나가와", re.I)
_JP_TITLE = re.compile(r"도쿄|東京|tokyo|오사카|후쿠오카|근무지\s*일본|일본\s*(현지|근무|에서)|\[일본", re.I)


def build_japan(today: date | None = None) -> dict:
    """[카드뉴스] 일본 취업 — '일본이 미국을 제치고 해외취업 1위, 한국인 IT 종사자 1만여 명'(한국경제 2025.11.4,
    한국노동연구원 노동리뷰 인용)과 지금 근무지가 일본인 모집중 IT 공고를 견준다."""
    import psycopg
    from psycopg.rows import dict_row
    from .collection import _AGENCY
    today = today or date.today()
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        rows = conn.execute("""
            SELECT c.display_name AS co, j.title, coalesce(j.location_text, '') AS loc, f.career_bucket AS b,
                   coalesce(j.full_jd, '') AS jd, j.deadline_on
              FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
              JOIN job_facet f ON f.job_id = j.id JOIN company c ON c.id = j.company_id
             WHERE NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""").fetchall()
    jp = [r for r in rows if (_JP_LOC.search(r["loc"]) or _JP_TITLE.search(r["title"]))
          and not re.search(r"일본\s*IP", r["title"]) and not _AGENCY.search(r["co"] + " " + r["title"])
          and not (r["deadline_on"] and r["deadline_on"] < today)]
    n = len(jp)
    lang = sum(1 for r in jp if re.search(r"일본어|JLPT|日本語|Japanese", r["title"] + r["jd"], re.I))
    entry = sum(1 for r in jp if r["b"] == "신입/무관")

    def who(r):   # 원티드 '일본 현지 채용' 은 채널 이름이다 — 실제 회사는 제목 대괄호에 있다
        m = re.match(r"\s*\[([^\]]+)\]", r["title"])
        if "현지 채용" in r["co"] and m:
            return re.sub(r"株式会社|\s+", "", m.group(1)) or m.group(1)
        c = re.sub(r"\(영업소\)", "", _co(r["co"])).strip()
        return c if len(c) > 1 else re.sub(r"\(영업소\)", "", r["co"]).strip()   # '칼' 한 글자는 '칼주식회사' 로
    picks, seen = [], set()
    for r in sorted(jp, key=lambda r: (r["deadline_on"] is None, r["deadline_on"] or today)):
        c = who(r)
        # 인력 소개 회사(마이나비·에이치알글로벌네트워크)는 건수에는 넣고 '눈여겨볼 곳' 에는 실제 고용주만 둔다
        if c in seen or re.search(r"마이나비|에이치알|HR|인재|리크루트|파견|글로벌네트워크", c):
            continue
        seen.add(c)
        d = (r["deadline_on"] - today).days if r["deadline_on"] else None
        when = "오늘 마감" if d == 0 else f"D-{d}" if d is not None else "상시"
        title = re.sub(r"^\s*\[[^\]]*\]\s*", "", r["title"])
        picks.append({"co": c, "title": _short(title), "meta": when})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 IT 공고 · {today:%Y.%m.%d}"
    slides = [
        {"type": "cover", "photo": "css.jpg", "kicker": f"일본 취업 · {today:%Y.%m.%d}",
         "big": f"{n}", "unit": "건", "title": ["해외 취업 1위 일본", "지금 열린 IT 자리"],
         "sub": "근무지가 일본인 모집중 IT 공고"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "보도", "title": "일본이 한국 IT 인재를 찾는다",
         "items": [{"num": "1만", "unit": "여 명", "label": "일본에서 일하는 한국인 IT 종사자"},
                   {"num": "13.4", "unit": "%", "label": "일본 내 한국인 취업자 중 IT 비중"},
                   {"num": "3.45", "unit": "배", "label": "일본 IT 기술자 구인배율(2025)"}],
         "explain": "고령화와 디지털 전환으로 일본 기업이 IT 인력을 찾으면서, 일본이 미국을 제치고 한국인 해외 취업 1위가 됐다."},
        {"type": "stat", "photo": "code.jpg", "kicker": "공고로 보면", "title": "일본 근무 공고에 적힌 것",
         "items": [{"num": f"{lang}", "unit": "건", "label": f"{n}건 중 일본어를 적은 공고"},
                   {"num": f"{entry}", "unit": "건", "label": "신입도 되는 공고"}],
         "explain": f"{round(100 * lang / n) if n else 0}%가 일본어를 적었다. 지원 전에 공고에서 요구 수준부터 확인하자."},
        {"type": "picks", "photo": "typing.jpg", "kicker": "눈여겨볼 곳", "title": "근무지가 일본인 자리",
         "sub": "마감이 가까운 순, 회사마다 한 건", "rows": picks},
        {"type": "end", "photo": "pangyo.jpg", "kicker": "저장해 두기", "title": "해외 취업을 생각한다면\n일본 공고부터 보자",
         "lines": ["일본 취업 준비하는 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    slides[1]["note"] = "한국경제 2025.11.4 보도(한국노동연구원 노동리뷰 2025년 10월호 인용) 요약"
    caption = "\n\n".join([
        f"한국인 해외 취업 1위는 이제 일본입니다. 지금 근무지가 일본인 IT 공고는 {n}건이에요.",
        f"· 일본어를 적은 공고 {lang}건 · 신입도 되는 공고 {entry}건\n· 눈여겨볼 곳: " + " · ".join(p["co"] for p in picks),
        "한국경제는 한국노동연구원 자료를 인용해, 일본이 미국을 제치고 한국인 해외 취업 1위가 됐고 일본에서 일하는 "
        "한국인 IT 종사자가 1만여 명(한국인 취업자의 13.4%)이라고 전했습니다. 일본의 IT 기술자 구인배율은 3.45배였습니다.",
        "출처\nhttps://www.hankyung.com/article/202511042453i",
        f"{today:%Y.%m.%d} JD Viewer 모집중 IT 공고 기준. 근무지에 일본 지명이 있거나 제목에 일본 근무를 적은 공고만 셌고, "
        "헤드헌팅 공고는 뺐습니다.",
    ])
    return {"id": f"japan-{today:%Y%m%d}", "series": "[일본 취업]", "title": "일본 근무 IT 공고", "slides": slides,
            "caption": caption}


_MIL = re.compile(r"병역\s*특[례레]|산업기능요원|전문연구요원")


def build_military(today: date | None = None) -> dict:
    """[카드뉴스] 병역특례 — 병무청 2026 배정(산업기능요원 3,200·전문연구요원 2,300, 뉴스서울 2025.6.2)과
    AI 분야 대기업 전문연구요원 2027 재도입 보도(시대에듀 2026.9.20)를, 지금 병역특례를 제목에 건 IT 공고로 받친다.
    같은 자리를 여러 사이트에 올린 것은 하나로 센다(series._role_key)."""
    import psycopg
    from psycopg.rows import dict_row
    from .collection import _AGENCY, _not_dev
    from .series import _role_key
    today = today or date.today()
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        rows = conn.execute("""
            SELECT f.stacks, c.display_name AS co, j.title, coalesce(j.full_jd, '') AS jd, f.career_bucket AS b, j.deadline_on
              FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
              JOIN job_facet f ON f.job_id = j.id JOIN company c ON c.id = j.company_id
             WHERE coalesce(f.region, '') <> '해외·원격'
               AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""").fetchall()
    rows = [r for r in rows if not _not_dev({"title": r["title"], "stack": r.get("stacks") or []}) and not _AGENCY.search(r["co"] + r["title"])
            and not (r["deadline_on"] and r["deadline_on"] < today)]
    titled = [r for r in rows if _MIL.search(r["title"])]
    uniq = {}
    for r in titled:
        uniq.setdefault((_co(r["co"]).split("(")[0], _role_key(r["title"])), r)
    jobs = list(uniq.values())
    n, body = len(jobs), sum(1 for r in rows if not _MIL.search(r["title"]) and _MIL.search(r["jd"]))
    expert = sum(1 for r in jobs if "전문연구" in r["title"] + r["jd"])
    industrial = sum(1 for r in jobs if "산업기능" in r["title"] + r["jd"])
    picks, seen = [], set()
    for r in sorted(jobs, key=lambda r: (r["deadline_on"] is None, r["deadline_on"] or today)):
        c = _co(r["co"]).split("(")[0]
        if c in seen:
            continue
        d = (r["deadline_on"] - today).days if r["deadline_on"] else None
        if d == 0:          # 오늘 닫히는 자리는 올라갈 때쯤 이미 닫혀 있다
            continue
        seen.add(c)
        when = f"D-{d}" if d is not None else "상시"
        kind = ("전문연구요원" if "전문연구" in r["title"] else "산업기능요원" if "산업기능" in r["title"]
                else "병역특례")   # '병역특례 가능' 만 적은 공고에 종류를 지어 붙이지 않는다
        title = re.sub(r"^\s*\[[^\]]*\]\s*", "", r["title"])
        picks.append({"co": c, "title": _short(title), "meta": f"{when} · {kind}"})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 · {today:%Y.%m.%d} · 같은 자리 중복 게시는 하나로"
    slides = [
        {"type": "cover", "photo": "typing.jpg", "kicker": f"병역특례 · {today:%Y.%m.%d}",
         "big": f"{n}", "unit": "개", "title": ["군대 대신 개발", "병역특례 IT 자리"],
         "sub": "제목에 산업기능요원·전문연구요원을 건 모집중 IT 공고"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "병무청 배정", "title": "2026년 자리는 정해져 있다",
         "items": [{"num": "3,200", "unit": "명", "label": "산업기능요원"},
                   {"num": "2,300", "unit": "명", "label": "전문연구요원"},
                   {"num": "−200", "unit": "명", "label": "전체 배정, 전년보다"}],
         "explain": "2027년부터는 AI 분야 대기업 연구소에도 전문연구요원을 한시로 다시 배정한다(14년 만)."},
        {"type": "stat", "photo": "code.jpg", "kicker": "공고로 보면", "title": "어떤 특례를 적었나",
         "items": [{"num": f"{industrial}", "unit": "개", "label": "산업기능요원을 적은 자리"},
                   {"num": f"{expert}", "unit": "개", "label": "전문연구요원을 적은 자리"}],
         "explain": f"둘 다 받는 자리는 양쪽에 셌다. 제목엔 없고 본문에만 적은 공고도 {body}건 더 있다."},
        {"type": "picks", "photo": "seoul.jpg", "kicker": "눈여겨볼 곳", "title": "병역특례 IT 자리",
         "sub": "마감이 가까운 순, 회사마다 한 건", "rows": picks},
        {"type": "end", "photo": "pangyo.jpg", "kicker": "저장해 두기", "title": "편입 조건(현역·보충역)은\n공고마다 다르다",
         "lines": ["입대 앞둔 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    slides[1]["note"] = "병무청 2026년도 배정(뉴스서울 2025.6.2) · AI 전문연구요원 재도입(시대에듀 2026.9.20) 요약"
    caption = "\n\n".join([
        f"군대 대신 개발 — 지금 제목에 병역특례를 건 IT 자리는 {n}개입니다(같은 자리를 여러 사이트에 올린 것은 하나로).",
        f"· 산업기능요원을 적은 자리 {industrial}개 · 전문연구요원 {expert}개\n· 본문에만 적은 공고도 {body}건\n"
        "· 눈여겨볼 곳: " + " · ".join(p["co"] for p in picks),
        "병무청은 2026년도 산업기능요원 3,200명, 전문연구요원 2,300명(승선근무예비역 포함 전체 6,300명, 전년보다 200명 감소)을 "
        "배정했습니다(뉴스서울). 또 2027년부터 3년간 AI 분야 대기업 연구소에 전문연구요원을 한시로 다시 배정한다고 합니다"
        "(2013년 폐지 뒤 14년 만, 시대에듀 보도).",
        "출처\nhttps://www.newsseoul.co.kr/news/view/1065584418219013\nhttps://www.sidae.com/article/2026092013412756768",
        f"{today:%Y.%m.%d} JD Viewer 모집중 IT 공고(국내 근무) 기준. 편입 조건은 공고마다 다르니 원문을 확인하세요.",
    ])
    return {"id": f"military-{today:%Y%m%d}", "series": "[병역특례]", "title": "병역특례 IT 자리", "slides": slides,
            "caption": caption}


_CAPITAL = ("서울", "경기", "인천")


def build_region(today: date | None = None) -> dict:
    """[카드뉴스] 수도권 쏠림 — R&D 비·인력 약 70% 가 수도권(SBS Biz 2025.9.30, 경성대 김종한 교수 보고서)을
    지금 국내 IT 공고의 근무지로 확인한다. 근무지를 모르는 공고는 분모에서 뺀다."""
    import psycopg
    from psycopg.rows import dict_row
    from .collection import _AGENCY, _not_dev
    today = today or date.today()
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        rows = conn.execute("""
            SELECT c.display_name AS co, j.title, f.region, f.district, f.company_size AS size, j.deadline_on, f.career_bucket AS b, f.stacks
              FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
              JOIN job_facet f ON f.job_id = j.id JOIN company c ON c.id = j.company_id
             WHERE coalesce(f.region, '정보없음') NOT IN ('해외·원격', '정보없음')
               AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""").fetchall()
    rows = [r for r in rows if not _not_dev({"title": r["title"], "stack": r["stacks"] or []}) and not _AGENCY.search(r["co"] + r["title"])
            and not (r["deadline_on"] and r["deadline_on"] < today)]
    n = len(rows)
    cap = sum(1 for r in rows if r["region"] in _CAPITAL)
    by = collections.Counter(r["region"] for r in rows if r["region"] not in _CAPITAL).most_common(3)
    local = [r for r in rows if r["region"] not in _CAPITAL]
    pct = lambda a: round(100 * a / n) if n else 0
    picks, seen = [], set()
    for r in sorted(local, key=lambda r: ({"대기업": 0, "중견기업": 1}.get(r["size"], 2),
                                          r["deadline_on"] is None, r["deadline_on"] or today)):
        c = _co(r["co"])
        d = (r["deadline_on"] - today).days if r["deadline_on"] else None
        if c in seen or d == 0:
            continue
        seen.add(c)
        when = f"D-{d}" if d is not None else "상시"
        place = r["region"] + (f" {r['district']}" if r["district"] else "")
        picks.append({"co": c, "title": _short(re.sub(r"^\s*\[[^\]]*\]\s*", "", r["title"])),
                      "meta": f"{place} · {when}"})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 IT 공고 · 근무지를 적은 국내 공고 {n:,}건 · {today:%Y.%m.%d}"
    slides = [
        {"type": "cover", "photo": "seoul.jpg", "kicker": f"지역별 채용 · {today:%Y.%m.%d}",
         "big": f"{pct(cap)}", "unit": "%", "title": [f"IT 공고 열에 {'일곱여덟아홉'[(round(pct(cap) / 10) - 7) * 2:(round(pct(cap) / 10) - 7) * 2 + 2]}은" if 7 <= round(pct(cap) / 10) <= 9 else "IT 공고 대부분은", "수도권에 있다"],
         "sub": f"근무지가 서울·경기·인천인 모집중 IT 공고 {cap:,}건"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "보고서", "title": "연구개발도 수도권에 모였다",
         "items": [{"num": "70", "unit": "%", "label": "연구개발비·연구인력 중 수도권"},
                   {"num": "10", "unit": "년", "label": "좋은 일자리 격차를 본 기간"}],
         "explain": "경성대 김종한 교수의 'R&D 지역인재정책' 보고서(한국고용정보원 계간지). 격차는 10년 동안 커졌다."},
        {"type": "stat", "photo": "code.jpg", "kicker": "공고로 보면", "title": "수도권 밖에서 많은 곳",
         "items": [{"num": f"{k:,}", "unit": "건", "label": name} for name, k in by[:2]],
         "explain": f"수도권 밖 IT 공고는 모두 {len(local):,}건({100 - pct(cap)}%). 다음은 {by[2][0]} {by[2][1]}건." if len(by) > 2 else ""},
        {"type": "picks", "photo": "typing.jpg", "kicker": "눈여겨볼 곳", "title": "수도권 밖 IT 자리",
         "sub": "대기업·중견기업 먼저, 회사마다 한 건", "rows": picks},
        {"type": "end", "photo": "pangyo.jpg", "kicker": "저장해 두기", "title": "고향에서 개발하고 싶다면\n지역 공고부터 보자",
         "lines": ["지역에서 일자리 찾는 친구에게 보내 주세요", "지역별 공고는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    slides[1]["note"] = "SBS Biz 2025.9.30 보도(김종한 경성대 교수, '지역산업과 고용' 가을호) 요약"
    caption = "\n\n".join([
        f"IT 공고의 {pct(cap)}%는 수도권에 있습니다. 근무지를 적은 국내 IT 공고 {n:,}건 중 서울·경기·인천이 {cap:,}건이에요.",
        "· 수도권 밖에서 많은 곳: " + " · ".join(f"{k} {v}건" for k, v in by) + "\n"
        "· 눈여겨볼 곳: " + " · ".join(p["co"] for p in picks),
        "SBS Biz 는 경성대 김종한 교수의 보고서를 인용해 연구개발비와 연구인력의 약 70%가 수도권에 모여 있고, "
        "지난 10년 동안 좋은 일자리의 지역 격차가 커졌다고 전했습니다.",
        "출처\nhttps://biz.sbs.co.kr/amp/article/20000263110",
        f"{today:%Y.%m.%d} JD Viewer 모집중 IT 공고 기준. 근무지를 적지 않은 공고와 해외·원격 공고는 뺐습니다.",
    ])
    return {"id": f"region-{today:%Y%m%d}", "series": "[지역별 채용]", "title": "수도권 밖 IT 자리", "slides": slides,
            "caption": caption}


def build_sme(today: date | None = None) -> dict:
    """[카드뉴스] 중견·중소 신입 — 2026 청년일자리도약장려금(복지로 안내: 만 15~34세 정규직 채용·6개월 유지 시 기업 월 60만·
    최대 720만, 비수도권 청년 본인 480~720만)과 지금 중견·중소기업의 신입 IT 공고를 견준다. 숫자는 정본 DB 에서."""
    import psycopg
    from psycopg.rows import dict_row
    from .collection import _AGENCY, _FOREIGN_TAG, _not_dev
    from .series import _role_key
    today = today or date.today()
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        rows = conn.execute("""
            SELECT f.stacks, c.display_name AS co, j.title, f.region, f.district, f.company_size AS size, j.deadline_on
              FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
              JOIN job_facet f ON f.job_id = j.id JOIN company c ON c.id = j.company_id
             WHERE f.career_bucket = '신입/무관' AND coalesce(f.region, '') <> '해외·원격'
               AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""").fetchall()
    rows = [r for r in rows if not _not_dev({"title": r["title"], "stack": r["stacks"] or []})
            and not _AGENCY.search(r["co"] + r["title"]) and not _NOT_JOB.search(r["title"] + r["co"])
            and not _FOREIGN_TAG.match(r["title"])
            and not (r["deadline_on"] and r["deadline_on"] < today)]
    uniq = {}
    for r in rows:
        uniq.setdefault((_co(r["co"]), _role_key(r["title"])), r)
    rows = list(uniq.values())
    n = len(rows)
    sme = [r for r in rows if r["size"] in ("중견기업", "중소기업")]
    mid = sum(1 for r in sme if r["size"] == "중견기업")
    local = sum(1 for r in sme if r["region"] and r["region"] not in ("서울", "경기", "인천", "정보없음"))
    pct = lambda a: round(100 * a / n) if n else 0
    picks, seen = [], set()
    for r in sorted(sme, key=lambda r: (r["size"] != "중견기업", r["deadline_on"] is None, r["deadline_on"] or today)):
        c = _co(r["co"])
        d = (r["deadline_on"] - today).days if r["deadline_on"] else None
        if c in seen or d == 0:
            continue
        seen.add(c)
        when = f"D-{d}" if d is not None else "상시"
        picks.append({"co": c, "title": _short(re.sub(r"^\s*\[[^\]]*\]\s*", "", r["title"])),
                      "meta": f"{r['size']} · {r['region'] or ''} · {when}"})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 신입 IT 공고 · 국내 근무 · {today:%Y.%m.%d} · 같은 자리 중복 게시는 하나로 · 규모를 모르는 회사는 중소로 셈"
    slides = [
        {"type": "cover", "photo": "pangyo.jpg", "kicker": f"중견·중소 신입 · {today:%Y.%m.%d}",
         "big": f"{len(sme):,}", "unit": "개", "title": ["신입 IT 자리의", f"{pct(len(sme))}%는 중견·중소"],
         "sub": f"신입이 넣을 수 있는 국내 IT 자리 {n:,}개 중"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "정부 지원", "title": "2026 청년일자리도약장려금",
         "items": [{"num": "720", "unit": "만", "label": "기업 지원 최대(월 60만 × 12)"},
                   {"num": "720", "unit": "만", "label": "비수도권 청년 본인 최대(지역별 480~720만)"}],
         "explain": "만 15~34세를 정규직으로 뽑아 6개월 넘게 고용하면 받는다. 비수도권은 산업단지 중견기업까지 대상이다."},
        {"type": "stat", "photo": "code.jpg", "kicker": "공고로 보면", "title": "중견·중소 신입 자리",
         "items": [{"num": f"{mid}", "unit": "개", "label": "중견기업"},
                   {"num": f"{local}", "unit": "개", "label": "수도권 밖"}],
         "explain": "지원금은 회사가 신청해야 받는다. 면접에서 장려금 참여 여부를 물어봐도 된다."},
        {"type": "picks", "photo": "typing.jpg", "kicker": "눈여겨볼 곳", "title": "중견·중소 신입 IT 자리",
         "sub": "중견기업 먼저, 회사마다 한 건", "rows": picks},
        {"type": "end", "photo": "seoul.jpg", "kicker": "저장해 두기", "title": "대기업만 보지 말고\n지원금 받는 자리도 보자",
         "lines": ["취준하는 친구에게 보내 주세요", "신입 공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    slides[1]["note"] = "복지로 '2026년 청년일자리도약장려금 한눈에 알아보기' 요약 · 자세한 조건은 고용24 공고"
    caption = "\n\n".join([
        f"신입이 넣을 수 있는 국내 IT 자리 {n:,}개 중 {len(sme):,}개({pct(len(sme))}%)가 중견·중소기업입니다.",
        f"· 중견기업 {mid}개 · 수도권 밖 {local}개\n· 눈여겨볼 곳: " + " · ".join(p["co"] for p in picks),
        "2026 청년일자리도약장려금은 만 15~34세 청년을 정규직으로 뽑아 6개월 넘게 고용한 기업에 월 60만 원씩 최대 720만 원을 "
        "지원합니다. 비수도권에 취업한 청년 본인도 지역에 따라 480만~720만 원을 받을 수 있습니다(복지로 안내). "
        "지원 조건은 고용24 공고에서 꼭 확인하세요.",
        "출처\nhttps://www.bokjiro.go.kr/ssis-tbu/cms/pc/news/promotion/1309561_1118.html",
        f"{today:%Y.%m.%d} JD Viewer 모집중 신입 IT 공고(국내 근무) 기준. 같은 자리를 여러 사이트에 올린 것은 하나로, "
        "규모를 모르는 회사는 중소기업으로 셌습니다.",
    ])
    return {"id": f"sme-{today:%Y%m%d}", "series": "[중견·중소 신입]", "title": "중견·중소 신입 IT 자리", "slides": slides,
            "caption": caption}


#: 짧게 일하는 제도 — '주 4일'·'주 4.5일'·'격주 주4일'·'주 35시간'. '4일 이상 근무' 같은 문장은 '주' 가 붙어야만 센다.
_SHORT_WEEK = {"주 4.5일": r"주\s*4\.5\s*일|4\.5\s*일\s*(제|근무)",
               # '주 4일 출근 + 주 1일 재택' 은 주 5일이다 — 출근은 세지 않는다
               "주 4일": r"주\s*4\s*일\s*(제|근무)|주\s*4\s*일제|4\s*day\s*work",
               "격주 주 4일": r"격주\s*(로\s*)?(주\s*)?4\s*일|격주\s*(금요일|월요일)\s*휴무|격주\s*놀금|놀금",
               "주 35시간": r"주\s*3[56]\s*시간\s*(근무|제)"}


def build_fourday(today: date | None = None) -> dict:
    """[카드뉴스] 주 4일·4.5일 — 경기도 주 4.5일제 시범사업(한국경제 2026.3.4: 97개 기업 참여, 1인당 월 최대 27만 원 임금 보전)과
    지금 공고 본문에 짧은 근무 제도를 적은 국내 IT 공고. 같은 자리 중복 게시는 하나로."""
    import psycopg
    from psycopg.rows import dict_row
    from .collection import _AGENCY, _FOREIGN_TAG, _not_dev
    from .series import _role_key
    today = today or date.today()
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        rows = conn.execute("""
            SELECT f.stacks, c.display_name AS co, j.title, f.region, f.company_size AS size, j.deadline_on,
                   concat_ws(' ', j.benefits, j.full_jd) AS body
              FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
              JOIN job_facet f ON f.job_id = j.id JOIN company c ON c.id = j.company_id
             WHERE coalesce(f.region, '') <> '해외·원격'
               AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""").fetchall()
    rows = [r for r in rows if not _not_dev({"title": r["title"], "stack": r["stacks"] or []})
            and not _AGENCY.search(r["co"] + r["title"]) and not _NOT_JOB.search(r["title"] + r["co"])
            and not _FOREIGN_TAG.match(r["title"]) and not (r["deadline_on"] and r["deadline_on"] < today)]
    uniq = {}
    for r in rows:
        uniq.setdefault((_co(r["co"]), _role_key(r["title"])), r)
    rows = list(uniq.values())
    n = len(rows)
    hits = [(r, [k for k, rx in _SHORT_WEEK.items() if re.search(rx, r["body"] or "", re.I)]) for r in rows]
    hits = [(r, h) for r, h in hits if h]
    by = collections.Counter(k for _, h in hits for k in h)
    gg = sum(1 for r, _ in hits if r["region"] == "경기")
    cos = len({_co(r["co"]) for r, _ in hits})
    picks, seen = [], set()
    for r, h in sorted(hits, key=lambda x: ({"대기업": 0, "중견기업": 1}.get(x[0]["size"], 2),
                                            x[0]["deadline_on"] is None, x[0]["deadline_on"] or today)):
        c = _co(r["co"])
        d = (r["deadline_on"] - today).days if r["deadline_on"] else None
        if c in seen or d == 0:
            continue
        seen.add(c)
        when = f"D-{d}" if d is not None else "상시"
        picks.append({"co": c, "title": _short(re.sub(r"^\s*\[[^\]]*\]\s*", "", r["title"])),
                      "meta": f"{h[0]} · {when}"})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {n:,}자리 · {today:%Y.%m.%d} · 같은 자리 중복 게시는 하나로 · 본문에 제도를 적은 것만"
    slides = [
        {"type": "cover", "photo": "seoul.jpg", "kicker": f"주 4일·4.5일 · {today:%Y.%m.%d}",
         "big": f"{len(hits)}", "unit": "개", "title": ["주 5일보다 짧게", "일하는 IT 자리"],
         "sub": f"주 4일·4.5일·격주 4일·주 35시간을 적은 국내 IT 자리 ({cos}개 회사)"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "경기도 시범사업", "title": "주 4.5일제, 지자체가 돈을 댄다",
         "items": [{"num": "97", "unit": "곳", "label": "작년에 뽑혀 참여 중인 기업"},
                   {"num": "27", "unit": "만", "label": "노동자 1인당 월 임금 보전(최대)"}],
         "explain": "경기도 300인 미만 중소·중견기업이 대상이고, 컨설팅도 기업당 1,500만 원까지 지원한다."},
        {"type": "stat", "photo": "code.jpg", "kicker": "공고로 보면", "title": "어떤 제도를 적었나",
         "items": [{"num": f"{by.get(k, 0)}", "unit": "개", "label": k} for k, _ in by.most_common(2)],
         "explain": f"근무지가 경기도인 자리는 {gg}개. 제도는 회사마다 다르니 면접에서 꼭 확인하자."},
        {"type": "picks", "photo": "typing.jpg", "kicker": "눈여겨볼 곳", "title": "짧게 일하는 IT 자리",
         "sub": "큰 회사 먼저, 회사마다 한 건", "rows": picks},
        {"type": "end", "photo": "pangyo.jpg", "kicker": "저장해 두기", "title": "연봉만큼 중요한 건\n일하는 시간",
         "lines": ["워라밸 찾는 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    slides[1]["note"] = "한국경제 2026.3.4 보도(경기도 2026 주 4.5일제 시범사업) 요약"
    caption = "\n\n".join([
        f"공고 본문에 주 4일·4.5일·격주 4일·주 35시간 같은 짧은 근무 제도를 적은 국내 IT 자리는 {len(hits)}개({cos}개 회사)입니다.",
        "· 적힌 제도: " + " · ".join(f"{k} {v}개" for k, v in by.most_common()) + f"\n· 근무지가 경기도인 자리 {gg}개\n"
        "· 눈여겨볼 곳: " + " · ".join(p["co"] for p in picks),
        "한국경제는 경기도가 주 4.5일제 시범사업 신규 기업을 모집한다며, 지난해 뽑힌 97개 기업과 1개 공공기관이 참여 중이고 "
        "노동자 1인당 월 최대 27만 원의 임금 보전 장려금과 기업당 최대 1,500만 원의 컨설팅을 지원한다고 전했습니다.",
        "출처\nhttps://www.hankyung.com/article/202603049160h",
        f"{today:%Y.%m.%d} JD Viewer 모집중 IT 공고(국내 근무) 기준. 같은 자리를 여러 사이트에 올린 것은 하나로, 공고 본문에 제도를 적은 것만 셌습니다.",
    ])
    return {"id": f"fourday-{today:%Y%m%d}", "series": "[주 4일·4.5일]", "title": "짧게 일하는 IT 자리", "slides": slides,
            "caption": caption}


def build_secneed(today: date | None = None) -> dict:
    """[카드뉴스] 보안 인력 — 과기정통부·KISIA 2024 사이버보안 인력수급 실태조사(이투데이 2025.4.10: 50인 이상 기업 27,785곳 중
    91.3% 가 '보안 인력 필요 없다')와, 그래도 지금 보안 직군을 뽑는 국내 회사들. 같은 자리 중복 게시는 하나로."""
    import psycopg
    from psycopg.rows import dict_row
    from .collection import _AGENCY, _FOREIGN_TAG, _not_dev
    from .series import _role_key
    today = today or date.today()
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        rows = conn.execute("""
            SELECT f.stacks, c.display_name AS co, j.title, f.company_size AS size, f.career_bucket AS b, j.deadline_on
              FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
              JOIN job_facet f ON f.job_id = j.id JOIN company c ON c.id = j.company_id
             WHERE '보안' = ANY(f.roles) AND coalesce(f.region, '') <> '해외·원격'
               AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""").fetchall()
    rows = [r for r in rows if not _not_dev({"title": r["title"], "stack": r["stacks"] or []})
            and not _AGENCY.search(r["co"] + r["title"]) and not _NOT_JOB.search(r["title"] + r["co"])
            and not _FOREIGN_TAG.match(r["title"]) and not (r["deadline_on"] and r["deadline_on"] < today)]
    uniq = {}
    for r in rows:
        uniq.setdefault((_co(r["co"]), _role_key(r["title"])), r)
    rows = list(uniq.values())
    n = len(rows)
    cos = len({_co(r["co"]) for r in rows})
    big = sum(1 for r in rows if r["size"] == "대기업")
    entry = sum(1 for r in rows if r["b"] == "신입/무관")
    picks, seen = [], set()
    for r in sorted(rows, key=lambda r: ({"대기업": 0, "중견기업": 1}.get(r["size"], 2),
                                         r["deadline_on"] is None, r["deadline_on"] or today)):
        c = _co(r["co"])
        d = (r["deadline_on"] - today).days if r["deadline_on"] else None
        if c in seen or d == 0:
            continue
        seen.add(c)
        when = f"D-{d}" if d is not None else "상시"
        picks.append({"co": c, "title": _short(re.sub(r"^\s*\[[^\]]*\]\s*", "", r["title"])),
                      "meta": f"{r['size'] or ''} · {when}"})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 보안 직군 공고 · 국내 근무 · {today:%Y.%m.%d} · 같은 자리 중복 게시는 하나로 · 직군은 제목·본문으로 가른 것"
    slides = [
        {"type": "cover", "photo": "css.jpg", "kicker": f"보안 인력 · {today:%Y.%m.%d}",
         "big": "91.3", "unit": "%", "title": ["보안 인력 필요 없다는", "기업들, 그런데"],
         "sub": "50인 이상 민간기업 27,785곳 중 '필요 없다' 고 답한 비율"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "실태조사", "title": "필요하다는 곳은 열에 하나도 안 된다",
         "items": [{"num": "8.7", "unit": "%", "label": "보안 인력이 필요하다고 답한 기업"},
                   {"num": "27,785", "unit": "곳", "label": "조사한 50인 이상 민간기업"}],
         "explain": "과기정통부·한국정보보호산업협회의 2024 사이버보안 인력수급 실태조사다."},
        {"type": "stat", "photo": "seoul.jpg", "kicker": "공고로 보면", "title": "그래도 지금 뽑는 보안 자리",
         "items": [{"num": f"{n}", "unit": "개", "label": f"보안 직군 자리 ({cos}개 회사)"},
                   {"num": f"{entry}", "unit": "개", "label": "신입도 되는 자리"}],
         "explain": f"대기업이 낸 자리는 {big}개다. 뽑는 곳은 뽑는다 — 회사가 어디냐가 갈린다."},
        {"type": "picks", "photo": "typing.jpg", "kicker": "눈여겨볼 곳", "title": "지금 보안을 뽑는 곳",
         "sub": "큰 회사 먼저, 회사마다 한 건", "rows": picks},
        {"type": "end", "photo": "pangyo.jpg", "kicker": "저장해 두기", "title": "보안 쪽을 준비한다면\n뽑는 회사부터 보자",
         "lines": ["보안 공부하는 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    for i in (0, 1):
        slides[i]["note"] = "과기정통부·KISIA 2024 사이버보안 인력수급 실태조사 · 이투데이 2025.4.10 보도 요약"
    caption = "\n\n".join([
        f"50인 이상 기업 열 곳 중 아홉은 '보안 인력이 필요 없다' 고 답했습니다. 그래도 지금 보안 직군 자리는 {n}개({cos}개 회사) 열려 있어요.",
        f"· 신입도 되는 자리 {entry}개 · 대기업 자리 {big}개\n· 눈여겨볼 곳: " + " · ".join(p["co"] for p in picks),
        "이투데이는 과기정통부와 한국정보보호산업협회의 2024 사이버보안 인력수급 실태조사를 인용해, 50인 이상 민간기업 27,785곳 중 "
        "보안 인력이 필요하다고 답한 곳은 8.7%뿐이었다고 전했습니다.",
        "출처\nhttps://www.etoday.co.kr/news/view/2460937",
        f"{today:%Y.%m.%d} JD Viewer 모집중 보안 직군 공고(국내 근무) 기준. 직군은 공고 제목·본문으로 가른 것이고, "
        "같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"id": f"secneed-{today:%Y%m%d}", "series": "[보안 인력]", "title": "보안 인력, 그래도 뽑는 곳", "slides": slides,
            "caption": caption}


_DBS = [("MySQL", ("MySQL", "MariaDB")), ("PostgreSQL", ("PostgreSQL",)), ("Oracle", ("Oracle",)),
        ("Redis", ("Redis",)), ("MongoDB", ("MongoDB",)), ("MSSQL", ("MSSQL",))]
_DBA = re.compile(r"(?<![A-Za-z])DBA(?![A-Za-z])|데이터베이스\s*(관리자|엔지니어|운영)|DB\s*(관리자|엔지니어|운영|담당)|Database\s*(Admin|Engineer)", re.I)


def build_db(today: date | None = None) -> dict:
    """[카드뉴스] 데이터베이스 — PostgreSQL 19 RC 1(postgresql.org 2026.10.15)을 계기로, 지금 국내 IT 공고가 적은 DB 와
    DB 를 직접 맡는 자리(DBA·DB 엔지니어). MySQL 은 MariaDB 를 함께 센다. 같은 자리 중복 게시는 하나로."""
    import psycopg
    from psycopg.rows import dict_row
    from .collection import _AGENCY, _FOREIGN_TAG, _SI_STAFF, _not_dev
    from .series import _role_key
    today = today or date.today()
    with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
        rows = conn.execute("""
            SELECT f.stacks, c.display_name AS co, j.title, f.company_size AS size, f.career_bucket AS b, j.deadline_on
              FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
              JOIN job_facet f ON f.job_id = j.id JOIN company c ON c.id = j.company_id
             WHERE coalesce(f.region, '') <> '해외·원격'
               AND NOT EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = j.id)""").fetchall()
    rows = [r for r in rows if not _not_dev({"title": r["title"], "stack": r["stacks"] or []})
            and not _AGENCY.search(r["co"] + r["title"]) and not _NOT_JOB.search(r["title"] + r["co"])
            and not _FOREIGN_TAG.match(r["title"]) and not (_SI_STAFF.search(r["title"]) and "정규직" not in r["title"])
            and not (r["deadline_on"] and r["deadline_on"] < today)]
    uniq = {}
    for r in rows:
        uniq.setdefault((_co(r["co"]), _role_key(r["title"])), r)
    rows = list(uniq.values())
    n = len(rows)
    by = sorted(((k, sum(1 for r in rows if set(r["stacks"] or []) & set(keys))) for k, keys in _DBS), key=lambda kv: -kv[1])
    rest = [kv for kv in by[1:] if kv[0] != "PostgreSQL"]
    dba = [r for r in rows if _DBA.search(r["title"])]
    picks, seen = [], set()
    for r in sorted(dba, key=lambda r: ({"대기업": 0, "중견기업": 1}.get(r["size"], 2),
                                        r["deadline_on"] is None, r["deadline_on"] or today)):
        c = _co(r["co"])
        d = (r["deadline_on"] - today).days if r["deadline_on"] else None
        if c in seen or d == 0:
            continue
        seen.add(c)
        when = f"D-{d}" if d is not None else "상시"
        picks.append({"co": c, "title": _short(re.sub(r"^\s*\[[^\]]*\]\s*", "", r["title"])), "meta": f"{r['size'] or ''} · {when}"})
        if len(picks) == 4:
            break
    pct = lambda a: round(100 * a / n) if n else 0
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {n:,}자리 · {today:%Y.%m.%d} · 기술은 공고 본문에서 뽑은 것 · 같은 자리 중복 게시는 하나로"
    slides = [
        {"type": "cover", "photo": "pangyo.jpg", "kicker": f"데이터베이스 · {today:%Y.%m.%d}",
         "big": f"{by[0][1]:,}", "unit": "개", "title": [f"공고가 가장 많이 적은 DB", f"{by[0][0]}"],
         "sub": f"국내 IT 자리 {n:,}개 중 {pct(by[0][1])}%"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "릴리스", "title": "PostgreSQL 19, 정식판 직전",
         "items": [{"num": "19", "unit": "RC 1", "label": "2026년 10월 15일 공개"},
                   {"num": f"{dict(by)['PostgreSQL']:,}", "unit": "개", "label": "PostgreSQL 을 적은 국내 IT 자리"}],
         "explain": "RC(릴리스 후보)는 정식판 바로 전 단계다. 큰 문제가 없으면 이 판이 그대로 정식판이 된다."},
        {"type": "stat", "photo": "code.jpg", "kicker": "공고로 보면", "title": "DB 별로 세면",
         "items": [{"num": f"{v:,}", "unit": "개", "label": k} for k, v in rest[:2]],
         "explain": " · ".join(f"{k} {v:,}개" for k, v in rest[2:]) + ". MySQL 은 MariaDB 를 함께 셌다."},
        {"type": "picks", "photo": "typing.jpg", "kicker": "눈여겨볼 곳", "title": f"DB 를 맡는 자리 {len(dba)}개",
         "sub": "제목에 DBA·DB 엔지니어를 단 공고, 큰 회사 먼저", "rows": picks},
        {"type": "end", "photo": "seoul.jpg", "kicker": "저장해 두기", "title": "쓰는 DB 를 알면\n공고가 좁혀진다",
         "lines": ["DB 공부하는 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    caption = "\n\n".join([
        f"PostgreSQL 19 RC 1 이 10월 15일 나왔습니다. 국내 IT 공고 {n:,}자리가 적은 DB 를 세 봤습니다.",
        "· " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in by) + f"\n· 제목에 DBA·DB 엔지니어를 단 자리 {len(dba)}개\n"
        "· 눈여겨볼 곳: " + " · ".join(p["co"] for p in picks),
        "postgresql.org 는 10월 15일 PostgreSQL 19 의 첫 릴리스 후보(RC 1)를 공개했습니다. RC 는 정식판 바로 전 단계입니다.",
        "출처\nhttps://www.postgresql.org/about/newsarchive/",
        f"{today:%Y.%m.%d} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고, MySQL 은 MariaDB 를 함께 셌습니다. "
        "같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"id": f"db-{today:%Y%m%d}", "series": "[데이터베이스]", "title": "공고가 적은 DB", "slides": slides,
            "caption": caption}


def build_k8s(today: date | None = None) -> dict:
    """[카드뉴스] 쿠버네티스 — kubernetes.io 릴리스 표(1.34 지원 종료 2026.10.27 · 최신 1.37.1)를 계기로, 지금 국내 IT 공고 중
    Kubernetes 를 적은 자리·직군·같이 적은 기술·눈여겨볼 곳. 같은 자리 중복 게시는 하나로."""
    from .series import _co_name, _it_rows
    today = today or date.today()
    rows = _it_rows()
    total = len(rows)
    k8 = [r for r in rows if "Kubernetes" in (r["stacks"] or [])]
    n = len(k8)
    roles = collections.Counter(x for r in k8 for x in set(r["roles"] or []) if x != "기타").most_common(4)
    with_ = collections.Counter(x for r in k8 for x in set(r["stacks"] or []) if x != "Kubernetes").most_common(5)
    entry = sum(1 for r in k8 if r["career_bucket"] == "신입/무관")
    pct = lambda a, b=n: round(100 * a / b) if b else 0
    picks, seen = [], set()
    for r in sorted((r for r in k8 if "DevOps/인프라" in (r["roles"] or [])),
                    key=lambda r: ({"대기업": 0, "중견기업": 1}.get(r["size"], 2), r["deadline_on"] is None, r["deadline_on"] or today)):
        c = re.sub(r"\s*지점$", "", _co_name(r["company"]))   # '스마일게이트 메가포트 지점'
        d = (r["deadline_on"] - today).days if r["deadline_on"] else None
        if c in seen or d == 0:
            continue
        seen.add(c)
        picks.append({"co": c, "title": _short(re.sub(r"^\s*\[[^\]]*\]\s*", "", r["title"])),
                      "meta": f"{r['size'] or ''} · {f'D-{d}' if d is not None else '상시'}"})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {total:,}자리 · {today:%Y.%m.%d} · 기술은 공고 본문에서 뽑은 것 · 같은 자리 중복 게시는 하나로"
    slides = [
        {"type": "cover", "photo": "pangyo.jpg", "kicker": f"쿠버네티스 · {today:%Y.%m.%d}",
         "big": f"{n:,}", "unit": "개", "title": ["Kubernetes 를 적은", "국내 IT 자리"],
         "sub": f"국내 IT 자리 {total:,}개 중 {pct(n, total)}% · 신입 가능 {entry}개"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "릴리스", "title": "1.34 지원, 10월 27일 끝",
         "items": [{"num": "1.37.1", "unit": "", "label": "지금 최신(2026.9.15)"},
                   {"num": "10.27", "unit": "", "label": "1.34 지원 종료일"}],
         "explain": "Kubernetes 는 최근 판 몇 개만 지원한다. 지원이 끝난 판에는 수정판이 더 나오지 않는다."},
        {"type": "stat", "photo": "code.jpg", "kicker": "어느 직군", "title": "Kubernetes 자리는",
         "items": [{"num": f"{v:,}", "unit": "개", "label": k} for k, v in roles[:2]],
         "explain": " · ".join(f"{k} {v:,}개" for k, v in roles[2:]) + ". 한 자리가 여러 직군이면 각각 셌다."},
        {"type": "stat", "photo": "css.jpg", "kicker": "같이 적은 기술", "title": "함께 적힌 것",
         "items": [{"num": f"{pct(v)}", "unit": "%", "label": k} for k, v in with_[:2]],
         "explain": " · ".join(f"{k} {pct(v)}%" for k, v in with_[2:]) + f". Kubernetes 자리 {n:,}개 중."},
        {"type": "picks", "photo": "typing.jpg", "kicker": "눈여겨볼 곳", "title": "인프라·DevOps 자리",
         "sub": "Kubernetes 를 적은 인프라 공고, 큰 회사 먼저", "rows": picks},
        {"type": "end", "photo": "seoul.jpg", "kicker": "저장해 두기", "title": "컨테이너를 알면\n인프라 문이 열린다",
         "lines": ["인프라 공부하는 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    caption = "\n\n".join([
        f"Kubernetes 1.34 지원이 10월 27일 끝납니다. 지금 국내 IT 자리 {total:,}개 중 Kubernetes 를 적은 자리는 {n:,}개({pct(n, total)}%), 신입 가능 {entry}개입니다.",
        "· 어느 직군: " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in roles) + "\n"
        "· 같이 적은 기술: " + " · ".join(f"{k} {pct(v)}%" for k, v in with_) + "\n"
        "· 눈여겨볼 곳: " + " · ".join(p["co"] for p in picks),
        "kubernetes.io 릴리스 표에 따르면 지금 최신은 1.37.1(9월 15일)이고, 지원 중인 판 가운데 1.34 는 10월 27일 지원이 끝납니다.",
        "출처\nhttps://kubernetes.io/releases/",
        f"{today:%Y.%m.%d} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고, 한 자리가 여러 직군에 걸치면 각각 셌습니다. "
        "같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"id": f"k8s-{today:%Y%m%d}", "series": "[쿠버네티스]", "title": "Kubernetes 자리", "slides": slides,
            "caption": caption}


def build_linux(today: date | None = None) -> dict:
    """[카드뉴스] 리눅스 — kernel.org(메인라인 7.3 2026.10.18 · 안정판 7.2.11)를 계기로, 지금 국내 IT 공고 중 Linux 를
    적은 자리·직군·같이 적은 기술·눈여겨볼 곳(임베디드·인프라). 같은 자리 중복 게시는 하나로."""
    from .collection import _group
    from .series import _co_name, _it_rows
    today = today or date.today()
    rows = _it_rows()
    total = len(rows)
    lx = [r for r in rows if "Linux" in (r["stacks"] or [])]
    n = len(lx)
    roles = collections.Counter(x for r in lx for x in set(r["roles"] or []) if x != "기타").most_common(4)
    with_ = collections.Counter(x for r in lx for x in set(r["stacks"] or []) if x not in ("Linux", "C/C++")).most_common(5)
    entry = sum(1 for r in lx if r["career_bucket"] == "신입/무관")
    pct = lambda a, b=n: round(100 * a / b) if b else 0
    picks, seen = [], set()
    for r in sorted((r for r in lx if {"펌웨어/임베디드", "DevOps/인프라"} & set(r["roles"] or [])),
                    key=lambda r: ({"대기업": 0, "중견기업": 1}.get(r["size"], 2), r["deadline_on"] is None, r["deadline_on"] or today)):
        c = re.sub(r"\s*지점$", "", _co_name(r["company"]))
        c = {"비바리퍼블리카": "토스"}.get(c, c)   # 법인명보다 서비스 이름이 읽힌다
        d = (r["deadline_on"] - today).days if r["deadline_on"] else None
        g = _group(c)                    # 한 그룹 한 곳 — 한화·현대가 두 칸씩 차지했다
        if g in seen or d == 0:
            continue
        seen.add(g)
        picks.append({"co": c, "title": _short(re.sub(r"^\s*\[[^\]]*\]\s*", "", r["title"])),
                      "meta": f"{r['size'] or ''} · {f'D-{d}' if d is not None else '상시'}"})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {total:,}자리 · {today:%Y.%m.%d} · 기술은 공고 본문에서 뽑은 것 · 같은 자리 중복 게시는 하나로"
    slides = [
        {"type": "cover", "photo": "code.jpg", "kicker": f"리눅스 · {today:%Y.%m.%d}",
         "big": f"{n:,}", "unit": "개", "title": ["Linux 를 적은", "국내 IT 자리"],
         "sub": f"국내 IT 자리 {total:,}개 중 {pct(n, total)}% · 신입 가능 {entry}개"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "릴리스", "title": "커널 7.3, 10월 18일",
         "items": [{"num": "7.3", "unit": "", "label": "메인라인(2026.10.18)"},
                   {"num": "7.2.11", "unit": "", "label": "안정판(2026.10.15)"}],
         "explain": "kernel.org 첫 화면 기준. 메인라인은 새 기능이 들어가는 줄기, 안정판은 수정만 받는 판이다."},
        {"type": "stat", "photo": "typing.jpg", "kicker": "어느 직군", "title": "Linux 자리는",
         "items": [{"num": f"{v:,}", "unit": "개", "label": k} for k, v in roles[:2]],
         "explain": " · ".join(f"{k} {v:,}개" for k, v in roles[2:]) + ". 한 자리가 여러 직군이면 각각 셌다."},
        {"type": "stat", "photo": "css.jpg", "kicker": "같이 적은 기술", "title": "함께 적힌 것",
         "items": [{"num": f"{pct(v)}", "unit": "%", "label": k} for k, v in with_[:2]],
         "explain": " · ".join(f"{k} {pct(v)}%" for k, v in with_[2:]) + f". Linux 자리 {n:,}개 중."},
        {"type": "picks", "photo": "pangyo.jpg", "kicker": "눈여겨볼 곳", "title": "임베디드·인프라 자리",
         "sub": "Linux 를 적은 임베디드·인프라 공고, 큰 회사 먼저", "rows": picks},
        {"type": "end", "photo": "seoul.jpg", "kicker": "저장해 두기", "title": "터미널이 익숙하면\n문이 하나 더 열린다",
         "lines": ["리눅스 공부하는 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    caption = "\n\n".join([
        f"리눅스 커널 7.3 이 10월 18일 나왔습니다. 지금 국내 IT 자리 {total:,}개 중 Linux 를 적은 자리는 {n:,}개({pct(n, total)}%), 신입 가능 {entry}개입니다.",
        "· 어느 직군: " + " · ".join(f"{k} {v:,}개({pct(v)}%)" for k, v in roles) + "\n"
        "· 같이 적은 기술: " + " · ".join(f"{k} {pct(v)}%" for k, v in with_) + "\n"
        "· 눈여겨볼 곳: " + " · ".join(p["co"] for p in picks),
        "kernel.org 첫 화면에 따르면 메인라인 7.3 은 10월 18일, 안정판 7.2.11 은 10월 15일 나왔습니다.",
        "출처\nhttps://www.kernel.org/",
        f"{today:%Y.%m.%d} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고, 한 자리가 여러 직군에 걸치면 각각 셌습니다. "
        "같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"id": f"linux-{today:%Y%m%d}", "series": "[리눅스]", "title": "Linux 자리", "slides": slides,
            "caption": caption}


_FE = ("React", "Next.js", "Vue", "TypeScript", "Angular", "Svelte")


def build_nextjs(today: date | None = None) -> dict:
    """[카드뉴스] Next.js — Next.js 16.4(2026.10.6)와 보안 업데이트(10.14, nextjs.org/blog)를 계기로, 지금 국내 IT 공고 중
    Next.js 를 적은 자리·프론트엔드 공고가 적은 기술·눈여겨볼 곳. 같은 자리 중복 게시는 하나로."""
    from .collection import _group
    from .series import _co_name, _it_rows
    today = today or date.today()
    rows = _it_rows()
    total = len(rows)
    nx = [r for r in rows if "Next.js" in (r["stacks"] or [])]
    n = len(nx)
    fe = [r for r in rows if "프론트엔드" in (r["roles"] or [])]
    fe_by = sorted(((k, sum(1 for r in fe if k in (r["stacks"] or []))) for k in _FE), key=lambda kv: -kv[1])
    entry = sum(1 for r in nx if r["career_bucket"] == "신입/무관")
    pct = lambda a, b=n: round(100 * a / b) if b else 0
    picks, seen = [], set()
    for r in sorted(nx, key=lambda r: ({"대기업": 0, "중견기업": 1}.get(r["size"], 2), r["deadline_on"] is None, r["deadline_on"] or today)):
        c = re.sub(r"\s*지점$", "", _co_name(r["company"]))
        c = {"비바리퍼블리카": "토스"}.get(c, c)
        d = (r["deadline_on"] - today).days if r["deadline_on"] else None
        g = _group(c)
        if g in seen or d == 0:
            continue
        seen.add(g)
        picks.append({"co": c, "title": _short(re.sub(r"^\s*\[[^\]]*\]\s*", "", r["title"])),
                      "meta": f"{r['size'] or ''} · {f'D-{d}' if d is not None else '상시'}"})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {total:,}자리 · {today:%Y.%m.%d} · 기술은 공고 본문에서 뽑은 것 · 같은 자리 중복 게시는 하나로"
    slides = [
        {"type": "cover", "photo": "pangyo.jpg", "kicker": f"Next.js · {today:%Y.%m.%d}",
         "big": f"{n:,}", "unit": "개", "title": ["Next.js 를 적은", "국내 IT 자리"],
         "sub": f"국내 IT 자리 {total:,}개 중 {pct(n, total)}% · 신입 가능 {entry}개"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "릴리스", "title": "16.4, 그리고 보안 업데이트",
         "items": [{"num": "16.4", "unit": "", "label": "2026년 10월 6일"},
                   {"num": "10.14", "unit": "", "label": "보안 업데이트 공지"}],
         "explain": "nextjs.org 블로그 기준. 10월 14일 글은 Next.js 가 쓰는 다른 패키지의 취약점에 대한 업데이트다."},
        {"type": "stat", "photo": "code.jpg", "kicker": "프론트엔드 공고로 보면", "title": f"프론트엔드 자리 {len(fe):,}개",
         "items": [{"num": f"{pct(v, len(fe))}", "unit": "%", "label": k} for k, v in fe_by[:2]],
         "explain": " · ".join(f"{k} {pct(v, len(fe))}%" for k, v in fe_by[2:]) + ". 프론트엔드 직군 공고 중 그 기술을 적은 비율."},
        {"type": "picks", "photo": "typing.jpg", "kicker": "눈여겨볼 곳", "title": "Next.js 를 쓰는 곳",
         "sub": "Next.js 를 적은 공고, 큰 회사 먼저 · 한 그룹 한 곳", "rows": picks},
        {"type": "end", "photo": "seoul.jpg", "kicker": "저장해 두기", "title": "React 다음 한 걸음은\n공고가 정한다",
         "lines": ["프론트엔드 공부하는 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    caption = "\n\n".join([
        f"Next.js 16.4 가 10월 6일 나왔습니다. 지금 국내 IT 자리 {total:,}개 중 Next.js 를 적은 자리는 {n:,}개({pct(n, total)}%), 신입 가능 {entry}개입니다.",
        f"· 프론트엔드 직군 자리 {len(fe):,}개가 적은 기술: " + " · ".join(f"{k} {pct(v, len(fe))}%" for k, v in fe_by) + "\n"
        "· 눈여겨볼 곳: " + " · ".join(p["co"] for p in picks),
        "nextjs.org 블로그에 따르면 Next.js 16.4 는 10월 6일 나왔고, 10월 14일에는 Next.js 가 쓰는 다른 패키지의 취약점에 대한 보안 업데이트 글이 올라왔습니다.",
        "출처\nhttps://nextjs.org/blog",
        f"{today:%Y.%m.%d} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고, 같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"id": f"nextjs-{today:%Y%m%d}", "series": "[Next.js]", "title": "Next.js 자리", "slides": slides,
            "caption": caption}


def build_vue(today: date | None = None) -> dict:
    """[카드뉴스] Vue — vuejs/core GitHub 릴리스(3.5.44 최신 정식 10.13 · 3.6.0-rc.12 10.16)를 계기로, 지금 국내 IT 공고 중
    Vue 를 적은 자리·프론트엔드 공고에서 React 와 견준 몫·Nuxt·눈여겨볼 곳. 같은 자리 중복 게시는 하나로."""
    from .collection import _group
    from .series import _co_name, _it_rows
    today = today or date.today()
    rows = _it_rows()
    total = len(rows)
    vu = [r for r in rows if "Vue" in (r["stacks"] or [])]
    n = len(vu)
    fe = [r for r in rows if "프론트엔드" in (r["roles"] or [])]
    has = lambda r, k: k in (r["stacks"] or [])
    react = sum(1 for r in fe if has(r, "React"))
    vue_fe = sum(1 for r in fe if has(r, "Vue"))
    both = sum(1 for r in fe if has(r, "React") and has(r, "Vue"))
    nuxt = sum(1 for r in vu if has(r, "Nuxt"))
    ts = sum(1 for r in vu if has(r, "TypeScript"))
    entry = sum(1 for r in vu if r["career_bucket"] == "신입/무관")
    pct = lambda a, b=n: round(100 * a / b) if b else 0
    picks, seen = [], set()
    for r in sorted(vu, key=lambda r: ({"대기업": 0, "중견기업": 1}.get(r["size"], 2), r["deadline_on"] is None, r["deadline_on"] or today)):
        c = re.sub(r"\s*지점$", "", _co_name(r["company"]))
        c = {"비바리퍼블리카": "토스"}.get(c, c)
        d = (r["deadline_on"] - today).days if r["deadline_on"] else None
        g = _group(c)
        if g in seen or d == 0:
            continue
        seen.add(g)
        picks.append({"co": c, "title": _short(re.sub(r"^\s*\[[^\]]*\]\s*", "", r["title"])),
                      "meta": f"{r['size'] or ''} · {f'D-{d}' if d is not None else '상시'}"})
        if len(picks) == 4:
            break
    note = f"JD Viewer 모집중 IT 공고 · 국내 근무 {total:,}자리 · {today:%Y.%m.%d} · 기술은 공고 본문에서 뽑은 것 · 같은 자리 중복 게시는 하나로"
    slides = [
        {"type": "cover", "photo": "pangyo.jpg", "kicker": f"Vue · {today:%Y.%m.%d}",
         "big": f"{n:,}", "unit": "개", "title": ["Vue 를 적은", "국내 IT 자리"],
         "sub": f"국내 IT 자리 {total:,}개 중 {pct(n, total)}% · 신입 가능 {entry}개"},
        {"type": "stat", "photo": "hourglass.jpg", "kicker": "릴리스", "title": "3.6 이 후보 단계에",
         "items": [{"num": "3.5.44", "unit": "", "label": "최신 정식(10월 13일)"},
                   {"num": "3.6", "unit": "rc.12", "label": "릴리스 후보(10월 16일)"}],
         "explain": "vuejs/core GitHub 릴리스 기준. rc 는 정식판 바로 전 단계다."},
        {"type": "stat", "photo": "code.jpg", "kicker": "프론트엔드 공고로 보면", "title": f"프론트엔드 자리 {len(fe):,}개",
         "items": [{"num": f"{pct(react, len(fe))}", "unit": "%", "label": "React"},
                   {"num": f"{pct(vue_fe, len(fe))}", "unit": "%", "label": "Vue"}],
         "explain": f"둘 다 적은 자리 {both:,}개({pct(both, len(fe))}%). 프론트엔드 직군 공고 중 그 기술을 적은 비율."},
        {"type": "stat", "photo": "css.jpg", "kicker": "Vue 자리 안에서", "title": "같이 적은 것",
         "items": [{"num": f"{pct(ts)}", "unit": "%", "label": "TypeScript"},
                   {"num": f"{pct(nuxt)}", "unit": "%", "label": "Nuxt"}],
         "explain": f"Vue 자리 {n:,}개 중. TypeScript {ts:,}개 · Nuxt {nuxt:,}개."},
        {"type": "picks", "photo": "typing.jpg", "kicker": "눈여겨볼 곳", "title": "Vue 를 쓰는 곳",
         "sub": "Vue 를 적은 공고, 큰 회사 먼저 · 한 그룹 한 곳", "rows": picks},
        {"type": "end", "photo": "seoul.jpg", "kicker": "저장해 두기", "title": "React 만 있는 건\n아니다",
         "lines": ["Vue 공부하는 친구에게 보내 주세요", "공고 전체는 프로필 링크에서"]},
    ]
    for sl in slides:
        sl["image"], sl["credit"] = _photo(sl.pop("photo"))
        sl["note"] = note
    caption = "\n\n".join([
        f"Vue 3.6 이 릴리스 후보(rc.12, 10월 16일) 단계에 있습니다. 지금 국내 IT 자리 {total:,}개 중 Vue 를 적은 자리는 {n:,}개({pct(n, total)}%), 신입 가능 {entry}개입니다.",
        f"· 프론트엔드 직군 자리 {len(fe):,}개 중 React {pct(react, len(fe))}% · Vue {pct(vue_fe, len(fe))}% · 둘 다 {pct(both, len(fe))}%\n"
        f"· Vue 자리 중 TypeScript {pct(ts)}% · Nuxt {pct(nuxt)}%\n"
        "· 눈여겨볼 곳: " + " · ".join(p["co"] for p in picks),
        "vuejs/core GitHub 릴리스 페이지에 따르면 최신 정식판은 10월 13일의 3.5.44 이고, 3.6.0-rc.12 가 10월 16일 나왔습니다.",
        "출처\nhttps://github.com/vuejs/core/releases",
        f"{today:%Y.%m.%d} JD Viewer 모집중 IT 공고(국내 근무) 기준. 기술은 공고 본문에서 뽑은 것이고, 같은 자리를 여러 사이트에 올린 것은 하나로 셌습니다.",
    ])
    return {"id": f"vue-{today:%Y%m%d}", "series": "[Vue]", "title": "Vue 자리", "slides": slides,
            "caption": caption}


BUILDERS = {"weekly": build_weekly, "brands": build_brands, "finance": build_finance, "intern": build_intern, "midlevel": build_midlevel, "japan": build_japan, "military": build_military, "region": build_region, "sme": build_sme, "fourday": build_fourday, "secneed": build_secneed, "db": build_db, "k8s": build_k8s, "linux": build_linux, "nextjs": build_nextjs, "vue": build_vue}


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
