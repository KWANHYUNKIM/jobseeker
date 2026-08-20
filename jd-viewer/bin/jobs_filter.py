"""공고 목록에서 '지금 시장'만 골라내는 공용 필터.

`all_jobs_enriched.json` 은 이제 모집중과 마감을 **함께** 담는다. 마감을 파일에서
빼버리면 색인·유사공고·과거 조회가 통째로 사라지기 때문이다. 대신 읽는 쪽이 목적에
맞게 고른다.

- 수요 분석(무엇을 요구하는가, 어떤 스택을 쓰는가)은 `active_only()` 를 쓴다.
  두 달 전에 끝난 공고를 현재 수요로 세면 트렌드가 과거에 눌린다.
- 색인·검색·재공고 추적처럼 '있었던 일'을 다루는 쪽은 전체를 그대로 쓴다.

status 가 없는 예전 파일도 그냥 통과시킨다(빈 결과보다 낫다).
"""
from __future__ import annotations


def active_only(jobs: list[dict]) -> list[dict]:
    if not jobs:
        return jobs
    if not any("status" in j for j in jobs[:50]):
        return jobs                      # status 이전 포맷 — 거를 근거가 없다
    return [j for j in jobs if (j.get("status") or "active") != "closed"]
