"""회사명 → 규모(대기업/중견/중소), title+tech → 개발자 직군 분류.

회사 화이트리스트는 dashboard/companies.json 에서 로드 (수동 큐레이션).
매칭 안 되면 fallback("중소기업" / "기타").

규모 매칭은 오탐 방지를 최우선으로 본다:
  1) 정규화 후 정확 일치   "삼성전자(주)" == "(주)삼성전자" == "삼성전자"
  2) 접두(prefix) 일치      회사명이 화이트리스트 이름으로 *시작*할 때만 계열사로 본다.
                            "삼성생명보험"→"삼성생명" ✓, "카카오VX"→"카카오" ✓, "라인게임즈"→"라인" ✓
  긴 이름 우선             "삼성전자DS" → "삼성전자"가 "삼성"보다 먼저 매칭.
중간/끝 substring 과 역방향 포함은 매칭하지 않는다(무관 회사 오탐 방지):
  "옥토스"/"LX판토스" ≠ "토스",  "(주)텐" ≠ "큐텐",  "디아이" ≠ "메디아이플러스".
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

_COMPANIES_JSON = Path(__file__).parent / "companies.json"


def _load_companies_from_json() -> tuple[list[str], list[str]]:
    """companies.json 에서 그룹을 평탄화해 [대기업], [중견기업] 두 리스트 반환."""
    if not _COMPANIES_JSON.exists():
        return [], []
    try:
        data = json.loads(_COMPANIES_JSON.read_text(encoding="utf-8"))
    except Exception:
        return [], []
    def _flatten(bucket: object) -> list[str]:
        if not isinstance(bucket, dict):
            return []
        out: list[str] = []
        for v in bucket.values():
            if isinstance(v, list):
                out.extend(x for x in v if isinstance(x, str) and x.strip())
        return out
    return _flatten(data.get("대기업")), _flatten(data.get("중견기업"))


# ---------- 회사 규모 ----------
# IT/개발자 채용 기준 사용자 인식에 맞춰 분류 (실제 데이터는 companies.json).
# 폴백 리스트: companies.json 로드 실패시에만 사용 (최소 시드).
_FALLBACK_LARGE: list[str] = [
    "삼성전자", "LG전자", "SK텔레콤", "KT", "현대자동차",
    "네이버", "카카오", "쿠팡", "토스", "라인", "배달의민족", "당근",
    "넥슨", "엔씨소프트", "넷마블", "크래프톤",
]

_FALLBACK_MID: list[str] = [
    "야놀자", "마켓컬리", "무신사", "두나무", "리벨리온", "업스테이지",
]


def _norm_company(name: str) -> str:
    """비교용 정규화: 소문자 + 공백/괄호/특수문자 제거."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name)
    s = s.lower()
    s = re.sub(r"\(주\)|주식회사|㈜|inc\.?|co\.?,?\s*ltd\.?|corp\.?|corporation|ltd\.?", "", s)
    s = re.sub(r"[\s\-_().,&/]+", "", s)
    return s


_LARGE_LIST_JSON, _MID_LIST_JSON = _load_companies_from_json()
LARGE_COMPANIES: list[str] = _LARGE_LIST_JSON or _FALLBACK_LARGE
MID_COMPANIES: list[str] = _MID_LIST_JSON or _FALLBACK_MID

# 매칭용 자료구조:
#  - _NORM_EXACT: 정규화 결과 → (size, original)  (정확 일치)
#  - _NORM_PREFIX: [(norm, size, original)] 긴 이름 우선으로 정렬 (접두 일치)
# 같은 norm 키가 대기업과 중견기업에 모두 있으면 대기업 우선 (큰 쪽 신뢰).
_NORM_EXACT: dict[str, tuple[str, str]] = {}
for _orig in MID_COMPANIES:
    _k = _norm_company(_orig)
    if _k:
        _NORM_EXACT[_k] = ("중견기업", _orig)
for _orig in LARGE_COMPANIES:
    _k = _norm_company(_orig)
    if _k:
        _NORM_EXACT[_k] = ("대기업", _orig)  # 대기업이 중견기업을 덮어씀

_NORM_PREFIX: list[tuple[str, str, str]] = [
    (k, sz, orig) for k, (sz, orig) in _NORM_EXACT.items()
]
# 긴 이름 우선 매칭 ("삼성전자" before "삼성")
_NORM_PREFIX.sort(key=lambda t: -len(t[0]))


# ---------- 회사 규모: 채용공고 본문에서 사원수·매출액 추출 ----------
# 채용 사이트(wanted/jobkorea/saramin 등)가 기업정보 영역에 실제 수치를 노출한다.
#   예) "구성원 25명 규모", "사원수 54명", "매출액 70억원", "매출 1.2조"
# 이 수치를 1순위로 쓰고, 없으면 화이트리스트, 그래도 없으면 중소기업으로 본다.

