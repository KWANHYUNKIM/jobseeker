#!/usr/bin/env bash
# 크롤 오케스트레이터(auto_crawl) 멱등 시작 래퍼 — cron/@reboot 에서 호출.
# 이미 실행 중이면 auto_crawl 이 PID 파일을 보고 아무것도 안 한다(멱등).
# auto_crawl 데몬 하나가 크롤 + 데이터 갱신 + 레이더 리파인 + 후기 데몬 + 학습 재수집을
# 모두 오케스트레이션하므로, 흩어진 cron 대신 이 한 줄만 keep-alive 하면 된다.
#
# 키워드/건수/주기는 아래 변수(또는 환경변수)로 조절.
set -uo pipefail
export PATH="/Users/kwanhyun/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# 주기적 데이터 자동 커밋은 항상 켜져 있다(로컬). 자동 push 까지 원하면 아래 주석을 해제.
# (CLAUDE.md 규칙상 기본 OFF — 명시적으로 켤 때만 push)
# export JOBSEEKER_AUTOPUSH=1

REPO="/Users/kwanhyun/jobseeker"
BASE="$REPO/catch_capture"
PY="$([ -x "$BASE/.venv/bin/python" ] && echo "$BASE/.venv/bin/python" || echo python3)"

KEYWORD="${KEYWORD:-개발자,프론트엔드,백엔드,풀스택,안드로이드,iOS,데이터엔지니어,데이터분석,머신러닝,AI,데브옵스,클라우드,플랫폼엔지니어,SRE,보안,자바,파이썬,자바스크립트,리액트,노드}"
COUNT="${COUNT:-50}"
INTERVAL="${INTERVAL:-3600}"

cd "$BASE"
exec "$PY" automation/auto_crawl.py start "$KEYWORD" "$COUNT" "$INTERVAL"
