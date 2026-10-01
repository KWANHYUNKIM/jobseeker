"""공통 경로 — 데이터·실행 위치의 단일 소스.

코드는 기능별 폴더(core·crawlers·pipeline·store·automation·servers)에 있고, 데이터는
catch_capture 루트(screenshots/·원장 파일들)와 `var/`(예전에 코드 폴더 안에 섞여 있던
런타임 데이터)에 둔다. 코드 폴더를 옮겨도 데이터가 따라 움직이지 않게 하려는 것이다.
"""
from __future__ import annotations

import sys
from pathlib import Path

CATCH_DIR = Path(__file__).resolve().parent.parent      # catch_capture/
ROOT_DIR = CATCH_DIR.parent                              # jobseeker/
SCREENSHOTS_DIR = CATCH_DIR / "screenshots"
VENV_PY = CATCH_DIR / ".venv" / "bin" / "python"
JD_VIEWER_DIR = ROOT_DIR / "jd-viewer"
VIEWER_PUBLIC = JD_VIEWER_DIR / "public"
REFRESH_SH = JD_VIEWER_DIR / "bin" / "refresh-data.sh"

# ── 런타임 데이터(git 밖) ─────────────────────────────────────────────
VAR_DIR = CATCH_DIR / "var"
# 방문 기록(8772 collect 가 쓰고 pipeline.engagement_score 가 읽는다). 정본은 DB engagement_event.
ENGAGEMENT_EVENTS = VAR_DIR / "engagement" / "events.jsonl"
# admin(8910) 개인 데이터 — 이력·지원 내역·API 키. 절대 커밋·터널 금지.
ADMIN_DATA_DIR = VAR_DIR / "admin" / "data"
ADMIN_SECRETS = VAR_DIR / "admin" / ".secrets.json"

# 폴더 개편(2026-10-01) 전 위치. adopt() 가 처음 쓰일 때 새 위치로 옮긴다.
LEGACY = {
    ENGAGEMENT_EVENTS: CATCH_DIR / "engagement" / "events.jsonl",
    ENGAGEMENT_EVENTS.with_suffix(".jsonl.1"): CATCH_DIR / "engagement" / "events.jsonl.1",
    ADMIN_DATA_DIR: CATCH_DIR / "admin" / "data",
    ADMIN_SECRETS: CATCH_DIR / "admin" / ".secrets.json",
}


def adopt(*targets: Path) -> None:
    """옛 위치에 남은 데이터를 새 위치로 옮긴다(없으면 아무것도 안 한다).

    배포 스크립트에 기대지 않고 데이터를 쓰는 모듈이 뜰 때 스스로 부른다 — 코드만 옮기고
    데이터는 옛 폴더에 남겨 두면, 새 코드는 빈 파일에서 시작해 기록이 갈라진다.
    새 위치에 이미 있으면 덮어쓰지 않는다: 폴더면 없는 파일만 옮기고, 파일이면 옛 것을
    `.legacy` 를 붙여 옆에 둔다(사람이 보고 합친다).
    """
    for new in targets:
        old = LEGACY.get(new)
        if not old or not old.exists():
            continue
        try:
            new.parent.mkdir(parents=True, exist_ok=True)
            if not new.exists():
                old.replace(new)
            elif old.is_dir():
                for f in old.rglob("*"):
                    dest = new / f.relative_to(old)
                    if f.is_file() and not dest.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        f.replace(dest)
            else:
                old.replace(new.with_name(new.name + ".legacy"))
        except OSError as e:                                        # 동시에 옮기던 다른 프로세스 등
            print(f"[paths] {old} → {new} 옮기기 실패: {e}", file=sys.stderr)
