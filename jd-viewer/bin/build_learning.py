#!/usr/bin/env python3
"""기술별 추천 학습 영상 수집기 (YouTube).

입력: jd-viewer/public/company_stacks.json  (선택 가능한 기술 목록)
출력: jd-viewer/public/learning_resources.json

각 기술 이름으로 "<기술> 강의" 를 YouTube 에서 검색해(초기 HTML 의 ytInitialData
파싱), 관련도 순 상위 영상을 모아 기술→영상목록 맵을 만든다. "이 기술을 어떻게
공부해야 하는지"를 정적 로드맵 대신 실제 학습 영상으로 추천하기 위한 자료.

- YouTube 검색 결과 HTML 에 ytInitialData(JSON)가 그대로 박혀 있어, JS 실행 없이
  서버사이드 GET 만으로 영상 메타(제목·채널·조회수·길이·게시일)를 얻는다.
- sp=EgIQAQ%3D%3D 필터로 '동영상' 타입만(채널·재생목록 제외).
- 너무 짧은 쇼츠(기본 60초 미만)는 제외 — 학습 콘텐츠로 부적합.
- 재실행 비용을 줄이려 기술별 원본 결과를 .learning_cache.json 에 캐시한다.
  --refresh 로 캐시 무시.

사용법:
    python3 jd-viewer/bin/build_learning.py            # 기본(의미있는 기술만)
    python3 jd-viewer/bin/build_learning.py --min 1    # 더 많은 기술 포함
    python3 jd-viewer/bin/build_learning.py --limit 10 # 앞 10개 기술만(테스트)
    python3 jd-viewer/bin/build_learning.py --refresh  # 캐시 무시하고 재수집
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent.parent
STACKS = ROOT / "jd-viewer" / "public" / "company_stacks.json"
OUTPUT = ROOT / "jd-viewer" / "public" / "learning_resources.json"
CACHE = Path(__file__).resolve().parent / ".learning_cache.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
YT_SEARCH = "https://www.youtube.com/results"
YT_VIDEO_FILTER = "EgIQAQ%3D%3D"   # 동영상 타입만
WATCH_URL = "https://www.youtube.com/watch?v={vid}"
THUMB_URL = "https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
PER_TECH = 8           # 기술당 최대 추천 영상 수
MIN_SECONDS = 60       # 이보다 짧은 영상(쇼츠)은 제외
MIN_VIEWS = 1000       # 관련도 없는데 조회수도 낮은 영상은 노이즈로 제외
MAX_PER_CHANNEL = 2    # 한 채널이 추천을 독식하지 않게 제한(다양성)
FETCH_DELAY = 0.7      # 요청 간 간격(초)

# 검색 노이즈가 크거나 회사 고유 표현이라 학습 영상 추천이 무의미한 이름
SKIP = {
    "API 개발", "AI/인공지능", "기타", "오픈소스", "협업", "형상관리",
}

# 학습 콘텐츠가 아닌 제목 신호 — 포함 시 제외(쇼츠는 길이로 이미 걸러짐)
NOISE = (
    "브이로그", "vlog", "생방송", "라이브 다시보기", "다시보기", "노래", "뮤직",
    "music video", "mv", "asmr", "광고", "이벤트 안내",
)

# 영어 표기로는 한글 제목과 매칭이 안 되는 기술의 음차/별칭 — 관련도 판정용.
# (정규화: 소문자+영숫자+한글). 없는 기술은 영어 토큰 자체로 매칭한다.
ALIASES: dict[str, list[str]] = {
    "Python": ["파이썬"], "Java": ["자바"], "JavaScript": ["자바스크립트"],
    "TypeScript": ["타입스크립트"], "Kotlin": ["코틀린"], "Go": ["고랭", "golang"],
    "Rust": ["러스트"], "Swift": ["스위프트"], "Ruby": ["루비"], "Scala": ["스칼라"],
    "React": ["리액트"], "Vue": ["뷰"], "Angular": ["앵귤러"], "Svelte": ["스벨트"],
    "Next.js": ["넥스트", "nextjs"], "Node.js": ["노드", "nodejs"],
    "Spring": ["스프링"], "Spring Boot": ["스프링부트", "springboot"],
    "Django": ["장고"], "Flask": ["플라스크"], "FastAPI": ["패스트api"],
    "Docker": ["도커"], "Kubernetes": ["쿠버네티스", "쿠버", "k8s"],
    "Kafka": ["카프카"], "Redis": ["레디스"], "MySQL": ["마이에스큐엘"],
    "PostgreSQL": ["포스트그레", "postgres", "포스트그레스큐엘"],
    "MongoDB": ["몽고", "몽고디비"], "GraphQL": ["그래프큐엘"],
    "Terraform": ["테라폼"], "Ansible": ["앤서블"], "Jenkins": ["젠킨스"],
    "Flutter": ["플러터"], "Android": ["안드로이드"], "iOS": ["아이오에스"],
    "PyTorch": ["파이토치"], "TensorFlow": ["텐서플로", "텐서플로우"],
    "Pandas": ["판다스"], "NumPy": ["넘파이"], "Spark": ["스파크"],
    "Airflow": ["에어플로우", "에어플로"], "Linux": ["리눅스"], "AWS": ["아마존웹서비스"],
}


def load_techs(min_count: int) -> list[dict]:
    """company_stacks.json 에서 (이름, 카테고리, 회사수) 목록 추출.

    실제 카테고리(≠기타)는 회사수와 무관히 포함하고, '기타'는 회사수가
    min_count 이상인 것만 — 노이즈 태그가 대부분이라 인기있는 것만 추린다.
    """
    data = json.loads(STACKS.read_text(encoding="utf-8"))
    agg: dict[str, dict] = {}
    for c in data["companies"]:
        for cat, arr in c.get("tech_categories", {}).items():
            for t in arr:
                name = t["name"]
                e = agg.setdefault(name, {"name": name, "category": cat, "companies": 0})
                e["companies"] += 1
    out = []
    for e in agg.values():
        if e["name"] in SKIP:
            continue
        if e["category"] != "기타" or e["companies"] >= min_count:
            out.append(e)
    out.sort(key=lambda e: -e["companies"])
    return out


def parse_duration(s: str) -> int:
    """'6:12:52' / '4:16' → 초. 빈/비정상값은 0."""
    if not s:
        return 0
    parts = s.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    sec = 0
    for n in nums:
        sec = sec * 60 + n
    return sec


def parse_views(s: str) -> int:
    """'조회수 9,846회' / 'No views' → 정수."""
    digits = re.sub(r"[^\d]", "", s or "")
    return int(digits) if digits else 0


def norm(s: str) -> str:
    """매칭용 정규화: 소문자 + 영숫자/한글만."""
    return re.sub(r"[^a-z0-9가-힣]", "", (s or "").lower())


# 제목으로 학습 단계 추정 — 데이터 자체가 입문→핵심→실전 경로가 되도록.
STAGE_ORDER = {"입문": 0, "핵심": 1, "실전": 2}
_INTRO = ("입문", "기초", "기본", "처음", "시작", "왜 ", "0강", "1강", "비기너",
          "beginner", "쉽게", "한방", "한번에", "개념", "맛보기", "쌩초보", "초보")
_ADV = ("실전", "심화", "고급", "프로젝트", "실무", "배포", "최적화", "클론", "만들기",
        "만들어", "advanced", "deep dive", "마스터", "완벽", "아키텍처", "실습")


def classify_stage(title: str) -> str:
    """입문 / 핵심 / 실전 중 하나. 실전 신호 우선, 다음 입문, 나머지는 핵심."""
    t = title.lower()
    if any(k in t for k in _ADV):
        return "실전"
    if any(k in t for k in _INTRO):
        return "입문"
    return "핵심"


def relevance(tech: str, title: str, channel: str) -> int:
    """기술/별칭이 제목·채널에 나타나는 정도. 제목 매칭을 더 높게 본다."""
    terms = [tech] + ALIASES.get(tech, [])
    nterms = [norm(t) for t in terms if norm(t)]
    nt, nc = norm(title), norm(channel)
    if any(t in nt for t in nterms):
        return 2
    if any(t in nc for t in nterms):
        return 1
    return 0


def fetch_videos(client: httpx.Client, query: str) -> list[dict]:
    """YouTube 검색(query 그대로) → videoRenderer 목록(슬림 dict). 실패 시 []."""
    try:
        r = client.get(
            YT_SEARCH,
            params={"search_query": query, "sp": YT_VIDEO_FILTER},
            timeout=20,
            follow_redirects=True,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"    [!] '{query}': 요청 실패 {e}", file=sys.stderr)
        return []
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", r.text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []

    found: list[dict] = []
    seen: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            vr = o.get("videoRenderer")
            if isinstance(vr, dict) and vr.get("videoId") not in seen:
                vid = vr.get("videoId", "")
                seen.add(vid)
                title = "".join(run.get("text", "") for run in vr.get("title", {}).get("runs", []))
                channel = ""
                ot = vr.get("ownerText", {}).get("runs", [])
                if ot:
                    channel = ot[0].get("text", "")
                found.append({
                    "videoId": vid,
                    "title": title.strip(),
                    "channel": channel,
                    "views": parse_views(vr.get("viewCountText", {}).get("simpleText", "")),
                    "length": vr.get("lengthText", {}).get("simpleText", ""),
                    "published": vr.get("publishedTimeText", {}).get("simpleText", ""),
                })
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return found


def pick(videos: list[dict], tech: str, n: int = PER_TECH, by_stage: bool = True) -> list[dict]:
    """쓰레기만 걷어내고 채널 다양성만 보장 — 순서는 YouTube 관련도를 신뢰.

    YouTube 가 매기는 관련도 순위가 이미 정확하므로(클릭베이트를 조회수로 끌어올리지
    않으려고) 재정렬은 하지 않는다. 다만 ① 쇼츠/비학습 영상, ② 기술과 무관한데 조회수도
    낮은 영상은 제거하고, ③ 관련도 있는 영상을 앞으로 둬 주제 이탈을 막는다.
    ④ 한 채널 최대 MAX_PER_CHANNEL편. by_stage=True 면 입문→핵심→실전으로 재배치한다
    (세부 주제 안에서는 주제 순서를 살려야 하므로 False).
    """
    on_topic, off_topic = [], []
    for v in videos:
        vid, title = v.get("videoId"), (v.get("title") or "").strip()
        if not vid or not title:
            continue
        if 0 < parse_duration(v.get("length", "")) < MIN_SECONDS:   # 쇼츠 제외
            continue
        if any(bad in title.lower() for bad in NOISE):              # 비학습 제외
            continue
        channel = v.get("channel", "")
        views = v.get("views", 0)
        rel = relevance(tech, title, channel)
        if rel == 0 and views < MIN_VIEWS:                          # 무관 + 무명 → 노이즈
            continue
        (on_topic if rel >= 1 else off_topic).append(v)

    out, per_channel = [], {}
    for v in on_topic + off_topic:        # 관련도 있는 것 먼저, 각 그룹은 YouTube 순서 유지
        ch = v.get("channel", "")
        if per_channel.get(ch, 0) >= MAX_PER_CHANNEL:               # 채널 독식 방지
            continue
        per_channel[ch] = per_channel.get(ch, 0) + 1
        title = v["title"].strip()
        out.append({
            "title": title,
            "url": WATCH_URL.format(vid=v["videoId"]),
            "thumbnail": THUMB_URL.format(vid=v["videoId"]),
            "channel": ch,
            "views": v.get("views", 0),
            "length": v.get("length", ""),
            "published": v.get("published", ""),
            "stage": classify_stage(title),
        })
        if len(out) >= n:
            break

    if by_stage:
        out.sort(key=lambda x: STAGE_ORDER[x["stage"]])
    return out


# ── 세부 주제 커리큘럼 ────────────────────────────────────────────────────
# 주요 기술을 "무엇을 어떤 순서로" 공부할지 세부 주제로 쪼갠다. 각 주제는
# (라벨, YouTube 검색어, 한 줄 설명). guide 는 '어떻게 공부하면 효과적인지'.
# 여기 없는 기술은 단계(입문/핵심/실전) 경로로만 노출된다.
CURRICULA: dict[str, dict] = {
    "AWS": {
        "guide": "프리티어 계정을 만들어 직접 띄워보며 익히세요. EC2로 서버를 올리고 → S3로 파일을 저장하고 → RDS로 DB를 붙인 뒤 → IAM으로 권한을 잠그고 → VPC·로드밸런서로 실제 배포 구조를 완성하는 순서가 가장 효과적입니다.",
        "topics": [
            ("EC2 · 컴퓨팅", "AWS EC2 강의", "가상 서버를 띄우고 접속·운영하는 기본"),
            ("S3 · 스토리지", "AWS S3 강의", "파일 저장·정적 웹 호스팅"),
            ("RDS · 데이터베이스", "AWS RDS 강의", "관리형 관계형 DB 붙이기"),
            ("IAM · 권한", "AWS IAM 강의", "사용자·역할·정책으로 접근 통제"),
            ("VPC · 네트워크", "AWS VPC 강의", "서브넷·보안그룹으로 망 구성"),
            ("ELB·배포 구성", "AWS 로드밸런서 배포 강의", "로드밸런서·오토스케일로 실제 배포"),
            ("아키텍처 설계", "AWS 아키텍처 설계 Well-Architected 강의", "확장성·비용·보안 고려한 구성 설계"),
        ],
    },
    "React": {
        "guide": "공식 문서를 곁에 두고, 작은 컴포넌트부터 직접 만들며 익히세요. JSX·컴포넌트 → props/state → hooks → 상태관리 → 라우팅 순으로 쌓고, 마지막에 작은 프로젝트로 통합하면 됩니다.",
        "topics": [
            ("JSX·컴포넌트", "React 컴포넌트 강의", "화면을 컴포넌트로 쪼개기"),
            ("props·state", "React props state 강의", "데이터 전달과 상태 관리 기본"),
            ("Hooks", "React hooks useEffect 강의", "useState·useEffect 등 훅"),
            ("상태관리", "React 상태관리 redux zustand 강의", "전역·서버 상태 다루기"),
            ("라우팅", "React Router 강의", "페이지 전환·중첩 라우팅"),
            ("실전 프로젝트", "React 프로젝트 만들기 강의", "기능을 합쳐 앱 완성"),
            ("컴포넌트·폴더 구조 설계", "리액트 폴더구조 컴포넌트 설계 강의", "재사용 구조·도메인별 분리"),
        ],
    },
    "Spring Boot": {
        "guide": "자바 기본기를 갖춘 뒤 시작하세요. 프로젝트 구조 → REST API → JPA로 DB 연동 → 시큐리티로 인증 → 배포 순서로, 직접 게시판 같은 작은 서버를 만들며 익히는 게 가장 빠릅니다.",
        "topics": [
            ("입문·구조", "스프링부트 입문 강의", "프로젝트 구조와 빈·DI"),
            ("REST API", "스프링부트 REST API 강의", "컨트롤러로 API 설계"),
            ("JPA·DB", "스프링부트 JPA 강의", "엔티티·리포지토리로 영속성"),
            ("시큐리티", "스프링 시큐리티 강의", "로그인·인증·인가"),
            ("배포", "스프링부트 배포 강의", "빌드·서버 배포"),
            ("아키텍처·DDD 설계", "스프링 DDD 레이어드 아키텍처 강의", "도메인 분리·계층 설계"),
        ],
    },
    "Python": {
        "guide": "문법은 짧게 보고 바로 작은 프로그램을 만들며 익히세요. 기본 문법 → 자료구조 → 함수·모듈 → 관심 분야(웹/데이터/자동화)로 넓히는 순서를 권합니다.",
        "topics": [
            ("문법 기초", "파이썬 기초 문법 강의", "변수·조건·반복문"),
            ("자료구조", "파이썬 자료구조 리스트 딕셔너리 강의", "리스트·딕셔너리 다루기"),
            ("함수·모듈", "파이썬 함수 모듈 강의", "함수·클래스·패키지"),
            ("웹 개발", "파이썬 장고 플라스크 강의", "Django·Flask로 웹"),
            ("데이터 분석", "파이썬 데이터 분석 판다스 강의", "Pandas로 데이터 다루기"),
            ("코드 구조·클린코드", "파이썬 클린코드 설계 강의", "모듈·패키지로 구조 잡기"),
        ],
    },
    "Java": {
        "guide": "객체지향 개념을 손으로 코드를 짜며 체득하세요. 문법 → 객체지향 → 컬렉션·제네릭 → 예외·스트림 → 멀티스레드 순으로 쌓으면 스프링 학습이 수월해집니다.",
        "topics": [
            ("문법 기초", "자바 기초 문법 강의", "변수·제어문·배열"),
            ("객체지향", "자바 객체지향 강의", "클래스·상속·다형성"),
            ("컬렉션·제네릭", "자바 컬렉션 제네릭 강의", "List·Map·제네릭"),
            ("예외·스트림", "자바 예외처리 스트림 강의", "예외·람다·스트림"),
            ("멀티스레드", "자바 멀티스레드 강의", "동시성 기초"),
            ("객체지향·디자인패턴", "자바 디자인패턴 객체지향 설계 강의", "SOLID·패턴으로 설계"),
        ],
    },
    "JavaScript": {
        "guide": "브라우저 콘솔로 바로 실행해보며 익히세요. 기본 문법 → DOM 조작 → 비동기 → ES6+ 문법 순으로, 작은 인터랙션을 직접 구현하면 빠르게 늡니다.",
        "topics": [
            ("문법 기초", "자바스크립트 기초 강의", "변수·함수·객체"),
            ("DOM 조작", "자바스크립트 DOM 강의", "HTML 요소 제어·이벤트"),
            ("비동기", "자바스크립트 비동기 promise async 강의", "Promise·async/await"),
            ("ES6+", "자바스크립트 ES6 강의", "구조분해·모듈 등 최신 문법"),
            ("모듈화·도메인 설계", "자바스크립트 모듈화 아키텍처 강의", "관심사 분리·도메인 나누기"),
        ],
    },
    "TypeScript": {
        "guide": "자바스크립트를 어느 정도 안 뒤 시작하세요. 기본 타입 → 인터페이스·제네릭 → React/Node와 함께 쓰기 순으로 익히면 실무에 바로 적용됩니다.",
        "topics": [
            ("기본 타입", "타입스크립트 기초 강의", "타입·인터페이스 기본"),
            ("제네릭·고급", "타입스크립트 제네릭 강의", "제네릭·유틸리티 타입"),
            ("React와 함께", "타입스크립트 리액트 강의", "컴포넌트 타이핑"),
            ("타입 설계 패턴", "타입스크립트 타입 설계 강의", "안전한 타입 모델링"),
        ],
    },
    "Node.js": {
        "guide": "자바스크립트 기초 위에서 시작하세요. 런타임 개념 → Express로 API → 비동기·이벤트루프 → DB 연동 → 배포 순으로 작은 서버를 만들며 익히세요.",
        "topics": [
            ("기초", "Node.js 기초 강의", "런타임·모듈 시스템"),
            ("Express API", "Node.js Express 강의", "라우팅·미들웨어로 API"),
            ("DB 연동", "Node.js MongoDB MySQL 강의", "데이터베이스 붙이기"),
            ("배포", "Node.js 배포 강의", "서버 배포·운영"),
            ("아키텍처 설계", "Node.js 레이어드 클린 아키텍처 강의", "계층 분리·폴더 구조 설계"),
        ],
    },
    "Docker": {
        "guide": "직접 컨테이너를 띄워보며 익히세요. 이미지·컨테이너 개념 → 실행 → Dockerfile 작성 → docker-compose로 여러 서비스 묶기 순서가 효과적입니다.",
        "topics": [
            ("개념·이미지", "도커 개념 강의", "이미지·컨테이너 이해"),
            ("Dockerfile", "Dockerfile 작성 강의", "내 앱을 이미지로 만들기"),
            ("compose", "docker compose 강의", "여러 컨테이너 묶어 실행"),
            ("배포", "도커 배포 강의", "실제 서버에 올리기"),
            ("이미지·구성 설계", "도커 멀티스테이지 이미지 최적화 강의", "가볍고 안전한 이미지 설계"),
        ],
    },
    "Kubernetes": {
        "guide": "도커를 먼저 익힌 뒤 시작하세요. 아키텍처 → Pod/Deployment → Service/Ingress → ConfigMap/Secret → Helm 순으로, minikube로 직접 띄워보며 배우는 게 좋습니다.",
        "topics": [
            ("개념·아키텍처", "쿠버네티스 개념 아키텍처 강의", "클러스터 구조 이해"),
            ("Pod·Deployment", "쿠버네티스 Pod Deployment 강의", "워크로드 배포"),
            ("Service·Ingress", "쿠버네티스 Service Ingress 강의", "트래픽 노출·라우팅"),
            ("Config·Secret", "쿠버네티스 ConfigMap Secret 강의", "설정·비밀 관리"),
            ("Helm", "쿠버네티스 Helm 강의", "패키지로 배포 관리"),
            ("클러스터 아키텍처 설계", "쿠버네티스 아키텍처 설계 강의", "확장·고가용 구성 설계"),
        ],
    },
    "Vue": {
        "guide": "공식 문서 튜토리얼을 따라가며 시작하세요. 기본 문법 → 컴포넌트 → 상태관리(Pinia) → 라우팅 → 실전 순으로 작은 앱을 만들며 익히세요.",
        "topics": [
            ("기초·문법", "Vue 기초 강의", "템플릿·디렉티브"),
            ("컴포넌트", "Vue 컴포넌트 강의", "컴포넌트·props"),
            ("상태관리", "Vue Pinia Vuex 강의", "전역 상태 관리"),
            ("라우팅", "Vue Router 강의", "페이지 전환"),
            ("프로젝트 구조 설계", "Vue 프로젝트 구조 설계 강의", "컴포넌트·모듈 분리"),
        ],
    },
    "Next.js": {
        "guide": "React를 먼저 익힌 뒤 시작하세요. 라우팅 → 데이터 패칭/SSR → App Router → 배포 순으로, Vercel에 직접 배포해보면 이해가 빠릅니다.",
        "topics": [
            ("기초·라우팅", "Next.js 기초 강의", "파일 기반 라우팅"),
            ("데이터·SSR", "Next.js SSR 데이터패칭 강의", "서버 렌더링·패칭"),
            ("App Router", "Next.js App Router 강의", "최신 앱 라우터"),
            ("배포", "Next.js 배포 강의", "Vercel 배포"),
            ("프로젝트 구조 설계", "Next.js 프로젝트 구조 아키텍처 강의", "폴더·레이어 설계"),
        ],
    },
    "Django": {
        "guide": "파이썬 기본기 위에서 시작하세요. MTV 구조 → 모델/ORM → DRF로 API → 배포 순으로 작은 서비스를 만들며 익히세요.",
        "topics": [
            ("기초·MTV", "장고 기초 강의", "MTV 구조와 뷰"),
            ("모델·ORM", "장고 모델 ORM 강의", "DB 모델링·쿼리"),
            ("REST API", "장고 DRF 강의", "DRF로 API 만들기"),
            ("배포", "장고 배포 강의", "실제 서버 배포"),
            ("앱 구조·설계", "장고 프로젝트 구조 설계 강의", "앱 분리·도메인 설계"),
        ],
    },
    "MySQL": {
        "guide": "직접 쿼리를 쳐보며 익히세요. SELECT 기본 → 조인 → 인덱스·최적화 → 설계 순으로, 실제 데이터로 연습하는 게 가장 효과적입니다.",
        "topics": [
            ("SQL 기초", "MySQL SQL 기초 강의", "SELECT·WHERE·정렬"),
            ("조인", "SQL 조인 강의", "테이블 결합"),
            ("인덱스·최적화", "MySQL 인덱스 최적화 강의", "성능 튜닝"),
            ("설계", "데이터베이스 설계 강의", "정규화·모델링"),
        ],
    },
    "Kafka": {
        "guide": "메시지 큐 개념을 먼저 잡으세요. 개념 → 프로듀서/컨슈머 → 스프링 연동·실전 순으로, 직접 토픽을 만들어 메시지를 흘려보며 익히세요.",
        "topics": [
            ("개념", "카프카 개념 강의", "토픽·파티션 이해"),
            ("프로듀서·컨슈머", "카프카 프로듀서 컨슈머 강의", "메시지 발행·소비"),
            ("실전 연동", "카프카 스프링 연동 강의", "애플리케이션 연동"),
            ("이벤트 아키텍처 설계", "카프카 이벤트 기반 아키텍처 강의", "이벤트 드리븐 설계"),
        ],
    },
    "Git": {
        "guide": "직접 저장소를 만들어 커밋하며 익히세요. 커밋 기본 → 브랜치/머지 → 협업(PR·충돌 해결) → 되돌리기 순서가 효과적입니다.",
        "topics": [
            ("기초·커밋", "깃 기초 강의", "add·commit·로그"),
            ("브랜치·머지", "깃 브랜치 머지 강의", "분기·병합"),
            ("협업", "깃허브 협업 PR 강의", "PR·충돌 해결"),
            ("되돌리기", "깃 reset revert 강의", "실수 되돌리기"),
        ],
    },
    "Linux": {
        "guide": "터미널을 직접 두드리며 익히세요. 기본 명령어 → 셸 스크립트 → 권한·프로세스 → 서버 운영 순으로 익히면 배포·운영이 편해집니다.",
        "topics": [
            ("기초 명령어", "리눅스 명령어 강의", "파일·디렉터리 조작"),
            ("셸 스크립트", "리눅스 쉘 스크립트 강의", "자동화 스크립트"),
            ("권한·프로세스", "리눅스 권한 프로세스 강의", "퍼미션·프로세스 관리"),
            ("서버 운영", "리눅스 서버 운영 강의", "서비스·네트워크 운영"),
        ],
    },
    "Flutter": {
        "guide": "Dart 기본을 짧게 본 뒤 위젯을 직접 그리며 익히세요. 위젯 → 상태관리 → 화면·네비게이션 → API 연동 → 배포 순으로 작은 앱을 만들어보세요.",
        "topics": [
            ("기초·위젯", "플러터 기초 위젯 강의", "위젯으로 UI 구성"),
            ("상태관리", "플러터 상태관리 강의", "Provider·Riverpod 등"),
            ("네비게이션", "플러터 화면 이동 강의", "화면 전환·라우팅"),
            ("API 연동", "플러터 API 연동 강의", "서버 데이터 붙이기"),
            ("앱 아키텍처 설계", "플러터 클린 아키텍처 MVVM 강의", "상태·계층 분리 설계"),
        ],
    },
    "PyTorch": {
        "guide": "파이썬·기초 수학 위에서 시작하세요. 텐서 → 신경망 구성 → 학습 루프 → 실전 모델 순으로, 직접 작은 모델을 학습시켜보며 익히세요.",
        "topics": [
            ("텐서 기초", "파이토치 텐서 기초 강의", "텐서 연산"),
            ("신경망", "파이토치 신경망 강의", "모델 정의"),
            ("학습 루프", "파이토치 학습 강의", "손실·옵티마이저"),
            ("실전 모델", "파이토치 프로젝트 강의", "CNN 등 실전"),
        ],
    },
    "Redis": {
        "guide": "직접 띄워 명령어를 쳐보며 익히세요. 자료구조 → 캐시 활용 → 실전(세션·랭킹 등) 순으로 익히면 됩니다.",
        "topics": [
            ("개념·자료구조", "레디스 기초 강의", "String·Hash·List 등"),
            ("캐시 활용", "레디스 캐시 강의", "캐싱 전략"),
            ("실전 활용", "레디스 실전 강의", "세션·랭킹 등"),
            ("캐시 아키텍처 설계", "레디스 캐시 전략 아키텍처 강의", "캐시 패턴·무효화 설계"),
        ],
    },
}


def atomic_write(path: Path, text: str) -> None:
    """임시 파일에 쓴 뒤 교체 — 디스크 부족·동시 실행에도 기존 파일이 손상되지 않게."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def fetch_cached(client: httpx.Client, cache: dict, query: str, refresh: bool) -> list[dict]:
    """검색어로 영상 원본을 가져오되 결과를 캐시(검색어 키)에 보관."""
    if not refresh and query in cache:
        return cache[query]
    raw = fetch_videos(client, query)
    cache[query] = raw
    time.sleep(FETCH_DELAY)
    return raw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=3, help="'기타' 기술 포함 최소 회사수 (기본 3)")
    ap.add_argument("--limit", type=int, default=0, help="앞 N개 기술만 처리(테스트용)")
    ap.add_argument("--refresh", action="store_true", help="캐시 무시하고 재수집")
    args = ap.parse_args()

    if not STACKS.exists():
        print(f"[!] 입력 없음: {STACKS} — 먼저 build_company_stacks.py 실행", file=sys.stderr)
        sys.exit(1)

    techs = load_techs(args.min)
    if args.limit:
        techs = techs[: args.limit]
    print(f"[*] 대상 기술 {len(techs)}개 — YouTube 학습 영상 수집 시작", flush=True)

    cache: dict = {}
    if CACHE.exists() and not args.refresh:
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    resources: dict[str, list] = {}
    curricula: dict[str, dict] = {}
    headers = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}
    with httpx.Client(headers=headers) as client:
        # 1) 기술별 단계 경로(입문→핵심→실전) — 폭넓은 추천
        for i, t in enumerate(techs, 1):
            name = t["name"]
            raw = fetch_cached(client, cache, f"{name} 강의", args.refresh)
            picked = pick(raw, name)
            if picked:
                resources[name] = picked
            if i % 20 == 0 or i == len(techs):
                print(f"    {i}/{len(techs)} … 단계 경로 보유 {len(resources)}개 기술", flush=True)

        # 2) 주요 기술 세부 주제 커리큘럼 — "무엇을 어떤 순서로" 깊이
        print(f"[*] 커리큘럼 {len(CURRICULA)}개 기술 세부 주제 수집", flush=True)
        for name, spec in CURRICULA.items():
            topics = []
            seen_urls: set[str] = set()   # 같은 영상이 여러 주제에 중복되지 않도록
            for label, query, note in spec["topics"]:
                raw = fetch_cached(client, cache, query, args.refresh)
                vids = [v for v in pick(raw, name, n=5, by_stage=False)
                        if v["url"] not in seen_urls][:3]
                seen_urls.update(v["url"] for v in vids)
                if vids:
                    topics.append({"topic": label, "note": note, "videos": vids})
            if topics:
                curricula[name] = {"guide": spec["guide"], "topics": topics}
            print(f"    {name:12s} → 주제 {len(topics)}개", flush=True)

    atomic_write(CACHE, json.dumps(cache, ensure_ascii=False))
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "youtube",
        "tech_count": len(resources),
        "curriculum_count": len(curricula),
        "search_url": "https://www.youtube.com/results?search_query={tech}+강의",
        "resources": resources,
        "curricula": curricula,
    }
    atomic_write(OUTPUT, json.dumps(out, ensure_ascii=False, indent=2))
    total = sum(len(v) for v in resources.values())
    print(f"[*] {OUTPUT.relative_to(ROOT)} 작성 — 단계경로 {len(resources)}개·커리큘럼 "
          f"{len(curricula)}개 / 영상 {total}건", flush=True)


if __name__ == "__main__":
    main()
