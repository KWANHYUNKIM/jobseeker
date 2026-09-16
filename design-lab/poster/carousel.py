"""공고 전문 → 인스타 캐러셀 여러 장.

한 장짜리 포스터(render.py)는 불릿을 3개로 자른다. 여기는 원문을 한 줄도 버리지 않고
표지 / 주요업무(소제목마다) / 자격요건 / 우대사항 / 복지 / 끝 장으로 접는다.
몇 장이 될지는 글 양이 정한다 — 템플릿 안의 스크립트가 흘려 넣다가 넘치면 다음 장을 연다.

    python -m poster.carousel wanted-364849
    python -m poster.carousel wanted-364849 --format ig_square --palette paper
    python -m poster.carousel wanted-364849 --one        # 전문을 한 장에(onepage.html)
    python -m poster.carousel wanted-364849 --one --frame label_sheet   # hire-17 틀
    python -m poster.carousel wanted-364849 --one --frame all           # 틀 전부 비교
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from . import assets, brands, jobsource
from .model import FORMATS, PALETTES, build_spec
from .render import LAB_DIR, OUT, _page_maker, shutdown

TEMPLATE = Path(__file__).resolve().parent / "templates" / "carousel.html"
ONEPAGE = TEMPLATE.with_name("onepage.html")
# 한 장짜리 틀. onepage 말고는 전부 refs.json 의 사람이 만든 공고에서 구조를 옮겼다(ONEPAGE.md).
FRAMES = {
    "onepage": ONEPAGE,                                      # 첫 시안 — 'AI 스럽다' 판정
    "label_sheet": TEMPLATE.with_name("label_sheet.html"),   # hire-17 엠쓰리디자인: 라벨 – 값
    "doc_table": TEMPLATE.with_name("doc_table.html"),       # kr-19 여자축구연맹: 공문형 번호 계층 + 표
    "swiss_grid": TEMPLATE.with_name("swiss_grid.html"),     # web-03 GREENERY CAVE: 텍스트 격자
    "dark_split": TEMPLATE.with_name("dark_split.html"),     # latam-03 AURE: 어두운 바탕, 제공|조건 마주보기
    "two_col": TEMPLATE.with_name("two_col.html"),           # eu-08 Tout Y Est: 업무는 깊게, 사람은 얕게
    # 회사 전용 판 — brands/<회사>.json 의 frame. 조사한 포인트를 자리로 옮긴 것(BRAND_RESEARCH.md)
    "brand": TEMPLATE.with_name("_brand"),
}
BRAND_FRAME = FRAMES["brand"]  # 표지 값. 실제 파일은 brands/*.json 의 frame
FRAME_JS = TEMPLATE.with_name("_frame.js")   # 틀들이 같이 쓰는 스크립트. /*__FRAME_JS__*/ 자리에 박는다
IG_MAX_SLIDES = 20
MIN_READABLE_PX = 18

# 사이트 이름 표는 뺐다 — 판에 채용 사이트를 적지 않기로 했다(compose 주석 참고).


def _until(job: dict) -> str:
    """'언제부터 언제까지 / 어떻게 모집하나' — 규칙은 collection.period_label 한 곳에만 둔다."""
    from .collection import period_label
    return period_label(job)


def _sections(full: dict) -> list[dict]:
    out: list[dict] = []
    groups = [g for g in full.get("tasks") or [] if g["items"]]
    numbered = len(groups) > 1
    for i, g in enumerate(groups, 1):
        out.append({
            "kind": "list", "kicker": "Tasks",
            "sub": f"주요업무 {i}/{len(groups)}" if numbered else "주요업무",
            "no": f"{i:02d}" if numbered else "",
            "title": g["title"] or "주요업무",
            "items": g["items"],
        })
    if full.get("qualifications"):
        out.append({"kind": "list", "kicker": "Requirements", "sub": "이 자리에 필요한 것",
                    "no": "", "title": "자격요건", "items": full["qualifications"]})
    if full.get("preferences"):
        out.append({"kind": "list", "kicker": "Preferred", "sub": "있으면 더 좋은 것",
                    "no": "", "title": "우대사항", "items": full["preferences"]})
    if full.get("benefits"):
        out.append({"kind": "rows", "kicker": "Benefits", "sub": "함께하면 받는 것",
                    "no": "", "title": "복지 / 혜택", "items": full["benefits"]})
    return out


def compose(job_key: str, fmt_id: str = "ig_portrait", *, palette: str = "") -> dict:
    job = jobsource.get(job_key)
    if not job:
        raise KeyError(f"모르는 공고: {job_key}")
    if fmt_id not in FORMATS:
        raise KeyError(f"모르는 포맷: {fmt_id}")
    spec = build_spec(job, mark=assets.mark(job["company"]), palette=palette).as_dict()
    sections = _sections(job.get("full") or {})
    toc: list[str] = []
    for s in sections:
        name = "주요업무" if s["kicker"] == "Tasks" else s["title"]
        if name not in toc:
            toc.append(name)
    brand = brands.find(job["company"])
    if brand and brand.get("palette") and not palette:   # --palette 를 주면 그게 이긴다
        spec["palette"] = {**spec["palette"], **brand["palette"]}
        spec["palette_name"] = "brand"
    return {
        **spec,
        "brand": brand,
        "title": job.get("title", ""),       # 괄호까지 그대로. role 은 괄호를 걷어낸 것
        "stack": (job.get("stack") or [])[:8],
        "fmt": FORMATS[fmt_id],
        # 판에는 채용 사이트 이름(원티드 등)도, 공고 주소·공고번호도 넣지 않는다(2026-09-16).
        # 남의 사이트 이름을 우리 판에 박아 홍보해 줄 이유가 없고, 소셜에서는 본문 링크가
        # 눌리지도 않는다. 지원 경로는 캡션·프로필에서 안내한다. spec["url"] 은 원장에만 남는다.
        # 판 안에 '언제까지' 를 반드시 넣는다(_frame.js 의 Frame.period). 날짜가 읽히면 날짜로,
        # 안 읽히면 사이트 표기 그대로, 아무 표기도 없으면 '상시' — 지어내지는 않는다.
        "until": _until(job),
        "career": job.get("career", ""),
        "sections": sections,
        "toc": toc,
    }


def _font_faces(brand: dict | None) -> str:
    """brands/*.json 의 ui.embed_fonts 를 data: URI @font-face 로. 렌더러는 file:// 을 못 읽는다."""
    faces = []
    kinds = {".ttf": ("font/ttf", "truetype"), ".otf": ("font/otf", "opentype"), ".woff2": ("font/woff2", "woff2")}
    for family, spec in ((brand or {}).get("ui", {}).get("embed_fonts") or {}).items():
        # "경로" 한 개(굵기 하나로 전 범위) 또는 [{"src": 경로, "weight": 700}, ...] (굵기별 파일)
        entries = [{"src": spec, "weight": "300 900"}] if isinstance(spec, str) else spec
        for e in entries:
            path = LAB_DIR / e["src"]
            if not path.is_file():
                continue
            mime, fmt = kinds.get(path.suffix.lower(), kinds[".ttf"])
            b64 = base64.b64encode(path.read_bytes()).decode()
            faces.append(f"@font-face{{font-family:'{family}';src:url(data:{mime};base64,{b64}) format('{fmt}');"
                         f"font-weight:{e['weight']};font-display:block}}")
    return "\n".join(faces)


IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml"}


def _brand_images(brand: dict | None) -> dict:
    """brands/*.json 의 images {이름: 경로} → {이름: data: URI}. 판은 D.brand_images.<이름> 으로 쓴다."""
    out = {}
    for name, rel in ((brand or {}).get("images") or {}).items():
        path = LAB_DIR / (rel["src"] if isinstance(rel, dict) else rel)
        if path.is_file():
            mime = IMAGE_MIME.get(path.suffix.lower(), "application/octet-stream")
            out[name] = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
    return out


def html_for(job_key: str, fmt_id: str = "ig_portrait", *, palette: str = "",
             template: Path = TEMPLATE) -> str:
    composed = compose(job_key, fmt_id, palette=palette)
    if template == BRAND_FRAME:
        brand = composed.get("brand") or {}
        if not brand.get("frame"):
            raise KeyError(f"브랜드 전용 판이 없다: {composed['company']} — brands/*.json 의 frame (BRAND_RESEARCH.md)")
        template = TEMPLATE.with_name(brand["frame"])
    composed["brand_images"] = _brand_images(composed.get("brand"))
    data = json.dumps(composed, ensure_ascii=False)
    html = template.read_text(encoding="utf-8").replace("/*__DATA__*/", data.replace("</", "<\\/"))
    html = html.replace("/*__FONTS__*/", _font_faces(composed.get("brand")))
    return html.replace("/*__FRAME_JS__*/", FRAME_JS.read_text(encoding="utf-8"))


