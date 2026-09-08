"""파일로 쌓이던 시계열 원장 → 정본 DB.

`trends_history.jsonl` 과 `job_history.jsonl` 은 다른 집계와 성질이 다르다.
공고 집계는 언제든 `job` 을 다시 훑으면 되지만, **지난 일은 다시 계산할 수 없다** —
3개월 전 그날 Java 가 몇 건이었는지는 그때 세어 둔 것 말고는 복원할 길이 없다.
그런 것이 파일 하나에 얹혀 있었다(로컬 54줄 / 운영 23줄 — 두 머신이 서로 다른
시계열을 들고 있었다는 뜻이다). DB 로 옮긴다.

여기가 담는 것:

  trend_day / trend_metric   trends_history.jsonl      → build_trends.py 가 읽는다
  job_version                job_history.jsonl         → build_reposts.py 가 읽고 쓴다
  engagement_event           engagement/events.jsonl   → engagement.score 가 읽는다

읽기 함수(`load_trend_days`, `load_job_versions`)는 **파일이 주던 것과 똑같은
모양**을 돌려준다. 빌더의 집계 로직(급상승 창 계산, 재공고 판정)은 손대지 않는다 —
거기가 이 시스템에서 가장 미묘한 부분이고, 이번에 바꾸는 것은 입력의 출처뿐이다.

사용:
    python -m store.ledgers seed            # JSONL → DB (멱등)
    python -m store.ledgers seed --trends   # 한쪽만
    python -m store.ledgers status          # 무엇이 얼마나 들어와 있나
"""
from __future__ import annotations

import argparse
import json
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from store import conn as store_conn  # noqa: E402

BASE = _Path(__file__).resolve().parent.parent
TRENDS_JSONL = BASE / "trends_history.jsonl"
HISTORY_JSONL = BASE / "job_history.jsonl"
EVENTS_JSONL = BASE / "engagement" / "events.jsonl"
# 64MB 를 넘으면 collect 가 밀어내는 옛 파일. 아무도 안 읽고 있었다 — 씨앗으로는 쓴다.
EVENTS_ROTATED = BASE / "engagement" / "events.jsonl.1"

KINDS = ("session", "view", "click", "dwell", "search", "filter")


# ── 공통 ────────────────────────────────────────────────────────────
def _pairs(v) -> dict[str, int]:
    """집계 필드는 {name: n} 과 [[name, n], ...] 두 모양으로 쓰였다.

    적재 시점의 직렬화 방식이 달라 히스토리 안에 섞여 있다. 한 모양으로 가정하면
    오래된 줄에서 조용히 빈 집계가 나온다 — build_trends.py 와 같은 판단이다.
    """
    if isinstance(v, dict):
        return {str(k): int(n) for k, n in v.items()}
    if isinstance(v, list):
        out: dict[str, int] = {}
        for item in v:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                out[str(item[0])] = int(item[1])
        return out
    return {}


def _read_jsonl(path: _Path) -> list[dict]:
    """한 줄 = 한 레코드. 깨진 줄은 건너뛴다.

    split("\\n") 이지 splitlines() 가 아니다. splitlines() 는 U+2028/U+2029/U+0085
    에서도 자르는데 json.dumps(ensure_ascii=False) 는 그 문자들을 그대로 흘려보낸다.
    크롤한 JD 본문에 섞여 있으면 한 레코드가 두 조각으로 쪼개진다.
    """
    if not path.exists():
        return []
    out, bad = [], 0
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            bad += 1
    if bad:
        print(f"  [{path.name}] 파싱 실패 {bad}줄 — 건너뜀")
    return out


