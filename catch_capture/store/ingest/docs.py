"""정적 문서 → 정본 DB(viewer_doc, kind='file'). 뷰어 API 의 `/api/docs/<경로>` 가 읽는다.

뷰어가 파일로만 받던 화면을 API 로 받게 한다. 대상은 두 종류다.
  - 빌더 산출물: 트렌드·캘린더·재공고·마인드맵·커리어 맵·학습 경로·레이더 … — DB 를 읽어
    파일로 굽는 계산은 그대로 두고 결과만 옮긴다.
  - 조사 엔진 문서: 역설계(reveng/)·취업 브리핑(guide/)·기술도서(book/)·하드웨어(hardware/) —
    Claude /loop 가 쓰고 git 으로 커밋하는 원고라 파일이 원본이다. DB 는 화면용 사본이다.

key 는 public 기준 경로('reveng/companies/toss.json')다. 내용 해시가 같으면 다시 쓰지 않고,
대상 범위 안에서 사라진 파일은 DB 에서도 지운다. .md 는 {"_text": 본문} 으로 담는다.

    python -m store.ingest.docs              # 바뀐 것만
    python -m store.ingest.docs --dry-run    # 무엇이 바뀌는지만
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))

from psycopg.types.json import Jsonb  # noqa: E402

from core.paths import VIEWER_PUBLIC  # noqa: E402
from store.db import conn as store_conn  # noqa: E402

KIND = "file"

# 한 파일씩 옮기는 것.
FILES = [
    "trends.json", "job_calendar.json", "reposts.json", "career_map.json", "mindmap_tree.json",
    "mindmap.md", "learning_resources.json", "blog_guides.json", "inflearn_courses.json",
    "tech_relations.json", "role_insights.json", "company_tech_radar.json", "engagement.json",
]
# 폴더째 옮기는 것(.json·.md). 부품 가격은 /api/hardware/prices 가 표에서 답하므로 뺀다.
DIRS = ["reveng", "guide", "book", "hardware", "blog_content"]
EXCLUDE = {"hardware/prices.json"}
EXTS = {".json", ".md"}


def targets(root: _Path = VIEWER_PUBLIC) -> list[_Path]:
    out = [root / f for f in FILES if (root / f).is_file()]
    for d in DIRS:
        base = root / d
        if base.is_dir():
            out += sorted(p for p in base.rglob("*") if p.is_file() and p.suffix in EXTS)
    return [p for p in out if p.relative_to(root).as_posix() not in EXCLUDE]


def in_scope(key: str) -> bool:
    return key in FILES or any(key.startswith(d + "/") for d in DIRS)


def _payload(path: _Path, raw: bytes):
    text = raw.decode("utf-8")
    return {"_text": text} if path.suffix == ".md" else json.loads(text)


def sync(root: _Path = VIEWER_PUBLIC, dry_run: bool = False, kind: str = KIND) -> dict:
    """kind 는 시험이 실제 문서와 섞이지 않게 바꿔 쓸 때만 준다."""
    files = targets(root)
    with store_conn.cursor() as cur:
        cur.execute("SELECT key, content_hash FROM viewer_doc WHERE kind = %s", (kind,))
        have = {r["key"]: r["content_hash"] for r in cur.fetchall()}

        seen: set[str] = set()
        written = bad = 0
        for p in files:
            key = p.relative_to(root).as_posix()
            seen.add(key)
            raw = p.read_bytes()
            digest = hashlib.sha1(raw).hexdigest()
            if have.get(key) == digest:
                continue
            try:
                payload = _payload(p, raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                # 반쯤 쓰인 파일 등 — 이번 회차는 건너뛰고 DB 의 옛 판을 그대로 둔다.
                print(f"  [docs] 건너뜀 {key}: {e}", file=_sys.stderr)
                bad += 1
                continue
            written += 1
            if not dry_run:
                cur.execute(
                    "INSERT INTO viewer_doc (kind, key, payload, content_hash) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (kind, key) DO UPDATE SET payload = EXCLUDED.payload, "
                    "content_hash = EXCLUDED.content_hash, built_at = now()",
                    (kind, key, Jsonb(payload), digest))

        gone = [k for k in have if k not in seen and in_scope(k)]
        if gone and not dry_run:
            cur.execute("DELETE FROM viewer_doc WHERE kind = %s AND key = ANY(%s)", (kind, gone))
        if dry_run:
            cur.connection.rollback()
    return {"files": len(files), "written": written, "removed": len(gone), "skipped_bad": bad}


def main() -> int:
    ap = argparse.ArgumentParser(description="정적 문서 → viewer_doc")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = sync(dry_run=args.dry_run)
    print(f"[docs] 문서 {s['files']:,}개 · 갱신 {s['written']:,} · 삭제 {s['removed']:,}"
          + (f" · 깨진 파일 {s['skipped_bad']}" if s["skipped_bad"] else "")
          + (" (dry-run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
