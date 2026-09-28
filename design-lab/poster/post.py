"""공고 하나 또는 여러 건 → 게시물 한 벌(장 순서대로).

**표지는 게시물당 한 장이다.** 공고마다 한 장이 아니다 —
여섯 건이 한 게시물로 나가면 `표지 1 + 본문 6` 이지 `표지 6 + 본문 6` 이 아니다.
한 건만 나갈 때도 마찬가지로 `표지 1 + 본문 1` 이다.

**본문이 몇 장인지는 매체가 정한다.** `brands/<회사>.json` 의 `signature.medium.text_load` 가

    full      → 그 회사 판은 전문을 한 장에 담는다.
    그 밖     → 표지가 고른 한 줄만 싣고, 전문은 본문 장이 맡는다.

`full` 인 회사도 표지는 있다 — 표지는 '전문을 못 담아서' 있는 것이 아니라
게시물의 얼굴이기 때문이다.

    python -m poster.post wanted-353819                 # 표지 1 + 본문 1
    python -m poster.post wanted-A wanted-B wanted-C    # 표지 1 + 본문 3
    python -m poster.post wanted-353819 --queue

결과: out/<첫 공고키>/_post/01_표지.jpg, 02_본문…  그리고 나란히 본 _preview.jpg
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

from . import brands, carousel, jobsource
from .variants import _label_font

LAB_DIR = Path(__file__).resolve().parent.parent
OUT = LAB_DIR / "out"

#: 표지를 그리는 갈래. 판마다 이름이 다르지만 '기본 = 표지' 라는 규칙은 같다.
COVER_VARIANT = ""
#: 전문을 담는 갈래.
BODY_VARIANT = "full"


def plan(job_keys: list[str], kind: str = "", value: str = "") -> list[dict]:
    """게시물의 장 구성. 표지 한 장 + 공고마다 본문 한 장.

    표지는 게시물이 무엇인지에 따라 둘 중 하나다:
      공고 한 건    → 그 회사 판의 표지(회사가 곧 게시물의 얼굴이다)
      여러 건 묶음  → **공통점을 말하는 묶음 표지**(collection.py 의 카테고리)
    묶음인데 첫 회사 판을 표지로 쓰면 네 회사짜리 게시물이 한 회사 얼굴을 달게 된다.
    """
    jobs = []
    for k in job_keys:
        j = jobsource.get(k)
        if not j:
            raise KeyError(f"모르는 공고: {k}")
        jobs.append(j)

    companies = {j["company"] for j in jobs}
    head = jobs[0]
    brand = brands.find(head["company"]) or {}
    med = ((brand.get("signature") or {}).get("medium") or {})
    load = med.get("text_load", "")

    if len(jobs) > 1:
        cards = [{"job": head["key"], "variant": "", "cover_kind": kind, "cover_value": value,
                  "is_cover": True, "role": "묶음 표지",
                  "note": f"{len(jobs)}건의 공통점 — {kind}{(' ' + value) if value else ''}"}]
    else:
        cards = [{
            "job": head["key"], "variant": COVER_VARIANT, "cover_kind": "", "cover_value": "",
            "is_cover": True, "role": "표지", "note": f"단일 채용 · text_load={load or '미기록'}",
        }]
    for j in jobs:
        b = brands.find(j["company"]) or {}
        m = ((b.get("signature") or {}).get("medium") or {})
        # 전문을 한 장에 담는 회사는 그 판이 곧 본문이다(갈래를 따로 안 쓴다).
        one_sheet = m.get("text_load") == "full"
        cards.append({
            "job": j["key"],
            "variant": COVER_VARIANT if one_sheet else BODY_VARIANT,
            "role": "본문" if len(jobs) == 1 else f"본문 {j['company']}",
            "note": ("전문 한 장 판" if one_sheet else "표지가 못 담은 나머지"),
        })
    return cards


def _render_set_cover(job_keys: list[str], kind: str, value: str, fmt: str, dest: Path) -> None:
    """묶음 표지 — collection.py 의 카테고리 표지를 그대로 쓴다.

    카테고리는 이미 절차 안에 있다(이번주·마감임박·직군·회사규모·기술·신입). 여기서 새로
    만들지 않는다 — 묶음의 공통점을 말하는 문구도 그쪽이 들고 있다.

    **카테고리는 문구만 준다. 목록은 받은 공고 그대로다.**
    collection.build() 는 원래 색인 전체에서 그 카테고리에 맞는 공고를 *고르는* 함수라
    넘겨준 공고도 다시 걸러 낸다. 여기서는 이미 사람이 고른 것이므로 다시 거르면 안 된다 —
    표지가 '2곳' 이라 해 놓고 판이 넉 장 넘어가는 게시물이 나온다.
    """
    from . import collection
    from .carousel import FORMATS
    from .render import _page_maker

    rows = [j for j in (jobsource.get(k) for k in job_keys) if j]
    col = collection.build(kind, value=value, jobs=rows,
                           limit=len(job_keys), brand_only=False, verify=False)
    # 목록을 받은 순서 그대로 덮어쓴다(문구·껍질은 카테고리 것을 그대로 둔다)
    sizes = collection._sizes()
    col["jobs"] = [collection._entry(j) for j in rows]
    col["spares"] = []
    col["count"] = len(rows)
    col["short_by"] = 0
    col["size_label"] = {j["company"]: sizes.get(j["company"], "") for j in rows}

    f = FORMATS[fmt]
    page = _page_maker().new_page(viewport={"width": f["w"], "height": f["h"]})
    try:
        page.set_content(collection.cover_html(col, f), wait_until="load")
        page.wait_for_function("window.__ready === true", timeout=30000)
        page.query_selector(".sheet").screenshot(path=str(dest), type="jpeg", quality=95)
    finally:
        page.close()


def build(job_keys: list[str], fmt: str = "ig_portrait",
          kind: str = "", value: str = "") -> tuple[list[Path], list[dict]]:
    cards = plan(job_keys, kind, value)
    dest_dir = OUT / job_keys[0] / "_post"
    if dest_dir.exists():
        shutil.rmtree(dest_dir)          # 장 수가 줄었을 때 옛 장이 남지 않게
    dest_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for i, card in enumerate(cards, 1):
        safe = card["role"].replace(" ", "_").replace("/", "_")
        dst = dest_dir / f"{i:02d}_{safe}.jpg"
        if card.get("cover_kind"):
            _render_set_cover(job_keys, card["cover_kind"], card["cover_value"], fmt, dst)
            card["font_px"] = "—"
        else:
            src, layout = carousel.render_onepage(card["job"], fmt, frame="brand",
                                                  variant=card["variant"])
            shutil.copyfile(src, dst)
            card["font_px"] = layout["font_px"]
        paths.append(dst)

    # 못 읽는 장을 두 장으로 나눈다.
    # 판이 한 장에 담을 수 있는 글의 양에는 끝이 있다 — 34항목짜리 공고를 우겨넣으면
    # 본문이 13px 까지 깎여 폰에서 못 읽는다. 그러면 그 장 하나를 a/b 로 쪼갠다
    # (하는 일·조건 / 우대·복지). 판이 그 갈래를 모르면 원래 장을 그대로 둔다.
    paths, cards = _split_unreadable(paths, cards, fmt, dest_dir)
    return paths, cards


def _split_unreadable(paths: list[Path], cards: list[dict], fmt: str,
                      dest_dir: Path) -> tuple[list[Path], list[dict]]:
    from .carousel import FORMATS, MIN_READABLE_PX
    scale = 1080 / FORMATS[fmt]["w"]

    out_p, out_c = [], []
    for p, c in zip(paths, cards):
        px = c["font_px"]
        # 표지는 나누지 않는다 — 고른 한 줄이지 전문이 아니다. 나눌 것이 애초에 없다.
        if c.get("is_cover") or not isinstance(px, (int, float)) or px * scale >= MIN_READABLE_PX:
            out_p.append(p); out_c.append(c); continue
        halves = []
        for tag in ("a", "b"):
            try:
                src, layout = carousel.render_onepage(c["job"], fmt, frame="brand",
                                                      variant=f"{c['variant'] or 'full'}-{tag}")
            except Exception:
                halves = []; break
            halves.append((src, layout))
        # 쪼갠 쪽이 더 나쁘면 원래 한 장을 그대로 둔다
        if len(halves) != 2 or min(h[1]["font_px"] for h in halves) <= px:
            print(f"[post] {c['role']} 못 나눔 — 한 장 그대로({px}px)")
            out_p.append(p); out_c.append(c); continue
        for i, (src, layout) in enumerate(halves, 1):
            nc = dict(c)
            nc["role"] = f"{c['role']} {i}/2"
            nc["note"] = "한 장에 안 들어가 나눔" if i == 1 else "이어지는 장"
            nc["font_px"] = layout["font_px"]
            out_c.append(nc)
            out_p.append(src)
        print(f"[post] {c['role']} 나눔 — {px}px → "
              f"{halves[0][1]['font_px']}px / {halves[1][1]['font_px']}px")

    # 나눈 장이 생겨 번호가 밀렸으니 파일 이름을 다시 매긴다
    final = []
    for i, (src, c) in enumerate(zip(out_p, out_c), 1):
        safe = c["role"].replace(" ", "_").replace("/", "-")
        dst = dest_dir / f"{i:02d}_{safe}.jpg"
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
            if src.parent == dest_dir:
                src.unlink(missing_ok=True)
        final.append(dst)
    return final, out_c


def preview(job_key: str, paths: list[Path], cards: list[dict], width: int = 560) -> Path:
    tiles = [Image.open(p).convert("RGB") for p in paths]
    tiles = [im.resize((width, round(im.height * width / im.width)), Image.LANCZOS) for im in tiles]
    pad, gap, top = 26, 20, 92
    f_n, f_s = _label_font(26), _label_font(18)
    h = max(t.height for t in tiles)
    canvas = Image.new("RGB", (pad * 2 + width * len(tiles) + gap * (len(tiles) - 1),
                               top + h + pad), "#0f0f11")
    d = ImageDraw.Draw(canvas)
    for i, (im, card) in enumerate(zip(tiles, cards)):
        x = pad + i * (width + gap)
        d.text((x, 24), f"{i + 1}. {card['role']}", font=f_n, fill="#ffffff")
        px = card["font_px"]
        tail = "" if px == "—" else f" · 본문 {px}px"
        d.text((x, 58), card["note"] + tail, font=f_s, fill="#8b8b93")
        canvas.paste(im, (x, top))
    out = OUT / job_key / "_post" / "_preview.jpg"
    canvas.save(out, quality=88)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_keys", nargs="+", help="공고 키 하나 또는 여러 개(한 게시물로 나갈 것들)")
    ap.add_argument("--format", dest="fmt", default="ig_portrait")
    ap.add_argument("--kind", default="", choices=["", "week", "deadline", "role", "size", "stack", "newgrad"],
                    help="묶음일 때 그 묶음의 공통점(collection.py 의 카테고리)")
    ap.add_argument("--value", default="", help="role: backend|frontend|data|infra|mobile / size: 대기업 / stack: React 등")
    ap.add_argument("--queue", action="store_true", help="발행 큐에 넣기까지 한다")
    args = ap.parse_args()
    try:
        if len(args.job_keys) > 1 and not args.kind:
            raise SystemExit(
                "묶음에는 --kind 가 있어야 한다 — 표지가 공통점을 말해야 하기 때문이다.\n"
                "  week 이번주 · deadline 마감임박 · role 직군(--value backend) ·\n"
                "  size 회사규모 · stack 기술 · newgrad 신입")
        paths, cards = build(args.job_keys, args.fmt, args.kind, args.value)
        for i, (p, c) in enumerate(zip(paths, cards), 1):
            px = c["font_px"]
            px = "  묶음 표지" if px == "—" else f"본문 {px:>5}px"
            print(f"  {i}. {c['role']:14s} {c['note']:34s} {px} → {p.name}")
        shot = preview(args.job_keys[0], paths, cards)
        print(f"[post] 공고 {len(args.job_keys)}건 → 표지 1 + 본문 {len(paths) - 1} = {len(paths)}장")
        print(f"[post] 미리보기 {shot}")

        if args.queue:
            from publish import queue
            item = queue.add(args.job_keys[0], template="brand",
                             formats=[args.fmt], platforms=["instagram"],
                             note=f"표지 1 + 본문 {len(paths) - 1}")
            print(f"[post] 큐에 넣음 {item['id']}")
    finally:
        carousel.shutdown()


if __name__ == "__main__":
    main()
