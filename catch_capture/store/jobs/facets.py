"""공고의 필터 축(지역·시군구·직군·경력 구간) — 뷰어 규칙의 파이썬 판.

지금까지 이 넷은 브라우저가 계산했다. 뷰어가 공고 전량(184MB)을 받아 놓고
`src/features/jobs/utils/region.ts`·`classify.ts`·`career.ts` 로 한 건씩 접어 필터와 칩 건수를 셌다.
필터를 서버(`store.api.main`)로 옮기면 같은 규칙이 SQL 쪽에도 있어야 한다.

**규칙 원본은 여전히 TS 쪽이다.** 여기는 그걸 글자 그대로 옮긴 사본이고, 둘이
어긋나지 않는지는 `python -m store.jobs.facets --parity` 가 실데이터 전량으로 대조한다
(node 로 TS 를 직접 돌려 비교). TS 규칙을 고치면 여기도 고치고 그 대조를 돌린다.

옮길 때 걸리는 자리 하나: **JS 정규식의 `\\b` 와 `\\s` 는 ASCII 기준이다.** 한글은
단어 문자가 아니라서 JS 에서 `/\\b(안드로이드)\\b/` 는 한글 사이에서 안 걸린다.
파이썬 `re` 는 기본이 유니코드라 같은 식이 걸려 버린다 — 그래서 전부 `re.ASCII` 로
컴파일한다. 대신 ASCII 모드의 IGNORECASE 는 ASCII 만 접는데, JS `/i` 도 규칙에
나오는 글자(영문)에 대해서는 같은 답을 낸다.

계산 결과는 `job_facet` 표(db/migrations/010)에 저장되고 `refresh()` 가 채운다.
"""
from __future__ import annotations

import re

# ── 경력 구간 (career.ts) ────────────────────────────────────────────────

_ENTRY = re.compile(r"신입|무관")
_NUM = re.compile(r"(\d+)", re.ASCII)


def career_bucket(career: str | None) -> str:
    if not career:
        return "정보없음"
    if _ENTRY.search(career):
        return "신입/무관"
    m = _NUM.search(career)
    if not m:
        return "정보없음"
    n = int(m.group(1))
    if n <= 2:
        return "1-2년"
    if n <= 4:
        return "3-4년"
    if n <= 7:
        return "5-7년"
    return "8년+"


# ── 직군 (classify.ts) ───────────────────────────────────────────────────

_F = re.ASCII | re.IGNORECASE


# JS 의 String.prototype.trim 과 \s 는 유니코드 공백(NBSP·전각 공백 등)까지 공백으로 본다.
# re.ASCII 의 \s 는 ASCII 공백뿐이라, 사람인 본문의 전각 들여쓰기('시스템\n\u3000운영')가
# JS 에서는 `시스템\s*운영` 에 걸리고 여기서는 안 걸렸다. 규칙의 \s 를 이 집합으로 바꿔 넣는다.
_JS_WS = ("\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008"
          "\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff")
_WS_CLASS = re.escape(_JS_WS)


def _r(p: str) -> re.Pattern:
    p = p.replace(r"[\s-]", "[" + _WS_CLASS + "-]").replace(r"[-\s]", "[-" + _WS_CLASS + "]")
    p = p.replace(r"\s", "[" + _WS_CLASS + "]")
    return re.compile(p, _F)


