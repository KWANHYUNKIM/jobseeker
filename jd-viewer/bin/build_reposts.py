#!/usr/bin/env python3
"""재공고 탐지 + 변경 로그.

입력: jd-viewer/public/all_jobs_enriched.json      (모집중 + 마감, status 포함)
      catch_capture/screenshots/closed_<label>.json (누적 마감 아카이브)
저장: 정본 DB 의 job_version                        (append-only 판본 기록)
      DB 가 없으면 catch_capture/job_history.jsonl 로 물러선다
출력: jd-viewer/public/reposts.json

**무엇을 푸는가.** 같은 회사가 같은 자리를 마감했다가 다시 올린다. 채용 사이트는 그때
새 URL 을 발급하므로 겉으로는 완전히 새로운 공고로 보이고, 무엇이 달라졌는지는 아무도
말해주지 않는다. 그런데 바로 그 '무엇이 달라졌는지'가 시장 신호다 — 한 곳은
`경력3년↑` 을 `경력1년↑` 로 낮춰서 다시 올렸다. 사람을 못 구했다는 뜻이다.

**동일성 판정.** URL 은 재발급되므로 쓸 수 없다. (회사, 제목) 정규화 키를 쓴다.
회사명이 비어 있는 소스가 있어 그때는 (사이트, 제목) 으로 대체한다. 제목까지 바꾼
재공고는 놓치는데, 그건 잡으려다 서로 다른 자리를 한 자리로 합치는 쪽이 더 나쁘다.

**히스토리.** 아카이브는 (회사,제목) 으로 중복 제거를 하므로 같은 자리가 세 번
올라와도 한 줄만 남는다. 즉 아카이브만으로는 '이전 버전'이 하나뿐이다. 그래서 여기서
판본을 append 한다. 내용 해시가 기존 기록과 다를 때만 한 판이 쌓이므로, 사이클마다
돌려도 변화가 없으면 원장이 자라지 않는다. 회차가 쌓일수록 "이 자리는 네 번째
재공고이고 매번 경력 요구가 내려갔다" 같은 것이 보이게 된다.

**원장은 DB 다.** 이 이력은 다시 계산할 수 없다 — 지난 판은 그때 남겨 둔 것 말고는
복원할 방법이 없는데, 머신마다 따로 노는 파일에 얹혀 있었다(로컬 30,431줄 / 운영
44,718줄). `job_version` 의 UNIQUE (job_key, hash) 가 "같은 판을 두 번 쌓지 않는다"는
규칙을 제약으로 들고 있어, 아래 `remember()` 가 잊어도 DB 가 거절한다.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "catch_capture"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobs_filter import load_jobs  # noqa: E402
ENRICHED = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
ARCHIVE_GLOB = "closed_*.json"
ARCHIVE_DIR = ROOT / "catch_capture" / "screenshots"
HISTORY = ROOT / "catch_capture" / "job_history.jsonl"
OUT = ROOT / "jd-viewer" / "public" / "reposts.json"

# 변경 로그에 올릴 필드. 긴 본문은 '바뀜/안 바뀜'과 길이 변화만 본다 — 전문을 담으면
# 파일이 수십 MB 가 되고, 읽는 사람이 궁금한 것도 대개 '바뀌었나' 까지다.
SHORT_FIELDS = ["career", "location", "deadline", "dday", "title", "url", "site"]
LIST_FIELDS = ["tech_stack"]
LONG_FIELDS = ["qualifications", "preferences", "main_tasks", "benefits"]


def nk(s: str | None) -> str:
    return re.sub(r"\s+", "", (s or "")).lower()


def key_of(j: dict) -> tuple[str, str]:
    comp = nk(j.get("company")) or f"site:{nk(j.get('site'))}"
    return comp, nk(j.get("title"))


def content_hash(j: dict) -> str:
    payload = json.dumps(
        {f: j.get(f) for f in SHORT_FIELDS + LIST_FIELDS + LONG_FIELDS if f != "url"},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def diff(old: dict, new: dict, live: dict | None = None) -> list[dict]:
    changes: list[dict] = []
    for f in SHORT_FIELDS:
        a, b = (old.get(f) or ""), (new.get(f) or "")
        if a != b:
            changes.append({"field": f, "kind": "value", "from": str(a)[:120], "to": str(b)[:120]})
    for f in LIST_FIELDS:
        a, b = set(old.get(f) or []), set(new.get(f) or [])
        if a != b:
            changes.append({
                "field": f, "kind": "list",
                "added": sorted(b - a)[:12], "removed": sorted(a - b)[:12],
            })
    for f in LONG_FIELDS:
        (alen, asig), (blen, bsig) = _long(old.get(f)), _long(new.get(f))
        if alen == blen and asig == bsig:
            continue
        # 한쪽이 0자면 '요구가 사라졌다'가 아니라 그 판의 본문을 못 긁은 것이다.
        # jobkorea 는 본문을 별도 txt 로 받아오는데 갓 올라온 공고는 아직 없을 수 있다.
        # 실제로 텍스트 변경 121건 중 81건(66%)이 이 경우였다 — 그대로 세면
        # "재공고하면서 자격요건을 통째로 지웠다"는 잘못된 트렌드가 만들어진다.
        missing = (alen == 0) != (blen == 0)
        ch = {
            "field": f, "kind": "text", "missing": missing,
            "from_len": alen, "to_len": blen,
            "to_excerpt": (live.get(f) or "")[:180] if live else "",
        }
        # 옛 판의 전문이 있을 때(아직 DB 에 남은 마감 공고와 짝지은 경우)만 줄 단위로 본다.
        # 히스토리 판본은 (길이, 해시)만 들고 있어 무엇이 빠졌는지까지는 모른다.
        a, b = old.get(f), new.get(f)
        if not missing and isinstance(a, str) and isinstance(b, str):
            ch["added_lines"], ch["removed_lines"] = _lines_delta(a, b)
        changes.append(ch)
    return changes


def _lines(t: str) -> list[str]:
    out = []
    for ln in re.split(r"[\n•▪■◦]", t):
        ln = re.sub(r"\s+", " ", ln).strip(" -*·")
        if len(ln) >= 4:
            out.append(ln)
    return out


def _lines_delta(a: str, b: str, cap: int = 4) -> tuple[list[str], list[str]]:
    """(더해진 줄, 빠진 줄). 공백만 다른 줄은 같은 줄로 본다."""
    la, lb = _lines(a), _lines(b)
    ka, kb = {nk(x) for x in la}, {nk(x) for x in lb}
    added = [x[:120] for x in lb if nk(x) not in ka][:cap]
    removed = [x[:120] for x in la if nk(x) not in kb][:cap]
    return added, removed


# ── 왜 다시 올렸나 ─────────────────────────────────────────────────
# 회사는 이유를 말해 주지 않는다. 대신 무엇을 바꿨는지가 남는다 — 바꾼 것은 사실이고,
# 그로부터 읽는 이유는 추정이다. 화면도 둘을 갈라 보여 준다(label = 사실, why = 추정).
# weight 는 '이유로서 얼마나 강한 신호인가' — 경력 문턱을 낮춘 것은 사람을 못 구했다는
# 가장 직접적인 증거이고, 복지 문구를 다듬은 것은 가장 약하다.
_YEARS = re.compile(r"(\d+)\s*년")


def career_years(s: str | None) -> int | None:
    """'경력3년↑' → 3, '신입'·'경력무관' → 0, 모르면 None."""
    s = s or ""
    if "신입" in s or "무관" in s:
        return 0        # '신입~3년' 처럼 신입을 같이 받으면 문턱은 0 이다
    m = _YEARS.search(s)
    return int(m.group(1)) if m else None


def explain(changes: list[dict], *, rounds: int = 2, gap_days: int | None = None) -> list[dict]:
    """바뀐 것(changes)에서 '왜 다시 올렸나' 를 읽는다. 강한 이유가 앞이다."""
    reasons: list[dict] = []

    def add(code: str, label: str, why: str, weight: int) -> None:
        reasons.append({"code": code, "label": label, "why": why, "weight": weight})

    by = {c["field"]: c for c in changes if not c.get("missing")}

    c = by.get("career")
    if c and c["kind"] == "value":
        a, b = career_years(c["from"]), career_years(c["to"])
        span = f"{c['from'] or '표기 없음'} → {c['to'] or '표기 없음'}"
        if a is not None and b is not None and b < a:
            add("career_down", f"경력 요구를 낮췄어요 ({span})",
                "처음 기준으로는 지원자가 모자랐다는 신호예요. 문턱을 낮춰 지원자 폭을 넓혔어요.", 100)
        elif a is not None and b is not None and b > a:
            add("career_up", f"경력 요구를 올렸어요 ({span})",
                "지난 모집에서 맞는 사람을 못 만났거나, 더 숙련된 사람이 필요해졌어요.", 90)
        else:
            add("career_changed", f"경력 조건을 바꿨어요 ({span})",
                "지원 자격의 범위를 다시 정했어요.", 60)

    c = by.get("tech_stack")
    if c:
        plus, minus = c.get("added") or [], c.get("removed") or []
        if plus and not minus:
            add("stack_added", "요구 기술을 늘렸어요 (" + ", ".join("+" + t for t in plus[:4]) + ")",
                "맡길 일이 넓어졌거나, 지난 지원자에게서 이 기술이 아쉬웠을 수 있어요.", 70)
        elif minus and not plus:
            add("stack_removed", "요구 기술을 줄였어요 (" + ", ".join("−" + t for t in minus[:4]) + ")",
                "요구를 덜어 지원자 폭을 넓혔어요.", 75)
        else:
            add("stack_changed", "요구 기술을 바꿨어요",
                "같은 자리지만 쓰는 기술이나 맡길 일이 달라졌어요.", 65)

    def text(field: str, name: str, w: int, shrink: str, grow: str, edit: str) -> None:
        c = by.get(field)
        if not c or c["kind"] != "text":
            return
        a, b = c["from_len"], c["to_len"]
        span = f"{a:,}자 → {b:,}자"
        if b < a * 0.8:
            add(f"{field}_shrunk", f"{name}을 줄였어요 ({span})", shrink, w + 10)
        elif b > a * 1.2:
            add(f"{field}_grown", f"{name}을 늘렸어요 ({span})", grow, w)
        else:
            add(f"{field}_edited", f"{name}을 고쳐 썼어요", edit, w - 20)

    text("qualifications", "자격요건", 70,
         "필수 조건을 덜어 지원 문턱을 낮췄어요.",
         "지난 지원자들에게 부족했던 조건을 더 구체적으로 적었어요.",
         "원하는 사람을 더 정확히 그리려고 조건을 다듬었어요.")
    text("main_tasks", "주요업무", 60,
         "맡길 일을 좁혔어요 — 자리의 범위가 줄었어요.",
         "맡길 일을 넓혔어요 — 지원자가 생각한 일과 실제 일이 달랐을 수 있어요.",
         "자리의 역할을 다시 설명했어요.")
    text("preferences", "우대사항", 45,
         "우대 조건을 덜어 더 많은 사람이 지원하게 했어요.",
         "원하는 사람의 모습을 더 자세히 적었어요.",
         "우대 조건을 다듬었어요.")
    text("benefits", "복지", 35,
         "복지 설명을 덜었어요.",
         "처우·복지를 더 내세웠어요 — 조건 때문에 지원이 적었을 수 있어요.",
         "복지 설명을 다듬었어요.")

    c = by.get("location")
    if c and c["kind"] == "value":
        add("location", f"근무지가 바뀌었어요 ({c['from'] or '표기 없음'} → {c['to'] or '표기 없음'})",
            "근무지 때문에 지원이 적었거나, 일할 곳 자체가 바뀌었어요.", 60)

    c = by.get("site")
    if c and c["kind"] == "value":
        add("site_moved", f"다른 사이트에 올렸어요 ({c['from']} → {c['to']})",
            "같은 곳에서는 사람이 안 모여 노출할 곳을 바꿨어요.", 40)

    if not any(r["code"] != "site_moved" for r in reasons):
        if gap_days is not None and gap_days <= 7:
            add("same_quick", "마감 직후 같은 조건으로 다시 올렸어요",
                "모집 기간 안에 뽑지 못해 기간만 이어 붙인 것으로 보여요.", 50)
        else:
            after = f" ({gap_days}일 만에)" if gap_days is not None else ""
            add("same_later", f"같은 조건으로 다시 올렸어요{after}",
                "그때 뽑지 못했거나, 뽑은 사람이 나가 자리가 다시 비었어요.", 50)

    if rounds >= 3:
        add("repeat", f"{rounds}번째 모집이에요",
            "여러 번 올려도 못 채우는 자리예요 — 조건이나 처우에 걸리는 게 있을 수 있어요.", 85)

    reasons.sort(key=lambda r: -r["weight"])
    return reasons


def _day(s) -> datetime | None:
    try:
        return datetime.strptime(str(s or "")[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _gap(old_end, new_start) -> int | None:
    a, b = _day(old_end), _day(new_start)
    return max(0, (b - a).days) if a and b else None


def _start(j: dict) -> str:
    """공고가 올라온 날 — 원본 등록일이 있으면 그것, 없으면 우리가 처음 본 날."""
    return str(j.get("posted_date") or j.get("first_seen_at") or "")[:10]


def fetch_hidden_closed() -> list[dict]:
    """`job_dup` 가 사본으로 숨긴 **마감** 공고.

    job_dup 는 (회사, 제목)으로 묶어 모집중 한 건만 대표로 남긴다 — 재공고 판정 키와 같은
    키다. 그래서 새 공고가 올라오는 순간 옛 마감 공고는 사본이 되어 `load_jobs()` 에서
    빠지고, 이 빌더는 '마감 → 다시 열림' 의 앞쪽을 못 봤다(마감과 재공고 사이에 회차가
    한 번이라도 돌아 마감 판이 먼저 기록된 경우만 잡혔다). 여기서 따로 읽어 짝을 짓는다.
    """
    try:
        from store.db import conn as store_conn
        from store.jobs.export import JOB_SELECT, row_to_job
        with store_conn.cursor(autocommit=True) as cur:
            cur.execute(JOB_SELECT + """
                  FROM v_job v
                 WHERE v.status = 'closed'
                   AND EXISTS (SELECT 1 FROM job_dup d WHERE d.job_id = v.id)
            """)
            return [row_to_job(r, i) for i, r in enumerate(cur.fetchall(), start=1)]
    except Exception as e:                                          # noqa: BLE001
        print(f"  [reposts] 숨겨진 마감 사본을 못 읽었습니다 — 히스토리로만 봅니다: {e}")
        return []


def _rounds(starts: list[str], upto: str) -> int:
    """upto 까지 몇 번 모집했나. 사흘 안에 올라온 것은 같은 모집(사이트만 다른 사본)으로 본다."""
    days = sorted({d for d in (_day(s) for s in starts if s and s <= upto) if d})
    n, last = 0, None
    for d in days:
        if last is None or (d - last).days > 3:
            n += 1
        last = d
    return max(n, 2)


def pair_reposts(postings: list[dict]) -> dict[tuple[str, str], dict]:
    """같은 자리의 옛 마감 공고와 새 모집중 공고를 직접 짝짓는다. 둘 다 전문이 있다."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for j in postings:
        groups.setdefault(key_of(j), []).append(j)
    out: dict[tuple[str, str], dict] = {}
    for k, js in groups.items():
        live = [j for j in js if (j.get("status") or "active") == "active"]
        closed = [j for j in js if j.get("status") == "closed"]
        if not live or not closed:
            continue
        new = max(live, key=_start)
        ns = _start(new)
        # 새 공고보다 **먼저** 올라온 마감 공고만 '이전 모집' 이다. 같은 날 올라온 것은
        # 사이트만 다른 사본이 먼저 닫힌 것이지 재공고가 아니다.
        older = [j for j in closed if _start(j) and ns and _start(j) < ns]
        if not older:
            continue
        old = max(older, key=_start)
        changes = diff(old, new, new)
        gap = _gap(old.get("deadline_date") or _start(old), ns)
        rounds = _rounds([_start(j) for j in js], ns)
        out[k] = {
            "company": new.get("company") or old.get("company") or "",
            "title": new.get("title") or "",
            "url": new.get("url") or "",
            "prev_url": old.get("url") or "",
            "site": new.get("site") or "",
            "rounds": rounds,
            "prev_deadline": old.get("deadline") or old.get("deadline_date") or "",
            "now_deadline": new.get("deadline") or new.get("deadline_date") or "",
            "prev_seen": _start(old),
            "now_seen": ns,
            "gap_days": gap,
            "changes": changes,
            "reasons": explain(changes, rounds=rounds, gap_days=gap),
            "tech_stack": new.get("tech_stack") or [],
            "basis": "pair",
        }
    return out


