#!/usr/bin/env python3
"""직군별 커리어 마인드맵 (markmap markdown) 생성기.

입력: jd-viewer/public/all_jobs_enriched.json
출력: jd-viewer/public/mindmap.md  (markmap-lib 호환 markdown)

데이터가 희소한 항목은 큐레이션 지식으로 보완하고, 관측 빈도가 있는 항목은
[N건]으로 표시한다.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "catch_capture" / "dashboard"))
from classifier import classify_dev_roles, extract_competencies  # noqa: E402

INPUT = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
OUTPUT = ROOT / "jd-viewer" / "public" / "mindmap.md"

ROLES_ORDER = [
    "프론트엔드", "백엔드", "풀스택", "모바일", "AI/ML",
    "데이터", "DevOps/인프라", "펌웨어/임베디드", "보안", "게임", "QA",
]

# ---------- 연차 파싱 ----------
YEAR_RE_RANGE = re.compile(r"(\d+)\s*[~\-]\s*(\d+)\s*년")
YEAR_RE_MIN = re.compile(r"(\d+)\s*년\s*이상|경력\s*(\d+)\s*년\s*↑|(\d+)\s*년\s*↑")
YEAR_RE_PAREN = re.compile(r"경력\s*\(\s*(\d+)\s*년\s*이상\s*\)|경력\s*\(\s*(\d+)\s*~\s*(\d+)\s*년\s*\)")


def parse_years(job: dict) -> int | None:
    """대표 연차(하한)를 정수로 반환. 신입은 0. 못찾으면 None."""
    text = " ".join([
        job.get("career", "") or "",
        job.get("title", "") or "",
        (job.get("qualifications", "") or "")[:400],
    ])
    if not text.strip():
        return None
    m = YEAR_RE_RANGE.search(text)
    if m:
        return int(m.group(1))
    m = YEAR_RE_MIN.search(text)
    if m:
        for g in m.groups():
            if g:
                return int(g)
    m = YEAR_RE_PAREN.search(text)
    if m:
        for g in m.groups():
            if g:
                return int(g)
    if "신입" in text and "경력" not in text.replace("신입·경력", "").replace("신입경력", ""):
        return 0
    if "신입·경력" in text or "신입/경력" in text or "신입,경력" in text:
        return 0
    return None


def bucket_years(y: int | None) -> str | None:
    if y is None:
        return None
    if y == 0:
        return "신입(0)"
    if y <= 3:
        return "주니어(1-3)"
    if y <= 7:
        return "미드(3-7)"
    return "시니어(7+)"


# ---------- 큐레이션 베이스라인 (직군별) ----------

ROLE_PROFILE: dict[str, dict] = {
    "프론트엔드": {
        "한줄": "사용자가 직접 보는 화면을 만드는 UI/웹 개발자. 디자인·백엔드 사이의 다리.",
        "핵심스택": ["JavaScript", "TypeScript", "React", "Next.js", "Vue", "Tailwind", "CSS", "HTML"],
        "추가스택": ["Vite", "Webpack", "Redux", "Zustand", "Recoil", "React Query", "Storybook", "Jest"],
        "주요업무": [
            "UI 컴포넌트 설계·구현 (디자인 시스템 운영)",
            "상태관리, API 연동 (REST/GraphQL)",
            "성능 최적화 (코드스플리팅, Web Vitals, 렌더링)",
            "크로스브라우저/반응형/접근성(a11y) 대응",
            "프론트엔드 빌드/배포 파이프라인",
        ],
        "연차로드맵": {
            "신입(0년)": [
                "HTML / CSS / JavaScript 기본기 (DOM, 이벤트, 비동기)",
                "React **또는** Vue 1개 프레임워크 컴포넌트 작성",
                "Git, GitHub 협업 흐름 (PR/리뷰)",
                "Figma 시안 → 마크업 변환 능력",
                "포트폴리오: 토이프로젝트 2-3개 (배포까지)",
            ],
            "주니어(1-3년)": [
                "TypeScript 실전 활용 (제네릭/유틸리티 타입)",
                "상태관리 라이브러리 1개 깊게 (Redux Toolkit / Zustand / Recoil)",
                "데이터 페칭 (React Query / SWR)",
                "테스트 (Jest + React Testing Library)",
                "디자인 시스템 사용/기여",
                "기본 SEO, 접근성, 웹 성능 지표 이해",
            ],
            "미드(3-7년)": [
                "Next.js SSR/SSG/ISR 운영, 라우팅 전략",
                "성능 측정·개선 (Lighthouse, Web Vitals, 번들 분석)",
                "CI/CD (GitHub Actions, Vercel/CloudFront)",
                "모노레포 (Turborepo/Nx) 또는 마이크로프론트엔드",
                "디자인 시스템 설계·운영, 코드 리뷰 주도",
                "FE 아키텍처 의사결정 (폴더구조, 데이터 흐름)",
            ],
            "시니어(7년+)": [
                "프론트엔드 플랫폼/아키텍처 설계",
                "팀 멘토링, 기술 결정, 채용 면접",
                "BE/디자인/PM 협업 리딩, 로드맵 수립",
                "성능 SLO 정의, 관측성(에러/로그) 시스템",
                "오픈소스/기술 블로그/컨퍼런스 발표",
            ],
        },
        "가산점": [
            "오픈소스 기여 (React 생태계 라이브러리)",
            "기술 블로그·발표 (Web Vitals, 렌더링 글 등)",
            "디자인 감각·Figma 활용",
            "TOEIC/영어 문서 읽기 능력",
            "UX/접근성(a11y) 깊은 이해",
            "WebAssembly, WebGL, 애니메이션(Lottie/Framer Motion)",
            "BFF(Node.js/NestJS) 운영 경험",
        ],
        "커리어전환": [
            "→ 풀스택 (Node.js/NestJS, DB 학습)",
            "→ 모바일 (React Native, Flutter)",
            "→ DX/플랫폼 엔지니어 (사내 DX 개선)",
            "→ 디자인 엔지니어 (디자인 시스템 전문)",
            "→ 테크니컬 PM/EM (관리·전략)",
        ],
    },
    "백엔드": {
        "한줄": "비즈니스 로직·데이터·API를 책임지는 서버 개발자. 안정성·성능·확장성이 핵심.",
        "핵심스택": ["Java", "Spring Boot", "Python", "FastAPI", "Django", "Node.js", "Go", "Kotlin", "MySQL", "PostgreSQL", "Redis"],
        "추가스택": ["JPA/Hibernate", "MongoDB", "Kafka", "RabbitMQ", "ElasticSearch", "gRPC", "GraphQL", "JUnit/Pytest"],
        "주요업무": [
            "REST/gRPC/GraphQL API 설계·구현",
            "DB 모델링, 쿼리 튜닝, 트랜잭션 관리",
            "비즈니스 로직 구현, 도메인 설계",
            "대규모 트래픽 처리 (캐싱, 큐, 비동기)",
            "장애 대응, 로그·모니터링, 보안",
        ],
        "연차로드맵": {
            "신입(0년)": [
                "한 언어(Java/Python/Node) 문법·표준 라이브러리",
                "Spring Boot 또는 Django/FastAPI 1개 깊게",
                "SQL (JOIN, 인덱스 기본), 1개 RDB 운용",
                "HTTP/REST, 인증 기초 (JWT/세션)",
                "Git, 테스트 기본 (JUnit/Pytest)",
            ],
            "주니어(1-3년)": [
                "ORM 깊게 (JPA/SQLAlchemy) — N+1, 지연로딩",
                "DB 인덱스·쿼리 플랜 분석",
                "캐싱 (Redis) — 무효화 전략",
                "비동기/큐 (Kafka, RabbitMQ, Celery)",
                "Docker, AWS 기본 (EC2, RDS, S3)",
                "도메인 분리·계층 구조 (Layered/Hexagonal)",
            ],
            "미드(3-7년)": [
                "MSA / 분산 시스템 (사가, 멱등성, 보상 트랜잭션)",
                "성능 튜닝 (DB, GC, 동시성)",
                "관측성 (Datadog/Prometheus, 분산 트레이싱)",
                "보안 (OWASP, 인증/인가, Secret 관리)",
                "코드 리뷰, 설계 문서, 멘토링",
            ],
            "시니어(7년+)": [
                "전사 아키텍처, 도메인 전략 수립",
                "장애 후처리 (포스트모템 문화)",
                "기술 부채/마이그레이션 리딩",
                "팀 빌딩, 채용, 평가",
                "비용 최적화 (인프라 ROI)",
            ],
        },
        "가산점": [
            "대규모 트래픽 운영 경험 (RPS/일사용자 수치)",
            "오픈소스 기여, 기술 블로그",
            "DB 내부 동작·OS 이해 (CS 기본기)",
            "TDD/클린아키텍처 실전 적용",
            "k8s, Terraform 등 인프라 운영",
            "보안 자격 (CISSP/CISA — 가산점 채용공고에 종종 등장)",
            "AI/LLM API 연동 경험 (RAG, 임베딩)",
        ],
        "커리어전환": [
            "→ DevOps/SRE (인프라·자동화 강화)",
            "→ 풀스택 (FE 학습)",
            "→ 데이터 엔지니어 (Spark/Airflow)",
            "→ 솔루션/플랫폼 아키텍트",
            "→ 테크리드/EM",
        ],
    },
    "풀스택": {
        "한줄": "FE+BE를 함께 다루는 개발자. 작은 팀/스타트업에서 가장 빠르게 가치 전달.",
        "핵심스택": ["TypeScript", "React", "Next.js", "Node.js", "Python", "FastAPI", "PostgreSQL", "Prisma", "Docker"],
        "추가스택": ["NestJS", "tRPC", "GraphQL", "Vercel", "AWS Lambda", "Supabase"],
        "주요업무": [
            "기획·디자인 → 화면·API·DB까지 한 번에 구현",
            "프로토타입/MVP 빠른 출시",
            "스타트업 초기 인프라 세팅 (배포, 인증, 결제)",
            "작은 팀에서 의사결정·운영",
        ],
        "연차로드맵": {
            "신입(0년)": ["FE 1개 (React) + BE 1개 (Node/FastAPI) 토이 + 배포"],
            "주니어(1-3년)": ["TypeScript 전구간, DB 모델링, 인증/결제, Docker"],
            "미드(3-7년)": ["SSR/엣지(Vercel/Cloudflare), 옵저버빌리티, 비용·확장 전략"],
            "시니어(7년+)": ["스타트업 CTO 트랙 — 채용·아키텍처·기술전략"],
        },
        "가산점": [
            "MVP 출시 경험 (실제 사용자/매출 수치)",
            "결제(Stripe/Toss) 통합 경험",
            "프로덕트 사고 (PM 협업)",
            "Side project / 오픈소스",
        ],
        "커리어전환": [
            "→ 스타트업 창업/CTO",
            "→ 전문 FE/BE로 깊이 파기",
            "→ 솔루션 엔지니어/DevRel",
        ],
    },
    "모바일": {
        "한줄": "iOS/Android 네이티브 또는 크로스플랫폼으로 모바일 앱을 만드는 개발자.",
        "핵심스택": ["Swift", "Kotlin", "SwiftUI", "Jetpack Compose", "Flutter", "React Native"],
        "추가스택": ["Combine", "RxSwift", "Coroutines", "Hilt", "Realm", "Firebase", "Fastlane"],
        "주요업무": [
            "네이티브 UI 구현 (SwiftUI / Compose)",
            "API 연동, 로컬 캐시, 오프라인 대응",
            "푸시·딥링크·인앱결제 통합",
            "앱 스토어 배포·심사 대응",
            "퍼포먼스/메모리 프로파일링",
        ],
        "연차로드맵": {
            "신입(0년)": [
                "Swift 또는 Kotlin 한 언어 깊게",
                "SwiftUI/Compose 또는 RN/Flutter 한 진영",
                "앱스토어/플레이스토어 1회 배포 경험",
            ],
            "주니어(1-3년)": [
                "MVVM/Clean Architecture",
                "비동기 (Combine/Coroutines/RxSwift)",
                "DI, 테스트, CI (Fastlane)",
                "Firebase/Crashlytics, 푸시(FCM/APNs)",
            ],
            "미드(3-7년)": [
                "모듈화 (멀티모듈/SPM)",
                "성능·메모리·배터리 최적화",
                "결제/심사 정책 변화 대응",
                "모바일 인프라 (배포, A/B, Remote Config)",
            ],
            "시니어(7년+)": [
                "모바일 플랫폼/아키텍처 결정",
                "iOS·Android 양쪽 리딩, 팀 빌딩",
                "장기 호환성·OS 정책 대응",
            ],
        },
        "가산점": [
            "앱스토어 인기 앱 운영/기여 경험",
            "WWDC/Google I/O 신기능 빠른 적용",
            "오픈소스(Swift Package, Compose 라이브러리)",
            "네이티브 ↔ 크로스플랫폼 양쪽 경험",
        ],
        "커리어전환": [
            "→ 풀스택 (BFF/서버 학습)",
            "→ AR/VR / 게임 클라이언트",
            "→ 모바일 인프라/플랫폼 엔지니어",
        ],
    },
    "AI/ML": {
        "한줄": "데이터/모델/추론 서빙을 다루는 개발자. 최근 LLM·생성형 AI로 영역 폭발 중.",
        "핵심스택": ["Python", "PyTorch", "TensorFlow", "HuggingFace", "LangChain", "OpenAI", "FastAPI", "NumPy", "Pandas"],
        "추가스택": ["MLflow", "Weights & Biases", "Ray", "Triton", "vLLM", "Pinecone/Weaviate(벡터DB)", "ONNX"],
        "주요업무": [
            "모델 학습·평가·튜닝 (CV/NLP/추천)",
            "LLM 활용 — 프롬프트/RAG/Fine-tuning",
            "데이터 파이프라인 (전처리, 라벨링)",
            "모델 서빙 (FastAPI/Triton/vLLM)",
            "MLOps — 실험 추적, 배포, 모니터링",
        ],
        "연차로드맵": {
            "신입(0년)": [
                "Python, NumPy/Pandas, Scikit-learn",
                "선형대수·통계·확률 기본",
                "PyTorch **또는** TensorFlow 1개",
                "Kaggle/논문 재현 1-2건",
            ],
            "주니어(1-3년)": [
                "딥러닝 구조 이해 (CNN/RNN/Transformer)",
                "HuggingFace Transformers 실전",
                "데이터 파이프라인 (Airflow/Prefect)",
                "FastAPI로 모델 서빙",
                "Docker, GPU 사용 (CUDA 기본)",
            ],
            "미드(3-7년)": [
                "분산 학습 (DDP, DeepSpeed)",
                "MLOps (MLflow, model registry, CI/CD)",
                "벡터DB·RAG·LLM 파이프라인",
                "추론 최적화 (양자화, vLLM, Triton)",
                "비용·지연·품질 트레이드오프 결정",
            ],
            "시니어(7년+)": [
                "AI 플랫폼 아키텍처, R&D 로드맵",
                "팀 빌딩, 논문/특허, 외부 발표",
                "비즈니스-AI 임팩트 정의",
            ],
        },
        "가산점": [
            "논문 publication (NeurIPS/ICML/ACL/CVPR)",
            "Kaggle 메달",
            "오픈소스 LLM/모델 공개 (HuggingFace)",
            "수학·통계 백그라운드",
            "도메인 전문성 (의료/금융/제조 등)",
            "MLOps 운영 경험 (모니터링·드리프트 탐지)",
        ],
        "커리어전환": [
            "→ 백엔드 (AI 서빙 전문)",
            "→ 데이터 엔지니어",
            "→ AI Product / Applied Research",
            "→ ML 인프라 (GPU·분산)",
        ],
    },
    "데이터": {
        "한줄": "데이터 인프라·파이프라인·분석을 책임. AI/ML과 BE 사이.",
        "핵심스택": ["Python", "SQL", "Spark", "Airflow", "Kafka", "dbt", "Snowflake", "BigQuery"],
        "추가스택": ["Flink", "Iceberg", "Delta Lake", "Trino", "Looker", "Tableau"],
        "주요업무": [
            "ETL/ELT 파이프라인 설계·운영 (Airflow/dbt)",
            "데이터 웨어하우스/레이크 모델링",
            "스트리밍 처리 (Kafka/Flink)",
            "BI 대시보드, 메트릭 정의",
            "데이터 품질·거버넌스",
        ],
        "연차로드맵": {
            "신입(0년)": ["SQL 깊게, Python, Pandas, 1개 ETL 토이"],
            "주니어(1-3년)": ["Spark, Airflow, 데이터 모델링(스타스키마), Docker"],
            "미드(3-7년)": ["스트리밍(Kafka/Flink), 비용 최적화, 거버넌스, dbt 운영"],
            "시니어(7년+)": ["데이터 플랫폼 아키텍처, 조직·문화 (데이터 메시)"],
        },
        "가산점": [
            "대규모 데이터(TB/PB) 운영 경험",
            "비용 최적화 (Snowflake/BQ) 사례",
            "데이터 메시/계약(Data Contract) 도입",
            "오픈소스 기여 (Airflow/Spark/dbt)",
        ],
        "커리어전환": [
            "→ AI/ML 엔지니어",
            "→ 백엔드 (분산·DB 전문)",
            "→ 분석가/BI → PM",
        ],
    },
    "DevOps/인프라": {
        "한줄": "서비스가 안정적·빠르게 굴러가게 만드는 사람. 자동화·관측·신뢰성.",
        "핵심스택": ["Linux", "Docker", "Kubernetes", "Terraform", "Ansible", "AWS", "GCP", "Helm"],
        "추가스택": ["ArgoCD", "Prometheus", "Grafana", "Datadog", "Vault", "Istio", "GitHub Actions/Jenkins"],
        "주요업무": [
            "CI/CD 파이프라인 설계·운영",
            "쿠버네티스 클러스터 운영 (멀티 환경)",
            "IaC (Terraform) — 인프라 코드화",
            "모니터링·알람·온콜 대응",
            "보안·시크릿·네트워크",
        ],
        "연차로드맵": {
            "신입(0년)": [
                "Linux 기본 (네트워크/프로세스/파일시스템)",
                "Docker, docker-compose",
                "AWS 핵심 (EC2, VPC, S3, IAM)",
                "Shell 스크립트, 기본 CI (GitHub Actions)",
            ],
            "주니어(1-3년)": [
                "Kubernetes 기본 (Deployment, Service, Ingress)",
                "Helm, Kustomize",
                "Terraform 모듈 작성",
                "Prometheus/Grafana로 메트릭",
            ],
            "미드(3-7년)": [
                "멀티 클러스터, GitOps (ArgoCD/Flux)",
                "분산 트레이싱 (OpenTelemetry)",
                "비용 최적화 (Spot/Karpenter)",
                "보안 (네트워크 정책, Vault, SBOM)",
                "온콜 문화·런북·SLO/SLI",
            ],
            "시니어(7년+)": [
                "전사 플랫폼 엔지니어링 (Internal Dev Platform)",
                "장애 후처리·SRE 문화 정착",
                "재해복구·BCP",
            ],
        },
        "가산점": [
            "AWS/GCP/Azure 자격 (SA, DevOps Pro)",
            "CKA / CKAD (쿠버네티스 자격)",
            "오픈소스 (Helm chart, K8s operator)",
            "보안 자격 (CISSP)",
            "대규모 마이그레이션 경험 (온프렘→클라우드)",
        ],
        "커리어전환": [
            "→ 백엔드 (플랫폼 측면)",
            "→ 보안 엔지니어",
            "→ 솔루션 아키텍트",
            "→ EM/플랫폼팀 리드",
        ],
    },
    "펌웨어/임베디드": {
        "한줄": "하드웨어와 가장 가까운 개발자. 자원·실시간성·신뢰성 제약 큼.",
        "핵심스택": ["C", "C++", "Rust", "Assembly", "RTOS (FreeRTOS/Zephyr)", "Linux Kernel"],
        "추가스택": ["ARM Cortex-M", "STM32/ESP32", "FPGA/Verilog", "Yocto", "I2C/SPI/UART", "CAN/LIN"],
        "주요업무": [
            "MCU/SoC 펌웨어 개발 (베어메탈/RTOS)",
            "디바이스 드라이버, 커널 모듈",
            "통신 프로토콜 구현 (CAN, BLE, Wi-Fi)",
            "전력 관리, 메모리 최적화",
            "HW 팀과의 디버깅 (오실로스코프, 로직 분석기)",
        ],
        "연차로드맵": {
            "신입(0년)": [
                "C 깊게 (포인터, 메모리, 비트 연산)",
                "MCU 보드 1개 (STM32/Arduino) 실습",
                "디지털 회로·전자공학 기본",
                "Git, Make/CMake",
            ],
            "주니어(1-3년)": [
                "RTOS (FreeRTOS) 태스크/세마포어",
                "I2C/SPI/UART, 인터럽트 처리",
                "C++ 임베디드 패턴",
                "디바이스 트리·리눅스 드라이버 입문",
            ],
            "미드(3-7년)": [
                "리얼타임 제약 분석, 최적화",
                "Yocto/Buildroot 커스텀 리눅스",
                "Rust for embedded 또는 Zephyr",
                "양산 대응 (수율, 캘리브레이션)",
            ],
            "시니어(7년+)": [
                "SoC 설계 협업, 보드 브링업 리딩",
                "안전·표준 (ISO 26262, IEC 61508)",
                "팀 빌딩, 양산 전체 리딩",
            ],
        },
        "가산점": [
            "FPGA (Verilog/VHDL)",
            "기능안전 자격 (FuSa, ISO 26262 ASIL)",
            "오픈소스 (Zephyr, Linux 커널) 기여",
            "전기/전자/통신 학사 이상",
            "양산 경험 (대량 제조)",
        ],
        "커리어전환": [
            "→ 시스템/SW 아키텍트",
            "→ HW-SW 코디자인",
            "→ 자동차 SW (AUTOSAR)",
            "→ 로봇·드론 SW",
        ],
    },
    "보안": {
        "한줄": "공격자의 관점으로 시스템을 지키는 개발자. 컴플라이언스·사고 대응 포함.",
        "핵심스택": ["Linux", "Python", "Burp Suite", "Wireshark", "Metasploit", "Nmap", "SIEM", "OWASP Top 10"],
        "추가스택": ["IDS/IPS", "WAF", "SAST/DAST", "Vault", "OAuth/OIDC", "암호학 기본"],
        "주요업무": [
            "취약점 점검 (모의해킹, SAST/DAST)",
            "보안 모니터링 (SIEM, EDR)",
            "사고 대응 (Forensic, IR)",
            "보안 아키텍처 리뷰",
            "컴플라이언스 (ISMS-P, ISO 27001)",
        ],
        "연차로드맵": {
            "신입(0년)": [
                "Linux/네트워크 기본 (TCP/IP)",
                "Python, Bash 자동화",
                "OWASP Top 10",
                "CTF 워게임 (드림핵, HackTheBox)",
            ],
            "주니어(1-3년)": [
                "Burp/ZAP로 웹 취약점 분석",
                "SAST/DAST 도구 운영",
                "SIEM (Splunk/Elastic) 룰 작성",
                "암호학 기본 (TLS, 해시, 서명)",
            ],
            "미드(3-7년)": [
                "보안 아키텍처 리뷰",
                "사고 대응 시나리오·런북",
                "클라우드 보안 (AWS IAM, GuardDuty)",
                "Zero Trust, BeyondCorp",
                "컴플라이언스 대응 리딩",
            ],
            "시니어(7년+)": [
                "CISO 트랙, 보안 전략",
                "외부 감사·인증 대응",
                "팀 빌딩, 채용",
            ],
        },
        "가산점": [
            "보안 자격 (CISSP, CISA, OSCP)",
            "CTF 입상",
            "버그바운티 (HackerOne) 실적",
            "보안 컨퍼런스 발표 (CODE BLUE, POC)",
            "리버싱 / 악성코드 분석 경험",
        ],
        "커리어전환": [
            "→ DevSecOps",
            "→ 보안 컨설팅",
            "→ CISO/거버넌스",
            "→ 보안 제품 개발 (EDR/WAF)",
        ],
    },
    "게임": {
        "한줄": "게임 클라이언트/서버를 만드는 개발자. 그래픽·최적화·동시성이 핵심.",
        "핵심스택": ["C++", "C#", "Unity", "Unreal", "DirectX/OpenGL/Vulkan", "Lua"],
        "추가스택": ["HLSL/GLSL", "Photon", "Mirror", "PlayFab", "Steam SDK", "Houdini/Maya 연동"],
        "주요업무": [
            "게임 클라이언트 (Unity/Unreal)",
            "게임 서버 (대규모 동시 접속, MMO)",
            "그래픽스/셰이더 프로그래밍",
            "AI/물리/애니메이션 시스템",
            "최적화 (메모리, 드로우콜, GC)",
        ],
        "연차로드맵": {
            "신입(0년)": ["C++ 또는 C#, Unity/Unreal 1개로 토이게임 1-2개"],
            "주니어(1-3년)": ["디자인 패턴(ECS), 멀티스레딩, 네트워킹 기본, 셰이더 입문"],
            "미드(3-7년)": ["대규모 동접 서버, 그래픽스 파이프라인, 빌드/배포(원격 빌드팜)"],
            "시니어(7년+)": ["게임 엔진 코어/리드, R&D, 차세대 플랫폼"],
        },
        "가산점": [
            "출시 게임 크레딧 (Shipped Title)",
            "그래픽스 깊은 지식 (RTX, PBR)",
            "오픈소스 엔진 기여 (Godot 등)",
            "게임잼 입상",
            "수학·물리 학위 (그래픽스 R&D)",
        ],
        "커리어전환": [
            "→ AR/VR / XR",
            "→ 그래픽스 R&D (영화/시뮬레이션)",
            "→ 일반 클라이언트 (모바일/데스크톱 앱)",
            "→ 게임 PD/디렉터",
        ],
    },
    "QA": {
        "한줄": "품질을 책임지는 엔지니어. 자동화·테스트 전략·릴리즈 게이트.",
        "핵심스택": ["Selenium", "Cypress", "Playwright", "Appium", "JUnit/Pytest", "JMeter", "Postman/Newman"],
        "추가스택": ["TestRail", "Allure", "BrowserStack", "k6/Locust", "CI 통합"],
        "주요업무": [
            "테스트 자동화 (E2E, API)",
            "테스트 계획·케이스·전략 수립",
            "회귀 테스트, 릴리즈 게이트",
            "성능/부하 테스트",
            "버그 트래킹, 품질 메트릭",
        ],
        "연차로드맵": {
            "신입(0년)": ["수동 테스트 케이스 작성, 1개 자동화 도구(Selenium/Cypress)"],
            "주니어(1-3년)": ["테스트 프레임워크 구축, CI 통합, API 테스트(Postman)"],
            "미드(3-7년)": ["성능/부하 테스트, 카오스 엔지니어링 입문, 테스트 전략"],
            "시니어(7년+)": ["QA 조직 운영, 품질 KPI, 셔트레프트 문화"],
        },
        "가산점": [
            "ISTQB 자격",
            "성능/보안 테스트 경험",
            "오픈소스 테스트 프레임워크 기여",
            "프로그래밍 능력 (테스트 인 코드)",
        ],
        "커리어전환": [
            "→ SDET (개발자형 QA)",
            "→ DevOps (CI/CD)",
            "→ 백엔드 (도메인 전문)",
            "→ EM/품질 리드",
        ],
    },
}


def md_escape(s: str) -> str:
    return s.replace("\n", " ").strip()


def collect_observed(jobs: list[dict]) -> dict[str, dict]:
    """직군별로 관측 통계를 모은다."""
    by_role: dict[str, dict] = {r: {
        "count": 0,
        "tech": Counter(),
        "comps": Counter(),
        "co_roles": Counter(),
        "by_bucket": defaultdict(Counter),  # bucket → tech Counter
        "bucket_count": Counter(),
    } for r in ROLES_ORDER}

    for j in jobs:
        # 분류 재실행 (enriched JSON에는 roles 필드가 없음)
        roles = classify_dev_roles(
            title=j.get("title") or "",
            tech_tags=[],
            tech_stack=j.get("tech_stack") or [],
            extra_text=(j.get("qualifications") or "")[:500],
        )
        if not roles or roles == ["기타"]:
            continue
        years = parse_years(j)
        bucket = bucket_years(years)
        comps = extract_competencies(" ".join([
            j.get("qualifications") or "",
            j.get("preferences") or "",
            j.get("main_tasks") or "",
        ]))
        for r in roles:
            if r not in by_role:
                continue
            by_role[r]["count"] += 1
            for t in j.get("tech_stack") or []:
                by_role[r]["tech"][t] += 1
            for c in comps:
                by_role[r]["comps"][c] += 1
            for r2 in roles:
                if r2 != r and r2 in by_role:
                    by_role[r]["co_roles"][r2] += 1
            if bucket:
                by_role[r]["bucket_count"][bucket] += 1
                for t in j.get("tech_stack") or []:
                    by_role[r]["by_bucket"][bucket][t] += 1
    return by_role


def render_md(observed: dict[str, dict], total_jobs: int) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []
    lines.append("---")
    lines.append("markmap:")
    lines.append("  colorFreezeLevel: 2")
    lines.append("  maxWidth: 380")
    lines.append("  initialExpandLevel: 2")
    lines.append("---")
    lines.append("")
    lines.append(f"# 개발자 직군 커리어 마인드맵")
    lines.append("")
    lines.append(f"- 데이터: 총 **{total_jobs}건** 잡공고 · 생성 {now}")
    lines.append("- [N건]은 실제 채용공고 관측 빈도, 그 외는 업계 표준 큐레이션")
    lines.append("- 공부·커리어 전환 가이드 — 각 직군의 가지를 클릭해 펼쳐보세요")
    lines.append("")

    for role in ROLES_ORDER:
        prof = ROLE_PROFILE.get(role, {})
        obs = observed.get(role, {})
        n = obs.get("count", 0)
        lines.append(f"## {role} 개발자  ({n}건 관측)")
        if prof.get("한줄"):
            lines.append(f"- _{prof['한줄']}_")

        # 핵심 기술 스택
        lines.append("- 핵심 기술 스택")
        seen = set()
        core = prof.get("핵심스택", [])
        obs_tech = obs.get("tech", Counter())
        for t in core:
            cnt = obs_tech.get(t, 0)
            tag = f" [{cnt}건]" if cnt else ""
            lines.append(f"  - **{t}**{tag}")
            seen.add(t.lower())
        # 관측 상위 중 핵심에 없는 것 보완
        extras_from_obs = [t for t, _ in obs_tech.most_common(8) if t.lower() not in seen][:6]
        for t in extras_from_obs:
            lines.append(f"  - {t} [{obs_tech[t]}건]")
            seen.add(t.lower())
        # 큐레이션 추가 스택
        addl = prof.get("추가스택", [])
        if addl:
            lines.append("  - _추가/심화 스택_")
            for t in addl:
                cnt = obs_tech.get(t, 0)
                tag = f" [{cnt}건]" if cnt else ""
                lines.append(f"    - {t}{tag}")

        # 주요 업무
        lines.append("- 주요 업무")
        for t in prof.get("주요업무", []):
            lines.append(f"  - {md_escape(t)}")

        # 연차별 로드맵
        roadmap = prof.get("연차로드맵", {})
        if roadmap:
            lines.append("- 연차별 로드맵")
            bucket_count = obs.get("bucket_count", Counter())
            for stage, items in roadmap.items():
                # 관측 매칭 (이름 prefix 매칭)
                key = stage.split("(")[0].strip()
                # 신입→신입, 주니어→주니어... 매칭
                cnt = 0
                for b, v in bucket_count.items():
                    if b.startswith(key):
                        cnt += v
                tag = f"  ({cnt}건 관측)" if cnt else ""
                lines.append(f"  - **{stage}**{tag}")
                for it in items:
                    lines.append(f"    - {md_escape(it)}")

        # 가산점·우대사항
        lines.append("- 가산점 / 우대사항")
        comps = obs.get("comps", Counter())
        if comps:
            lines.append("  - _관측 기반_")
            for c, v in comps.most_common(6):
                lines.append(f"    - {c} [{v}건]")
        lines.append("  - _업계 표준_")
        for t in prof.get("가산점", []):
            lines.append(f"    - {md_escape(t)}")

        # 커리어 전환
        lines.append("- 커리어 전환 경로")
        co = obs.get("co_roles", Counter())
        if co:
            lines.append("  - _데이터상 인접 직군 (공고 동시 매칭)_")
            for r2, v in co.most_common(4):
                lines.append(f"    - {r2} [{v}건]")
        lines.append("  - _표준 전환 경로_")
        for t in prof.get("커리어전환", []):
            lines.append(f"    - {md_escape(t)}")

        lines.append("")  # role 사이 공백

    # 공통: 모든 직군에 통하는 가산점
    lines.append("## 모든 직군 공통 — 가산점·공부법")
    lines.append("- 협업·커뮤니케이션 — 어떤 직군이든 1순위")
    lines.append("  - 기술 글쓰기 (PR 설명, 설계 문서)")
    lines.append("  - 코드 리뷰 주고받기 — 이유까지 설명")
    lines.append("- 포트폴리오·아웃풋")
    lines.append("  - GitHub 활동 (꾸준한 커밋 < 의미있는 프로젝트)")
    lines.append("  - 기술 블로그 (배운 것 회고 + 깊은 글 1-2편)")
    lines.append("  - 오픈소스 PR 1-2건 (Good first issue 부터)")
    lines.append("- CS 기본기 — 시니어로 갈수록 결정적")
    lines.append("  - 자료구조·알고리즘, 운영체제, 네트워크, DB 내부")
    lines.append("- 영어")
    lines.append("  - 문서 읽기 (공식 docs, RFC)")
    lines.append("  - 외국계/원격 채용 시 결정적")
    lines.append("- 사이드프로젝트 / 토이 → MVP 출시")
    lines.append("  - '동작하는 무언가'를 만들어 사용자/매출을 가져본 경험")
    lines.append("- 커뮤니티")
    lines.append("  - 모임 발표, 컨퍼런스 라이트닝 토크")
    lines.append("  - 멘토링 받기/하기")
    lines.append("- 자격증 (가산점 채용 일부)")
    lines.append("  - 클라우드 (AWS SAA/SAP, GCP PCA)")
    lines.append("  - 정보처리기사 (공공/대기업 가산)")
    lines.append("  - 보안 (CISSP, OSCP)")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    if not INPUT.exists():
        print(f"[!] 입력 파일 없음: {INPUT}", file=sys.stderr)
        sys.exit(1)
    jobs = json.loads(INPUT.read_text(encoding="utf-8"))
    print(f"[*] 입력 {len(jobs)}건 로드", flush=True)
    observed = collect_observed(jobs)
    for r in ROLES_ORDER:
        print(f"    {r}: {observed[r]['count']}건, top tech: "
              f"{[t for t, _ in observed[r]['tech'].most_common(5)]}",
              flush=True)
    md = render_md(observed, total_jobs=len(jobs))
    OUTPUT.write_text(md, encoding="utf-8")
    print(f"[*] {OUTPUT.relative_to(ROOT)} 작성 ({len(md):,} bytes)", flush=True)


if __name__ == "__main__":
    main()