# ── 트렌드 시계열 ───────────────────────────────────────────────────
def _metric_rows(snap: dict) -> list[tuple]:
    """스냅샷 한 장 → trend_metric 행들. (axis, role, name, n)"""
    day, kw = snap["date"], snap.get("keyword") or ""
    rows: list[tuple] = []

    def add(axis: str, role: str, pairs: dict[str, int]) -> None:
        for name, n in pairs.items():
            rows.append((day, kw, axis, role, name, n))

    add("tech", "", _pairs(snap.get("tech_overall")))
    add("concept", "", _pairs(snap.get("concepts_overall")))
    add("band", "", _pairs(snap.get("bands")))
    add("role", "", _pairs(snap.get("by_role")))

    # 직군별 분해. 전체 집계만 보면 안 보이는 것을 잡는다 — Kubernetes 비중이
    # 내려가도 그게 수요 감소인지 백엔드 공고 비중 감소인지는 직군을 갈라야 안다.
    for role, entry in (snap.get("roles") or {}).items():
        entry = entry or {}
        add("tech", role, _pairs(entry.get("tech")))
        add("concept", role, _pairs(entry.get("concepts")))
        add("band", role, _pairs(entry.get("bands")))

    # 같은 (axis, role, name) 이 두 번 나오면 뒤엣것이 이긴다. PK 충돌로 배치가
    # 통째로 죽는 것보다 낫고, 원본에서 그런 일은 표기 정규화 전 데이터에서만 난다.
    dedup: dict[tuple, tuple] = {}
    for r in rows:
        dedup[(r[0], r[1], r[2], r[3], r[4])] = r
    return list(dedup.values())


def write_trend_day(cur, snap: dict) -> int:
    """스냅샷 한 장을 DB 에. 같은 (day, keyword) 는 통째로 갈아 끼운다.

    --force 재기록이 그날 항목을 교체하는 파일 쪽 동작과 같게 맞춘다. metric 은
    FK ON DELETE CASCADE 로 함께 지워지므로 지운 뒤 다시 넣으면 된다.
    """
    if not snap.get("date"):
        return 0
    day, kw = snap["date"], snap.get("keyword") or ""
    cur.execute(
        """INSERT INTO trend_day (day, keyword, total, at) VALUES (%s,%s,%s,%s)
           ON CONFLICT (day, keyword) DO UPDATE SET
               total = EXCLUDED.total, at = EXCLUDED.at""",
        (day, kw, int(snap.get("total") or 0), snap.get("ts") or None),
    )
    cur.execute("DELETE FROM trend_metric WHERE day = %s AND keyword = %s", (day, kw))
    rows = _metric_rows(snap)
    if rows:
        cur.executemany(
            "INSERT INTO trend_metric (day, keyword, axis, role, name, n) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            rows,
        )
    return len(rows)


def load_trend_days() -> list[dict]:
    """DB → build_trends.py 가 받던 히스토리 레코드 모양 그대로.

    돌려주는 각 항목은 파일 한 줄과 같은 키를 가진다: date/keyword/total/
    tech_overall/concepts_overall/bands/by_role/roles. 그래야 빌더 본문이
    한 줄도 안 바뀐다.
    """
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute("SELECT day, keyword, total FROM trend_day ORDER BY keyword, day")
        days = cur.fetchall()
        if not days:
            return []
        cur.execute(
            "SELECT day, keyword, axis::text AS axis, role, name, n FROM trend_metric"
        )
        metrics = cur.fetchall()

    out: dict[tuple, dict] = {}
    for d in days:
        out[(d["keyword"], d["day"])] = {
            "date": d["day"].isoformat(),
            "keyword": d["keyword"],
            "total": d["total"],
            "tech_overall": {}, "concepts_overall": {}, "bands": {}, "by_role": {},
            "roles": {},
        }

    # 전체 축은 그대로, 직군별 축은 roles[직군] 아래로 되돌린다.
    AXIS_KEY = {"tech": "tech_overall", "concept": "concepts_overall",
                "band": "bands", "role": "by_role"}
    ROLE_KEY = {"tech": "tech", "concept": "concepts", "band": "bands"}
    for m in metrics:
        rec = out.get((m["keyword"], m["day"]))
        if rec is None:
            continue
        if not m["role"]:
            rec[AXIS_KEY[m["axis"]]][m["name"]] = m["n"]
        else:
            slot = rec["roles"].setdefault(m["role"], {"count": 0})
            slot.setdefault(ROLE_KEY[m["axis"]], {})[m["name"]] = m["n"]

    # roles[직군].count 는 by_role 이 들고 있다 — 같은 숫자를 두 번 저장하지 않는다.
    for rec in out.values():
        for role, cnt in rec["by_role"].items():
            rec["roles"].setdefault(role, {})["count"] = cnt

    return [out[k] for k in sorted(out, key=lambda k: (k[0], k[1]))]


