"""8780 /design 화면이 읽고 쓰는 것 — 시안·교훈·출처를 한 번에, 판정은 사람이 누른 그대로."""
from __future__ import annotations

from pathlib import Path

from . import db

LAB_DIR = Path(__file__).resolve().parent.parent
OUT = LAB_DIR / "out"


def _url(path: Path) -> str | None:
    """out/ 아래 파일 → 8780 이 내주는 /out/… 주소. out 이 다른 드라이브로 이어져 있어도 맞춘다."""
    for root in (OUT, OUT.resolve()):
        try:
            return "/out/" + path.relative_to(root).as_posix()
        except ValueError:
            continue
    return None


def snapshot(limit: int = 12) -> dict:
    trials = []
    for t in db.trials(limit):
        d = Path(t["out_dir"])
        shots = sorted(d.glob("*.jpg")) if d.is_dir() else []
        votes = {v["slide"]: v for v in (t["verdicts"] or [])}
        trials.append({
            "id": t["id"], "corner": t["corner"], "rendered_at": t["rendered_at"].isoformat(),
            "release": t["release"], "release_note": t["release_note"],
            "direction": {k: t["direction"].get(k) for k in ("season", "photo", "palette", "color_why", "trend")},
            "lessons": t["lessons"] or [],
            "slides": [{"no": i, "url": _url(p), **({"verdict": votes[i]["verdict"], "reason": votes[i]["reason"]}
                                                   if i in votes else {})} for i, p in enumerate(shots, 1)],
            "overall": votes.get(0),
        })
    return {"trials": trials, "lessons": [_plain(l) for l in db.lessons(("active", "candidate"))],
            "sources": [_plain(x) for x in db.sources()]}


def _plain(row: dict) -> dict:
    """DB 행의 시각 칸(created_at 등)은 JSON 이 못 싣는다 — ISO 문자열로."""
    return {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in row.items()}


def post(path: str, p: dict) -> dict:
    if path == "/api/design/verdict":
        db.verdict(int(p["trial"]), int(p["slide"]), int(p["verdict"]), (p.get("reason") or "").strip())
        return {"ok": True}
    if path == "/api/design/release":
        db.release(int(p["trial"]), bool(p["ok"]), (p.get("note") or "").strip())
        return {"ok": True}
    raise KeyError(path)