RULES: list[tuple[str, list[re.Pattern]]] = [
    ("백엔드", [
        _r(r"백[\s-]?엔드|backend|back[\s-]?end|서버\s*개발|server\s*dev"),
        _r(r"\b(API|REST|gRPC|MSA)\b"),
        _r(r"\b(Spring|Spring\s*Boot|Django|Flask|FastAPI|Express|NestJS|Rails|Laravel|\.NET)\b"),
        _r(r"\b(Node\.?js|Java|Kotlin|Go|Golang|Scala|Ruby|PHP)\b.*\b(개발|engineer|developer)\b"),
        _r(r"\b(Python|Rust|C#|Scala|Ruby|PHP|Elixir)\s+(developer|engineer|programmer)\b"),
    ]),
    ("프론트엔드", [
        _r(r"프[\s-]?론[\s-]?트[\s-]?엔드|frontend|front[\s-]?end|클라이언트\s*웹"),
        _r(r"\b(React|Vue|Angular|Next\.?js|Nuxt|Svelte)\b"),
        _r(r"\b(웹\s*퍼블리|publisher|UI\s*개발)\b"),
        _r(r"\bweb\s+(developer|engineer)\b"),
    ]),
    ("모바일", [
        _r(r"\b(iOS|Android|안드로이드|모바일\s*개발|모바일\s*앱|앱\s*개발)\b"),
        _r(r"\b(Swift|Kotlin|Flutter|React\s*Native)\b"),
    ]),
    ("AI/ML", [
        _r(r"\b(AI|ML|머신러닝|딥러닝|인공지능|MLOps|데이터\s*사이언티스트?|data\s*scien(?:tist|ce)?)\b"),
        _r(r"\b(TensorFlow|PyTorch|Keras|Scikit[-\s]?learn|HuggingFace|LangChain|OpenAI|LLM|NLP|CV|컴퓨터\s*비전)\b"),
        _r(r"\b(데이터\s*엔지니어|data\s*engineer)\b"),
        _r(r"\b(research\s*engineer|research\s*scientist|applied\s*scientist|ml\s*engineer|machine\s*learning)\b"),
    ]),
    ("펌웨어/임베디드", [
        _r(r"펌웨어|firmware|임베디드|embedded|반도체\s*설계|SoC|RTOS|MCU|FPGA|디바이스\s*드라이버"),
        _r(r"\b(C\/?C\+\+|C\+\+|어셈블리|assembly)\b.*\b(임베디드|펌웨어|hw|hardware)\b"),
    ]),
    ("DevOps/인프라", [
        _r(r"DevOps|SRE|MLOps|infrastructure|인프라|클라우드\s*엔지니어|cloud\s*engineer|플랫폼\s*엔지니어"
           r"|platform\s*engineer|site\s*reliability"),
        _r(r"\b(Kubernetes|K8s|Docker|Terraform|Ansible|Jenkins|GitHub\s*Actions|AWS|GCP|Azure)\b.*"
           r"\b(엔지니어|engineer|운영|ops)\b"),
        _r(r"시스템\s*운영|시스템\s*관리"),
    ]),
    ("데이터", [
        _r(r"데이터\s*엔지니어|data\s*engineer|데이터\s*분석|data\s*analy|빅데이터|big\s*data|BI\s*개발"),
        _r(r"\b(Hadoop|Spark|Airflow|Kafka|ETL|Snowflake|BigQuery)\b"),
        _r(r"data\s*(scientist|governance|platform|warehouse|analyst)"),
    ]),
    ("보안", [
        _r(r"정보\s*보안|보안\s*엔지니어|security\s*engineer|침해\s*대응|모의\s*해킹|penetration|보안\s*개발"
           r"|\b(appsec|infosec|cyber\s*security|cybersecurity|application\s*security|product\s*security"
           r"|cloud\s*security|security\s*researcher)\b"),
    ]),
    ("게임", [_r(r"게임\s*개발|game\s*dev|game\s*client|game\s*server|언리얼|unreal|유니티|unity")]),
    ("QA", [_r(r"\bQA\b|품질\s*보증|품질\s*엔지니어|test\s*engineer|테스트\s*자동화|automation\s*test"
               r"|automation\s*engineer|\bSDET\b")]),
    ("풀스택", [_r(r"풀스택|full[\s-]?stack")]),
]


