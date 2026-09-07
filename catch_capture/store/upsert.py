"""정본 DB 쓰기 경로 — 회사/기술/공고 upsert.

백필(store.backfill)과 크롤 사이클이 **같은 함수**를 쓴다. 지금까지 정합성이
깨진 자리가 대부분 "백필과 파이프라인이 다른 규칙으로 같은 데이터를 만들던 곳"
이었기 때문이다(aggregate 의 `_norm_key` vs classifier 의 `_norm_company`).

핵심 규칙 셋:
  - 회사는 norm 으로 식별하고 표기는 alias 로 흡수한다.
  - 공고는 url 로 식별한다. 이미 있으면 본문만 갱신하고 first_seen_at 은 지킨다.
  - 목록에서 사라진 공고는 지우지 않는다. gone_at 만 찍고 close_check 에 맡긴다
    (사라짐 ≠ 마감 — 페이지네이션이 실패해도 사라진다).
"""
from __future__ import annotations

import hashlib
import re
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from store.slug import (  # noqa: E402
    base_company_slug, is_noise_tech, norm_company, tech_slug,
)

# tech.kind 로 쓸 값 — 택소노미 카테고리를 스키마 ENUM 으로 옮긴다.
_KIND_BY_CATEGORY = {
    "언어": "language",
    "프론트엔드": "framework", "백엔드": "framework", "모바일": "framework",
    "AI/ML": "framework", "LLM/생성형": "framework",
    "데이터": "platform", "데이터베이스": "database",
    "인프라/클라우드": "infra", "관측성": "infra",
    "시스템/OS": "platform", "펌웨어/임베디드": "platform",
    "알고리즘/이론": "concept", "연구/논문": "concept",
    "보안": "concept", "그래픽/게임": "framework", "블록체인": "platform",
    "협업/도구": "tool",
}


def content_hash(job: dict) -> str:
    """임베딩 입력의 해시. 이 값이 바뀌면 재임베딩 대상이다.

    semantic 이 실제로 임베딩하는 필드만 넣는다 — 조회수나 마감일이 바뀌었다고
    다시 임베딩하면 8GB M1 에서 사이클이 끝나지 않는다.
    """
    parts = [
        str(job.get("title") or ""),
        str(job.get("company") or ""),
        " ".join(sorted(str(t) for t in (job.get("tech_stack") or []))),
        str(job.get("qualifications") or ""),
        str(job.get("preferences") or ""),
        str(job.get("main_tasks") or ""),
    ]
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:16]


# ── 공고 조건 파싱 ────────────────────────────────────────────────────
# 백필과 크롤이 같은 규칙을 써야 한다. 백필에만 있으면 이관 뒤에 값이 갈린다.

# '경력3년↑' / '경력 3년 이상' → 3
_YEARS = re.compile(r"(\d+)\s*년")
_ENTRY = re.compile(r"신입|경력무관|무관")

# 스키마의 employment_type ENUM 으로 옮기는 표. ENUM 에 없는 형태는 '기타' 로
# 받는다 — 아르바이트를 정규직도 계약직도 아닌 칸에 넣을 수는 없고, 그렇다고
# 버리면 "고용형태가 안 적힌 공고"와 구별이 안 된다.
_EMPLOYMENT = {
    "정규직": "정규직", "계약직": "계약직", "인턴": "인턴",
    "프리랜서": "프리랜서", "파견": "파견", "파견직": "파견",
    "아르바이트": "기타",
}


def parse_career(text: str) -> tuple[int | None, bool | None]:
    """'경력3년↑' → (3, False) / '신입·경력' → (0, True) / 빈 값 → (None, None)"""
    t = (text or "").strip()
    if not t:
        return None, None
    m = _YEARS.search(t)
    years = int(m.group(1)) if m else None
    entry = bool(_ENTRY.search(t))
    if entry and years is None:
        years = 0
    return years, entry


# 고용형태 칸에 절대 안 들어가는 낱말. 이게 붙어 있으면 공고 제목이 흘러든 것이다.
# (crawlers/crawl_jobkorea.TITLEISH 와 같은 뜻이지만, 그 모듈은 playwright 를 끌고
#  들어와서 여기서 import 하지 않는다. 규칙이 갈릴 여지는 작고 목적도 다르다 —
#  저쪽은 크롤 카드에서 값을 고르고, 이쪽은 DB 에 넣기 전 마지막 관문이다.)
_TITLEISH = re.compile(r"채용|모집|개발자|엔지니어|담당자", re.I)
_EMP_HEAD = re.compile(r"^(정규직|계약직|인턴|프리랜서|파견직|파견|아르바이트)")


