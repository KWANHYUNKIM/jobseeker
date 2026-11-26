"""벡터(임베딩·유사 문서) 설정 — 모델·튜닝 상수의 단일 소스.

예전 SQLite 판(semantic/)의 config 를 옮겨 왔다. 환경변수 이름(SEMANTIC_*)은 운영 맥의
설정을 깨지 않으려고 그대로 둔다.
"""
from __future__ import annotations

import os
from pathlib import Path

CATCH_DIR = Path(__file__).resolve().parent.parent.parent  # catch_capture/
ROOT_DIR = CATCH_DIR.parent  # jobseeker/
VIEWER_PUBLIC = ROOT_DIR / "jd-viewer" / "public"

# ── 출력 (API 가 없는 배포에서 뷰어가 정적으로 소비) ──────────────────
SIMILAR_JOBS_JSON = VIEWER_PUBLIC / "similar_jobs.json"
SIMILAR_POSTS_JSON = VIEWER_PUBLIC / "similar_posts.json"

# ── 임베딩 모델 ───────────────────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("SEMANTIC_EMBED_MODEL", "bge-m3")
EMBED_DIM = int(os.environ.get("SEMANTIC_EMBED_DIM", "1024"))  # bge-m3 = 1024

# 한 번의 /api/embed 요청에 넣을 문서 수. M1 에서 8~16 이 무난하다.
EMBED_BATCH = int(os.environ.get("SEMANTIC_EMBED_BATCH", "8"))
# 임베딩 입력 최대 길이(문자). bge-m3 는 8192 토큰까지 받지만
# JD 뒷부분(복지/회사소개)은 변별력이 낮고 M1 속도만 깎는다.
MAX_EMBED_CHARS = int(os.environ.get("SEMANTIC_MAX_CHARS", "2000"))
EMBED_TIMEOUT = int(os.environ.get("SEMANTIC_EMBED_TIMEOUT", "180"))

# ── 추천 ──────────────────────────────────────────────────────────────
TOP_K = int(os.environ.get("SEMANTIC_TOP_K", "5"))
# 같은 회사(계열) 공고로 추천이 도배되는 것을 막는다. 상한은 계열 단위로 건다.
MAX_PER_COMPANY = int(os.environ.get("SEMANTIC_MAX_PER_COMPANY", "2"))

# 계열사 묶음 — `company.norm`(NFKC·법인격 제거·공백 제거·소문자)의 **접두**로 묶는다.
# 토스뱅크·토스증권·토스는 회사 id 가 달라 회사별 상한을 그대로 통과했고, 토스 공고의
# "비슷한 공고"가 전부 토스 계열로 찼다(2026-11-25). 추천은 **원래 공고와 같은 계열을
# 빼고** 고른다 — 같은 회사의 다른 자리는 회사 화면에서 이미 보인다.
# 여기 없는 회사는 회사 하나가 곧 한 계열이다. 긴 접두가 먼저 이긴다.
# 짧고 흔한 접두(하나·kt 등)는 무관한 회사를 끌어들여서 일부러 넣지 않았다.
COMPANY_GROUPS: dict[str, tuple[str, ...]] = {
    "토스": ("토스", "비바리퍼블리카", "toss"),
    "카카오": ("카카오", "kakao"),
    "네이버": ("네이버", "naver"),
    "라인": ("라인플러스", "라인게임즈", "라인넥스트", "라인비즈플러스", "lineplus", "linecorp", "ly코퍼레이션"),
    "쿠팡": ("쿠팡", "coupang"),
    "삼성": ("삼성", "samsung"),
    "sk": ("sk", "에스케이"),
    "lg": ("lg", "엘지"),
    "현대차": ("현대자동차", "현대오토에버", "현대모비스", "기아", "현대글로비스", "현대위아", "현대카드", "현대캐피탈", "42dot", "포티투닷"),
    "롯데": ("롯데",),
    "한화": ("한화",),
    "cj": ("cj", "씨제이"),
    "신세계": ("신세계", "이마트", "ssg", "에스에스지"),
    "nhn": ("nhn",),
    "넥슨": ("넥슨", "nexon", "네오플"),
    "kb": ("kb", "국민은행", "케이비"),
    "신한": ("신한",),
    "우아한": ("우아한", "배달의민족"),
    "당근": ("당근",),
    "넷마블": ("넷마블",),
    "엔씨": ("엔씨소프트", "ncsoft", "엔씨"),
    "크래프톤": ("크래프톤", "krafton"),
}
# 사실상 동일 공고(재게시/중복)는 추천으로서 가치가 없다.
DUP_SCORE = float(os.environ.get("SEMANTIC_DUP_SCORE", "0.985"))
# 이 아래로는 "비슷하다"고 부르기 민망한 수준이라 잘라낸다.
MIN_SCORE = float(os.environ.get("SEMANTIC_MIN_SCORE", "0.55"))