def _js_slice(text: str, n: int) -> str:
    """JS `str.slice(0, n)` — UTF-16 코드 단위로 자른다(이모지 등 BMP 밖 글자는 2칸)."""
    if len(text) <= n // 2:
        return text
    units = text.encode("utf-16-le")[: n * 2]
    return units.decode("utf-16-le", "ignore")


def classify_roles(title: str | None, tech_stack: list[str] | None = None,
                   extra_text: str | None = "") -> list[str]:
    blob = " | ".join([title or "", " ".join(tech_stack or []), _js_slice(extra_text or "", 500)])
    roles = [role for role, pats in RULES if any(p.search(blob) for p in pats)]
    if "풀스택" in roles:
        if "백엔드" not in roles:
            roles.append("백엔드")
        if "프론트엔드" not in roles:
            roles.append("프론트엔드")
    return roles or ["기타"]


# ── 지역·시군구 (region.ts) ──────────────────────────────────────────────

REGIONS = ["서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
           "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
OVERSEAS = "해외·원격"
UNKNOWN_REGION = "정보없음"
REGION_OPTIONS = [*REGIONS, OVERSEAS, UNKNOWN_REGION]

_DISTRICT = re.compile(r"^\s*([가-힣]+?(?:시|군|구))")
_ADMIN_SUFFIX = re.compile(r"특별|광역|자치")
_LONG_SIDO = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원",
    "충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전북특별자치도": "전북",
    "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주", "제주도": "제주",
}
_FOREIGN = [
    "해외", "일본", "중국", "미국", "인도", "베트남", "싱가포르", "대만", "홍콩",
    "필리핀", "인도네시아", "태국", "말레이시아", "캄보디아", "캐나다", "호주",
    "독일", "영국", "프랑스", "아시아", "유럽", "북미", "중동", "아프리카",
]
_ROMANIZED = [
    (_r(r"seoul"), "서울"),
    (_r(r"pangyo|seongnam|bundang"), "경기"),
    (_r(r"busan"), "부산"), (_r(r"incheon"), "인천"), (_r(r"daejeon"), "대전"),
    (_r(r"daegu"), "대구"), (_r(r"gwangju"), "광주"), (_r(r"ulsan"), "울산"),
    (_r(r"sejong"), "세종"), (_r(r"jeju"), "제주"),
]
_HANGUL = re.compile(r"[가-힣]")
_KOREA = _r(r"korea")
_LEAD_KOREA = re.compile(r"^대한민국[" + _JS_WS + r"]*")


def _js_trim(s: str) -> str:
    return s.strip(_JS_WS)


def _match_region(text: str) -> str | None:
    for long, short in _LONG_SIDO.items():
        if text.startswith(long):
            return short
    for r in REGIONS:
        if text.startswith(r):
            return r
    return None


def place_of(location: str | None, overseas: bool | None = False) -> tuple[str, str | None]:
    """(지역, 시군구). region.ts 의 placeOf 와 같은 답을 낸다."""
    if overseas:
        return OVERSEAS, None
    raw = _js_trim(location or "")
    if not raw:
        return UNKNOWN_REGION, None
    segs = [s for s in (_js_trim(x) for x in re.split(r"[|\n]", _LEAD_KOREA.sub("", raw))) if s]
    for seg in segs:
        region = _match_region(seg)
        if not region:
            continue
        rest = seg[len(region):] if seg.startswith(region) else seg
        # JS 의 \s 는 유니코드 공백까지 — _DISTRICT 앞자리의 공백도 그렇게 벗긴다.
        m = _DISTRICT.match(rest.lstrip(_JS_WS))
        district = m.group(1) if m and not _ADMIN_SUFFIX.search(m.group(1)) else None
        return region, district
    if any(any(s.startswith(f) for f in _FOREIGN) for s in segs):
        return OVERSEAS, None
    if not _HANGUL.search(raw):
        for pat, region in _ROMANIZED:
            if pat.search(raw):
                return region, None
        if _KOREA.search(raw):
            return UNKNOWN_REGION, None
        return OVERSEAS, None
    return UNKNOWN_REGION, None


