#!/usr/bin/env bash
# 가장 최근의 통합 폴더로 all_개발자_latest 심볼릭링크를 갱신.
# 멀티 키워드 통합(all_통합_*)이 있으면 그것을, 없으면 단일 키워드(all_개발자_*)를 쓴다.
# enrich_jobs.py 가 all_개발자_latest 만 읽으므로 심링크 대상만 바꿔 무수정으로 통합본을 소비한다.
set -euo pipefail

# 경로는 cd 하기 전에 모두 절대경로로 확정한다. 아래에서 screenshots 로 cd 한
# 뒤 상대경로 $0 로 다시 dirname 하면(호출을 상대경로로 했을 때) 깨진다.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCREENSHOTS_DIR="$ROOT_DIR/catch_capture/screenshots"
cd "$SCREENSHOTS_DIR"

# set -e + pipefail 아래에서 매칭이 없으면 ls/grep 파이프라인이 exit 1 을 내
# 폴백에 닿기도 전에 스크립트가 죽는다. 단일 키워드 크롤은 all_통합_* 을 만들지
# 않으므로 첫 줄에서 바로 걸린다. `|| true` 로 빈 결과를 정상 처리한다.
LATEST=$(ls -1dt all_통합_* 2>/dev/null | grep -v '_latest$' | head -1 || true)
if [ -z "$LATEST" ]; then
  LATEST=$(ls -1dt all_개발자_* 2>/dev/null | grep -v '_latest$' | head -1 || true)
fi
if [ -z "$LATEST" ]; then
  echo "all_통합_* / all_개발자_* 폴더를 찾을 수 없습니다." >&2
  exit 1
fi

# venv 파이썬을 쓴다 — build_learning.py 가 httpx 등 venv 의존성을 필요로 하므로
# 시스템 python3 로 돌리면 ModuleNotFoundError 로 실패한다.
VENV_PY="$ROOT_DIR/catch_capture/.venv/bin/python"
PY="$([ -x "$VENV_PY" ] && echo "$VENV_PY" || echo python3)"

# ── 급감 가드 ───────────────────────────────────────────────
# enrich_jobs.py 는 all_개발자_latest 하나만 읽어 public/all_jobs_enriched.json 을
# 통째로 덮어쓴다(병합이 아니다). 그래서 심링크가 작은 스냅샷을 가리키는 순간
# 누적된 만 건이 그 스냅샷 건수로 통째 교체된다. 2026-08-17 에 실제로 터졌다:
# 스냅샷 이력이 없는 새 서버에서 단일 키워드 크롤(all_개발자_*)이 폴백으로 잡혀
# 10,275건 → 25건이 됐고, autocommit 이 그대로 push 까지 했다.
#
# 원인이 부분 크롤 실패든 폴더 오선택이든 증상은 늘 "건수가 확 준다" 이므로,
# 심링크를 옮기기 전에 건수를 비교해 급감이면 아무것도 손대지 않고 멈춘다.
#   REFRESH_MIN_RATIO=0.5  기존 대비 이 비율 미만이면 중단 (기본 50%)
#   REFRESH_FORCE=1        가드 무시 (키워드 축소 등 의도적 감소일 때만)
count_jobs() {  # $1=JSON 경로 → 배열 길이. 없거나 깨졌으면 빈 문자열.
  [ -f "$1" ] || return 0
  "$PY" -c '
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(0)
if isinstance(d, list):
    print(len(d))
' "$1" 2>/dev/null || true
}

ENRICHED="$ROOT_DIR/jd-viewer/public/all_jobs_enriched.json"
MIN_RATIO="${REFRESH_MIN_RATIO:-0.5}"
# 가드가 잡아야 하는 것은 **데이터 손실**이지 마감 전환이 아니다. enriched 는 모집중과
# 마감을 함께 담으므로(마감을 지우면 "예전에 이런 자리가 있었다"가 사라진다) 새 스냅샷도
# 두 파일을 합쳐 세야 같은 기준이 된다. 모집중만 세면, 마감 재확인(pipeline/close_check)이
# 공고를 닫을수록 비율이 떨어져 멀쩡한 갱신이 급감으로 오인된다.
ACTIVE_COUNT="$(count_jobs "$SCREENSHOTS_DIR/$LATEST/all_jobs.json")"
CLOSED_COUNT="$(count_jobs "$SCREENSHOTS_DIR/$LATEST/all_jobs_closed.json")"
NEW_COUNT="$(( ${ACTIVE_COUNT:-0} + ${CLOSED_COUNT:-0} ))"
[ -z "$ACTIVE_COUNT" ] && NEW_COUNT=""
OLD_COUNT="$(count_jobs "$ENRICHED")"

if [ -z "$NEW_COUNT" ]; then
  echo "✗ $LATEST/all_jobs.json 을 읽을 수 없습니다 (없거나 JSON 배열이 아님)." >&2
  echo "  크롤이 통합 단계까지 못 갔을 수 있습니다. 데이터는 건드리지 않고 중단합니다." >&2
  exit 3
fi