def render_onepage(job_key: str, fmt_id: str = "ig_portrait", *, palette: str = "",
                   frame: str = "onepage", out_dir: Path | None = None) -> tuple[Path, dict]:
    """전문을 한 장에. (경로, 스크립트가 고른 배치·글자 크기)."""
    fmt = FORMATS[fmt_id]
    html = html_for(job_key, fmt_id, palette=palette, template=FRAMES[frame])
    dest_dir = out_dir or (OUT / job_key)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{frame}_{fmt_id}.jpg"
    page = _page_maker().new_page(viewport={"width": fmt["w"], "height": fmt["h"]})
    try:
        page.set_content(html, wait_until="load")
        page.wait_for_function("window.__paged === true", timeout=30000)
        page.wait_for_timeout(120)
        layout = page.evaluate("window.__layout")
        page.query_selector(".sheet").screenshot(path=str(dest), type="jpeg", quality=95)
    finally:
        page.close()
    # 인스타는 1080 폭 기준으로 보여 준다. 이보다 작으면 폰에서 확대 없이는 못 읽는다.
    if layout["font_px"] * 1080 / fmt["w"] < MIN_READABLE_PX:
        print(f"[onepage] 경고: 본문 {layout['font_px']}px — 확대하지 않으면 읽기 어렵다")
    return dest, layout


