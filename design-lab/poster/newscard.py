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
DEFAULT_STYLES = {"weekly": ["magazine", "paper", "poster", "scrap"], "brands": ["brandmag"]}


def _font_faces(families: list[str]) -> str:
    out = []
    for fam in families:
        for weight, rel in FONTS[fam]:
            p = LAB_DIR / rel
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


BUILDERS = {"weekly": build_weekly, "brands": build_brands}


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
