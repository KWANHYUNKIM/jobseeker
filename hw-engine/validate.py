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
MIXED_RATIO = 1.6
CLASS_CATS = {"mainboard", "psu", "cooler", "case"}  # 중앙값이 최저가의 1.6배를 넘으면 다른 물건이 섞였다고 본다


def load(name: str):
    return json.loads((HW / name).read_text(encoding="utf-8"))


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def _hit(name: str, rule: dict) -> bool:
    """뷰어 offerMatches 와 같은 규칙 — 'A|B' 는 둘 중 하나."""
    has = lambda t: any(_norm(x) in name for x in t.split("|"))
    return all(has(t) for t in rule.get("must", [])) and not any(has(t) for t in rule.get("not", []))


FAN_POS = {"front", "side", "bottom", "top", "rear"}
INTAKE_PANELS = {"메시", "틈새", "막힘"}


def _check_case_specs(s: dict) -> list[str]:
    """케이스 제품 — 크기·팬 배치는 뷰어가 계산(부피·흡기/배기 수·열 빼기)에 쓰니 형식이 맞아야 한다.
    모르는 값은 null 로 둔다. 팬 목록은 null(모름)과 [](기본 팬 없음)이 다르다."""
    errs = []
    for k in ("width_mm", "depth_mm", "height_mm", "max_gpu_mm", "max_cooler_mm", "max_radiator_mm"):
        v = s.get(k)
        if v is not None and not (isinstance(v, (int, float)) and 0 < v < 1000):
            errs.append(f"{k} 는 mm 숫자(또는 null)")
    for k in ("fans_included", "fan_mounts"):
        fans = s.get(k)
        if fans is None:
            continue
        if not isinstance(fans, list):
            errs.append(f"{k} 는 [{{pos, mm, n}}] 목록(또는 null)")
            continue
        for f in fans:
            if f.get("pos") not in FAN_POS or not isinstance(f.get("n"), int) or f["n"] < 1 or not f.get("mm"):
                errs.append(f"{k}: {f} — pos 는 front·side·bottom·top·rear, n 은 1 이상, mm 필수")
    inc, mounts = s.get("fans_included"), s.get("fan_mounts")
    if isinstance(inc, list) and isinstance(mounts, list) and mounts:
        for pos in FAN_POS:
            a = sum(f.get("n", 0) for f in inc if f.get("pos") == pos)
            b = sum(f.get("n", 0) for f in mounts if f.get("pos") == pos)
            if a > b:
                errs.append(f"{pos} 기본 팬 {a}개가 그 자리 수 {b}보다 많다(fan_mounts 는 차 있는 자리까지 센다)")
    if s.get("intake_panel") not in INTAKE_PANELS | {None}:
        errs.append("intake_panel 은 메시·틈새·막힘(또는 null)")
    return errs


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
                img = m.get("image")
                if img:
                    if not all(img.get(k) for k in ("url", "credit", "page")):
                        errs.append(f"models/{pid}/{mid}: image 는 url·credit·page 가 다 있어야 한다(출처 표시)")
                    if any(h in str(img.get("url", "")) + str(img.get("page", "")) for h in ("danawa", "danuri", "coupang", "naver")):
                        errs.append(f"models/{pid}/{mid}: 사진은 제조사 공식 페이지 것만 — 판매처 이미지는 쓰지 않는다")
                for s in m.get("sources") or []:
                    if "danawa.com" in str(s.get("url", "")):
                        errs.append(f"models/{pid}/{mid}: 다나와는 스펙 출처로 쓰지 않는다 — 제조사 공식 페이지로")
                if cats.get(pid) == "case":
                    errs += [f"models/{pid}/{mid}: {e}" for e in _check_case_specs(m.get("specs") or {})]
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
    # 이름 읽는 법(Ti·X3D·OC…) — 매물 이름에서 찾는 정규식과, 차이를 보여 줄 비교 부품
    for n in g.get("names", []):
        where = f"names/{n.get('key')}"
        if n.get("applies") not in ("gpu", "cpu", "product"):
            errs.append(f"guide.json {where}: applies 는 gpu·cpu·product")
        try:
            re.compile(n.get("match", ""))
        except re.error as e:
            errs.append(f"guide.json {where}: match 정규식이 깨졌다 {e}")
        for a in n.get("compare", []):
            if a not in ids:
                errs.append(f"guide.json {where}: 모르는 비교 부품 {a}")
        srcs(where, n.get("sources"))
    # 소켓별 메모리 한도 — 최대 용량·채널·꽂은 개수별 공식 속도
    for m in g.get("memory_platforms", []):
        where = f"memory_platforms/{m.get('socket')}"
        for k in ("socket", "mem", "channels", "max_gb", "speed"):
            if k not in m:
                errs.append(f"guide.json {where}: {k} 없음")
        srcs(where, m.get("sources"))
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
        img = p.get("image")
        if img:
            if not all(img.get(k) for k in ("url", "credit", "page")):
                errs.append(f"{pid}: image 는 url·credit·page 가 다 있어야 한다(출처 표시)")
            if any(h in str(img.get("url", "")) + str(img.get("page", "")) for h in ("danawa", "danuri", "coupang", "naver")):
                errs.append(f"{pid}: 사진은 제조사 공식 페이지 것만 — 판매처 이미지는 쓰지 않는다")
        q = p.get("price_query")
        if q is not None and not q.get("q"):
            errs.append(f"{pid}: price_query.q 가 비었다")
    for c in index.get("categories", []):
        mins = [t["min"] for t in c.get("tiers", [])]
        if mins != sorted(mins, reverse=True) or (mins and mins[-1] != 0):
            errs.append(f"index.json {c.get('key')}: 등급 문턱은 내림차순이고 마지막이 0 이어야 한다")
    if {c.get("key") for c in index.get("categories", [])} != CATS:
        errs.append("index.json: 분류가 아홉 개와 다르다")
    for v in bench.get("vendor", []):
        if v.get("gpu") not in ids:
            errs.append(f"bench.json vendor: 모르는 부품 {v.get('gpu')}")
        if not (v.get("source") or {}).get("url") or not v.get("footnote"):
            errs.append(f"bench.json vendor/{v.get('gpu')}: 제조사 측정값은 출처 url 과 각주가 있어야 한다")
    anchor = bench.get("image", {}).get("anchor", {}).get("gpu")
    if anchor not in ids:
        errs.append(f"bench.json: 이미지 기준 GPU {anchor!r} 가 parts 에 없다")
    # 영상 편집 점수는 추정이 아니라 Puget 실측이다 — 카드마다 그 값을 본 비교 페이지를 남긴다
    for gid, v in bench.get("video", {}).get("gpu", {}).items():
        if gid not in ids:
            errs.append(f"bench.json video: 모르는 부품 {gid}")
        if not str(v.get("src", "")).startswith("https://"):
            errs.append(f"bench.json video/{gid}: 실측 점수는 출처 url(src)이 있어야 한다")
    for g in bench.get("games", []):
        for k in ("gpu100", "vram"):
            if set(g.get(k, {})) != {"fhd", "qhd", "uhd"}:
                errs.append(f"bench.json {g.get('key')}: {k} 는 fhd·qhd·uhd 셋")
    errs.extend(check_guide(ids))
    errs.extend(check_datacenter())
    errs.extend(check_notes(ids))
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
    spec_todo: dict[str, list[str]] = {}
    assumed: list[str] = []
    for p in parts:
        if p.get("status") == "legacy":
            continue
        rec = book.get(p["id"]) or {}
        if p.get("price_query") and rec.get("min") is None:
            no_price.append(p["id"])
        # 칩셋·용량 '급' 단위 분류(보드·파워·쿨러·케이스)는 보급형부터 고급형까지 원래 값 폭이 넓다 — 섞임으로 보지 않는다
        elif rec.get("min") and p.get("price_basis") != "median" and p["category"] not in CLASS_CATS                 and rec.get("median", 0) / rec["min"] > MIXED_RATIO:
            mixed.append(f"{p['id']} (최저 {rec['min']:,} · 중앙 {rec['median']:,})")
        if p.get("class_assumption"):
            # 급 가정(쿨러·케이스 급) — 확인할 제조사 표가 없다. 대표 제품으로 바꿀 때까지 따로 센다
            assumed.append(p["id"])
            continue
        if (p.get("perf") or {}).get("confidence") == "seed":
            seed.setdefault(p["category"], []).append(p["id"])
        if not p.get("specs_verified"):
            spec_todo.setdefault(p["category"], []).append(p["id"])
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
    # 스펙(제조사 표의 숫자)과 성능 지수(리뷰로 잰 상대값)는 확인하는 곳이 달라 따로 센다
    print(f"4a. 스펙 확인 전 {sum(len(v) for v in spec_todo.values())}: " + (" · ".join(f"{c} {len(v)}" for c, v in spec_todo.items()) or "-"))
    print(f"4c. 급 가정(대표 제품으로 바꿀 후보) {len(assumed)}: {', '.join(assumed) or '-'}")
    print(f"4b. 성능 지수 확인 전(seed) {total_seed}: " + (" · ".join(f"{c} {len(v)}" for c, v in seed.items()) or "-"))
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
    # 조립 화면의 '메모리 슬롯' 칸 — 보드는 급 단위라 슬롯 수를 규격으로 짐작한다. 인기 매물부터
    # 제품별 스펙(models/<보드 id>.json 의 dimm_slots·form)을 채우면 짐작이 사실로 바뀐다.
    # 소켓별 최대 용량·꽂은 개수별 속도(guide.json memory_platforms)가 없는 소켓도 여기서 센다.
    try:
        guide = json.loads((HW / "guide.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        guide = {}
    have = {m.get("socket") for m in guide.get("memory_platforms", [])}
    sockets = sorted({str(p["specs"].get("socket")) for p in parts if p["category"] == "cpu" and p["specs"].get("socket")} - have)
    no_slots: dict[str, int] = {}
    for p in parts:
        if p["category"] != "mainboard":
            continue
        mf = HW / "models" / f"{p['id']}.json"
        try:
            ms = json.loads(mf.read_text(encoding="utf-8")).get("models", []) if mf.exists() else []
        except ValueError:
            ms = []
        n = sum(1 for m in ms if not (m.get("specs") or {}).get("dimm_slots"))
        if n or not ms:
            no_slots[p["id"]] = n or -1
    top = sorted(no_slots.items(), key=lambda kv: -kv[1])
    print(f"9. 메모리 슬롯 수 모르는 보드 제품 {sum(max(v, 0) for v in no_slots.values())}: "
          + (", ".join(f"{k} {'파일 없음' if v < 0 else v}" for k, v in top) or "-")
          + f" · 메모리 한도 없는 소켓 {len(sockets)}: {', '.join(sockets) or '-'}")
    dc_gaps()
    notes_gaps(parts)


# ── AI 데이터센터 (public/hardware/datacenter.json) ─────────────────────
#
# 회사별 칩 수·성능 환산·금액·시장 조사. 매출·설비투자·칩 수는 분기마다 바뀌어 오래 두면 틀린 숫자가 된다.
# 형식 검사는 check_datacenter, 일감(10번)은 dc_gaps — hw-datacenter 레인이 오래된 것부터 다시 조사한다.

DC_PATH = HW / "datacenter.json"
DC_STALE_DAYS = 90        # 섹션(market·money·ratios) 확인일이 이보다 오래되면 다시 조사
DC_CLUSTER_STALE_DAYS = 365  # 가동 중인 데이터센터의 as_of 가 이보다 오래되면 다시 조사
DC_REGIONS = {"US", "CN", "KR", "JP", "EU", "ME", "IN", "OTHER"}


def _dc_srcs(errs: list[str], where: str, xs) -> None:
    if not xs:
        errs.append(f"datacenter.json {where}: 출처가 없다")
    for s in xs or []:
        u = s.get("url") if isinstance(s, dict) else s
        if not str(u or "").startswith(("http://", "https://")):
            errs.append(f"datacenter.json {where}: 출처 url 이 이상하다")


def check_datacenter() -> list[str]:
    """숫자마다 출처, 환산에 쓰는 칩 이름이 사양비 표에 있나, 합계 규칙 필드가 맞나."""
    if not DC_PATH.exists():
        return []
    errs: list[str] = []
    try:
        d = json.loads(DC_PATH.read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"datacenter.json: JSON 이 깨졌다 {e}"]
    ratio_names = {r.get("name") for r in d.get("ratios", [])}
    for r in d.get("ratios", []):
        if not isinstance(r.get("ratio"), (int, float)) or r["ratio"] <= 0:
            errs.append(f"datacenter.json ratios/{r.get('name')}: ratio 가 양수가 아니다")
        _dc_srcs(errs, f"ratios/{r.get('name')}", r.get("sources"))
    keys: set[str] = set()
    for c in d.get("clusters", []):
        w = f"clusters/{c.get('key')}"
        if not c.get("key") or c["key"] in keys:
            errs.append(f"datacenter.json {w}: key 가 없거나 겹친다")
        keys.add(c.get("key"))
        if c.get("status") not in ("operational", "planned", "past"):
            errs.append(f"datacenter.json {w}: status 는 operational·planned·past")
        if c.get("confidence") not in ("official", "estimate"):
            errs.append(f"datacenter.json {w}: confidence 는 official·estimate")
        if c.get("region") not in DC_REGIONS:
            errs.append(f"datacenter.json {w}: 모르는 region {c.get('region')}")
        if not re.match(r"^\d{4}(-\d{2})?$", str(c.get("as_of", ""))):
            errs.append(f"datacenter.json {w}: as_of 는 YYYY 또는 YYYY-MM")
        if c.get("chip_key") and c["chip_key"] not in ratio_names:
            errs.append(f"datacenter.json {w}: 사양비 표에 없는 chip_key {c['chip_key']}")
        for m in c.get("mix") or []:
            if m.get("chip_key") not in ratio_names:
                errs.append(f"datacenter.json {w}: mix 에 사양비 표에 없는 칩 {m.get('chip_key')}")
        _dc_srcs(errs, w, c.get("sources"))
    for n in d.get("national", []):
        _dc_srcs(errs, f"national/{n.get('scope')}", n.get("sources"))
    money = d.get("money") or {}
    for u in money.get("unit_prices", []):
        if u.get("chip_key") not in ratio_names:
            errs.append(f"datacenter.json money/unit_prices: 사양비 표에 없는 칩 {u.get('chip_key')}")
        _dc_srcs(errs, f"money/unit_prices/{u.get('chip_key')}", u.get("sources"))
    for c in money.get("capex", []):
        _dc_srcs(errs, f"money/capex/{c.get('company')}", c.get("sources"))
    for c in money.get("commitments", []):
        _dc_srcs(errs, f"money/commitments/{c.get('who')}·{c.get('deal')}", [c.get("src")])
    market = d.get("market") or {}
    for b in market.get("business", []):
        _dc_srcs(errs, f"market/business/{b.get('company')}", b.get("sources"))
    fx = d.get("fx") or {}
    if fx:
        if not isinstance(fx.get("krw_per_usd"), (int, float)):
            errs.append("datacenter.json fx: krw_per_usd 가 숫자가 아니다")
        _dc_srcs(errs, "fx", fx.get("sources"))
    return errs


# ── 실무자 이야기 (public/hardware/notes.json) ─────────────────────────
#
# 고성능 그래픽카드를 AI·ML 에 쓰는 사람들의 실측·경험 요약. Reddit 은 robots.txt 가 전부 막아 쓰지 않는다.

NOTES_PATH = HW / "notes.json"
NOTES_EXTRA_GPUS = {"rtx-3090-used", "mac-studio", "strix-halo", "dgx-spark"}  # 우리 부품 목록 밖의 비교 대상
NOTES_USES = {"llm-inference", "fine-tuning", "image-gen", "multi-gpu", "build", "alternatives"}
NOTES_STALE_DAYS = 180


def check_notes(ids: set[str]) -> list[str]:
    if not NOTES_PATH.exists():
        return []
    errs: list[str] = []
    try:
        d = json.loads(NOTES_PATH.read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"notes.json: JSON 이 깨졌다 {e}"]
    for n in d.get("notes", []):
        w = f"notes.json '{n.get('topic')}'"
        if n.get("evidence") not in ("measurement", "experience", "official"):
            errs.append(f"{w}: evidence 는 measurement·experience·official")
        if n.get("confidence") not in ("high", "medium", "low"):
            errs.append(f"{w}: confidence 는 high·medium·low")
        if n.get("use") not in NOTES_USES:
            errs.append(f"{w}: 모르는 use {n.get('use')}")
        for g in n.get("gpus", []):
            if g not in ids and g not in NOTES_EXTRA_GPUS:
                errs.append(f"{w}: 모르는 GPU {g}")
        srcs = n.get("sources") or []
        if not srcs:
            errs.append(f"{w}: 출처가 없다")
        for s in srcs:
            u = str(s.get("url", ""))
            if not u.startswith(("http://", "https://")):
                errs.append(f"{w}: 출처 url 이 이상하다")
            if "reddit.com" in u:
                errs.append(f"{w}: Reddit 은 robots.txt 가 막아 출처로 쓰지 않는다")
        if len(n.get("summary", "")) > 400:
            errs.append(f"{w}: 요약이 너무 길다 — 원문을 옮기지 말고 줄인다")
    return errs


def notes_gaps(parts: list[dict]) -> None:
    """11번 — 실무자 이야기가 없는 고성능 그래픽카드(성능 지수 45 이상 · 12GB 이상), 반년 넘은 이야기."""
    if not NOTES_PATH.exists():
        return
    notes = json.loads(NOTES_PATH.read_text(encoding="utf-8")).get("notes", [])
    covered = {g for n in notes for g in n.get("gpus", [])}
    high = [p for p in parts if p["category"] == "gpu" and p.get("status") == "current"
            and p["perf"].get("index", 0) >= 45 and float(p["specs"].get("vram_gb") or 0) >= 12]
    missing = [p["id"] for p in sorted(high, key=lambda p: -p["perf"]["index"]) if p["id"] not in covered]
    today = date.today()
    old = [n["topic"] for n in notes
           if re.match(r"^\d{4}-\d{2}$", n.get("as_of", "")) and (today - datetime.strptime(n["as_of"] + "-01", "%Y-%m-%d").date()).days > NOTES_STALE_DAYS]
    print(f"11. 실무자 이야기 — 없는 고성능 카드 {len(missing)}: {', '.join(missing) or '-'} · 반년 넘은 이야기 {len(old)}(새 측정으로 바꿀 후보)")


def dc_gaps() -> None:
    """10번 — AI 데이터센터에서 다시 조사할 것: 오래된 섹션, 오래된 가동 데이터센터, 환산이 빠진 회사."""
    if not DC_PATH.exists():
        return
    d = json.loads(DC_PATH.read_text(encoding="utf-8"))
    today = date.today()

    def age(s: str | None) -> int | None:
        if not s:
            return None
        s = s if len(s) > 7 else (s + "-01" if len(s) == 7 else s + "-01-01")
        try:
            return (today - datetime.strptime(s[:10], "%Y-%m-%d").date()).days
        except ValueError:
            return None

    checked = d.get("checked") or {}
    old_sections = [k for k in ("clusters", "ratios", "money", "market", "fx") if (a := age(checked.get(k))) is None or a > DC_STALE_DAYS]
    ratio_names = {r["name"] for r in d.get("ratios", [])}
    live = [c for c in d.get("clusters", []) if c.get("status") == "operational" and c.get("in_total", True)]
    old = sorted((c for c in live if (age(c.get("as_of")) or 0) > DC_CLUSTER_STALE_DAYS), key=lambda c: -(c.get("count") or c.get("h100eq") or 0))
    no_eq = sorted({c["company"] for c in live if c.get("h100eq") is None and not c.get("fp16_pflops")
                    and not (c.get("chip_key") in ratio_names or (c.get("mix") and all(m["chip_key"] in ratio_names for m in c["mix"])))})
    print(f"10. AI 데이터센터 — 확인 {DC_STALE_DAYS}일 넘은 섹션 {len(old_sections)}: {', '.join(old_sections) or '-'}"
          f" · 1년 넘은 가동 데이터센터 {len(old)}: {', '.join(f'{c['company']}/{c['name']}' for c in old[:6]) or '-'}"
          f" · H100 환산이 빠진 회사 {len(no_eq)}: {', '.join(no_eq[:8]) or '-'}")


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
