"""직무 역설계(공고 한 줄씩 읽기) 검사 · 색인 · 다음 일감.

    python engine/roles/validate.py            # 검사 + jd-viewer/public/roles/index.json 굽기
    python engine/roles/validate.py --gaps     # 다음에 조사할 공고(대상 1건 + 후보 몇 건)

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


def gaps(items: list[dict], jobs: list[dict], show: int = 6) -> None:
    """다음 일감: 모집중이고 업무·요건 줄이 충분한 공고 중, 그 회사 모집중 공고가 많은 곳부터.
    이미 풀이가 있는 공고와 같은 회사·같은 제목은 건너뛴다(같은 자리)."""
    done = {k for d in items for k in d["jobs"]}
    done_titles = {(d["company"], norm(d["role"])) for d in items}
    active = [j for j in jobs if j.get("status") != "closed"]
    per_co: dict[str, int] = {}
    for j in active:
        per_co[j.get("company", "")] = per_co.get(j.get("company", ""), 0) + 1
    cand = []
    for j in active:
        key = f"{j.get('site')}-{j.get('pid')}"
        if key in done or (j.get("company"), norm(j.get("title", ""))) in done_titles:
            continue
        n = sum(len(posting_lines(j.get(f))) for f in SECTIONS.values())
        if n < 5:
            continue
        cand.append((per_co.get(j.get("company", ""), 0), n, key, j))
    cand.sort(key=lambda x: (-x[0], -x[1]))
    print(f"[roles] 풀이 {len(items)}개 · 후보 공고 {len(cand)}건 — 위에서부터")
    for i, (co_n, n, key, j) in enumerate(cand[:show]):
        mark = "▶ 대상" if i == 0 else "  후보"
        print(f"  {mark} {key} · {j.get('company')} · {j.get('title')} (줄 {n}, 회사 모집중 {co_n})")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    jobs = load_jobs()
    by_key = {f"{j.get('site')}-{j.get('pid')}": j for j in jobs}
    items, errs, warns = [], [], []
    for p in sorted(DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errs.append(f"{p.name}: JSON 깨짐 — {e}")
            continue
        e, wn = check(d, p, by_key)
        errs += e
        warns += wn
        if not e:
            items.append(d)
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
