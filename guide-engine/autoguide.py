#!/usr/bin/env python3
"""자동 브리핑 — 크롤한 공고만으로 기계가 확정할 수 있는 것만 뽑는다.

    python3 guide-engine/autoguide.py 포밸류소프트     # 회사 하나
    python3 guide-engine/autoguide.py --queue          # QUEUE.md "## 대기" 맨 위
    python3 guide-engine/autoguide.py --top 30         # 모집중 공고 많은 순 N곳
    python3 guide-engine/autoguide.py --all            # 손으로 쓴 브리핑이 없는 회사 전량
    python3 guide-engine/autoguide.py 포밸류소프트 --print   # 파일 안 쓰고 요약만

**손으로 쓴 브리핑(`guide/companies/`)과 완전히 다른 자리에 쌓는다**
(`guide/auto/`). 섞으면 안 된다 — 저쪽은 사람이 판단해서 쓴 글이고 여기는 정규식이
공고에서 긁어낸 사실이다. 여기에는 `why`·`drill`·`verdict` 같은 **판단 필드를 만들지
않는다.** 규칙으로 그 칸을 채우면 일반론이 사실인 척하게 되고, 그건 브리핑을 읽는
사람에게 손해다. 코드가 확정할 수 있는 것만 담고, 못 하는 것은 `gaps` 에 이름을 적어
남긴다.

`study[].quote` 는 validate.py 와 같은 규칙(공백만 접어 대조)으로 **공고 원문의
부분문자열**이어야 한다 — 뷰어가 이 문자열로 본문을 하이라이트하기 때문이다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
GUIDE = ROOT / "jd-viewer" / "public" / "guide"
AUTO = GUIDE / "auto"
STATE = Path(__file__).resolve().parent / "state"
QUEUE = STATE / "QUEUE.md"
SLUG_OVERRIDE = STATE / "auto_slugs.json"

GENERATOR = "autoguide.py 1"


# ── 회사명 정규화 ────────────────────────────────────────────────────────
# validate.py 의 norm_company() 와 **같은 규칙**이어야 한다. 어긋나면 자동 브리핑과
# 손으로 쓴 브리핑이 같은 회사를 다른 회사로 본다.
def norm_company(name: str) -> str:
    s = re.sub(r"\((주|유|재|사)\)", "", name or "")
    s = re.sub(r"(주식회사|유한회사)", "", s)
    s = re.sub(r"\s*\([^)]*\)\s*", "", s)
    return re.sub(r"\s+", "", s).strip()


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


# 공고를 회사별로 모을 때만 쓰는 더 느슨한 키. norm_company() 는 뷰어의
# normalizeCompany() 와 글자 하나까지 같아야 해서 손대면 안 되는데, 그 규칙은
# 합자 ㈜ 를 안 벗긴다 — 그래서 `㈜포밸류소프트` 와 `(주)포밸류소프트` 가 서로
# 다른 회사가 된다. 뷰어는 aliases 배열로 그 간극을 메우므로, 여기서는 **모을 때만**
# 합자를 벗기고 **내보내는 aliases 는 norm_company() 를 통과한 값**으로 적는다.
_LIGATURE = str.maketrans({"㈜": "", "㈐": "", "㈑": "", "\u321c": ""})


def collect_key(name: str) -> str:
    return norm_company((name or "").translate(_LIGATURE))


# ── slug ────────────────────────────────────────────────────────────────
# 회사명은 대부분 한글이라 파일명을 만들려면 로마자로 옮겨야 한다. 국어의 로마자
# 표기법을 그대로 구현하지는 않는다 — 여기서 필요한 건 **읽기 좋은 이름**이 아니라
# **같은 회사가 늘 같은 파일로 가는 것**이라 결정적이기만 하면 된다. 사람이 읽을
# 이름을 따로 주고 싶으면 state/auto_slugs.json 에 {"회사명": "slug"} 로 적는다.
_CHO = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj",
        "ch", "k", "t", "p", "h"]
_JUNG = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe",
         "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
_JONG = ["", "k", "k", "k", "n", "n", "n", "t", "l", "l", "l", "l", "l", "l", "l",
         "l", "m", "p", "p", "t", "t", "ng", "t", "t", "k", "t", "p", "t"]


def romanize(s: str) -> str:
    out = []
    for ch in s:
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            n = code - 0xAC00
            out.append(_CHO[n // 588] + _JUNG[(n % 588) // 28] + _JONG[n % 28])
        elif ch.isalnum():
            out.append(ch.lower())
        else:
            out.append("-")
    slug = re.sub(r"-+", "-", "".join(out)).strip("-")
    return slug or "unknown"


def load_overrides() -> dict:
    if SLUG_OVERRIDE.exists():
        try:
            return json.loads(SLUG_OVERRIDE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def existing_slugs() -> dict:
    """손으로 쓴 브리핑이 이미 정한 slug 는 그대로 따른다 — 두 데이터셋이 같은
    회사를 가리킬 때 파일명이 갈리면 화면에서 잇지 못한다."""
    idx = GUIDE / "index.json"
    if not idx.exists():
        return {}
    try:
        doc = json.loads(idx.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for c in doc.get("companies", []):
        for a in c.get("aliases", []) or []:
            out[collect_key(a)] = c["slug"]
        out.setdefault(collect_key(c.get("name", "")), c["slug"])
    return out


# ── 회사 사실 ────────────────────────────────────────────────────────────
# 사람인·잡코리아·원티드가 공고 본문 머리에 붙이는 회사 소개 정형 문구를 노린다.
#   "(주)포밸류소프트는 2018년에 설립된 회사로 자본금 1억원, 매출액 67억 1천만원,
#    사원수 38명 규모의 …"
# 이 문구가 있는 회사는 전체의 일부지만, 있을 때는 **공시 없이도 규모를 원문으로
# 받칠 수 있는 유일한 근거**다. 회사가 직접 적어 낸 값이므로 confirmed 로 본다.
FACT_RE = {
    "founded":   re.compile(r"(\d{4})\s*년에?\s*설립"),
    "capital":   re.compile(r"자본금\s*([0-9][0-9,\s억천백만]*원)"),
    "revenue":   re.compile(r"매출액\s*([0-9][0-9,\s억천백만]*원)"),
    "headcount": re.compile(r"사원수\s*([0-9][0-9,]*)\s*명"),
}
FACT_LABEL = {"founded": "설립", "capital": "자본금",
              "revenue": "매출액", "headcount": "사원수"}

# 연봉이 본문에 숫자로 적힌 경우만. "회사 내규에 따름" 은 근거가 아니라 침묵이다.
# `이상`·`부터` 를 인용문에서 떨어뜨리면 "5,000만원" 이 상한처럼 읽힌다 — 밴드의
# 뜻이 바뀌므로 꼬리까지 함께 잡는다.
SALARY_RE = re.compile(
    r"(?:연봉|급여|보수|연 ?봉)[^\n]{0,40}?"
    r"([0-9][0-9,]{2,6})\s*만\s*원"
    r"(?:\s*[~\-–]\s*([0-9][0-9,]{2,6})\s*만\s*원)?"
    r"(\s*(?:이상|이하|부터|내외|수준))?")

CAREER_PATTERNS = [
    (re.compile(r"경력\s*무관"),                                  lambda m: (0, None, "경력무관")),
    (re.compile(r"^신입$|신입\s*(?:지원\s*)?(?:가능|이상)?$"),     lambda m: (0, 0, "신입")),
    (re.compile(r"경력\s*(\d+)\s*[~\-–]\s*(\d+)\s*년"),           lambda m: (int(m[1]), int(m[2]), "범위")),
    (re.compile(r"경력\s*(\d+)\s*년\s*(?:이상|↑)"),               lambda m: (int(m[1]), None, "이상")),
    (re.compile(r"경력\s*(\d+)\s*년"),                            lambda m: (int(m[1]), int(m[1]), "고정")),
    (re.compile(r"신입"),                                         lambda m: (0, None, "신입포함")),
]

# 정규직이 아닌 자리는 학습 계획의 전제가 달라진다. 공고 본문에 있으면 표시한다.
EMPLOYMENT_FLAGS = [
    ("계약직", re.compile(r"계약직")),
    ("프리랜서", re.compile(r"프리랜서|프리 ?계약")),
    ("파견", re.compile(r"파견|도급인력|상주\s*인력")),
    ("인턴", re.compile(r"인턴")),
    ("고객사상주", re.compile(r"고객사\s*(?:투입|상주)|프로젝트\s*투입")),
]


def extract_facts(postings: list[dict]) -> dict:
    """같은 값이 여러 공고에 반복되면 그게 회사가 스스로 적어 낸 값이다."""
    found: dict[str, list] = defaultdict(list)
    for j in postings:
        text = j.get("full_jd") or ""
        for key, rx in FACT_RE.items():
            m = rx.search(text)
            if m:
                found[key].append((norm_text(m.group(1)), norm_text(m.group(0)), j["url"]))
    out = {}
    for key, hits in found.items():
        vals = Counter(v for v, _, _ in hits)
        value, n = vals.most_common(1)[0]
        quote, url = next((q, u) for v, q, u in hits if v == value)
        out[key] = {
            "label": FACT_LABEL[key], "value": value, "quote": quote,
            "source_url": url, "seen_in": n, "of_postings": len(postings),
            "basis": "posting", "confidence": "confirmed",
        }
    return out


def extract_salary(postings: list[dict]) -> list[dict]:
    out = []
    for j in postings:
        for chunk in (j.get("full_jd") or "", j.get("benefits") or ""):
            m = SALARY_RE.search(chunk)
            if not m:
                continue
            low = int(m.group(1).replace(",", ""))
            high = int(m.group(2).replace(",", "")) if m.group(2) else None
            bound = norm_text(m.group(3) or "")
            out.append({
                "low": low, "high": high, "unit": "만원",
                # "이상" 이면 low 는 하한이지 밴드가 아니다. 읽는 쪽이 헷갈리지 않게 적는다.
                "bound": bound or ("range" if high else "point"),
                "quote": norm_text(m.group(0)), "url": j["url"],
                "title": j.get("title", ""), "career": j.get("career", ""),
                "basis": "posting", "confidence": "confirmed",
            })
            break
    return out


def parse_career(raw: str):
    s = norm_text(raw)
    if not s:
        return None
    for rx, fn in CAREER_PATTERNS:
        m = rx.search(s)
        if m:
            lo, hi, kind = fn(m)
            return {"raw": s, "min_years": lo, "max_years": hi, "kind": kind}
    return {"raw": s, "min_years": None, "max_years": None, "kind": "unparsed"}


# ── 학습 항목 ────────────────────────────────────────────────────────────
# 자격요건·우대사항·주요업무를 문장으로 쪼갠 것이 학습 항목의 원재료다. 다만 그
# 절에는 공부할 것이 아닌 줄이 섞여 있다(학력, 근무지, 마감일, 고용형태…). 이걸
# 거르지 않으면 "학력 무관"이 학습 항목이 되어 목록 전체의 신뢰가 깨진다.
BULLET_RE = re.compile(r"^\s*(?:[•·ㆍ∙▪▶◆■□○●\-\*※]|\d+[\.\)]|[가-힣]\.)\s*")
NOISE_RE = re.compile(
    r"학력|근무지|근무\s*형태|고용\s*형태|마감|접수|제출|채용\s*절차|전형|"
    r"연봉|급여|복리|복지|우대\s*사항$|자격\s*요건$|주요\s*업무$|담당\s*업무$|"
    r"모집\s*(?:부문|인원)|성별|나이|병역|보훈|장애|채용시|출퇴근|위치|주소|"
    r"^경력\s*[:：]|^경력\s*\d|^신입|^\s*$|문의|이메일|지원\s*방법")
# 절 머리글은 학습 항목이 아니다. 원티드는 "2. 자격 요건 (Qualifications) / 필수"
# 처럼 번호와 영문을 붙여 오므로 끝 앵커만으로는 안 걸린다.
HEADER_RE = re.compile(
    r"^\d*\.?\s*(?:자격\s*요건|우대\s*사항|주요\s*업무|담당\s*업무|필수\s*사항|"
    r"근무\s*조건|복지|혜택|채용\s*전형|전형\s*절차|서비스\s*소개|회사\s*소개)"
    r"\s*(?:\([^)]*\))?\s*(?:[/·|]\s*\S{1,10})?\s*[:：]?\s*$")
# 사람 이름·회사 소개처럼 문장이 아닌 조각이 섞이는 것을 막는 최소 길이.
MIN_LINE = 6
MAX_LINE = 200

# 제목 유사도가 이 위면 같은 자리로 본다. 0.75 는 "금융SI 고급 개발자(원천징수/환원
# 개발)" 과 "금융권 SI 고급 개발자( 원천징수/환원) 모집" 을 묶고, 같은 회사의 다른
# 직군(백엔드 vs 프론트엔드)은 안 묶이는 선이다.
TITLE_SIM = 0.75


def build_vocab(all_jobs: list[dict]) -> list[str]:
    """기술 용어 사전을 코퍼스에서 만든다 — 크롤러가 이미 뽑아 둔 tech_stack 이
    사람이 손으로 적은 어떤 목록보다 이 데이터에 맞는다."""
    c = Counter()
    for j in all_jobs:
        for t in j.get("tech_stack") or []:
            if t:
                c[t] += 1
    return sorted(c, key=lambda t: (-len(t), t))   # 긴 것부터 — "Spring Boot" 가 "Spring" 보다 먼저


# 영문 용어는 부분문자열로 찾으면 안 된다 — `Claude` 에서 `C` 를, `RAG` 에서 `R` 을
# 잡아 목록이 쓰레기가 된다. 한글 용어는 조사가 붙어 오므로 경계를 걸지 않는다.
_ASCII_TERM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+#.\- ]*$")
_TERM_CACHE: dict[str, re.Pattern | None] = {}


def _term_re(term: str):
    if term not in _TERM_CACHE:
        _TERM_CACHE[term] = (
            re.compile(r"(?<![A-Za-z0-9+#.])" + re.escape(term) + r"(?![A-Za-z0-9+#])",
                       re.IGNORECASE)
            if _ASCII_TERM.match(term) else None)
    return _TERM_CACHE[term]


def match_topics(quote: str, vocab: list[str]) -> list[str]:
    low = quote.lower()
    hits, taken = [], []
    for term in vocab:
        t = term.lower()
        rx = _term_re(term)
        if rx is not None:
            if not rx.search(quote):
                continue
        elif t not in low:
            continue
        if any(t in got for got in taken):      # "Spring" 은 "Spring Boot" 에 먹힌다
            continue
        taken.append(t)
        hits.append(term)
    return hits[:6]


def split_lines(section: str) -> list[str]:
    out = []
    for raw in (section or "").split("\n"):
        line = BULLET_RE.sub("", raw).strip()
        line = re.sub(r"\s+", " ", line)
        if len(line) < MIN_LINE or len(line) > MAX_LINE:
            continue
        if NOISE_RE.search(line) or HEADER_RE.match(line):
            continue
        out.append(line)
    return out


SECTIONS = [("qualifications", "qualification", "core"),
            ("preferences", "preference", "nice"),
            ("main_tasks", "task", "high")]


def extract_study(job: dict, vocab: list[str]) -> list[dict]:
    body = "\n".join([job.get("main_tasks") or "", job.get("qualifications") or "",
                      job.get("preferences") or ""])
    body_n = norm_text(body)
    items, seen = [], set()
    for field, origin, priority in SECTIONS:
        for line in split_lines(job.get(field) or ""):
            key = line.lower()
            if key in seen:
                continue
            # 뷰어가 이 문자열로 본문을 하이라이트한다. 원문에 없으면 조용히
            # 사라지므로, validate.py 와 같은 규칙으로 여기서 미리 떨어뜨린다.
            if norm_text(line) not in body_n:
                continue
            seen.add(key)
            items.append({
                "quote": line,
                "from": origin,
                "priority": priority,
                "topics": match_topics(line, vocab),
            })
    return items


# ── 중복 공고 ────────────────────────────────────────────────────────────
# 같은 자리가 원티드·점핏·사람인에 겹쳐 올라온다. 세지 않고 두면 "모집중 8건"이
# 실제 자리 수인 것처럼 읽힌다.
TITLE_NOISE = re.compile(
    r"\[[^\]]*\]|\([^)]*채용[^)]*\)|모집|채용|공고|정규직|신입|경력|"
    r"[\s·ㆍ,\-–—/()（）\[\]<>~!?.:：]")


def title_key(job: dict) -> str:
    return TITLE_NOISE.sub("", (job.get("title") or "")).lower()


def body_key(job: dict) -> str:
    q = norm_text(job.get("qualifications") or "")[:180]
    t = norm_text(job.get("main_tasks") or "")[:180]
    return f"{q}|{t}" if (q or t) else ""


def group_duplicates(postings: list[dict]) -> list[dict]:
    """같은 자리가 원티드·점핏·사람인에 겹쳐 올라온다. 세지 않고 두면 "모집중 8건"이
    실제 자리 수인 것처럼 읽힌다.

    **제목이 기준이다.** 처음엔 본문이 같으면 같은 자리로 묶었는데, 포밸류소프트에서
    `업무총괄 PL` 과 `종합수익관리 개발` 의 자격요건이 **글자까지 같았다** — 회사가
    요건을 복붙한 것이지 같은 자리가 아니다. 본문 일치는 이제 **묶는 근거가 아니라
    묶은 것의 확신도를 올리는 근거**로만 쓴다.
    """
    n = len(postings)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    titles = [title_key(j) for j in postings]
    bodies = [body_key(j) for j in postings]
    for i in range(n):
        for k in range(i + 1, n):
            a, b = find(i), find(k)
            if a == b or not titles[i] or not titles[k]:
                continue
            if SequenceMatcher(None, titles[i], titles[k]).ratio() >= TITLE_SIM:
                parent[b] = a

    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    groups = []
    for idxs in clusters.values():
        if len(idxs) < 2:
            continue
        bods = {bodies[i] for i in idxs if bodies[i]}
        sure = len(bods) == 1 and len(idxs) == len([i for i in idxs if bodies[i]])
        groups.append({
            "reason": "제목이 거의 같고 자격요건·주요업무 본문도 같다" if sure
                      else "제목이 거의 같다 — 사이트별 표기 차이로 보이나 확인이 필요하다",
            "confidence": "confirmed" if sure else "inferred",
            "postings": [{"url": postings[i]["url"], "site": postings[i].get("site", ""),
                          "title": postings[i].get("title", "")} for i in idxs],
        })
    return sorted(groups, key=lambda g: -len(g["postings"]))


# ── 회사 하나 만들기 ─────────────────────────────────────────────────────
# 코드가 못 하는 것은 지어내지 않고 이름만 남긴다. 이 목록이 "손으로 쓸 때 뭐부터
# 봐야 하나"를 그대로 알려 준다.
UNCODEABLE = [
    ("verdict", "이 공고가 찾는 사람 한 줄 — 공고 문장을 업무와 이어 읽어야 나온다"),
    ("study[].why / gap_check / drill", "왜 이 회사에서 필요한지와 손으로 만들 과제"),
    ("company.business / domains / signals", "무엇을 팔아 버는가, 기술로 푸는 문제의 경계"),
    ("people", "공개 인물 — 공고에 없다. 컨퍼런스·기술글·인터뷰를 찾아야 한다"),
    ("edge", "다 한 사람이 더 할 것"),
    ("interview.process", "전형 절차 — 공고에 적힌 회사가 드물다"),
]


def build_company(name: str, jobs: list[dict], vocab: list[str],
                  slug: str) -> dict:
    active = [j for j in jobs if j.get("status") != "closed"]
    closed = [j for j in jobs if j.get("status") == "closed"]
    dups = group_duplicates(active)
    dup_extra = sum(len(g["postings"]) - 1 for g in dups)

    postings = []
    for j in sorted(jobs, key=lambda x: (x.get("status") == "closed", x.get("title") or "")):
        study = extract_study(j, vocab)
        flags = [label for label, rx in EMPLOYMENT_FLAGS
                 if rx.search(j.get("full_jd") or "")]
        postings.append({
            "url": j.get("url", ""),
            "title": j.get("title", ""),
            "site": j.get("site", ""),
            "closed": j.get("status") == "closed",
            "career": parse_career(j.get("career") or ""),
            "location": norm_text(j.get("location") or "").split("지도보기")[0].strip(),
            "tech_stack": j.get("tech_stack") or [],
            "employment_flags": flags,
            "has_body": bool((j.get("qualifications") or "") or (j.get("main_tasks") or "")),
            "study": study,
        })

    stacks = Counter(t for j in jobs for t in (j.get("tech_stack") or []))
    careers = [p["career"] for p in postings if not p["closed"] and p["career"]]

    return {
        "_note": "정규식이 공고에서 뽑은 사실만 담는다. 판단 필드는 없다 — gaps 참조.",
        "slug": slug,
        "name": name,
        # 뷰어는 aliases.includes(normalizeCompany(공고.company)) 로 잇는다 —
        # 정규화를 거친 값을 적어야 화면에서 붙는다.
        "aliases": sorted({norm_company(j.get("company", "")) for j in jobs
                           if norm_company(j.get("company", ""))}),
        "company_names": sorted({j.get("company", "") for j in jobs if j.get("company")}),
        "generator": GENERATOR,
        "generated_at": date.today().isoformat(),
        "counts": {
            "postings": len(jobs),
            "active": len(active),
            "closed": len(closed),
            "with_body": sum(1 for p in postings if p["has_body"]),
            "distinct_active": len(active) - dup_extra,
            "study_items": sum(len(p["study"]) for p in postings),
        },
        "facts": extract_facts(jobs),
        "salary_mentions": extract_salary(jobs),
        "career_bands": careers,
        "tech_stack": [{"name": t, "count": n} for t, n in stacks.most_common(30)],
        "duplicates": dups,
        "postings": postings,
        "gaps": [{"field": f, "needs": w} for f, w in UNCODEABLE],
    }


# ── 실행 ─────────────────────────────────────────────────────────────────
def load_jobs() -> list[dict]:
    if not JOBS.exists():
        sys.exit(f"공고 파일이 없다: {JOBS}")
    with JOBS.open(encoding="utf-8") as f:
        return json.load(f)


def queue_top() -> str | None:
    """QUEUE.md '## 대기' 표의 첫 회사. 인트로에도 같은 글자가 있어 줄 시작으로 찾는다."""
    if not QUEUE.exists():
        return None
    text = QUEUE.read_text(encoding="utf-8")
    i = text.find("\n## 대기")
    if i < 0:
        return None
    for line in text[i:].split("\n")[1:]:
        if line.startswith("## ") and "대기" not in line:
            break
        if line.startswith("|") and not re.match(r"^\|[\s\-:|]+\|$", line):
            cell = line.split("|")[1].strip()
            if cell and cell != "회사":
                return cell
    return None


def write_company(doc: dict) -> Path:
    AUTO.mkdir(parents=True, exist_ok=True)
    (AUTO / "companies").mkdir(parents=True, exist_ok=True)
    fp = AUTO / "companies" / f"{doc['slug']}.json"
    fp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return fp


def rebuild_index() -> dict:
    """폴더를 다시 읽어 만든다 — 한 번에 한 회사만 돌려도 목록이 안 어긋난다.

    파일을 둘로 나눈다. **뷰어는 공고를 열 때마다 인덱스를 받으므로** 거기엔 회사를
    찾는 데 필요한 것(slug·aliases)만 넣는다. 3천 곳까지 늘어나면 카운트까지 담은
    인덱스가 700KB 가 되고, 그건 브리핑 하나 보려고 치르는 값으로 너무 크다.
    대시보드가 쓰는 집계는 stats.json 으로 뺀다 — 그건 사람이 열 때만 받는다.
    """
    lookup, stats = [], []
    for fp in sorted((AUTO / "companies").glob("*.json")):
        d = json.loads(fp.read_text(encoding="utf-8"))
        lookup.append({"slug": d["slug"], "aliases": d["aliases"]})
        stats.append({
            "slug": d["slug"], "name": d["name"], "counts": d["counts"],
            "has_facts": bool(d["facts"]), "has_salary": bool(d["salary_mentions"]),
            "generated_at": d["generated_at"],
        })
    today = date.today().isoformat()
    idx = {"_note": "뷰어 조회용 — 회사를 찾는 데 필요한 것만. 집계는 stats.json.",
           "generator": GENERATOR, "updated_at": today, "companies": lookup}
    (AUTO / "index.json").write_text(
        json.dumps(idx, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (AUTO / "stats.json").write_text(
        json.dumps({"generator": GENERATOR, "updated_at": today,
                    "companies": sorted(stats, key=lambda r: -r["counts"]["active"])},
                   ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return idx


def summarize(doc: dict) -> str:
    c = doc["counts"]
    out = [f"■ {doc['name']}  ({doc['slug']})",
           f"  공고 {c['postings']}건 — 모집중 {c['active']} / 마감 {c['closed']} / "
           f"본문있음 {c['with_body']} / 중복 뺀 실제 자리 {c['distinct_active']}",
           f"  학습 항목 {c['study_items']}개"]
    if doc["facts"]:
        out.append("  사실: " + " · ".join(
            f"{f['label']} {f['value']}" for f in doc["facts"].values()))
    else:
        out.append("  사실: 공고 본문에 회사 소개 정형 문구 없음")
    if doc["salary_mentions"]:
        for s in doc["salary_mentions"][:3]:
            rng = f"{s['low']}~{s['high']}" if s["high"] else f"{s['low']}"
            out.append(f"  연봉: {rng}만원 {s['bound']} — {s['quote'][:56]}")
    else:
        out.append("  연봉: 공고에 숫자 없음")
    bands = Counter(b["raw"] for b in doc["career_bands"])
    if bands:
        out.append("  경력: " + " · ".join(f"{k}×{v}" for k, v in bands.most_common(8)))
    for g in doc["duplicates"][:4]:
        out.append(f"  중복 {len(g['postings'])}건: " +
                   " / ".join(f"{p['site']}" for p in g["postings"]) +
                   f" — {g['postings'][0]['title'][:34]}")
    flagged = [p for p in doc["postings"] if p["employment_flags"] and not p["closed"]]
    for p in flagged[:4]:
        out.append(f"  ⚠ {','.join(p['employment_flags'])}: {p['title'][:40]}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("company", nargs="*", help="회사명 (여러 개 가능)")
    ap.add_argument("--queue", action="store_true", help="QUEUE.md 대기 맨 위 한 곳")
    ap.add_argument("--top", type=int, metavar="N", help="모집중 공고 많은 순 N곳")
    ap.add_argument("--all", action="store_true", help="손으로 쓴 브리핑이 없는 회사 전량")
    ap.add_argument("--min-active", type=int, default=3,
                    help="--top/--all 에서 모집중 공고가 이보다 적으면 건너뛴다 (기본 3)")
    ap.add_argument("--print", dest="dry", action="store_true", help="파일 안 쓰고 요약만")
    args = ap.parse_args()

    jobs = load_jobs()
    vocab = build_vocab(jobs)
    by_company: dict[str, list[dict]] = defaultdict(list)
    display: dict[str, str] = {}
    for j in jobs:
        n = collect_key(j.get("company", ""))
        if not n:
            continue
        by_company[n].append(j)
        # 표시명은 가장 짧은 표기를 쓴다 — "(주)" 가 붙은 쪽보다 읽기 낫다.
        if n not in display or len(j.get("company", "")) < len(display[n]):
            display[n] = j.get("company", "")

    targets: list[str] = [collect_key(c) for c in args.company]
    if args.queue:
        top = queue_top()
        if not top:
            sys.exit("QUEUE.md '## 대기' 에서 회사를 못 읽었다")
        targets.append(collect_key(top))
    if args.top or args.all:
        # 손으로 쓴 브리핑이 있는 회사도 뺀 적이 있는데 그게 틀렸다 — 뷰어는 **공고
        # 단위로** 폴백한다. 메가존클라우드처럼 회사 브리핑은 있는데 42건이 아직
        # 안 채워진 곳이 정확히 폴백이 필요한 자리다. 파일은 다른 폴더에 쌓이므로
        # 손으로 쓴 것을 덮지 않는다.
        ranked = sorted(by_company, key=lambda n: -sum(
            1 for j in by_company[n] if j.get("status") != "closed"))
        pool = [n for n in ranked
                if sum(1 for j in by_company[n] if j.get("status") != "closed") >= args.min_active]
        targets += pool[:args.top] if args.top else pool
    if not targets:
        ap.error("회사를 지정하거나 --queue / --top / --all 중 하나를 쓴다")

    overrides = {collect_key(k): v for k, v in load_overrides().items()}
    known = existing_slugs()
    used, missing, docs = set(), [], []
    for n in dict.fromkeys(targets):
        if n not in by_company:
            missing.append(n)
            continue
        slug = overrides.get(n) or known.get(n) or romanize(display[n])
        while slug in used:                       # 로마자가 겹치면 뒤에 번호를 붙인다
            slug += "-2"
        used.add(slug)
        docs.append(build_company(display[n], by_company[n], vocab, slug))

    for d in docs:
        print(summarize(d))
        if not args.dry:
            print(f"  → {write_company(d).relative_to(ROOT)}")
        print()
    if not args.dry and docs:
        idx = rebuild_index()
        print(f"index: {len(idx['companies'])}곳 → jd-viewer/public/guide/auto/index.json")
    for n in missing:
        print(f"⚠ 공고가 없다: {n}", file=sys.stderr)
    return 1 if missing and not docs else 0


if __name__ == "__main__":
    raise SystemExit(main())
