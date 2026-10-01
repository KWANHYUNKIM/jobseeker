"""기업 규모/유형 분류 — 큐레이션 + 휴리스틱.

크롤 공고에는 기업 규모 정보가 없어(회사명만) 정확한 규모 판정은 불가능하다.
주요 기업/계열·외국계 빅테크·유니콘·공공기관을 이름으로 매칭하고, 나머지는 '중소/기타'.
완벽하지 않으며 목록은 계속 보강 가능. (company_tech_radar.json의 글로벌 빅테크 재활용)
"""
from __future__ import annotations

# 우선순위 순으로 검사. 각 항목은 회사명에 포함되면 매칭되는 키워드(소문자).
_RULES: list[tuple[str, list[str]]] = [
    ("공공/연구", [
        "연구원", "연구소", "공단", "공사", "진흥원", "재단", "위원회", "협회",
        "kisti", "전자통신연구원", "원자력", "우정사업", "정부", "교육청",
    ]),
    ("외국계/빅테크", [
        "google", "구글", "amazon", "아마존", "aws", "microsoft", "마이크로소프트",
        "apple", "애플", "meta", "메타", "facebook", "netflix", "넷플릭스", "oracle",
        "오라클", "ibm", "sap", "nvidia", "엔비디아", "intel", "인텔", "openai",
        "anthropic", "uber", "우버", "tesla", "테슬라", "spotify", "salesforce",
        "datadog", "snowflake", "mongodb", "cloudflare", "linkedin", "discord",
        "지멘스", "siemens", "본사", "코리아", "korea ",
    ]),
    ("대기업/계열", [
        "삼성", "samsung", "에스케이", "sk텔레콤", "sk하이닉스", "sk c&c", "skt",
        "엘지", "lg전자", "lg화학", "lg cns", "lg유플러스", "현대", "기아", "롯데",
        "한화", "씨제이", "cj그룹", "지에스리테일", "두산", "포스코", "posco", "kt corporation",
        "네이버", "naver", "카카오", "kakao", "쿠팡", "coupang", "우아한형제들",
        "배달의민족", "라인플러스", "넥슨", "nexon", "엔씨소프트", "ncsoft", "넷마블",
        "netmarble", "크래프톤", "krafton", "스마일게이트", "신한", "kb국민", "하나은행",
        "우리은행", "nh농협", "현대오토에버", "삼성sds", "삼성전자", "한국전력",
        "대한항공", "현대모비스", "올리브영",
    ]),
    ("유니콘/스타트업", [
        "비바리퍼블리카", "토스", "당근", "두나무", "업비트", "야놀자", "무신사",
        "컬리", "마켓컬리", "직방", "리디", "뱅크샐러드", "업스테이지", "뤼튼",
        "오늘의집", "버킷플레이스", "센드버드", "몰로코", "포티투닷", "42dot",
        "메가존클라우드", "엔에이치엔", "nhn", "스캐터랩", "토스뱅크", "카카오뱅크",
    ]),
]

_DEFAULT = "중소/기타"


def classify(company: str | None) -> str:
    name = (company or "").strip().lower()
    if not name:
        return _DEFAULT
    for tier, kws in _RULES:
        for kw in kws:
            if kw in name:
                return tier
    return _DEFAULT


# UI 드롭다운 정렬용 표준 순서
ORDER = ["대기업/계열", "외국계/빅테크", "유니콘/스타트업", "공공/연구", _DEFAULT]
