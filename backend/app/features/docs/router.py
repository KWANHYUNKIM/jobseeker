"""정적 문서 API — 뷰어가 파일로만 받던 화면을 DB 에서 답한다.

    GET /api/docs/trends.json
    GET /api/docs/reveng/companies/toss.json
    GET /api/docs/mindmap.md                    (마크다운은 text/markdown)

역설계·취업 브리핑·기술도서·레이더·트렌드·캘린더·재공고·마인드맵·커리어 맵·학습 경로·
부품 스펙·데이터센터가 이 경로로 받는다. 응답은 같은 이름의 정적 파일과 글자 그대로 같은
내용이고, 없으면 404 — 뷰어는 그때 정적 파일로 물러선다(src/api/client.ts 의 docFetch).
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from app.features.docs import service

router = APIRouter(prefix="/api/docs", tags=["docs"])


@router.get("/{path:path}")
def get_doc(path: str) -> Response:
    doc = service.get(path)
    headers = {"ETag": f'"{doc["content_hash"]}"'} if doc["content_hash"] else {}
    payload = doc["payload"]
    if path.endswith(".md"):
        return PlainTextResponse(payload.get("_text", ""), media_type="text/markdown; charset=utf-8",
                                 headers=headers)
    return JSONResponse(payload, headers=headers)
