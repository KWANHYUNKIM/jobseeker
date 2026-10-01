"""공고 API 의 요청 형식.

응답 본문(Job)은 뷰어 `types.ts` 의 Job 그대로라 `mapping.row_to_job` 이 만든다 —
여기에 같은 필드를 다시 적으면 세 번째 사본이 된다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import Query

from app.features.jobs.constants import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX
from app.utils.text import split_multi

Closed = Literal["hide", "show", "only"]
Unverified = Literal["show", "hide"]


@dataclass
class JobsQuery:
    """`/api/jobs` 의 질의. 이름은 뷰어 `features/jobs/api.ts` 의 toParams 와 같아야 한다
    (tests/features/jobs/test_contract.py 가 양쪽을 대조한다)."""

    site: list[str]
    career: list[str]
    stack: list[str]
    role: list[str]
    region: list[str]
    district: list[str]
    size: list[str]
    q: str
    semantic: bool
    closed: Closed
    unverified: Unverified
    page: int
    limit: int

    def cache_key(self) -> tuple:
        def norm(v: list[str]) -> tuple:
            return tuple(sorted(split_multi(v)))
        return (norm(self.site), norm(self.career), norm(self.stack), norm(self.role),
                norm(self.region), norm(self.district), norm(self.size), self.q, self.semantic,
                self.closed, self.unverified, self.page, self.limit)


def jobs_query(
    site: list[str] = Query([], description="사이트(wanted, saramin …). 여러 번 또는 쉼표"),
    career: list[str] = Query([], description="경력 구간(신입/무관, 1-2년 …)"),
    stack: list[str] = Query([], description="기술 스택 — 고른 것을 **전부** 가진 공고"),
    role: list[str] = Query([], description="직군(백엔드 …) — 하나라도 맞으면"),
    region: list[str] = Query([], description="시도(서울 …)"),
    district: list[str] = Query([], description="시군구(지역을 하나 골랐을 때)"),
    size: list[str] = Query([], description="회사 규모(대기업·중견기업·중소기업)"),
    q: str = Query("", description="검색어 — 회사·제목·본문 부분일치"),
    semantic: bool = Query(False, description="검색어를 의미 검색(하이브리드)으로"),
    closed: Closed = "hide",
    unverified: Unverified = "show",
    page: int = Query(1, ge=1),
    limit: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
) -> JobsQuery:
    return JobsQuery(site, career, stack, role, region, district, size, q, semantic, closed,
                     unverified, page, limit)
