"""합격·입사 당시 나이 — 글쓴이가 밝힌 것만. 모델이 뽑은 값이 먼저, 없으면 본문에서 찾는다.

본문에서 찾는 것: '29살' · '만 31세' · '94년생'(사건 연도로 계산) · '30대 초반'(→32, 대략).
'3살 조카' 같은 남 얘기를 줄이려고 17~60 만 받고, '○○대'는 나 얘기 표지(저는·제가·나이·늦은…) 근처만 본다.
"""
from __future__ import annotations

import re
from statistics import median

_SAL = re.compile(r"(?<![\d.])(?:만\s*)?([1-5]\d)\s*(?:살|세(?!기|대))")
_BORN = re.compile(r"(?<!\d)(\d{2})\s*년생")
_DECADE = re.compile(r"(?<!\d)([2-5])0\s*대\s*(초반|중반|후반)?")
_ME = re.compile(r"저는|제가|나이|늦은|늦게|늦깎이|당시|입사|합격|취업|이직|전향|시작")
_MID = {"초반": 2, "중반": 5, "후반": 8, None: 5}
BANDS = ["20대 초반", "20대 중반", "20대 후반", "30대 초반", "30대 중반", "30대 후반", "40대 이상"]


def from_text(body: str, year: int | None) -> tuple[int | None, str | None]:
    """(나이, 근거) — 근거는 'stated'(숫자로 밝힘) 또는 'approx'(○○대)."""
    body = body or ""
    ages = [int(m.group(1)) for m in _SAL.finditer(body) if 17 <= int(m.group(1)) <= 60]
    if ages:
        return ages[0], "stated"
    if year:
        for m in _BORN.finditer(body):
            yy = int(m.group(1))
            born = 1900 + yy if yy > 30 else 2000 + yy
            a = year - born
            if 17 <= a <= 60:
                return a, "stated"
    for m in _DECADE.finditer(body):
        near = body[max(0, m.start() - 40): m.end() + 40]
        if _ME.search(near):
            return int(m.group(1)) * 10 + _MID[m.group(2)], "approx"
    return None, None


def band(a: int | None) -> str | None:
    if not isinstance(a, int):
        return None
    if a >= 40:
        return "40대 이상"
    if a < 20:
        return "20대 초반"
    d, r = divmod(a, 10)
    return f"{d}0대 " + ("초반" if r <= 3 else "중반" if r <= 6 else "후반")


def stats(ages: list[int]) -> dict | None:
    ages = [a for a in ages if isinstance(a, int)]
    if not ages:
        return None
    c = {b: 0 for b in BANDS}
    for a in ages:
        c[band(a)] += 1
    return {"n": len(ages), "median": median(ages), "min": min(ages), "max": max(ages),
            "bands": [[b, v, round(100 * v / len(ages))] for b, v in c.items()]}


# ── 이미 뽑아 둔 경험담에 나이를 덧붙인다(본문에 나이 단서가 있는 글만, 단서 주변 글만 모델에 보낸다) ──
import json as _json
from . import store as _store

AGES = _store.DIR / "age.jsonl"          # {id, age, how}
_PROMPT = """다음은 개발자 취업·이직 경험담에서 나이가 나오는 부분만 잘라 온 것이다. 사건 연도: {year}.
글쓴이 본인이 합격·입사·이직한 '그 당시' 나이를 JSON 으로 답하라: {{"age": 숫자 또는 null, "how": "밝힘|계산|대략|null"}}
- 글쓴이 본인 나이만. 다른 사람·평균·'20살에 대학 갔다' 같은 다른 시점 나이는 버리고, 그것밖에 없으면 null.
- '96년생'은 사건 연도로 계산(how=계산). '30대 초반'이면 32(how=대략). 글을 쓰는 지금 나이라도 합격 직후 회고면 그 값을 쓴다.

{snips}"""


def _snips(body: str) -> str:
    spans = sorted({(max(0, m.start() - 160), m.end() + 80) for rx in (_SAL, _BORN, _DECADE) for m in rx.finditer(body)})
    out, last = [], -1
    for a, b in spans:
        if a <= last:
            continue
        out.append("…" + body[a:b].replace("\n", " ") + "…")
        last = b
    return "\n".join(out[:8])


def read_ages() -> dict:
    out = {}
    for l in AGES.read_text(encoding="utf-8").splitlines() if AGES.exists() else []:
        try:
            d = _json.loads(l)
            out[d["id"]] = d
        except (ValueError, KeyError):
            pass
    return out


def backfill(limit: int = 0) -> int:
    from .extract import _ask
    done = read_ages()
    n = 0
    for r in _store.read_paths():
        if not r.get("is_story") or r["id"] in done:
            continue
        if isinstance((r.get("background") or {}).get("age"), int):
            continue
        raw = _store.load_json(_store.RAW / f"{r['id']}.json", {})
        body = raw.get("body") or ""
        sn = _snips(body)
        year = r.get("year") if isinstance(r.get("year"), int) else (int(raw.get("date", "")[:4]) if raw.get("date", "")[:4].isdigit() else None)
        rec = {"id": r["id"], "age": None, "how": None}
        if sn:
            try:
                d = _json.loads(_ask(_PROMPT.format(year=year or "모름", snips=sn), "local", fmt="json"))
                a = d.get("age")
                if isinstance(a, (int, float)) and 17 <= a <= 60:
                    rec.update(age=int(a), how=d.get("how"))
            except Exception as e:  # noqa: BLE001
                print(f"  ! {r['id']}: {e}", flush=True)
                continue
        with AGES.open("a", encoding="utf-8") as w:
            w.write(_json.dumps(rec, ensure_ascii=False) + "\n")
        n += bool(sn)
        if limit and n >= limit:
            break
    print(f"나이 확인 {n}건", flush=True)
    return n


def of(r: dict, ages: dict | None = None) -> int | None:
    a = (r.get("background") or {}).get("age")
    if isinstance(a, int) and 17 <= a <= 60:
        return a
    return ((ages or {}).get(r.get("id")) or {}).get("age")


if __name__ == "__main__":
    import sys
    backfill(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