_HEADCOUNT_RES: list[re.Pattern[str]] = [
    re.compile(r"(?:사원수|임직원|구성원|종업원|직원\s*수)\s*[:은는]?\s*약?\s*([\d,]+)\s*명"),
    re.compile(r"([\d,]+)\s*명\s*규모"),
]
_REV_JO_RE = re.compile(r"매출(?:액)?\s*[:은는]?\s*약?\s*([\d,]+(?:\.\d+)?)\s*조\s*(?:([\d,]+)\s*억)?")
_REV_EOK_RE = re.compile(r"매출(?:액)?\s*[:은는]?\s*약?\s*([\d,]+(?:\.\d+)?)\s*억")
# 회사 자체 매출이 아닌 수치는 규모 판정에서 제외한다:
#   플랫폼 거래액/GMV("누적 ... 매출 1.1조 달성"), 추정·목표치("예상 매출액 6,462억").
_REV_NEG_CTX = re.compile(r"누적|거래\s*액|거래\s*대금|거래\s*규모|거래\s*총액|유통\s*액|gmv|예상|목표|전망", re.IGNORECASE)


def _rev_ctx_ok(text: str, start: int) -> bool:
    """매출 매칭 바로 앞(40자)에 거래액/예상치 신호가 없으면 회사 매출로 인정."""
    return not _REV_NEG_CTX.search(text[max(0, start - 40):start])

# 사원수 기준 (한국 통용): 1000명↑ 대기업 / 300명↑ 중견 / 그 외 중소.
# 매출액(억원)은 보조 — 사원수가 없을 때만 사용하고, 단독으로는 최대 중견까지만
# 올린다(대기업은 사원수·화이트리스트로만 판정). 본문 매출 수치는 '목표/달성' 등
# 신뢰도가 낮을 수 있어 보수적으로 본다.
_HC_LARGE, _HC_MID = 1000, 300
_REV_MID_EOK = 1000
_SIZE_RANK = {"대기업": 3, "중견기업": 2, "중소기업": 1}


