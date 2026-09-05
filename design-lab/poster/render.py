"""HTML 한 장 → 실제 이미지. Playwright 크로미움으로 캔버스 크기 그대로 찍는다.

브라우저는 비싸다(8GB 머신). 한 번 띄워 두고 페이지만 갈아 끼운다.
    python -m poster.render wanted-364663 --template role_hero --format ig_portrait
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
    return templates.render(template_id, compose(job_key, palette=palette), fmt)


def render(job_key: str, template_id: str = "role_hero", fmt_id: str = "ig_portrait",
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
    ap.add_argument("--template", default="role_hero", choices=list(templates.TEMPLATES))
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
