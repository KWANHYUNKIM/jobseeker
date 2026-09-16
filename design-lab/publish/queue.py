"""발행 큐 — 무엇을 어디에 언제 올렸는지의 원장.

크롤 쪽 job_closures.json 과 같은 성격이다. 파일 하나가 진실이고, 같은 공고를 같은
플랫폼에 두 번 올리는 사고를 막는 것이 이 파일의 첫 번째 일이다.

상태는 두 갈래다.

  랩(8780)에서 손으로:   planned → rendered → published | failed
  자동 발행(daemon):     approved → scheduled → published
                                              ↘ failed     (재시도 다 쓴 것)
                                              ↘ rehearsed  (자격이 없어 dry-run 으로만 돈 것)
                                              ↘ skipped    (그 사이 공고가 마감된 것)

사람은 approved 까지만 만든다(publish.cli approve). 그 뒤는 데몬이 한다.
rehearsed 는 실제로 안 나갔다는 뜻이다 — 자격을 넣은 뒤 requeue 로 approved 로 되돌린다.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
LEDGER = LAB_DIR / "state" / "publish_queue.json"

#: 아직 끝나지 않은(데몬이 손댈) 상태
PENDING = ("approved", "scheduled")
#: 끝난 상태 — 데몬이 다시 건드리지 않는다
FINAL = ("published", "failed", "rehearsed", "skipped")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load() -> dict:
    if LEDGER.is_file():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"items": []}


def save(data: dict) -> None:
    # 대시보드(8770)가 2초마다 읽는다. 쓰다 만 파일을 읽히지 않게 바꿔치기로 쓴다.
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, LEDGER)


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


def add_approved(bundle: dict, image_rel: str, images: list[str] | None = None,
                 video_rel: str = "") -> dict:
    """승인 묶음(inbox) 하나를 원장에 올린다. 같은 id 가 이미 있으면 그대로 돌려준다.

    images 가 있으면 묶음(카테고리) 게시물이다 — 표지 + 공고 판 여러 장이 한 게시물로 나간다.
    video_rel 이 있으면 그 묶음은 **영상 한 편**으로 나간다(인스타 릴스 / 페이스북 동영상).
    둘 중 하나다 — 같은 내용을 캐러셀로도 영상으로도 올리면 중복 게시로 보인다.
    """
    data = load()
    for item in data["items"]:
        if item["id"] == bundle["id"]:
            return item
    item = {
        "id": bundle["id"],
        # 묶음인지 공고 한 건인지. **판이 몇 장인지로 판단하지 않는다** — 릴스 묶음은
        # 판 대신 mp4 한 개로 오므로 장 수로 재면 공고 한 건으로 오인되고, 그러면
        # drop_closed 가 `collection:week-…` 를 공고 색인에서 찾다가 없으니 마감으로
        # 보고 묶음을 통째로 버린다. 묶음의 표시는 카테고리 정보(collection)다.
        "kind": "collection" if (bundle.get("collection") or images or video_rel) else "job",
        "job_key": bundle["job_key"],
        # 묶음일 때만: 카테고리 정보와 들어간 공고들
        "collection": bundle.get("collection") or {},
        "images": images or [],
        # "carousel"(기본) | "reel". 발행 단계가 이 값으로 갈린다.
        "format": "reel" if video_rel else (bundle.get("format") or "carousel"),
        "video": video_rel,
        "company": bundle.get("company", ""),
        "role": bundle.get("role", ""),
        "template": bundle.get("template", "brand"),
        "palette": "",
        "formats": ["ig_portrait"],
        "platforms": bundle.get("platforms") or ["instagram"],
        "status": "approved",
        "note": bundle.get("note", ""),
        # approve --force — 같은 공고를 일부러 다시 올린다(판을 고쳐 다시 올리는 경우).
        # 받기 단계와 발행 단계의 중복 검사를 둘 다 건너뛴다.
        "force": bool(bundle.get("force")),
        "caption": bundle.get("caption", ""),              # 예전 묶음 호환
        "captions": bundle.get("captions") or {},          # 플랫폼 → 캡션
        "files": {"ig_portrait": image_rel},
        "results": {},
        "posted": [],                                      # 실제로 올라간 플랫폼
        "attempts": 0,
        "scheduled_at": "",
        "published_at": "",
        "approved_at": bundle.get("approved_at", _now()),
        "approved_on": bundle.get("approved_on", ""),
        "history": [{"at": _now(), "event": "approved", "detail": bundle.get("approved_on", "")}],
        "stats": {},
        "created_at": _now(),
        "updated_at": _now(),
    }
    data["items"].append(item)
    save(data)
    return item


def get(item_id: str) -> dict | None:
    return next((i for i in load()["items"] if i["id"] == item_id), None)


def update(item_id: str, *, event: str = "", detail: str = "", **fields) -> dict | None:
    """필드를 고친다. event 를 주면 history 에 한 줄 남긴다(대시보드가 이걸로 경과를 그린다)."""
    data = load()
    for item in data["items"]:
        if item["id"] == item_id:
            item.update(fields)
            item["updated_at"] = _now()
            if event:
                item.setdefault("history", []).append(
                    {"at": item["updated_at"], "event": event, "detail": detail[:300]})
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


def pending_for(job_key: str, platform: str) -> dict | None:
    """같은 공고·플랫폼으로 이미 줄 서 있는 항목."""
    return next((i for i in load()["items"]
                 if i["job_key"] == job_key and i["status"] in PENDING
                 and platform in i.get("platforms", [])), None)


def items(status: str = "") -> list[dict]:
    rows = load()["items"]
    if status:
        rows = [i for i in rows if i["status"] == status]
    return sorted(rows, key=lambda i: i["created_at"], reverse=True)
