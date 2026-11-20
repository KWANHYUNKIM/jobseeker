"""강의 영상 한 편을 '읽을 수 있는 재료'로 바꾼다 — 자막(말) + 장면(그림).

Claude 는 영상을 직접 보지도 듣지도 못한다. 그래서 회차마다 이 스크립트로
  1) 자막을 받아(공식 자막 → 없으면 자동 자막) 타임스탬프가 붙은 대본으로 풀고
  2) 저화질 영상을 받아 일정 간격으로 장면을 떼어 내고
  3) 장면을 한 장에 여러 칸씩 이어 붙인 '밀착 인화(contact sheet)'를 만든다
— 그러면 대본은 텍스트로, 판서·슬라이드는 그림으로 읽을 수 있다.

재료는 전부 `catch_capture/var/lectures/<영상 id>/` 에 둔다(커밋하지 않는다, 공개하지 않는다).
뷰어에 나가는 것은 이 재료를 읽고 **우리 말로 다시 쓴 노트**(public/lectures/)뿐이다 —
원본 장면·대본·영상은 옮기지 않는다. 영상은 장면을 떼고 나면 지운다(--keep-video 로 남긴다).

    python lecture-engine/fetch.py 9vM4p9NN0Ts                # 기본: 30초마다 한 장, 4×4 인화
    python lecture-engine/fetch.py 9vM4p9NN0Ts --every 20 --grid 3
    python lecture-engine/fetch.py <id> --subs-only           # 자막만

필요한 것: yt-dlp(pip), imageio-ffmpeg(pip — ffmpeg 바이너리를 같이 준다), node(유튜브 JS 풀이).
"""
from __future__ import annotations

import argparse
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "catch_capture" / "var" / "lectures"


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg 이 없다 — `pip install imageio-ffmpeg` 또는 ffmpeg 설치")


def ytdlp(*args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--no-warnings",
           "--ffmpeg-location", ffmpeg_exe(), *args]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


def fetch_meta(vid: str, out: Path) -> dict:
    r = ytdlp("--skip-download", "--dump-json", f"https://www.youtube.com/watch?v={vid}")
    if r.returncode != 0:
        sys.exit(f"메타데이터 실패: {r.stderr[-500:]}")
    raw = json.loads(r.stdout)
    meta = {k: raw.get(k) for k in ("id", "title", "channel", "channel_url", "duration", "upload_date",
                                     "view_count", "description", "license", "language")}
    meta["chapters"] = [{"start": c.get("start_time"), "title": c.get("title")} for c in raw.get("chapters") or []]
    meta["subs"] = sorted((raw.get("subtitles") or {}).keys())
    meta["auto_subs"] = sorted(k for k in (raw.get("automatic_captions") or {}) if k.endswith("-orig") or k in ("en", "ko"))
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


TS = re.compile(r"(\d+):(\d+):(\d+)[.,](\d+)\s*-->")


def vtt_to_lines(path: Path) -> list[tuple[int, str]]:
    """VTT → (초, 문장). 자동 자막은 같은 줄이 겹쳐 반복되므로 직전과 같은 글은 버린다."""
    out: list[tuple[int, str]] = []
    cur = 0
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TS.match(line)
        if m:
            h, mi, s, _ = map(int, m.groups())
            cur = h * 3600 + mi * 60 + s
            continue
        if not line.strip() or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        text = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append((cur, text))
    return out


