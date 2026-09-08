"""공고 목록을 **어디서 읽고** 그중 무엇을 쓸지 정하는 공용 모듈.

## 어디서 읽는가 — `load_jobs()`

정본 DB(`v_job`)에서 바로 읽는다. 지금까지 빌더들은 저마다
`json.loads(all_jobs_enriched.json)` 으로 127MB 를 파싱했는데, 그 파일 자체가
`store.export` 가 같은 DB 에서 뽑아 놓은 것이었다 — DB → JSON → 다시 파싱.
빌더 12개가 각자 그 짓을 했다.

DB 에서 읽으면 부수적으로 두 가지가 맞는다:

- **status·dday 가 읽는 시점 기준이다.** 파일은 export 가 돈 시점에 박제된다.
  export 와 빌더 사이에 자정이 지나면 어제 마감된 공고가 모집중으로 집계된다.
- **파일이 없거나 낡아도 된다.** export 가 실패한 사이클에서도 빌더는 최신을 본다.

DB 가 꺼져 있으면 파일로 물러선다 — 크롤 서버가 DB 없이도 돌아야 한다.

## 무엇을 쓰는가 — `active_only()`

`all_jobs_enriched.json` 은 모집중과 마감을 **함께** 담는다. 마감을 파일에서
빼버리면 색인·유사공고·과거 조회가 통째로 사라지기 때문이다. 대신 읽는 쪽이 목적에
맞게 고른다.

- 수요 분석(무엇을 요구하는가, 어떤 스택을 쓰는가)은 `active_only()` 를 쓴다.
  두 달 전에 끝난 공고를 현재 수요로 세면 트렌드가 과거에 눌린다.
- 색인·검색·재공고 추적처럼 '있었던 일'을 다루는 쪽은 전체를 그대로 쓴다.

status 가 없는 예전 파일도 그냥 통과시킨다(빈 결과보다 낫다).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ENRICHED = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"


def load_jobs(fallback: Path | None = None, *, quiet: bool = False) -> list[dict]:
    """정본 DB 의 공고 전량(모집중 + 마감). 못 읽으면 JSON 파일로 물러선다.

    돌려주는 dict 는 `store.export` 가 JSON 에 쓰던 것과 **같은 모양**이다 —
    빌더는 출처가 바뀐 줄 모른다.
    """
    sys.path.insert(0, str(ROOT / "catch_capture"))
    try:
        from store.export import fetch_jobs
        jobs = fetch_jobs()
        if jobs:
            if not quiet:
                print(f"  [입력] 정본 DB v_job {len(jobs):,}건")
            return jobs
        if not quiet:
            print("  [입력] DB 가 비어 있습니다 — 파일로 물러섭니다")
    except Exception as e:                                          # noqa: BLE001
        if not quiet:
            print(f"  [입력] DB 를 못 읽어 파일로 물러섭니다: {e}")

    path = fallback or ENRICHED
    if not path.exists():
        raise SystemExit(f"[입력] DB 에도 파일에도 공고가 없습니다: {path}")
    jobs = json.loads(path.read_text(encoding="utf-8"))
    if not quiet:
        print(f"  [입력] {path.name} {len(jobs):,}건")
    return jobs


def active_only(jobs: list[dict]) -> list[dict]:
    if not jobs:
        return jobs
    if not any("status" in j for j in jobs[:50]):
        return jobs                      # status 이전 포맷 — 거를 근거가 없다
    return [j for j in jobs if (j.get("status") or "active") != "closed"]


def load_posts(fallback: Path | None = None, *, quiet: bool = False) -> list[dict]:
    """기술 블로그 글 전량. 정본 DB 의 `post` 를 읽고, 못 읽으면 tech_blogs.json.

    돌려주는 dict 는 `tech_blogs.json` 의 posts 항목과 같은 키를 쓴다 —
    company / country / title / url / published / published_ts / summary /
    tags / tech_stack / categories / lang. 읽는 쪽은 출처를 몰라도 된다.

    `published_ts` 는 저장하지 않고 `published_on` 에서 만든다. 파일 쪽 값도
    날짜 단위였고(그날 00:00 UTC), 같은 값을 두 군데 두면 어긋날 자리만 는다.
    """
    sys.path.insert(0, str(ROOT / "catch_capture"))
    try:
        from store import conn as store_conn
        with store_conn.cursor(autocommit=True) as cur:
            cur.execute(
                """SELECT p.url, p.title, p.blog_name, p.published_on, p.summary,
                          p.country, p.lang, p.tags, p.tech_stack, p.categories,
                          p.content_id
                     FROM post p ORDER BY p.published_on DESC NULLS LAST, p.id"""
            )
            rows = cur.fetchall()
        if rows:
            from datetime import datetime, timezone
            out = []
            for r in rows:
                d = r["published_on"]
                out.append({
                    "company": r["blog_name"] or "",
                    "country": r["country"] or "",
                    "lang": r["lang"] or "",
                    "title": r["title"],
                    "url": r["url"],
                    "summary": r["summary"] or "",
                    "published": d.isoformat() if d else "",
                    "published_ts": (datetime(d.year, d.month, d.day,
                                              tzinfo=timezone.utc).timestamp() if d else 0),
                    "tags": list(r["tags"] or []),
                    "tech_stack": list(r["tech_stack"] or []),
                    "categories": list(r["categories"] or []),
                    "content_id": r["content_id"] or "",
                })
            if not quiet:
                print(f"  [입력] 정본 DB post {len(out):,}편")
            return out
        if not quiet:
            print("  [입력] DB 에 블로그 글이 없습니다 — 파일로 물러섭니다")
    except Exception as e:                                          # noqa: BLE001
        if not quiet:
            print(f"  [입력] DB 를 못 읽어 파일로 물러섭니다: {e}")

    path = fallback or (ROOT / "jd-viewer" / "public" / "tech_blogs.json")
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    posts = data.get("posts") if isinstance(data, dict) else data
    if not quiet:
        print(f"  [입력] {path.name} {len(posts or []):,}편")
    return posts or []
