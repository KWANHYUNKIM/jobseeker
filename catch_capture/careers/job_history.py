"""공고 이력 — 경험담을 '그때 공고'와 맞추려고 예전 공고를 쌓는다.

    python -m careers.job_history backfill     # git 이력의 all_jobs_enriched.json 버전 전부에서 쌓기(한 번)
    python -m careers.job_history update       # 지금 공고를 더한다(cycle 이 회차마다 부른다)

var/careers/job_history.json : {"<site>-<pid>": {공고 필드…, "seen_first": 날짜, "seen_last": 날짜}}
공고 내용은 마지막으로 본 판을 남기고, 처음·마지막 본 날만 넓힌다. 등록일(posted_date)이 있으면 그걸 시기로 쓴다.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime

from careers import store

HIST = store.DIR / "job_history.json"
REPO = store.JOBS.parents[2]                       # jobseeker/
REL = "jd-viewer/public/all_jobs_enriched.json"
KEEP = ("company", "title", "career", "tech_stack", "qualifications", "preferences", "main_tasks",
        "site", "pid", "url", "posted_date", "first_seen_at", "deadline_date", "location")


def _key(j: dict) -> str | None:
    if j.get("site") and j.get("pid"):
        return f"{j['site']}-{j['pid']}"
    return j.get("url")


def _merge(h: dict, jobs: list[dict], day: str) -> int:
    new = 0
    for j in jobs if isinstance(jobs, list) else []:
        k = _key(j)
        if not k:
            continue
        rec = {f: j.get(f) for f in KEEP}
        first = min(x for x in (day, (j.get("posted_date") or "")[:10], (j.get("first_seen_at") or "")[:10]) if x)
        cur = h.get(k)
        if cur is None:
            new += 1
            h[k] = rec | {"seen_first": first, "seen_last": day}
        else:
            cur.update({f: v for f, v in rec.items() if v})        # 내용은 최신 판으로
            cur["seen_first"] = min(cur["seen_first"], first)
            cur["seen_last"] = max(cur["seen_last"], day)
    return new


def backfill() -> None:
    h = store.load_json(HIST, {})
    log = subprocess.run(["git", "-C", str(REPO), "log", "--all", "--reverse", "--format=%H %ad", "--date=short", "--", REL],
                         capture_output=True, text=True, check=True).stdout.split("\n")
    revs = [l.split() for l in log if l.strip()]
    print(f"git 판 {len(revs)}개", flush=True)
    for i, (sha, day) in enumerate(revs, 1):
        p = subprocess.run(["git", "-C", str(REPO), "show", f"{sha}:{REL}"], capture_output=True)
        if p.returncode:
            continue
        try:
            jobs = json.loads(p.stdout.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        n = _merge(h, jobs, day)
        if i % 25 == 0 or n:
            print(f"  {i}/{len(revs)} {day}: 공고 {len(jobs) if isinstance(jobs, list) else '?'} · 새로 {n} · 누적 {len(h)}", flush=True)
    store.save_json(HIST, h)
    print(f"공고 이력 {len(h)}건 → {HIST}", flush=True)


def update() -> int:
    h = store.load_json(HIST, {})
    n = _merge(h, store.load_json(store.JOBS, []), datetime.now().strftime("%Y-%m-%d"))
    store.save_json(HIST, h)
    return n


def load() -> list[dict]:
    """매칭용 — 이력 전부(없으면 지금 공고)."""
    h = store.load_json(HIST, {})
    return list(h.values()) or store.load_json(store.JOBS, [])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["backfill", "update"])
    a = ap.parse_args()
    backfill() if a.cmd == "backfill" else print(f"새 공고 {update()}건")
