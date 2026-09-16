"""판 여러 장 → 릴스용 mp4 한 개.

묶음(카테고리)을 캐러셀 대신 **영상 한 편**으로 내보낼 때 쓴다. 판을 다시 만들지
않는다 — 이미 찍어 둔 장면(1080×1920)을 순서대로 이어 붙이고 사이를 짧게 겹쳐
넘긴다. 그래서 여기서 하는 일은 사실상 ffmpeg 한 번 부르는 것뿐이다.

## 소리 — 기본은 무음, 원하면 우리 음원을 굽는다

메타 API 로는 **인스타그램 음원 라이브러리를 못 쓴다.** 그리고 이미 올라간 릴스에는
나중에 오디오를 붙일 수도 없다. 그러니 API 로 올릴 거면 길은 둘뿐이다 —
무음으로 두거나, **우리가 권리를 가진 음원을 영상에 구워 넣거나.**

`audio=` 를 주면 그 파일을 깐다. 안 주면 무음 AAC 트랙을 깐다(`anullsrc`) —
트랙 자체가 없는 mp4 는 인스타가 종종 되돌려 보내기 때문에 무음이라도 있어야 한다.

음원을 넣을 때 세 가지를 자동으로 한다.

- **길이 맞추기** — 짧으면 반복하고 영상 길이에서 자른다.
- **소리 크기 고르기**(`loudnorm` I=-16) — 트랙마다 녹음 레벨이 달라서, 안 맞추면
  어떤 판은 안 들리고 어떤 판은 폰에서 찢어진다. -16 LUFS 는 소셜 영상의 통용값이다.
- **처음·끝 페이드** — 뚝 시작하고 뚝 끊기는 소리는 그 자체로 아마추어 신호다.

**권리는 우리가 확인한다.** 이 함수는 파일을 받을 뿐 출처를 묻지 않는다.
저작권 있는 곡을 넣으면 인스타가 음소거하거나 계정에 경고가 붙는다.

## 값을 이렇게 고른 이유

- **장당 1.8초**(`HOLD`) — 회사 이름과 직무 한 줄을 읽는 데 필요한 최소치다.
  더 짧으면 못 읽고, 더 길면 10장짜리가 25초를 넘겨 끝까지 안 본다.
- **겹침 0.4초**(`FADE`) — 넘어가는 게 보일 만큼만. 이 값이 크면 읽는 시간이 준다.
- **yuv420p · faststart** — 둘 중 하나만 빠져도 메타가 "처리 실패" 만 돌려주고
  이유를 말해 주지 않는다. faststart 는 moov 를 앞으로 옮겨 메타 서버가 파일을
  다 받기 전에 읽을 수 있게 한다.

ffmpeg 은 세 군데에서 찾는다: `$FFMPEG` → PATH → imageio-ffmpeg 이 들고 있는 것.
맥에는 `brew install ffmpeg`, 없으면 `pip install imageio-ffmpeg` 로도 된다.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

#: 한 장이 화면에 머무는 시간(초). 겹치는 구간을 뺀 '읽는 시간'이다.
HOLD = 1.8
#: 장과 장이 겹치는 시간(초)
FADE = 0.4
FPS = 30
#: 릴스 하한. 판이 한두 장뿐이면 여기에 못 미쳐 메타가 거절한다.
MIN_SECONDS = 3.0
#: 릴스 상한은 15분이지만, 끝까지 보는 영상은 그보다 훨씬 짧다.
MAX_SECONDS = 90.0


class FFmpegMissing(RuntimeError):
    pass


def ffmpeg_exe() -> str:
    """ffmpeg 실행 파일 경로. 없으면 어디를 봤는지까지 말하고 죽는다."""
    if (env := os.environ.get("FFMPEG")):
        if Path(env).is_file():
            return env
        raise FFmpegMissing(f"$FFMPEG 가 가리키는 파일이 없습니다: {env}")
    if (found := shutil.which("ffmpeg")):
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:                                               # noqa: BLE001
        pass
    raise FFmpegMissing(
        "ffmpeg 을 찾지 못했습니다. 셋 중 하나로 해결합니다:\n"
        "  1) brew install ffmpeg            (맥)\n"
        "  2) pip install imageio-ffmpeg     (파이썬이 들고 있는 것을 씀)\n"
        "  3) FFMPEG=/경로/ffmpeg 로 직접 지정")


def _ffprobe_exe(ffmpeg: str) -> str | None:
    """같은 자리의 ffprobe. imageio-ffmpeg 에는 없을 수 있어 None 을 허용한다."""
    if (found := shutil.which("ffprobe")):
        return found
    cand = Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix)
    return str(cand) if cand.is_file() else None


def duration_for(n_slides: int, *, hold: float = HOLD, fade: float = FADE) -> float:
    """장 수 → 완성된 영상 길이(초).

    장마다 (hold + fade) 만큼 두고 사이를 fade 만큼 겹치므로
    전체 = n*(hold+fade) - (n-1)*fade = n*hold + fade 가 된다.
    """
    if n_slides <= 0:
        return 0.0
    return n_slides * hold + fade


def _filter_chain(n: int, hold: float, fade: float, size: tuple[int, int]) -> str:
    """장면 정규화 + xfade 사슬.

    **정규화를 먼저 한다.** xfade 는 크기가 다른 두 입력을 붙이지 못하고, 섞였을 때
    나오는 말이 "First input link ... parameters do not match" 라 원인을 짐작하기
    어렵다. 어차피 캔버스에 맞춰야 하므로 입력마다 한 번씩 맞춰 두고 시작한다.

    같은 자리에서 **색 범위도 고친다.** JPEG 은 full range(yuvj420p)로 들어오는데
    그대로 h264 로 나가면 스트림이 yuvj420p 로 태깅되고, `-pix_fmt yuv420p` 를 줘도
    같은 서브샘플링이라 ffmpeg 이 바꾸지 않는다. 폰과 메타가 기대하는 건 tv range 다.
    """
    w, h = size
    fit = (f"scale={w}:{h}:force_original_aspect_ratio=decrease:"
           f"in_range=full:out_range=tv,"
           f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
           f"setsar=1,format=yuv420p")
    parts = [f"[{k}:v]{fit}[s{k}]" for k in range(n)]
    prev = "[s0]"
    for k in range(1, n):
        out = f"[v{k}]"
        # k 번째 넘김이 시작되는 시각. 앞선 k 장이 각각 hold 만큼 '읽히고' 난 자리다
        # (겹치는 fade 는 앞 장의 hold 에 이어 붙으므로 여기 더하지 않는다).
        parts.append(f"{prev}[s{k}]xfade=transition=fade:duration={fade}:"
                     f"offset={k * hold:.3f}{out}")
        prev = out
    parts.append(f"{prev}format=yuv420p[vout]")
    return ";".join(parts)


#: 릴스 캔버스. 9:16 이 아니면 인스타가 위아래를 잘라 글자가 날아간다.
REEL_SIZE = (1080, 1920)


#: 음원 목표 라우드니스(LUFS). 소셜 영상의 통용값.
AUDIO_LUFS = -16
#: 음원 페이드 — 시작 0.8초, 끝 1.5초
AUDIO_FADE_IN, AUDIO_FADE_OUT = 0.8, 1.5


def _audio_chain(idx: int, seconds: float) -> str:
    """음원 한 줄. 길이를 맞추고 크기를 고르고 양끝을 페이드한다."""
    out_at = max(0.0, seconds - AUDIO_FADE_OUT)
    return (f"[{idx}:a]atrim=0:{seconds:.3f},asetpts=N/SR/TB,"
            f"afade=t=in:st=0:d={AUDIO_FADE_IN},"
            f"afade=t=out:st={out_at:.3f}:d={AUDIO_FADE_OUT},"
            f"loudnorm=I={AUDIO_LUFS}:TP=-1.5:LRA=11,"
            f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[aout]")


def build(slides: list[Path], dest: Path, *, hold: float = HOLD, fade: float = FADE,
          fps: int = FPS, size: tuple[int, int] = REEL_SIZE, audio: Path | None = None,
          quiet: bool = True) -> Path:
    """장면들을 이어 붙여 mp4 를 만든다. 완성본 경로를 돌려준다.

    audio 를 주면 그 음원을 깐다(길이 맞춤 · 크기 고름 · 양끝 페이드).
    안 주면 무음 트랙을 깐다 — 권리 확인은 부르는 쪽 몫이다.
    """
    if not slides:
        raise ValueError("장면이 없습니다")
    missing = [p for p in slides if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"없는 장면: {', '.join(p.name for p in missing)}")

    seconds = duration_for(len(slides), hold=hold, fade=fade)
    if seconds < MIN_SECONDS:
        raise ValueError(
            f"{len(slides)}장이면 {seconds:.1f}초라 릴스 하한({MIN_SECONDS}초)에 못 미칩니다. "
            f"판을 더 넣거나 hold 를 늘리세요")
    if seconds > MAX_SECONDS:
        raise ValueError(f"{seconds:.1f}초는 너무 깁니다(상한 {MAX_SECONDS}초)")

    exe = ffmpeg_exe()
    dest.parent.mkdir(parents=True, exist_ok=True)
    clip = hold + fade
    cmd = [exe, "-y", "-loglevel", "error" if quiet else "info"]
    for p in slides:
        # -loop 1 + -t 로 정지 이미지를 그 길이만큼의 영상으로 만든다.
        cmd += ["-loop", "1", "-t", f"{clip:.3f}", "-i", str(p)]
    # 소리는 **맨 뒤**에 붙인다. 앞에 두면 위의 [k:v] 번호가 통째로 밀린다.
    if audio is not None:
        if not audio.is_file():
            raise FileNotFoundError(f"음원 파일이 없습니다: {audio}")
        # -stream_loop -1: 곡이 영상보다 짧으면 반복한다. 자르는 것은 atrim 이 한다.
        cmd += ["-stream_loop", "-1", "-i", str(audio)]
    else:
        cmd += ["-f", "lavfi", "-t", f"{seconds:.3f}",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    chain = _filter_chain(len(slides), hold, fade, size)
    audio_map = f"{len(slides)}:a"
    if audio is not None:
        chain += ";" + _audio_chain(len(slides), seconds)
        audio_map = "[aout]"
    cmd += [
        "-filter_complex", chain,
        "-map", "[vout]",
        "-map", audio_map,
        "-r", str(fps),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
        # 태깅까지 명시한다. 빠지면 플레이어마다 범위를 다르게 읽어 색이 뜬다.
        "-color_range", "tv", "-colorspace", "bt709",
        "-color_primaries", "bt709", "-color_trc", "bt709",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",
        "-t", f"{seconds:.3f}",
        str(dest),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not dest.is_file():
        tail = (r.stderr or "").strip().splitlines()[-6:]
        raise RuntimeError("ffmpeg 실패:\n  " + "\n  ".join(tail))
    return dest


def set_audio(source: Path, audio: Path | None, dest: Path) -> Path:
    """이미 만든 영상의 **소리만** 바꾼다. 영상은 다시 인코딩하지 않는다(`-c:v copy`).

    판을 여덟 장 다시 찍는 데 몇 분이 걸린다. 음악만 바꿔 보려고 그걸 다시 돌릴
    이유가 없고, 다시 인코딩하면 화질도 한 번 더 깎인다. 소리만 갈아 끼운다.

    audio 가 None 이면 무음 트랙으로 되돌린다.
    """
    info = probe(source)
    seconds = info.get("seconds") or 0.0
    if not seconds:
        raise RuntimeError(f"영상 길이를 못 읽었습니다: {source}")
    exe = ffmpeg_exe()
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-y", "-loglevel", "error", "-i", str(source)]
    if audio is not None:
        if not audio.is_file():
            raise FileNotFoundError(f"음원 파일이 없습니다: {audio}")
        cmd += ["-stream_loop", "-1", "-i", str(audio),
                "-filter_complex", _audio_chain(1, seconds)]
        amap = "[aout]"
    else:
        cmd += ["-f", "lavfi", "-t", f"{seconds:.3f}",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
        amap = "1:a"
    cmd += ["-map", "0:v", "-c:v", "copy", "-map", amap,
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-movflags", "+faststart", "-t", f"{seconds:.3f}", str(dest)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not dest.is_file():
        tail = (r.stderr or "").strip().splitlines()[-6:]
        raise RuntimeError("ffmpeg 실패:\n  " + "\n  ".join(tail))
    return dest


def probe(path: Path) -> dict:
    """만든 영상의 코덱·길이·크기. 못 읽으면 빈 dict.

    ffprobe 가 있으면 그걸 쓰고, **없으면 ffmpeg 이 stderr 에 찍는 것을 읽는다.**
    imageio-ffmpeg 으로 설치하면 ffprobe 가 딸려 오지 않는데, 그때 조용히 확인을
    건너뛰면 검사가 있으나 마나다 — 메타는 조건이 틀리면 "처리 실패" 만 돌려주고
    무엇이 틀렸는지 말해 주지 않으므로, 올리기 전에 여기서 걸러야 한다.
    """
    ffmpeg = ffmpeg_exe()
    if (exe := _ffprobe_exe(ffmpeg)):
        r = subprocess.run([exe, "-v", "error", "-print_format", "json",
                            "-show_format", "-show_streams", str(path)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            data = json.loads(r.stdout or "{}")
            v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
            a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
            return {
                "seconds": round(float((data.get("format") or {}).get("duration") or 0), 2),
                "width": v.get("width"), "height": v.get("height"),
                "video_codec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"),
                "audio_codec": a.get("codec_name") or "",
                "mb": round(int((data.get("format") or {}).get("size") or 0) / 1_048_576, 2),
            }
    return _probe_via_ffmpeg(ffmpeg, path)


_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")
_VIDEO_RE = re.compile(r"Stream #\d+:\d+.*?: Video: (\w+).*?, (\w+)\(?.*?, (\d+)x(\d+)")
_AUDIO_RE = re.compile(r"Stream #\d+:\d+.*?: Audio: (\w+)")


def _probe_via_ffmpeg(ffmpeg: str, path: Path) -> dict:
    """ffprobe 가 없을 때. `ffmpeg -i <파일>` 은 정보를 찍고 에러로 끝난다(정상)."""
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True)
    text = r.stderr or ""
    out: dict = {"seconds": 0.0, "width": None, "height": None,
                 "video_codec": "", "pix_fmt": "", "audio_codec": "",
                 "mb": round(path.stat().st_size / 1_048_576, 2) if path.is_file() else 0}
    if (m := _DUR_RE.search(text)):
        out["seconds"] = round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 2)
    if (m := _VIDEO_RE.search(text)):
        out["video_codec"], out["pix_fmt"] = m.group(1), m.group(2)
        out["width"], out["height"] = int(m.group(3)), int(m.group(4))
    if (m := _AUDIO_RE.search(text)):
        out["audio_codec"] = m.group(1)
    return out if out["video_codec"] else {}


def check(path: Path) -> list[str]:
    """릴스로 못 올릴 이유들. 빈 리스트면 통과."""
    info = probe(path)
    if not info:
        return []                      # ffprobe 가 없으면 확인을 건너뛴다(막지는 않는다)
    bad = []
    if not (MIN_SECONDS <= info["seconds"] <= 900):
        bad.append(f"길이 {info['seconds']}초 (3초~15분)")
    if info["video_codec"] != "h264":
        bad.append(f"영상 코덱 {info['video_codec']} (h264 여야 한다)")
    if info["pix_fmt"] != "yuv420p":
        bad.append(f"픽셀 형식 {info['pix_fmt']} (yuv420p 여야 한다)")
    if not info["audio_codec"]:
        bad.append("오디오 트랙 없음 (무음이라도 있어야 한다)")
    if info["mb"] > 1000:
        bad.append(f"{info['mb']}MB (1GB 상한)")
    return bad


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="판 여러 장 → 릴스용 mp4")
    ap.add_argument("slides", nargs="*", help="장면 이미지들(순서대로)")
    ap.add_argument("--from-video", default="",
                    help="이미 만든 mp4 의 소리만 바꾼다(영상은 다시 인코딩하지 않는다)")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--hold", type=float, default=HOLD)
    ap.add_argument("--fade", type=float, default=FADE)
    ap.add_argument("--audio", default="", help="깔 음원 파일. 권리는 부르는 쪽이 확인한다")
    args = ap.parse_args()
    track = Path(args.audio) if args.audio else None
    if args.from_video:
        out = set_audio(Path(args.from_video), track, Path(args.out))
    elif args.slides:
        out = build([Path(p) for p in args.slides], Path(args.out),
                    hold=args.hold, fade=args.fade, audio=track, quiet=False)
    else:
        ap.error("장면 이미지들 또는 --from-video 중 하나는 있어야 합니다")
    info = probe(out)
    print(f"[video] {out}  {info.get('seconds', '?')}초 "
          f"{info.get('width')}×{info.get('height')} {info.get('mb', '?')}MB")
    for why in check(out):
        print(f"  ! {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
