#!/usr/bin/env python3
"""직군(수식어)별 인사이트 집계 → public/role_insights.json

내 잡 리스트(all_jobs_enriched.json)를 직군으로 멀티라벨 분류하고, 각 직군에 대해
- 관련 산업(도메인) 분포
- 경력 / 학력 분포
- 주요 기술스택
- 우대사항 / 자격요건 키워드 빈도(키워드 사전 스캔)
를 취합한다. 분류·정규화·도메인 매핑은 기존 파이프라인 로직을 그대로 재사용.

실행: cd jd-viewer/bin && python3 build_role_insights.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "catch_capture" / "dashboard"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from classifier import classify_dev_roles, _norm_company  # noqa: E402
from build_company_stacks import infer_domains  # noqa: E402
from jobs_filter import active_only  # noqa: E402

INPUT = ROOT / "jd-viewer" / "public" / "all_jobs_enriched.json"
OUTPUT = ROOT / "jd-viewer" / "public" / "role_insights.json"

# ── 우대사항/자격요건 키워드 사전 ──────────────────────────────────────────
# surface(표시명) → 매칭 정규식(대소문자 무시). 자유텍스트에서 의미있는 개념을 빈도화.
KW_RULES: dict[str, str] = {
    "관련 전공/학위": r"관련\s*(전공|학과|분야)|전공자|학위\s*소지",
    "대용량 트래픽": r"대용량|대규모\s*트래픽|트래픽|고트래픽|high\s*traffic",
    "MSA/마이크로서비스": r"마이크로\s*서비스|msa|microservice",
    "분산 시스템": r"분산\s*(시스템|처리|환경)|distributed",
    "클라우드(AWS/GCP/Azure)": r"\b(aws|gcp|azure)\b|클라우드|cloud",
    "컨테이너(Docker/K8s)": r"docker|kubernetes|k8s|컨테이너|쿠버네티스",
    "CI/CD": r"ci/?cd|지속적\s*통합|배포\s*자동화",
    "테스트 코드/TDD": r"테스트\s*코드|tdd|단위\s*테스트|test\s*code",
    "성능 최적화": r"성능\s*(최적화|개선|튜닝)|performance",
    "데이터 파이프라인/ETL": r"데이터\s*파이프라인|etl|data\s*pipeline",
    "실시간 처리": r"실시간|real[\s-]?time|스트리밍|streaming",
    "메시지 큐(Kafka)": r"kafka|rabbitmq|메시지\s*큐|message\s*queue|이벤트\s*기반",
    "캐시(Redis)": r"redis|memcached|캐시|caching",
    "SQL/RDBMS": r"\b(sql|mysql|postgres|postgresql|oracle|rdbms)\b|관계형",
    "NoSQL": r"nosql|mongodb|cassandra|dynamodb|elasticsearch",
    "REST/gRPC/GraphQL": r"\b(rest|restful|grpc|graphql)\b|api\s*설계",
    "동시성/병렬": r"동시성|병렬|concurren|멀티\s*스레드|멀티스레딩",
    "알고리즘/자료구조": r"알고리즘|자료\s*구조|algorithm|data\s*structure",
    "오픈소스 기여": r"오픈\s*소스|open\s*source|github\s*활동|컨트리뷰",
    "논문/특허": r"논문|특허|paper|patent|학회",
    "보안/인증": r"보안|security|인증|암호화|oauth|취약점",
    "모니터링/관측": r"모니터링|monitoring|observability|prometheus|grafana|로그\s*분석",
    "장애 대응": r"장애\s*(대응|처리|분석)|trouble\s*shoot|on[\s-]?call",
    "코드 리뷰": r"코드\s*리뷰|code\s*review",
    "리팩토링/클린코드": r"리팩토링|refactor|클린\s*코드|clean\s*code",
    "애자일/스크럼": r"애자일|agile|스크럼|scrum|칸반",
    "협업/커뮤니케이션": r"협업|커뮤니케이션|communication|collaborat",
    "문서화": r"문서화|기술\s*문서|documentation|테크\s*라이팅",
    "리더십/리딩": r"리더십|leadership|리딩|팀\s*리드|tech\s*lead|멘토",
    "스타트업 경험": r"스타트업|startup|초기\s*멤버|0\s*to\s*1",
    "영어 가능": r"영어|english|글로벌|비즈니스\s*회화",
    "도메인 경험": r"도메인\s*(지식|경험|이해)|domain\s*(knowledge|experience)",
    "ML/AI 경험": r"머신\s*러닝|machine\s*learning|딥\s*러닝|deep\s*learning|\bml\b|\bai\b|llm",
    "데이터 분석": r"데이터\s*분석|data\s*analy|통계|statistic",
    "임베디드/펌웨어": r"임베디드|embedded|펌웨어|firmware|rtos|mcu",
    "하드웨어 연동": r"하드웨어|hardware|디바이스|device|센서|sensor|회로",
    "모바일(iOS/AOS)": r"\bios\b|android|안드로이드|모바일\s*앱|flutter|react\s*native",
}
KW_COMPILED = {k: re.compile(v, re.I) for k, v in KW_RULES.items()}

EDU_RULES: dict[str, str] = {
    "박사": r"박사",
    "석사": r"석사",
    "학사/대졸": r"학사|대졸|4년제",
    "전문학사/초대졸": r"초대졸|전문학사|2년제",
    "고졸": r"고졸",
    "학력무관": r"학력\s*무관",
}
EDU_COMPILED = {k: re.compile(v, re.I) for k, v in EDU_RULES.items()}

YEAR_BUCKETS = ["신입", "1~3년", "3~5년", "5~10년", "10년+"]


def career_bucket(career: str) -> str:
    s = career or ""
    if "무관" in s:
        return "경력무관"
    has_sin = "신입" in s
    has_gyeong = "경력" in s or re.search(r"\d", s)
    if has_sin and has_gyeong:
        return "신입·경력"
    if has_sin:
        return "신입"
    if has_gyeong:
        return "경력"
    return "기타"


def career_years(career: str) -> str | None:
    """경력 문자열에서 최소 연차 추출 → 구간 라벨."""
    s = career or ""
    if "신입" in s and "경력" not in s:
        return "신입"
    m = re.search(r"(\d+)\s*[년~\-↑]", s)
    if not m:
        return None
    y = int(m.group(1))
    if y < 1:
        return "신입"
    if y < 3:
        return "1~3년"
    if y < 5:
        return "3~5년"
    if y < 10:
        return "5~10년"
    return "10년+"


def top_list(counter: Counter, n: int) -> list[dict]:
    return [{"name": k, "count": v} for k, v in counter.most_common(n)]


def kw_list(counter: Counter, n: int) -> list[dict]:
    return [{"kw": k, "count": v} for k, v in counter.most_common(n)]


def main() -> None:
    # 마감 공고는 뺀다. all_jobs_enriched.json 은 이제 모집중과 마감을 함께 담는데
    # (색인·과거 조회를 살리려고) 이 빌더의 결과는 "지금 시장"이라 만료 공고를 세면
    # 수요가 과거에 눌린다.
    jobs = active_only(json.loads(INPUT.read_text(encoding="utf-8")))
    print(f"[*] loaded {len(jobs)} jobs")

    # 직군별 누적기
    agg: dict[str, dict] = defaultdict(
        lambda: {
            "count": 0,
            "industries": Counter(),
            "career": Counter(),
            "years": Counter(),
            "education": Counter(),
            "tech": Counter(),
            "preferences": Counter(),
            "qualifications": Counter(),
        }
    )

    # 도메인 캐시(같은 회사 공고 반복 → 회사별 1회)
    domain_cache: dict[str, str] = {}

    for i, job in enumerate(jobs):
        title = job.get("title", "")
        tech = job.get("tech_stack", []) or []
        quals = job.get("qualifications", "") or ""
        prefs = job.get("preferences", "") or ""

        roles = classify_dev_roles(title=title, tech_stack=tech, extra_text=quals[:500])

        # 산업 도메인 (회사 단위 캐시)
        cn = _norm_company(job.get("company", ""))
        if cn in domain_cache:
            domain = domain_cache[cn]
        else:
            text = " ".join(
                [title, job.get("main_tasks", ""), quals, prefs, (job.get("full_jd", "") or "")[:1500]]
            )
            doms = infer_domains(text, top=1)
            domain = doms[0]["name"] if doms else "기타/미상"
            domain_cache[cn] = domain

        cb = career_bucket(job.get("career", ""))
        yb = career_years(job.get("career", ""))
        edus = [k for k, rx in EDU_COMPILED.items() if rx.search(quals + " " + prefs)]
        pref_kws = [k for k, rx in KW_COMPILED.items() if rx.search(prefs)]
        qual_kws = [k for k, rx in KW_COMPILED.items() if rx.search(quals)]

        for role in roles:
            a = agg[role]
            a["count"] += 1
            a["industries"][domain] += 1
            a["career"][cb] += 1
            if yb:
                a["years"][yb] += 1
            for e in edus:
                a["education"][e] += 1
            for t in tech:
                a["tech"][t] += 1
            for k in pref_kws:
                a["preferences"][k] += 1
            for k in qual_kws:
                a["qualifications"][k] += 1

        if (i + 1) % 1000 == 0:
            print(f"    .. {i + 1}/{len(jobs)}")

    # 직군 정렬: 공고 수 내림차순, '기타'는 맨 뒤
    def sort_key(item):
        role, _ = item
        return (role == "기타", -agg[role]["count"])

    roles_out = []
    for role, a in sorted(agg.items(), key=sort_key):
        ed_order = ["학력무관", "고졸", "전문학사/초대졸", "학사/대졸", "석사", "박사"]
        roles_out.append(
            {
                "role": role,
                "count": a["count"],
                "industries": top_list(a["industries"], 12),
                "career": [
                    {"name": k, "count": a["career"][k]}
                    for k in ["경력무관", "신입", "신입·경력", "경력", "기타"]
                    if a["career"].get(k)
                ],
                "years": [
                    {"name": k, "count": a["years"][k]} for k in YEAR_BUCKETS if a["years"].get(k)
                ],
                "education": [
                    {"name": k, "count": a["education"][k]} for k in ed_order if a["education"].get(k)
                ],
                "tech": top_list(a["tech"], 24),
                "preferences": kw_list(a["preferences"], 30),
                "qualifications": kw_list(a["qualifications"], 30),
            }
        )

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_jobs": len(jobs),
        "roles": roles_out,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"[*] wrote {OUTPUT} ({len(roles_out)} roles, {OUTPUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