def _stacks(tech_stack: list[str] | None) -> list[str]:
    """칩 건수용 스택 이름 — 뷰어 stackCounts 처럼 앞뒤 공백을 벗기고 공고 안 중복을 뺀다."""
    out: list[str] = []
    for t in tech_stack or []:
        k = (t or "").strip()
        if k and k not in out:
            out.append(k)
    return out


def facets_of(job: dict) -> dict:
    """공고 한 건의 필터 축. 입력은 뷰어 Job 형태(export.fetch_jobs 가 만드는 것)."""
    region, district = place_of(job.get("location"), job.get("overseas"))
    return {
        "region": region,
        "district": district,
        "roles": classify_roles(job.get("title"), job.get("tech_stack"), job.get("qualifications")),
        "career_bucket": career_bucket(job.get("career")),
    }


# ── 회사 규모 (jd-viewer/bin/build_company_meta.py 가 하던 일) ────────────

def company_sizes(jobs) -> dict[str, str]:
    """{공고에 적힌 회사명 원문: '대기업'|'중견기업'|'중소기업'}.

    판정 규칙의 소유자는 dashboard/classifier 하나다(화이트리스트 + 공고 본문의
    사원수·매출액). 회사명 정규화로 묶어 그 회사 공고들에서 가장 큰 사원수·매출액을
    쓴다. `jobs` 는 한 번만 훑는 반복자여도 된다 — 본문을 쌓아 두지 않고 회사별
    최댓값만 들고 있다(공고 본문 합이 100MB 를 넘는다).
    """
    from collections import Counter, defaultdict
    from dashboard.classifier import (
        _norm_company, classify_company_size, extract_headcount, extract_revenue_eok,
    )
    name_votes: dict[str, Counter] = defaultdict(Counter)
    hc_max: dict[str, int] = {}
    rev_max: dict[str, float] = {}
    for j in jobs:
        name = (j.get("company") or "").strip()
        nk = _norm_company(name)
        if not nk:
            continue
        name_votes[nk][name] += 1
        # 규모 신호는 공고 본문 전체에서 뽑는다 — 기업정보 표가 JD 뒤쪽에 붙는다.
        text = " ".join([j.get("full_jd") or "", j.get("benefits") or "",
                         j.get("qualifications") or "", j.get("preferences") or ""])
        hc = extract_headcount(text)
        if hc and hc > hc_max.get(nk, 0):
            hc_max[nk] = hc
        rev = extract_revenue_eok(text)
        if rev and rev > rev_max.get(nk, 0):
            rev_max[nk] = rev
    sizes: dict[str, str] = {}
    for nk, votes in name_votes.items():
        display = votes.most_common(1)[0][0]
        size, _alias = classify_company_size(display, hc_max.get(nk), rev_max.get(nk))
        for raw in votes:
            sizes[raw] = size
    return sizes


# ── job_facet 채우기 ─────────────────────────────────────────────────────

_ROWS_SQL = """
    SELECT v.id, v.company, v.title, v.tech_stack, v.qualifications, v.preferences,
           v.benefits, v.full_jd, v.location_text, v.overseas, v.career_text,
           d.job_id IS NOT NULL AS is_dup
      FROM v_job v
      -- 조인으로 건다. SELECT 목록의 EXISTS 로 두면 job_dup(전량 윈도 함수)이 공고마다
      -- 다시 계산돼 한 바퀴에 10분을 넘겼다.
      LEFT JOIN job_dup d ON d.job_id = v.id
"""


