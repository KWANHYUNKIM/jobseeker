"""DB 저장 현황 — 8770 의 'DB 저장 현황' 칸(`/api/db`).

크롤러 현황은 '받았나'(파일)를 보고, 여기는 '정본 DB 에 들어갔나'를 본다. 둘은 다르다 —
공고는 키워드를 다 돈 뒤 통합 단계에서야 DB 에 들어가서, 수집은 끝났는데 뷰어 목록은
옛것인 시간이 생긴다(2026-10-18 따라잡기 회차: 수집 끝나고 DB 까지 2시간). 화면은 API 로
DB 를 읽으므로 사용자가 보는 것은 여기 숫자다.

표마다 '마지막으로 쓴 때'와 최근 24시간 신규를 낸다. DB 가 내려가 있으면 ok=false 와 이유만.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

_CACHE: dict = {"at": 0.0, "data": None}

# (정상 상한, 주의 상한) 시간 — 넘으면 멈춤
HOURLY = (3, 24)
DAILY = (30, 72)

SQL_SITES = """
select j.site,
       count(*)                                                        as total,
       count(*) filter (where s.status = 'active')                      as active,
       count(*) filter (where j.first_seen_at > now() - interval '24 hours') as new_24h,
       max(j.first_seen_at)                                            as last_new,
       max(j.last_seen_at)                                             as last_seen
from job j left join job_state s on s.job_id = j.id
group by j.site order by active desc
"""

SQL_RUNS = """
select started_at, ok, n_raw, n_upserted, n_new, coalesce(n_closed, 0), label
from crawl_run order by id desc limit 8
"""

SQL_TABLES = [
    ("project", "외주·프리 프로젝트", HOURLY, """
        select count(*), count(*) filter (where s.status = 'active'),
               count(*) filter (where p.first_seen_at > now() - interval '24 hours'), max(p.last_seen_at)
        from project p left join project_state s on s.project_id = p.id"""),
    ("post", "기술 블로그 글", DAILY, """
        select count(*), null, count(*) filter (where first_seen_at > now() - interval '24 hours'),
               max(last_seen_at) from post"""),
    ("job_embedding", "공고 임베딩(추천·검색)", HOURLY, """
        select count(*), null, count(*) filter (where embedded_at > now() - interval '24 hours'),
               max(embedded_at) from job_embedding"""),
    ("job_state", "마감 재확인", HOURLY, """
        select count(*), count(*) filter (where status = 'closed'),
               count(*) filter (where last_verified_at > now() - interval '24 hours'), max(last_verified_at)
        from job_state"""),
    ("hw_price_day", "부품 가격(일별)", DAILY, """
        select count(*), count(distinct part_id) filter (where day = (select max(day) from hw_price_day)),
               count(*) filter (where day >= current_date - 1), max(day)::timestamptz from hw_price_day"""),
]


def _age_hours(ts) -> float | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - ts).total_seconds() / 3600, 2)


def _state(age: float | None, limits: tuple[float, float]) -> str:
    if age is None:
        return "unknown"
    if age <= limits[0]:
        return "ok"
    return "warn" if age <= limits[1] else "stale"


def _iso(ts) -> str | None:
    return ts.isoformat(timespec="seconds") if ts else None


def summary() -> dict:
    if _CACHE["data"] is not None and time.time() - _CACHE["at"] < 30:
        return _CACHE["data"]
    try:
        from store.db.conn import cursor
        with cursor(autocommit=True) as cur:   # 읽기만 한다 — 행은 dict 로 온다
            rows = lambda: [tuple(r.values()) for r in cur.fetchall()]  # noqa: E731
            cur.execute(SQL_SITES)
            sites = []
            for site, total, active, new24, last_new, last_seen in rows():
                age = _age_hours(last_seen)
                sites.append({"site": site, "total": total, "active": active, "new_24h": new24,
                              "last_new": _iso(last_new), "last_seen": _iso(last_seen),
                              "age_hours": age, "state": _state(age, HOURLY)})
            cur.execute(SQL_RUNS)
            runs = [{"started_at": _iso(r[0]), "ok": r[1], "n_raw": r[2], "n_upserted": r[3],
                     "n_new": r[4], "n_closed": r[5], "label": r[6]} for r in rows()]
            tables = []
            for key, name, limits, sql in SQL_TABLES:
                try:
                    cur.execute(f"select * from ({sql}) t(total, sub, new24, last)")  # 같은 이름 열이 dict 에서 겹치지 않게
                    total, sub, new24, last = rows()[0]
                except Exception as e:  # 마이그레이션이 안 된 표 하나가 칸 전체를 죽이지 않게
                    tables.append({"key": key, "name": name, "error": str(e).splitlines()[0][:160],
                                   "state": "error"})
                    continue
                age = _age_hours(last)
                tables.append({"key": key, "name": name, "total": total, "sub": sub, "new_24h": new24,
                               "last": _iso(last), "age_hours": age, "state": _state(age, limits)})
    except Exception as e:
        data = {"ok": False, "error": str(e).splitlines()[0][:200],
                "generated_at": datetime.now().isoformat(timespec="seconds")}
        _CACHE.update(at=time.time(), data=data)
        return data

    last_run = runs[0] if runs else {}
    data = {
        "ok": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "jobs": {
            "total": sum(s["total"] for s in sites),
            "active": sum(s["active"] for s in sites),
            "new_24h": sum(s["new_24h"] for s in sites),
            "last_write": last_run.get("started_at"),
            "last_write_age_hours": _age_hours(datetime.fromisoformat(last_run["started_at"])) if last_run else None,
        },
        "sites": sites, "runs": runs, "tables": tables,
    }
    _CACHE.update(at=time.time(), data=data)
    return data


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    print(json.dumps(summary(), ensure_ascii=False, indent=1))
