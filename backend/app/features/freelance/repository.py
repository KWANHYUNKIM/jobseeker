"""외주·프리 프로젝트 — project 표(파이프라인 store/market/freelance.py 가 쓴다)와 분석 문서."""
from __future__ import annotations

from app.db.docs import get_doc
from app.db.session import cursor

HISTORY_KEEP = 30   # 프로젝트마다 화면 '세부 내역' 표에 싣는 변경 이력 수


def projects() -> tuple[list[dict], dict[int, list[dict]], dict[int, str]]:
    """프로젝트 행(모집 상태는 project_state 가 지금 계산), 변경 이력, 닫힌 근거."""
    with cursor() as cur:
        cur.execute("SELECT * FROM v_project "
                    "ORDER BY COALESCE(posted_on, first_seen_at::date) DESC, id DESC")
        rows = cur.fetchall()
        cur.execute("SELECT project_id, seen_at, budget_basis::text AS b, budget_min, budget_max, "
                    "duration_days, source_open, applicants FROM project_version "
                    "ORDER BY project_id, seen_at")
        hist: dict[int, list[dict]] = {}
        for v in cur.fetchall():
            hist.setdefault(v["project_id"], []).append(v)
        cur.execute("SELECT project_id, evidence FROM project_check_latest WHERE closed")
        reasons = {r["project_id"]: r["evidence"] for r in cur.fetchall()}
    return rows, hist, reasons


def meta() -> dict | None:
    return get_doc("freelance", "meta")
