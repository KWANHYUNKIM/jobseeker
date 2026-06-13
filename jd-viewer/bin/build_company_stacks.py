#!/usr/bin/env python3
"""회사별 기술스택·도메인·아키텍처 분석기 (StackShare 스타일).

입력: jd-viewer/public/all_jobs_enriched.json
출력: jd-viewer/public/company_stacks.json

회사명(company)으로 공고를 묶어, 각 회사가 어떤 기술을 쓰고(카테고리별 분류),
어떤 도메인에서 개발하며, 어떤 아키텍처를 쓸지 규칙기반으로 추론한다.

2차 보강: crawl_company.py 가 만든 company_profiles.json(회사 홈페이지 조사 결과)이
있으면 병합해 도메인/설명을 상세화한다. 없어도 1차 결과만으로 완결적이다.

기본은 공고 2건 이상 회사만(표본이 빈약한 1건짜리는 추론 신뢰도가 낮음).
--min N 으로 임계값 조정, --all 로 전체 포함.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "catch_capture" / "dashboard"))
from classifier import (  # noqa: E402
    classify_company_size,
    classify_dev_roles,
    extract_headcount,
    extract_revenue_eok,
    _norm_company,
)

INPUT = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
PROFILES = ROOT / "jd-viewer" / "public" / "company_profiles.json"
OUTPUT = ROOT / "jd-viewer" / "public" / "company_stacks.json"


# ─────────────────────────────────────────────────────────────────────────
# 1) 기술 정규화 + 카테고리
#    tech_stack 태그는 표기가 제각각("AZURE"/"Azure", "C/C++", "Tensorflow",
#    "Node.js", "CSS 3"...)이라, 정규화 키(소문자+공백/기호 제거)로 canonical
#    이름과 카테고리에 매핑한다. 매핑 안 되는 태그는 "기타"로.
# ─────────────────────────────────────────────────────────────────────────

CATEGORIES = [
    "언어", "백엔드", "프론트엔드", "모바일",
    "데이터베이스", "인프라/DevOps", "AI/ML", "데이터", "협업/도구", "기타",
]

# (canonical, category, [aliases]) — aliases 는 정규화 전 원문 표기
_TECH_DEFS: list[tuple[str, str, list[str]]] = [
    # 언어
    ("Java", "언어", []),
    ("Kotlin", "언어", []),
    ("Python", "언어", []),
    ("JavaScript", "언어", ["JS", "ES6", "ES2015", "Vanilla JS"]),
    ("TypeScript", "언어", ["TS"]),
    ("C++", "언어", ["C/C++", "CPP"]),
    ("C", "언어", []),
    ("C#", "언어", ["CSharp"]),
    ("Go", "언어", ["Golang"]),
    ("Rust", "언어", []),
    ("Ruby", "언어", []),
    ("PHP", "언어", []),
    ("Swift", "언어", []),
    ("Objective-C", "언어", ["Objective C", "ObjC"]),
    ("Scala", "언어", []),
    ("Dart", "언어", []),
    ("R", "언어", ["R Language"]),
    ("MATLAB", "언어", []),
    ("Perl", "언어", []),
    ("Assembly", "언어", ["어셈블리"]),
    # 백엔드
    ("Spring", "백엔드", ["Spring Framework"]),
    ("Spring Boot", "백엔드", ["SpringBoot"]),
    ("Node.js", "백엔드", ["NodeJS", "Node"]),
    ("Django", "백엔드", []),
    ("Flask", "백엔드", []),
    ("FastAPI", "백엔드", []),
    ("Express", "백엔드", ["Express.js", "ExpressJS"]),
    ("NestJS", "백엔드", ["Nest.js", "Nest"]),
    (".NET", "백엔드", ["ASP.NET", "dotNET", ".NET Core"]),
    ("Rails", "백엔드", ["Ruby on Rails", "RoR"]),
    ("Laravel", "백엔드", []),
    ("JPA", "백엔드", ["Hibernate"]),
    ("GraphQL", "백엔드", []),
    ("gRPC", "백엔드", []),
    ("REST API", "백엔드", ["RESTful", "REST"]),
    ("MSA", "백엔드", ["Microservices", "마이크로서비스"]),
    # 프론트엔드
    ("React", "프론트엔드", ["ReactJS", "React.js"]),
    ("Vue", "프론트엔드", ["Vue.js", "VueJS", "Vue3"]),
    ("Angular", "프론트엔드", ["AngularJS"]),
    ("Next.js", "프론트엔드", ["NextJS", "Next"]),
    ("Nuxt", "프론트엔드", ["Nuxt.js"]),
    ("Svelte", "프론트엔드", ["SvelteKit"]),
    ("jQuery", "프론트엔드", []),
    ("HTML", "프론트엔드", ["HTML5"]),
    ("CSS", "프론트엔드", ["CSS3", "CSS 3"]),
    ("SCSS", "프론트엔드", ["SASS"]),
    ("Tailwind", "프론트엔드", ["TailwindCSS", "Tailwind CSS"]),
    ("Redux", "프론트엔드", []),
    ("Webpack", "프론트엔드", []),
    ("Vite", "프론트엔드", []),
    # 모바일
    ("iOS", "모바일", []),
    ("Android", "모바일", ["Android OS"]),
    ("SwiftUI", "모바일", []),
    ("Jetpack Compose", "모바일", ["Compose"]),
    ("Flutter", "모바일", []),
    ("React Native", "모바일", ["ReactNative", "RN"]),
    # 데이터베이스
    ("MySQL", "데이터베이스", []),
    ("PostgreSQL", "데이터베이스", ["Postgres"]),
    ("MongoDB", "데이터베이스", ["Mongo"]),
    ("Redis", "데이터베이스", []),
    ("Oracle", "데이터베이스", []),
    ("MariaDB", "데이터베이스", []),
    ("MSSQL", "데이터베이스", ["Microsoft SQL Server", "SQL Server"]),
    ("Elasticsearch", "데이터베이스", ["ElasticSearch", "ES", "OpenSearch"]),
    ("DynamoDB", "데이터베이스", []),
    ("Cassandra", "데이터베이스", []),
    ("SQLite", "데이터베이스", []),
    ("Prisma", "데이터베이스", []),
    # 인프라/DevOps
    ("AWS", "인프라/DevOps", ["Amazon Web Services"]),
    ("GCP", "인프라/DevOps", ["Google Cloud", "Google Cloud Platform"]),
    ("Azure", "인프라/DevOps", []),
    ("Docker", "인프라/DevOps", []),
    ("Kubernetes", "인프라/DevOps", ["K8s"]),
    ("Jenkins", "인프라/DevOps", []),
    ("GitHub Actions", "인프라/DevOps", []),
    ("GitLab CI", "인프라/DevOps", ["GitLab"]),
    ("Terraform", "인프라/DevOps", []),
    ("Ansible", "인프라/DevOps", []),
    ("Nginx", "인프라/DevOps", ["NGINX"]),
    ("Apache", "인프라/DevOps", []),
    ("Helm", "인프라/DevOps", []),
    ("ArgoCD", "인프라/DevOps", []),
    ("Prometheus", "인프라/DevOps", []),
    ("Grafana", "인프라/DevOps", []),
    ("Linux", "인프라/DevOps", []),
    ("Embedded Linux", "인프라/DevOps", []),
    # AI/ML
    ("TensorFlow", "AI/ML", ["Tensorflow"]),
    ("PyTorch", "AI/ML", ["Pytorch"]),
    ("Keras", "AI/ML", []),
    ("Scikit-learn", "AI/ML", ["Scikit Learn", "sklearn"]),
    ("OpenCV", "AI/ML", []),
    ("HuggingFace", "AI/ML", ["Hugging Face"]),
    ("LangChain", "AI/ML", []),
    ("OpenAI", "AI/ML", []),
    ("NumPy", "AI/ML", ["Numpy"]),
    ("Pandas", "AI/ML", []),
    ("CUDA", "AI/ML", []),
    ("ONNX", "AI/ML", []),
    ("DeepLearning", "AI/ML", ["Deep Learning", "딥러닝"]),
    # 데이터 엔지니어링
    ("Spark", "데이터", ["Apache Spark"]),
    ("Hadoop", "데이터", []),
    ("Airflow", "데이터", ["Apache Airflow"]),
    ("Kafka", "데이터", ["Apache Kafka"]),
    ("RabbitMQ", "데이터", []),
    ("Snowflake", "데이터", []),
    ("BigQuery", "데이터", []),
    ("dbt", "데이터", []),
    ("Flink", "데이터", []),
    # 협업/도구
    ("Git", "협업/도구", []),
    ("GitHub", "협업/도구", []),
    ("Bitbucket", "협업/도구", []),
    ("SVN", "협업/도구", []),
    ("Jira", "협업/도구", []),
    ("Confluence", "협업/도구", []),
    ("Figma", "협업/도구", []),
    ("Slack", "협업/도구", []),
    ("Notion", "협업/도구", []),
    # 추가 매핑 — 기타로 새던 실제 기술들
    ("SQL", "데이터베이스", []),
    ("NoSQL", "데이터베이스", ["NoSql"]),
    ("Firebase", "데이터베이스", []),
    ("Supabase", "데이터베이스", []),
    ("Amazon RDS", "데이터베이스", ["RDS"]),
    ("MyBatis", "백엔드", ["Mybatis"]),
    ("JSP", "백엔드", []),
    ("Apache Tomcat", "인프라/DevOps", ["Tomcat"]),
    ("WebSocket", "백엔드", []),
    ("WebRTC", "백엔드", []),
    ("MQTT", "백엔드", []),
    ("Zustand", "프론트엔드", []),
    ("Linux", "인프라/DevOps", ["Unix", "Ubuntu"]),
    ("Windows", "인프라/DevOps", []),
    ("Firmware", "펌웨어/임베디드", ["FW", "펌웨어"]),
    ("Embedded", "펌웨어/임베디드", ["임베디드"]),
    ("RTOS", "펌웨어/임베디드", ["FreeRTOS", "Zephyr"]),
    ("MCU", "펌웨어/임베디드", []),
    ("FPGA", "펌웨어/임베디드", []),
    ("ARM", "펌웨어/임베디드", []),
    ("PLC", "펌웨어/임베디드", []),
    ("ROS", "펌웨어/임베디드", []),
    ("Qt", "기타", []),
    ("WPF", "기타", []),
    ("MFC", "기타", ["Mfc"]),
    ("Delphi", "기타", []),
    ("Unity", "기타", []),
    ("Unreal Engine", "기타", ["Unreal", "UnrealEngine"]),
    ("Blockchain", "기타", ["블록체인"]),
    ("Selenium", "협업/도구", []),
    ("Jest", "협업/도구", []),
    ("JUnit", "협업/도구", []),
    ("Pytest", "협업/도구", []),
]

# 펌웨어/임베디드 카테고리를 카테고리 목록에 반영
if "펌웨어/임베디드" not in CATEGORIES:
    CATEGORIES.insert(CATEGORIES.index("AI/ML"), "펌웨어/임베디드")


def _nk(s: str) -> str:
    """정규화 키: 소문자 + 영숫자만(공백/기호/점 제거)."""
    return re.sub(r"[^a-z0-9가-힣+#]", "", s.lower())


# 기술이 아닌 잡음 태그 — 집계에서 완전히 제외(지역명·초일반 약어)
_STOPWORDS: set[str] = {
    _nk(x) for x in [
        "서울", "경기", "경기도", "인천", "부산", "대구", "대전", "광주", "울산",
        "세종", "경남", "경북", "전남", "전북", "충남", "충북", "강원", "제주",
        "SW", "HW", "DB", "GUI", "OS", "PC", "IT", "API", "UI", "UX", "QA",
        "Network", "신입", "경력", "정규직", "계약직", "병역특례", "기타",
    ]
}


# 정규화 키 → (canonical, category). 긴 별칭이 짧은 것보다 먼저 매칭되도록
# 길이 내림차순으로 lookup 을 구성한다.
_TECH_LOOKUP: dict[str, tuple[str, str]] = {}
for _canon, _cat, _aliases in _TECH_DEFS:
    for _name in [_canon, *_aliases]:
        k = _nk(_name)
        if k and k not in _TECH_LOOKUP:
            _TECH_LOOKUP[k] = (_canon, _cat)


def canon_tech(tag: str) -> tuple[str, str] | None:
    """원문 태그 → (canonical 이름, 카테고리).

    잡음(지역명·초일반 약어)이면 None. 못 찾으면 (정리된 원문, '기타')."""
    k = _nk(tag)
    if not k or k in _STOPWORDS:
        return None
    if k in _TECH_LOOKUP:
        return _TECH_LOOKUP[k]
    return tag.strip(), "기타"


# ─────────────────────────────────────────────────────────────────────────
# 2) 도메인 추론 — 공고 본문 키워드 매칭(공고 단위 점수)
# ─────────────────────────────────────────────────────────────────────────

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "의료/헬스케어/바이오": [
        "의료", "헬스케어", "병원", "바이오", "진단", "제약", "의공",
        "디지털 치료", "의료기기", "임상", "유전체", "신약", "환자",
    ],
    "핀테크/금융": [
        "금융", "핀테크", "결제", "페이먼트", "간편결제", "보험", "증권",
        "자산운용", "은행", "카드사", "대출", "송금", "거래소", "지급결제",
    ],
    "커머스/리테일/물류": [
        "커머스", "이커머스", "쇼핑", "리테일", "유통", "물류", "배송",
        "주문", "장바구니", "셀러", "풀필먼트", "재고",
    ],
    "게임": [
        "게임", "메타버스", "MMORPG", "모바일 게임", "게임 서버", "유저 콘텐츠",
    ],
    "교육/에듀테크": [
        "교육", "에듀", "이러닝", "학습", "강의", "튜터", "코딩 교육", "입시",
    ],
    "모빌리티/자율주행": [
        "모빌리티", "자율주행", "차량", "운송", "택시", "라이드", "주차",
        "ADAS", "전기차", "충전",
    ],
    "제조/하드웨어/로보틱스": [
        "제조", "반도체", "로봇", "로보틱스", "드론", "IoT", "디바이스",
        "센서", "스마트팩토리", "공정", "양산", "자동화 장비", "PLC",
    ],
    "콘텐츠/미디어/광고": [
        "콘텐츠", "미디어", "영상", "스트리밍", "웹툰", "음악", "광고",
        "마케팅 플랫폼", "크리에이터", "OTT",
    ],
    "보안": [
        "정보보안", "보안 솔루션", "침해", "해킹", "위협", "악성코드",
        "취약점", "관제", "암호",
    ],
    "AI/데이터 플랫폼": [
        "생성형 AI", "LLM", "거대언어모델", "추천 시스템", "데이터 플랫폼",
        "AI 모델", "초거대", "비전 AI", "음성인식", "자연어처리",
    ],
    "B2B SaaS/엔터프라이즈": [
        "SaaS", "B2B", "ERP", "CRM", "그룹웨어", "솔루션", "엔터프라이즈",
        "업무 자동화", "협업 툴", "워크플로우",
    ],
    "프롭테크/부동산": ["부동산", "프롭테크", "임대", "중개", "공간", "인테리어"],
    "여행/숙박": ["여행", "숙박", "항공", "호텔", "예약", "투어"],
    "HR/채용": ["채용", "HR", "인사", "구인", "이력서", "원티드"],
    "푸드테크": ["푸드", "배달", "음식점", "외식", "식자재", "레시피"],
    "블록체인/웹3": ["블록체인", "암호화폐", "가상자산", "NFT", "web3", "토큰", "디파이"],
}


def infer_domains(text: str, top: int = 2) -> list[dict]:
    """공고 본문 합본 텍스트에서 도메인 점수화. 상위 top 개 반환."""
    if not text:
        return []
    low = text.lower()
    scores: list[tuple[str, int, list[str]]] = []
    for dom, kws in DOMAIN_KEYWORDS.items():
        hits = [k for k in kws if k.lower() in low]
        if hits:
            # 점수 = 매칭 키워드 수(다양성) + 최빈 키워드 등장수 보정
            score = len(hits) + sum(low.count(h.lower()) for h in hits) // 3
            scores.append((dom, score, hits[:4]))
    scores.sort(key=lambda t: -t[1])
    return [{"name": d, "score": s, "evidence": ev} for d, s, ev in scores[:top]]


# ─────────────────────────────────────────────────────────────────────────
# 3) 아키텍처 추론 — 기술 조합 + 본문 신호 기반 규칙
#    각 규칙: 기술 집합/텍스트를 보고 (라벨, 근거) 를 만든다. "예측"의 핵심.
# ─────────────────────────────────────────────────────────────────────────


def infer_architecture(canon_set: set[str], text: str, roles: set[str]) -> list[dict]:
    """canon_set: canonical 기술 이름 집합. text: 본문 합본(소문자 비교용)."""
    low = text.lower()
    has = lambda *names: any(n in canon_set for n in names)
    out: list[dict] = []

    def add(label: str, why: str) -> None:
        if not any(o["label"] == label for o in out):
            out.append({"label": label, "why": why})

    # MSA / 마이크로서비스
    msa_signal = "MSA" in canon_set or "msa" in low or "마이크로서비스" in low or "microservice" in low
    if msa_signal or (has("Kafka") and has("Kubernetes") and has("Spring", "Spring Boot")):
        add("MSA · 마이크로서비스",
            "MSA 언급 또는 Kafka·Kubernetes·Spring 조합 — 서비스 분리·이벤트 기반 구조 추정")

    # 컨테이너 오케스트레이션
    if has("Kubernetes"):
        add("컨테이너 오케스트레이션 (K8s)",
            "Kubernetes 사용 — 컨테이너 기반 배포·오토스케일링 운영 추정")
    elif has("Docker"):
        add("컨테이너 기반 배포 (Docker)",
            "Docker 사용 — 컨테이너로 패키징·배포하는 환경 추정")

    # 클라우드 네이티브
    cloud = [c for c in ("AWS", "GCP", "Azure") if c in canon_set]
    if cloud:
        add(f"클라우드 ({'/'.join(cloud)})",
            f"{', '.join(cloud)} 사용 — 매니지드 클라우드 인프라 위에서 운영")

    # 데이터 파이프라인 / 스트리밍
    if has("Airflow", "Spark", "Kafka", "Hadoop", "dbt", "Flink"):
        de = [t for t in ("Airflow", "Spark", "Kafka", "Hadoop", "dbt", "Flink", "Snowflake", "BigQuery") if t in canon_set]
        add("데이터 파이프라인 · ETL",
            f"{', '.join(de)} — 배치/스트리밍 데이터 처리 파이프라인 추정")

    # ML 서빙
    if has("PyTorch", "TensorFlow", "HuggingFace") and has("FastAPI", "Flask", "OpenAI", "LangChain"):
        add("ML 모델 서빙 파이프라인",
            "딥러닝 프레임워크 + API 서빙 조합 — 모델 학습·추론 서빙 구조 추정")
    elif has("LangChain", "OpenAI") or "llm" in low or "rag" in low:
        add("LLM · 생성형 AI 애플리케이션",
            "LangChain/OpenAI 또는 LLM·RAG 언급 — 생성형 AI 파이프라인 추정")

    # 프론트/백 분리 (SPA + API)
    fe = has("React", "Vue", "Angular", "Svelte")
    be = has("Spring", "Spring Boot", "Django", "FastAPI", "Express", "NestJS", "Node.js", ".NET", "Laravel", "Rails")
    if has("Next.js", "Nuxt"):
        add("SSR · 풀스택 프레임워크",
            "Next.js/Nuxt — 서버사이드 렌더링 기반 풀스택 웹 구조")
    elif fe and be:
        add("SPA + REST API (프론트/백 분리)",
            "SPA 프레임워크 + 서버 프레임워크 — 화면/서버를 API로 분리한 구조")

    # 모바일 네이티브
    if has("Swift", "SwiftUI", "Kotlin", "Jetpack Compose") and ("모바일" in roles or has("iOS", "Android")):
        add("네이티브 모바일 앱",
            "Swift/Kotlin 네이티브 + 모바일 직군 — iOS/Android 앱 개발")
    elif has("Flutter", "React Native"):
        add("크로스플랫폼 모바일 앱",
            "Flutter/React Native — 단일 코드베이스로 iOS·Android 동시 개발")

    # 임베디드 / 펌웨어
    if "펌웨어/임베디드" in roles or has("Embedded Linux") or "rtos" in low or "임베디드" in low:
        if has("C", "C++"):
            add("임베디드 · 펌웨어",
                "C/C++ + 임베디드 신호 — 하드웨어 제어 펌웨어/디바이스 SW")

    # 모놀리식(폴백) — 단일 백엔드 프레임워크에 분산 신호가 없을 때
    if be and not out:
        add("모놀리식 (추정)",
            "단일 서버 프레임워크 중심, 분산/컨테이너 신호 약함 — 모놀리식 추정")

    return out


# ─────────────────────────────────────────────────────────────────────────
# 4) 취업 가이드 — "이 회사에 들어가려면" 추론
#    회사가 실제로 쓰는 스택/직군/도메인/아키텍처를 근거로
#    (1) 원하는 인재상  (2) 공부 로드맵  (3) 입사 후 업무  (4) 추천 기술블로그
#    를 규칙기반으로 생성한다. 모두 그 회사의 데이터에서만 끌어온다.
# ─────────────────────────────────────────────────────────────────────────

# canonical 기술 → "무엇을·어떻게 공부할지" 한 줄 팁 (구체적 행동 위주)
LEARN_DB: dict[str, str] = {
    # 언어
    "Java": "JVM·OOP 기본기 → 컬렉션·제네릭·스트림, 멀티스레드 동시성까지",
    "Kotlin": "코루틴 기반 비동기와 널 안전성 — 자바 상호운용까지 익히기",
    "Python": "기본 문법 후 가상환경·타입힌트, 표준 라이브러리로 작은 도구 만들기",
    "JavaScript": "ES6+ 문법·비동기(Promise/async)·이벤트루프 이해가 핵심",
    "TypeScript": "타입 시스템·제네릭·유틸리티 타입으로 안전한 JS 작성",
    "Go": "고루틴·채널 동시성 모델과 표준 net/http로 서버 만들기",
    "Rust": "소유권·라이프타임·트레잇 — 소규모 CLI로 메모리 모델 체득",
    "C++": "포인터·메모리·RAII, STL 컨테이너/알고리즘 활용",
    "C": "포인터·메모리 구조·시스템 콜 — 임베디드/시스템 기반",
    "Swift": "옵셔널·프로토콜 지향, SwiftUI로 화면 만들어 보기",
    "Scala": "함수형 + JVM, Spark 데이터 처리와 함께 학습하면 효율적",
    # 백엔드
    "Spring": "DI/IoC·AOP 이해 후 Spring Boot로 REST API 토이프로젝트",
    "Spring Boot": "REST API·JPA·검증·예외처리로 CRUD 서비스 완성해 보기",
    "Node.js": "이벤트루프·논블로킹 IO 이해, Express/Nest로 API 구현",
    "Django": "ORM·Admin·DRF로 빠르게 API 서버 만들어 배포까지",
    "FastAPI": "비동기 + Pydantic 검증으로 ML/일반 API 서빙 실습",
    "NestJS": "모듈·DI 구조로 확장 가능한 TS 백엔드 설계",
    "Express": "미들웨어 패턴으로 라우팅·인증 붙여 REST API 완성",
    "JPA": "엔티티 매핑·연관관계·N+1 문제와 페치 전략 이해",
    "GraphQL": "스키마·리졸버 설계, REST와의 트레이드오프 비교",
    "gRPC": "Protobuf 스키마·스트리밍 — 서비스 간 통신 실습",
    "MSA": "도메인 분리·서비스 경계·통신/트랜잭션 패턴 학습",
    "REST API": "리소스 설계·상태코드·버저닝 등 API 설계 원칙 체득",
    # 프론트엔드
    "React": "컴포넌트·훅·상태관리·렌더링 최적화로 SPA 완성",
    "Vue": "반응형 시스템·컴포지션 API로 화면 구성",
    "Next.js": "SSR/SSG·라우팅·서버컴포넌트로 풀스택 웹 구축",
    "Redux": "전역 상태·불변성·미들웨어 흐름 이해",
    "Tailwind": "유틸리티 클래스로 빠르게 반응형 UI 구성",
    # 모바일
    "iOS": "Swift + UIKit/SwiftUI, 생명주기·네트워킹·앱스토어 배포",
    "Android": "Kotlin + Jetpack(아키텍처 컴포넌트)로 앱 구조 설계",
    "SwiftUI": "선언형 UI·상태관리로 iOS 화면 빠르게 구현",
    "Jetpack Compose": "선언형 UI로 안드로이드 화면 구성",
    "Flutter": "Dart + 위젯 트리로 iOS·Android 동시 개발",
    "React Native": "JS/RN 컴포넌트로 크로스플랫폼 앱 구현",
    # DB
    "MySQL": "스키마 설계·인덱스·실행계획(EXPLAIN)으로 쿼리 최적화",
    "PostgreSQL": "고급 SQL·인덱스·트랜잭션 격리수준 이해",
    "MongoDB": "문서 모델링·인덱스, 언제 NoSQL이 유리한지 판단",
    "Redis": "캐시·세션·랭킹·분산락 등 활용 패턴 익히기",
    "Elasticsearch": "역색인·분석기·검색 쿼리로 검색 기능 구현",
    "SQL": "조인·집계·서브쿼리·윈도우 함수 등 쿼리 기본기",
    # 인프라/DevOps
    "AWS": "EC2·S3·RDS·IAM 기본 → VPC·로드밸런서로 배포 구성",
    "GCP": "GCE·GCS·BigQuery 중심으로 클라우드 인프라 이해",
    "Azure": "App Service·AKS·Storage로 클라우드 배포 실습",
    "Docker": "이미지·레이어·Dockerfile·compose로 앱 컨테이너화",
    "Kubernetes": "Pod·Service·Deployment·Ingress로 배포·오토스케일",
    "Terraform": "IaC로 인프라를 코드화 — 상태·모듈 관리",
    "Jenkins": "파이프라인으로 빌드·테스트·배포 자동화(CI/CD)",
    "GitHub Actions": "워크플로 YAML로 CI/CD 파이프라인 구성",
    "Nginx": "리버스 프록시·로드밸런싱·TLS 설정 이해",
    "Prometheus": "메트릭 수집·쿼리(PromQL)로 서비스 관측",
    "Grafana": "대시보드로 지표 시각화·알람 구성",
    "Linux": "셸·프로세스·권한·네트워크 등 서버 운영 기본",
    # AI/ML · 데이터
    "PyTorch": "텐서·autograd로 모델 직접 학습, 파인튜닝까지",
    "TensorFlow": "Keras API로 모델 구성·학습·서빙",
    "LangChain": "프롬프트·체인·RAG 파이프라인으로 LLM 앱 구현",
    "OpenAI": "API·함수호출·임베딩으로 생성형 기능 붙이기",
    "HuggingFace": "사전학습 모델 로드·파인튜닝·추론 파이프라인",
    "Pandas": "데이터프레임 가공·집계·결합으로 전처리 실습",
    "Spark": "분산 처리·DataFrame API로 대용량 ETL",
    "Airflow": "DAG로 배치 워크플로 스케줄링·의존성 관리",
    "Kafka": "토픽·파티션·컨슈머 그룹으로 이벤트 스트리밍 설계",
    "dbt": "SQL 기반 데이터 변환·테스트·문서화",
    # 협업
    "Git": "브랜치 전략·PR·리베이스 등 협업 워크플로 체득",
}

# 직군 → 로드맵 핵심 단계의 주력 카테고리
ROLE_PRIMARY_CAT: dict[str, str] = {
    "백엔드": "백엔드",
    "풀스택": "백엔드",
    "프론트엔드": "프론트엔드",
    "모바일": "모바일",
    "AI/ML": "AI/ML",
    "데이터": "데이터",
    "DevOps/인프라": "인프라/DevOps",
    "보안": "인프라/DevOps",
    "펌웨어/임베디드": "언어",
}

# 직군 → 입사 후 핵심 업무(베이스)
ROLE_TASK: dict[str, str] = {
    "백엔드": "API·서버 비즈니스 로직 개발과 DB 모델링",
    "프론트엔드": "사용자 화면(UI) 구현과 상태관리·렌더링 성능 최적화",
    "모바일": "iOS/Android 앱 화면·기능 개발과 스토어 배포",
    "AI/ML": "모델 학습·평가와 추론(서빙) 파이프라인 개발",
    "데이터": "데이터 수집·가공(ETL)과 분석·지표 파이프라인 구축",
    "DevOps/인프라": "CI/CD·컨테이너 배포와 모니터링·인프라 운영",
    "보안": "취약점 점검·보안 모니터링과 침해 대응 체계 운영",
    "풀스택": "프론트엔드~백엔드 전반의 기능 개발",
    "펌웨어/임베디드": "디바이스 펌웨어·하드웨어 제어 SW 개발",
}


def _seniority(titles: list[str]) -> tuple[bool, bool]:
    """공고 제목들에서 시니어/주니어 신호. (시니어_강함, 주니어_기회)."""
    blob = " ".join(titles).lower()
    senior = any(k in blob for k in (
        "senior", "staff", "principal", "lead", "리드", "팀장", "수석", "책임",
        "head of", "엔지니어링 매니저", "engineering manager",
    ))
    junior = any(k in blob for k in (
        "신입", "주니어", "junior", "인턴", "intern", "associate", "전환형", "신규편입",
    ))
    return senior, junior


def infer_career_guide(rec: dict, blob: str) -> dict:
    """rec(집계된 회사 레코드) + 본문 blob 으로 취업 가이드 생성."""
    cats = rec["tech_categories"]
    top_tech = [t["name"] for t in rec["top_tech"]]
    roles = list(rec["roles"])
    primary_role = roles[0] if roles else None
    dom = rec["domains"][0]["name"] if rec["domains"] else None
    arch_labels = [a["label"] for a in rec["architecture"]]
    low = blob.lower()

    def cat_names(cat: str, n: int = 4) -> list[str]:
        return [t["name"] for t in cats.get(cat, [])][:n]

    # ── (1) 원하는 인재상 ────────────────────────────────────────────
    wants: list[str] = []
    senior, junior = _seniority(rec.get("titles") or [])
    if senior and not junior:
        wants.append("주로 시니어·리드 채용 — 주도적으로 설계·문제 해결한 경력 어필이 필요")
    elif junior:
        wants.append("신입·주니어/인턴 기회 있음 — 기본기 + 완성도 있는 포트폴리오로 도전 가능")
    if top_tech:
        wants.append(f"핵심 역량: {', '.join(top_tech[:3])} 실무 경험(토이프로젝트라도 동작하는 결과물)")
    if primary_role:
        sec = roles[1] if len(roles) > 1 else None
        rtxt = primary_role + (f" 중심(+{sec})" if sec else " 중심")
        wants.append(f"{rtxt} 직군 — 해당 역할의 실전 문제를 풀어본 경험")
    if dom:
        wants.append(f"{dom} 도메인 이해 — 해당 산업의 용어·데이터·규제를 알면 강점")
    if arch_labels:
        wants.append(f"{arch_labels[0]} 같은 구조에 대한 이해·운영 경험")
    if any(t in top_tech for t in ("Git", "GitHub", "Jira", "Confluence", "Slack", "Notion")):
        wants.append("협업 역량 — Git 기반 코드리뷰·문서화·이슈 트래킹에 익숙할 것")

    # ── (2) 공부 로드맵 (회사 실제 스택 기반 단계) ──────────────────
    roadmap: list[dict] = []

    def stage(label: str, goal: str, techs: list[str]) -> None:
        techs = [t for t in dict.fromkeys(techs) if t]  # 중복 제거·순서 유지
        if not techs:
            return
        tips = [f"{t} — {LEARN_DB[t]}" for t in techs if LEARN_DB.get(t)]
        roadmap.append({"stage": label, "goal": goal, "techs": techs, "tips": tips})

    stage("1. 언어·기본기", "주력 언어로 문법·자료구조/알고리즘 기본기를 다진다",
          cat_names("언어", 3))
    primary_cat = ROLE_PRIMARY_CAT.get(primary_role or "", "백엔드")
    role_goal = {
        "백엔드": "프레임워크로 REST API·인증·예외처리를 갖춘 서버를 직접 만든다",
        "프론트엔드": "컴포넌트·상태관리로 동작하는 SPA를 만들어 배포한다",
        "모바일": "네이티브/크로스플랫폼으로 앱을 만들어 스토어 흐름까지 경험한다",
        "AI/ML": "프레임워크로 모델을 직접 학습·평가하고 API로 서빙한다",
        "데이터": "수집→적재→가공(ETL) 파이프라인을 한 번 끝까지 만든다",
        "인프라/DevOps": "컨테이너·CI/CD로 앱을 빌드·배포·운영해 본다",
    }.get(primary_cat, "핵심 프레임워크로 동작하는 결과물을 만든다")
    stage(f"2. {primary_role or '핵심'} 핵심 스킬", role_goal, cat_names(primary_cat, 4))
    stage("3. 데이터 계층", "데이터 저장·조회를 설계하고 쿼리/인덱스를 최적화한다",
          cat_names("데이터베이스", 3) + cat_names("데이터", 2))
    infra = cat_names("인프라/DevOps", 4)
    if infra or arch_labels:
        goal = "배포·운영·확장 구조를 이해한다"
        if arch_labels:
            goal += f" (목표 구조: {arch_labels[0]})"
        stage("4. 인프라·배포·아키텍처", goal, infra)
    # 차별화 단계: 주력이 아닌 AI/ML·데이터 스택을 우대 무기로
    diff = []
    if primary_cat != "AI/ML":
        diff += cat_names("AI/ML", 3)
    if primary_cat != "데이터":
        diff += cat_names("데이터", 2)
    if "llm" in low or "rag" in low or any(t in top_tech for t in ("LangChain", "OpenAI")):
        diff = ["LangChain", "OpenAI"] + diff
    stage("5. 우대·차별화", "지원서에서 돋보일 무기 — 우대 기술을 1개라도 깊게", diff)

    # ── (3) 입사 후 업무 추론 ────────────────────────────────────────
    tasks: list[str] = []
    prefix = f"[{dom}] " if dom else ""
    for r in roles[:2]:
        base = ROLE_TASK.get(r)
        if base:
            tasks.append(prefix + base)
    extra: list[str] = []
    if any("MSA" in a for a in arch_labels):
        extra.append("마이크로서비스 분리·서비스 간 연동과 장애 격리 설계")
    if any("K8s" in a or "컨테이너" in a for a in arch_labels):
        extra.append("컨테이너 기반 배포·오토스케일링 운영")
    if any("데이터 파이프라인" in a for a in arch_labels):
        extra.append("대용량 데이터의 배치/스트리밍 처리 파이프라인 운영")
    if any("LLM" in a or "생성형" in a for a in arch_labels):
        extra.append("LLM·RAG 기반 기능 개발과 프롬프트/품질 개선")
    if any("ML 모델 서빙" in a for a in arch_labels):
        extra.append("모델 학습·평가 후 추론 서비스로 배포·모니터링")
    tasks.extend(extra[:2])
    if not tasks:
        tasks.append("채용공고 기반 — 제품 기능 개발과 운영 전반")

    return {"wants": wants, "roadmap": roadmap, "tasks": tasks[:5]}


# ─────────────────────────────────────────────────────────────────────────
# 5) 추천 기술블로그 — tech_blogs.json 의 글을 회사 스택/도메인과 매칭
# ─────────────────────────────────────────────────────────────────────────

TECH_BLOGS = ROOT / "jd-viewer" / "public" / "tech_blogs.json"

# 내부 카테고리 → 블로그 카테고리(tech_blogs.json categories) 매핑
_CAT_TO_BLOGCAT: dict[str, str] = {
    "언어": "언어",
    "백엔드": "백엔드",
    "프론트엔드": "프론트엔드",
    "모바일": "모바일",
    "데이터베이스": "데이터베이스",
    "인프라/DevOps": "인프라/클라우드",
    "AI/ML": "AI/ML",
    "데이터": "데이터",
}


def _load_blog_index() -> list[dict]:
    """블로그 글을 검색용 인덱스로 로드. 실패 시 빈 리스트(가이드는 여전히 동작)."""
    if not TECH_BLOGS.exists():
        return []
    try:
        data = json.loads(TECH_BLOGS.read_text(encoding="utf-8"))
    except Exception:
        return []
    idx: list[dict] = []
    for p in data.get("posts", []):
        tags = {str(t).lower() for t in (p.get("tags") or [])}
        tags |= {str(t).lower() for t in (p.get("tech_stack") or [])}
        idx.append({
            "company": p.get("company") or "",
            "country": p.get("country") or "",
            "title": p.get("title") or "",
            "url": p.get("url") or "",
            "cats": set(p.get("categories") or []),
            "tags": tags,
            "ts": p.get("published_ts") or 0,
        })
    return idx


def recommend_study_blogs(rec: dict, blog_idx: list[dict], limit: int = 6) -> list[dict]:
    """회사 스택/도메인과 겹치는 기술블로그 글 추천. 최신·관련도 우선, 출처 다양성 유지."""
    if not blog_idx:
        return []
    tech_terms = {t["name"].lower() for t in rec["top_tech"]}
    want_cats = {
        _CAT_TO_BLOGCAT[c] for c in rec["tech_categories"] if c in _CAT_TO_BLOGCAT
    }
    arch_labels = [a["label"] for a in rec["architecture"]]
    if any("LLM" in a or "생성형" in a for a in arch_labels):
        want_cats.add("LLM/생성형")

    scored: list[tuple[int, int, dict]] = []
    for p in blog_idx:
        tag_hits = tech_terms & p["tags"]
        cat_hits = want_cats & p["cats"]
        score = 3 * len(tag_hits) + len(cat_hits)
        if score <= 0:
            continue
        why = ", ".join(sorted(tag_hits)[:3]) or ", ".join(sorted(cat_hits)[:2])
        scored.append((score, p["ts"], {
            "title": p["title"], "url": p["url"],
            "company": p["company"], "country": p["country"], "why": why,
        }))
    scored.sort(key=lambda t: (-t[0], -t[1]))

    out: list[dict] = []
    per_company: Counter = Counter()
    for _, _, item in scored:
        if per_company[item["company"]] >= 2:  # 한 출처 최대 2개 — 다양성
            continue
        per_company[item["company"]] += 1
        out.append(item)
        if len(out) >= limit:
            break
    return out


# ─────────────────────────────────────────────────────────────────────────
# 집계
# ─────────────────────────────────────────────────────────────────────────


def build(jobs: list[dict], min_count: int) -> list[dict]:
    # 회사명 정규화 키로 묶되, 표시 이름은 최빈 원문을 쓴다.
    by_norm: dict[str, list[dict]] = defaultdict(list)
    name_votes: dict[str, Counter] = defaultdict(Counter)
    for j in jobs:
        name = (j.get("company") or "").strip()
        if not name:
            continue
        nk = _norm_company(name)
        if not nk:
            continue
        by_norm[nk].append(j)
        name_votes[nk][name] += 1

    profiles = _load_profiles()
    blog_idx = _load_blog_index()
    companies: list[dict] = []

    for nk, group in by_norm.items():
        if len(group) < min_count:
            continue
        display = name_votes[nk].most_common(1)[0][0]

        tech_counter: Counter = Counter()
        cat_counter: dict[str, Counter] = {c: Counter() for c in CATEGORIES}
        role_counter: Counter = Counter()
        sites: set[str] = set()
        titles: list[str] = []
        urls: list[dict] = []
        text_parts: list[str] = []
        hc_max: int | None = None        # 회사 사원수 (공고들 중 최댓값)
        rev_max: float | None = None     # 회사 매출액(억원)

        for j in group:
            sites.add(j.get("site") or "")
            # 규모 신호는 full_jd(비절단) 전체에서 추출 — 기업정보가 뒤쪽에 있을 수 있음
            size_text = " ".join([
                j.get("full_jd") or "", j.get("benefits") or "",
                j.get("qualifications") or "", j.get("preferences") or "",
            ])
            hc = extract_headcount(size_text)
            if hc and (hc_max is None or hc > hc_max):
                hc_max = hc
            rev = extract_revenue_eok(size_text)
            if rev and (rev_max is None or rev > rev_max):
                rev_max = rev
            if j.get("title"):
                titles.append(j["title"])
            if j.get("url"):
                urls.append({"title": j.get("title") or "", "url": j["url"], "site": j.get("site") or ""})
            roles = classify_dev_roles(
                title=j.get("title") or "",
                tech_stack=j.get("tech_stack") or [],
                extra_text=(j.get("qualifications") or "")[:500],
            )
            for r in roles:
                if r != "기타":
                    role_counter[r] += 1
            seen_in_job: set[str] = set()
            for t in j.get("tech_stack") or []:
                ct = canon_tech(t)
                if ct is None:
                    continue
                canon, cat = ct
                if canon in seen_in_job:
                    continue
                seen_in_job.add(canon)
                tech_counter[canon] += 1
                cat_counter[cat][canon] += 1
            text_parts.append(" ".join([
                j.get("title") or "", j.get("main_tasks") or "",
                j.get("qualifications") or "", j.get("preferences") or "",
                (j.get("full_jd") or "")[:1500],
            ]))

        blob = "\n".join(text_parts)
        canon_set = set(tech_counter)
        role_set = set(role_counter)
        size, alias = classify_company_size(display, hc_max, rev_max)

        domains = infer_domains(blob, top=2)
        arch = infer_architecture(canon_set, blob, role_set)

        # 카테고리별 기술 (빈도순)
        tech_categories = {}
        for c in CATEGORIES:
            items = [{"name": n, "count": cnt} for n, cnt in cat_counter[c].most_common()]
            if items:
                tech_categories[c] = items

        rec = {
            "name": display,
            "norm": nk,
            "size": size,
            "size_alias": alias,
            "posting_count": len(group),
            "sites": sorted(s for s in sites if s),
            "roles": dict(role_counter.most_common()),
            "top_tech": [{"name": n, "count": c} for n, c in tech_counter.most_common(12)],
            "tech_categories": tech_categories,
            "domains": domains,
            "architecture": arch,
            "titles": titles[:8],
            "postings": urls[:12],
        }
        # 2차 보강 병합
        prof = profiles.get(nk)
        if prof:
            rec["homepage"] = prof.get("homepage")
            rec["homepage_desc"] = prof.get("desc")
            rec["homepage_tech"] = prof.get("tech") or []
            # 홈페이지에서 추가로 잡힌 도메인이 있으면 합산
            hp_dom = prof.get("domains") or []
            if hp_dom:
                known = {d["name"] for d in rec["domains"]}
                for d in hp_dom:
                    if d not in known:
                        rec["domains"].append({"name": d, "score": 1, "evidence": ["홈페이지"]})
        rec["summary"] = _summary(rec)
        guide = infer_career_guide(rec, blob)
        guide["study_blogs"] = recommend_study_blogs(rec, blog_idx)
        rec["career_guide"] = guide
        companies.append(rec)

    companies.sort(key=lambda c: -c["posting_count"])
    return companies


def _summary(rec: dict) -> str:
    parts = []
    dom = rec["domains"][0]["name"] if rec["domains"] else None
    size = rec["size"]
    top_roles = list(rec["roles"])[:2]
    top_tech = [t["name"] for t in rec["top_tech"][:4]]
    head = rec["name"]
    if dom:
        head += f"는 {dom} 도메인의 {size}"
    else:
        head += f"는 {size}"
    if top_roles:
        head += f"으로, 주로 {' · '.join(top_roles)} 직군을 채용"
    if top_tech:
        head += f"하며 {', '.join(top_tech)} 기반으로 개발"
    head += "합니다."
    if rec["architecture"]:
        head += f" 아키텍처는 {rec['architecture'][0]['label']}로 추정됩니다."
    return head


def _load_profiles() -> dict[str, dict]:
    if not PROFILES.exists():
        return {}
    try:
        data = json.loads(PROFILES.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=2, help="최소 공고 수 (기본 2)")
    ap.add_argument("--all", action="store_true", help="공고 1건 회사도 포함(--min 1)")
    args = ap.parse_args()
    min_count = 1 if args.all else args.min

    if not INPUT.exists():
        print(f"[!] 입력 없음: {INPUT}", file=sys.stderr)
        sys.exit(1)
    jobs = json.loads(INPUT.read_text(encoding="utf-8"))
    print(f"[*] {len(jobs)}건 로드 (min={min_count})", flush=True)

    companies = build(jobs, min_count)
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_jobs": len(jobs),
        "company_count": len(companies),
        "min_posting": min_count,
        "companies": companies,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[*] {OUTPUT.relative_to(ROOT)} 작성 — {len(companies)}개 회사 "
          f"({len(json.dumps(out, ensure_ascii=False)):,} bytes)", flush=True)
    # 상위 5개 미리보기
    for c in companies[:5]:
        doms = ", ".join(d["name"] for d in c["domains"]) or "—"
        arch = ", ".join(a["label"] for a in c["architecture"]) or "—"
        print(f"    {c['posting_count']:2d}건 {c['name'][:16]:16s} | {doms} | {arch}", flush=True)


if __name__ == "__main__":
    main()
