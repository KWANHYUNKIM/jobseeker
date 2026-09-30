"""모션 릴스 — 대본(JSON)을 장면으로 움직여 mp4 로 굽는다.

`reel.py` 는 캐러셀 판을 넘기는 슬라이드 쇼였다. 여기는 **이야기**다: 훅 → 장면(지도·대화·숫자) →
이 회사가 일하는 방식 → 지원자가 준비할 것 → 저장. 대본은 `reels/<이름>.json` 에 두고, 모든 사실 문장은
`sources` 에 근거를 적는다(인물은 그림 캐릭터 = 연출, 화면에 '연출' 이라고 쓴다).

장면 길이는 **박자 단위**다(`beats`). 곡은 `poster.beats` 로 만든다 — 장면이 바뀌는 순간이 마디와 맞는다.
프레임은 `templates/reelfx.html` 의 `render(t)` 를 시간마다 불러 찍으므로 CSS 애니메이션과 달리 결정적이다.

    python -m poster.reelfx reels/oliveyoung.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from . import beats, video

LAB_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).resolve().parent / "templates" / "reelfx.html"
OUT = LAB_DIR / "out" / "reelfx"
FPS = 30


def render(script: Path, *, fps: int = FPS) -> Path:
    spec = json.loads(script.read_text(encoding="utf-8"))
    style = spec.get("music", "bright")
    beat = beats.beat_seconds(style)
    for sc in spec["scenes"]:
        sc["dur"] = round(sc.get("beats", 8) * beat, 4)
    total = sum(sc["dur"] for sc in spec["scenes"])
    spec["beat"] = beat
    name = script.stem
    frames = OUT / name / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)

    from .render import _page_maker, shutdown
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "/*__DATA__*/", json.dumps(spec, ensure_ascii=False).replace("</", "<\\/"))
    page = _page_maker().new_page(viewport={"width": 1080, "height": 1920})
    try:
        page.set_content(html, wait_until="load")
        page.wait_for_function("window.__ready === true", timeout=30000)
        n = int(total * fps)
        for i in range(n):
            page.evaluate(f"window.render({i / fps:.4f})")
            page.screenshot(path=str(frames / f"{i:05d}.jpg"), type="jpeg", quality=90)
    finally:
        page.close()
        shutdown()

    audio = OUT / name / "music.wav"
    beats.build(audio, style, total + 0.5)
    dest = OUT / name / f"{name}.mp4"
    ff = video.ffmpeg_exe()
    cmd = [ff, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames / "%05d.jpg"),
           "-i", str(audio),
           "-vf", "scale=1080:1920:in_range=full:out_range=tv,format=yuv420p",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(fps),
           "-af", f"loudnorm=I={video.AUDIO_LUFS}:TP=-1.5:LRA=11,afade=t=out:st={max(0, total - 0.8):.2f}:d=0.8",
           "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", "-movflags", "+faststart", str(dest)]
    subprocess.run(cmd, check=True)
    bad = video.check(dest)
    if bad:
        raise RuntimeError("릴스 규격: " + "; ".join(bad))
    # 표지(첫 장면이 다 뜬 순간)와 스토리용 정지 화면
    shutil.copyfile(frames / f"{min(n - 1, int(fps * 2.2)):05d}.jpg", OUT / name / "cover.jpg")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(prog="poster.reelfx")
    ap.add_argument("script")
    ap.add_argument("--fps", type=int, default=FPS)
    a = ap.parse_args()
    p = render(Path(a.script), fps=a.fps)
    print(p, video.probe(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
