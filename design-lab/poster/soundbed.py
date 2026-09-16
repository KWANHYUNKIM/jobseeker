"""릴스에 깔 배경음을 **직접 만든다**.

## 왜 만드나 — 받아 오지 않고

인스타그램 음원 라이브러리는 API 로 못 쓴다. 그러면 남은 길은 우리가 권리를 가진
음원을 영상에 구워 넣는 것뿐인데, 받아 온 곡은 그 "권리를 가졌나" 를 확인할 길이
마땅치 않다. '무료' 라고 적힌 곡도 라이선스가 CC0 부터 CC-BY-NC 까지 제각각이고,
표기 조건을 놓치면 허락이 아닌 게 된다. 게다가 인스타의 음원 지문 검사에 걸리면
소리만 조용히 사라지거나 계정에 경고가 붙는다.

**만들면 그 질문이 통째로 없어진다.** 우리가 쓴 것이니 표기도, 기간도, 용도 제한도
없다. 지문 검사에 걸릴 곡이 세상에 없다.

## 무엇을 만드나

공고 목록이 넘어가는 18초짜리 영상의 **배경**이다. 노래가 아니라 바닥이다 —
귀를 끌면 판의 글자를 안 읽는다. 그래서 셋만 쓴다.

  패드   한 마디를 통째로 채우는 화음. 천천히 열리고 천천히 닫힌다.
  아르페지오  8분음표로 화음을 훑는다. 넘어가는 장면에 박자를 준다.
  킥     아주 낮은 둥, 마디의 1·3박에만. 없으면 흘러가 버리고, 세면 광고가 된다.

화성은 Am–F–C–G 네 마디. 흔해서 고른 것이다 — 배경음이 새로우면 그것부터 듣는다.
한 바퀴가 10초라 그대로 이어 붙여도 이음매가 안 들린다(릴스는 18.4초다).

## 소리 크기는 여기서 맞추지 않는다

`poster.video` 가 영상에 깔면서 `loudnorm` 으로 -16 LUFS 에 맞춘다. 여기서 또
맞추면 두 번 눌려 납작해지므로, 여기서는 클리핑만 피하고 넘긴다.

    python -m poster.soundbed -o bed.wav              # 10초 한 바퀴
    python -m poster.soundbed -o bed.wav --seconds 20 # 이어 붙여 20초
"""
from __future__ import annotations

import argparse
import math
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 96
BEAT = 60.0 / BPM            # 0.625초
BAR = BEAT * 4               # 2.5초

# Am – F – C – G. 낮은 음이 널뛰지 않게 자리바꿈으로 붙여 뒀다(전위).
# 숫자는 MIDI 음높이. 57 = A3.
PROGRESSION: list[tuple[int, ...]] = [
    (45, 57, 60, 64),        # Am : A2 A3 C4 E4
    (41, 57, 60, 65),        # F  : F2 A3 C4 F4
    (48, 55, 60, 64),        # C  : C3 G3 C4 E4
    (43, 55, 59, 62),        # G  : G2 G3 B3 D4
]


