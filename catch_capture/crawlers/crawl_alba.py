"""컴퓨터 알바 모음 → jd-viewer/public/alba.json (누적, 출처 다섯 곳).

알바 공고 가운데 **컴퓨터로 하는 일**(웹·앱 제작·개발·코딩 강사·디자인/영상·쇼핑몰 운영·엑셀/AI 사무·PC 지원)만
모은다. 출처는 당근알바·알바천국·알바몬·사람인(아르바이트·파트)·잡코리아(아르바이트). 출처마다 어디서 받고
무엇을 마감이라 하는지는 crawlers/alba/<출처>.py 머리말에 있고, 분류 규칙·요약만 싣는 규칙·누적·마감 반영은
crawlers/alba/common.py 하나를 같이 쓴다. **요약과 링크만** — 본문·상호·연락처·번지는 저장하지 않는다.

한 회차:
  출처마다 따로 돈다(스레드 하나씩, 호스트마다 초당 한 번). 한 출처가 실패해도 나머지는 끝까지 간다 —
  실패한 출처의 공고는 그대로 두고 다음 회차에 다시 본다. 다 돌면 제목+지역이 같은 공고에 dup_of 를 단다
  (지우지 않는다). 공고 id 는 `<출처>-<원본 번호>` 로 출처 사이에서 겹치지 않는다(당근 옛 id 는 처음 한 번 옮긴다).

사용:
    python -m crawlers.crawl_alba                          # 기본(출처마다 신규 150·재확인 100/60)
    python -m crawlers.crawl_alba --new 150 --recheck 80   # 출처마다 같은 한도
    python -m crawlers.crawl_alba --source albamon,saramin # 일부 출처만
    python -m crawlers.crawl_alba --check                  # 회차 사이 재확인(새 공고 없이 마감만 — launchd albacheck)
    python -m crawlers.crawl_alba --candidates albamon     # 그 출처의 1차 후보 제목만 출력(상세를 받지 않는다)
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from crawlers.alba import common as C
from crawlers.alba.albacheonguk import AlbaCheonguk
from crawlers.alba.albamon import Albamon
from crawlers.alba.daangn import Daangn
from crawlers.alba.jobkorea import JobKorea
from crawlers.alba.saramin import Saramin

SOURCES = {cls.name: cls for cls in (Daangn, AlbaCheonguk, Albamon, Saramin, JobKorea)}
LABELS = {k: v.label for k, v in SOURCES.items()}
CHECK_LIMIT = 60          # 회차 사이 재확인 한 번에 출처마다 묻는 수(사라진 것은 GONE_LIMIT 까지 따로)

# 옛 크롤러(crawl_daangn_alba)와 테스트가 쓰던 이름 — 경로만 옮겼다.
OUT_PATH, STATE_PATH, LOCK_PATH = C.OUT_PATH, C.STATE_PATH, C.LOCK_PATH


def migrate(doc: dict, state: dict) -> tuple[list[dict], dict]:
    """당근 하나만 있던 때의 파일을 출처별 모양으로 한 번 옮긴다(이미 옮겼으면 그대로).

    공고: id '<12자>' → 'daangn-<12자>', source·pid 를 붙인다. 상태: 평평한 rejected/lastmod/sitemap_count →
    state['sources']['daangn'].
    """
    posts = []
    for p in doc.get("posts") or []:
        if not p.get("source"):
            p["source"], p["pid"] = "daangn", p["id"]
            p["id"] = C.post_id("daangn", p["id"])
        p.setdefault("pid", p["id"].split("-", 1)[-1])
        posts.append(p)
    if "sources" not in state:
        old = {k: state[k] for k in ("rejected", "lastmod", "rules_version") if k in state}
        if "sitemap_count" in state:
            old["listing_count"] = state["sitemap_count"]
        state = {"sources": {"daangn": old} if old else {}}
    return posts, state


def run(new_limit: int | None = None, recheck_limit: int | None = None, sources=None, check: bool = False) -> dict:
    """한 회차. 잠금을 못 잡으면(다른 쪽이 도는 중) 건너뛴다 — 다음 주기에 다시 온다."""
    C.LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(C.LOCK_PATH, "a+") as fh:
        if not C.try_lock(fh):
            print("[alba] 다른 회차가 alba.json 을 쓰는 중 — 이번엔 건너뜀", flush=True)
            return {"ok": True, "skipped": True, "total": None, "open": None, "new": 0, "closed_now": 0}
        return _run(new_limit, recheck_limit, sources, check)


def check(limit: int = CHECK_LIMIT, sources=None) -> dict:
    """회차 사이 재확인 — 새 공고는 받지 않고 마감만 본다(launchd albacheck 가 부른다).

    사람을 구하면 공고가 닫히는데, 크롤 회차(1시간)만 기다리면 그만큼 늦게 닫힌다. 목록은 당근(사이트맵)만
    다시 받고 나머지 출처는 오래 안 물어본 모집중부터 원본에 묻는다. 결과는 뷰어 API(viewer_doc)에도 바로 옮긴다.
    """
    stats = run(new_limit=0, recheck_limit=limit, sources=sources, check=True)
    if stats.get("ok") and not stats.get("skipped"):
        try:
            from store.ingest.docs import sync
            sync()
        except Exception as e:                                   # noqa: BLE001 — DB 가 없어도 파일은 이미 갱신됐다
            print(f"[alba] 뷰어 문서 동기화 건너뜀: {str(e)[:120]}", flush=True)
    try:
        from automation import orchestration as orch
        orch.emit("alba_check", **{k: v for k, v in stats.items() if k != "per_source"})
    except Exception:                                            # noqa: BLE001
        pass
    return stats


def _one(src: C.Source, posts: dict, st: dict, now: str, new_limit, recheck_limit, check: bool) -> dict:
    try:
        return C.run_source(src, posts, st, now,
                            src.new_limit if new_limit is None else new_limit,
                            (src.check_limit if check else src.recheck_limit) if recheck_limit is None else recheck_limit,
                            use_listing=src.check_uses_listing or not check)
    except Exception as e:                                       # noqa: BLE001 — 출처 하나의 실패로 끝낸다
        print(f"[alba:{src.name}] 실패: {str(e)[:200]}", flush=True)
        return {"ok": False, "error": str(e)[:200]}


def _run(new_limit, recheck_limit, sources, check: bool) -> dict:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    t0 = time.time()
    posts, state = migrate(C.load_json(C.OUT_PATH, {"posts": []}), C.load_json(C.STATE_PATH, {}))
    doc_prev = C.load_json(C.OUT_PATH, {})
    names = [n for n in (sources or SOURCES) if n in SOURCES]
    by_src: dict[str, dict[str, dict]] = {n: {} for n in SOURCES}
    for p in posts:
        by_src.setdefault(p["source"], {})[p["pid"]] = p
    sts = state["sources"]
    srcs = [SOURCES[n]() for n in names]
    with ThreadPoolExecutor(max_workers=max(1, len(srcs))) as ex:
        futs = {s.name: ex.submit(_one, s, by_src[s.name], sts.setdefault(s.name, {}), now,
                                  new_limit, recheck_limit, check) for s in srcs}
        reps = {n: f.result() for n, f in futs.items()}

    rows = [p for d in by_src.values() for p in d.values()]
    dups = C.mark_dups(rows)
    rows.sort(key=lambda p: p.get("posted_at") or p.get("first_seen_at") or "", reverse=True)
    per = dict(doc_prev.get("sources") or {})
    for n, r in reps.items():
        per[n] = {**r, "at": now, "label": LABELS[n]}
    new = sum(r.get("new") or 0 for r in reps.values())
    closed_now = sum(r.get("closed_now") or 0 for r in reps.values())
    failed = [n for n, r in reps.items() if not r.get("ok")]
    out = {"updated_at": now, "started_at": doc_prev.get("started_at") or now,
           "source": {"ok": not failed, "new": new, "rechecked": sum(r.get("rechecked") or 0 for r in reps.values()),
                      "closed_now": closed_now, "failed": failed, "dups": dups,
                      "elapsed": round(time.time() - t0, 1)},
           "sources": per, "source_labels": LABELS, "categories": C.CATEGORIES, "posts": rows}
    C.write_json(C.OUT_PATH, out)
    C.write_json(C.STATE_PATH, state)
    open_n = sum(p["status"] == "open" for p in rows)
    for n, r in reps.items():
        print(f"[alba:{n}] " + (f"실패 — {r.get('error')}" if not r.get("ok") and "listed" not in r else
              f"목록 {r.get('listed', '-')} · 후보 {r.get('candidates')} · 상세 {r.get('fetched')}(실패 {r.get('failed')}) · "
              f"신규 {r.get('new')} · 재확인 {r.get('rechecked')} → 마감 {r.get('closed_now')} · "
              f"누적 {r.get('total')}(모집중 {r.get('open')}) · {r.get('elapsed')}s"), flush=True)
    print(f"[alba] 누적 {len(rows)}건(모집중 {open_n}, 중복 표시 {dups}) · 신규 {new} · 마감 {closed_now}"
          + (f" · 실패 출처 {','.join(failed)}" if failed else "") + f" → {C.OUT_PATH}", flush=True)
    # 출처가 하나라도 돌았으면 성공으로 친다 — 실패한 출처는 failed 에 이름이 남는다(8770 단계 표).
    return {"ok": len(failed) < len(reps), "total": len(rows), "open": open_n, "new": new,
            "closed_now": closed_now, "failed": failed,
            "per_source": {n: {k: r.get(k) for k in ("ok", "new", "total", "open", "closed_now")} for n, r in reps.items()}}


def _arg(args: list[str], name: str):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def main() -> None:
    args = _sys.argv[1:]
    srcs = (_arg(args, "--source") or "").split(",") if "--source" in args else None
    if "--candidates" in args:
        name = _arg(args, "--candidates") or "daangn"
        src = SOURCES[name]()
        entries = src.listing()
        for pid, e in sorted(entries.items(), key=lambda x: x[1].get("lastmod") or x[1].get("sort") or "", reverse=True):
            if src.candidate(e):
                print(pid, (e.get("lastmod") or "")[:10], e.get("title"))
        return
    recheck = int(_arg(args, "--recheck")) if "--recheck" in args else None
    if "--check" in args:                                        # 회차 사이 재확인(launchd albacheck)
        stats = check(recheck or CHECK_LIMIT, srcs)
        _sys.exit(0 if stats["ok"] else 1)
    new_limit = int(_arg(args, "--new")) if "--new" in args else None
    stats = run(new_limit, recheck, srcs)
    _sys.exit(0 if stats["ok"] else 1)


if __name__ == "__main__":
    main()
