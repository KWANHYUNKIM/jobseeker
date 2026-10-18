"""메인 화면 스냅숏 — 뷰어 API 가 없을 때 `/` 가 읽는 `jd-viewer/public/home.json`.

뷰어는 화면마다 API 먼저, 안 되면 정적 파일이다(src/api/client.ts). 메인(`/api/home`)도 그렇게
물러서도록 회차마다 같은 모양을 파일로 굽는다. 묶기·점수·업종 규칙은 backend 의
`app.features.home.service` 를 그대로 부른다 — 파일과 API 가 다른 규칙을 쓰면 API 가 꺼진 날만
화면이 달라진다(store.jobs.export 가 공고 매핑을 backend 에서 가져오는 것과 같은 이유).

파일에는 회사 300곳과 구역마다 TOP 50 전부를 싣는다 — API 가 없으면 '더보기'도 파일에서 편다.
회사 패널(그 회사 공고 전부)은 싣지 않는다(뷰어가 잡 리스트로 안내한다).

    python -m store.jobs.home_export          # refresh-data.sh 가 공고 내보내기 다음에 부른다
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))  # catch_capture 루트

import json
import os

from core.paths import ROOT_DIR, VIEWER_PUBLIC

# 방향은 언제나 파이프라인 → backend 다(backend 는 파이프라인을 import 하지 않는다).
_sys.path.insert(0, str(ROOT_DIR / "backend"))
os.environ.setdefault("API_CACHE_TTL", "0")      # 한 번 굽고 끝나는 프로세스라 캐시가 필요 없다

OUT = VIEWER_PUBLIC / "home.json"
COMPANIES = 300


def build() -> dict:
    from app.features.home import service
    d = service.home(limit=COMPANIES)
    d["sections"] = [dict(x) for x in service._sections()]   # 파일은 구역마다 50건 전부
    d["snapshot"] = True
    return d


def main() -> int:
    try:
        d = build()
    except Exception as e:                                  # noqa: BLE001 — DB 가 없으면 기존 파일을 둔다
        print(f"[home_export] 건너뜀: {e}", file=_sys.stderr)
        return 1
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(OUT)
    print(f"[home_export] 회사 {len(d['companies'])} · 구역 {len(d['sections'])} → {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
