"""한 회차 = 검색어 대기열에서 한 조각 수집 → 새 글 추출 → 보고서 다시 굽기.

  python -m careers.cycle                 # 기본: 검색어 60개
  python -m careers.cycle --queries 120
  python -m careers.cycle --add "SI 탈출 후기" "네카라쿠배 합격"   # 검색어를 대기열 앞에 더한다

검색어 대기열(`var/careers/queue.json`)은 일반 검색어 + 공고 있는 회사 × (합격·입사·이직)로 채우고,
루프 에이전트가 보고서의 빈칸(후기 0건인 회사, 얇은 직무·전환)을 보고 새 검색어를 `--add` 로 넣는다.
한 번 돈 검색어는 `done` 에 남고, 대기열이 비면 처음부터 다시 돈다(새 글은 seen 으로 걸러진다).
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from datetime import datetime, timezone

from careers import collect, extract, github_orgs, report, store

QUEUE = store.DIR / "queue.json"
BACKLOG_MAX = 150        # 이보다 밀려 있으면 수집을 쉬고 추출만 한다
EXTRACT_PER_RUN = 400    # 한 회차에 구조화하는 최대 글 수(5070 Ti 로컬 모델)


_LEGAL = re.compile(r"\(주\)|\(유\)|\(사\)|주식회사|유한회사|㈜|\b(?:inc|corp|corporation|co\.?,?\s*ltd|ltd)\b\.?", re.I)


def _query_name(name: str) -> str:
    """검색어용 회사 이름 — velog 는 '(주)티빙 합격' 에 0건을 준다. 법인격만 지우고 띄어쓰기는 둔다."""
    s = _LEGAL.sub(" ", unicodedata.normalize("NFKC", name))
    return re.sub(r"\s+", " ", s).strip(" ,.")


def _fill(q: dict) -> None:
    q["pending"] = list(dict.fromkeys(_query_name(k) for k in q["pending"]))   # 예전에 '(주)…' 로 넣은 것도 고친다
    have = set(q["pending"]) | set(q["done"])
    new_generic = [k for k in collect.GENERIC if k not in have]          # 새로 넣은 일반 검색어는 줄 맨 앞
    per_co = [_query_name(f"{c} {s}") for c in store.companies() for s in collect.PER_COMPANY]
    per_co = list(dict.fromkeys(per_co))
    q["pending"] = new_generic + q["pending"] + [k for k in per_co if k not in have]
    if not q["pending"]:                       # 한 바퀴 다 돌았다 → 새 글을 찾아 다시 돈다
        q["pending"], q["done"] = q["done"], []
        q["rounds"] = q.get("rounds", 0) + 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", type=int, default=60)
    ap.add_argument("--add", nargs="*", default=[])
    ap.add_argument("--no-extract", action="store_true")
    ap.add_argument("--forever", action="store_true", help="끝나면 --sleep 초 쉬고 다시(Ctrl+C 로 멈춘다)")
    ap.add_argument("--sleep", type=int, default=60)
    a = ap.parse_args()
    if a.forever:
        import time
        n = 0
        while True:
            n += 1
            print(f"=== 회차 {n} {datetime.now().isoformat(timespec='seconds')}", flush=True)
            try:
                once(a)
            except Exception as e:  # noqa: BLE001 — 한 회차가 깨져도 다음 회차는 돈다
                print(f"  ! 회차 실패: {e}", flush=True)
            time.sleep(a.sleep)
    once(a)


IG_EVERY = 3600           # 인스타는 계정 보호로 1시간에 한 번, 40개만
IG_LAST = store.DIR / "ig_last.txt"


def _instagram() -> None:
    import time
    try:
        last = float(IG_LAST.read_text()) if IG_LAST.exists() else 0
        if time.time() - last < IG_EVERY:
            return
        IG_LAST.write_text(str(time.time()))
        from . import instagram
        instagram.run(posts=40)
        from . import roster
        roster.collect(posts=15)            # 합격자 명단·취업 현황 카드(이름 없이 학교·전공·나이·합격처만 남긴다)
    except BaseException as e:            # 로그인 풀림·크롬 문제로 회차 전체를 죽이지 않는다
        if isinstance(e, KeyboardInterrupt):
            raise
        print(f"인스타 건너뜀: {e}")


def once(a) -> None:
    store.ensure()
    q = store.load_json(QUEUE, {"pending": [], "done": [], "rounds": 0})
    if a.add:
        q["pending"] = [k for k in a.add if k not in q["pending"]] + q["pending"]
        store.save_json(QUEUE, q)
        print(f"검색어 {len(a.add)}개를 앞에 넣었다")
        return
    done_ids = {r["id"] for r in store.read_paths()}
    backlog = sum(1 for f in store.RAW.glob("*.json") if f.stem not in done_ids)
    _instagram()
    collect.run_inbox()
    if backlog <= BACKLOG_MAX:            # 밀린 추출이 적을 때만 새로 모은다 — 회차가 한없이 길어지지 않게
        _fill(q)
        take, q["pending"] = q["pending"][: a.queries], q["pending"][a.queries:]
        generic = set(collect.GENERIC)
        collect.run_velog([(k, 40 if k in generic else 2) for k in take])   # 일반 검색어는 velog 상한(2,000건)까지 — 앞 4쪽만 보던 때 '합격 후기' 하나에 안 본 글 1,285건
        q["done"] += take
        collect.run_devto(pages=2)
        try:                                # velog·dev.to 밖 — Medium(키 없음), 티스토리(KAKAO_REST_KEY 있을 때만)
            from careers import blogs
            blogs.run_medium()
            blogs.run_tistory([(k, 10 if k in generic else 1) for k in take])
        except Exception as e:  # noqa: BLE001
            print(f"블로그 건너뜀: {e}", flush=True)
        q["last_run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        store.save_json(QUEUE, q)
    else:
        print(f"추출 밀림 {backlog}건 — 이번 회차는 수집을 쉬고 추출만", flush=True)
    if not a.no_extract:
        extract.main_args(limit=EXTRACT_PER_RUN, workers=1, batch=5)   # claude 를 하나씩 — 여럿 띄우면 메모리가 모자란다
        extract.backfill_application(limit=60)                           # 먼저 뽑은 글에 서류(이력서·포폴·자소서) 항목 채우기
        try:
            from . import age, roster
            age.backfill(limit=30)                                       # 먼저 뽑은 글에 합격 당시 나이
            roster.read(limit=8)                                        # 명단 캡처 → 표
        except Exception as e:  # noqa: BLE001
            print(f"나이·명단 건너뜀: {e}", flush=True)
    try:
        from . import job_history
        print(f"공고 이력: 새 공고 {job_history.update()}건", flush=True)   # 그때 공고와 맞추려고 회차마다 쌓는다
    except Exception as e:  # noqa: BLE001
        print(f"공고 이력 건너뜀: {e}", flush=True)
    github_orgs.run(limit=15)
    try:                                   # 기술블로그 새 글 번역(5070 Ti) — 원문이 그대로인 글은 건너뛴다
        from store.ingest import translate
        translate.cmd_run(limit=20, dry=False)
    except Exception as e:  # noqa: BLE001
        print(f"블로그 번역 건너뜀: {e}", flush=True)
    report.build()
    try:                                   # 원문·경험담·명단 → 정본 DB(019). 뷰어 기술도서 › 취업 이 읽는다
        from store.ingest import careers as careers_db
        print(f"DB: {careers_db.sync()}", flush=True)
    except Exception as e:  # noqa: BLE001 — DB 가 없어도 회차는 끝난다
        print(f"DB 적재 건너뜀: {e}", flush=True)
    print(f"대기 {len(q['pending'])} · 끝난 검색어 {len(q['done'])} · 바퀴 {q.get('rounds', 0)}")


if __name__ == "__main__":
    main()
