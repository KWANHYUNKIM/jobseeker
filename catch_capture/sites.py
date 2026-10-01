"""채용 사이트 등록부 — 사이트 목록의 단일 소스.

예전에는 같은 목록이 여섯 군데(crawl_all SOURCES · auto_crawl KEYWORD_SITES/AGNOSTIC_SITES ·
aggregate SITES · ingest.crawl SITES · backfill SITES · close_check CHECKERS)에 따로 있어서,
사이트 하나를 더하면 어디 한 곳을 빠뜨리기 쉬웠다(빠진 곳에서는 조용히 무시된다).

순서가 뜻을 갖는다: **사이트 간 중복의 대표를 고르는 순서**다(aggregate 와 DB 의 job_dup 뷰).
새 사이트는 여기 한 줄을 더하고, DB enum(job_site)·close_check 판정기·뷰어 Site 타입을
맞춘다 — tests/test_sites.py 가 넷을 대조한다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    key: str            # 폴더·DB·뷰어가 쓰는 이름(screenshots/<key>_<키워드>/)
    script: str         # crawlers/ 아래 크롤러
    keyword_based: bool  # 키워드마다 검색하나. 아니면 보드 전체를 훑어 사이클당 한 번
    label: str


# 중복 대표 순서(위가 먼저).
SITES: tuple[Site, ...] = (
    Site("wanted", "crawl_wanted.py", True, "원티드"),
    Site("jumpit", "crawl_jumpit.py", True, "점핏"),
    Site("jobkorea", "crawl_jobkorea.py", True, "잡코리아"),
    Site("saramin", "crawl_saramin.py", True, "사람인"),
    Site("dev", "crawl_dev.py", True, "캐치"),
    Site("remote", "crawl_remote.py", False, "해외 원격 보드(RemoteOK·WWR·Himalayas)"),
    Site("ats", "crawl_ats.py", False, "회사 채용페이지(Greenhouse·Lever·Ashby)"),
)

SITE_KEYS: tuple[str, ...] = tuple(s.key for s in SITES)
BY_KEY: dict[str, Site] = {s.key: s for s in SITES}

# 크롤 순서. 무거운 Playwright 사이트(캐치·잡코리아)를 앞에 둬 차단 백오프가 걸려도
# 뒤 사이트가 굶지 않게 한다 — 예전 KEYWORD_SITES 순서 그대로다.
_CRAWL_ORDER = ("dev", "jobkorea", "jumpit", "saramin", "wanted", "remote", "ats")
KEYWORD_SITES: list[str] = [k for k in _CRAWL_ORDER if BY_KEY[k].keyword_based]
AGNOSTIC_SITES: list[str] = [k for k in _CRAWL_ORDER if not BY_KEY[k].keyword_based]
KEYWORD_AGNOSTIC: frozenset[str] = frozenset(AGNOSTIC_SITES)

assert set(_CRAWL_ORDER) == set(SITE_KEYS), "크롤 순서와 등록부가 어긋났다"
