"""하드웨어 엔진 산출물 검증 — 커밋 전에 돌린다.

    python hw-engine/validate.py          # 형식·참조 검사. 오류가 있으면 1 로 끝난다
    python hw-engine/validate.py --gaps   # 위 + 다음 사이클이 할 일(가격 없음·섞인 매물·확인 전·오래됨)

엔진은 "다음에 뭘 하지"를 사람에게 묻지 않는다. PROMPT.md 의 사다리가 이 출력을 읽고 정한다.
jsonschema 가 없어도 돈다 — 필요한 검사는 여기 손으로 적었다(맥·윈도우 어디서나 같은 결과).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "jd-viewer" / "public" / "hardware"
VIEWER_LIB = ROOT / "jd-viewer" / "src" / "lib" / "hardware.ts"

CATS = {"gpu", "cpu", "ram", "ssd", "hdd", "mainboard", "psu", "cooler", "case"}
ID_PREFIX = {"mainboard": "mb"}
CONF = {"seed", "low", "medium", "high"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STALE_DAYS = 90
MIXED_RATIO = 1.6  # 중앙값이 최저가의 1.6배를 넘으면 다른 물건이 섞였다고 본다


def load(name: str):
    return json.loads((HW / name).read_text(encoding="utf-8"))


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def _hit(name: str, rule: dict) -> bool:
    """뷰어 offerMatches 와 같은 규칙 — 'A|B' 는 둘 중 하나."""
    has = lambda t: any(_norm(x) in name for x in t.split("|"))
    return all(has(t) for t in rule.get("must", [])) and not any(has(t) for t in rule.get("not", []))


def check_models(ids: set[str], cats: dict[str, str], prices: dict) -> tuple[list[str], dict[str, int]]:
    """public/hardware/models/<부품 id>.json — 제품(보드 파트너 모델) 단위 스펙.

    돌려주는 두 번째 값은 부품별 '스펙 조사 전 매물 수' — 다음 사이클의 일감이다.
    한 매물이 두 제품에 걸리면 이름 규칙이 겹친 것이라 오류로 본다(가격이 두 번 세어진다).
    """
    errs: list[str] = []
    todo: dict[str, int] = {}
    mdir = HW / "models"
    files = {f.stem: f for f in mdir.glob("*.json")} if mdir.exists() else {}
    for pid in ids:
        offers = (prices.get("parts", {}).get(pid) or {}).get("offers") or []
        models = []
        if pid in files:
            try:
                doc = json.loads(files[pid].read_text(encoding="utf-8"))
            except ValueError as e:
                errs.append(f"models/{pid}.json: JSON 이 깨졌다 {e}")
                continue
            if doc.get("part") != pid:
                errs.append(f"models/{pid}.json: part 가 파일 이름과 다르다")
            models = doc.get("models") or []
            seen = set()
            for m in models:
                mid = m.get("id", "?")
                if mid in seen:
                    errs.append(f"models/{pid}: 제품 id 중복 {mid}")
                seen.add(mid)
                for k in ("name", "brand", "match", "specs", "sources", "confidence", "checked_at"):
                    if k not in m:
                        errs.append(f"models/{pid}/{mid}: {k} 없음")
                if not (m.get("match") or {}).get("must"):
                    errs.append(f"models/{pid}/{mid}: match.must 가 비면 모든 매물을 가져간다")
                if m.get("confidence") not in {"low", "medium", "high"}:
                    errs.append(f"models/{pid}/{mid}: confidence 는 low·medium·high")
                if not m.get("sources"):
                    errs.append(f"models/{pid}/{mid}: 출처가 없다")
                for s in m.get("sources") or []:
                    if "danawa.com" in str(s.get("url", "")):
                        errs.append(f"models/{pid}/{mid}: 다나와는 스펙 출처로 쓰지 않는다 — 제조사 공식 페이지로")
        for o in offers:
            name = _norm(o["name"])
            hits = [m["id"] for m in models if _hit(name, m.get("match") or {})]
            if len(hits) > 1:
                errs.append(f"models/{pid}: 매물 '{o['name']}' 이 제품 {hits} 에 동시에 걸린다")
            if not hits:
                todo[pid] = todo.get(pid, 0) + 1
    for stem in files:
        if stem not in ids:
            errs.append(f"models/{stem}.json: 그런 부품이 없다")
    return errs, todo


def check_guide(ids: set[str]) -> list[str]:
    """public/hardware/guide.json — 판매 형태(정품·병행…)·유통사·내구성 메모.

    소비자가 무엇을 살지 가르는 말이라 출처 없는 문장을 싣지 않는다.
    """
    path = HW / "guide.json"
    if not path.exists():
        return []
    errs: list[str] = []
    try:
        g = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"guide.json: JSON 이 깨졌다 {e}"]

    def srcs(where: str, xs) -> None:
        if not xs:
            errs.append(f"guide.json {where}: 출처가 없다")
        for s in xs or []:
            if not str(s.get("url", "")).startswith(("http://", "https://")):
                errs.append(f"guide.json {where}: 출처 url 이 이상하다")
            if "danawa.com" in str(s.get("url", "")):
                errs.append(f"guide.json {where}: 다나와 문구를 출처로 쓰지 않는다")

    for f in g.get("forms", []):
        for k in ("key", "label", "tokens", "plain", "official"):
            if k not in f:
                errs.append(f"guide.json forms/{f.get('key')}: {k} 없음")
        srcs(f"forms/{f.get('key')}", f.get("sources"))
    for d in g.get("distributors", []):
        if not d.get("name"):
            errs.append("guide.json distributors: 이름 없는 유통사")
        srcs(f"distributors/{d.get('name')}", d.get("sources"))
    for n in g.get("durability", []):
        for a in n.get("applies_to", []):
            if a.startswith("category:"):
                if a.split(":", 1)[1] not in CATS:
                    errs.append(f"guide.json durability/{n.get('key')}: 모르는 분류 {a}")
            elif a not in ids:
                errs.append(f"guide.json durability/{n.get('key')}: 모르는 부품 {a}")
        if n.get("level") not in ("주의", "참고"):
            errs.append(f"guide.json durability/{n.get('key')}: level 은 주의·참고")
        srcs(f"durability/{n.get('key')}", n.get("sources"))
    return errs


def spec_keys() -> dict[str, set[str]]:
    """뷰어 표의 열(SPEC_COLUMNS) — 부품 specs 에 이 키가 없으면 표에 '—' 로 나온다."""
    src = VIEWER_LIB.read_text(encoding="utf-8")
    block = src.split("export const SPEC_COLUMNS", 1)[1].split("\n}\n", 1)[0]
    out: dict[str, set[str]] = {}
    for m in re.finditer(r"\n  (\w+): \[(.*?)\n  \]", block, re.S):
        out[m.group(1)] = set(re.findall(r"key: '(\w+)'", m.group(2)))
    return out


def check() -> tuple[list[str], list[dict], dict, dict, dict]:
    errs: list[str] = []
    parts_doc, index, bench = load("parts.json"), load("index.json"), load("bench.json")
    try:
        prices = load("prices.json")
    except (OSError, ValueError):
        prices = {"parts": {}}
    parts = parts_doc.get("parts", [])
    ids = set()
    cols = spec_keys()
    for p in parts:
        pid = p.get("id", "?")
        if pid in ids:
            errs.append(f"{pid}: id 중복")
        ids.add(pid)
        cat = p.get("category")
        if cat not in CATS:
            errs.append(f"{pid}: 모르는 분류 {cat!r}")
            continue
        if not pid.startswith(ID_PREFIX.get(cat, cat) + "-"):
            errs.append(f"{pid}: id 는 '{ID_PREFIX.get(cat, cat)}-' 로 시작해야 한다")
        for k in ("name", "maker", "status", "specs", "perf", "sources", "checked_at"):
            if k not in p:
                errs.append(f"{pid}: {k} 없음")
        perf = p.get("perf") or {}
        if not isinstance(perf.get("index"), (int, float)):
            errs.append(f"{pid}: perf.index 가 숫자가 아니다")
        if perf.get("confidence") not in CONF:
            errs.append(f"{pid}: perf.confidence 는 {sorted(CONF)} 중 하나")
        if cat == "cpu" and not isinstance(perf.get("multi"), (int, float)):
            errs.append(f"{pid}: CPU 는 perf.multi 가 있어야 한다(빌드 시간 시뮬레이션)")
        if "tier" in p or "tier" in perf:
            errs.append(f"{pid}: 등급을 부품에 적지 않는다 — index.json 문턱으로 계산한다")
        if not DATE_RE.match(str(p.get("checked_at", ""))):
            errs.append(f"{pid}: checked_at 형식(YYYY-MM-DD)")
        for s in p.get("sources") or []:
            if not str(s.get("url", "")).startswith(("http://", "https://")):
                errs.append(f"{pid}: 출처 url 이 이상하다 {s.get('url')!r}")
            if "danawa.com" in str(s.get("url", "")):
                errs.append(f"{pid}: 다나와는 스펙 출처로 쓰지 않는다(가격·링크만) — 제조사 자료로")
        missing = cols.get(cat, set()) - set((p.get("specs") or {}).keys())
        if missing:
            errs.append(f"{pid}: specs 에 표 열 {sorted(missing)} 이 없다")
        q = p.get("price_query")
        if q is not None and not q.get("q"):
            errs.append(f"{pid}: price_query.q 가 비었다")
    for c in index.get("categories", []):
        mins = [t["min"] for t in c.get("tiers", [])]
        if mins != sorted(mins, reverse=True) or (mins and mins[-1] != 0):
            errs.append(f"index.json {c.get('key')}: 등급 문턱은 내림차순이고 마지막이 0 이어야 한다")
    if {c.get("key") for c in index.get("categories", [])} != CATS:
        errs.append("index.json: 분류가 아홉 개와 다르다")
    anchor = bench.get("image", {}).get("anchor", {}).get("gpu")
    if anchor not in ids:
        errs.append(f"bench.json: 이미지 기준 GPU {anchor!r} 가 parts 에 없다")
    for g in bench.get("games", []):
        for k in ("gpu100", "vram"):
            if set(g.get(k, {})) != {"fhd", "qhd", "uhd"}:
                errs.append(f"bench.json {g.get('key')}: {k} 는 fhd·qhd·uhd 셋")
    errs.extend(check_guide(ids))
    merrs, todo = check_models(ids, {p["id"]: p.get("category") for p in parts}, prices)
    errs.extend(merrs)
    prices["_model_todo"] = todo
    stray = set(prices.get("parts", {})) - ids
    if stray:
        errs.append(f"prices.json: 목록에 없는 부품의 가격 {sorted(stray)[:5]} — 부품 id 를 바꿨나?")
    return errs, parts, index, bench, prices


def gaps(parts: list[dict], bench: dict, prices: dict) -> None:
    book = prices.get("parts", {})
    today = date.today()
    no_price, mixed, seed, stale = [], [], {}, []
    for p in parts:
        if p.get("status") == "legacy":
            continue
        rec = book.get(p["id"]) or {}
        if p.get("price_query") and rec.get("min") is None:
            no_price.append(p["id"])
        elif rec.get("min") and p.get("price_basis") != "median" and rec.get("median", 0) / rec["min"] > MIXED_RATIO:
            mixed.append(f"{p['id']} (최저 {rec['min']:,} · 중앙 {rec['median']:,})")
        if (p.get("perf") or {}).get("confidence") == "seed":
            seed.setdefault(p["category"], []).append(p["id"])
        try:
            if (today - datetime.strptime(p["checked_at"], "%Y-%m-%d").date()).days > STALE_DAYS:
                stale.append(p["id"])
        except (KeyError, ValueError):
            pass
    bench_seed = [g["key"] for g in bench.get("games", []) if g.get("confidence") == "seed"]
    for k in ("image", "dev"):
        if bench.get(k, {}).get("confidence") == "seed":
            bench_seed.append(k)

    print(f"\n── 다음에 할 일 (가격 기준일 {prices.get('day', '없음')}) ──")
    print(f"2. 가격 없음 {len(no_price)}: {', '.join(no_price) or '-'}")
    print(f"3. 섞인 매물 {len(mixed)}: {'; '.join(mixed) or '-'}")
    total_seed = sum(len(v) for v in seed.values())
    print(f"4. 확인 전(seed) {total_seed}: " + (" · ".join(f"{c} {len(v)}" for c, v in seed.items()) or "-"))
    print(f"5. 기준값 seed {len(bench_seed)}: {', '.join(bench_seed) or '-'}")
    todo = prices.get("_model_todo", {})
    top = sorted(todo.items(), key=lambda kv: -kv[1])[:8]
    print(f"6. 스펙 조사 전 매물 {sum(todo.values())}: " + (", ".join(f"{k} {v}" for k, v in top) or "-"))
    print(f"7. {STALE_DAYS}일 넘은 확인 {len(stale)}: {', '.join(stale[:10]) or '-'}")
    # 완제품 조립PC 가 쓰는데 우리 목록에 없는 CPU·그래픽카드 — 많이 쓰이는 것부터 더할 부품이다
    try:
        pb = json.loads((HW / "prebuilt.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pb = {}
    miss: dict[str, int] = {}
    for it in (pb.get("items") or {}).values():
        comp, mapped = it.get("comp") or {}, it.get("mapped") or {}
        for c in ("cpu", "gpu"):
            t = comp.get(c)
            if t and not mapped.get(c) and "내장" not in str(t) and it.get("source") == "danawa":
                miss[f"{c}:{t}"] = miss.get(f"{c}:{t}", 0) + 1
        chip = comp.get("chipset")
        if chip and not mapped.get("mainboard") and it.get("source") == "danawa":
            miss[f"mainboard:{chip}"] = miss.get(f"mainboard:{chip}", 0) + 1
    top = sorted(miss.items(), key=lambda kv: -kv[1])[:10]
    print(f"8. 완제품이 쓰는데 목록에 없는 부품 {len(miss)}: " + (", ".join(f"{k}×{v}" for k, v in top) or "-"))


def main(argv: list[str]) -> int:
    errs, parts, _index, bench, prices = check()
    for e in errs:
        print(f"✗ {e}")
    print(f"부품 {len(parts)} · 오류 {len(errs)}")
    if "--gaps" in argv:
        gaps(parts, bench, prices)
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