def hz(midi: int) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _adsr(n: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    """샘플 n 개짜리 음량 곡선. 길이가 짧으면 구간을 비율대로 줄인다."""
    a, d, r = (max(1, int(SR * x)) for x in (attack, decay, release))
    if a + d + r > n:                       # 짧은 음에서는 통째로 줄인다
        scale = n / (a + d + r)
        a, d, r = (max(1, int(x * scale)) for x in (a, d, r))
    s = max(0, n - a - d - r)
    return np.concatenate([
        np.linspace(0, 1, a, endpoint=False),
        np.linspace(1, sustain, d, endpoint=False),
        np.full(s, sustain),
        np.linspace(sustain, 0, n - a - d - s),
    ])


def _tone(freq: float, n: int, partials: tuple[tuple[int, float], ...]) -> np.ndarray:
    """배음을 쌓은 한 음. partials 는 (몇 배음, 얼마나 크게).

    사인 하나만 쓰면 전화 신호음처럼 들린다. 배음을 조금 얹으면 악기 비슷해진다.
    """
    t = np.arange(n) / SR
    out = np.zeros(n)
    for mult, amp in partials:
        out += amp * np.sin(2 * math.pi * freq * mult * t)
    return out


def _pad(bars: int) -> np.ndarray:
    """마디마다 화음 하나. 천천히 열리고 천천히 닫힌다."""
    n_bar = int(SR * BAR)
    out = np.zeros(n_bar * bars)
    for i in range(bars):
        chord = PROGRESSION[i % len(PROGRESSION)]
        env = _adsr(n_bar, attack=0.45, decay=0.30, sustain=0.75, release=0.60)
        block = np.zeros(n_bar)
        for midi in chord:
            block += _tone(hz(midi), n_bar, ((1, 1.0), (2, 0.22), (3, 0.08)))
        out[i * n_bar:(i + 1) * n_bar] = block / len(chord) * env
    return out


def _arp(bars: int) -> np.ndarray:
    """8분음표로 화음을 훑는다. 장면이 넘어가는 박자를 여기서 준다."""
    n_bar = int(SR * BAR)
    n_note = int(SR * BEAT / 2)
    out = np.zeros(n_bar * bars)
    for i in range(bars):
        chord = PROGRESSION[i % len(PROGRESSION)][1:]      # 베이스는 빼고 위 세 음
        for j in range(8):
            # 올라갔다 내려온다. 한 방향으로만 가면 계단처럼 단조롭다.
            order = list(chord) + list(chord[::-1])[1:]
            midi = order[j % len(order)] + (12 if j >= 4 else 0)
            start = i * n_bar + j * n_note
            env = _adsr(n_note, attack=0.004, decay=0.10, sustain=0.18, release=0.12)
            out[start:start + n_note] += _tone(hz(midi), n_note, ((1, 1.0), (2, 0.15))) * env
    return out


def _kick(bars: int) -> np.ndarray:
    """1·3박의 낮은 둥. 음높이가 떨어지면서 사라진다(그게 킥처럼 들리는 이유다)."""
    n_bar = int(SR * BAR)
    n_hit = int(SR * 0.22)
    t = np.arange(n_hit) / SR
    # 90Hz 에서 42Hz 로 빠르게 떨어진다
    freq = 42 + 48 * np.exp(-t * 28)
    hit = np.sin(2 * math.pi * np.cumsum(freq) / SR) * np.exp(-t * 11)
    out = np.zeros(n_bar * bars)
    for i in range(bars):
        for beat in (0, 2):
            start = i * n_bar + int(SR * BEAT * beat)
            out[start:start + n_hit] += hit
    return out


def render(seconds: float = 0.0, *, bars: int = 4) -> np.ndarray:
    """(샘플, 2) 스테레오 배열. seconds 를 주면 그 길이까지 이어 붙이고 자른다."""
    pad, arp, kick = _pad(bars), _arp(bars), _kick(bars)
    n = min(len(pad), len(arp), len(kick))
    # 배경이므로 패드가 바닥, 아르페지오는 그 위에 얇게, 킥은 존재만 알린다.
    mono = pad[:n] * 0.55 + arp[:n] * 0.22 + kick[:n] * 0.30

    # 아르페지오만 좌우로 조금 벌린다. 전부 벌리면 폰 스피커(모노)에서 음이 상쇄된다.
    left = mono + arp[:n] * 0.06
    right = mono - arp[:n] * 0.06
    stereo = np.stack([left, right], axis=1)

    if seconds:
        want = int(SR * seconds)
        reps = int(np.ceil(want / len(stereo)))
        stereo = np.tile(stereo, (reps, 1))[:want]

    # 클리핑만 피한다. 최종 크기는 poster.video 의 loudnorm 이 맞춘다 —
    # 여기서 또 맞추면 두 번 눌려 납작해진다.
    peak = np.max(np.abs(stereo))
    if peak > 0:
        stereo = stereo / peak * 0.89
    return stereo


def write_wav(path: Path, samples: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


def build(path: Path, seconds: float = 0.0, *, bars: int = 4) -> Path:
    return write_wav(path, render(seconds, bars=bars))


def main() -> int:
    ap = argparse.ArgumentParser(description="릴스 배경음을 만든다(권리: 우리 것)")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--seconds", type=float, default=0.0, help="이 길이까지 이어 붙인다")
    ap.add_argument("--bars", type=int, default=4, help="한 바퀴 마디 수(기본 4 = 10초)")
    args = ap.parse_args()
    out = build(Path(args.out), args.seconds, bars=args.bars)
    n = out.stat().st_size
    print(f"[soundbed] {out}  {args.seconds or args.bars * BAR:.1f}초  {n / 1048576:.2f}MB  "
          f"{BPM}BPM Am-F-C-G")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