def _rows(cur):
    """v_job 을 한 줄씩(서버 커서). 뷰어 Job 과 같은 키 이름으로 바꿔 준다."""
    cur.execute(_ROWS_SQL)
    for r in cur:
        yield {
            "id": r["id"], "company": r["company"], "title": r["title"],
            "tech_stack": list(r["tech_stack"] or []),
            "qualifications": r["qualifications"] or "", "preferences": r["preferences"] or "",
            "benefits": r["benefits"] or "", "full_jd": r["full_jd"] or "",
            "location": r["location_text"] or "", "overseas": bool(r["overseas"]),
            "career": r["career_text"] or "", "is_dup": r["is_dup"],
        }


def refresh(verbose: bool = True) -> int:
    """job_facet 을 전량 다시 채운다. 채운 행 수.

    두 번 훑는다 — 회사 규모는 회사의 모든 공고를 본 뒤에야 정해지므로 첫 바퀴에
    규모를, 두 번째 바퀴에 공고별 축을 만든다. 둘 다 서버 커서로 한 줄씩 읽어
    본문 전량을 메모리에 올리지 않는다(8GB 맥에서 크롤과 같이 돈다).

    규모는 사이트 간 중복을 뺀 공고로 판정한다(store.jobs.export·빌더가 보는 것과 같은
    모집단 — 그래야 company_meta.json 과 같은 답이 나온다). 판정한 규모는 중복
    사본에도 같은 회사명이면 붙인다.
    """
    import time
    from store.db import conn as store_conn

    t0 = time.time()
    # 읽는 연결과 쓰는 연결을 나눈다. 한 연결에서 서버 커서로 읽으며 COPY 로 쓰면,
    # 연결이 COPY 모드에 묶여 커서의 다음 FETCH 를 보낼 수 없다 — 에러 없이 멈춘다.
    with store_conn.connect() as rd, store_conn.connect() as db:
        with rd.cursor(name="facet_sizes") as cur:
            sizes = company_sizes(r for r in _rows(cur) if not r["is_dup"])
        with db.cursor() as w:
            w.execute("""CREATE TEMP TABLE facet_in (
                             job_id bigint, region text, district text, roles text[],
                             career_bucket text, company_size text, stacks text[],
                             stacks_lc text[], hay text) ON COMMIT DROP""")
            n = 0
            with rd.cursor(name="facet_rows") as cur, \
                 w.copy("COPY facet_in FROM STDIN") as cp:
                for r in _rows(cur):
                    f = facets_of(r)
                    hay = (r["company"] + "\n" + r["title"] + "\n" + r["full_jd"]).lower()
                    stacks = _stacks(r["tech_stack"])
                    cp.write_row((r["id"], f["region"], f["district"], f["roles"],
                                  f["career_bucket"], sizes.get((r["company"] or "").strip()),
                                  stacks, [t.lower() for t in r["tech_stack"]], hay))
                    n += 1
            w.execute("""
                INSERT INTO job_facet (job_id, region, district, roles, career_bucket,
                                       company_size, stacks, stacks_lc, hay, updated_at)
                SELECT job_id, region, district, roles, career_bucket, company_size,
                       stacks, stacks_lc, hay, now()
                  FROM facet_in
                ON CONFLICT (job_id) DO UPDATE SET
                    region = EXCLUDED.region, district = EXCLUDED.district,
                    roles = EXCLUDED.roles, career_bucket = EXCLUDED.career_bucket,
                    company_size = EXCLUDED.company_size, stacks = EXCLUDED.stacks,
                    stacks_lc = EXCLUDED.stacks_lc, hay = EXCLUDED.hay,
                    updated_at = EXCLUDED.updated_at
                 WHERE (job_facet.region, job_facet.district, job_facet.roles,
                        job_facet.career_bucket, job_facet.company_size, job_facet.stacks,
                        job_facet.stacks_lc, job_facet.hay)
                       IS DISTINCT FROM
                       (EXCLUDED.region, EXCLUDED.district, EXCLUDED.roles,
                        EXCLUDED.career_bucket, EXCLUDED.company_size, EXCLUDED.stacks,
                        EXCLUDED.stacks_lc, EXCLUDED.hay)
            """)
            changed = w.rowcount
        db.commit()
    refresh_dup()
    if verbose:
        print(f"[facets] job_facet {n:,}건 계산 · {changed:,}건 갱신 · 회사 규모 {len(sizes):,}곳 "
              f"({time.time() - t0:.1f}s)", flush=True)
    return n


