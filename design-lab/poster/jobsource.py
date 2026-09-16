"""공고 원천 — 127MB 짜리 all_jobs_enriched.json 을 포스터에 필요한 만큼만 깎아 둔다.

랩 서버가 원본을 통째로 들고 있으면 8GB 머신에서 크롤과 같이 못 뜬다. 그래서
한 번만 스트리밍으로 훑어 슬림 색인(state/jobs_index.json)을 만들고, 이후에는
그것만 읽는다. 원본이 새로 갱신되면 mtime 이 달라지므로 자동으로 다시 만든다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = LAB_DIR.parent
SOURCE = ROOT_DIR / "jd-viewer" / "public" / "all_jobs_enriched.json"
INDEX = LAB_DIR / "state" / "jobs_index.json"
# 색인 필드가 바뀌면 올린다. 원본이 그대로여도 옛 색인을 다시 만든다.
#   2 → 3: 모집 기간·모집 방식(period)을 원본 full_jd 에서 뽑아 넣는다
SCHEMA = 3

# 불릿으로 쓸 수 있는 줄머리들. 사이트마다 제각각이라 넉넉히 받는다.
_BULLET = re.compile(r"^\s*(?:[*\-•·▶▪◆■□○●]|└|\d+[.)])\s*")
_NOISE = re.compile(r"^\s*[#=\-]{2,}\s*$")


def _bullets(text: str, limit: int) -> list[str]:
    """긴 문단에서 '읽을 수 있는 한 줄'만 골라낸다."""
    out: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or _NOISE.match(line):
            continue
        if line.startswith("#"):          # 소제목(#이런 동료를 만나고 싶어요)은 버린다
            continue
        if not _BULLET.match(line):
            continue
        line = _BULLET.sub("", line).strip()
        line = re.sub(r"\s+", " ", line)
        if len(line) < 6:
            continue
        if len(line) > 68:                # 포스터는 두 줄 넘어가면 못 읽는다
            line = line[:66].rstrip() + "…"
        if line in out:
            continue
        out.append(line)
        if len(out) >= limit:
            break
    return out


_GROUP_HEAD = re.compile(r"^\s*(\d+)[.)]\s+(.+)$")
_BENEFIT = re.compile(r"^(.{1,16}?)\s*:\s*(.+)$")


def _groups(text: str) -> list[dict]:
    """자르지 않은 원문을 소제목(1. 2.) 단위로 묶는다. 캐러셀은 한 줄도 버리지 않는다."""
    groups: list[dict] = [{"title": "", "items": []}]
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or _NOISE.match(line):
            continue
        head = _GROUP_HEAD.match(line)
        if head:
            groups.append({"title": re.sub(r"\s+", " ", head.group(2)).strip(), "items": []})
            continue
        line = re.sub(r"\s+", " ", _BULLET.sub("", line)).strip()
        if line and line not in groups[-1]["items"]:
            groups[-1]["items"].append(line)
    return [g for g in groups if g["title"] or g["items"]]


def _all_lines(text: str) -> list[str]:
    return [item for g in _groups(text) for item in ([g["title"]] if g["title"] else []) + g["items"]]


def _benefits(text: str) -> list[dict]:
    """'· 리프레시 : 생일자 반차, …' → {label, text}. 라벨이 없으면 label 을 비운다."""
    out = []
    for line in _all_lines(text):
        m = _BENEFIT.match(line)
        out.append({"label": m.group(1).strip(), "text": m.group(2).strip()} if m
                   else {"label": "", "text": line})
    return out


# --- 모집 기간·방식 ----------------------------------------------------
# 공고가 기간을 적는 방식은 제각각이다. 아래 네 갈래로만 읽고, 못 읽으면 비워 둔다
# (없는 정보를 '상시' 라고 지어내지 않는다 — 판에 그대로 실린다).
_PERIOD_RANGE = re.compile(
    r"(?:접수|모집|지원|채용)\s*기간[^\n:0-9]{0,6}[:：]?\s*"
    r"(\d{4})?[.\-/년]?\s*(\d{1,2})[.\-/월]\s*(\d{1,2})\s*일?"
    r"\s*(?:~|-|–|부터)\s*"
    r"(\d{4})?[.\-/년]?\s*(\d{1,2})[.\-/월]\s*(\d{1,2})\s*일?")
_PERIOD_END = re.compile(
    r"(?:접수|모집|지원|채용)\s*기간[^\n:0-9]{0,6}[:：]?\s*~?\s*"
    r"(\d{4})?[.\-/년]?\s*(\d{1,2})[.\-/월]\s*(\d{1,2})\s*일?")
_MODE = (
    ("상시", re.compile(r"상시\s*(?:채용|모집)|접수\s*기간\s*[:：]?\s*상시")),
    ("수시", re.compile(r"수시\s*(?:채용|모집)")),
    ("채용시마감", re.compile(r"채용\s*시\s*(?:마감|종료)|충원\s*시\s*마감|채용시\s*마감")),
)


def _ymd(y, mo, d, fallback_year: str = "") -> str:
    """연도가 빠진 표기는 비워 둔다 — 잘못된 연도를 넣으면 지난 공고가 살아 보인다."""
    y = y or fallback_year
    if not y:
        return ""
    try:
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    except (TypeError, ValueError):
        return ""


def _period(job: dict) -> dict:
    """{start, end, start_md, end_md, mode, quote} — 못 읽은 칸은 빈 문자열.

    연도가 없는 표기('지원 기간: 9/1 ~ 9/30')는 연도를 지어내지 않고 월·일만 남긴다 —
    판에는 '9/1–9/30' 으로 적을 수 있고, 지난 공고 판정에는 쓰지 않는다.
    """
    text = job.get("full_jd") or ""
    out = {"start": "", "end": "", "start_md": "", "end_md": "", "mode": "", "quote": ""}
    if m := _PERIOD_RANGE.search(text):
        y1, mo1, d1, y2, mo2, d2 = m.groups()
        out["start"] = _ymd(y1, mo1, d1, y2 or "")
        out["end"] = _ymd(y2, mo2, d2, y1 or "")
        out["start_md"], out["end_md"] = f"{int(mo1)}/{int(d1)}", f"{int(mo2)}/{int(d2)}"
        out["quote"] = m.group(0).strip()[:60]
    elif m := _PERIOD_END.search(text):
        y, mo, d = m.groups()
        out["end"] = _ymd(y, mo, d)
        out["end_md"] = f"{int(mo)}/{int(d)}"
        out["quote"] = m.group(0).strip()[:60]
    for name, pat in _MODE:
        if m := pat.search(text):
            out["mode"] = name
            out["quote"] = out["quote"] or m.group(0).strip()[:60]
            break
    return out


def _slim(job: dict) -> dict | None:
    site, pid = job.get("site"), job.get("pid")
    if not site or not pid:
        return None
    return {
        "key": f"{site}-{pid}",
        "site": site,
        "pid": str(pid),
        "company": (job.get("company") or "").strip(),
        "title": (job.get("title") or "").strip(),
        "url": job.get("url") or "",
        "career": (job.get("career") or "").strip(),
        "location": (job.get("location") or "").strip(),
        "stack": [t for t in (job.get("tech_stack") or []) if t][:10],
        "status": job.get("status") or "active",
        "deadline": (job.get("deadline") or job.get("deadline_date") or "").strip(),
        "dday": job.get("dday"),
        # 언제부터 언제까지 · 어떻게 모집하나. 판과 묶음 표지가 이걸 쓴다.
        "period": _period(job),
        "qualifications": _bullets(job.get("qualifications", ""), 5),
        "preferences": _bullets(job.get("preferences", ""), 4),
        "tasks": _bullets(job.get("main_tasks", ""), 5),
        # 캐러셀용 전문. 위 셋은 한 장짜리 포스터가 쓰도록 잘라 둔 것이다.
        "full": {
            "tasks": _groups(job.get("main_tasks", "")),
            "qualifications": _all_lines(job.get("qualifications", "")),
            "preferences": _all_lines(job.get("preferences", "")),
            "benefits": _benefits(job.get("benefits", "")),
        },
    }


def build_index(source: Path = SOURCE, dest: Path = INDEX) -> dict:
    """원본을 한 건씩 뜯어 슬림 색인으로 옮긴다(전체 파싱 결과를 메모리에 안 남긴다)."""
    if not source.is_file():
        raise FileNotFoundError(f"공고 원본이 없습니다: {source}")
    text = source.read_text(encoding="utf-8")
    dec = json.JSONDecoder()
    i = text.index("[") + 1
    jobs: list[dict] = []
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n or text[i] == "]":
            break
        obj, i = dec.raw_decode(text, i)
        slim = _slim(obj)
        if slim and slim["company"] and slim["title"]:
            jobs.append(slim)
    del text
    payload = {
        "schema": SCHEMA,
        "source_mtime": source.stat().st_mtime,
        "count": len(jobs),
        "jobs": jobs,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def load_index(rebuild: bool = False) -> dict:
    """색인을 읽는다. 원본이 더 새로우면 조용히 다시 만든다."""
    if not rebuild and INDEX.is_file():
        payload = json.loads(INDEX.read_text(encoding="utf-8"))
        if not SOURCE.is_file():
            return payload
        if (payload.get("source_mtime") == SOURCE.stat().st_mtime
                and payload.get("schema") == SCHEMA):
            return payload
        if not SOURCE.is_file():
            return payload
    return build_index()


def search(q: str = "", *, only_active: bool = True, limit: int = 40) -> list[dict]:
    jobs = load_index()["jobs"]
    q = (q or "").strip().lower()
    hits = []
    for j in jobs:
        if only_active and j["status"] != "active":
            continue
        if q and q not in j["company"].lower() and q not in j["title"].lower():
            continue
        hits.append(j)
        if len(hits) >= limit:
            break
    return hits


def get(key: str) -> dict | None:
    for j in load_index()["jobs"]:
        if j["key"] == key:
            return j
    return None


if __name__ == "__main__":
    p = build_index()
    print(f"[jobsource] {p['count']}건 색인 → {INDEX}")
