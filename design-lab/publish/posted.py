"""이미 내보낸 공고 — 같은 공고를 두 번 올리지 않으려고 묻는 곳.

묶음(week·role·…)은 매주 새로 고르는데, 고르는 기준이 '알아보는 회사 → 큰 회사 → 마감 순' 이라
모집이 길게 열려 있는 공고는 매주 같은 자리에 다시 뽑힌다. 2026-09-29 의 이번 주 묶음 8장 중
6장이 9/16 에 이미 올라간 공고였다. 그래서 고르는 단계에서 이 목록을 빼고 고른다.

'내보냈다' 는 넓게 잡는다 — 실제로 올라간 것만이 아니라 올라가기로 한 것까지.

  | 어디                                 | 무엇                                   |
  |--------------------------------------|----------------------------------------|
  | state/publish_queue.json             | 이 머신의 원장(맥에서는 이게 진실)     |
  | state/publish_queue.mac.json         | 윈도우가 push 뒤 받아 둔 맥 원장 사본  |
  | inbox/<id>/bundle.json               | 승인했지만 아직 안 보낸 묶음           |
  | inbox/_sent/<id>/bundle.json         | 맥으로 보냈지만 원장 사본에 아직 없는 것 |

원장 상태 중 failed·skipped 는 안 나간 것이라 다시 쓸 수 있다. rehearsed 는 안 나갔지만
requeue 하면 나가므로 잡아 둔다. inbox/_held/ 는 사람이 보류한 묶음이라 세지 않는다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
LEDGERS = (LAB_DIR / "state" / "publish_queue.json", LAB_DIR / "state" / "publish_queue.mac.json")
INBOX = LAB_DIR / "inbox"

#: 이 상태면 그 공고는 '쓴 것' 이다
TAKEN = ("approved", "scheduled", "published", "rehearsed")


def title_key(company: str, title: str) -> str:
    """같은 회사·같은 제목이면 번호가 달라도 같은 자리다 — 토스는 'Node.js Developer' 를
    번호 둘로 올려 두었고, 그게 이번 주 묶음과 백엔드 묶음에 한 장씩 실렸다."""
    norm = lambda t: re.sub(r"[\s\W_]+", "", (t or "").lower())      # noqa: E731
    return f"title:{norm(company)}|{norm(title)}"


def _keys(item: dict) -> list[str]:
    """원장 항목·묶음 하나가 실은 공고 키들 — 공고 키와 (회사, 제목) 키를 같이 낸다.
    한 장짜리는 job_key, 묶음은 그 안의 공고들."""
    jk = item.get("job_key") or ""
    col = item.get("collection") or {}
    keys = []
    for j in col.get("jobs") or []:
        if j.get("key"):
            keys.append(j["key"])
        if j.get("company") and j.get("role"):
            keys.append(title_key(j["company"], j["role"]))
    if jk and not jk.startswith("collection:"):
        keys.append(jk)
        if item.get("company") and item.get("role"):
            keys.append(title_key(item["company"], item["role"]))
    return keys


def taken(job: dict, table: dict) -> dict | None:
    """이 공고를 이미 냈나 — 번호로 먼저, 없으면 (회사, 제목)으로."""
    return table.get(job.get("key", "")) or table.get(title_key(job.get("company", ""), job.get("title", "")))


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def posted() -> dict[str, dict]:
    """{공고키: {"id", "status", "at", "where"}} — 한 번이라도 내보냈거나 내보내기로 한 공고."""
    out: dict[str, dict] = {}

    def put(key: str, item: dict, status: str, where: str) -> None:
        at = item.get("published_at") or item.get("approved_at") or item.get("created_at") or ""
        if key not in out or at > out[key]["at"]:
            out[key] = {"id": item.get("id", ""), "status": status, "at": at, "where": where}

    for ledger in LEDGERS:
        for item in _read(ledger).get("items") or []:
            if item.get("status") in TAKEN:
                for k in _keys(item):
                    put(k, item, item["status"], ledger.name)
    for folder, status in ((INBOX, "approved"), (INBOX / "_sent", "sent")):
        if not folder.is_dir():
            continue
        for bundle in folder.glob("*/bundle.json"):
            item = _read(bundle)
            for k in _keys(item):
                if k not in out:                         # 원장에 있으면 원장 상태가 맞다
                    put(k, item, status, f"{folder.name}/{bundle.parent.name}")
    return out


def describe(key: str, row: dict) -> str:
    return f"{key} — {row['status']} {row['at'][:10]} ({row['where']}:{row['id']})"
