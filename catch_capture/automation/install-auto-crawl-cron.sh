#!/usr/bin/env bash
# 크롤 오케스트레이터 keep-alive cron 설치 (idempotent) — 통합된 단일 cron.
#
# auto_crawl 데몬 하나가 모든 주기 작업을 오케스트레이션한다:
#   크롤 5사이트 → 통합/마감분류 → 기술블로그 → (새 데이터면) 대시보드+jd-viewer 데이터 갱신
#   → 기술 스택 레이더 점진 리파인(claude) → 공개 면접 후기 적응형 데몬 보장 → 학습영상 6h 재수집
# 따라서 learning/radar/reviews 용 개별 cron 은 더 이상 필요 없다(여기로 통합).
#
#   - @reboot: 부팅 시 오케스트레이터 시작
#   - 매시간: 멱등 start(이미 살아있으면 no-op) → 죽었으면 자동 복구
# 다시 실행해도 중복 등록되지 않는다. 제거: crontab -e 에서 해당 줄 삭제 후
#   python catch_capture/automation/auto_crawl.py stop.
set -euo pipefail

SCRIPT="/Users/kwanhyun/jobseeker/catch_capture/automation/start-auto-crawl.sh"
MARKER="# jobseeker-auto-crawl"

chmod +x "$SCRIPT"

# 통합 전 흩어져 있던 개별 작업 cron 마커들도 함께 제거한다.
current="$(crontab -l 2>/dev/null \
  | grep -vE 'jobseeker-auto-crawl|jobseeker-learning-refresh|jobseeker-radar-refresh|jobseeker-reviews-daemon' || true)"
{
  [ -n "$current" ] && printf '%s\n' "$current"
  printf '@reboot %s %s\n' "$SCRIPT" "$MARKER"
  printf '0 * * * * %s %s\n' "$SCRIPT" "$MARKER"
} | crontab -

echo "설치 완료(개별 learning/radar/reviews cron 은 정리됨). 현재 crontab:"
crontab -l
echo
echo "상태: python catch_capture/automation/auto_crawl.py status"
echo "로그: python catch_capture/automation/auto_crawl.py logs 50"