def extract_headcount(text: str) -> int | None:
    """본문에서 사원수(명)를 추출. 못 찾으면 None."""
    if not text:
        return None
    for rx in _HEADCOUNT_RES:
        m = rx.search(text)
        if not m:
            continue
        try:
            n = int(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if 1 <= n <= 2_000_000:
            return n
    return None


def extract_revenue_eok(text: str) -> float | None:
    """본문에서 매출액을 억원 단위 숫자로 추출. 못 찾으면 None."""
    if not text:
        return None
    for m in _REV_JO_RE.finditer(text):
        if not _rev_ctx_ok(text, m.start()):
            continue
        try:
            jo = float(m.group(1).replace(",", ""))
            eok = float(m.group(2).replace(",", "")) if m.group(2) else 0.0
            return jo * 10000 + eok
        except ValueError:
            continue
    for m in _REV_EOK_RE.finditer(text):
        if not _rev_ctx_ok(text, m.start()):
            continue
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            continue
    return None


def _size_from_numbers(headcount: int | None, revenue_eok: float | None) -> str | None:
    if headcount:
        if headcount >= _HC_LARGE:
            return "대기업"
        if headcount >= _HC_MID:
            return "중견기업"
        return "중소기업"
    if revenue_eok:
        if revenue_eok >= _REV_MID_EOK:
            return "중견기업"
        # 매출액만으로 중소/대 단정은 하지 않음 (보조 지표)
    return None


def _whitelist_size(nc: str) -> tuple[str | None, str | None]:
    if not nc:
        return None, None
    # 1) 정확 일치
    hit = _NORM_EXACT.get(nc)
    if hit:
        return hit[0], hit[1]
    # 2) 접두(prefix) 일치만 허용 — 회사명이 화이트리스트 이름으로 *시작*할 때만 계열사로 본다.
    #    중간/끝 substring("옥토스"⊃"토스") 과 역방향 포함("(주)텐"⊂"큐텐")은
    #    무관한 회사를 끌어들이므로 매칭하지 않는다. 긴 이름이 먼저 매칭된다(_NORM_PREFIX 정렬).
    for key, size, orig in _NORM_PREFIX:
        if key and nc.startswith(key):
            return size, orig
    return None, None


def classify_company_size(
    company: str,
    headcount: int | None = None,
    revenue_eok: float | None = None,
) -> tuple[str, str | None]:
    """반환: (label, matched_alias). label ∈ {"대기업","중견기업","중소기업"}.

    사원수·매출액 수치(공고 본문 추출)와 화이트리스트 중 더 큰 규모를 택한다.
    수치도 화이트리스트도 없으면 중소기업으로 본다(기존 기본값).
    """
    if not company:
        return "중소기업", None
    nc = _norm_company(company)
    wl_size, wl_alias = _whitelist_size(nc)
    num_size = _size_from_numbers(headcount, revenue_eok)
    candidates = [s for s in (wl_size, num_size) if s]
    if not candidates:
        return "중소기업", None
    best = max(candidates, key=lambda s: _SIZE_RANK[s])
    # alias 는 화이트리스트로 매칭됐을 때만 의미가 있다
    return best, (wl_alias if wl_size else None)


# ---------- 개발자 직군 ----------
# title + tech_tags + tech_stack 텍스트에 대해 멀티라벨 매칭.

DEV_ROLE_RULES: dict[str, list[re.Pattern[str]]] = {
    "백엔드": [
        re.compile(r"백[\s-]?엔드|backend|back[\s-]?end|서버\s*개발|server\s*dev", re.IGNORECASE),
        re.compile(r"\b(API|REST|gRPC|MSA)\b", re.IGNORECASE),
        re.compile(r"\b(Spring|Spring\s*Boot|Django|Flask|FastAPI|Express|NestJS|Rails|Laravel|\.NET)\b", re.IGNORECASE),
        re.compile(r"\b(Node\.?js|Java|Kotlin|Go|Golang|Scala|Ruby|PHP)\b.*\b(개발|engineer|developer)\b", re.IGNORECASE),
        re.compile(r"\b(Python|Rust|C#|Scala|Ruby|PHP|Elixir)\s+(developer|engineer|programmer)\b", re.IGNORECASE),
    ],
    "프론트엔드": [
        re.compile(r"프[\s-]?론[\s-]?트[\s-]?엔드|frontend|front[\s-]?end|클라이언트\s*웹", re.IGNORECASE),
        re.compile(r"\b(React|Vue|Angular|Next\.?js|Nuxt|Svelte)\b", re.IGNORECASE),
        re.compile(r"\b(웹\s*퍼블리|publisher|UI\s*개발)\b", re.IGNORECASE),
        re.compile(r"\bweb\s+(developer|engineer)\b", re.IGNORECASE),
    ],
    "모바일": [
        re.compile(r"\b(iOS|Android|안드로이드|모바일\s*개발|모바일\s*앱|앱\s*개발)\b", re.IGNORECASE),
        re.compile(r"\b(Swift|Kotlin|Flutter|React\s*Native)\b", re.IGNORECASE),
    ],
    "AI/ML": [
        re.compile(r"\b(AI|ML|머신러닝|딥러닝|인공지능|MLOps|데이터\s*사이언티스트?|data\s*scien(?:tist|ce)?)\b", re.IGNORECASE),
        re.compile(r"\b(TensorFlow|PyTorch|Keras|Scikit[-\s]?learn|HuggingFace|LangChain|OpenAI|LLM|NLP|CV|컴퓨터\s*비전)\b", re.IGNORECASE),
        re.compile(r"\b(데이터\s*엔지니어|data\s*engineer)\b", re.IGNORECASE),
        re.compile(r"\b(research\s*engineer|research\s*scientist|applied\s*scientist|ml\s*engineer|machine\s*learning)\b", re.IGNORECASE),
    ],
    "펌웨어/임베디드": [
        re.compile(r"펌웨어|firmware|임베디드|embedded|반도체\s*설계|SoC|RTOS|MCU|FPGA|디바이스\s*드라이버", re.IGNORECASE),
        re.compile(r"\b(C/?C\+\+|C\+\+|어셈블리|assembly)\b.*\b(임베디드|펌웨어|hw|hardware)\b", re.IGNORECASE),
    ],
    "DevOps/인프라": [
        re.compile(r"DevOps|SRE|MLOps|infrastructure|인프라|클라우드\s*엔지니어|cloud\s*engineer|플랫폼\s*엔지니어|platform\s*engineer|site\s*reliability", re.IGNORECASE),
        re.compile(r"\b(Kubernetes|K8s|Docker|Terraform|Ansible|Jenkins|GitHub\s*Actions|AWS|GCP|Azure)\b.*\b(엔지니어|engineer|운영|ops)\b", re.IGNORECASE),
        re.compile(r"시스템\s*운영|시스템\s*관리", re.IGNORECASE),
    ],
    "데이터": [
        re.compile(r"데이터\s*엔지니어|data\s*engineer|데이터\s*분석|data\s*analy|빅데이터|big\s*data|BI\s*개발", re.IGNORECASE),
        re.compile(r"\b(Hadoop|Spark|Airflow|Kafka|ETL|Snowflake|BigQuery)\b", re.IGNORECASE),
        re.compile(r"data\s*(scientist|governance|platform|warehouse|analyst)", re.IGNORECASE),
    ],
    "보안": [
        re.compile(r"정보\s*보안|보안\s*엔지니어|security\s*engineer|침해\s*대응|모의\s*해킹|penetration|보안\s*개발|\b(appsec|infosec|cyber\s*security|cybersecurity|application\s*security|product\s*security|cloud\s*security|security\s*researcher)\b", re.IGNORECASE),
    ],
    "게임": [
        re.compile(r"게임\s*개발|game\s*dev|game\s*client|game\s*server|언리얼|unreal|유니티|unity", re.IGNORECASE),
    ],
    "QA": [
        re.compile(r"\bQA\b|품질\s*보증|품질\s*엔지니어|test\s*engineer|테스트\s*자동화|automation\s*test|automation\s*engineer|\bSDET\b", re.IGNORECASE),
    ],
    "풀스택": [
        re.compile(r"풀스택|full[\s-]?stack", re.IGNORECASE),
    ],
}


def classify_dev_roles(title: str, tech_tags: list[str] | None = None,
                       tech_stack: list[str] | None = None,
                       extra_text: str = "") -> list[str]:
    """멀티라벨. 매칭이 하나도 없으면 ['기타']."""
    tech_tags = tech_tags or []
    tech_stack = tech_stack or []
    blob = " | ".join([title or "", " ".join(tech_tags), " ".join(tech_stack), extra_text])
    roles: list[str] = []
    for role, patterns in DEV_ROLE_RULES.items():
        if any(p.search(blob) for p in patterns):
            roles.append(role)
    # 풀스택이 매칭되면 백/프 둘 다 추가(분포 통계에 양쪽 다 반영)
    if "풀스택" in roles:
        if "백엔드" not in roles:
            roles.append("백엔드")
        if "프론트엔드" not in roles:
            roles.append("프론트엔드")
    return roles or ["기타"]


# ---------- 역량(자격요건/우대사항) 키워드 추출 ----------
# 단순 정규식 매칭: 학력/경력/협업/문제해결 등 비기술 역량 + 도구

COMPETENCY_RULES: dict[str, list[re.Pattern[str]]] = {
    "협업/커뮤니케이션": [re.compile(r"협업|커뮤니케이션|소통|이해관계자|stakeholder|cross[-\s]?functional", re.IGNORECASE)],
    "문제해결": [re.compile(r"문제\s*해결|trouble\s*shoot|디버깅|장애\s*대응|incident", re.IGNORECASE)],
    "테스트/품질": [re.compile(r"테스트\s*코드|TDD|단위\s*테스트|unit\s*test|코드\s*리뷰|code\s*review", re.IGNORECASE)],
    "성능 최적화": [re.compile(r"성능\s*최적화|performance\s*tuning|튜닝|optimization", re.IGNORECASE)],
    "대용량 처리": [re.compile(r"대용량|대규모\s*트래픽|high\s*traffic|scalab|확장성", re.IGNORECASE)],
    "오너십/주도성": [re.compile(r"주도적|오너십|ownership|자기\s*주도|책임감", re.IGNORECASE)],
    "영어 가능": [re.compile(r"영어\s*가능|english\s*proficien|business\s*english|영어\s*비즈니스", re.IGNORECASE)],
    "학사 이상": [re.compile(r"학사\s*이상|bachelor", re.IGNORECASE)],
    "석박사 우대": [re.compile(r"석사|박사|phd|master|m\.s\.", re.IGNORECASE)],
    "오픈소스 기여": [re.compile(r"오픈소스|open[\s-]?source\s*contrib|github\s*활동", re.IGNORECASE)],
    "MSA/분산": [re.compile(r"MSA|microservice|마이크로서비스|분산\s*시스템|distributed", re.IGNORECASE)],
    "CI/CD": [re.compile(r"CI/CD|CI\s*\/\s*CD|jenkins|github\s*actions|gitlab\s*ci", re.IGNORECASE)],
    "클라우드 운영": [re.compile(r"클라우드\s*운영|aws\s*운영|gcp\s*운영|azure\s*운영", re.IGNORECASE)],
    "Agile/Scrum": [re.compile(r"애자일|agile|scrum|스크럼|kanban|칸반", re.IGNORECASE)],
}


def extract_competencies(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for label, patterns in COMPETENCY_RULES.items():
        if any(p.search(text) for p in patterns):
            found.append(label)
    return found
