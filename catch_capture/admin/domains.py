"""공고 도메인(업종) 분류 — 키워드 기반.

크롤된 공고에는 도메인이 없으므로(company_tech_radar.json은 유명사 큐레이션 전용),
공고 텍스트(회사/직무/주요업무/자격요건/우대)를 키워드로 스캔해 도메인을 부여한다.
가장 많이 적중한 도메인 상위 2개를 반환, 없으면 ['기타'].
"""
from __future__ import annotations

import re
from typing import Any

# 도메인 → 키워드(한/영). 소문자 비교.
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "핀테크": ["핀테크", "금융", "결제", "페이", "송금", "증권", "은행", "카드", "보험",
               "대출", "자산", "회계", "정산", "fintech", "payment", "bank", "finance"],
    "이커머스/커머스": ["커머스", "이커머스", "쇼핑", "마켓", "상거래", "리테일", "주문",
                      "쇼핑몰", "commerce", "retail", "shopping", "seller"],
    "데이터/AI": ["인공지능", "머신러닝", "딥러닝", "추천", "자연어", "비전", "데이터분석",
                 "데이터 분석", "빅데이터", "ai", "ml", "llm", "nlp", "recommendation", "데이터 파이프라인"],
    "게임": ["게임", "game", "유니티", "언리얼", "rpg", "캐주얼게임"],
    "IoT/임베디드": ["iot", "사물인터넷", "임베디드", "펌웨어", "센서", "디바이스", "하드웨어",
                    "제조", "양산", "embedded", "firmware", "hardware", "device", "mcu", "로봇"],
    "모빌리티": ["모빌리티", "자율주행", "차량", "운송", "택시", "주차", "물류배송", "mobility"],
    "물류/배달": ["물류", "배달", "배송", "풀필먼트", "fulfillment", "logistics", "delivery"],
    "헬스케어/바이오": ["헬스", "의료", "병원", "바이오", "제약", "진단", "건강", "health", "medical", "bio"],
    "교육": ["교육", "학습", "강의", "에듀", "이러닝", "edu", "education", "학원"],
    "미디어/콘텐츠": ["미디어", "콘텐츠", "영상", "웹툰", "스트리밍", "음악", "방송", "media", "content", "streaming"],
    "여행/숙박": ["여행", "숙박", "호텔", "항공", "예약", "travel", "booking"],
    "광고/마케팅": ["광고", "마케팅", "퍼포먼스", "ad ", "adtech", "marketing", "crm"],
    "HR/채용": ["채용", "인사", "hr", "recruit", "인재"],
    "부동산/프롭테크": ["부동산", "프롭테크", "임대", "분양", "proptech"],
    "블록체인/크립토": ["블록체인", "가상자산", "코인", "암호화폐", "blockchain", "crypto", "web3", "nft"],
    "인프라/클라우드": ["클라우드", "인프라", "devops", "sre", "cloud", "infra", "쿠버네티스", "데이터센터"],
    "SI/SM/공공": ["전자정부", "공공", "관공서", "시스템 통합", "구축", "유지보수", "sm ", "si ",
                  "운영 유지", "관리시스템", "연구원", "공단", "공사"],
    "보안": ["보안", "security", "침해", "백신", "암호", "인증", "취약점"],
    "협업툴/SaaS": ["saas", "협업", "솔루션", "b2b", "워크스페이스"],
    "커뮤니티/SNS": ["sns", "커뮤니티", "소셜", "메신저", "메시징", "community", "social"],
}

_DOMAIN_RE = {dom: re.compile("|".join(re.escape(k) for k in kws), re.I)
              for dom, kws in DOMAIN_KEYWORDS.items()}

_FIELDS = ("company", "title", "main_tasks", "qualifications", "preferences")


def _job_text(job: dict[str, Any]) -> str:
    out = []
    for k in _FIELDS:
        v = job.get(k)
        out.append(" ".join(v) if isinstance(v, list) else str(v or ""))
    return " ".join(out).lower()


def classify(job: dict[str, Any], top: int = 2) -> list[str]:
    text = _job_text(job)
    hits = []
    for dom, rx in _DOMAIN_RE.items():
        n = len(rx.findall(text))
        if n:
            hits.append((n, dom))
    if not hits:
        return ["기타"]
    hits.sort(reverse=True)
    return [d for _, d in hits[:top]]
