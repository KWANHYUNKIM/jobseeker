"""자동 발행 데몬 — 사람이 승인한 포스터를 정해진 시각에 인스타에 올린다.

launchd 가 5분마다 `tick` 을 한 번 부른다(deploy/setup-publisher.sh). 상주 프로세스가
아니라서 PID 관리가 없고, 한 번 돌 때 하는 일은 이 순서로 정해져 있다.

  1. 받기     inbox/<id>/ (publish.cli approve·push 가 놓고 간 묶음) → 원장 approved
  2. 마감     승인 뒤 마감된 공고는 올리지 않는다 → skipped
  3. 예약     approved 에 다음 빈 발행 시각(slots)을 붙인다 → scheduled
  4. 발행     시각이 된 것 한 건만 올린다 → published / 재시도 / failed / rehearsed
  5. 반응     최근 게시물의 좋아요·댓글 수를 몇 시간에 한 번 갱신한다
  6. 토큰     만료 7일 전이면 장기 토큰을 갱신한다
  7. 상태     state/publish_status.json — 크롤 운영 대시보드(8770)의 '인스타 발행' 칸이 읽는다

실제로 나가는 건 설정의 autopublish.live 가 true 이고 자격이 다 있을 때뿐이다. 아니면
dry-run 으로 돌고 rehearsed 로 남는다(requeue 로 되돌린다) — 자격 없이 설치해도 사고가 안 난다.

    python -m publish.daemon tick            # 한 번
    python -m publish.daemon tick --now 2026-09-17T12:31
    python -m publish.daemon status
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from publish import queue                                          # noqa: E402
from publish.base import CONFIG, LAB_DIR, PLATFORMS, load_config, publisher_for  # noqa: E402

INBOX = LAB_DIR / "inbox"
APPROVED_DIR = LAB_DIR / "state" / "approved"
STATUS = LAB_DIR / "state" / "publish_status.json"
LOCK = LAB_DIR / "state" / "publish.lock"

DEFAULTS = {
    "live": False,
    # 채용 공고를 보는 시간 — 점심과 퇴근 뒤. 하루 두 건을 넘기면 계정이 공고 게시판처럼 보인다.
    "slots": ["12:30", "19:30"],
    "max_attempts": 3,
    "stats_every_hours": 3,
    "stats_days": 14,
    "token_refresh_days": 7,
}


def settings(cfg: dict) -> dict:
    return {**DEFAULTS, **(cfg.get("autopublish") or {})}


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


def _parse(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s) if s else None
    except ValueError:
        return None


# --- 1. 받기 ------------------------------------------------------------
def ingest(log: list[str]) -> int:
    """inbox 의 완성된 묶음을 원장에 올린다. 전송 중인 묶음(bundle.json 없음)은 건드리지 않는다."""
    if not INBOX.is_dir():
        return 0
    n = 0
    for d in sorted(p for p in INBOX.iterdir() if p.is_dir() and not p.name.startswith("_")):
        bundle_path, image = d / "bundle.json", d / "poster.jpg"
        if not bundle_path.is_file() or not image.is_file():
            continue
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        platform = (bundle.get("platforms") or ["instagram"])[0]
        dup = queue.pending_for(bundle["job_key"], platform)
        if dup and dup["id"] != bundle["id"]:
            log.append(f"받기 거절 {bundle['id']}: {bundle['job_key']} 는 이미 줄 서 있음({dup['id']})")
            _park(d, "_rejected")
            continue
        if platform in queue.published_platforms(bundle["job_key"]) and not bundle.get("force"):
            log.append(f"받기 거절 {bundle['id']}: {bundle['job_key']} 는 이미 {platform} 에 올라감")
            _park(d, "_rejected")
            continue
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        dest = APPROVED_DIR / f"{bundle['id']}.jpg"
        shutil.copyfile(image, dest)
        # 묶음 묶음: poster.jpg(표지) 외에 slide_01.jpg… 가 함께 온다. 순서가 곧 캐러셀 순서다.
        slides = sorted(d.glob("slide_*.jpg"))
        images = [str(dest.relative_to(LAB_DIR).as_posix())]
        for s in slides:
            kept = APPROVED_DIR / f"{bundle['id']}_{s.name}"
            shutil.copyfile(s, kept)
            images.append(str(kept.relative_to(LAB_DIR).as_posix()))
        queue.add_approved(bundle, images[0], images if slides else None)
        _park(d, "_done")
        log.append(f"받음 {bundle['id']} {bundle['job_key']}")
        n += 1
    return n


def _park(d: Path, where: str) -> None:
    target = INBOX / where / d.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(d), str(target))


# --- 2. 마감 ------------------------------------------------------------
def drop_closed(log: list[str], status_of=None) -> int:
    """승인 뒤 마감된 공고를 뺀다. 공고 색인을 한 번만 읽는다(45MB).

    묶음(카테고리)은 검사하지 않는다 — 9곳 중 한 곳이 닫혔다고 묶음을 버릴 수는 없다.
    대신 묶음은 승인한 날 안에 나가도록 슬롯을 가까이 둔다(SOCIAL.md).
    """
    pending = [i for i in queue.load()["items"]
               if i["status"] in queue.PENDING and i.get("kind", "job") != "collection"]
    if not pending:
        return 0
    if status_of is None:
        from poster import jobsource
        from publish.openness import check
        by_key = {j["key"]: j for j in jobsource.load_index()["jobs"]}

        def status_of(key):
            """승인 뒤 며칠 지나 올라갈 수도 있다 — 원본에 다시 묻는다(판정은 캐시된다).

            확인 불가(차단·타임아웃)는 빼지 않는다. 그건 '닫혔다' 가 아니고, 못 물었다고 예약을
            버리면 사이트가 느린 날 묶음이 통째로 사라진다. 대신 승인 단계에서 이미 걸렀다.
            """
            job = by_key.get(key)
            if not job:
                return "missing"
            state, _ = check(job)
            return "active" if state in ("open", "unknown") else "closed"
    n = 0
    for item in pending:
        st = status_of(item["job_key"])
        if st != "active":
            queue.update(item["id"], status="skipped", scheduled_at="",
                         event="skipped", detail=f"공고 상태 {st}")
            log.append(f"뺌 {item['id']} {item['job_key']}: 공고 {st}")
            n += 1
    return n


# --- 3. 예약 ------------------------------------------------------------
def next_slot(now: datetime, slots: list[str], taken: set[str]) -> datetime:
    """now 이후 첫 빈 발행 시각. taken 은 이미 잡힌 시각(분 단위 iso)."""
    times = sorted(datetime.strptime(s, "%H:%M").time() for s in slots)
    day = now.date()
    for _ in range(400):
        for t in times:
            cand = datetime.combine(day, t)
            if cand > now and _iso(cand) not in taken:
                return cand
        day += timedelta(days=1)
    raise RuntimeError("400일 안에 빈 발행 시각이 없습니다")


def taken_slots() -> set[str]:
    out = set()
    for i in queue.load()["items"]:
        if i["status"] == "scheduled" and i.get("scheduled_at"):
            out.add(i["scheduled_at"])
        elif i["status"] in ("published", "rehearsed") and i.get("slot"):
            out.add(i["slot"])
    return out


def schedule(now: datetime, conf: dict, log: list[str]) -> int:
    approved = sorted((i for i in queue.load()["items"] if i["status"] == "approved"),
                      key=lambda i: i.get("approved_at") or i["created_at"])
    taken = taken_slots()
    for item in approved:
        slot = next_slot(now, conf["slots"], taken)
        taken.add(_iso(slot))
        queue.update(item["id"], status="scheduled", scheduled_at=_iso(slot),
                     event="scheduled", detail=_iso(slot))
        log.append(f"예약 {item['id']} {item['job_key']} → {_iso(slot)}")
    return len(approved)


# --- 4. 발행 ------------------------------------------------------------
def _done_on(results: dict, platform: str) -> bool:
    """이 플랫폼에는 이미 진짜로 올라갔나(연습 발행은 안 올라간 것)."""
    r = results.get(platform) or {}
    return bool(r.get("ok")) and not r.get("dry_run")


def publish_due(now: datetime, cfg: dict, conf: dict, log: list[str], publishers=None) -> dict | None:
    """시각이 된 예약 한 건을 인스타·페이스북에 올린다. 한 tick 에 한 건 — 몰아서 올리지 않는다.

    한 판이 두 곳에 나간다. 한쪽만 실패하면 성공한 쪽은 그대로 두고 실패한 쪽만 다시 시도한다 —
    재시도 때 인스타에 같은 판이 두 번 올라가면 안 된다.
    """
    due = sorted((i for i in queue.load()["items"]
                  if i["status"] == "scheduled" and (_parse(i.get("scheduled_at")) or now) <= now),
                 key=lambda i: i["scheduled_at"])
    if not due:
        return None
    item = due[0]
    results = dict(item.get("results") or {})
    captions = item.get("captions") or {}
    # 묶음이면 표지+공고 판 여러 장이 한 게시물로 나간다(캐러셀/사진 여러 장 글)
    images = [LAB_DIR / p for p in (item.get("images") or [])] or [LAB_DIR / item["files"]["ig_portrait"]]
    slot = item["scheduled_at"]
    pubs = publishers or {p: publisher_for(p, cfg) for p in item["platforms"]}
    todo = [p for p in item["platforms"] if not _done_on(results, p)]

    failures, rehearsals, posted = [], [], []
    for platform in todo:
        pub = pubs[platform]
        live = bool(conf["live"]) and not pub.missing()
        if live and platform in queue.published_platforms(item["job_key"]) and not item.get("force"):
            log.append(f"뺌 {item['id']} {platform}: 이 공고는 이미 {platform} 에 올라감")
            results[platform] = {"platform": platform, "ok": False, "dry_run": False,
                                 "error": "이미 올라간 공고", "skipped": True}
            continue
        res = pub.publish_many(images=images, caption=captions.get(platform) or item.get("caption", ""),
                               dry_run=not live)
        results[platform] = res.as_dict()
        if not res.ok:
            failures.append(f"{platform}: {res.error}")
        elif live:
            posted.append(platform)
            log.append(f"게시 {item['id']} {item['job_key']} {platform} {res.url}")
        else:
            why = "autopublish.live 가 꺼져 있음" if not conf["live"] else f"자격 없음: {', '.join(pub.missing())}"
            rehearsals.append(f"{platform}({why})")

    if failures:
        attempts = int(item.get("attempts") or 0) + 1
        detail = " / ".join(failures)
        if attempts >= conf["max_attempts"]:
            queue.update(item["id"], status="failed", results=results, attempts=attempts,
                         scheduled_at="", slot=slot, posted=posted or item.get("posted", []),
                         event="failed", detail=detail)
            log.append(f"실패 {item['id']} {attempts}회째 — 포기: {detail}")
        else:
            retry = next_slot(now, conf["slots"], taken_slots())
            queue.update(item["id"], results=results, attempts=attempts, scheduled_at=_iso(retry),
                         event="retry", detail=f"{attempts}회 실패 → {_iso(retry)}: {detail}")
            log.append(f"실패 {item['id']} {attempts}회째 → {_iso(retry)} 재시도: {detail}")
    elif rehearsals:
        queue.update(item["id"], status="rehearsed", results=results, slot=slot, scheduled_at="",
                     event="rehearsed", detail=" / ".join(rehearsals))
        log.append(f"연습 {item['id']} {item['job_key']} {' / '.join(rehearsals)}")
    elif not any(_done_on(results, p) for p in item["platforms"]):
        # 올릴 곳이 하나도 남지 않았다 — 전부 '이미 올라감' 으로 걸러졌을 때
        queue.update(item["id"], status="skipped", results=results, slot=slot, scheduled_at="",
                     event="skipped", detail="올릴 곳이 없음(이미 올라간 공고)")
        log.append(f"뺌 {item['id']} {item['job_key']}: 올릴 곳 없음")
    else:
        done = sorted(set(posted) | set(p for p in item["platforms"] if _done_on(results, p)))
        queue.update(item["id"], status="published", results=results, slot=slot, scheduled_at="",
                     published_at=item.get("published_at") or _iso(now), posted=done,
                     event="published", detail=", ".join(done))
        log.append(f"게시 완료 {item['id']} {item['job_key']} → {', '.join(done)}")
    return queue.get(item["id"])


# --- 5. 반응 ------------------------------------------------------------
def refresh_stats(now: datetime, cfg: dict, conf: dict, log: list[str], publisher=None) -> int:
    pub = publisher or publisher_for("instagram", cfg)
    if pub.missing():
        return 0
    n = 0
    for item in queue.load()["items"]:
        if item["status"] != "published":
            continue
        res = (item.get("results") or {}).get("instagram") or {}
        published = _parse(item.get("published_at"))
        fetched = _parse((item.get("stats") or {}).get("fetched_at"))
        if not res.get("remote_id") or not published or now - published > timedelta(days=conf["stats_days"]):
            continue
        if fetched and now - fetched < timedelta(hours=conf["stats_every_hours"]):
            continue
        try:
            stats = pub.media_stats(res["remote_id"])
        except RuntimeError as e:
            # 사람이 인스타 앱에서 지운 게시물은 영영 안 돌아온다 — 지워졌다고 적고 그만 묻는다
            if "does not exist" in str(e) or "code\":100" in str(e):
                queue.update(item["id"], stats={"deleted_at": _iso(now), "fetched_at": _iso(now)},
                             event="gone", detail="게시물이 지워졌다(앱에서 삭제)")
                log.append(f"지워짐 {item['id']} — 반응 조회 중단")
            else:
                log.append(f"반응 조회 실패 {item['id']}: {e}")
            continue
        queue.update(item["id"], stats={**stats, "fetched_at": _iso(now)})
        n += 1
    return n


# --- 6. 토큰 ------------------------------------------------------------
def refresh_token(now: datetime, cfg: dict, conf: dict, log: list[str], publisher=None) -> str:
    pub = publisher or publisher_for("instagram", cfg)
    ig = cfg.get("instagram") or {}
    expires = _parse(ig.get("token_expires_at", ""))
    if pub.missing() or not expires or pub.login != "instagram":
        return ""
    if expires - now > timedelta(days=conf["token_refresh_days"]):
        return ""
    if os.environ.get("DESIGN_LAB_IG_TOKEN"):
        log.append("토큰 만료 임박 — 환경변수 토큰이라 자동 갱신 못 함")
        return "env"
    try:
        new = pub.refresh_token()
    except RuntimeError as e:
        log.append(f"토큰 갱신 실패: {e}")
        return "failed"
    raw = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.is_file() else {}
    raw.setdefault("instagram", {}).update(new)
    tmp = CONFIG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, CONFIG)
    log.append(f"토큰 갱신 → {new['token_expires_at']} 까지")
    return "refreshed"


# --- 7. 상태 ------------------------------------------------------------
def write_status(now: datetime, cfg: dict, conf: dict, log: list[str], publisher=None) -> dict:
    pub = publisher or publisher_for("instagram", cfg)
    fb = publisher_for("facebook", cfg)
    ig = cfg.get("instagram") or {}
    expires = _parse(ig.get("token_expires_at", ""))
    quota = None
    if not pub.missing():
        try:
            quota = pub.publishing_limit()
        except RuntimeError as e:
            log.append(f"게시 한도 조회 실패: {e}")
    prev = _read(STATUS)
    status = {
        "updated_at": _iso(now),
        "live": bool(conf["live"]),
        # 두 곳 중 한 곳만 자격이 있으면 그 한 곳으로만 나간다 — 어디가 되는지 대시보드가 보여 준다
        "mode": "live" if conf["live"] and not (pub.missing() and fb.missing()) else "rehearsal",
        "ready": {p: not q.missing() for p, q in (("instagram", pub), ("facebook", fb))},
        "missing": pub.missing(),
        "missing_by": {"instagram": pub.missing(), "facebook": fb.missing()},
        "login": pub.login,
        "public_base_url": cfg.get("public_base_url", ""),
        "slots": conf["slots"],
        "token_expires_at": _iso(expires) if expires else "",
        "token_days_left": (expires - now).days if expires else None,
        "quota": quota,
        # 대시보드 이벤트 줄. 조용한 tick 은 남기지 않는다.
        "log": ([{"at": _iso(now), "msg": m} for m in log] + (prev.get("log") or []))[:40],
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATUS)
    return status


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# --- tick --------------------------------------------------------------
def _lock() -> bool:
    """손으로 돌린 tick 과 launchd tick 이 겹치지 않게. 10분 넘은 잠금은 죽은 것으로 본다."""
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.is_file() and datetime.now().timestamp() - LOCK.stat().st_mtime < 600:
        return False
    LOCK.write_text(str(os.getpid()))
    return True


def tick(now: datetime | None = None) -> dict:
    now = now or datetime.now().replace(microsecond=0)
    if not _lock():
        return {"skipped": "다른 tick 이 돌고 있음"}
    try:
        cfg = load_config()
        conf = settings(cfg)
        log: list[str] = []
        pubs = {p: publisher_for(p, cfg) for p in PLATFORMS}
        pub = pubs["instagram"]
        ingest(log)
        drop_closed(log)
        schedule(now, conf, log)
        publish_due(now, cfg, conf, log, pubs)
        refresh_stats(now, cfg, conf, log, pub)
        refresh_token(now, cfg, conf, log, pub)
        cfg = load_config()                     # 토큰이 갱신됐으면 새 만료일로
        return write_status(now, cfg, conf, log, publisher_for("instagram", cfg))
    finally:
        LOCK.unlink(missing_ok=True)


def _report(out: dict) -> None:
    if "skipped" in out:
        print(f"[publish] {out['skipped']}")
        return
    for row in out.get("log", []):
        if row["at"] == out["updated_at"]:
            print(f"[publish] {row['msg']}")
    print(f"[publish] {out['mode']} · 토큰 {out['token_days_left']}일 · 한도 {out['quota']}")


def main() -> int:
    ap = argparse.ArgumentParser(prog="publish.daemon")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tick")
    t.add_argument("--now", default="", help="시각을 흉내 낸다(시험용)")
    # 맥에서는 launchd 가 tick 을 주기로 부른다(deploy/setup-publisher.sh). launchd 가 없는
    # 곳(윈도우에서 직접 돌려 볼 때)을 위한 반복 실행 — Ctrl+C 로 끝낸다.
    r = sub.add_parser("run", help="tick 을 주기로 반복(launchd 없는 곳에서)")
    r.add_argument("--every", type=int, default=300, help="초 단위 주기(기본 300)")
    sub.add_parser("status")
    args = ap.parse_args()

    if args.cmd == "status":
        print(json.dumps(_read(STATUS), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "run":
        import time
        print(f"[publish] {args.every}초마다 tick — Ctrl+C 로 종료")
        try:
            while True:
                _report(tick())
                time.sleep(args.every)
        except KeyboardInterrupt:
            print("\n[publish] 종료")
        return 0
    _report(tick(_parse(args.now) if args.now else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
