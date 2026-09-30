"""릴스용 배경음 — 비트감 있는 곡을 **직접 합성한다**(권리: 우리 것).

`soundbed.py` 는 96BPM 잔잔한 바닥 하나였다. 새 릴스(`reelfx.py`)는 장면이 박자에 맞춰 튀어나오므로
곡에 박이 서야 한다. 그리고 릴스 10편이 같은 곡이면 피드에서 한 편처럼 들린다 — 그래서
**곡마다 템포·조·진행·드럼 결을 바꾼다**(STYLES). 받아 온 곡을 쓰지 않는 이유는 soundbed.py 머리말과 같다
(라이선스 확인·음원 지문 검사).

구성: 킥(4박) · 클랩(2·4박) · 하이햇(8분/16분) · 베이스(근음) · 플럭 리드(짧은 동기 반복) · 패드.
킥이 칠 때 베이스·패드를 잠깐 눌러(사이드체인 흉내) 박이 또렷하게 들리게 한다.
최종 크기는 `poster.video` 의 loudnorm(-16 LUFS)이 맞춘다 — 여기서는 클리핑만 피한다.

    python -m poster.beats -o out.wav --style bright --seconds 20
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from .soundbed import SR, hz, write_wav

#: 이름 → (BPM, 근음 MIDI, 진행(도수), 장/단, 하이햇 분할, 스윙, 리드 동기)
STYLES = {
    "bright": (118, 60, (1, 5, 6, 4), "major", 16, 0.0, (0, 4, 7, 9, 7, 4)),
    "drive": (124, 57, (1, 6, 3, 7), "minor", 16, 0.0, (0, 3, 7, 10, 7, 3)),
    "bounce": (110, 62, (1, 4, 6, 5), "major", 8, 0.18, (7, 4, 2, 0, 2, 4)),
    "focus": (114, 55, (6, 4, 1, 5), "major", 16, 0.08, (0, 2, 4, 7, 4, 2)),
    "night": (120, 52, (1, 7, 6, 7), "minor", 16, 0.0, (0, 7, 3, 5, 3, 7)),
}
_SCALE = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10)}


def beat_seconds(style: str) -> float:
    return 60.0 / STYLES[style][0]


def _chord(root: int, degree: int, mode: str) -> list[int]:
    sc = _SCALE[mode]
    i = degree - 1
    return [root + sc[(i + k) % 7] + 12 * ((i + k) // 7) for k in (0, 2, 4)]


def _env(n: int, a: float, d: float) -> np.ndarray:
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(a, 1e-4)) * np.exp(-t / max(d, 1e-4))


def _saw(freq: float, n: int, bright: float = 0.5) -> np.ndarray:
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k in range(1, 7):
        out += (bright ** (k - 1)) * np.sin(2 * math.pi * freq * k * t) / k
    return out


def render(style: str = "bright", seconds: float = 20.0) -> np.ndarray:
    bpm, root, prog, mode, hat_div, swing, motif = STYLES[style]
    beat = 60.0 / bpm
    bar = beat * 4
    n_total = int(SR * seconds)
    bars = int(math.ceil(seconds / bar)) + 1
    n = int(SR * bar * bars)
    kick, clap, hat, bass, lead, pad = (np.zeros(n) for _ in range(6))
    duck = np.ones(n)
    rng = np.random.default_rng(abs(hash(style)) % 2**32)

    # 킥 — 4박, 음높이가 빠르게 떨어진다
    hn = int(SR * 0.25)
    t = np.arange(hn) / SR
    k_hit = np.sin(2 * math.pi * np.cumsum(50 + 110 * np.exp(-t * 35)) / SR) * np.exp(-t * 9)
    # 클랩 — 잡음 폭발 두세 번
    cn = int(SR * 0.18)
    noise = rng.standard_normal(cn)
    c_env = np.exp(-np.arange(cn) / SR * 30)
    c_hit = noise * c_env
    c_hit[:int(SR * 0.012)] *= 1.6
    # 하이햇 — 짧은 고역 잡음(1차 차분으로 저역을 깎는다)
    hh = int(SR * 0.045)
    h_hit = np.diff(rng.standard_normal(hh + 1)) * np.exp(-np.arange(hh) / SR * 90)

    for b in range(bars):
        s0 = int(SR * b * bar)
        chord = _chord(root, prog[b % len(prog)], mode)
        for q in range(4):
            s = s0 + int(SR * q * beat)
            kick[s:s + hn] += k_hit[:max(0, min(hn, n - s))]
            d = np.ones(int(SR * beat * .6))
            d[:len(d)] = 0.35 + 0.65 * np.linspace(0, 1, len(d)) ** 1.5
            duck[s:s + len(d)] = np.minimum(duck[s:s + len(d)], d[:max(0, min(len(d), n - s))])
            if q in (1, 3):
                clap[s:s + cn] += c_hit[:max(0, min(cn, n - s))]
        step = beat * 4 / hat_div
        for h in range(hat_div):
            off = step * h + (step * swing if h % 2 else 0)
            s = s0 + int(SR * off)
            amp = 0.6 if h % 2 else 1.0
            hat[s:s + hh] += amp * h_hit[:max(0, min(hh, n - s))]
        # 베이스 — 8분음표로 근음(마디 끝에서 5도로 한 번 튄다)
        for e in range(8):
            s = s0 + int(SR * e * beat / 2)
            ln = int(SR * beat / 2 * .9)
            note = chord[0] - 24 + (7 if e == 7 else 0)
            bass[s:s + ln] += (_saw(hz(note), ln, .35) * _env(ln, .005, .25))[:max(0, min(ln, n - s))]
        # 패드 — 마디 통째로
        ln = int(SR * bar)
        blk = sum(_saw(hz(m), ln, .25) for m in chord) / 3
        pad[s0:s0 + ln] += (blk * np.minimum(1, np.arange(ln) / (SR * .2)))[:max(0, min(ln, n - s0))]
        # 리드 — 동기를 16분 음표 자리에 흩어 놓는다(마디마다 같은 리듬, 화음 따라 높이만 바뀜)
        for i, pos in enumerate((0, 3, 6, 8, 11, 14)):
            s = s0 + int(SR * pos * beat / 4)
            ln = int(SR * beat / 4 * 1.6)
            note = root + 12 + motif[i % len(motif)] + (chord[0] - root) % 12 * 0
            lead[s:s + ln] += (_saw(hz(note), ln, .55) * _env(ln, .003, .12))[:max(0, min(ln, n - s))]

    mix = (kick * .95 + clap * .35 + hat * .16 + bass * .42 * duck + pad * .20 * duck + lead * .24)
    left = mix + lead * .05 + hat * .04
    right = mix - lead * .05 - hat * .04
    st = np.stack([left, right], axis=1)[:n_total]
    fade = int(SR * .6)
    st[-fade:] *= np.linspace(1, 0, fade)[:, None]
    st[:int(SR * .02)] *= np.linspace(0, 1, int(SR * .02))[:, None]
    peak = np.max(np.abs(st))
    return st / peak * 0.89 if peak else st


def build(path: Path, style: str = "bright", seconds: float = 20.0) -> Path:
    return write_wav(path, render(style, seconds))


def main() -> int:
    ap = argparse.ArgumentParser(description="릴스 배경음(비트)을 만든다 — 권리: 우리 것")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--style", default="bright", choices=list(STYLES))
    ap.add_argument("--seconds", type=float, default=20.0)
    a = ap.parse_args()
    p = build(Path(a.out), a.style, a.seconds)
    print(f"[beats] {p} {a.style} {STYLES[a.style][0]}BPM {a.seconds}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
