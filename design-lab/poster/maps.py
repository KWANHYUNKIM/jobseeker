"""근무지 지도 한 장 — OpenStreetMap 타일을 이어 붙이고 핀과 거리 원을 그린다.

릴스 판의 '위치' 장면에 쓴다. 타일은 OSM 표준 타일(© OpenStreetMap contributors, 판마다 표기)이고
한 판에 열 몇 장만 받으며 `assets/maps/tiles/` 에 남겨 두고 다시 받지 않는다(OSM 타일 사용 정책 —
대량·오프라인 수집 금지, 식별 가능한 User-Agent). 바탕은 판 색에 맞춰 어둡게 눌러 쓴다.

  render(37.4953, 127.0294, zoom=16, label="강남대로 364") → PIL.Image (1600×1200)
"""
from __future__ import annotations

import io
import math
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

LAB_DIR = Path(__file__).resolve().parent.parent
TILES = LAB_DIR / "assets" / "maps" / "tiles"
UA = {"User-Agent": "devjobseeker-design-lab/1.0 (static social images; molba06@naver.com)"}
TILE = 256
CREDIT = "지도 © OpenStreetMap contributors"


def _xy(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x * TILE, y * TILE


def _tile(z: int, x: int, y: int) -> Image.Image:
    p = TILES / str(z) / str(x) / f"{y}.png"
    if not p.is_file():
        p.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(f"https://tile.openstreetmap.org/{z}/{x}/{y}.png", headers=UA)
        p.write_bytes(urllib.request.urlopen(req, timeout=30).read())
        time.sleep(0.3)
    return Image.open(p).convert("RGB")


def _font(size: int) -> ImageFont.FreeTypeFont:
    for f in ("C:/Windows/Fonts/malgunbd.ttf", "/System/Library/Fonts/AppleSDGothicNeo.ttc",
              "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def meters(a: tuple[float, float], b: tuple[float, float]) -> float:
    """두 좌표 사이 직선거리(m)."""
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def render(lat: float, lon: float, *, zoom: int = 16, size: tuple[int, int] = (1600, 1200),
           label: str = "", landmark: tuple[float, float, str] | None = None,
           accent: str = "#ffe066") -> Image.Image:
    """(lat, lon) 을 가운데에 둔 지도. landmark 를 주면 그곳에도 작은 점과 이름을 찍는다."""
    w, h = size
    # 레티나처럼 보이게 한 단계 위 줌의 타일을 받아 반으로 줄인다
    z = zoom + 1
    cx, cy = _xy(lat, lon, z)
    big_w, big_h = w * 2 // 2, h * 2 // 2
    x0, y0 = cx - big_w, cy - big_h
    canvas = Image.new("RGB", (big_w * 2, big_h * 2))
    for tx in range(int(x0 // TILE), int((cx + big_w) // TILE) + 1):
        for ty in range(int(y0 // TILE), int((cy + big_h) // TILE) + 1):
            canvas.paste(_tile(z, tx, ty), (int(tx * TILE - x0), int(ty * TILE - y0)))
    img = canvas.resize((w, h), Image.LANCZOS)
    # 판 색에 맞춰 어둡게 — 흑백으로 눌러 남색을 살짝 입힌다
    g = ImageOps.grayscale(img)
    g = ImageEnhance.Contrast(g).enhance(1.15)
    img = ImageOps.colorize(g, black="#10131c", white="#8a93aa")
    d = ImageDraw.Draw(img)

    def pt(la: float, lo: float) -> tuple[float, float]:
        px, py = _xy(la, lo, z)
        return (px - x0) / 2, (py - y0) / 2

    if landmark:
        lx, ly = pt(landmark[0], landmark[1])
        if 0 <= lx <= w and 0 <= ly <= h:
            d.line([pt(lat, lon), (lx, ly)], fill="#ffffff", width=6)
            d.ellipse([lx - 18, ly - 18, lx + 18, ly + 18], fill="#ffffff")
            d.text((lx + 28, ly - 34), landmark[2], font=_font(60), fill="#ffffff",
                   stroke_width=6, stroke_fill="#0b0d14")
    px, py = pt(lat, lon)
    for r, a in ((90, 60), (54, 110)):
        ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse([px - r, py - r, px + r, py + r], fill=(255, 224, 102, a))
        img = Image.alpha_composite(img.convert("RGBA"), ring).convert("RGB")
    d = ImageDraw.Draw(img)
    d.ellipse([px - 26, py - 26, px + 26, py + 26], fill=accent, outline="#141218", width=6)
    if label:
        f = _font(68)
        d.text((px + 48, py - 44), label, font=f, fill=accent, stroke_width=7, stroke_fill="#0b0d14")
    d.text((w - 24, h - 20), CREDIT, font=_font(26), fill="#c9cfdb", anchor="rb",
           stroke_width=4, stroke_fill="#0b0d14")
    return img


def data_uri(img: Image.Image) -> str:
    import base64
    b = io.BytesIO()
    img.save(b, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
