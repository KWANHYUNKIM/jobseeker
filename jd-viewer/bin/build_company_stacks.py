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
