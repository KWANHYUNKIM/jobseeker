"""본문이 비거나 잘려 저장된 모집중 공고를 다시 받아 채운다 — 잡코리아·사람인.

공고 상세에 "이 공고는 해당 정보가 비어있습니다" 가 뜨던 공고 중 본문 자체가 짧은 것들:
  · 잡코리아: 본문 영역을 정규식으로 자르다 회사가 꾸민 표 모양 공고가 중간에서 잘렸다(fetch_jd 고침).
  · 사람인: 포스터 한 장 + 짧은 글(유의사항·키워드)이라 '이미지 공고' 판정에서 빠져 OCR 을 안 돌렸다
    (is_image_only 고침).
고친 규칙으로 다시 받아, 이미지 공고면 OCR 을 돌린다. **누적본 jobs.json 과 정본 DB 를 둘 다** 고친다 —
aggregate 가 회차마다 jobs.json 을 DB 로 다시 쓰므로 DB 만 고치면 다음 회차에 되돌아간다.
섹션은 빈 칸만 채운다. 요청 사이 1.5초(지터)를 둔다.

    python -m crawlers.refetch_bodies jobkorea
    python -m crawlers.refetch_bodies saramin --limit 300
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import json
import time
from pathlib import Path

from crawlers.jobs_common import (
    OCR_AVAILABLE, build_jd_sections, extract_img_urls, is_image_only, jitter, ocr_images, save_jobs_json,
)

SECTIONS = ("main_tasks", "qualifications", "preferences", "benefits")


def _fetcher(site: str):
    if site == "jobkorea":
        from crawlers.crawl_jobkorea import fetch_jd
    elif site == "saramin":
        from crawlers.crawl_saramin import fetch_jd
    else:
        raise SystemExit(f"지원하지 않는 사이트: {site}")
    return fetch_jd


def run(site: str, min_len: int = 400, limit: int = 1000, use_ocr: bool = True) -> dict:
    from store.db.conn import cursor
    fetch_jd = _fetcher(site)
    with cursor(autocommit=True) as cur:
        cur.execute("""SELECT j.id, j.pid, j.url, coalesce(j.full_jd,'') AS jd
                         FROM job j JOIN job_state s ON s.job_id = j.id AND s.status = 'active'
                        WHERE j.site = %s AND length(coalesce(j.full_jd,'')) < %s
                          AND coalesce(j.main_tasks,'') = '' AND coalesce(j.qualifications,'') = ''
                          AND coalesce(j.preferences,'') = ''
                        ORDER BY j.first_seen_at DESC LIMIT %s""", (site, min_len, limit))
        rows = cur.fetchall()
    base = Path(__file__).resolve().parent.parent / "screenshots"
    files = {f: json.loads(f.read_text(encoding="utf-8")) for f in base.glob(f"{site}_*/jobs.json")}
    fixed = ocr_n = 0
    dirty: set[Path] = set()
    for i, r in enumerate(rows, 1):
        try:
            html, text = fetch_jd(r["pid"], referer=r["url"])
        except Exception as e:                                  # noqa: BLE001
            print(f"  [{i}/{len(rows)}] {r['pid']} 실패: {e}", flush=True)
            time.sleep(jitter(1500) / 1000)
            continue
        full = text or ""
        if use_ocr and OCR_AVAILABLE and is_image_only(html, text):
            ocr = ocr_images(extract_img_urls(html), referer=r["url"])
            if ocr:
                full = (full + "\n\n[이미지 OCR]\n" + ocr).strip()
                ocr_n += 1
        time.sleep(jitter(1500) / 1000)
        parts = build_jd_sections(None, full)
        new = {k: parts[k] for k in SECTIONS if parts.get(k)}
        if len(full) <= len(r["jd"]) + 50 and not new:
            continue
        with cursor() as cur:
            if len(full) > len(r["jd"]):
                cur.execute("UPDATE job SET full_jd = %s WHERE id = %s", (full, r["id"]))
            for k, v in new.items():
                cur.execute(f"UPDATE job SET {k} = %s WHERE id = %s AND coalesce({k}, '') = ''", (v, r["id"]))
        for f, jobs in files.items():
            for j in jobs:
                if str(j.get("pid") or j.get("gno") or j.get("rec_idx")) == str(r["pid"]):
                    if len(full) > len(j.get("full_jd") or ""):
                        j["full_jd"] = full
                    for k, v in new.items():
                        if not j.get(k):
                            j[k] = v
                    dirty.add(f)
        fixed += 1
        print(f"  [{i}/{len(rows)}] {r['pid']} {len(r['jd'])} → {len(full)}자 {sorted(new)}", flush=True)
    for f in dirty:
        save_jobs_json(f.parent, files[f])
    print(f"[{site}] 빈 본문 {len(rows)}건 중 {fixed}건 채움(OCR {ocr_n}) · jobs.json {len(dirty)}개 갱신", flush=True)
    return {"checked": len(rows), "fixed": fixed, "ocr": ocr_n}


if __name__ == "__main__":
    a = _sys.argv[1:]
    site = a[0] if a else "saramin"
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 1000
    run(site, limit=limit, use_ocr="--no-ocr" not in a)
