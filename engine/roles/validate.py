"""직무 역설계(공고 한 줄씩 읽기) 검사 · 색인 · 다음 일감.

    python engine/roles/validate.py            # 검사 + jd-viewer/public/roles/index.json 굽기
    python engine/roles/validate.py --gaps     # 다음에 조사할 공고(대상 1건 + 후보 몇 건)
    python engine/roles/validate.py --claim    # 병렬 루프: 맨 위 후보를 집는다(다른 회차가 같은 공고를 못 잡게)
    python engine/roles/validate.py --only <id>   # 내 파일만 검사(쓰는 중인 남의 파일은 index 에서만 뺀다)
    python engine/roles/validate.py --release <키> # 집기를 푼다(커밋 뒤)

산출물: jd-viewer/public/roles/items/<id>.json (형식은 engine/roles/schema.json, 절차는 PROMPT.md).
단위는 '회사 × 직무' 하나 — 같은 자리가 여러 사이트·여러 번 올라와도 파일은 하나이고 `jobs` 에 공고 키를 모은다.
뷰어 공고 상세는 index.json 의 jobs(공고 키 → 파일 id)로 찾아 공고 줄마다 풀이를 붙인다.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "jd-viewer" / "public"
DIR = PUBLIC / "roles" / "items"
INDEX = PUBLIC / "roles" / "index.json"
JOBS = PUBLIC / "all_jobs_enriched.json"

SECTIONS = {"task": "main_tasks", "qualification": "qualifications", "preference": "preferences"}
SOURCE_KINDS = {"company", "posting", "news", "reference", "community"}
RES_KINDS = {"book", "course", "doc", "video", "internal"}
LEVELS = ["입문", "실무", "심화"]
CLAIMS = ROOT / "catch_capture" / "var" / "roles" / "claims"   # 병렬 루프가 집어 간 공고(커밋 안 함)
CLAIM_TTL_S = 3 * 3600   # 이보다 오래된 집기는 죽은 회차로 보고 무시한다
REF = re.compile(r"\[(\d{1,2})\]")
SHORT_MAX = 90            # 공고 줄 바로 밑에 늘 보이는 한 줄 — 길면 훑어 읽기가 깨진다
LONG_ENGLISH = re.compile(r"[A-Za-z ,.'\"()\-:;]{220,}")   # 영어 원문을 옮긴 흔적


def norm(s: str) -> str:
    """공고 줄과 quote 를 맞출 때 쓰는 꼴 — 글머리표·공백·문장부호 차이를 지운다."""
    s = re.sub(r"^[\s\-•·*○●▶▪✓✔︎\d.)]+", "", s or "")
    return re.sub(r"[\s.,·!?~'\"“”‘’()]+", "", s).lower()


def posting_lines(text: str | None) -> list[str]:
    out = []
    for ln in (text or "").splitlines():
        if len(norm(ln)) >= 8:
            out.append(ln.strip())
    return out


def texts(node) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [t for k, v in node.items() if k not in ("url", "code") for t in texts(v)]
    if isinstance(node, list):
        return [t for v in node for t in texts(v)]
    return []


def check(d: dict, path: Path, jobs_by_key: dict) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    w = path.name
    for k in ("id", "company", "role", "jobs", "researched_at", "tldr", "lines", "sources"):
        if not d.get(k):
            errs.append(f"{w}: '{k}' 없음")
    if errs:
        return errs, warns
    if d["id"] != path.stem:
        errs.append(f"{w}: id({d['id']}) 와 파일 이름이 다르다")
    nums = {s.get("n") for s in d["sources"]}
    for s in d["sources"]:
        if not s.get("url") or not s.get("title"):
            errs.append(f"{w}: 출처 {s.get('n')} 에 url·title 없음")
        if s.get("kind") not in SOURCE_KINDS:
            errs.append(f"{w}: 출처 {s.get('n')} kind '{s.get('kind')}' — {sorted(SOURCE_KINDS)}")
    for t in texts({k: v for k, v in d.items() if k != "sources"}):
        for n in REF.findall(t):
            if int(n) not in nums:
                errs.append(f"{w}: 본문의 [{n}] 에 해당하는 출처가 없다")
        if LONG_ENGLISH.search(t):
            errs.append(f"{w}: 긴 영어 원문이 있다 — 옮기지 말고 우리 말로 다시 쓴다")
    used = {int(n) for t in texts(d) for n in REF.findall(t)}
    for n in sorted(nums - used):
        warns.append(f"{w}: 출처 {n} 이 본문 어디에서도 안 쓰였다")
    for i, ln in enumerate(d["lines"]):
        lw = f"{w} lines[{i}]"
        if ln.get("section") not in SECTIONS:
            errs.append(f"{lw}: section 은 {list(SECTIONS)}")
        for k in ("quote", "short", "why"):
            if not ln.get(k):
                errs.append(f"{lw}: '{k}' 없음")
        if len(ln.get("short", "")) > SHORT_MAX:
            errs.append(f"{lw}: short 가 {len(ln['short'])}자 — {SHORT_MAX}자 안으로(공고 줄 밑에 늘 보이는 한 줄)")
        for ex in ln.get("examples", []):
            if ex.get("code") and not ex.get("lang"):
                errs.append(f"{lw}: 코드 예시에 lang 없음")
    # 공부 자료 — 실제로 있는 책·강의·문서만(조사에서 존재를 확인한 것). 줄·로드맵은 id 로만 가리킨다.
    res_ids = set()
    for x in d.get("resources", []):
        rw = f"{w} resources[{x.get('id')}]"
        for k in ("id", "title", "kind", "url", "why", "lang", "level"):
            if not x.get(k):
                errs.append(f"{rw}: '{k}' 없음")
        if x.get("kind") not in RES_KINDS:
            errs.append(f"{rw}: kind 는 {sorted(RES_KINDS)}")
        if x.get("level") not in LEVELS:
            errs.append(f"{rw}: level 은 {LEVELS}")
        res_ids.add(x.get("id"))
    wanted = [(f"lines[{i}]", r) for i, ln in enumerate(d["lines"]) for r in ln.get("study", [])]
    for i, st in enumerate(d.get("study_path", [])):
        for k in ("title", "goal", "task", "resources"):
            if not st.get(k):
                errs.append(f"{w} study_path[{i}]: '{k}' 없음")
        wanted += [(f"study_path[{i}]", r) for r in st.get("resources", [])]
    for where, r in wanted:
        if r not in res_ids:
            errs.append(f"{w} {where}: 공부 자료 '{r}' 가 resources 에 없다")
    # 연봉·복지·위치 — 숫자마다 기준(basis)과 출처. 근거가 없으면 칸을 비운다(지어내지 않는다).
    pay = d.get("pay")
    if pay:
        if not pay.get("summary") or not pay.get("rows"):
            errs.append(f"{w} pay: summary·rows 가 있어야 한다")
        for i, row in enumerate(pay.get("rows", [])):
            for k in ("label", "value", "basis"):
                if not row.get(k):
                    errs.append(f"{w} pay.rows[{i}]: '{k}' 없음")
            if not REF.search(row.get("note", "")):
                errs.append(f"{w} pay.rows[{i}]: note 에 출처 [n] 이 없다 — 연봉 숫자는 출처 없이 싣지 않는다")
            if "amount" in row and not (isinstance(row["amount"], (int, float)) and row["amount"] > 0):
                errs.append(f"{w} pay.rows[{i}]: amount 는 만원 단위 양수(막대 길이)")
    ben = d.get("benefits")
    if ben:
        if not ben.get("items"):
            errs.append(f"{w} benefits: items 없음")
        if not REF.search(ben.get("note", "")):
            errs.append(f"{w} benefits: note 에 출처 [n] 이 없다")
    loc = d.get("location")
    if loc:
        for k in ("name", "address"):
            if not loc.get(k):
                errs.append(f"{w} location: '{k}' 없음")
        if not REF.search(loc.get("note", "")):
            errs.append(f"{w} location: note 에 출처 [n] 이 없다")
    for k in ("pay", "benefits", "location"):
        if k not in d:
            warns.append(f"{w}: '{k}' 가 없다 — 공개된 근거가 있으면 채운다(PROMPT 4-2)")
    # 공고의 모든 줄에 풀이가 붙었나 — 수집된 공고가 있을 때만 대조한다
    quotes = {norm(ln["quote"]) for ln in d["lines"] if ln.get("quote")}
    for key in d["jobs"]:
        job = jobs_by_key.get(key)
        if not job:
            continue
        for sec, field in SECTIONS.items():
            for pl in posting_lines(job.get(field)):
                n = norm(pl)
                if not any(q in n or n in q for q in quotes):
                    warns.append(f"{w}: 공고 {key} 의 줄에 풀이가 없다 — {pl[:50]}")
    return errs, warns


def load_jobs() -> list[dict]:
    try:
        return json.loads(JOBS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 공고 파일이 없으면 대조만 건너뛴다
        return []


def build_index(items: list[dict]) -> dict:
    return {
        "updated_at": date.today().isoformat(),
        "jobs": {k: d["id"] for d in items for k in d["jobs"]},
        "roles": [{"id": d["id"], "company": d["company"], "role": d["role"], "jobs": d["jobs"],
                   "researched_at": d["researched_at"], "lines": len(d["lines"])} for d in items],
    }


def _claim_path(key: str) -> Path:
    return CLAIMS / (re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".claim")


# 근거를 못 구해 그만둔 공고(`--block <키> <이유>`). 집기만 풀면 다음 일꾼이 같은 공고를 또 집어 같은 403 에
# 비용을 쓴다(무신사 — 테크 블로그·자소설 403, 2026-11-25 두 회차 연속). 막힌 지 BLOCK_TTL_DAYS 안이면 건너뛰고,
# 한 회사에서 BLOCK_COMPANY_N 건 이상 막혔으면 그 회사 전체를 건너뛴다(출처가 회사째 막힌 것).
BLOCKED = ROOT / "catch_capture" / "var" / "roles" / "blocked.tsv"   # 키 \t 날짜 \t 회사 \t 이유
BLOCK_TTL_DAYS = 14
BLOCK_COMPANY_N = 3


def blocked() -> tuple[set[str], set[str]]:
    """(막힌 공고 키, 회사째 막힌 회사) — TTL 이 지난 줄은 무시한다."""
    keys, per_co = set(), {}
    try:
        lines = BLOCKED.read_text(encoding="utf-8").splitlines()
    except OSError:
        return keys, set()
    for ln in lines:
        p = ln.split("\t")
        if len(p) < 3:
            continue
        try:
            if (date.today() - date.fromisoformat(p[1])).days > BLOCK_TTL_DAYS:
                continue
        except ValueError:
            continue
        keys.add(p[0])
        per_co[p[2]] = per_co.get(p[2], 0) + 1
    return keys, {c for c, n in per_co.items() if n >= BLOCK_COMPANY_N}


def block(key: str, reason: str, by_key: dict) -> None:
    BLOCKED.parent.mkdir(parents=True, exist_ok=True)
    co = (by_key.get(key) or {}).get("company", "")
    with BLOCKED.open("a", encoding="utf-8") as f:
        f.write(f"{key}\t{date.today().isoformat()}\t{co}\t{reason.replace(chr(9), ' ')}\n")
    _claim_path(key).unlink(missing_ok=True)


def claimed() -> set[str]:
    """살아 있는 집기 — 다른 회차가 지금 쓰고 있는 공고 키."""
    import time
    out = set()
    for f in CLAIMS.glob("*.claim") if CLAIMS.exists() else []:
        try:
            if time.time() - f.stat().st_mtime < CLAIM_TTL_S:
                out.add(f.read_text(encoding="utf-8").strip())
        except OSError:
            pass
    return out


# ── 비슷한 새 공고는 다시 조사하지 않는다(2026-11-25) ────────────────────────────────────
# 공고는 내려가고 비슷한 공고가 다시 올라온다. 같은 회사 풀이가 새 공고 줄을 이미 덮으면:
#   · 전부 덮음 → Claude 없이 기존 풀이의 jobs 에 공고 키만 붙인다(`--relink`, 회차 뒤 러너가 돌린다)
#   · SIMILAR_MIN 이상 덮음(또는 같은 제목) → '갱신 모드' — 일꾼은 새 줄만 조사해 기존 풀이에 덧붙인다
#   · 그 밖 → 새로 조사
SIMILAR_MIN = 0.5


def co_norm(s: str | None) -> str:
    return re.sub(r"\(주\)|㈜|주식회사|\s", "", s or "").lower()


def job_lines(j: dict) -> list[tuple[str, str]]:
    return [(sec, pl) for sec, field in SECTIONS.items() for pl in posting_lines(j.get(field))]


def _hit(n: str, quotes: set[str]) -> bool:
    return any(q in n or n in q for q in quotes)


def _items_by_company(items: list[dict], by_key: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for d in items:
        cos = {co_norm(d.get("company"))} | {co_norm((by_key.get(k) or {}).get("company")) for k in d["jobs"]}
        for c in cos - {""}:
            out.setdefault(c, []).append(d)
    return out


def best_match(j: dict, by_co: dict[str, list[dict]]) -> tuple[dict | None, list[tuple[str, str]], int]:
    """같은 회사 풀이 중 이 공고 줄을 가장 많이 덮는 것 → (풀이, 안 덮인 줄, 전체 줄 수)."""
    lines = job_lines(j)
    best, best_missing = None, lines
    for d in by_co.get(co_norm(j.get("company")), []):
        quotes = {norm(ln["quote"]) for ln in d["lines"] if ln.get("quote")}
        missing = [(s, pl) for s, pl in lines if not _hit(norm(pl), quotes)]
        if len(missing) < len(best_missing):
            best, best_missing = d, missing
    return best, best_missing, len(lines)


def relink(items: list[dict], jobs: list[dict]) -> int:
    """줄이 전부 기존 풀이에 있는 모집중 공고 → 그 풀이의 jobs 에 키를 붙인다(파일을 고친다). 붙인 수를 돌려준다."""
    by_key = {f"{j.get('site')}-{j.get('pid')}": j for j in jobs}
    done = {k for d in items for k in d["jobs"]}
    by_co = _items_by_company(items, by_key)
    busy = claimed()
    touched: dict[str, dict] = {}
    added = 0
    for j in jobs:
        key = f"{j.get('site')}-{j.get('pid')}"
        if j.get("status") == "closed" or key in done:
            continue
        d, missing, total = best_match(j, by_co)
        if d is None or missing or total < 5 or any(k in busy for k in d["jobs"]):
            continue   # 쓰는 중인 풀이는 건드리지 않는다(일꾼이 덮어쓴다)
        d["jobs"].append(key)
        done.add(key)
        touched[d["id"]] = d
        added += 1
    for d in touched.values():
        _write_jobs(DIR / f"{d['id']}.json", d["jobs"])
    return added


def _write_jobs(path: Path, keys: list[str]) -> None:
    """파일의 "jobs" 배열만 갈아 끼운다 — 통째로 다시 쓰면 일꾼마다 다른 들여쓰기가 바뀌어 diff 가 파일 전체가 된다."""
    raw = path.read_text(encoding="utf-8")
    m = re.search(r'("jobs"\s*:\s*)\[(.*?)\]', raw, re.S)
    if not m:
        d = json.loads(raw)
        d["jobs"] = keys
        path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        return
    body = m.group(2)
    nl = chr(10)
    if nl in body:   # 여러 줄 꼴 — 첫 원소의 들여쓰기와 닫는 괄호 앞 들여쓰기를 그대로 쓴다
        ind = (re.search(nl + r"([ \t]*)\S", body) or [None, "  "])[1]
        close = (re.search(nl + r"([ \t]*)$", body) or [None, ""])[1]
        arr = "[" + nl + ("," + nl).join(ind + json.dumps(k, ensure_ascii=False) for k in keys) + nl + close + "]"
    else:
        arr = "[" + ", ".join(json.dumps(k, ensure_ascii=False) for k in keys) + "]"
    path.write_text(raw[:m.start()] + m.group(1) + arr + raw[m.end():], encoding="utf-8")


def candidates(items: list[dict], jobs: list[dict]) -> list[tuple]:
    """다음 일감 후보: 모집중이고 업무·요건 줄이 충분한 공고, 그 회사 모집중 공고가 많은 곳부터.
    이미 풀이가 있는 공고와 다른 회차가 집어 간 공고는 건너뛴다. 같은 회사 풀이가 줄을 이미 덮는 공고는
    relink 몫(전부 덮음)이거나 갱신 모드(새 줄만)다 — 튜플 끝의 upd 가 (기존 풀이 id, 안 덮인 줄) 이다."""
    done = {k for d in items for k in d["jobs"]}
    done_titles = {(d["company"], norm(d["role"])) for d in items}
    by_key_all = {f"{j.get('site')}-{j.get('pid')}": j for j in jobs}
    by_co = _items_by_company(items, by_key_all)
    busy = claimed()
    blk_keys, blk_cos = blocked()
    active = [j for j in jobs if j.get("status") != "closed"
              and f"{j.get('site')}-{j.get('pid')}" not in blk_keys and j.get("company") not in blk_cos]
    # 같은 자리가 여러 사이트에 올라온다(원티드·잡코리아 …) — 집힌 공고와 회사·제목이 같으면 그것도 집힌 것으로 본다.
    # 키만 보다가 두 일꾼이 같은 자리를 잡아 한쪽이 덮어쓴 일이 있었다(현대오토에버, 2026-11-23).
    busy_titles = {(j.get("company"), norm(j.get("title", ""))) for j in jobs if f"{j.get('site')}-{j.get('pid')}" in busy}
    busy_items = {d["id"] for d in items if any(k in busy for k in d["jobs"])}
    per_co: dict[str, int] = {}
    for j in active:
        per_co[j.get("company", "")] = per_co.get(j.get("company", ""), 0) + 1
    cand = []
    for j in active:
        key = f"{j.get('site')}-{j.get('pid')}"
        title = (j.get("company"), norm(j.get("title", "")))
        if key in done or key in busy or title in busy_titles:
            continue
        n = sum(len(posting_lines(j.get(f))) for f in SECTIONS.values())
        if n < 5:
            continue
        d, missing, total = best_match(j, by_co)
        upd = None
        if d is not None and (title in done_titles or total - len(missing) >= SIMILAR_MIN * total):
            if not missing or d["id"] in busy_items:
                continue   # 전부 덮음 → relink 몫 / 그 풀이를 다른 일꾼이 쓰는 중 → 다음에
            upd = (d["id"], missing)
        cand.append((per_co.get(j.get("company", ""), 0), n, key, j, upd))
    # 순서: ① 사람이 먼저 해 달라고 한 공고(PRIORITY, 적힌 순서) ② 갱신 모드(새 줄만 — 싸고 빨리 끝난다) ③ 국내 회사
    # ④ 일본 회사(가나·株式会社 — 해외 보드에서 같이 들어온다) — 그 안에서는 회사 모집중 공고가 많은 곳부터.
    pri = priority()
    cand.sort(key=lambda x: (pri.index(x[2]) if x[2] in pri else len(pri), x[4] is None, is_japanese(x[3]), -x[0], -x[1]))
    return cand


PRIORITY = ROOT / "catch_capture" / "var" / "roles" / "priority.txt"   # 한 줄에 공고 키 하나(site-pid)
JAPANESE = re.compile(r"[぀-ヿ]|株式会社")


def priority() -> list[str]:
    try:
        return [ln.strip() for ln in PRIORITY.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    except OSError:
        return []


def is_japanese(j: dict) -> bool:
    return bool(JAPANESE.search(f"{j.get('company', '')} {j.get('title', '')}"))


def claim(items: list[dict], jobs: list[dict]) -> int:
    """맨 위 후보 하나를 집는다(파일을 O_EXCL 로 만들어 두 회차가 같은 공고를 못 잡는다). 집은 키를 찍는다."""
    import os
    CLAIMS.mkdir(parents=True, exist_ok=True)
    for _, n, key, j, upd in candidates(items, jobs):
        p = _claim_path(key)
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            # TTL 이 지난 집기는 죽은 회차가 남긴 것이다(한도에 걸려 멈춘 일꾼 등) — candidates 는 이미 후보로 보는데
            # 여기서 건너뛰면 그 공고는 영영 안 집히고 목록 맨 위에 남는다(토스 공고들, 2026-11-23 → 11-25).
            import time
            try:
                stale = time.time() - p.stat().st_mtime >= CLAIM_TTL_S
            except OSError:
                stale = True
            if not stale:
                continue
            p.unlink(missing_ok=True)
            try:
                fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                continue
        os.write(fd, key.encode("utf-8"))
        os.close(fd)
        print(f"▶ 대상 {key} · {j.get('company')} · {j.get('title')} (줄 {n})")
        if upd:
            rid, missing = upd
            print(f"  ★ 갱신 모드 — 같은 회사의 비슷한 공고 풀이 `{rid}.json` 이 이미 {n - len(missing)}/{n}줄을 덮는다.")
            print(f"    새로 조사하지 않는다: 그 파일을 열어 `jobs` 에 {key} 를 더하고, 아래 새 줄만 lines 에 덧붙인다(PROMPT '갱신 모드').")
            for sec, pl in missing:
                print(f"    + [{sec}] {pl}")
        print(f"  (집기: {_claim_path(key).relative_to(ROOT)} — 커밋하면 validate --release {key} 로 푼다)")
        return 0
    print("[roles] 집을 후보가 없다")
    return 1


def gaps(items: list[dict], jobs: list[dict], show: int = 6) -> None:
    cand = candidates(items, jobs)
    print(f"[roles] 풀이 {len(items)}개 · 후보 공고 {len(cand)}건 · 집힌 것 {len(claimed())}건 — 위에서부터")
    n_upd = sum(1 for c in cand if c[4])
    print(f"         그중 갱신 모드(비슷한 기존 풀이에 새 줄만) {n_upd}건 · 새로 조사 {len(cand) - n_upd}건")
    for i, (co_n, n, key, j, upd) in enumerate(cand[:show]):
        mark = "▶ 대상" if i == 0 else "  후보"
        tail = f" · 갱신 {upd[0]} 에 새 줄 {len(upd[1])}" if upd else ""
        print(f"  {mark} {key} · {j.get('company')} · {j.get('title')} (줄 {n}, 회사 모집중 {co_n}){tail}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    jobs = load_jobs()
    by_key = {f"{j.get('site')}-{j.get('pid')}": j for j in jobs}
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    if "--release" in sys.argv:
        _claim_path(sys.argv[sys.argv.index("--release") + 1]).unlink(missing_ok=True)
        return 0
    if "--relink" in sys.argv:
        items = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DIR.glob("*.json"))]
        n = relink(items, jobs)
        print(f"[roles] relink — 기존 풀이가 줄을 전부 덮는 새 공고 {n}건을 이어 붙였다")
        if n:
            INDEX.write_text(json.dumps(build_index(items), ensure_ascii=False, indent=1), encoding="utf-8")
        return 0
    if "--block" in sys.argv:
        i = sys.argv.index("--block")
        block(sys.argv[i + 1], " ".join(sys.argv[i + 2:]) or "근거 부족", by_key)
        return 0
    items, errs, warns = [], [], []
    for p in sorted(DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errs.append(f"{p.name}: JSON 깨짐 — {e}")
            continue
        e, wn = check(d, p, by_key)
        if only and p.stem != only:
            # 다른 회차가 쓰는 중인 파일 — 이번 검사를 막지 않고 index 에서만 뺀다
            if e:
                warns.append(f"{p.name}: 오류 {len(e)}건 — 쓰는 중으로 보고 index 에서 뺀다")
            else:
                items.append(d)
            continue
        errs += e
        warns += wn
        if not e:
            items.append(d)
    if "--claim" in sys.argv:
        return claim(items, jobs)
    if "--gaps" in sys.argv:
        gaps(items, jobs)
        return 0
    for m in warns:
        print("  경고", m)
    for m in errs:
        print("  오류", m)
    if errs:
        print(f"[roles] 오류 {len(errs)}건 — index 를 굽지 않는다")
        return 1
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(build_index(items), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[roles] 통과 {len(items)}개 · 경고 {len(warns)}건 → {INDEX.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
