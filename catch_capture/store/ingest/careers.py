"""커리어 후기(var/careers/) → 정본 DB(`career_post`·`career_story`·`career_roster`, 019).

careers.cycle 이 회차 끝에 부른다(실패해도 회차는 그대로 끝난다). 처음 한 번은 손으로:

    python -m store.ingest.careers            # 바뀐 것만 쓴다(content_hash)
    python -m store.ingest.careers --dry-run  # 무엇이 몇 건 바뀌는지만
    python -m store.ingest.careers --full     # 해시를 무시하고 전부 다시 쓴다(규칙을 고친 뒤)

무엇을 쓰나.
  - 원문(raw/*.json)은 그대로 career_post 에. 본문은 공개 API 로 나가지 않는다(019 머리말).
  - 경험담은 careers.report.load_rows 가 정리한 줄(원문으로 다시 본 학력·전환, 서류·나이)을 쓴다 —
    보고서와 화면의 숫자가 같은 규칙에서 나온다. 자르는 축은 여기서 미리 계산해 열로 둔다:
    회사 유형(company_type), 전환 갈래(transition_cat), 경력직의 출발지(origin), 교육과정(program).
    백엔드는 catch_capture 를 import 하지 않으므로 이 판정은 여기에만 있다.
  - 걸러진 글(is_story=false, IT 아님)도 행을 남긴다 — counted=false.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys as _sys
from datetime import date
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))

from careers import report as rp  # noqa: E402
from careers import store as cs  # noqa: E402
from core.classifier import _norm_company, _whitelist_size  # noqa: E402
from core.normalize import company as norm  # noqa: E402

ROSTER_ROWS = cs.DIR / "roster" / "rows.jsonl"

# ── 회사 유형 ───────────────────────────────────────────────────────────
# 위에서부터 먼저 맞는 것. 금융을 빅테크보다 먼저 본다(카카오뱅크·토스뱅크는 금융).
_EN = r"(?<![A-Za-z])"
_EN_END = r"(?![A-Za-z])"
TYPE_RULES: list[tuple[str, re.Pattern]] = [
    ("금융", re.compile(
        r"은행|뱅크|(?i:bank)|증권|카드|보험|생명|화재|캐피탈|금융|저축|자산운용|투자|핀테크|코스콤|거래소|예탁결제|"
        r"페이(?!지)|" + _EN + r"(?:KB|NH|IBK|BNK|DGB|FIS|IBKS)" + _EN_END + r"|신한|하나(?:은행|금융|카드|증권|티아이|손해)|"
        r"우리(?:은행|카드|FIS|금융)|농협|미래에셋|케이뱅크|두나무|업비트|빗썸")),
    ("공공", re.compile(
        r"공사$|공단|진흥원|연구원|연구소|정부|시청|구청|도청|공공|한국전력|한전|코레일|철도|국민연금|건강보험|"
        r"우정|국방|군무원|공무원|교육청|" + _EN + r"(?:LH|ETRI|KISA|NIA|NIPA|KAIST)" + _EN_END)),
    ("게임", re.compile(
        r"넥슨|(?i:nexon)|엔씨|(?i:ncsoft|nc\s?soft)|넷마블|크래프톤|(?i:krafton)|스마일게이트|펄어비스|컴투스|위메이드|"
        r"데브시스터즈|카카오게임즈|시프트업|네오위즈|그라비티|웹젠|게임")),
    ("외국계", re.compile(
        r"(?i:google|amazon|\baws\b|microsoft|\bmeta\b|apple|oracle|\bibm\b|\bsap\b|salesforce|nvidia|intel|qualcomm|cisco|"
        r"uber|airbnb|netflix|tiktok|bytedance|agoda|booking|delivery\s?hero|shopify|stripe|atlassian|datadog)|"
        r"구글|아마존|마이크로소프트|메타$|애플|오라클|엔비디아|인텔|퀄컴|시스코|넷플릭스|틱톡|바이트댄스|아고다|딜리버리히어로")),
    ("SI·SM", re.compile(
        _EN + r"(?:SI|SM|CNS|SDS|C&C|I&C)" + _EN_END + r"|에스디에스|정보통신|정보기술|데이타|데이터시스템|"
        r"시스템즈?$|오토에버|포스코DX|롯데정보|롯데이노베이트|아이앤씨|한화시스템|대우정보|쌍용정보|KTDS|kt\s?ds")),
    ("빅테크·플랫폼", re.compile(
        r"네카라|네이버|(?i:naver)|카카오|(?i:kakao)|라인|(?i:\bline\b)|쿠팡|(?i:coupang)|우아한|배달의\s?민족|배민|당근|토스|"
        r"비바리퍼블리카|(?i:toss)|야놀자|무신사|오늘의\s?집|버킷플레이스|컬리|직방|하이퍼커넥트|센드버드|몰로코|리디|"
        r"번개장터|여기어때|쏘카|요기요|11번가|(?i:ssg)|에이블리|지그재그|29CM|당근마켓|크림|네이버웹툰|스노우")),
]
# 화이트리스트가 계열사 표기를 놓치는 대기업(SKT·대한항공…) — 이름 앞머리로 본다.
_CHAEBOL = re.compile(r"^(?:SK|삼성|LG|현대|기아|롯데|CJ|한화|포스코|GS|KT|두산|HD|대한항공|아시아나|신세계|이마트|올리브영|아모레|LS|효성|코오롱)")
# report._program 이 놓치는 교육과정·동아리·병과 — 회사 칸에 들어온 것을 교육과정으로 옮긴다.
_EXTRA_PROG = re.compile(r"(?i)AICE|BOAZ|보아즈|피로그래밍|\bCMC\b|데브코스|\bBoB\b|SKALA|DEVOCEAN|코드스쿼드|인턴십$|정보보호병|^ICT$")

TYPES = ["빅테크·플랫폼", "대기업", "금융", "공공", "게임", "외국계", "SI·SM", "중견기업", "중소·스타트업", "교육과정", "미분류"]


# 이름이 아니라 설명인 것 — '두번째 회사' · 'C 기업' · 'Pre-A 단계 스타트업' · '보험회사 IT 자회사'. 회사 칸에서는
# 빼고(company=NULL) 유형만 설명으로 가른다. 자격증·과정 이름이 회사 칸에 잘못 들어온 것도 여기서 뺀다.
_ANON = re.compile(r"^[A-Za-z]\s?(?:사|기업|회사|스타트업)$|(?:회사|기업|상장사|자회사|스타트업|단계|불명|모름|익명|비공개|미공개|곳)$|"
                   r"^(?:SQLD|ADsP|정보처리기사|정처기|null|none|없음|기타|기억하지 않음|언론사)$", re.I)
_ANON_SIZE = [("대기업", r"대기업|그룹|상장사"), ("중견기업", r"중견"), ("중소·스타트업", r"스타트업|중소|소기업|시리즈|Pre-?A")]


def is_anonymous(company: str | None) -> bool:
    co = (company or "").strip()
    return not co or bool(_ANON.search(co))


def company_type(company: str | None, program: str | None) -> tuple[str, str | None]:
    """(유형, 규모) — 규모는 core.classifier 화이트리스트가 아는 것만(대기업·중견기업), 모르면 None."""
    if program:
        return "교육과정", None
    co = (company or "").strip()
    if not co or co.lower() in ("null", "none", "없음", "모름"):
        return "미분류", None
    if is_anonymous(co):
        for name, rx in TYPE_RULES:
            if rx.search(co):
                return name, None
        for name, rx in _ANON_SIZE:
            if re.search(rx, co):
                return name, None
        return "미분류", None
    size, _ = _whitelist_size(_norm_company(co))
    for name, rx in TYPE_RULES:
        if rx.search(co):
            return name, size
    if size == "대기업" or _CHAEBOL.search(co):
        return "대기업", size
    if size == "중견기업":
        return "중견기업", size
    return "중소·스타트업", size


# ── 경력직 출발지 ────────────────────────────────────────────────────────
# 어디서 떠나 왔나 — 전환 문장의 화살표 왼쪽과, 마지막 단계 앞의 경로 문장에서 찾는다.
ORIGIN_RULES = [
    ("SI·SM", r"(?<![A-Za-z])(?:SI|SM)(?![A-Za-z])|에스아이|파견|솔루션\s?회사|에이전시|외주|하청"),
    ("빅테크·플랫폼", r"네이버|카카오|라인|쿠팡|배민|우아한|토스|당근|네카라|빅테크"),
    ("대기업", r"대기업|삼성|LG|SK|현대|롯데|CJ|한화|포스코|GS"),
    ("금융", r"은행|증권|카드사|보험|금융|핀테크"),
    ("공공", r"공공|공기업|공무원|공사|공단|군무원"),
    ("게임", r"게임"),
    ("외국계·해외", r"외국계|해외|미국|일본|싱가포르|유럽"),
    ("스타트업", r"스타트업|시리즈\s?[A-E]|초기\s?기업|창업"),
    ("중견·중소", r"중소|중견|소기업|작은\s?회사"),
    ("프리랜서", r"프리랜서|프리랜스|1인\s?개발"),
    ("비개발 직장", r"비개발|영업|마케팅|디자이너|기획자|회계|교사|간호|공정|생산|서비스직|사무직|은행원"),
    ("군·산업기능요원", r"산업기능요원|전문연구요원|병역특례|군\s?복무|장교|부사관"),
]


def origin(r: dict) -> str | None:
    """경력직(이직·전환)만. 못 찾으면 '확인되지 않음'."""
    yb = r.get("years_before")
    career = r.get("level") == "경력" or r.get("kind") in ("이직", "직무전환") or (isinstance(yb, (int, float)) and yb > 0)
    if not career:
        return None
    t = str(r.get("transition") or "")
    text = t.split("→")[0] if "→" in t else t
    steps = [s.get("step", "") for s in (r.get("path") or []) if isinstance(s, dict)]
    text += " " + " ".join(steps[:-1] if len(steps) > 1 else steps)
    for name, rx in ORIGIN_RULES:
        if re.search(rx, text):
            return name
    return rp.UNKNOWN


def destination(r: dict) -> tuple[str | None, str | None]:
    """(간 곳, 어디서 읽었나). 회사 칸이 비고 다른 지원처 중 최종 합격이 하나면 그곳."""
    co = r.get("company")
    if isinstance(co, str) and co.strip() and co.strip().lower() not in ("null", "none"):
        return co.strip(), "company"
    won = [o.get("company") for o in (r.get("_others") or [])
           if isinstance(o, dict) and isinstance(o.get("company"), str) and o.get("company")
           and re.search(r"합격", str(o.get("result") or "")) and not re.search(r"불", str(o.get("result") or ""))]
    if len(won) == 1:
        return won[0].strip(), "other_companies"
    return None, None


# ── 적재 ───────────────────────────────────────────────────────────────

def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _date(s) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _post_row(b: dict) -> dict:
    row = {"id": b["id"], "source": b.get("source") or b["id"].split("-")[0], "url": b.get("url"),
           "title": b.get("title"), "posted_on": _date(b.get("date")),
           "tags": [str(t) for t in (b.get("tags") or []) if t][:30], "query": b.get("query"),
           "body": (b.get("body") or "").replace("\x00", ""), "collected_at": b.get("collected_at") or None}
    row["content_hash"] = _h({k: row[k] for k in ("url", "title", "posted_on", "tags", "body")})
    return row


def _others_raw(paths: dict[str, dict], rid: str) -> list:
    """report._clean 이 other_companies 를 글자 목록으로 바꿔 버리므로 원래 모양은 paths 에서 다시 읽는다."""
    v = (paths.get(rid) or {}).get("other_companies")
    return [o for o in v if isinstance(o, dict)] if isinstance(v, list) else []


def story_rows(raw: dict[str, dict]) -> list[dict]:
    paths = {r["id"]: r for r in cs.read_paths() if r.get("id")}
    counted = {r["id"]: r for r in rp.load_rows(raw, match=False)}
    out = []
    for rid, p in paths.items():
        if rid not in raw:
            continue                                  # 원문이 없는 줄은 FK 를 못 맞춘다(지운 글)
        r = counted.get(rid)
        if r is None:                                 # 경험담이 아니거나 IT 이야기가 아닌 글
            data = {k: p.get(k) for k in ("kind", "summary") if p.get(k)}
            row = {"post_id": rid, "is_story": bool(p.get("is_story")), "counted": False, "kind": p.get("kind"),
                   "year": None, "period": None, "company": None, "company_key": None, "program": None,
                   "company_type": None, "company_size": None, "role": None, "level": None, "years_before": None,
                   "transition": None, "transition_cat": None, "origin": None, "education": None, "age": None,
                   "data": data, "extracted_by": p.get("by") or p.get("screened")}
        else:
            r["_others"] = _others_raw(paths, rid)
            prog = rp._program(r)
            if not prog and isinstance(r.get("company"), str) and _EXTRA_PROG.search(r["company"]):
                prog = r["company"].strip()
            dest, dest_from = (None, None) if prog else destination(r)
            ctype, size = company_type(dest, prog)
            desc = None
            if dest and is_anonymous(dest):           # 이름이 아니라 설명 — 유형만 남기고 회사 칸은 비운다
                desc, dest = dest, None
            year, year_from = (r["year"], "story") if isinstance(r.get("year"), int) else (None, None)
            if year is None:
                d = _date(raw[rid].get("date") or p.get("posted"))
                year, year_from = (d.year, "posted") if d else (None, None)
            yb = r.get("years_before")
            data = {k: r.get(k) for k in ("summary", "path", "spec", "selection", "stack", "prep_months", "prep_methods",
                                          "key_factors", "advice", "market_note", "background", "application")}
            data |= {"other_companies": r.pop("_others"), "year_from": year_from, "company_from": dest_from,
                     "company_desc": desc,
                     "path_tags": sorted({t for s in (r.get("path") or []) for t in rp._tags(s.get("step", ""))}),
                     "age_how": "본문" if r.get("age") else None}
            row = {"post_id": rid, "is_story": True, "counted": True, "kind": r.get("kind"), "year": year,
                   "period": r.get("period") if isinstance(r.get("period"), str) else None,
                   "company": prog or dest, "company_key": norm(prog or dest) if (prog or dest) else None,
                   "program": prog, "company_type": ctype, "company_size": size,
                   "role": r.get("role"), "level": r.get("level"),
                   "years_before": yb if isinstance(yb, (int, float)) and 0 <= yb < 50 else None,
                   "transition": r.get("transition") if isinstance(r.get("transition"), str) else None,
                   "transition_cat": rp._transition(str(r.get("transition") or "")) or None,
                   "origin": origin(r), "education": rp._edu(r),
                   "age": r.get("age") if isinstance(r.get("age"), int) else None,
                   "data": data, "extracted_by": p.get("by")}
        row["content_hash"] = _h({k: v for k, v in row.items() if k != "content_hash"})
        out.append(row)
    return out


def roster_rows() -> list[dict]:
    out = []
    if not ROSTER_ROWS.exists():
        return out
    for line in ROSTER_ROWS.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not r.get("post"):
            continue
        rows = [{k: v for k, v in x.items() if k != "name"} for x in (r.get("rows") or []) if isinstance(x, dict)]
        row = {"post": r["post"], "url": r.get("url"), "tag": r.get("tag"), "posted_on": _date(r.get("date")),
               "poster": r.get("poster"), "list_kind": r.get("list_kind"), "it": bool(r.get("it")), "rows": rows}
        row["content_hash"] = _h(row)
        out.append(row)
    return out


def _upsert(cur, table: str, key: str, rows: list[dict], *, full: bool, json_cols=()) -> int:
    from psycopg.types.json import Jsonb
    if not rows:
        return 0
    cur.execute(f"SELECT {key} AS k, content_hash AS h FROM {table}")
    have = {r["k"]: r["h"] for r in cur.fetchall()}
    todo = [r for r in rows if full or have.get(r[key]) != r["content_hash"]]
    if not todo:
        return 0
    cols = list(todo[0].keys())
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != key) + ", updated_at = now()"
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('%s' for _ in cols)}) "
           f"ON CONFLICT ({key}) DO UPDATE SET {sets}")
    cur.executemany(sql, [[Jsonb(r[c]) if c in json_cols else r[c] for c in cols] for r in todo])
    return len(todo)


def sync(*, dry_run: bool = False, full: bool = False) -> dict:
    raw = {r["id"]: r for r in cs.raw_items() if r.get("id")}
    posts = [_post_row(b) for b in raw.values()]
    stories = story_rows(raw)
    roster = roster_rows()
    counts = {"posts": len(posts), "stories": len(stories), "counted": sum(s["counted"] for s in stories),
              "roster": len(roster)}
    if dry_run:
        return counts
    from store.db import conn as store_conn
    with store_conn.cursor() as cur:
        counts["posts_written"] = _upsert(cur, "career_post", "id", posts, full=full)
        counts["stories_written"] = _upsert(cur, "career_story", "post_id", stories, full=full, json_cols=("data",))
        counts["roster_written"] = _upsert(cur, "career_roster", "post", roster, full=full, json_cols=("rows",))
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    print(json.dumps(sync(dry_run=a.dry_run, full=a.full), ensure_ascii=False))


if __name__ == "__main__":
    main()