def fetch_subs(vid: str, out: Path, meta: dict) -> Path | None:
    # 자동 자막은 원어 트랙이 '<언어>-orig' 다(한국어 영상은 ko-orig). 번역 트랙보다 원어를 먼저 쓴다.
    langs = "en.*,ko.*" if meta["subs"] else "en-orig,ko-orig,en,ko"
    flag = "--write-subs" if meta["subs"] else "--write-auto-subs"
    ytdlp("--skip-download", flag, "--sub-langs", langs, "--sub-format", "vtt",
          "-o", str(out / "subs.%(ext)s"), f"https://www.youtube.com/watch?v={vid}")
    vtts = sorted(glob.glob(str(out / "subs*.vtt")), key=lambda p: ("-orig" not in p, "ko" in p, p))
    if not vtts:
        return None
    lines = vtt_to_lines(Path(vtts[0]))
    # 1분 단위 문단으로 묶는다 — 노트의 타임스탬프가 원본 영상의 위치로 이어진다.
    paras: dict[int, list[str]] = {}
    for sec, text in lines:
        paras.setdefault(sec // 60, []).append(text)
    dst = out / "transcript.txt"
    with dst.open("w", encoding="utf-8") as f:
        for m in sorted(paras):
            f.write(f"[{m // 60:d}:{m % 60:02d}:00] {' '.join(paras[m])}\n\n")
    return dst


def fetch_frames(vid: str, out: Path, every: int, grid: int, keep: bool) -> int:
    video = out / "video.mp4"
    if not video.exists():
        r = ytdlp("-f", "bv*[height<=480][ext=mp4]/bv*[height<=480]/b[height<=480]/worst",
                  "-o", str(out / "video.%(ext)s"), "--remux-video", "mp4",
                  f"https://www.youtube.com/watch?v={vid}")
        cands = sorted(out.glob("video.*"))
        if not cands:
            sys.exit(f"영상 받기 실패: {r.stderr[-500:]}")
        if cands[0] != video:
            cands[0].rename(video)
    frames = out / "frames"
    frames.mkdir(exist_ok=True)
    for old in frames.glob("*.jpg"):
        old.unlink()
    ff = ffmpeg_exe()
    # 장면: every 초마다 한 장. 파일 이름의 번호 × every = 영상 속 초.
    subprocess.run([ff, "-loglevel", "error", "-i", str(video), "-vf", f"fps=1/{every},scale=640:-2",
                    "-q:v", "4", str(frames / "f%05d.jpg")], check=True)
    n = len(list(frames.glob("*.jpg")))
    # 밀착 인화: grid×grid 칸에 시각을 찍어 이어 붙인다 — 한 번 읽을 때 grid² 장면을 본다.
    sheets = out / "sheets"
    sheets.mkdir(exist_ok=True)
    for old in sheets.glob("*.jpg"):
        old.unlink()
    per = grid * grid
    draw = (f"fps=1/{every},scale=480:-2,"
            "drawtext=text='%{pts\\:hms}':x=8:y=8:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6,"
            f"tile={grid}x{grid}")
    subprocess.run([ff, "-loglevel", "error", "-i", str(video), "-vf", draw, "-q:v", "5",
                    str(sheets / "s%03d.jpg")], check=False)
    if not list(sheets.glob("*.jpg")):  # drawtext 에 글꼴이 없는 환경 — 시각 없이 붙인다
        subprocess.run([ff, "-loglevel", "error", "-i", str(video), "-vf",
                        f"fps=1/{every},scale=480:-2,tile={grid}x{grid}", "-q:v", "5",
                        str(sheets / "s%03d.jpg")], check=True)
    (out / "frames.json").write_text(json.dumps(
        {"every_sec": every, "frames": n, "grid": grid, "per_sheet": per,
         "sheet_sec": every * per}, indent=2), encoding="utf-8")
    if not keep:
        video.unlink(missing_ok=True)
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("vid")
    ap.add_argument("--every", type=int, default=30, help="장면 간격(초)")
    ap.add_argument("--grid", type=int, default=4, help="밀착 인화 한 장의 칸 수(grid×grid)")
    ap.add_argument("--subs-only", action="store_true")
    ap.add_argument("--keep-video", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    vid = re.sub(r".*(?:v=|youtu\.be/)([\w-]{11}).*", r"\1", a.vid)
    out = WORK / vid
    out.mkdir(parents=True, exist_ok=True)
    meta = fetch_meta(vid, out)
    t = fetch_subs(vid, out, meta)
    print(f"[meta] {meta['title']} · {meta['channel']} · {meta['duration']}s · 공식자막 {meta['subs'][:5]}")
    print(f"[subs] {t or '없음'}")
    if not a.subs_only:
        n = fetch_frames(vid, out, a.every, a.grid, a.keep_video)
        print(f"[frames] {n}장 → {out / 'sheets'} (한 장 = {a.every * a.grid * a.grid}초)")
    print(f"[dir] {out}")


if __name__ == "__main__":
    main()
