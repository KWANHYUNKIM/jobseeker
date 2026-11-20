#!/usr/bin/env python3
"""책 예제를 엔진 전용 가상환경에서 돌린다 — `python book-engine/run.py <예제.py> [인자…]`.

루프는 `python …` 명령만 허락받아 돈다(automation/loop_runner.py). 가상환경의 파이썬 경로를 직접 부르면
그 허락 밖이라 막히므로, 이 파일이 대신 가상환경을 만들고(없으면) 그 안의 파이썬으로 예제를 돌린다.

    python book-engine/run.py --install pandas matplotlib    # 패키지 더하기
    python book-engine/run.py book-engine/work/hist.py       # 예제 실행 — 출력이 그대로 책에 실린다

예제 파일과 그 출력은 `book-engine/work/` 에 둔다(커밋하지 않는다). 그림은 예제가 직접
`jd-viewer/public/book/<책>/img/` 에 저장한다.
"""
from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"
BASE = ["pandas", "numpy", "matplotlib", "scikit-learn"]


def _python() -> Path:
    exe = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not exe.exists():
        venv.create(VENV, with_pip=True)
        subprocess.check_call([str(exe), "-m", "pip", "install", "-q", *BASE])
    return exe


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    py = _python()
    if argv[0] == "--install":
        return subprocess.call([str(py), "-m", "pip", "install", "-q", *argv[1:]])
    env = {**os.environ, "MPLBACKEND": "Agg", "PYTHONIOENCODING": "utf-8"}   # 화면 없이 그림만 파일로
    return subprocess.call([str(py), *argv], env=env)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