def seed_trends(*paths: _Path) -> tuple[int, int]:
    """trends_history.jsonl → DB. 이미 있는 날짜는 갈아 끼운다(멱등).

    여러 파일을 받으면 순서대로 넣는다 — 같은 (day, keyword) 가 겹치면 뒤에
    준 파일이 이긴다. 날짜 단위 스냅샷이라 합치는 데 순서 문제가 없다.
    """
    rows: list[dict] = []
    for path in (paths or (TRENDS_JSONL,)):
        rows.extend(_read_jsonl(path))
    n_days = n_metrics = 0
    with store_conn.connect() as db:
        with db.cursor() as cur:
            for snap in rows:
                if not snap.get("date") or int(snap.get("total") or 0) <= 0:
                    continue        # total 0 인 날은 크롤이 실패한 날이다
                n_metrics += write_trend_day(cur, snap)
                n_days += 1
        db.commit()
    return n_days, n_metrics


# ── 공고 판본 이력 ──────────────────────────────────────────────────
def load_job_versions() -> dict[str, list[dict]]:
    """DB → build_reposts.py 의 `hist` 모양 그대로: {key: [레코드, ...]}.

    id 순서가 곧 append 순서이고, 빌더는 versions[-1] 을 '최신 판' 으로 읽는다.
    """
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute("SELECT job_key, hash, seen, data FROM job_version ORDER BY id")
        rows = cur.fetchall()
    hist: dict[str, list[dict]] = {}
    for r in rows:
        hist.setdefault(r["job_key"], []).append(
            {"key": r["job_key"], "hash": r["hash"], "seen": r["seen"], "data": r["data"]}
        )
    return hist


def append_job_versions(records: list[dict]) -> int:
    """새 판본을 append. (job_key, hash) 가 이미 있으면 조용히 버린다.

    빌더가 파이썬으로 지키던 "그 자리의 모든 기록과 비교" 규칙을 UNIQUE 제약이
    대신 지킨다. 빌더가 잊어도 같은 판이 두 번 쌓이지 않는다.
    """
    if not records:
        return 0
    with store_conn.connect() as db:
        with db.cursor() as cur:
            cur.executemany(
                """INSERT INTO job_version (job_key, hash, seen, data)
                   VALUES (%s,%s,%s,%s) ON CONFLICT (job_key, hash) DO NOTHING""",
                [(r["key"], r["hash"], r["seen"], json.dumps(r["data"], ensure_ascii=False))
                 for r in records],
            )
        db.commit()
    return len(records)