def load_history() -> tuple[dict[str, list[dict]], bool]:
    """(자리별 판본, DB 를 쓰는가). DB 가 답하면 파일은 아예 열지 않는다."""
    try:
        from store.db.ledgers import load_job_versions
        hist = load_job_versions()
        if hist:
            return hist, True
        # 비어 있는 것과 못 읽는 것은 다르다. 여기까지 왔으면 DB 는 살아 있고
        # 원장만 아직 안 옮겨진 것이다 — 파일에서 읽고 쓰기는 DB 에 한다.
        print("  [history] DB 원장이 비어 있습니다 — 파일로 읽고 DB 로 씁니다"
              " (python -m store.db.ledgers seed --history 로 옮기세요)")
    except Exception as e:
        print(f"  [history] DB 원장을 못 읽어 파일로 물러섭니다: {e}")
        return _load_history_file(), False

    return _load_history_file(), True


def _load_history_file() -> dict[str, list[dict]]:
    hist: dict[str, list[dict]] = {}
    if not HISTORY.exists():
        return hist
    # split("\n") 이지 splitlines() 가 아니다. splitlines() 는 \n 외에 U+2028,
    # U+2029, U+0085, \x0b, \x0c 에서도 자르는데, json.dumps(ensure_ascii=False) 는
    # 그 문자들을 이스케이프하지 않고 그대로 흘려보낸다. 크롤한 JD 본문에 그런 문자가
    # 섞여 있으면 한 레코드가 두 조각으로 쪼개지고 둘 다 파싱에 실패해, 그 자리는
    # 히스토리에서 통째로 사라진 것처럼 보인다. 그러면 매 실행마다 같은 판이 다시
    # append 되어 파일만 자란다 — 새 해시는 하나도 없는데 줄 수만 느는 증상이었다.
    # (JSON 문자열 안의 U+2028 자체는 적법하므로 json.loads 는 문제없이 읽는다.)
    bad = 0
    for line in HISTORY.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        hist.setdefault(r["key"], []).append(r)
    if bad:
        print(f"  [history] 파싱 실패 {bad}줄 — 건너뜀")
    return hist


