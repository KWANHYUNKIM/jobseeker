"""묶음(카테고리) — 공고 한 건이 아니라 '9월 16~22일 채용', '백엔드 채용', '대기업 채용' 처럼
여러 공고를 한 게시물로 묶는다.

사람들이 저장하고 공유하는 건 공고 한 장보다 **묶음**이다. 묶음 한 세트는 이렇게 생겼다.

    00 키워드 표지   '2026.09 · 3주차 / 개발자 채용 / 8곳 모집중'  ← 피드에서 넘길지 말지가 여기서 갈린다
    01 차례 표지     회사·자리·경력 목록                            ← 뒤에 뭐가 오는지 한눈에
    02~ 공고 판      회사별 공고 전문(전용 판이 있으면 그 판)

인스타 캐러셀은 한 게시물에 10장까지라 표지 2 + 공고 8 이 상한이다.

    python -m poster.collection cats                      카테고리 목록
    python -m poster.collection pick week                  이번 주 묶음에 뭐가 들어가나
    python -m poster.collection pick role --value backend --limit 9
    python -m poster.collection render size --value 대기업  표지+판 렌더 → out/collections/<id>/

고르는 규칙은 하나다. **모집중이고, 판에 실을 본문(주요업무)이 있는 공고만.** 회사는 한 번씩만
넣는다 — 같은 회사가 여러 장이면 묶음이 아니라 그 회사 광고가 된다.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from . import brands, jobsource
from .model import clean_role, pick_palette

LAB_DIR = Path(__file__).resolve().parent.parent
OUT = LAB_DIR / "out" / "collections"
COVER = Path(__file__).resolve().parent / "templates" / "collection_cover.html"
HOOK = Path(__file__).resolve().parent / "templates" / "collection_hook.html"
COMPANY_META = LAB_DIR.parent / "jd-viewer" / "public" / "company_meta.json"

#: 인스타 캐러셀 상한(10장) — 앞의 표지 두 장(키워드·차례)을 빼고
MAX_SLIDES = 8
#: 폰에서 확대 없이 읽히는 최소 본문 크기(1080 폭 기준)
MIN_BODY_PX = 16
#: 못 읽는 판이 빠질 때 메꿀 여유 후보 수
SPARES = 6

FAMILY_LABEL = {"backend": "백엔드", "frontend": "프론트엔드", "data": "데이터·AI",
                "infra": "인프라·데브옵스", "mobile": "모바일", "general": "개발"}


def _sizes() -> dict[str, str]:
    try:
        return json.loads(COMPANY_META.read_text(encoding="utf-8")).get("sizes", {})
    except (OSError, json.JSONDecodeError):
        return {}


def _deadline(job: dict, today: date | None = None) -> date | None:
    """마감일. 연도가 없는 표기('~ 06.16(화) 18시')도 읽는다.

    연도를 안 읽으면 지난 공고가 마감 없는 공고처럼 보인다 — 실제로 2026-06-16 에 닫힌 LG CNS
    신입 공고가 `status: active` 인 채로 '지금 지원할 수 있는 자리' 묶음에 들어왔다. 연도가 없으면
    올해로 보고, 올해로 보면 한참 지난 날짜면 내년으로 본다(연말에 1월 마감을 적는 경우).
    """
    raw = job.get("deadline") or ""
    today = today or date.today()
    # 공고 전문에서 뽑아 둔 접수 마감(period.end)이 있으면 그게 더 정확하다 — 사이트의 마감 표기는
    # 연도가 없거나 비어 있는 경우가 많다(jobsource._period).
    if not raw:
        end = (job.get("period") or {}).get("end")
        if end:
            try:
                return date.fromisoformat(end)
            except ValueError:
                pass
    m = re.search(r"(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})", raw)
    if m:
        y, mo, d = (int(x) for x in m.groups())
    else:
        m = re.search(r"(?<!\d)(\d{1,2})[.\-/]\s*(\d{1,2})(?!\d)", raw)
        if not m:
            return None
        mo, d = (int(x) for x in m.groups())
        y = today.year
    try:
        got = date(y, mo, d)
    except ValueError:
        return None
    if not re.search(r"\d{4}", raw) and (today - got).days > 180:
        try:
            got = date(y + 1, mo, d)          # 연말에 적힌 내년 1월 마감
        except ValueError:
            return got
    return got


def _md(d: date) -> str:
    return f"{d.month}월 {d.day}일"


def _span(a: date, b: date) -> str:
    """같은 달이면 '9월 14–20일', 달이 넘어가면 '9월 28일–10월 4일'."""
    return f"{a.month}월 {a.day}–{b.day}일" if a.month == b.month else f"{_md(a)}–{_md(b)}"


def _role(job: dict) -> str:
    """표지 목록에 쓸 자리 이름. clean_role 뒤에 남는 '경력' 같은 꼬리를 뗀다."""
    return re.sub(r"[\s·/-]*(경력직|경력|신입|모집|채용)$", "", clean_role(job.get("title", ""))).strip() \
        or clean_role(job.get("title", ""))


def _family(job: dict) -> str:
    """직군 판정 — **제목만 본다.**

    pick_palette 는 제목과 기술 스택을 함께 본다(판 색을 고르는 용도라 그래도 된다). 직군 묶음에서
    스택까지 보면 'Java/Spring 백엔드' 가 스택에 React 가 있다는 이유로 프론트엔드 묶음에 들어가고,
    'SM 사업 관리' 처럼 직군이 안 적힌 공고까지 끌려온다. 묶음 표지에 '프론트엔드' 라고 써 놓고
    아닌 걸 넣으면 그게 제일 눈에 띈다 — 애매하면 빼는 쪽이 낫다.
    """
    return pick_palette({"title": job.get("title", ""), "stack": []})[0]


def _data_warning(job: dict) -> str:
    """이 공고의 원본 데이터에 문제가 적혀 있으면 그 이유. 없으면 빈 문자열.

    brands/<회사>.json 의 `data_warning` 에 회사 조사 중 발견한 것을 남긴다
    ({"job": "<공고키>", "note": "..."} 또는 그 목록). 공고키가 없으면 그 회사 전체에 적용한다.
    """
    warn = (brands.find(job.get("company", "")) or {}).get("data_warning")
    for w in (warn if isinstance(warn, list) else [warn] if warn else []):
        if not isinstance(w, dict):
            continue
        if not w.get("job") or w["job"] == job.get("key"):
            return w.get("note", "원본 데이터에 문제 있음")
    return ""


def _gaps(rows: list[dict], already: set[str]) -> list[dict]:
    """이 카테고리에서 전용 판이 없어 못 들어간 회사 — 다음에 만들 판의 대기열.

    줄 세우는 기준은 **알아보는 회사 먼저**다(회사 규모 → 모집중 공고 수). 공고 수만 보면 공고를
    수십 건 뿌리는 모르는 회사가 위로 올라오는데, 묶음에 필요한 건 사람들이 아는 회사다.
    BRAND_RESEARCH.md 의 절차를 여기 위에서부터 돌리면 묶음이 채워진다.
    """
    sizes = _sizes()
    rank = {"대기업": 0, "중견기업": 1}
    count: dict[str, int] = {}
    for j in rows:
        if j["company"] in already or brands.find(j["company"]):
            continue
        count[j["company"]] = count.get(j["company"], 0) + 1
    return [{"company": c, "postings": n, "size": sizes.get(c, "")} for c, n in
            sorted(count.items(),
                   key=lambda kv: (rank.get(sizes.get(kv[0], ""), 2), -kv[1], kv[0]))][:20]


# 모집 방식 — 마감일이 없는 공고에 회사가 적어 둔 말이다. 우리가 지어내는 말이 아니다.
MODE_LABEL = {"상시": "상시 채용 · 마감 없음", "수시": "수시 채용 · 채용 시 마감",
              "채용시마감": "채용 시 마감"}
MODE_SHORT = {"상시": "상시 채용", "수시": "수시 채용", "채용시마감": "채용 시 마감"}


def period_label(job: dict, *, short: bool = False) -> str:
    """'언제부터 언제까지 / 어떻게 모집하나' 한 마디. 판과 차례가 같은 규칙을 쓴다.

    순서: **원본에서 찾아온 게시일·마감일**(publish.postingdates) → 공고 전문의 접수기간 →
    마감일 → 모집 방식(상시·수시·채용 시 마감) → 사이트 표기 → 확인한 날짜.
    없는 것은 지어내지 않는다 — 판에 그대로 실린다.
    """
    def both(a: date, b: date) -> str:
        return f"{a.month}/{a.day}~{b.month}/{b.day}" if short else f"{_md(a)}부터 {_md(b)}까지 모집중"

    live = job.get("period_live") or {}
    if live.get("always"):
        return "상시 채용" if short else "상시 채용 · 마감 없음"
    if live.get("start") and live.get("end"):
        return both(date.fromisoformat(live["start"]), date.fromisoformat(live["end"]))
    if live.get("start"):
        a = date.fromisoformat(live["start"])
        # 게시일은 찾았고 마감은 사이트에도 없다 — '언제부터' 만 말한다
        return f"{a.month}/{a.day}~" if short else f"{_md(a)}부터 모집중"
    p = job.get("period") or {}
    if p.get("start") and p.get("end"):
        return both(date.fromisoformat(p["start"]), date.fromisoformat(p["end"]))
    if p.get("start_md") and p.get("end_md"):        # 연도 없는 표기 — 날짜만 보여 준다
        return (f"{p['start_md']}~{p['end_md']}" if short
                else f"{p['start_md']}부터 {p['end_md']}까지 모집중")
    if d := _deadline(job):
        # 여기까지 왔으면 원본에서도 게시일을 못 찾은 것이다 — '언제까지' 만 말한다.
        return f"~{d.month}/{d.day}" if short else f"{_md(d)}까지 모집중"
    if mode := (MODE_SHORT if short else MODE_LABEL).get(p.get("mode", "")):
        return mode
    raw = (job.get("deadline") or "").strip()
    if raw:
        return raw[:12] if short else raw[:16]
    # 아무 날짜도 못 찾았다 — **아무것도 적지 않는다.** '9월 16일 확인' 처럼 우리 사정(확인 시점)을
    # 판에 적으면 공고를 보는 사람에게는 무슨 말인지 모를 소리가 된다. 마감된 공고는 고르는
    # 단계에서 이미 걸러지므로(publish.openness), 판에 남은 공고는 모집중인 것이다.
    return ""


def _until(job: dict) -> str:
    """차례(표지)에 쓸 짧은 판."""
    return period_label(job, short=True)


def _entry(job: dict) -> dict:
    return {"key": job["key"], "company": job["company"], "role": _role(job),
            "career": job.get("career", ""), "deadline": job.get("deadline", ""),
            "until": _until(job),
            "stack": (job.get("stack") or [])[:3],
            "brand": bool(brands.find(job["company"]))}


def _hook(kind: str, value: str, since: str, until: str) -> dict:
    """첫 장(키워드 표지)에 들어갈 말.

    피드에서는 첫 장 한 장으로 넘길지 말지가 갈린다. 그래서 차례보다 앞에 **키워드만 있는 판**을
    한 장 더 둔다 — 작은 줄(언제/무엇) + 큰 글자 두 줄(무슨 채용인가).
    """
    today = date.today()
    if kind in ("week", "deadline"):
        a, b = _week_range(since, until)
        nth = (a.day - 1) // 7 + 1                      # 그 달의 몇째 주
        top = f"{a.year}. {a.month:02d} · {nth}주차"
        # **기간이 첫 줄이다.** 사람들이 이 판에서 가장 먼저 찾는 것이 '언제부터 언제까지' 다.
        big = [_span(a, b), "개발자 채용" if kind == "week" else "마감"]
    elif kind == "role":
        top, big = f"{today.year}. {today.month:02d}. {today.day:02d} 기준", [FAMILY_LABEL.get(value, value), "채용"]
    elif kind == "size":
        top, big = f"{today.year}. {today.month:02d}. {today.day:02d} 기준", [value, "채용"]
    elif kind == "stack":
        top, big = f"{today.year}. {today.month:02d}. {today.day:02d} 기준", [value, "채용"]
    else:                                                # newgrad
        top, big = f"{today.year}. {today.month:02d}. {today.day:02d} 기준", ["신입", "채용"]
    return {"hook_top": top, "hook_big": big, "as_of": today.isoformat()}


# --- 카테고리 ----------------------------------------------------------
# kind 마다 (라벨 만드는 법, 공고 고르는 법)이 다르다. value 가 필요한 것과 아닌 것이 있다.
def _week_range(since: str, until: str) -> tuple[date, date]:
    if since and until:
        return date.fromisoformat(since), date.fromisoformat(until)
    today = date.today()
    start = today - timedelta(days=today.weekday())        # 이번 주 월요일
    return start, start + timedelta(days=6)


def _verifier():
    """공고가 지금도 모집중인지 묻는 함수. 크롤 쪽 의존이 없으면 마감 표기만 본다."""
    from publish.openness import check
    return check


def _dates(job: dict) -> dict:
    """모집 시작·마감을 원본에서 찾아온다(사이트마다 적어 두는 자리가 다르다)."""
    from publish.postingdates import find
    return find(job)


def build(kind: str, *, value: str = "", since: str = "", until: str = "",
          limit: int = MAX_SLIDES, jobs: list[dict] | None = None,
          brand_only: bool = True, verify: bool = True) -> dict:
    """카테고리 하나를 묶음 데이터로. brand_only 면 **회사 전용 판이 있는 회사만** 넣는다.

    전용 판은 BRAND_RESEARCH.md 절차로 회사마다 만든 것이다(대표 물건 → 실제 서체 → 공식 색 →
    원본 이미지). 기본 틀 판을 섞으면 묶음 전체가 '색만 바꾼 판' 으로 보인다 — 그래서 기본값이
    True 다. 전용 판이 모자라면 `gaps()` 가 다음에 만들 회사를 알려 준다.
    """
    rows = jobs if jobs is not None else jobsource.load_index()["jobs"]
    today = date.today()
    # 모집중 + 판에 실을 본문이 있는 것만. 본문 없는 공고는 판이 반쪽이 된다.
    rows = [j for j in rows if j.get("status") == "active" and (j.get("tasks") or j.get("qualifications"))]
    # 마감일이 이미 지난 공고를 뺀다. 크롤이 status 를 active 로 들고 있어도 마감은 마감이다
    # (사이트가 목록에서 안 내린 공고). '지금 지원할 수 있는 자리' 라고 써 놓고 지난 걸 넣으면 안 된다.
    rows = [j for j in rows if not ((d := _deadline(j, today)) and d < today)]
    # 원본 데이터가 깨진 공고를 뺀다 — 판은 원문을 한 글자도 바꾸지 않으므로 깨진 글이 그대로 실린다.
    # 회사 조사(brands/*.json)에서 발견하면 data_warning 에 적어 둔다(예: OCR 로 읽은 이미지 공고).
    rows = [j for j in rows if not _data_warning(j)]
    sizes = _sizes()
    kicker, title, sub = "", "", ""

    if kind == "week":
        a, b = _week_range(since, until)
        kicker, title = "이번 주 채용", _span(a, b)
        sub = "지금 지원할 수 있는 자리"
    elif kind == "deadline":
        a, b = _week_range(since, until)
        kicker, title = "마감 임박", f"{_span(a, b)} 마감"
        sub = "이 기간에 문 닫는 자리"
        rows = [j for j in rows if (d := _deadline(j)) and a <= d <= b]
    elif kind == "role":
        label = FAMILY_LABEL.get(value, value)
        kicker, title, sub = "직군별 채용", f"{label} 개발자", "모집중인 자리"
        rows = [j for j in rows if _family(j) == value]
    elif kind == "size":
        kicker, title, sub = "회사 규모별", f"{value} 채용", "모집중인 자리"
        rows = [j for j in rows if sizes.get(j["company"]) == value]
    elif kind == "stack":
        kicker, title, sub = "기술별 채용", f"{value} 쓰는 곳", "모집중인 자리"
        needle = value.lower()
        rows = [j for j in rows
                if needle in (j.get("title") or "").lower()
                or any(needle == (s or "").lower() for s in j.get("stack") or [])]
    elif kind == "newgrad":
        kicker, title, sub = "신입 가능", "신입도 되는 자리", "경력 조건에 신입이 있는 공고"
        rows = [j for j in rows if "신입" in (j.get("career") or "")]
    else:
        raise KeyError(f"모르는 카테고리: {kind}")

    matched = rows                                    # 전용 판 여부와 무관한 후보(gaps 가 쓴다)
    if brand_only:
        rows = [j for j in rows if brands.find(j["company"])]

    # 회사 한 번씩. 순서는 '사람이 알아보는 것' 부터다 — 전용 판이 있는 회사 → 큰 회사 →
    # 마감 빠른 순 → 이름. 묶음의 앞장에 모르는 회사만 나오면 넘겨 보지 않는다.
    far = date(9999, 12, 31)
    rank = {"대기업": 0, "중견기업": 1}
    rows.sort(key=lambda j: (0 if brands.find(j["company"]) else 1,
                             rank.get(sizes.get(j["company"], ""), 2),
                             _deadline(j) or far, j["company"]))
    # 회사 중복을 걷어내고 limit 보다 넉넉히 뽑는다. 판이 안 읽히는 공고(글이 너무 긴 것)는
    # render 에서 빠지고, 그 자리를 뒤 후보가 메꾼다.
    #
    # **모집이 끝났는지는 여기서 확인한다** — 렌더가 제일 비싸므로(브라우저 + 판마다 수십 초)
    # 고르는 단계에서 걸러야 한다. 확인은 원본 사이트에 묻는 것이고(publish.openness), 판정은
    # 캐시되므로 같은 공고를 반복해 두드리지 않는다. 필요한 만큼만 묻는다 — limit 을 채우면 멈춘다.
    verifier = _verifier() if verify else None
    picked, seen, closed = [], set(), []
    for j in rows:
        if j["company"] in seen:
            continue
        if verifier:
            state, why = verifier(j)
            if state != "open":
                closed.append({"company": j["company"], "key": j["key"], "state": state, "why": why})
                continue
            # 모집 기간을 원본에서 찾아 붙인다(게시일은 색인에 없다). 판과 표지가 이걸 쓴다.
            j["period_live"] = _dates(j)
            end = (j["period_live"] or {}).get("end")
            if end and date.fromisoformat(end) < date.today():
                # 원본이 모집중이라고 답했는데 마감일이 지났다 — 사이트가 목록을 안 내린 것이다
                closed.append({"company": j["company"], "key": j["key"], "state": "closed",
                               "why": f"원본 마감일 {end} 지남 ({j['period_live'].get('source', '')})"})
                continue
        seen.add(j["company"])
        picked.append(j)
        if len(picked) >= limit + SPARES:
            break
    spares = picked[limit:]
    picked = picked[:limit]

    stamp = date.today().isoformat().replace("-", "")
    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "", value)[:20]
    return {
        "brand_only": brand_only,
        # 고르는 단계에서 원본에 물어 걸러낸 것들 — 왜 빠졌는지 남긴다(렌더 전에 걸러야 토큰이 안 든다)
        "closed_out": closed[:20],
        "short_by": max(0, limit - len(picked)),      # 전용 판이 없어 못 채운 자리
        "gaps": _gaps(matched, {j["company"] for j in picked + spares}),
        **_hook(kind, value, since, until),
        "id": f"{kind}{'-' + slug if slug else ''}-{stamp}",
        "kind": kind, "value": value,
        "kicker": kicker, "title": title, "sub": sub,
        "count": len(picked),
        "size_label": {j["company"]: sizes.get(j["company"], "") for j in picked + spares},
        "jobs": [_entry(j) for j in picked],
        "spares": [_entry(j) for j in spares],
    }


# --- 렌더 --------------------------------------------------------------
def _html(template: Path, col: dict) -> str:
    data = json.dumps(col, ensure_ascii=False).replace("</", "<\\/")
    return template.read_text(encoding="utf-8").replace("/*__DATA__*/", data)


def cover_html(col: dict) -> str:
    return _html(COVER, col)


def hook_html(col: dict) -> str:
    return _html(HOOK, col)


def render(col: dict, fmt_id: str = "ig_portrait", *, out_dir: Path | None = None) -> list[Path]:
    """키워드 표지 → 차례 표지 → 공고 판 여러 장. 브랜드 전용 판이 있는 회사는 그 판으로."""
    from .carousel import FORMATS, render_onepage
    from .render import _page_maker

    dest_dir = out_dir or (OUT / col["id"])
    dest_dir.mkdir(parents=True, exist_ok=True)
    fmt = FORMATS[fmt_id]

    # 공고 판을 먼저 찍는다. 못 읽는 판(글이 너무 긴 공고)은 빼고 여유 후보로 메꾸므로,
    # 표지의 목록은 이 단계가 끝나야 확정된다.
    slides: list[tuple[dict, Path]] = []
    dropped: list[str] = []
    for job in col["jobs"] + col.get("spares", []):
        if len(slides) >= col["count"]:
            break
        frame = "brand" if job["brand"] else "onepage"
        src, layout = render_onepage(job["key"], fmt_id, frame=frame)
        px = layout["font_px"] * 1080 / fmt["w"]
        # 브랜드 전용 판은 그 회사의 '어떤 공고' 에 맞춰 만든 것이다. 다른 공고를 넣으면 글이
        # 넘쳐 본문이 작아진다 — 폰에서 못 읽을 크기면 기본 틀로 물러난다.
        if frame == "brand" and px < MIN_BODY_PX:
            print(f"[collection] {job['company']} · 브랜드 판 본문 {layout['font_px']}px → 기본 틀로")
            src, layout = render_onepage(job["key"], fmt_id, frame="onepage")
            px, frame = layout["font_px"] * 1080 / fmt["w"], "onepage"
        if px < MIN_BODY_PX:
            # 기본 틀로도 못 읽는다 = 공고 글이 한 장에 안 들어간다. 묶음에서 뺀다.
            print(f"[collection] {job['company']} 빼기 — 본문 {layout['font_px']}px 로는 폰에서 못 읽는다")
            dropped.append(f"{job['company']}({layout['font_px']}px)")
            continue
        slides.append((job, src))
        print(f"[collection] {len(slides):02d} {job['company']} · {frame} · 본문 {layout['font_px']}px")

    col["jobs"] = [j for j, _ in slides]
    col["count"] = len(slides)
    col["dropped"] = dropped

    paths = []
    for name, template in (("00_hook", HOOK), ("01_index", COVER)):
        dest = dest_dir / f"{name}_{fmt_id}.jpg"
        page = _page_maker().new_page(viewport={"width": fmt["w"], "height": fmt["h"]})
        try:
            page.set_content(_html(template, col), wait_until="load")
            page.wait_for_function("window.__ready === true", timeout=30000)
            page.query_selector(".sheet").screenshot(path=str(dest), type="jpeg", quality=95)
        finally:
            page.close()
        paths.append(dest)
    for i, (job, src) in enumerate(slides, 2):
        dest = dest_dir / f"{i:02d}_{job['key']}.jpg"
        dest.write_bytes(src.read_bytes())
        paths.append(dest)
    (dest_dir / "collection.json").write_text(json.dumps(col, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths


# --- CLI ---------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(prog="poster.collection")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cats", help="카테고리 목록")
    for name in ("pick", "render"):
        p = sub.add_parser(name)
        p.add_argument("kind", choices=["week", "deadline", "role", "size", "stack", "newgrad"])
        p.add_argument("--value", default="", help="role: backend|frontend|data|infra|mobile / size: 대기업|중견기업 / stack: React 등")
        p.add_argument("--since", default="", help="YYYY-MM-DD (week·deadline)")
        p.add_argument("--until", default="", help="YYYY-MM-DD (week·deadline)")
        p.add_argument("--limit", type=int, default=MAX_SLIDES)
        p.add_argument("--allow-generic", action="store_true",
                       help="전용 판 없는 회사도 기본 틀로 넣는다(기본은 전용 판만)")
    g = sub.add_parser("gaps", help="이 카테고리에서 전용 판이 없어 빠지는 회사(= 다음에 만들 판)")
    g.add_argument("kind", choices=["week", "deadline", "role", "size", "stack", "newgrad"])
    g.add_argument("--value", default="")
    g.add_argument("--since", default="")
    g.add_argument("--until", default="")
    args = ap.parse_args()

    if args.cmd == "cats":
        print("week      이번 주 채용 (기간 라벨, --since/--until)")
        print("deadline  기간 내 마감 (--since/--until)")
        print("role      직군별 (--value backend|frontend|data|infra|mobile)")
        print("size      회사 규모 (--value 대기업|중견기업)")
        print("stack     기술 (--value React|Kotlin|...)")
        print("newgrad   신입 가능")
        return 0

    if args.cmd == "gaps":
        col = build(args.kind, value=args.value, since=args.since, until=args.until)
        short = f" · {col['short_by']}자리 모자람" if col["short_by"] else ""
        print(f"[{col['id']}] 전용 판으로 채운 자리 {col['count']}/{MAX_SLIDES}{short}")
        if not col["gaps"]:
            print("전용 판이 없는 회사가 없다 — 이 카테고리는 다 덮었다")
            return 0
        print("다음에 만들 판 (모집중 공고 수 순) — BRAND_RESEARCH.md 절차로:")
        for row in col["gaps"]:
            print(f"  {row['postings']:>3}건  {row['company']:<26} {row['size']}")
        return 0

    col = build(args.kind, value=args.value, since=args.since, until=args.until, limit=args.limit,
                brand_only=not args.allow_generic)
    print(f"[{col['id']}] {col['kicker']} · {col['title']} · {col['count']}곳")
    for j in col["jobs"]:
        print(f"  - {j['company']:<22} {j['role'][:34]:<36} {j['career']}"
              f"{'  [브랜드 판]' if j['brand'] else ''}")
    if not col["count"]:
        print("조건에 맞는 공고가 없다 — 카테고리나 기간을 바꿔라")
        return 1
    if args.cmd == "render":
        from .render import shutdown
        try:
            paths = render(col)
        finally:
            shutdown()
        print(f"[collection] {len(paths)}장 → {paths[0].parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
