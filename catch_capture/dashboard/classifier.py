"""회사명 → 규모(대기업/중견/중소), title+tech → 개발자 직군 분류.

회사 화이트리스트는 dashboard/companies.json 에서 로드 (수동 큐레이션).
매칭 안 되면 fallback("중소기업" / "기타").
회사명은 부분 일치로 본다 ("삼성전자(주)" / "(주)삼성전자" 모두 "삼성전자"와 매칭).
긴 이름 우선 매칭 ("삼성전자DS" → "삼성전자"가 "삼성"보다 먼저 매칭).
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
#  - _NORM_PREFIX: [(norm, size, original)] 긴 이름 우선으로 정렬 (부분 일치)
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


def classify_company_size(company: str) -> tuple[str, str | None]:
    """반환: (label, matched_alias). label ∈ {"대기업","중견기업","중소기업"}."""
    if not company:
        return "중소기업", None
    nc = _norm_company(company)
    if not nc:
        return "중소기업", None
    # 1) 정확 일치
    hit = _NORM_EXACT.get(nc)
    if hit:
        return hit[0], hit[1]
    # 2) 부분 일치 — 긴 화이트리스트 이름이 회사명에 포함되거나 그 역
    for key, size, orig in _NORM_PREFIX:
        if not key:
            continue
        if key in nc or nc in key:
            return size, orig
    return "중소기업", None


# ---------- 개발자 직군 ----------
# title + tech_tags + tech_stack 텍스트에 대해 멀티라벨 매칭.

DEV_ROLE_RULES: dict[str, list[re.Pattern[str]]] = {
    "백엔드": [
        re.compile(r"백[\s-]?엔드|backend|back[\s-]?end|서버\s*개발|server\s*dev", re.IGNORECASE),
        re.compile(r"\b(API|REST|gRPC|MSA)\b", re.IGNORECASE),
        re.compile(r"\b(Spring|Spring\s*Boot|Django|Flask|FastAPI|Express|NestJS|Rails|Laravel|\.NET)\b", re.IGNORECASE),
        re.compile(r"\b(Node\.?js|Java|Kotlin|Go|Golang|Scala|Ruby|PHP)\b.*\b(개발|engineer|developer)\b", re.IGNORECASE),
    ],
    "프론트엔드": [
        re.compile(r"프[\s-]?론[\s-]?트[\s-]?엔드|frontend|front[\s-]?end|클라이언트\s*웹", re.IGNORECASE),
        re.compile(r"\b(React|Vue|Angular|Next\.?js|Nuxt|Svelte)\b", re.IGNORECASE),
        re.compile(r"\b(웹\s*퍼블리|publisher|UI\s*개발)\b", re.IGNORECASE),
    ],
    "모바일": [
        re.compile(r"\b(iOS|Android|안드로이드|모바일\s*개발|모바일\s*앱|앱\s*개발)\b", re.IGNORECASE),
        re.compile(r"\b(Swift|Kotlin|Flutter|React\s*Native)\b", re.IGNORECASE),
    ],
    "AI/ML": [
        re.compile(r"\b(AI|ML|머신러닝|딥러닝|인공지능|MLOps|데이터\s*사이언|data\s*scien)\b", re.IGNORECASE),
        re.compile(r"\b(TensorFlow|PyTorch|Keras|Scikit[-\s]?learn|HuggingFace|LangChain|OpenAI|LLM|NLP|CV|컴퓨터\s*비전)\b", re.IGNORECASE),
        re.compile(r"\b(데이터\s*엔지니어|data\s*engineer)\b", re.IGNORECASE),
    ],
    "펌웨어/임베디드": [
        re.compile(r"펌웨어|firmware|임베디드|embedded|반도체\s*설계|SoC|RTOS|MCU|FPGA|디바이스\s*드라이버", re.IGNORECASE),
        re.compile(r"\b(C/?C\+\+|C\+\+|어셈블리|assembly)\b.*\b(임베디드|펌웨어|hw|hardware)\b", re.IGNORECASE),
    ],
    "DevOps/인프라": [
        re.compile(r"DevOps|SRE|MLOps|infrastructure|인프라|클라우드\s*엔지니어|cloud\s*engineer|플랫폼\s*엔지니어|platform\s*engineer", re.IGNORECASE),
        re.compile(r"\b(Kubernetes|K8s|Docker|Terraform|Ansible|Jenkins|GitHub\s*Actions|AWS|GCP|Azure)\b.*\b(엔지니어|engineer|운영|ops)\b", re.IGNORECASE),
        re.compile(r"시스템\s*운영|시스템\s*관리", re.IGNORECASE),
    ],
    "데이터": [
        re.compile(r"데이터\s*엔지니어|data\s*engineer|데이터\s*분석|data\s*analy|빅데이터|big\s*data|BI\s*개발", re.IGNORECASE),
        re.compile(r"\b(Hadoop|Spark|Airflow|Kafka|ETL|Snowflake|BigQuery)\b", re.IGNORECASE),
    ],
    "보안": [
        re.compile(r"정보\s*보안|보안\s*엔지니어|security\s*engineer|침해\s*대응|모의\s*해킹|penetration|보안\s*개발", re.IGNORECASE),
    ],
    "게임": [
        re.compile(r"게임\s*개발|game\s*dev|game\s*client|game\s*server|언리얼|unreal|유니티|unity", re.IGNORECASE),
    ],
    "QA": [
        re.compile(r"\bQA\b|품질\s*보증|품질\s*엔지니어|test\s*engineer|테스트\s*자동화|automation\s*test", re.IGNORECASE),
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