def render(job_key: str, fmt_id: str = "ig_portrait", *, palette: str = "",
           out_dir: Path | None = None) -> list[Path]:
    fmt = FORMATS[fmt_id]
    html = html_for(job_key, fmt_id, palette=palette)
    dest = out_dir or (OUT / job_key / f"carousel_{fmt_id}")
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.jpg"):      # 장 수가 줄었을 때 옛 장이 섞이지 않게
        old.unlink()

    page = _page_maker().new_page(viewport={"width": fmt["w"], "height": fmt["h"]})
    try:
        page.set_content(html, wait_until="load")
        page.wait_for_function("window.__paged === true", timeout=15000)
        page.wait_for_timeout(120)
        paths = []
        for i, slide in enumerate(page.query_selector_all(".slide"), 1):
            p = dest / f"{i:02d}.jpg"
            slide.screenshot(path=str(p), type="jpeg", quality=92)
            paths.append(p)
    finally:
        page.close()
    if len(paths) > IG_MAX_SLIDES:
        print(f"[carousel] 경고: {len(paths)}장 — 인스타 캐러셀은 {IG_MAX_SLIDES}장까지다")
    return paths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_key", help="예: wanted-364849")
    ap.add_argument("--format", dest="fmt", default="ig_portrait", choices=list(FORMATS))
    ap.add_argument("--palette", default="", choices=["", *PALETTES])
    ap.add_argument("--one", action="store_true", help="여러 장 대신 한 장에 전부")
    ap.add_argument("--frame", default="onepage", choices=[*FRAMES, "all"], help="--one 일 때 쓸 틀")
    args = ap.parse_args()
    try:
        if args.one:
            for frame in (list(FRAMES) if args.frame == "all" else [args.frame]):
                dest, layout = render_onepage(args.job_key, args.fmt, palette=args.palette, frame=frame)
                print(f"[onepage] {frame}: {layout['columns']}단 · 본문 {layout['font_px']}px → {dest}")
            return
        paths = render(args.job_key, args.fmt, palette=args.palette)
        print(f"[carousel] {len(paths)}장 → {paths[0].parent}")
    finally:
        shutdown()


if __name__ == "__main__":
    main()