def seed_history(*paths: _Path) -> tuple[int, int]:
    """job_history.jsonl → DB. 여러 파일을 받으면 시간순으로 합친다.

    **왜 정렬하는가.** id 순서가 곧 판본 순서이고 빌더는 versions[-1] 을 '최신 판'
    으로 읽는다. 한 파일만 넣을 때는 파일 순서가 곧 append 순서라 그대로면 되지만,
    두 머신의 원장을 합칠 때 파일을 이어 붙이면 뒷 파일의 옛 판이 앞 파일의 새 판
    뒤에 놓인다 — 그러면 몇 달 전 판이 '최신' 이 되어 재공고 판정이 뒤집힌다.
    seen(YYYY-MM-DD) 으로 안정 정렬하고, 'bootstrap'(아카이브에서 온 옛 판)을
    맨 앞에 둔다. 같은 날짜 안에서는 파일 순서가 그대로 유지된다.

    파일에는 (key, hash) 가 중복된 줄이 있을 수 있다 — '직전 판만 비교' 하던 시절
    A→B→A 를 오가며 쌓인 것들이다. UNIQUE 가 먼저 들어온 쪽을 남긴다.
    """
    rows: list[dict] = []
    for path in (paths or (HISTORY_JSONL,)):
        rows.extend(_read_jsonl(path))
    ok = [r for r in rows if r.get("key") and r.get("hash")]
    if len(paths) > 1:
        ok.sort(key=lambda r: ((r.get("seen") or "") != "bootstrap", r.get("seen") or ""))
    with store_conn.connect() as db:
        with db.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM job_version")
            before = cur.fetchone()["n"]
            # 22MB · 3만 줄이라 한 번에 보내면 메모리를 크게 먹는다. 8GB 맥이다.
            for i in range(0, len(ok), 2000):
                chunk = ok[i:i + 2000]
                cur.executemany(
                    """INSERT INTO job_version (job_key, hash, seen, data)
                       VALUES (%s,%s,%s,%s) ON CONFLICT (job_key, hash) DO NOTHING""",
                    [(r["key"], r["hash"], r.get("seen") or "bootstrap",
                      json.dumps(r.get("data") or {}, ensure_ascii=False)) for r in chunk],
                )
            cur.execute("SELECT count(*) AS n FROM job_version")
            after = cur.fetchone()["n"]
        db.commit()
    return len(ok), after - before


# ── 행동 기록 ───────────────────────────────────────────────────────
def _event_rows(rows: list[dict]) -> list[tuple]:
    """파일 한 줄 → engagement_event 행. 알 수 없는 종류·시각은 버린다."""
    from datetime import datetime, timezone
    out = []
    for r in rows:
        kind = r.get("t")
        ts = r.get("ts")
        if kind not in KINDS or not isinstance(ts, (int, float)) or ts <= 0:
            continue
        dwell = r.get("s") if kind == "dwell" else None
        try:
            dwell = int(dwell) if dwell is not None else None
        except (TypeError, ValueError):
            dwell = None
        out.append((
            str(r.get("sid") or "?"), kind,
            datetime.fromtimestamp(float(ts), tz=timezone.utc),
            (str(r["k"])[:400] if r.get("k") else None),
            (str(r["from"])[:400] if r.get("from") else None),
            dwell,
        ))
    return out


def append_events(rows: list[dict]) -> int:
    """새 사건을 DB 에. `collect.append` 가 파일에 적은 뒤 부른다.

    중복 방지 제약을 걸지 않는다 — 같은 세션이 같은 초에 같은 항목을 두 번 볼 수
    있고(스크롤로 되돌아오는 경우), 그것도 진짜 행동이다. 대신 seed 는 표에 이미
    무언가 있으면 넣지 않는다(아래).
    """
    vals = _event_rows(rows)
    if not vals:
        return 0
    with store_conn.connect() as db:
        with db.cursor() as cur:
            cur.executemany(
                "INSERT INTO engagement_event (sid, kind, at, item, source, dwell_s) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                vals,
            )
        db.commit()
    return len(vals)


def load_events(days: int) -> list[dict]:
    """DB → engagement.score 가 받던 레코드 모양 그대로(t/ts/sid/k/from/s)."""
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute(
            """SELECT sid, kind::text AS kind, at, item, source, dwell_s
                 FROM engagement_event
                WHERE at >= now() - make_interval(days => %s)
                ORDER BY at""",
            (days,),
        )
        rows = cur.fetchall()
    out = []
    for r in rows:
        e = {"sid": r["sid"], "t": r["kind"], "ts": r["at"].timestamp()}
        if r["item"]:
            e["k"] = r["item"]
        if r["source"]:
            e["from"] = r["source"]
        if r["dwell_s"] is not None:
            e["s"] = r["dwell_s"]
        out.append(e)
    return out


