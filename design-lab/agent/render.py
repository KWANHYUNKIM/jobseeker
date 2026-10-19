"""③ 써 보기 — 코너를 **한 번에 하나씩** 찍는다. 이 PC 메모리에 맞춘 순서다.

2026-10-19 에 DB(도커)·8780·크로미엄을 한꺼번에 띄워 세 코너를 찍다가 PC 가 꺼졌다. 그래서:
  - 코너는 차례로, 하나 끝나면 쉬었다가 다음 것(크로미엄이 메모리를 돌려줄 틈)
  - 시작 전에 남은 메모리를 보고, 모자라면 찰 때까지 기다린다(오래 걸려도 된다 — 꺼지는 것보다 낫다)
  - 찍기는 낮은 우선순위로, cardpress 는 브라우저를 몇 장마다 새로 띄운다(CARDPRESS_RECYCLE)

    python -m agent render                 # 세 코너 전부
    python -m agent render deadline        # 하나만

손잡이(환경변수): DESIGN_MIN_FREE_MB(기본 2500) · DESIGN_WAIT_MAX_S(기본 1800) · DESIGN_PAUSE_S(기본 20)
                  CARDPRESS(실행 파일 경로) · CARDPRESS_RECYCLE(기본 4)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
CORNERS_OUT = LAB_DIR / "out" / "corners"

MIN_FREE_MB = int(os.environ.get("DESIGN_MIN_FREE_MB", "2500"))
WAIT_MAX_S = int(os.environ.get("DESIGN_WAIT_MAX_S", "1800"))
PAUSE_S = int(os.environ.get("DESIGN_PAUSE_S", "20"))


def free_mb() -> int | None:
    """지금 쓸 수 있는 메모리(MB). 못 재면 None — 그때는 기다리지 않는다."""
    try:
        if sys.platform == "win32":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("avail", ctypes.c_ulonglong), ("pt", ctypes.c_ulonglong), ("pa", ctypes.c_ulonglong),
                            ("vt", ctypes.c_ulonglong), ("va", ctypes.c_ulonglong), ("ve", ctypes.c_ulonglong)]
            m = MS(); m.len = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.avail // 2**20
        if sys.platform == "darwin":
            out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
            page = int(out.split("page size of ")[1].split()[0])
            n = {k.strip(): int(v.strip(" .")) for k, v in (l.split(":") for l in out.splitlines()[1:] if ":" in l)}
            return (n.get("Pages free", 0) + n.get("Pages inactive", 0) + n.get("Pages speculative", 0)) * page // 2**20
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except Exception:  # noqa: BLE001
        return None
    return None


def wait_for_memory(need_mb: int = MIN_FREE_MB, max_s: int = WAIT_MAX_S) -> bool:
    """남은 메모리가 need_mb 를 넘을 때까지 30초마다 본다. max_s 가 지나면 False(찍지 않는다)."""
    start = time.monotonic()
    while True:
        free = free_mb()
        if free is None or free >= need_mb:
            return True
        waited = time.monotonic() - start
        if waited >= max_s:
            print(f"[render] 남은 메모리 {free}MB < {need_mb}MB — {max_s // 60}분 기다려도 안 찼다. 이번엔 건너뛴다")
            return False
        print(f"[render] 남은 메모리 {free}MB < {need_mb}MB — 30초 뒤 다시 본다 ({int(waited)}s)")
        time.sleep(30)


def cardpress() -> str:
    exe = os.environ.get("CARDPRESS") or shutil.which("cardpress")
    if exe:
        return exe
    venv = Path.home() / "Desktop" / "cardpress" / ".venv"
    for p in (venv / "Scripts" / "cardpress.exe", venv / "bin" / "cardpress"):
        if p.is_file():
            return str(p)
    raise SystemExit("cardpress 를 못 찾았다 — CARDPRESS 환경변수로 실행 파일 경로를 준다")


def _low_priority() -> dict:
    if sys.platform == "win32":
        return {"creationflags": subprocess.BELOW_NORMAL_PRIORITY_CLASS}
    return {"preexec_fn": lambda: os.nice(10)}


def render_one(key: str) -> bool:
    base = CORNERS_OUT / key
    deck, kit = base / "deck.yaml", base / "kit.yaml"
    if not deck.is_file():
        print(f"[render] {key}: 원고가 없다 — python -m poster.corners 먼저")
        return False
    if not wait_for_memory():
        return False
    env = {**os.environ, "CARDPRESS_RECYCLE": os.environ.get("CARDPRESS_RECYCLE", "4"), "PYTHONIOENCODING": "utf-8"}
    t = time.monotonic()
    # -o 를 꼭 준다 — 안 주면 cardpress 가 원고 파일 이름(deck)으로 out/deck/ 에 찍고, 시안 기록은 out/<코너>/ 의 옛 장을 본다
    r = subprocess.run([cardpress(), "render", str(deck), "-k", str(kit), "-o", str(base / "out")], env=env, **_low_priority())
    print(f"[render] {key}: {'완료' if r.returncode == 0 else f'실패({r.returncode})'} · {time.monotonic() - t:.0f}s"
          f" · 남은 메모리 {free_mb()}MB")
    return r.returncode == 0


def run(keys: list[str], after=None) -> list[str]:
    """keys 를 차례로 찍고, 찍힌 것마다 after(key)(시안 기록). 찍힌 코너 목록을 돌려준다."""
    done = []
    for n, key in enumerate(keys):
        if n:
            time.sleep(PAUSE_S)
        if render_one(key):
            done.append(key)
            if after:
                after(key)
    return done
