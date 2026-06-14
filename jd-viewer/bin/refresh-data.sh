#!/usr/bin/env bash
# 가장 최근의 통합 폴더로 all_개발자_latest 심볼릭링크를 갱신.
# 멀티 키워드 통합(all_통합_*)이 있으면 그것을, 없으면 단일 키워드(all_개발자_*)를 쓴다.
# enrich_jobs.py 가 all_개발자_latest 만 읽으므로 심링크 대상만 바꿔 무수정으로 통합본을 소비한다.
set -euo pipefail

SCREENSHOTS_DIR="$(cd "$(dirname "$0")/../.." && pwd)/catch_capture/screenshots"
cd "$SCREENSHOTS_DIR"

LATEST=$(ls -1dt all_통합_* 2>/dev/null | grep -v '_latest$' | head -1)
if [ -z "$LATEST" ]; then
  LATEST=$(ls -1dt all_개발자_* 2>/dev/null | grep -v '_latest$' | head -1)
fi
if [ -z "$LATEST" ]; then
  echo "all_통합_* / all_개발자_* 폴더를 찾을 수 없습니다." >&2
  exit 1
fi

ln -sfn "$LATEST" all_개발자_latest
echo "latest -> $LATEST"

# enrich + mindmap + 회사 기술스택 재빌드
# build_company_stacks 는 company_profiles.json(crawl_company 결과)이 있으면 병합한다.
# venv 파이썬을 쓴다 — build_learning.py 가 httpx 등 venv 의존성을 필요로 하므로
# 시스템 python3 로 돌리면 ModuleNotFoundError 로 실패한다.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$(cd "$(dirname "$0")/../.." && pwd)/catch_capture/.venv/bin/python"
PY="$([ -x "$VENV_PY" ] && echo "$VENV_PY" || echo python3)"
"$PY" "$SCRIPT_DIR/enrich_jobs.py"
"$PY" "$SCRIPT_DIR/build_mindmap.py"
"$PY" "$SCRIPT_DIR/build_company_stacks.py"
# 기술별 추천 학습 영상(YouTube) — company_stacks.json 의 기술 목록을 소비. 캐시로 증분 수집.
"$PY" "$SCRIPT_DIR/build_learning.py"
# 모집 캘린더 — JD 본문의 접수/모집기간·마감 표기를 파싱해 job_calendar.json 생성
"$PY" "$SCRIPT_DIR/build_calendar.py"
# 개발 트렌드 — 날짜별 스냅샷에서 기술 수요 시계열(trends.json) 집계
"$PY" "$SCRIPT_DIR/build_trends.py"
# 기술 관계·맥락 — 동시출현(스택 레이어) 집계(LLM context/domains 는 보존)
"$PY" "$SCRIPT_DIR/build_tech_relations.py"
