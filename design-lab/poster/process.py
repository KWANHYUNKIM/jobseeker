"""프로세스 — 판 하나가 어떻게 만들어져 어디로 나가는지, 그리고 지금 어디까지 왔는지.

8780 의 '프로세스' 칸이 읽는다.

**여기에 절차를 적지 않는다.** 적으면 문서와 화면이 따로 늙는다. 전부 원본에서 읽는다:

    제작 9단계     ← BRAND_RESEARCH.md 의 '1. 순서' 표
    발행 상태      ← publish/queue.py 의 문서주석 갈래 그림 + PENDING/FINAL 상수
    스튜디오 등록  ← poster/templates.py 의 TEMPLATES
    지금 어디까지  ← brands/*.json · poster/templates/ · assets/ · out/ 의 실물

그래서 절차서를 고치면 화면이 따라 바뀐다. 반대로 화면만 고치는 길은 없다 —
새 단계를 넣고 싶으면 BRAND_RESEARCH.md 의 표에 줄을 더하고, 그 단계가 '됐다'를
무엇으로 볼지 여기 STAGE_PROBE 에 한 줄 더한다. 표에만 있고 probe 가 없으면
화면은 그 단계를 '셀 수 없음' 으로 표시한다(조용히 통과시키지 않는다).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import brands, jobsource, templates

LAB_DIR = Path(__file__).resolve().parent.parent
DOC = LAB_DIR / "BRAND_RESEARCH.md"
QUEUE_PY = LAB_DIR / "publish" / "queue.py"
OUT = LAB_DIR / "out"

_index_cache: tuple[float, dict] | None = None


# ---------------------------------------------------------------- 원본 읽기

def steps() -> list[dict]:
    """BRAND_RESEARCH.md '1. 순서' 표 → [{no, name, artifact}]."""
    if not DOC.is_file():
        return []
    body = DOC.read_text(encoding="utf-8")
    m = re.search(r"^##\s*1\.\s*순서.*?$", body, re.M)
    if not m:
        return []
    rows = []
    for line in body[m.end():].splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if rows:          # 표가 끝났다
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or set(cells[0]) <= set("-: "):
            continue          # 머리줄·구분줄
        no = cells[0]
        if not no.isdigit():
            continue
        rows.append({
            "no": int(no),
            "name": _plain(cells[1]),
            "artifact": _plain(cells[2]),
            "key": STAGE_ORDER[int(no) - 1] if int(no) <= len(STAGE_ORDER) else "",
        })
    return rows


def publish_flow() -> dict:
    """publish/queue.py 의 문서주석 갈래 그림과 상태 상수. 그림은 원문 그대로 보여 준다."""
    out = {"diagram": [], "pending": [], "final": [], "note": ""}
    if not QUEUE_PY.is_file():
        return out
    src = QUEUE_PY.read_text(encoding="utf-8")
    doc = re.match(r'\s*"""(.*?)"""', src, re.S)
    if doc:
        lines = doc.group(1).splitlines()
        # '상태는 두 갈래다.' 아래의 그림 블록 — 들여쓴 줄이 이어지는 동안
        start = next((i for i, l in enumerate(lines) if "갈래" in l), None)
        if start is not None:
            block = []
            for l in lines[start + 1:]:
                if l.strip() and not l.startswith(" "):
                    break
                if l.strip() or block:
                    block.append(l.rstrip())
            out["diagram"] = [l for l in block if l.strip()]
            tail = [l.strip() for l in lines[start + 1 + len(block):] if l.strip()]
            out["note"] = " ".join(tail)
    for name in ("PENDING", "FINAL"):
        m = re.search(rf"^{name}\s*=\s*\(([^)]*)\)", src, re.M)
        if m:
            out[name.lower()] = re.findall(r'"([^"]+)"', m.group(1))
    return out


def _plain(s: str) -> str:
    return re.sub(r"[`*]", "", s).strip()


# ---------------------------------------------------------------- 지금 어디까지

#: BRAND_RESEARCH 표의 줄에 붙는 이름. 표에 줄을 더하면 여기에도 더하고 _probe 에도 더한다.
STAGE_ORDER = ["jobs", "signature", "points", "fonts", "palette",
               "images", "frame", "proof", "record", "studio"]


def _files_exist(spec) -> bool:
    """embed_fonts / images 처럼 '경로 또는 경로 목록' 을 받아 전부 실재하는지."""
    paths = []
    for v in (spec or {}).values():
        entries = [v] if isinstance(v, str) else (v if isinstance(v, list) else [v])
        for e in entries:
            p = e if isinstance(e, str) else (e or {}).get("src")
            if p:
                paths.append(p)
    return bool(paths) and all((LAB_DIR / p).is_file() for p in paths)


def _has_type_plan(tp) -> bool:
    """글자 계획(BRAND_RESEARCH 4-1절)이 네 칸을 다 채웠나."""
    if not isinstance(tp, dict):
        return False
    if not tp.get("verbatim") or not tp.get("scale"):
        return False
    hi, im = tp.get("highlight"), tp.get("as_image")
    if not isinstance(hi, dict) or not hi.get("how"):
        return False
    # 그림이 되는 글자는 없어도 된다. 다만 '없다'는 것과 '안 적었다'는 다르다.
    if not isinstance(im, dict):
        return False
    return bool(im.get("what") or im.get("why_none"))


#: 매체의 네 칸(BRAND_RESEARCH 2-1절). 앞 셋이 판을 서로 안 닮게 하는 축이다.
MEDIUM_AXES = ("ground", "text_load", "hand")


def _has_medium(m) -> bool:
    return isinstance(m, dict) and all(m.get(k) for k in (*MEDIUM_AXES, "dominant", "why"))


def mediums() -> dict:
    """회사마다 고른 매체와, 겹친 것. 겹침이 곧 '판이 서로 닮았다' 는 뜻이다."""
    rows, buckets = [], {}
    for path in sorted(brands.BRANDS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        m = (data.get("signature") or {}).get("medium") or {}
        axes = tuple(m.get(k) or "—" for k in MEDIUM_AXES)
        rows.append({"name": path.stem, "axes": dict(zip(MEDIUM_AXES, axes)),
                     "dominant": m.get("dominant", ""), "filled": _has_medium(m)})
        buckets.setdefault(axes, []).append(path.stem)
    clashes = [{"axes": dict(zip(MEDIUM_AXES, k)), "companies": v}
               for k, v in buckets.items() if len(v) > 1]
    clashes.sort(key=lambda c: -len(c["companies"]))
    return {"rows": rows, "clashes": clashes,
            "distinct": len(buckets), "total": len(rows)}


def _probe(data: dict, keys: list[str], names: list[str], registered: set[str]) -> dict:
    ui = data.get("ui") or {}
    sig = data.get("signature") or {}
    frame = data.get("frame") or ""
    return {
        # 1 공고 전문 — 이 판을 쓸 데가 있나(모집중 공고)
        "jobs": len(keys) > 0,
        # 2 시그니처 — 고른 물건·근거·그 물건이 부르는 매체(2-1절)가 다 있나.
        #    매체를 안 적으면 판은 반드시 다른 판과 닮는다 — 그래서 여기서 같이 본다.
        "signature": bool(sig.get("id") and sig.get("evidence")) and _has_medium(sig.get("medium")),
        # 3 보조 포인트
        "points": bool(data.get("points")),
        # 4 서체와 글자 세우기 — 조사 기록·실제 파일·글자 계획이 셋 다 있나.
        #    type_plan 은 '비어 있지 않다' 가 아니라 네 칸을 다 채웠는지로 본다 —
        #    as_image 는 '없음' 도 답이지만, 왜 없는지는 적어야 한다(4-1절).
        "fonts": (bool(ui.get("fonts_research"))
                  and _files_exist(ui.get("embed_fonts"))
                  and _has_type_plan(ui.get("type_plan"))),
        # 5 색 — 팔레트와 '어디서 봤나' 가 둘 다 있나
        "palette": bool(data.get("palette")) and bool(ui.get("observed_at")),
        # 6 이미지 — 넣었고 파일이 실재하나
        "images": _files_exist(ui.get("images") or data.get("images")),
        # 7 전용 판 — frame 이 가리키는 파일이 실재하나
        "frame": bool(frame) and (templates.TPL_DIR / frame).is_file(),
        # 8 검증 — 그 회사 공고로 실제 렌더가 나왔나
        "proof": any((OUT / k).is_dir() and any((OUT / k).glob("brand_*.jpg")) for k in keys),
        # 9 기록
        "record": any((OUT / k).is_dir() and any((OUT / k).glob("RECORD_v*.md")) for k in keys),
        # 10 스튜디오 — TEMPLATES 에 올라가 공고에서 고를 수 있나
        "studio": any(n in registered for n in names),
    }


def _index() -> dict:
    global _index_cache
    mt = jobsource.INDEX.stat().st_mtime if jobsource.INDEX.is_file() else 0.0
    if _index_cache and _index_cache[0] == mt:
        return _index_cache[1]
    payload = jobsource.load_index()
    _index_cache = (mt, payload)
    return payload


def _company_keys() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for j in _index().get("jobs", []):
        if j.get("status") == "active":
            out.setdefault(j["company"], []).append(j["key"])
    return out


def companies() -> list[dict]:
    """전용 판을 만든(또는 만들다 만) 회사마다 어느 단계까지 왔는지."""
    by_company = _company_keys()
    registered = {c for meta in templates.TEMPLATES.values()
                  for c in (meta.get("company") or [])}
    rows = []
    for path in sorted(brands.BRANDS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        names = [path.stem, *(data.get("names") or [])]
        keys, listed = [], ""
        for n in names:
            if n in by_company:
                keys += by_company[n]
                listed = listed or n
        stages = _probe(data, keys, names, registered)
        rows.append({
            "name": path.stem,
            "listed_as": listed,
            "open": len(keys),
            "stages": stages,
            "done": sum(1 for v in stages.values() if v),
            "researched_at": data.get("researched_at", ""),
        })
    rows.sort(key=lambda r: (-r["done"], -r["open"], r["name"]))
    return rows


def next_up(limit: int = 8) -> list[dict]:
    """전용 판이 없는데 모집중 공고가 많은 회사 — 다음에 만들 것."""
    have = set()
    for path in brands.BRANDS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("frame"):
            have.update([path.stem, *(data.get("names") or [])])
    rows = [{"company": c, "open": len(ks)}
            for c, ks in _company_keys().items() if c not in have]
    rows.sort(key=lambda r: -r["open"])
    return rows[:limit]


def queue_counts() -> dict:
    from publish import queue
    counts: dict[str, int] = {}
    for it in queue.items():
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    return counts


def snapshot() -> dict:
    rows = companies()
    step_rows = steps()
    # 단계마다 '몇 곳이 통과했나'. probe 가 없는 단계는 셀 수 없다고 말한다.
    for s in step_rows:
        k = s["key"]
        s["done"] = sum(1 for r in rows if r["stages"].get(k)) if k else None
    return {
        "sources": {
            "steps": "BRAND_RESEARCH.md · 1. 순서",
            "publish": "publish/queue.py",
            "studio": "poster/templates.py · TEMPLATES",
        },
        "steps": step_rows,
        "publish": publish_flow(),
        "queue_counts": queue_counts(),
        "companies": rows,
        "company_total": len(rows),
        "studio_total": len(templates.TEMPLATES),
        "next": next_up(),
        "mediums": mediums(),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "mediums":
        m = mediums()
        print(f"[mediums] 서로 다른 조합 {m['distinct']} / 회사 {m['total']}곳")
        for r in m["rows"]:
            a = r["axes"]
            mark = "" if r["filled"] else "  ← 안 적음"
            print(f"  {r['name']:12s} {a['ground']:8s} {a['text_load']:9s} {a['hand']:12s} {r['dominant'][:18]}{mark}")
        for c in m["clashes"]:
            a = c["axes"]
            print(f"  겹침 ({a['ground']}/{a['text_load']}/{a['hand']}) — {', '.join(c['companies'])}")
        raise SystemExit(0)
    snap = snapshot()
    print(f"[process] 제작 {len(snap['steps'])}단계 · 회사 {snap['company_total']}곳 "
          f"· 스튜디오 {snap['studio_total']}종")
    for s in snap["steps"]:
        mark = "-" if s["done"] is None else f"{s['done']}/{snap['company_total']}"
        print(f"  {s['no']}. {s['name'][:38]:40s} {mark}")
    print(f"[process] 큐 {snap['queue_counts']}")
