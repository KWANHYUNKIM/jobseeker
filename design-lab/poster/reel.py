"""4:5 게시물 → 9:16 릴스 한 편.

판은 캐러셀용 1080×1350 으로 찍혀 있다. 릴스 캔버스(1080×1920)에 그대로 넣으면 위아래에
검은 띠가 남으므로, 장면마다 **위에 시리즈 이름·아래에 계정과 안내** 를 시리즈 색으로 채워
9:16 장면을 만든 뒤 `poster.video.build` 로 잇는다. 판을 다시 그리지 않는다.

글이 많은 판(가이드·데이터)은 1.8초로 못 읽는다 — 종류마다 한 장의 시간을 다르게 둔다.
공고 전문 판은 릴스에서 읽히지 않으므로 앞 몇 장만 싣고 "전문은 게시물에서" 로 넘긴다.

  python -m poster.reel inbox/<id> [--hold 3] [--max 8]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import video

LAB_DIR = Path(__file__).resolve().parent.parent
AUDIO = LAB_DIR / "assets" / "audio" / "bed_calm.wav"
W, H, SW, SH = 1080, 1920, 1080, 1350
TOP = (H - SH) // 2

#: 종류 → (바탕, 글자, 머리말, 한 장 초). 캐러셀 시리즈 색과 같다(CONTENT_PLAN.md 3절).
STYLE = {
    "insight": ("#f5f2ea", "#111317", "[데이터로 본 채용]", 3.0),
    "guide": ("#102a43", "#f4f1e8", "[들어가려면]", 3.2),
    "company": (None, None, "[회사 해부]", 2.2),
    "newgrad": ("#e9f6ee", "#0c2a1b", "[신입 가능]", 2.2),
}


def _font(size: int) -> ImageFont.FreeTypeFont:
    for f in ("C:/Windows/Fonts/malgunbd.ttf", "/System/Library/Fonts/AppleSDGothicNeo.ttc",
              "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def frames(bundle_dir: Path, out: Path, *, limit: int = 8) -> tuple[list[Path], float]:
    b = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    col = b.get("collection") or {}
    kind = col.get("kind", "")
    bg, ink, head, hold = STYLE.get(kind, ("#111317", "#ffffff", "", 2.2))
    if kind == "company":
        brand = col.get("brand") or {}
        bg, ink = brand.get("accent") or "#111317", brand.get("on") or "#ffffff"
    # 위 띠의 말 — 판 안에 시리즈 이름이 이미 있으니 여기는 그 게시물의 제목이다
    if kind == "company":
        head = f"{col.get('value', '')} 개발자 {col.get('count', '')}자리"
    elif kind in ("insight", "guide"):
        head = col.get("title") or b.get("role") or head
    else:
        head = f"{col.get('kicker', '')} · {col.get('count', '')}곳".strip(" ·")
    imgs = [bundle_dir / "poster.jpg"] + sorted(bundle_dir.glob("slide_*.jpg"))
    imgs = imgs[:limit]
    out.mkdir(parents=True, exist_ok=True)
    f_head, f_foot = _font(54), _font(38)
    paths = []
    for i, src in enumerate(imgs, 1):
        can = Image.new("RGB", (W, H), bg)
        can.paste(Image.open(src).convert("RGB").resize((SW, SH)), (0, TOP))
        d = ImageDraw.Draw(can)
        d.text((72, TOP // 2), head, font=f_head, fill=ink, anchor="lm")
        # 진행 표시 — 몇 장 중 몇 번째(글자 없이 막대만)
        x0, x1, y = 72, W - 72, TOP // 2 + 62
        seg = (x1 - x0) / len(imgs)
        for k in range(len(imgs)):
            d.rectangle([x0 + k * seg + 3, y, x0 + (k + 1) * seg - 3, y + 6],
                        fill=ink if k < i else _mix(bg, ink))
        foot = "전문은 게시물에서 · 프로필 링크" if i == len(imgs) else "저장해 두고 보세요"
        d.text((72, TOP + SH + (H - TOP - SH) // 2), foot, font=f_foot, fill=ink, anchor="lm")
        p = out / f"{i:02d}.jpg"
        can.save(p, quality=94)
        paths.append(p)
    return paths, hold


def _mix(a: str, b: str) -> tuple[int, int, int]:
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return tuple(int(x * .72 + y * .28) for x, y in zip(ca, cb))


def make(bundle_dir: Path, *, hold: float = 0.0, limit: int = 8) -> Path:
    scenes, default_hold = frames(bundle_dir, bundle_dir / "_reel", limit=limit)
    dest = bundle_dir / "reel.mp4"
    video.build(scenes, dest, hold=hold or default_hold, audio=AUDIO if AUDIO.exists() else None)
    bad = video.check(dest)
    if bad:
        raise RuntimeError("릴스 규격: " + "; ".join(bad))
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(prog="poster.reel")
    ap.add_argument("bundle")
    ap.add_argument("--hold", type=float, default=0.0)
    ap.add_argument("--max", type=int, default=8)
    a = ap.parse_args()
    p = make(Path(a.bundle), hold=a.hold, limit=a.max)
    print(p, video.probe(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
