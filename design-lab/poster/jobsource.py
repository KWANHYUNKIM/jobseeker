"""공고 원천 — 127MB 짜리 all_jobs_enriched.json 을 포스터에 필요한 만큼만 깎아 둔다.

랩 서버가 원본을 통째로 들고 있으면 8GB 머신에서 크롤과 같이 못 뜬다. 그래서
한 번만 스트리밍으로 훑어 슬림 색인(state/jobs_index.json)을 만들고, 이후에는
그것만 읽는다. 원본이 새로 갱신되면 mtime 이 달라지므로 자동으로 다시 만든다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = LAB_DIR.parent
SOURCE = ROOT_DIR / "jd-viewer" / "public" / "all_jobs_enriched.json"
INDEX = LAB_DIR / "state" / "jobs_index.json"

# 불릿으로 쓸 수 있는 줄머리들. 사이트마다 제각각이라 넉넉히 받는다.
_BULLET = re.compile(r"^\s*(?:[*\-•·▶▪◆■□○●]|└|\d+[.)])\s*")
_NOISE = re.compile(r"^\s*[#=\-]{2,}\s*$")


def _bullets(text: str, limit: int) -> list[str]:
    """긴 문단에서 '읽을 수 있는 한 줄'만 골라낸다."""
    out: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or _NOISE.match(line):
            continue
        if line.startswith("#"):          # 소제목(#이런 동료를 만나고 싶어요)은 버린다
            continue
        if not _BULLET.match(line):
            continue
        line = _BULLET.sub("", line).strip()
        line = re.sub(r"\s+", " ", line)
        if len(line) < 6:
            continue
        if len(line) > 68:                # 포스터는 두 줄 넘어가면 못 읽는다
            line = line[:66].rstrip() + "…"
        if line in out:
            continue
        out.append(line)
        if len(out) >= limit:
            break
    return out


def _slim(job: dict) -> dict | None:
    site, pid = job.get("site"), job.get("pid")
    if not site or not pid:
        return None
    return {
        "key": f"{site}-{pid}",
        "site": site,
        "pid": str(pid),
        "company": (job.get("company") or "").strip(),
        "title": (job.get("title") or "").strip(),
        "url": job.get("url") or "",
        "career": (job.get("career") or "").strip(),
        "location": (job.get("location") or "").strip(),
        "stack": [t for t in (job.get("tech_stack") or []) if t][:10],
        "status": job.get("status") or "active",
        "deadline": (job.get("deadline") or job.get("deadline_date") or "").strip(),
        "dday": job.get("dday"),
        "qualifications": _bullets(job.get("qualifications", ""), 5),
        "preferences": _bullets(job.get("preferences", ""), 4),
        "tasks": _bullets(job.get("main_tasks", ""), 5),
    }


def build_index(source: Path = SOURCE, dest: Path = INDEX) -> dict:
    """원본을 한 건씩 뜯어 슬림 색인으로 옮긴다(전체 파싱 결과를 메모리에 안 남긴다)."""
    if not source.is_file():
        raise FileNotFoundError(f"공고 원본이 없습니다: {source}")
    text = source.read_text(encoding="utf-8")
    dec = json.JSONDecoder()
    i = text.index("[") + 1
    jobs: list[dict] = []
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n or text[i] == "]":
            break
        obj, i = dec.raw_decode(text, i)
        slim = _slim(obj)
        if slim and slim["company"] and slim["title"]:
            jobs.append(slim)
    del text
    payload = {
        "source_mtime": source.stat().st_mtime,
        "count": len(jobs),
        "jobs": jobs,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def load_index(rebuild: bool = False) -> dict:
    """색인을 읽는다. 원본이 더 새로우면 조용히 다시 만든다."""
    if not rebuild and INDEX.is_file():
        payload = json.loads(INDEX.read_text(encoding="utf-8"))
        if SOURCE.is_file() and payload.get("source_mtime") == SOURCE.stat().st_mtime:
            return payload
        if not SOURCE.is_file():
            return payload
    return build_index()


def search(q: str = "", *, only_active: bool = True, limit: int = 40) -> list[dict]:
    jobs = load_index()["jobs"]
    q = (q or "").strip().lower()
    hits = []
    for j in jobs:
        if only_active and j["status"] != "active":
            continue
        if q and q not in j["company"].lower() and q not in j["title"].lower():
            continue
        hits.append(j)
        if len(hits) >= limit:
            break
    return hits


def get(key: str) -> dict | None:
    for j in load_index()["jobs"]:
        if j["key"] == key:
            return j
    return None


if __name__ == "__main__":
    p = build_index()
    print(f"[jobsource] {p['count']}건 색인 → {INDEX}")