EXCERPT = 200


def snapshot(j: dict, status: str) -> dict:
    """히스토리에 남길 최소 형태.

    긴 본문은 전문을 넣지 않는다. 넣었더니 파일이 51MB 가 됐는데, 정작 변경 로그가
    쓰는 것은 길이와 앞부분뿐이다. 변화 감지는 content_hash 가 원본 전문으로 하므로
    전문을 보관하지 않아도 정확도는 그대로다.
    """
    rec = {f: j.get(f) for f in SHORT_FIELDS}
    rec["tech_stack"] = list(j.get("tech_stack") or [])
    for f in LONG_FIELDS:
        t = j.get(f) or ""
        # 길이 + 해시만. 앞부분 200자를 넣었을 때가 35MB, 전문을 넣었을 때가 51MB 였다.
        # 두 판이 같은지 판단하는 데는 (길이, 해시) 가 발췌보다 오히려 정확하고,
        # 화면에 띄울 발췌는 '지금 살아 있는 공고' 에서 그때그때 읽으면 된다.
        rec[f] = {"len": len(t), "h": hashlib.sha1(t.encode("utf-8")).hexdigest()[:12]}
    rec["status"] = status
    return rec


def _long(v) -> tuple[int, str]:
    """LONG_FIELD 값을 (길이, 지문) 으로. 예전 두 포맷(전문 문자열 / head 보관)도 받는다."""
    if isinstance(v, dict):
        if "h" in v:
            return int(v.get("len") or 0), str(v["h"])
        head = str(v.get("head") or "")
        return int(v.get("len") or 0), hashlib.sha1(head.encode("utf-8")).hexdigest()[:12]
    t = str(v or "")
    return len(t), hashlib.sha1(t.encode("utf-8")).hexdigest()[:12]


