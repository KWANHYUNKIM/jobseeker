"""claude-loop 을 '한 번 = 새 프로세스 하나' 로 돌린다.

왜. 조사 엔진(역설계·브리핑·하드웨어 레인·인스타 …)을 열어 둔 세션의 `/loop` 로 돌리면 반복마다
도구 결과·스크린샷이 대화에 쌓여 세션이 끝없이 커진다(한 세션의 기록이 77MB 까지 갔다, 2026-11).
엔진은 원래 다음 일감을 파일(state/·STATE.md·LOG.md·validate.py --gaps)에서 읽게 짜여 있어서
대화를 이어 갈 이유가 없다. 그래서 반복 한 번마다 `claude -p "<loops.py 의 프롬프트>"` 를 새로 띄우고
끝나면 버린다 — 세션이 자라지 않는다.

    python -m automation.loops run hw-engine                 # 한 번(잠금·시간 제한·기록)
    python -m automation.loops run hw-engine --dry-run       # 무엇을 부를지만
    python -m automation.loops repeat hw-engine --every 20m  # 주기 반복(--times N 으로 횟수 제한)

기록은 var/loops/<키>/ — 회차마다 로그 하나(최근 KEEP_LOGS 개만)와 마지막 결과(last.json).
`python -m automation.loops list` 와 8770 '반복 작업' 칸이 last.json 을 같이 보여 준다.

권한. 무인 실행이라 묻지 않는다 — 편집은 받아들이고(acceptEdits), 셸은 git·python 만 연다.
`git push` 는 막는다(엔진 프롬프트도 '푸시하지 않는다'). 바꾸려면 LOOP_CLAUDE_ARGS 에 인자를 준다.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import json
import os
import re
import shlex
import shutil
import subprocess
import time
from datetime import datetime

from core.paths import VAR_DIR

RUN_DIR = VAR_DIR / "loops"
KEEP_LOGS = 30
TIMEOUT_S = 45 * 60
ALLOWED = ["Read", "Edit", "Write", "Glob", "Grep", "WebFetch", "WebSearch",
           "Bash(git:*)", "Bash(python:*)", "Bash(python3:*)", "Bash(ls:*)", "Bash(cd:*)"]
DENIED = ["Bash(git push:*)"]
UNATTENDED = (" (무인 실행이다 — 사람에게 묻지 말고 끝까지 한다. 막히면 그 사실을 로그에 남기고 그 회차를 끝낸다. "
              "이 회차와 상관없는 파일·남이 고치던 파일은 건드리지 않는다.)")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _dir(key: str):
    d = RUN_DIR / key
    d.mkdir(parents=True, exist_ok=True)
    return d


def last_run(key: str) -> dict | None:
    try:
        return json.loads((RUN_DIR / key / "last.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _lock(key: str, timeout_s: int) -> bool:
    """같은 엔진이 겹쳐 돌면 같은 파일을 고쳐 커밋이 섞인다 — 이미 돌고 있으면 이번 회차를 건너뛴다.
    잠금이 시간 제한보다 오래됐으면(죽은 회차가 남긴 것) 치우고 잡는다."""
    lock = _dir(key) / "run.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        age = time.time() - lock.stat().st_mtime
        if age < timeout_s + 600:
            return False
        lock.unlink(missing_ok=True)
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"pid": os.getpid(), "started": _now()}))
    return True


def _unlock(key: str) -> None:
    (RUN_DIR / key / "run.lock").unlink(missing_ok=True)


def command(prompt: str) -> list[str]:
    exe = shutil.which("claude")
    if not exe:
        raise FileNotFoundError("claude CLI 가 PATH 에 없다")
    extra = os.environ.get("LOOP_CLAUDE_ARGS")
    args = shlex.split(extra) if extra else [
        "--permission-mode", "acceptEdits",
        "--allowedTools", ",".join(ALLOWED),
        "--disallowedTools", ",".join(DENIED),
    ]
    # 프롬프트는 표준입력으로 준다 — 윈도우의 claude 는 .CMD 래퍼라 긴 한글·괄호 인자가 cmd.exe 를 거치며 깨진다.
    return [exe, "-p", "--output-format", "json", *args]


def run_once(loop, root, timeout_s: int = TIMEOUT_S, dry_run: bool = False) -> dict:
    """엔진 한 회차. 반환은 last.json 에 적는 것과 같다."""
    if not loop.prompt:
        raise ValueError(f"{loop.key} 는 claude-loop 이 아니다({loop.kind}) — {loop.run}")
    cmd = command(loop.prompt)
    if dry_run:
        print(" ".join(shlex.quote(c) for c in cmd) + "  < 프롬프트(표준입력)")
        return {"key": loop.key, "dry_run": True}
    if not _lock(loop.key, timeout_s):
        print(f"[loops] {loop.key} — 이미 도는 회차가 있어 건너뜀", flush=True)
        return {"key": loop.key, "skipped": "locked", "at": _now()}
    d = _dir(loop.key)
    started = _now()
    log = d / (re.sub(r"[^0-9T]", "", started[:19]) + ".log")
    t0 = time.time()
    rec: dict = {"key": loop.key, "started": started}
    try:
        try:
            p = subprocess.run(cmd, cwd=str(root), input=loop.prompt + UNATTENDED, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout_s)
            out, err, code = p.stdout, p.stderr, p.returncode
        except subprocess.TimeoutExpired as e:
            out, err, code = (e.stdout or ""), (e.stderr or ""), "timeout"
            out = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
            err = err.decode("utf-8", "replace") if isinstance(err, bytes) else err
        log.write_text(f"# {loop.key} {started}\n\n## stdout\n{out}\n\n## stderr\n{err}\n", encoding="utf-8")
        result: dict = {}
        try:
            result = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
        except (json.JSONDecodeError, IndexError):
            pass
        rec.update(
            ended=_now(), seconds=round(time.time() - t0), exit=code,
            ok=code == 0 and not result.get("is_error"),
            turns=result.get("num_turns"), cost_usd=result.get("total_cost_usd"),
            summary=(result.get("result") or err or "")[-1500:].strip(),
            log=str(log.relative_to(VAR_DIR.parent)),
        )
    finally:
        _unlock(loop.key)
    (d / "last.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    for old in sorted(d.glob("*.log"))[:-KEEP_LOGS]:
        old.unlink(missing_ok=True)
    mark = "ok" if rec["ok"] else f"실패({rec['exit']})"
    print(f"[loops] {loop.key} {mark} · {rec['seconds']}s · {rec.get('turns')}턴 · ${rec.get('cost_usd')}\n{rec['summary']}", flush=True)
    return rec


def parse_every(text: str) -> int:
    """'20m' '2h' '90s' → 초"""
    m = re.fullmatch(r"(\d+)\s*([smh])", text.strip())
    if not m:
        raise ValueError(f"주기는 20m·2h·90s 꼴: {text!r}")
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600}[m.group(2)]


def repeat(loop, root, every_s: int, times: int | None = None, timeout_s: int = TIMEOUT_S) -> None:
    """주기 반복. 회차 사이에는 프로세스가 아무것도 들고 있지 않다 — 다음 회차는 또 새 claude 다.
    실패해도 다음 회차는 돈다(연속 3번 실패하면 멈춘다 — 프롬프트·권한이 깨진 것이다)."""
    n = fails = 0
    while times is None or n < times:
        n += 1
        print(f"[loops] {loop.key} {n}회차 시작 {_now()}", flush=True)
        rec = run_once(loop, root, timeout_s)
        fails = 0 if rec.get("ok") or rec.get("skipped") else fails + 1
        if fails >= 3:
            print(f"[loops] {loop.key} 연속 3번 실패 — 멈춘다. 마지막 로그: {rec.get('log')}", flush=True)
            return
        if times is not None and n >= times:
            break
        time.sleep(every_s)
