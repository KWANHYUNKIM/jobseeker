"""뷰어 ↔ API 계약 — DB 없이 OpenAPI 명세만 본다.

뷰어(jd-viewer/src/features/jobs/hooks/useJobsApi.ts 의 toParams)가 보내는 파라미터 이름을 서버가
받는지. 이름이 한쪽에서만 바뀌면 필터가 조용히 무시된다(422 도 안 난다 — 모르는
파라미터는 FastAPI 가 그냥 버린다). 뷰어 쪽 목록은 useJobsApi.test.ts 가 고정한다.
"""
from __future__ import annotations

import re

from tests.conftest import VIEWER

VIEWER_PARAMS = {"site", "career", "stack", "role", "region", "district", "size", "q",
                 "semantic", "closed", "unverified", "page", "limit"}
TS = VIEWER / "src" / "features" / "jobs" / "api.ts"


def _server_params() -> set[str]:
    from app.main import app
    op = app.openapi()["paths"]["/api/jobs"]["get"]
    return {p["name"] for p in op["parameters"]}


def test_server_accepts_every_param_the_viewer_sends():
    assert VIEWER_PARAMS <= _server_params()


def test_viewer_source_sends_exactly_these_params():
    # toParams 본문에서 add('이름', …) / p.set('이름', …) 을 긁는다.
    src = TS.read_text(encoding="utf-8")
    body = src[src.index("export function toParams"):]
    body = body[: body.index("\n}\n")]
    sent = set(re.findall(r"add\('([a-z_]+)'", body)) | set(re.findall(r"p\.set\('([a-z_]+)'", body))
    assert sent == VIEWER_PARAMS


def test_list_paths_exist():
    from app.main import app
    paths = set(app.openapi()["paths"])
    assert {"/api/jobs", "/api/jobs/{key}", "/api/jobs/lookup", "/api/search",
            "/api/health"} <= paths
