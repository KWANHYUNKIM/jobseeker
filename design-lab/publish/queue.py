"""발행 큐 — 무엇을 어디에 언제 올렸는지의 원장.

크롤 쪽 job_closures.json 과 같은 성격이다. 파일 하나가 진실이고, 상태는
planned → rendered → published 로만 앞으로 간다(실패는 failed 로 남기고 재시도).
같은 공고를 같은 플랫폼에 두 번 올리는 사고를 막는 것이 이 파일의 첫 번째 일이다.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
LEDGER = LAB_DIR / "state" / "publish_queue.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load() -> dict:
    if LEDGER.is_file():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"items": []}


def save(data: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add(job_key: str, *, template: str, formats: list[str], platforms: list[str],
        palette: str = "", note: str = "") -> dict:
    data = load()
    item = {
        "id": uuid.uuid4().hex[:8],
        "job_key": job_key,
        "template": template,
        "palette": palette,
        "formats": formats,
        "platforms": platforms,
        "status": "planned",
        "note": note,
        "files": {},          # format → out/ 상대경로
        "results": {},        # platform → PublishResult dict
        "created_at": _now(),
        "updated_at": _now(),
    }
    data["items"].append(item)
    save(data)
    return item


def get(item_id: str) -> dict | None:
    return next((i for i in load()["items"] if i["id"] == item_id), None)


def update(item_id: str, **fields) -> dict | None:
    data = load()
    for item in data["items"]:
        if item["id"] == item_id:
            item.update(fields)
            item["updated_at"] = _now()
            save(data)
            return item
    return None


def remove(item_id: str) -> bool:
    data = load()
    before = len(data["items"])
    data["items"] = [i for i in data["items"] if i["id"] != item_id]
    save(data)
    return len(data["items"]) < before


def published_platforms(job_key: str) -> set[str]:
    """이 공고가 이미 올라간 플랫폼들 — 중복 발행을 막는 근거."""
    out: set[str] = set()
    for item in load()["items"]:
        if item["job_key"] != job_key:
            continue
        for platform, res in (item.get("results") or {}).items():
            if res.get("ok") and not res.get("dry_run"):
                out.add(platform)
    return out


def items(status: str = "") -> list[dict]:
    rows = load()["items"]
    if status:
        rows = [i for i in rows if i["status"] == status]
    return sorted(rows, key=lambda i: i["created_at"], reverse=True)