def refresh_dup(verbose: bool = False) -> bool:
    """mv_job_dup(사이트 간 중복의 구체화) 갱신. 실패해도 예외를 올리지 않는다.

    대표 공고를 고르는 기준에 모집 상태가 들어간다 — 대표가 닫히고 사본이 아직 열려
    있으면 사본이 대표가 돼야 목록에서 안 사라진다. 그래서 상태를 바꾸는 쪽(크롤
    사이클·close_check)이 끝에 이걸 부른다.
    """
    try:
        from store.db import conn as store_conn
        with store_conn.cursor(autocommit=True) as cur:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_job_dup")
        if verbose:
            print("[facets] mv_job_dup 갱신", flush=True)
        return True
    except Exception as e:                                          # noqa: BLE001
        print(f"[facets] mv_job_dup 갱신 실패: {e}", flush=True)
        return False


# ── 뷰어 규칙과 대조 ─────────────────────────────────────────────────────

_PARITY_JS = r"""
import { readFileSync, writeFileSync } from 'node:fs'
import { placeOf } from '%(viewer)s/src/features/jobs/utils/region.ts'
import { classifyRoles } from '%(viewer)s/src/utils/classify.ts'
import { careerBucket } from '%(viewer)s/src/features/jobs/utils/career.ts'
const jobs = JSON.parse(readFileSync(process.argv[2], 'utf8'))
writeFileSync(process.argv[3], JSON.stringify(jobs.map((j) => {
  const p = placeOf(j)
  return [p.region, p.district, classifyRoles(j.title, j.tech_stack, j.qualifications || ''), careerBucket(j.career)]
})))
"""


def parity() -> int:
    """뷰어 TS 규칙과 이 파일의 규칙을 공고 전량으로 대조한다. 불일치 수를 돌려준다.

    node 로 TS 원본을 직접 돌린다(node 22.6+ 는 .ts 의 타입을 벗겨 바로 실행한다).
    """
    import json
    import subprocess
    import tempfile
    from pathlib import Path
    from store.jobs.export import fetch_jobs

    viewer = Path(__file__).resolve().parents[3] / "jd-viewer"
    jobs = fetch_jobs()
    with tempfile.TemporaryDirectory() as td:
        src, dst, js = Path(td, "in.json"), Path(td, "out.json"), Path(td, "p.mjs")
        slim = [{k: j.get(k) for k in ("title", "tech_stack", "qualifications", "location",
                                       "overseas", "career")} for j in jobs]
        src.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
        js.write_text(_PARITY_JS % {"viewer": viewer.as_uri()}, encoding="utf-8")
        subprocess.run(["node", "--no-warnings", str(js), str(src), str(dst)], check=True)
        ts = json.loads(dst.read_text(encoding="utf-8"))
    bad = 0
    for j, t in zip(jobs, ts):
        f = facets_of(j)
        mine = [f["region"], f["district"], f["roles"], f["career_bucket"]]
        if mine != t:
            bad += 1
            if bad <= 10:
                print(f"  ✗ {j['site']}:{j['pid']} py={mine} ts={t}")
    print(f"[facets] 뷰어 규칙 대조: {len(jobs):,}건 중 불일치 {bad:,}건", flush=True)
    return bad


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="job_facet 채우기 / 뷰어 규칙 대조")
    ap.add_argument("--parity", action="store_true", help="뷰어 TS 규칙과 전량 대조(node 필요)")
    args = ap.parse_args()
    if args.parity:
        raise SystemExit(1 if parity() else 0)
    refresh()


if __name__ == "__main__":
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
    main()