def parse_employment(text: str) -> str | None:
    """'정규직' → '정규직' · '정규직(수습 3개월)' → '정규직' · 제목이면 None.

    크롤러가 값을 잘못 넣어도 DB 까지는 못 가게 하는 마지막 관문이다. 실제로
    jobkorea 의 고용형태 242건 중 225건이 공고 제목이었다(217건은 제목과 동일).
    스키마의 ENUM 이 어차피 거부하지만, 거부가 트랜잭션을 깨는 것보다 여기서
    조용히 버리는 편이 낫다. 확실한 것만 받고 나머지는 빈 값으로 둔다.
    """
    t = (text or "").strip()
    if not t or len(t) > 20:
        return None
    m = _EMP_HEAD.match(t)
    if not m:
        return None
    rest = t[m.end():].strip(" /·,")
    # 뒤에 붙을 수 있는 건 짧은 괄호 주석이나 다른 고용형태뿐이다.
    if rest and (len(rest) > 12 or _TITLEISH.search(rest)):
        return None
    # get 이다. 위 정규식과 이 표가 어긋나면(실제로 '아르바이트'가 정규식에만
    # 있었다) KeyError 가 이 함수 밖으로 튀어 크롤 사이클의 이중 쓰기를 통째로
    # 롤백시킨다 — 값 하나 못 읽은 대가로 그 사이클의 공고 전부를 잃는 셈이다.
    # 확실한 것만 받고 나머지는 빈 값으로 둔다는 이 함수의 규칙 그대로 둔다.
    return _EMPLOYMENT.get(m.group(1))


