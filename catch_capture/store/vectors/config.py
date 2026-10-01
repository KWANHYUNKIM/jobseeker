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
# 같은 회사 공고로 추천이 도배되는 것을 막는다.
MAX_PER_COMPANY = int(os.environ.get("SEMANTIC_MAX_PER_COMPANY", "2"))
# 사실상 동일 공고(재게시/중복)는 추천으로서 가치가 없다.
DUP_SCORE = float(os.environ.get("SEMANTIC_DUP_SCORE", "0.985"))
# 이 아래로는 "비슷하다"고 부르기 민망한 수준이라 잘라낸다.
MIN_SCORE = float(os.environ.get("SEMANTIC_MIN_SCORE", "0.55"))
