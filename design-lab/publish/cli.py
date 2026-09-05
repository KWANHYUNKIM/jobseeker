"""발행 파이프라인 CLI.

    python -m publish.cli check                                  자격 점검
    python -m publish.cli plan wanted-364663 -t role_hero -p instagram,linkedin
    python -m publish.cli render <item-id>                       큐 항목의 이미지를 굽는다
    python -m publish.cli caption <item-id>                      플랫폼별 캡션 미리보기
    python -m publish.cli publish <item-id>                      기본 dry-run
    python -m publish.cli publish <item-id> --live               진짜로 올린다
    python -m publish.cli ls [--status planned]

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
        res = pub.publish(image=image, caption=captions.build(spec, platform),
                          link=spec.get("url", ""), dry_run=dry)
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


def main() -> int:
    ap = argparse.ArgumentParser(prog="publish.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check").set_defaults(fn=cmd_check)

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