# ── 회사 ──────────────────────────────────────────────────────────────
def upsert_company(cur, raw_name: str, *, slug_hint: str | None = None) -> int | None:
    """표기 하나를 받아 회사 id 를 돌려준다. 표기는 alias 로 쌓인다.

    slug 는 한 번 정하면 안 바뀐다 — 이미 있는 회사면 기존 slug 를 그대로 둔다
    (바뀌면 색인된 /companies/<slug> 가 통째로 404 가 된다).
    """
    raw = (raw_name or "").strip()
    norm = norm_company(raw)
    if not norm:
        return None   # 회사명이 없는 공고는 여기서 걸러 호출부가 건너뛴다

    # alias 로 이미 아는 표기면 조회 한 번으로 끝난다(크롤 대부분이 이 경로다).
    cur.execute("SELECT company_id FROM company_alias WHERE raw = %s", (raw,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE company_alias SET n_seen = n_seen + 1 WHERE raw = %s", (raw,)
        )
        cur.execute(
            "UPDATE company SET last_seen_at = now() WHERE id = %s", (row["company_id"],)
        )
        return row["company_id"]

    base = slug_hint or base_company_slug(norm)
    # 슬러그 충돌은 -2, -3 으로 피한다. 이미 그 norm 이 있으면 slug 는 건드리지 않는다.
    cur.execute(
        """
        INSERT INTO company (norm, slug, display_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (norm) DO UPDATE SET last_seen_at = now()
        RETURNING id
        """,
        (norm, _free_slug(cur, base), raw),
    )
    company_id = cur.fetchone()["id"]
    cur.execute(
        """
        INSERT INTO company_alias (raw, company_id) VALUES (%s, %s)
        ON CONFLICT (raw) DO UPDATE SET n_seen = company_alias.n_seen + 1
        """,
        (raw, company_id),
    )
    return company_id


def _free_slug(cur, base: str) -> str:
    cur.execute("SELECT 1 FROM company WHERE slug = %s", (base,))
    if not cur.fetchone():
        return base
    n = 2
    while True:
        cand = f"{base}-{n}"
        cur.execute("SELECT 1 FROM company WHERE slug = %s", (cand,))
        if not cur.fetchone():
            return cand
        n += 1


def refresh_display_names(cur) -> int:
    """대표 표기를 alias 중 가장 자주 온 것으로 맞춘다.

    `메가존클라우드(주)`(40건) / `메가존클라우드㈜`(24건) 중 앞엣것을 고른다.
    name_locked 인 회사는 사람이 정한 것이라 건드리지 않는다.

    고른 표기는 **NFKC 정규형으로** 내보낸다. `㈜`(U+321C)는 한 글자로 합쳐진
    문자라, 뷰어의 `companyMark.normalizeCompany` 는 `(주)` 세 글자만 지우고 이건
    못 지운다. 그래서 대표 표기가 `㈜와탭랩스` 가 되면 그 회사의 취업 브리핑이
    화면에서 조용히 사라진다(실측 7건). NFKC 가 하는 일이 정확히 `㈜`→`(주)`,
    전각→반각 같은 호환 문자의 통일이라 여기에 딱 맞는다. 빈도가 가장 높은 표기를
    고르되 글자만 정규형으로 편다 — 회사 이름 자체는 바뀌지 않는다.
    """
    cur.execute(
        """
        UPDATE company c SET display_name = normalize(best.raw, NFKC)
          FROM (
            SELECT DISTINCT ON (company_id) company_id, raw
              FROM company_alias
             ORDER BY company_id, n_seen DESC, length(raw), raw
          ) best
         WHERE best.company_id = c.id
           AND NOT c.name_locked
           AND c.display_name <> normalize(best.raw, NFKC)
        """
    )
    return cur.rowcount


# ── 기술 ──────────────────────────────────────────────────────────────
def upsert_tech(cur, name: str, *, category: str | None = None,
                cache: dict | None = None) -> int | None:
    """기술명 하나 → tech.id. 슬러그를 못 만들면(파싱 사고·너무 김) None.

    `cache` 는 한 번의 실행 안에서만 쓰는 이름→id 표다. 공고 17,000건에 기술 연결이
    75,000건이라 캐시가 없으면 그만큼 왕복이 생긴다.
    """
    raw = (name or "").strip()
    if cache is not None and raw in cache:
        return cache[raw]
    slug = tech_slug(raw)
    if not slug:
        if cache is not None:
            cache[raw] = None
        return None

    cur.execute("SELECT tech_id FROM tech_alias WHERE alias = %s", (raw,))
    row = cur.fetchone()
    if row:
        if cache is not None:
            cache[raw] = row["tech_id"]
        return row["tech_id"]

    kind = _KIND_BY_CATEGORY.get(category or "", "tool")
    noise = is_noise_tech(raw)
    if noise:
        kind = "noise"
    cur.execute(
        """
        INSERT INTO tech (slug, name, kind, is_noise) VALUES (%s, %s, %s, %s)
        ON CONFLICT (slug) DO UPDATE SET
            -- 노이즈 판정은 한 번 true 가 되면 유지한다(사람이 되돌리기 전까지)
            is_noise = tech.is_noise OR EXCLUDED.is_noise
        RETURNING id
        """,
        (slug, raw, kind, noise),
    )
    tech_id = cur.fetchone()["id"]
    cur.execute(
        "INSERT INTO tech_alias (alias, tech_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (raw, tech_id),
    )
    if cache is not None:
        cache[raw] = tech_id
    return tech_id


def set_job_techs(cur, job_id: int, names, *, source: str = "crawl",
                  cache: dict | None = None) -> int:
    """공고의 기술 목록을 통째로 맞춘다(빠진 것은 지운다)."""
    ids = set()
    for n in names or []:
        tid = upsert_tech(cur, n, cache=cache)
        if tid:
            ids.add(tid)
    cur.execute("DELETE FROM job_tech WHERE job_id = %s AND NOT (tech_id = ANY(%s))",
                (job_id, list(ids) or [-1]))
    for tid in ids:
        cur.execute(
            "INSERT INTO job_tech (job_id, tech_id, source) VALUES (%s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            (job_id, tid, source),
        )
    return len(ids)


# ── 공고 ──────────────────────────────────────────────────────────────
JOB_COLUMNS = (
    "site", "pid", "url", "company_id", "title",
    "career_text", "career_min", "accepts_entry",
    "location_text", "sido", "sigungu", "region", "overseas",
    "employment", "education", "source_board",
    "main_tasks", "qualifications", "preferences", "benefits", "full_jd",
    "deadline_text", "deadline_on", "always_open", "dday_text_raw",
    "content_hash",
)

# 재크롤 때 갱신하는 컬럼. first_seen_at 은 여기 없다 — 최초 발견 시각은 불변이다.
_UPDATE_COLUMNS = tuple(c for c in JOB_COLUMNS if c not in ("site", "pid", "url"))


def upsert_job(cur, row: dict) -> tuple[int, bool]:
    """공고 1건. (job_id, 새로 생겼는가) 를 돌려준다.

    `xmax = 0` 은 이번 문장이 INSERT 였다는 뜻이다 — UPDATE 였다면 갱신된 튜플의
    xmax 가 채워진다. 이 값으로 job_event('appeared') 를 남길지 판단한다.

    주소는 공고의 이름표일 뿐 정체성이 아니다. 같은 공고가 사이트에 따라 여러
    주소로 나온다 — jobkorea 는 검색 위치를 URL 에 싣고(`?Oem_Code=…&listno=…`),
    saramin 은 식별자를 쿼리에 둔다. 그래서 `ON CONFLICT (url)` 만 보면 "URL 은
    처음 보는데 (site,pid) 는 이미 있는" 경우 INSERT 로 밀다가 job_site_pid_uniq
    에 걸린다. 2026-09-08 에 실제로 그렇게 됐다: 다른 머신에서 모은 공고를 합친
    뒤, 매 크롤 사이클의 이중 쓰기가 통째로 롤백돼 DB 가 24,417 에서 멈춘 채
    JSON 만 늘어갔다. 예외 하나가 사이클 전체를 삼키므로 조용히 낡아간다.

    그래서 pid 가 있으면 **(site,pid) 를 먼저 찾아본다** — 스키마가 유일 키로
    선언한 그 짝이 이 도메인의 정체성이다.
    """
    site, pid = row.get("site"), row.get("pid")
    if pid:
        cur.execute("SELECT id, url FROM job WHERE site = %s AND pid = %s", (site, pid))
        hit = cur.fetchone()
        if hit is not None and hit["url"] != row.get("url"):
            # 주소 표기만 다른 같은 공고다. 최신 표기로 맞추되, 그 주소를 이미 다른
            # 행이 들고 있으면(파싱이 어긋나 pid 가 갈린 경우) 주소는 그대로 둔다 —
            # 여기서 url unique 를 건드리면 같은 방식으로 사이클이 죽는다.
            cur.execute("SELECT id FROM job WHERE url = %s", (row.get("url"),))
            other = cur.fetchone()
            take_url = other is None or other["id"] == hit["id"]

            sets = [f"{c} = %s" for c in _UPDATE_COLUMNS]
            args = [row.get(c) for c in _UPDATE_COLUMNS]
            if take_url:
                sets.append("url = %s")
                args.append(row.get("url"))
            args.append(hit["id"])
            cur.execute(
                f"""
                UPDATE job SET {", ".join(sets)},
                    last_seen_at = now(),
                    last_crawled_at = now(),
                    gone_at = NULL
                 WHERE id = %s
                RETURNING id
                """,
                tuple(args),
            )
            return cur.fetchone()["id"], False

    cols = ", ".join(JOB_COLUMNS)
    holes = ", ".join(["%s"] * len(JOB_COLUMNS))
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in _UPDATE_COLUMNS)
    cur.execute(
        f"""
        INSERT INTO job ({cols}) VALUES ({holes})
        ON CONFLICT (url) DO UPDATE SET
            {sets},
            last_seen_at = now(),
            last_crawled_at = now(),
            gone_at = NULL          -- 다시 나타났다
        RETURNING id, (xmax = 0) AS inserted
        """,
        tuple(row.get(c) for c in JOB_COLUMNS),
    )
    r = cur.fetchone()
    return r["id"], r["inserted"]


def mark_gone(cur, seen_job_ids, *, site: str | None = None) -> int:
    """이번 사이클에 안 보인 공고에 gone_at 을 찍는다.

    지우지 않는다. 사라짐은 마감의 **신호**일 뿐이고, 답은 close_check 가
    원본에 직접 물어서 가져온다.
    """
    where_site = "AND site = %s" if site else ""
    args = [list(seen_job_ids) or [-1]]
    if site:
        args.append(site)
    cur.execute(
        f"""
        UPDATE job SET gone_at = now()
         WHERE gone_at IS NULL AND NOT (id = ANY(%s)) {where_site}
        """,
        tuple(args),
    )
    return cur.rowcount


def log_event(cur, job_id: int, kind: str, *, run_id: int | None = None,
              detail: dict | None = None) -> None:
    import json
    cur.execute(
        "INSERT INTO job_event (job_id, kind, crawl_run_id, detail) VALUES (%s,%s,%s,%s)",
        (job_id, kind, run_id, json.dumps(detail or {}, ensure_ascii=False)),
    )