# 기존 파일이 없으면 첫 부트스트랩이므로 비교 없이 통과시킨다.
if [ -n "$OLD_COUNT" ] && [ "$OLD_COUNT" -gt 0 ] && [ "${REFRESH_FORCE:-0}" != "1" ] \
   && [ "$(awk -v n="$NEW_COUNT" -v o="$OLD_COUNT" -v r="$MIN_RATIO" \
          'BEGIN { print (n < o * r) ? 1 : 0 }')" = "1" ]; then
  echo "✗ 공고 건수 급감 감지 — 데이터를 덮어쓰지 않고 중단합니다." >&2
  echo "    기존: ${OLD_COUNT}건  →  새 스냅샷($LATEST): ${NEW_COUNT}건  (기준 ${MIN_RATIO})" >&2
  echo "  확인할 것:" >&2
  echo "    1) 크롤 로그에서 사이트별 수집 0건이 없는지 — $LATEST/summary.txt" >&2
  echo "    2) screenshots/ 에 누적 폴더({site}_{키워드})가 남아 있는지" >&2
  echo "       (새 서버라면 옛 서버의 screenshots/ 를 rsync 로 먼저 가져와야 한다)" >&2
  echo "    3) 의도한 감소라면: REFRESH_FORCE=1 $0" >&2
  exit 3
fi

ln -sfn "$LATEST" all_개발자_latest
echo "latest -> $LATEST (${NEW_COUNT}건 = 모집중 ${ACTIVE_COUNT} + 마감 ${CLOSED_COUNT:-0}${OLD_COUNT:+, 기존 ${OLD_COUNT}건})"

# enrich + mindmap + 회사 기술스택 재빌드
# build_company_stacks 는 company_profiles.json(crawl_company 결과)이 있으면 병합한다.
"$PY" "$SCRIPT_DIR/enrich_jobs.py"
# 근무지 보수 — 크롤이 못 채운 칸을 원본(wanted 상세 API / jobkorea JSON-LD)에서
# 받아 온다. 캐시가 있어 이미 확인한 공고는 다시 조회하지 않는다.
(cd "$ROOT_DIR/catch_capture" && "$PY" -m pipeline.backfill_location) || \
  echo "  [경고] 근무지 보수 실패 — 기존 값으로 계속합니다." >&2

# ── 정본 DB 로 한 벌 만들기 (이관 3단계) ────────────────────
# 여기까지의 JSON 은 **이 서버가 이번에 훑은 것**만 담는다. 정본 DB 는 그보다
# 넓다 — 다른 머신이 모아 온 공고가 얹혀 있고(2026-09-08 기준 7천여 건),
# status·dday 도 저장값이 아니라 읽는 시점에 계산한 값이다. 그래서 8771 검색은
# 2만 4천 건을 답하는데 목록 화면은 1만 7천 건만 보이는 어긋남이 생겼다.
#
# JSON 을 DB 에서 다시 뽑아 **아래 빌더들이 전부 같은 것을 읽게** 한다.
#
# **backfill 은 여기 없다.** 크롤 결과는 aggregate 가 `store.ingest_crawl` 로
# 이미 넣었다(이중 쓰기). backfill 까지 돌리면 같은 데이터가 한 사이클에 두 번
# 들어간다 — 127MB JSON 전량 재적재이고, append-only 인 job_closure_check 에는
# 원장이 통째로 다시 쌓여 공고 14,288건에 175,140행이 되어 있었다(12배).
# 이제 판정한 쪽이 판정한 것만 남긴다(`pipeline.close_check`), 회사 표기 재선정과
# mv_company_stack 갱신도 ingest_crawl 이 맡는다. backfill 은 이관·복구용
# 일회성 도구로 남는다(`python -m store.backfill`).
#
# DB 가 꺼져 있으면 조용히 지나간다 — 방금 만든 스냅샷 JSON 이 그대로 쓰이고
# 사이클은 계속된다. export 는 원자적 교체이고 자체 급감 가드(EXPORT_MIN_RATIO)를
# 들고 있으므로, 반쯤 쓰인 파일이나 갑자기 줄어든 파일이 화면에 닿지 않는다.
(cd "$ROOT_DIR/catch_capture" && "$PY" -m store.export) \
  || echo "  [경고] 정본 DB 반영 실패 — 이번 사이클은 스냅샷 JSON 으로 계속합니다." >&2
"$PY" "$SCRIPT_DIR/build_mindmap.py"
"$PY" "$SCRIPT_DIR/build_company_stacks.py"
# 회사 규모 색인 — 잡 리스트의 "기업 규모" 필터가 읽는 얇은 파일(공고 1건 회사 포함)
"$PY" "$SCRIPT_DIR/build_company_meta.py"
# 기술별 추천 학습 영상(YouTube) — company_stacks.json 의 기술 목록을 소비. 캐시로 증분 수집.
"$PY" "$SCRIPT_DIR/build_learning.py"
# 모집 캘린더 — JD 본문의 접수/모집기간·마감 표기를 파싱해 job_calendar.json 생성
"$PY" "$SCRIPT_DIR/build_calendar.py"
# 개발 트렌드 — 날짜별 스냅샷에서 기술 수요 시계열(trends.json) 집계
"$PY" "$SCRIPT_DIR/build_trends.py"
# 기술 관계·맥락 — 동시출현(스택 레이어) 집계(LLM context/domains 는 보존)
"$PY" "$SCRIPT_DIR/build_tech_relations.py"
# 직군별 인사이트 — 직군(수식어)별 산업·경력·학력·우대사항·자격요건 취합(role_insights.json)
"$PY" "$SCRIPT_DIR/build_role_insights.py"