def main() -> None:
    jobs = load_jobs(ENRICHED)
    today = datetime.now().strftime("%Y-%m-%d")

    # 아카이브의 옛 버전을 히스토리 부트스트랩으로 쓴다. 히스토리가 비어 있는 첫 실행에서도
    # 과거 한 판은 확보된다 — 없으면 재공고를 "지금부터" 만 볼 수 있다.
    archived: dict[tuple[str, str], dict] = {}
    for f in sorted(ARCHIVE_DIR.glob(ARCHIVE_GLOB)):
        try:
            for a in json.loads(f.read_text(encoding="utf-8")):
                archived.setdefault(key_of(a), a)
        except (json.JSONDecodeError, OSError):
            continue

    hist, use_db = load_history()
    appended = 0
    lines: list[str] = []
    fresh: list[dict] = []

    def remember(k: tuple[str, str], j: dict, status: str, seen: str,
                 bootstrap: bool = False) -> None:
        nonlocal appended
        ks = f"{k[0]}\t{k[1]}"
        h = content_hash(j)
        prev = hist.get(ks)
        # 부트스트랩(아카이브)은 그 자리의 기록이 아예 없을 때만 넣는다. 조건 없이 넣으면
        # 매 실행마다 [아카이브판, 현재판] 이 번갈아 append 되어 파일이 실행할 때마다
        # 두 배로 자란다 — 직전 해시만 보고 판단하면 A→B→A 를 새 변경으로 오해한다.
        if bootstrap and prev:
            return
        # 직전 판이 아니라 그 자리의 **모든** 기록과 비교한다. 직전만 보면 한 자리가
        # 이미 기록된 두 상태 사이를 오갈 때(A→B→A) 매 실행마다 줄이 하나씩 쌓인다.
        # 실제로 그렇게 20개 자리가 실행마다 파일을 늘리고 있었다 — 새 해시는 하나도
        # 없는데 줄만 늘어나는, 눈으로는 안 보이는 종류의 증식이었다.
        # 대가: 공고가 예전 상태로 정확히 되돌아가면 그 회귀는 새 판으로 남지 않는다.
        # 재공고 추적이 보려는 것은 '서로 다른 상태들' 이므로 이 쪽이 맞다.
        if prev and any(p["hash"] == h for p in prev):
            return
        rec = {"key": ks, "hash": h, "seen": seen, "data": snapshot(j, status)}
        hist.setdefault(ks, []).append(rec)
        fresh.append(rec)
        lines.append(json.dumps(rec, ensure_ascii=False))
        appended += 1

    for k, a in archived.items():
        remember(k, a, "closed", a.get("_archived_at") or "bootstrap", bootstrap=True)
    # 한 실행에서 자리당 한 판만 기록한다. enriched 에는 같은 자리가 모집중과 마감 두
    # 판으로 들어 있을 수 있고(재공고된 자리의 옛 판이 아직 마감 목록에 남아 있는 경우),
    # 그대로 두 번 remember 하면 실행마다 두 해시가 번갈아 append 되어 파일이 계속 자란다.
    # '지금' 을 대표하는 것은 살아 있는 판이므로 모집중을 우선한다.
    best: dict[tuple[str, str], dict] = {}
    for j in jobs:
        k = key_of(j)
        cur = best.get(k)
        if cur is None or ((j.get("status") or "active") == "active"
                           and (cur.get("status") or "active") == "closed"):
            best[k] = j
    for k, j in best.items():
        remember(k, j, j.get("status") or "active", today)

    if fresh:
        if use_db:
            from store.db.ledgers import append_job_versions
            append_job_versions(fresh)
        else:
            with HISTORY.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")

    # ── 재공고 판정 ────────────────────────────────────────────────
    # 마감된 판이 있고, 그 뒤에 다시 모집중인 판이 있는 자리.
    by_key_now = {}
    for j in jobs:
        by_key_now.setdefault(key_of(j), []).append(j)

    # 1) 아직 DB 에 남은 옛 마감 공고와 짝지은 것 — 두 판의 전문이 다 있다
    paired = pair_reposts(list(jobs) + fetch_hidden_closed())
    reposts = list(paired.values())

    # 2) 옛 공고가 DB 에서도 사라진 자리는 히스토리 판본(길이·해시)으로 본다
    for ks, versions in hist.items():
        if len(versions) < 2:
            continue
        comp, title = ks.split("\t", 1)
        if (comp, title) in paired:
            continue
        live = [v for v in versions if v["data"].get("status") == "active"]
        closed = [v for v in versions if v["data"].get("status") == "closed"]
        if not live or not closed:
            continue
        latest = versions[-1]
        if latest["data"].get("status") != "active":
            continue                    # 지금 살아 있는 자리만 '재공고'다
        # 직전의 마감 판과 비교한다
        prev_closed = closed[-1]
        cur_live = by_key_now.get((comp, title), [None])[0]
        changes = diff(prev_closed["data"], latest["data"], cur_live)
        if not changes:
            continue
        cur = cur_live or {}
        # 판 수는 '몇 번째 모집' 이 아니다 — D-day 표기만 바뀌어도 판이 하나 쌓인다.
        # 마감 → 모집중으로 넘어간 횟수를 센다.
        st = [v["data"].get("status") for v in versions]
        rounds = max(2, 1 + sum(1 for a, b in zip(st, st[1:]) if a == "closed" and b == "active"))
        gap = _gap(prev_closed.get("seen"), latest.get("seen"))
        reposts.append({
            "company": cur.get("company") or prev_closed["data"].get("site") or "",
            "title": cur.get("title") or latest["data"].get("title") or "",
            "url": latest["data"].get("url") or "",
            "prev_url": prev_closed["data"].get("url") or "",
            "site": latest["data"].get("site") or "",
            "rounds": rounds,
            "prev_deadline": prev_closed["data"].get("deadline") or "",
            "now_deadline": latest["data"].get("deadline") or "",
            "prev_seen": prev_closed.get("seen") or "",
            "now_seen": latest.get("seen") or "",
            "gap_days": gap,
            "changes": changes,
            "reasons": explain(changes, rounds=rounds, gap_days=gap),
            "tech_stack": latest["data"].get("tech_stack") or [],
            "basis": "history",
        })

    # 이유가 강한 순 → 변화가 많은 순 — 읽을 가치가 큰 순서다
    reposts.sort(key=lambda r: (-(r["reasons"][0]["weight"] if r["reasons"] else 0),
                                -sum(1 for c in r["changes"] if not c.get("missing")),
                                -r["rounds"]))

    # 집계: 무엇이 자주 바뀌는가 (트렌드 분석의 재료), 자리마다 가장 강한 이유는 무엇인가
    reason_counts: dict[str, int] = {}
    for r in reposts:
        if r["reasons"]:
            top = r["reasons"][0]
            reason_counts[top["code"]] = reason_counts.get(top["code"], 0) + 1
    field_counts: dict[str, int] = {}
    career_moves = {"낮춤": 0, "높임": 0, "동일": 0}
    for r in reposts:
        for c in r["changes"]:
            if c.get("missing"):
                continue        # 비교 불가는 '바뀐 항목'으로 세지 않는다
            field_counts[c["field"]] = field_counts.get(c["field"], 0) + 1
            if c["field"] == "career" and c["kind"] == "value":
                # '신입' 도 0년으로 센다 — explain() 과 같은 규칙이어야 칸의 숫자와 이유가 맞는다
                a, b = career_years(c["from"]), career_years(c["to"])
                if a is not None and b is not None:
                    career_moves["낮춤" if b < a else "높임" if b > a else "동일"] += 1

    doc = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "history_versions": sum(len(v) for v in hist.values()),
        "tracked_positions": len(hist),
        "reposts": reposts,
        "summary": {
            "count": len(reposts),
            "changed_fields": sorted(field_counts.items(), key=lambda kv: -kv[1]),
            "career_moves": career_moves,
            # 자리마다 가장 강한 이유 하나씩 센 것 — 화면 머리의 '왜 다시 올렸나' 줄
            "top_reasons": sorted(reason_counts.items(), key=lambda kv: -kv[1]),
        },
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    where = "DB(job_version)" if use_db else "파일(job_history.jsonl)"
    print(f"[reposts] 판본 +{appended:,} → {where} "
          f"(누적 {doc['history_versions']:,}판 / 자리 {len(hist):,})")
    print(f"[reposts] 재공고 {len(reposts):,}건 → {OUT} ({OUT.stat().st_size:,} bytes)")
    if field_counts:
        top = ", ".join(f"{k} {v}" for k, v in sorted(field_counts.items(), key=lambda kv: -kv[1])[:6])
        print(f"  자주 바뀐 필드: {top}")
    print(f"  경력 요구: 낮춤 {career_moves['낮춤']} · 높임 {career_moves['높임']} · 동일 {career_moves['동일']}")


if __name__ == "__main__":
    main()
