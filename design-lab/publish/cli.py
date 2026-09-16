"""발행 파이프라인 CLI.

    python -m publish.cli check                                  자격 점검
    python -m publish.cli plan wanted-364663 -t role_hero -p instagram,linkedin
    python -m publish.cli render <item-id>                       큐 항목의 이미지를 굽는다
    python -m publish.cli caption <item-id>                      플랫폼별 캡션 미리보기
    python -m publish.cli publish <item-id>                      기본 dry-run
    python -m publish.cli publish <item-id> --live               진짜로 올린다
    python -m publish.cli ls [--status planned]

자동 발행(사람은 승인까지만, 나머지는 publish.daemon — SOCIAL.md):

    python -m publish.cli approve wanted-376128                  인스타·페이스북에 올릴 판을 승인
    python -m publish.cli approve wanted-376128 -p instagram     한 곳에만
    python -m publish.cli push                                   승인 묶음을 맥 inbox 로
    python -m publish.cli queue                                  원장(맥에서)
    python -m publish.cli requeue --all-rehearsed                연습 발행분을 다시 승인 상태로
    python -m publish.cli token-refresh                          인스타 장기 토큰 갱신

랩 서버(8780)의 버튼들도 결국 이 함수들을 부른다. CLI 가 원본이다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from poster import render as renderer                      # noqa: E402
from poster.model import FORMATS                            # noqa: E402
from publish import caption as captions                     # noqa: E402
from publish import queue                                   # noqa: E402
from publish.base import PLATFORMS, load_config, publisher_for  # noqa: E402

LAB_DIR = Path(__file__).resolve().parent.parent
OUT = LAB_DIR / "out"


def cmd_check(_args) -> int:
    cfg = load_config()
    print(f"public_base_url: {cfg.get('public_base_url') or '(없음 — 인스타 발행 불가)'}")
    for p in PLATFORMS:
        c = publisher_for(p, cfg).check()
        mark = "준비됨" if c["ready"] else f"모자람: {', '.join(c['missing'])}"
        print(f"  {p:<10} {mark}")
    auto = cfg.get("autopublish") or {}
    ig = publisher_for("instagram", cfg)
    print(f"autopublish.live: {bool(auto.get('live'))}  (false 면 데몬은 연습 발행만 한다)")
    print(f"instagram 로그인 방식: {ig.login} · 토큰 만료 {(cfg.get('instagram') or {}).get('token_expires_at') or '(모름)'}")
    if not ig.missing():
        try:
            q = ig.publishing_limit()
            print(f"instagram 게시 한도: 24시간 {q['used']}/{q['limit']}")
        except RuntimeError as e:
            print(f"instagram 한도 조회 실패 — 토큰·권한 확인: {e}")
    return 0


def cmd_plan(args) -> int:
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    unknown = [p for p in platforms if p not in PLATFORMS]
    if unknown:
        print(f"모르는 플랫폼: {unknown}", file=sys.stderr)
        return 2
    formats = [f.strip() for f in args.formats.split(",") if f.strip()] if args.formats else [
        publisher_for(p).preferred_format for p in platforms]
    formats = list(dict.fromkeys(formats))
    already = queue.published_platforms(args.job_key)
    if already:
        print(f"! 이미 올라간 곳: {', '.join(sorted(already))}")
    item = queue.add(args.job_key, template=args.template, formats=formats,
                     platforms=platforms, palette=args.palette, note=args.note)
    print(f"[plan] {item['id']}  {item['job_key']}  {item['template']}  {formats} → {platforms}")
    return 0


def cmd_render(args) -> int:
    item = queue.get(args.item_id)
    if not item:
        print("그런 큐 항목이 없습니다", file=sys.stderr)
        return 2
    files = dict(item.get("files") or {})
    try:
        for fmt in item["formats"]:
            path = renderer.render(item["job_key"], item["template"], fmt,
                                   palette=item.get("palette", ""))
            files[fmt] = str(path.relative_to(LAB_DIR))
            print(f"[render] {fmt} → {files[fmt]}")
    finally:
        renderer.shutdown()
    queue.update(args.item_id, files=files, status="rendered")
    return 0


def cmd_caption(args) -> int:
    item = queue.get(args.item_id)
    if not item:
        print("그런 큐 항목이 없습니다", file=sys.stderr)
        return 2
    spec = renderer.compose(item["job_key"], palette=item.get("palette", ""))
    for platform in item["platforms"]:
        print(f"\n=== {platform} ===\n{captions.build(spec, platform)}")
    return 0


def cmd_publish(args) -> int:
    item = queue.get(args.item_id)
    if not item:
        print("그런 큐 항목이 없습니다", file=sys.stderr)
        return 2
    if not item.get("files"):
        print("먼저 render 하세요", file=sys.stderr)
        return 2
    dry = not args.live
    spec = renderer.compose(item["job_key"], palette=item.get("palette", ""))
    results = dict(item.get("results") or {})
    already = queue.published_platforms(item["job_key"])
    ok_all = True
    for platform in item["platforms"]:
        if platform in already and not dry and not args.force:
            print(f"[skip] {platform} — 이 공고는 이미 올라갔습니다(--force 로 무시)")
            continue
        pub = publisher_for(platform)
        fmt = pub.preferred_format if pub.preferred_format in item["files"] else next(iter(item["files"]))
        image = LAB_DIR / item["files"][fmt]
        # link 를 주지 않는다 — 채용 사이트 주소는 판에도 캡션에도 넣지 않기로 했다
        # (poster/carousel.py compose 주석). 지원 경로는 프로필 링크로 안내한다.
        res = pub.publish(image=image, caption=captions.build(spec, platform), dry_run=dry)
        results[platform] = res.as_dict()
        ok_all = ok_all and res.ok
        head = "DRY" if res.dry_run else ("OK" if res.ok else "FAIL")
        print(f"[{head}] {platform} {res.remote_id or res.error}")
        if dry:
            for s in res.steps:
                print(f"    {s['method']} {s['url']}")
    status = item["status"] if dry else ("published" if ok_all else "failed")
    queue.update(args.item_id, results=results, status=status)
    return 0 if ok_all else 1


def cmd_ls(args) -> int:
    rows = queue.items(args.status)
    if not rows:
        print("큐가 비었습니다")
        return 0
    for i in rows:
        done = ",".join(k for k, v in (i.get("results") or {}).items()
                        if v.get("ok") and not v.get("dry_run")) or "-"
        print(f"{i['id']}  {i['status']:<9} {i['job_key']:<22} {i['template']:<12} 발행:{done}")
    return 0


# --- 자동 발행: 사람이 하는 일은 승인까지 ---------------------------------
# 포스터는 이 윈도우(브랜드 조사·렌더)에서, 발행은 맥(데몬·8770)에서 한다. 원장은 맥에만
# 두고 여기서는 승인 묶음(inbox/<id>/)을 만들어 보낸다 — 두 머신이 같은 파일을 고치지 않는다.
INBOX = LAB_DIR / "inbox"
# 인스타 피드가 받는 가로:세로 범위 — 4:5(0.8) 부터 1.91:1 까지
RATIO_MIN, RATIO_MAX = 0.8, 1.91


def _check_image(path: Path) -> str:
    """문제가 있으면 이유, 없으면 빈 문자열."""
    if not path.is_file():
        return f"이미지가 없습니다: {path}"
    if path.read_bytes()[:3] != b"\xff\xd8\xff":
        return f"JPEG 가 아닙니다(인스타는 JPEG 만 받음): {path.name}"
    try:
        from PIL import Image
    except ImportError:
        return ""
    with Image.open(path) as im:
        w, h = im.size
    if not RATIO_MIN - 0.01 <= w / h <= RATIO_MAX + 0.01:
        return f"비율 {w}x{h} 는 인스타 피드 범위(4:5 ~ 1.91:1) 밖입니다"
    return ""


def cmd_approve(args) -> int:
    import shutil
    import socket
    import uuid
    from datetime import datetime

    from poster import jobsource

    job = jobsource.get(args.job_key)
    if not job:
        print(f"모르는 공고: {args.job_key}", file=sys.stderr)
        return 2
    # 끝난 모집을 홍보하면 안 된다. 색인의 status 는 못 믿는다(마감 표기가 없는 공고는 영구
    # '모집중' 으로 남는다) — 원본 사이트에 다시 묻는다(publish.openness). 확인 불가도 막는다.
    from publish import openness
    state, why = openness.check(job)
    print(f"[확인] {openness.describe(job)}")
    if state != "open" and not args.force:
        print(f"올리지 않습니다 — {state}: {why} (--force 로만 무시)", file=sys.stderr)
        return 2
    image = Path(args.image) if args.image else OUT / args.job_key / "brand_ig_portrait.jpg"
    if not image.is_absolute():
        image = (LAB_DIR / image) if (LAB_DIR / image).exists() else image.resolve()
    problem = _check_image(image)
    if problem:
        print(problem, file=sys.stderr)
        return 2

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    unknown = [p for p in platforms if p not in PLATFORMS]
    if unknown:
        print(f"모르는 플랫폼: {unknown}", file=sys.stderr)
        return 2
    spec = renderer.compose(args.job_key)
    # 플랫폼마다 읽는 태도가 다르다(caption.py). 인스타는 해시태그, 페이스북은 링크가 걸린다.
    caption_text = Path(args.caption_file).read_text(encoding="utf-8").strip() if args.caption_file else ""
    by_platform = {p: caption_text or captions.build(spec, p) for p in platforms}

    item_id = uuid.uuid4().hex[:8]
    d = INBOX / item_id
    d.mkdir(parents=True)
    shutil.copyfile(image, d / "poster.jpg")
    for p, text in by_platform.items():
        (d / f"caption_{p}.txt").write_text(text, encoding="utf-8")
    bundle = {
        "id": item_id, "job_key": args.job_key, "company": job.get("company", ""),
        "role": job.get("title", ""), "template": args.template, "platforms": platforms,
        "captions": by_platform, "caption": by_platform.get("instagram", ""),
        "note": args.note, "force": bool(args.force),
        "source_image": str(image), "approved_on": socket.gethostname(),
        "approved_at": datetime.now().isoformat(timespec="seconds"),
    }
    # bundle.json 을 마지막에 쓴다 — 데몬은 이게 있는 묶음만 받으므로 반쯤 복사된 묶음을 안 집는다.
    (d / "bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[approve] {item_id}  {job.get('company')} · {job.get('title')}  → {', '.join(platforms)}")
    print(f"          {d}")
    for p, text in by_platform.items():
        print(f"          caption_{p}.txt 첫 줄: {text.splitlines()[0]}")
    print("          맥에서 승인했다면 다음 tick 이 가져갑니다. 이 윈도우라면: python -m publish.cli push")
    return 0


def cmd_approve_collection(args) -> int:
    """묶음(카테고리) 하나를 승인한다 — 표지 한 장 + 공고 판 여러 장이 한 게시물로 나간다."""
    import shutil
    import socket
    import uuid
    from datetime import datetime

    from poster import collection
    from poster.render import shutdown

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    unknown = [p for p in platforms if p not in PLATFORMS]
    if unknown:
        print(f"모르는 플랫폼: {unknown}", file=sys.stderr)
        return 2
    col = collection.build(args.kind, value=args.value, since=args.since, until=args.until,
                           limit=min(args.limit, collection.MAX_SLIDES),
                           brand_only=not args.allow_generic)
    if not col["count"]:
        print("조건에 맞는 공고가 없습니다 — 카테고리나 기간을 바꾸세요", file=sys.stderr)
        return 2
    print(f"[{col['id']}] {col['kicker']} · {col['title']} · {col['count']}곳")
    for j in col["jobs"]:
        print(f"  - {j['company']:<22} {j['role'][:32]:<34} {j['until']}")
    for row in col.get("closed_out", [])[:8]:
        # 렌더 전에 걸러진 것들. 여기서 걸러야 브라우저를 안 띄운다(판 하나가 수십 초다).
        print(f"  x {row['company']:<22} {row['state']} — {row['why'][:44]}")
    if col.get("short_by"):
        # 전용 판이 없어 자리가 빈 것이다. 어떤 회사 판을 만들면 채워지는지 같이 알려 준다.
        print(f"  ! 전용 판이 없어 {col['short_by']}자리 비었다 — 다음에 만들 판:")
        for row in col.get("gaps", [])[:5]:
            print(f"      {row['postings']:>3}건  {row['company']} {row['size']}")
        print("      BRAND_RESEARCH.md 절차로 만든 뒤 다시 묶으면 채워진다"
              " (급하면 --allow-generic 으로 기본 틀 판을 섞는다)")
    try:
        paths = collection.render(col)
    finally:
        shutdown()
    problem = next((p for p in (_check_image(x) for x in paths) if p), "")
    if problem:
        print(problem, file=sys.stderr)
        return 2

    item_id = uuid.uuid4().hex[:8]
    d = INBOX / item_id
    d.mkdir(parents=True)
    shutil.copyfile(paths[0], d / "poster.jpg")                 # 표지
    for i, p in enumerate(paths[1:], 1):
        shutil.copyfile(p, d / f"slide_{i:02d}.jpg")            # 공고 판 — 이름 순서가 캐러셀 순서
    by_platform = {p: captions.build_collection(col, p) for p in platforms}
    for p, text in by_platform.items():
        (d / f"caption_{p}.txt").write_text(text, encoding="utf-8")
    bundle = {
        "id": item_id, "job_key": f"collection:{col['id']}",
        "company": col["kicker"], "role": col["title"], "template": "collection",
        "platforms": platforms, "captions": by_platform,
        "caption": by_platform.get("instagram", ""), "note": args.note,
        "force": bool(args.force), "collection": col,
        "approved_on": socket.gethostname(),
        "approved_at": datetime.now().isoformat(timespec="seconds"),
    }
    (d / "bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[approve] {item_id}  묶음 {len(paths)}장 → {', '.join(platforms)}")
    print(f"          {d}")
    print(f"          caption_{platforms[0]}.txt 첫 줄: {by_platform[platforms[0]].splitlines()[0]}")
    return 0


def cmd_push(args) -> int:
    """승인 묶음을 맥의 inbox 로 보낸다. bundle.json 은 맨 나중에 보내 반쪽 묶음이 안 잡히게 한다."""
    import shutil
    import subprocess

    cfg = load_config().get("autopublish") or {}
    host = args.host or cfg.get("push_host", "jobseeker-mac")
    root = args.root or cfg.get("push_root", "jobseeker/design-lab")
    bundles = sorted(p for p in INBOX.iterdir() if p.is_dir() and not p.name.startswith("_")) \
        if INBOX.is_dir() else []
    if not bundles:
        print("보낼 승인 묶음이 없습니다")
        return 0
    failed = 0
    for d in bundles:
        remote = f"{root}/inbox/{d.name}"
        # bundle.json 은 맨 마지막에 — 데몬은 그게 도착한 묶음만 받는다(반쪽 묶음 방지)
        others = [str(p) for p in sorted(d.iterdir()) if p.name != "bundle.json"]
        steps = [
            ["ssh", "-o", "ConnectTimeout=10", host, f"mkdir -p '{remote}'"],
            ["scp", "-q", *others, f"{host}:{remote}/"],
            ["scp", "-q", str(d / "bundle.json"), f"{host}:{remote}/"],
        ]
        for cmd in steps:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                print(f"[push] {d.name} 실패: {' '.join(cmd[:2])} → {proc.stderr.strip()}", file=sys.stderr)
                failed += 1
                break
        else:
            sent = INBOX / "_sent" / d.name
            sent.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(d), str(sent))
            print(f"[push] {d.name} → {host}:{remote}")
    return 1 if failed else 0


def cmd_queue(_args) -> int:
    rows = [i for i in queue.items() if i["status"] not in ("planned", "rendered")]
    if not rows:
        print("자동 발행 원장이 비었습니다(이 머신에 원장이 없을 수도 — 원장은 맥에 있습니다)")
        return 0
    for i in sorted(rows, key=lambda r: r.get("scheduled_at") or r.get("published_at") or r["created_at"]):
        when = i.get("scheduled_at") or i.get("published_at") or i.get("slot") or ""
        where = ",".join(i.get("posted") or []) or ("→" + ",".join(i.get("platforms") or []))
        links = " ".join(((i.get("results") or {}).get(p) or {}).get("url", "") for p in (i.get("posted") or []))
        print(f"{i['id']}  {i['status']:<9} {when:<19}  {where:<22} {i.get('company', ''):<14} "
              f"{i['job_key']:<16} {links}")
    return 0


def cmd_requeue(args) -> int:
    targets = [i for i in queue.items() if i["status"] in ("rehearsed", "failed", "skipped")
               and (args.all_rehearsed and i["status"] == "rehearsed" or i["id"] in args.ids)]
    if not targets:
        print("되돌릴 항목이 없습니다(rehearsed·failed·skipped 만 됩니다)")
        return 2
    for i in targets:
        dup = next((queue.pending_for(i["job_key"], p) for p in i["platforms"]
                    if queue.pending_for(i["job_key"], p)), None)
        if dup:
            print(f"[requeue] {i['id']} 건너뜀 — {i['job_key']} 는 이미 줄 서 있음({dup['id']})")
            continue
        left = [p for p in i["platforms"] if p not in queue.published_platforms(i["job_key"])]
        if not left:
            print(f"[requeue] {i['id']} 건너뜀 — {i['job_key']} 는 두 곳 다 이미 올라감")
            continue
        # 성공한 플랫폼의 기록(results)은 지우지 않는다 — 다시 돌 때 그곳엔 안 올린다.
        queue.update(i["id"], status="approved", attempts=0, scheduled_at="",
                     event="requeued", detail=f"{i['status']} → approved ({', '.join(left)})")
        print(f"[requeue] {i['id']} {i['job_key']}  {i['status']} → approved  남은 곳: {', '.join(left)}")
    return 0


def cmd_token_refresh(_args) -> int:
    from datetime import datetime

    from publish import daemon
    cfg = load_config()
    conf = {**daemon.settings(cfg), "token_refresh_days": 10 ** 6}   # 만료일과 상관없이 지금
    log: list[str] = []
    out = daemon.refresh_token(datetime.now(), cfg, conf, log)
    print("\n".join(log) or "갱신하지 않음(토큰·token_expires_at 이 없거나 페이스북 로그인)")
    return 0 if out in ("refreshed", "") else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="publish.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check").set_defaults(fn=cmd_check)

    a = sub.add_parser("approve", help="포스터 한 장을 자동 발행 대상으로 승인한다")
    a.add_argument("job_key")
    a.add_argument("--image", default="", help="기본 out/<공고키>/brand_ig_portrait.jpg")
    a.add_argument("-p", "--platforms", default="instagram,facebook",
                   help=f"쉼표 구분. 가능: {','.join(PLATFORMS)}")
    a.add_argument("--caption-file", default="", help="캡션을 직접 쓴 파일(기본은 플랫폼별 자동 생성)")
    a.add_argument("--template", default="brand")
    a.add_argument("--note", default="")
    a.add_argument("--force", action="store_true", help="마감·중복 검사를 무시한다")
    a.set_defaults(fn=cmd_approve)

    c = sub.add_parser("approve-collection", help="카테고리 묶음을 승인한다(표지+여러 장)")
    c.add_argument("kind", choices=["week", "deadline", "role", "size", "stack", "newgrad"])
    c.add_argument("--value", default="", help="role: backend|frontend|data|infra|mobile / size: 대기업 / stack: React")
    c.add_argument("--since", default="", help="YYYY-MM-DD (week·deadline)")
    c.add_argument("--until", default="", help="YYYY-MM-DD (week·deadline)")
    c.add_argument("--limit", type=int, default=8, help="공고 수(표지 2장 제외, 최대 8)")
    c.add_argument("-p", "--platforms", default="instagram,facebook")
    c.add_argument("--note", default="")
    c.add_argument("--force", action="store_true")
    c.add_argument("--allow-generic", action="store_true",
                   help="전용 판 없는 회사도 기본 틀로 넣는다(기본은 전용 판만)")
    c.set_defaults(fn=cmd_approve_collection)

    u = sub.add_parser("push", help="승인 묶음을 맥으로 보낸다")
    u.add_argument("--host", default="")
    u.add_argument("--root", default="", help="원격 design-lab 경로(홈 기준)")
    u.set_defaults(fn=cmd_push)

    sub.add_parser("queue", help="자동 발행 원장").set_defaults(fn=cmd_queue)

    rq = sub.add_parser("requeue", help="rehearsed·failed·skipped 를 다시 승인 상태로")
    rq.add_argument("ids", nargs="*")
    rq.add_argument("--all-rehearsed", action="store_true")
    rq.set_defaults(fn=cmd_requeue)

    sub.add_parser("token-refresh", help="인스타 장기 토큰을 지금 갱신").set_defaults(fn=cmd_token_refresh)

    p = sub.add_parser("plan")
    p.add_argument("job_key")
    p.add_argument("-t", "--template", default="role_hero")
    p.add_argument("-p", "--platforms", default="instagram")
    p.add_argument("-f", "--formats", default="", help=f"쉼표 구분. 가능: {','.join(FORMATS)}")
    p.add_argument("--palette", default="")
    p.add_argument("--note", default="")
    p.set_defaults(fn=cmd_plan)

    for name, fn in (("render", cmd_render), ("caption", cmd_caption)):
        q = sub.add_parser(name)
        q.add_argument("item_id")
        q.set_defaults(fn=fn)

    r = sub.add_parser("publish")
    r.add_argument("item_id")
    r.add_argument("--live", action="store_true", help="진짜로 올린다")
    r.add_argument("--force", action="store_true", help="중복 발행 경고를 무시한다")
    r.set_defaults(fn=cmd_publish)

    s = sub.add_parser("ls")
    s.add_argument("--status", default="")
    s.set_defaults(fn=cmd_ls)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
