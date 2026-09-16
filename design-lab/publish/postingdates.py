"""모집 시작·마감을 원본에서 찾아온다.

색인에는 마감 표기 한 줄밖에 없고 그마저 비어 있는 공고가 많다(wanted 는 마감 필드가 아예
없다). 그런데 '언제부터 언제까지 모집하나' 는 공고를 보는 사람이 제일 먼저 찾는 것이다.
그래서 없으면 원본에 가서 찾는다 — 사이트마다 적어 두는 자리가 다르다.

  wanted   : 공고 페이지의 JSON-LD `datePosted` / `validThrough`
  jumpit   : position API 의 `publishedAt` / `closedAt` / `alwaysOpen`
  jobkorea : 공고 페이지의 JSON-LD `datePosted` / `validThrough`
  saramin  : 공고 페이지의 '시작일 YYYY.MM.DD / 마감일 YYYY.MM.DD'
  dev      : catch 상세의 JSON-LD `datePosted` / `validThrough`

한 번 찾은 값은 캐시한다(state/posting_dates.json) — 게시일은 바뀌지 않고, 같은 공고를
반복해 두드리면 차단당한다. 못 찾으면 빈 값이고, 판에는 '지어낸 날짜' 를 넣지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
CATCH_DIR = LAB_DIR.parent / "catch_capture"
CACHE = LAB_DIR / "state" / "posting_dates.json"
#: 게시일은 안 바뀌고 마감일은 늦춰질 수 있다 — 며칠에 한 번만 다시 묻는다
TTL_DAYS = 5

_ISO = re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})")


def _fetcher():
    """크롤 파이프라인의 HTTP 도우미(User-Agent·타임아웃·차단 간격이 여기 맞춰져 있다)."""
    if str(CATCH_DIR) not in sys.path:
        sys.path.insert(0, str(CATCH_DIR))
    try:
        from pipeline.close_check import _fetch
    except Exception:                       # noqa: BLE001
        return None
    return _fetch


def _iso(text: str | None) -> str:
    if not text:
        return ""
    m = _ISO.search(str(text))
    if not m:
        return ""
    y, mo, d = (int(x) for x in m.groups())
    try:
        return f"{y:04d}-{mo:02d}-{d:02d}"
    except ValueError:
        return ""


def _jsonld(body: str) -> tuple[str, str]:
    """JSON-LD 의 datePosted / validThrough. 이스케이프된 형태도 같이 잡는다."""
    def one(field: str) -> str:
        m = re.search(field + r"\\{0,3}\"?\s*:\s*\\{0,3}\"([^\"\\]{4,32})", body)
        return _iso(m.group(1)) if m else ""
    return one("datePosted"), one("validThrough")


def _from_wanted(job: dict, fetch) -> dict:
    code, body = fetch(f"https://www.wanted.co.kr/wd/{job['pid']}")
    if code != 200 or not body:
        return {}
    start, end = _jsonld(body)
    return {"start": start, "end": end, "source": "wanted 공고 페이지 JSON-LD"}


def _from_jumpit(job: dict, fetch) -> dict:
    code, body = fetch(f"https://jumpit.saramin.co.kr/api/position/{job['pid']}")
    if code != 200 or not body:
        return {}
    try:
        r = json.loads(body).get("result", {})
    except json.JSONDecodeError:
        return {}
    return {"start": _iso(r.get("publishedAt")), "end": _iso(r.get("closedAt")),
            "always": bool(r.get("alwaysOpen")), "source": "jumpit API publishedAt/closedAt"}


def _from_jobkorea(job: dict, fetch) -> dict:
    code, body = fetch(f"https://www.jobkorea.co.kr/Recruit/GI_Read/{job['pid']}")
    if code != 200 or not body:
        return {}
    start, end = _jsonld(body)
    return {"start": start, "end": end, "source": "잡코리아 공고 페이지 JSON-LD"}


_SARAMIN = re.compile(r"시작일\s*(20\d{2}[.\-/]\s?\d{1,2}[.\-/]\s?\d{1,2})"
                      r"[^마]{0,40}마감일\s*(20\d{2}[.\-/]\s?\d{1,2}[.\-/]\s?\d{1,2})")


def _from_saramin(job: dict, fetch) -> dict:
    code, body = fetch(f"https://www.saramin.co.kr/zf_user/jobs/view?rec_idx={job['pid']}")
    if code != 200 or not body:
        return {}
    plain = re.sub(r"<[^>]+>", " ", body)
    if m := _SARAMIN.search(plain):
        return {"start": _iso(m.group(1)), "end": _iso(m.group(2)),
                "source": "사람인 공고 페이지 접수기간"}
    return {"start": "", "end": "", "source": "사람인 — 접수기간 못 찾음"}


def _from_dev(job: dict, fetch) -> dict:
    url = job.get("url") or ""
    if not url:
        return {}
    code, body = fetch(url)
    if code != 200 or not body:
        return {}
    start, end = _jsonld(body)
    return {"start": start, "end": end, "source": "catch 상세 JSON-LD"}


FINDERS = {"wanted": _from_wanted, "jumpit": _from_jumpit, "jobkorea": _from_jobkorea,
           "saramin": _from_saramin, "dev": _from_dev}


def _cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, CACHE)


def find(job: dict, *, network: bool = True) -> dict:
    """{"start": iso, "end": iso, "always": bool, "source": str} — 못 찾으면 빈 값."""
    key = job.get("key") or ""
    data = _cache()
    row = data.get(key)
    if row and (datetime.now() - datetime.fromisoformat(row["at"])).days < TTL_DAYS:
        return row["dates"]
    finder = FINDERS.get(job.get("site", ""))
    fetch = _fetcher() if network else None
    if not finder or not fetch:
        return {}
    try:
        dates = finder(job, fetch) or {}
    except Exception as e:                  # noqa: BLE001 — 차단·타임아웃은 '못 찾음' 이다
        dates = {"source": f"찾기 실패: {type(e).__name__}"}
    if key:
        data[key] = {"dates": dates, "at": datetime.now().isoformat(timespec="seconds")}
        _save(data)
    return dates
