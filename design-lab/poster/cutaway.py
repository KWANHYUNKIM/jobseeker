"""3D 해부도 릴스 조립 — AI 로 만든 장면 클립에 자막·출처·배경음을 얹어 한 편으로 잇는다.

archcutaway(건축해부도)처럼 **영상이 주인공**이고 글은 자막이다. 장면 영상은 우리가 만들지 않는다 —
`storyboard.json` 의 프롬프트로 사람이 생성 도구(정지 그림: Nano Banana / 움직임: Kling · Veo)에서 뽑아
`clips/` 에 넣는다. 한글은 생성 도구가 자주 틀리므로 **클립에는 글자를 넣지 않고** 여기서 얹는다.

장면마다 찾는 순서: clips/<id>.mp4 → clips/<id>.png|jpg(천천히 당겨 들어가는 움직임으로) → 자리표시 화면.
그래서 클립이 몇 개만 와도 전체 흐름을 미리 볼 수 있다.

    python -m poster.cutaway reels/oliveyoung_3d
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import beats, video

W, H, FPS = 1080, 1920, 30


def _font(size: int) -> ImageFont.FreeTypeFont:
    for f in ("C:/Windows/Fonts/malgunbd.ttf", "/System/Library/Fonts/AppleSDGothicNeo.ttc"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _rich_lines(text: str, font, width: int) -> list[list[tuple[str, bool]]]:
    """**강조** 를 살리면서 폭에 맞춰 줄을 나눈다(한글은 글자 단위로 끊는다)."""
    runs = [(p[2:-2], True) if p.startswith("**") else (p, False) for p in re.split(r"(\*\*[^*]+\*\*)", text) if p]
    lines, cur, cur_w = [], [], 0
    for txt, hi in runs:
        for ch in txt:
            w = font.getlength(ch)
            if cur_w + w > width and ch != " ":
                lines.append(cur)
                cur, cur_w = [], 0
            if cur and cur[-1][1] == hi:
                cur[-1] = (cur[-1][0] + ch, hi)
            else:
                cur.append((ch, hi))
            cur_w += w
    if cur:
        lines.append(cur)
    return lines


def overlay(sb: dict, shot: dict, idx: int, total: int, dest: Path) -> Path:
    """자막·머리·출처를 그린 투명 PNG(1080×1920)."""
    th = sb["theme"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    band = _hex(th["band"])
    # 위: 시리즈 · 진행 막대 · AI 표시
    d.rectangle([0, 0, W, 190], fill=band + (215,))
    d.text((64, 70), sb["series"], font=_font(40), fill=_hex(th["ink"]))
    d.text((W - 64, 78), "@devjobseeker", font=_font(30), fill=_hex(th["sub"]), anchor="ra")
    seg = (W - 128) / total
    for k in range(total):
        d.rectangle([64 + k * seg + 3, 146, 64 + (k + 1) * seg - 3, 154],
                    fill=_hex(th["accent"] if k <= idx else th["sub"]) + (255 if k <= idx else 90,))
    # 아래: 자막
    f = _font(58)
    lines = _rich_lines(shot["sub"], f, W - 160)
    lh = 80
    box_h = lh * len(lines) + 80 + (46 if shot.get("source") else 0) + 40
    y0 = H - 260 - box_h
    d.rounded_rectangle([48, y0, W - 48, H - 260], radius=34, fill=band + (225,))
    y = y0 + 44
    for ln in lines:
        x = 80
        for txt, hi in ln:
            d.text((x, y), txt, font=f, fill=_hex(th["accent"] if hi else th["ink"]))
            x += f.getlength(txt)
        y += lh
    if shot.get("source"):
        # 화면에는 짧게 — 괄호 속 파일 경로는 대본(storyboard.json)에만 남긴다
        src = shot["source"].split(" — ")[-1].split(" (")[0]
        d.text((80, y + 14), ("출처: " + src)[:40], font=_font(26), fill=_hex(th["sub"]))
    d.text((64, H - 200), sb.get("label", ""), font=_font(28), fill=_hex(th["sub"]))
    img.save(dest)
    return dest


def end_card(sb: dict, dest: Path) -> Path:
    th, e = sb["theme"], sb["end"]
    img = Image.new("RGB", (W, H), _hex(th["band"]))
    d = ImageDraw.Draw(img)
    size = 140                                   # 폭에 맞춰 줄인다
    while size > 70 and max(_font(size).getlength(e["title"]), _font(size).getlength(e["title2"])) > W - 160:
        size -= 6
    d.text((80, 700), e["title"], font=_font(size), fill=_hex(th["ink"]))
    d.text((80, 700 + int(size * 1.2)), e["title2"], font=_font(size), fill=_hex(th["accent"]))
    y = 700 + int(size * 2.6)
    for ln in _rich_lines(e["sub"], _font(44), W - 160):          # 긴 안내는 줄을 나눈다
        d.text((80, y), "".join(t for t, _ in ln), font=_font(44), fill=_hex(th["sub"]))
        y += 62
    d.text((80, y + 40), "@devjobseeker", font=_font(64), fill=_hex(th["ink"]))
    img.save(dest)
    return dest


def _placeholder(shot: dict, dest: Path) -> Path:
    img = Image.new("RGB", (W, H), (38, 44, 40))
    d = ImageDraw.Draw(img)
    d.text((80, 500), f"[{shot['id']}] 클립 자리", font=_font(60), fill=(200, 210, 200))
    y = 620
    for ln in _rich_lines(shot["image"], _font(34), W - 160)[:14]:
        d.text((80, y), "".join(t for t, _ in ln), font=_font(34), fill=(150, 160, 150))
        y += 50
    img.save(dest)
    return dest


# ── 목소리 · 고객 화면(PIP) ───────────────────────────────
def tts(text: str, dest: Path, voice: str) -> float:
    """내레이션 한 줄 → mp3. 길이(초)를 돌려준다. 같은 문장으로 만든 게 있으면 다시 안 만든다.
    edge-tts(마이크로소프트 온라인 신경망 음성) — 공개 게시용 권리는 CONTENT_PLAN.md 참고."""
    stamp = dest.with_suffix(".txt")
    if not (dest.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == voice + "|" + text):
        subprocess.run([sys.executable, "-m", "edge_tts", "--voice", voice, "--rate", "+6%", "--text", text,
                        "--write-media", str(dest)], check=True, capture_output=True)
        stamp.write_text(voice + "|" + text, encoding="utf-8")
    out = subprocess.run([video.ffmpeg_exe(), "-i", str(dest)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 3.0


PIP = {  # 고객 화면 — 시스템이 바뀌는 동안 고객은 무엇을 보나
    "late": ("선착순 추가 증정", "#FF7878", "실제로는 이미 마감", "반영 대기 최대 45분", "#FF7878"),
    "fast": ("증정 마감", "#b7bcb4", "행사가 끝나자", "수 초 안에 반영", "#4c9a12"),
    "verify": ("증정 마감", "#b7bcb4", "옛 결과와 나란히", "3주 병행 검증 중", "#c79a10"),
    "done": ("증정 마감", "#b7bcb4", "화면 = 실제", "45분 → 수 초", "#4c9a12"),
}


def pip(state: str, dest: Path) -> Path:
    flag, fcol, line1, line2, lcol = PIP[state]
    w, h = 300, 560
    img = Image.new("RGBA", (w + 24, h + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 10, w + 16, h + 18], radius=40, fill=(0, 0, 0, 80))
    d.rounded_rectangle([0, 0, w, h], radius=40, fill=(34, 40, 36, 255))
    d.rounded_rectangle([12, 12, w - 12, h - 12], radius=30, fill=(255, 255, 255, 255))
    d.text((30, 30), "고객 화면", font=_font(24), fill=(90, 100, 90))
    d.rounded_rectangle([30, 70, w - 30, 260], radius=20, fill=_hex("#eaf6dc"))
    d.rounded_rectangle([w / 2 - 28, 100, w / 2 + 28, 230], radius=16, fill=(255, 255, 255))
    d.rectangle([w / 2 - 28, 100, w / 2 + 28, 128], fill=_hex("#82DC28"))
    d.text((30, 278), "수분 크림 50ml", font=_font(26), fill=_hex("#16241a"))
    d.text((30, 314), "24,000원", font=_font(32), fill=_hex("#16241a"))
    fw = _font(24).getlength(flag) + 32
    d.rounded_rectangle([30, 362, 30 + fw, 404], radius=12, fill=_hex(fcol))
    d.text((46, 370), flag, font=_font(24), fill=(255, 255, 255))
    d.text((30, 432), line1, font=_font(24), fill=(90, 100, 90))
    d.text((30, 468), line2, font=_font(30), fill=_hex(lcol))
    img.save(dest)
    return dest


def _render3d(sh: dict, sec: float, clips: Path) -> Path:
    """장면에 3D(scene)가 정해져 있으면 그 길이로 굽는다. 같은 길이로 구운 게 있으면 다시 안 굽는다."""
    from . import scene3d
    dest = clips / f"{sh['id']}.mp4"
    stamp = clips / f"{sh['id']}.len"
    key = f"{sh['scene']}|{sec:.2f}|v3"
    if dest.exists() and stamp.exists() and stamp.read_text() == key:
        return dest
    scene3d.render(f"{sh['scene']}&d={sec:.2f}", sec, dest)      # 3D 가 장면 길이를 알아야 애니메이션을 끝까지 늘린다
    stamp.write_text(key)
    return dest


def build(folder: Path) -> Path:
    sb = json.loads((folder / "storyboard.json").read_text(encoding="utf-8"))
    clips, work = folder / "clips", folder / "_work"
    clips.mkdir(exist_ok=True)
    work.mkdir(exist_ok=True)
    ff = video.ffmpeg_exe()
    voice = sb.get("voice", "ko-KR-SunHiNeural")
    shots = sb["shots"]
    # 1) 목소리 먼저 — 장면 길이 = 목소리 길이 + 0.9초(최소 4초)
    for sh in shots + [sb["end"]]:
        if sh.get("voice"):
            sh["_vo"] = work / f"{sh.get('id', 'end')}_vo.mp3"
            sh["_vo_len"] = tts(sh["voice"], sh["_vo"], voice)
            sh["sec"] = round(max(4.0, sh["_vo_len"] + 0.9), 2)
    parts = []
    for i, sh in enumerate(shots):
        if sh.get("scene"):
            _render3d(sh, sh["sec"], clips)
        ov = overlay(sb, sh, i, len(shots), work / f"{sh['id']}_ov.png")
        pp = pip(sh["pip"], work / f"{sh['id']}_pip.png") if sh.get("pip") else None
        out = work / f"{sh['id']}.mp4"
        src = next((clips / f"{sh['id']}{e}" for e in (".mp4", ".mov", ".webm") if (clips / f"{sh['id']}{e}").exists()), None)
        cover = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1"
        if src:
            inp = ["-stream_loop", "-1", "-i", str(src)]
            base = f"[0:v]{cover}[b]"
        else:
            still = next((clips / f"{sh['id']}{e}" for e in (".png", ".jpg", ".jpeg", ".webp") if (clips / f"{sh['id']}{e}").exists()), None)
            still = still or _placeholder(sh, work / f"{sh['id']}_ph.png")
            frames = int(sh["sec"] * FPS)
            inp = ["-loop", "1", "-i", str(still)]
            base = (f"[0:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
                    f"zoompan=z='min(1.0+0.0009*on,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},setsar=1[b]")
        ins = inp + ["-i", str(ov)]
        vf = base + ";[b][1:v]overlay=0:0[o]"
        if pp:
            # 고객 화면 — 같은 자리(오른쪽)에 계속 있어서 장면이 바뀌어도 이어 보인다
            ins += ["-loop", "1", "-i", str(pp)]
            vf += f";[2:v]scale=iw*0.78:-1[pp];[o][pp]overlay=x={W - 290}:y=820:shortest=1[o2];[o2]format=yuv420p[v]"
        else:
            vf += ";[o]format=yuv420p[v]"
        subprocess.run([ff, "-y", "-loglevel", "error", *ins, "-filter_complex", vf, "-map", "[v]",
                        "-t", str(sh["sec"]), "-r", str(FPS), "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
                        "-an", str(out)], check=True)
        parts.append((out, sh["sec"], sh))
    endp = end_card(sb, work / "end.png")
    endv = work / "end.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-loop", "1", "-i", str(endp), "-t", str(sb["end"]["sec"]),
                    "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-crf", "19", str(endv)], check=True)
    parts.append((endv, sb["end"]["sec"], sb["end"]))

    # 2) 장면 잇기(0.3초 겹침) — 각 장면이 시작하는 시각을 같이 적는다(목소리를 그 자리에 놓는다)
    fade = 0.3
    inputs, chain, offset, prev, starts = [], [], 0.0, "[0:v]", [0.0]
    for p, _, _ in parts:
        inputs += ["-i", str(p)]
    for k in range(1, len(parts)):
        offset += parts[k - 1][1] - fade
        starts.append(offset)
        outl = f"[x{k}]"
        chain.append(f"{prev}[{k}:v]xfade=transition=fade:duration={fade}:offset={offset:.3f}{outl}")
        prev = outl
    total = sum(s for _, s, _ in parts) - fade * (len(parts) - 1)
    music = work / "music.wav"
    beats.build(music, sb.get("music", "bright"), total + 0.5)
    # 3) 소리 — 목소리는 장면 시작 0.25초 뒤, 음악은 목소리 밑으로 낮게
    a_in, a_chain, labels = ["-i", str(music)], [], []
    n_v = len(parts)
    for k, (_, _, sh) in enumerate(parts):
        if sh.get("_vo"):
            idx = n_v + 1 + len(labels)
            a_in += ["-i", str(sh["_vo"])]
            ms = int((starts[k] + 0.25) * 1000)
            a_chain.append(f"[{idx}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms},apad[v{k}]")
            labels.append(f"[v{k}]")
    a_chain.append(f"[{n_v}:a]aresample=44100,aformat=channel_layouts=stereo,volume=0.22[m]")
    a_chain.append("[m]" + "".join(labels) + f"amix=inputs={1 + len(labels)}:duration=first:normalize=0,"
                   f"loudnorm=I={video.AUDIO_LUFS}:TP=-1.5:LRA=11,afade=t=out:st={total - 0.8:.2f}:d=0.8[a]")
    dest = folder / f"{folder.name}.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", *inputs, *a_in,
                    "-filter_complex", ";".join(chain + [f"{prev}scale=in_range=full:out_range=tv,format=yuv420p[v]"] + a_chain),
                    "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
                    "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-color_range", "tv", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dest)], check=True)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(prog="poster.cutaway")
    ap.add_argument("folder")
    a = ap.parse_args()
    p = build(Path(a.folder))
    print(p, video.probe(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
