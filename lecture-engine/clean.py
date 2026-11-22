"""노트가 끝난 강의의 재료(장면 이미지·자막 원본·영상)를 지운다.

    python lecture-engine/clean.py            # 지울 것만 보여 준다
    python lecture-engine/clean.py --apply    # 실제로 지운다

지우는 조건은 셋 다다 — 하나라도 아니면 남긴다(다시 써야 할 수도 있으니).
  1) jd-viewer/public/lectures/items/<id>.json 노트가 있다
  2) 그 노트가 git 에 커밋돼 있다(작업 트리 변경 없음)
  3) DB viewer_doc 에 들어 있다 — store.ingest.docs 가 옮긴 것(지우기 전에 그 동기화를 한 번 돌린다)
남기는 것: transcript.txt·meta.json(편당 수십 KB). validate 의 '대본 전재' 검사가 대본을 쓴다.
영상 한 편의 장면이 10~15MB 라 과목 몇 개면 수백 MB 가 쌓였다(2026-11-21, 사용자 요청).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATCH = ROOT / "catch_capture"
WORK = CATCH / "var" / "lectures"
ITEMS = ROOT / "jd-viewer" / "public" / "lectures" / "items"
HEAVY = ("frames", "sheets")                      # 폴더
HEAVY_GLOBS = ("subs*.vtt", "video.*")            # 파일


def committed(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT, capture_output=True).returncode == 0
    dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return tracked and not dirty


def in_db() -> dict[str, str] | None:
    """viewer_doc 의 강의 노트 key → content_hash. DB 에 못 붙으면 None(그러면 아무것도 안 지운다)."""
    sys.path.insert(0, str(CATCH))
    try:
        from store.db import conn as store_conn
        from store.ingest import docs
        with store_conn.cursor() as cur:
            cur.execute("SELECT key, content_hash FROM viewer_doc WHERE kind = %s AND key LIKE 'lectures/items/%%'",
                        (docs.KIND,))
            return {r["key"]: r["content_hash"] for r in cur.fetchall()}
    except Exception as e:                        # noqa: BLE001
        print(f"[clean] DB 에 못 붙었다 — 아무것도 지우지 않는다: {str(e)[:120]}")
        return None


def size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def venv_python() -> Path | None:
    for rel in ("Scripts/python.exe", "bin/python"):
        p = CATCH / ".venv" / rel
        if p.exists():
            return p
    return None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    # 루프 세션은 시스템 python 으로 부른다 — 거기엔 psycopg 가 없어 DB 확인이 늘 실패하고 아무것도 못 지웠다.
    # DB 드라이버가 없으면 catch_capture 의 venv python 으로 다시 띄운다(fetch.py 의 yt_dlp 는 시스템 쪽에 있어 루프는 그대로 둔다).
    try:
        import psycopg  # noqa: F401
    except ImportError:
        vp = venv_python()
        if vp and Path(sys.executable).resolve() != vp.resolve() and "LECTURE_CLEAN_REEXEC" not in os.environ:
            env = {**os.environ, "LECTURE_CLEAN_REEXEC": "1", "PYTHONIOENCODING": "utf-8"}
            sys.exit(subprocess.run([str(vp), str(Path(__file__).resolve()), *sys.argv[1:]], env=env).returncode)
    apply = "--apply" in sys.argv
    if apply:                                     # 방금 쓴 노트도 DB 에 들어가 있게 — 회차 끝의 동기화와 같은 것
        sys.path.insert(0, str(CATCH))
        try:
            from store.ingest.docs import sync
            sync()
        except Exception as e:                    # noqa: BLE001
            print(f"[clean] 문서 동기화 실패 — 아무것도 지우지 않는다: {str(e)[:120]}")
            sys.exit(1)
    db = in_db()
    if db is None:
        sys.exit(1)
    freed = done = kept = 0
    for d in sorted(p for p in WORK.iterdir() if p.is_dir()):
        note = ITEMS / f"{d.name}.json"
        key = f"lectures/items/{d.name}.json"
        heavy = [d / h for h in HEAVY if (d / h).exists()] + [f for g in HEAVY_GLOBS for f in d.glob(g)]
        if not heavy:
            continue
        why = None
        if not note.exists():
            why = "노트 없음"
        elif not committed(note):
            why = "노트가 아직 커밋 전"
        elif key not in db:
            why = "DB 에 없음"
        if why:
            kept += 1
            print(f"  남김 {d.name} — {why}")
            continue
        n = sum(size(h) for h in heavy)
        freed += n
        done += 1
        print(f"  {'지움' if apply else '지울 것'} {d.name} — {n / 1e6:.1f}MB")
        if apply:
            for h in heavy:
                shutil.rmtree(h) if h.is_dir() else h.unlink()
    print(f"[clean] {'지웠다' if apply else '지울 수 있다'}: {done}편 · {freed / 1e6:.0f}MB · 남김 {kept}편")


if __name__ == "__main__":
    main()