def seed_events(*paths: _Path) -> tuple[int, int]:
    """events.jsonl(+회전된 .1) → DB.

    **이미 행이 있으면 넣지 않는다.** 이 표에는 중복 방지 제약이 없어서 — 같은
    세션이 같은 초에 같은 항목을 두 번 보는 것도 진짜 행동이므로 — 두 번 돌리면
    그대로 두 배가 된다. 씨앗 뿌리기는 한 번만 하는 일이다.
    """
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute("SELECT count(*) AS n FROM engagement_event")
        if cur.fetchone()["n"]:
            print("  [events] 이미 들어 있다 — 건너뜀 (두 번 넣으면 그대로 두 배가 된다)")
            return 0, 0
    rows: list[dict] = []
    for path in (paths or (EVENTS_ROTATED, EVENTS_JSONL)):
        if path.exists():
            rows.extend(_read_jsonl(path))
    return len(rows), append_events(rows)


# ── CLI ─────────────────────────────────────────────────────────────
def _status() -> None:
    with store_conn.cursor(autocommit=True) as cur:
        cur.execute("""SELECT keyword, count(*) n, min(day)::text lo, max(day)::text hi,
                              max(total) peak FROM trend_day GROUP BY keyword ORDER BY n DESC""")
        rows = cur.fetchall()
        print("트렌드 시계열(trend_day)")
        for r in rows or []:
            print(f"    {r['keyword']:<10} {r['n']:>4}일  {r['lo']} ~ {r['hi']}  최대 {r['peak']:,}건")
        if not rows:
            print("    (비어 있음 — python -m store.ledgers seed --trends)")
        cur.execute("SELECT count(*) n FROM trend_metric")
        print(f"    지표 {cur.fetchone()['n']:,}행")

        cur.execute("SELECT count(*) n, count(DISTINCT job_key) k FROM job_version")
        r = cur.fetchone()
        print(f"\n공고 판본(job_version): {r['n']:,}판 / 자리 {r['k']:,}곳")
        cur.execute("""SELECT count(*) n FROM (
                         SELECT job_key FROM job_version GROUP BY job_key HAVING count(*) > 1
                       ) t""")
        print(f"    판본이 둘 이상인 자리(= 재공고 후보): {cur.fetchone()['n']:,}곳")

        cur.execute("""SELECT count(*) n, count(DISTINCT sid) s,
                              min(at)::date::text lo, max(at)::date::text hi
                         FROM engagement_event""")
        r = cur.fetchone()
        print(f"\n행동 기록(engagement_event): {r['n']:,}건 / 세션 {r['s']:,}개"
              + (f"  {r['lo']} ~ {r['hi']}" if r["n"] else " (비어 있음)"))


def main() -> int:
    ap = argparse.ArgumentParser(description="파일 원장 → 정본 DB")
    ap.add_argument("cmd", choices=["seed", "status"])
    ap.add_argument("--trends", action="store_true", help="트렌드만")
    ap.add_argument("--history", action="store_true", help="공고 판본만")
    ap.add_argument("--events", action="store_true", help="행동 기록만")
    ap.add_argument("--also", action="append", default=[], metavar="JSONL",
                    help="다른 머신에서 가져온 원장 파일을 함께 넣는다 (여러 번 가능)")
    args = ap.parse_args()

    extra = [_Path(x) for x in args.also]
    for x in extra:
        if not x.exists():
            print(f"[중단] 없는 파일: {x}")
            return 2

    if args.cmd == "status":
        _status()
        return 0

    both = not (args.trends or args.history or args.events)
    if args.trends or both:
        srcs = [TRENDS_JSONL] + [x for x in extra if "trend" in x.name]
        d, m = seed_trends(*srcs)
        print(f"트렌드: {d}일 · 지표 {m:,}행  ← {', '.join(x.name for x in srcs)}")
    if args.history or both:
        srcs = [HISTORY_JSONL] + [x for x in extra if "trend" not in x.name]
        n, added = seed_history(*srcs)
        print(f"공고 판본: 읽은 {n:,}줄 중 새로 {added:,}판  ← {', '.join(x.name for x in srcs)}")
    if args.events or both:
        n, added = seed_events()
        print(f"행동 기록: 읽은 {n:,}줄 중 {added:,}건 적재  ← events.jsonl(+회전본)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
