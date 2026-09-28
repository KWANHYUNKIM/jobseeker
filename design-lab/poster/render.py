"""HTML 한 장 → 실제 이미지. Playwright 크로미움으로 캔버스 크기 그대로 찍는다.

브라우저는 비싸다(8GB 머신). 한 번 띄워 두고 페이지만 갈아 끼운다.
    python -m poster.render wanted-364663 --template brand_ridi --format ig_portrait
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import assets, jobsource, templates
from .model import FORMATS, build_spec

LAB_DIR = Path(__file__).resolve().parent.parent
OUT = LAB_DIR / "out"

_browser = None
_pw = None


def _page_maker():
    global _browser, _pw
    if _browser is None:
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(args=["--font-render-hinting=none"])
    return _browser


def shutdown() -> None:
    global _browser, _pw
    if _browser is not None:
        _browser.close()
        _browser = None
    if _pw is not None:
        _pw.stop()
        _pw = None


def compose(job_key: str, *, palette: str = "") -> dict:
    """공고 키 → 포스터 원고(dict). 회사 이미지가 있으면 여기서 붙는다."""
    job = jobsource.get(job_key)
    if not job:
        raise KeyError(f"모르는 공고: {job_key}")
    spec = build_spec(job, mark=assets.mark(job["company"]), palette=palette)
    return spec.as_dict()


def html_for(job_key: str, template_id: str, fmt_id: str, *, palette: str = "") -> str:
    fmt = FORMATS.get(fmt_id)
    if not fmt:
        raise KeyError(f"모르는 포맷: {fmt_id}")
    # 판 엔진이 둘이다. 여기(templates.render)는 {{key}} 치환기 — 스튜디오가 처음부터 쓰던 길이다.
    # 회사 전용 판은 그 길로 못 간다: /*__DATA__*/ 에 원고를 통째로 넣고 _frame.js 가 글자 크기를
    # 맞추는 구조라 치환기로 그리면 빈 판이 나온다. 그래서 engine:"frame" 인 틀은 carousel 로 넘긴다.
    # (carousel 을 위에서 import 하면 순환이 된다 — carousel 도 이 패키지를 쓴다.)
    meta = templates.TEMPLATES.get(template_id)
    if meta and meta.get("engine") == "frame":
        from . import carousel
        return carousel.html_for(job_key, fmt_id, palette=palette,
                                 template=templates.TPL_DIR / meta["file"])
    return templates.render(template_id, compose(job_key, palette=palette), fmt)


def render(job_key: str, template_id: str = "", fmt_id: str = "ig_portrait",
           *, palette: str = "", out_dir: Path | None = None) -> Path:
    fmt = FORMATS[fmt_id]
    html = html_for(job_key, template_id, fmt_id, palette=palette)
    dest_dir = out_dir or (OUT / job_key)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{template_id}_{fmt_id}.jpg"

    browser = _page_maker()
    page = browser.new_page(viewport={"width": fmt["w"], "height": fmt["h"]})
    try:
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(120)  # 웹폰트/이미지 디코딩 여유
        page.screenshot(path=str(dest), type="jpeg", quality=92)
    finally:
        page.close()
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_key", help="예: wanted-364663")
    ap.add_argument("--template", required=True, choices=list(templates.TEMPLATES))
    ap.add_argument("--format", dest="fmt", default="ig_portrait", choices=list(FORMATS))
    ap.add_argument("--palette", default="")
    args = ap.parse_args()
    try:
        p = render(args.job_key, args.template, args.fmt, palette=args.palette)
        print(f"[render] {p}")
    finally:
        shutdown()


if __name__ == "__main__":
    main()
