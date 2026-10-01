"""공고 목록의 고정값.

지역 목록의 원본은 뷰어 `src/features/jobs/utils/region.ts` 의 REGION_OPTIONS 이고, 값을
채우는 쪽은 파이프라인의 `store/jobs/facets.py` 다. 셋이 어긋나면 칩이 사라지므로
`tests/features/jobs/test_constants.py` 가 TS 원본과 대조한다.
"""
from __future__ import annotations

REGIONS = ["서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
           "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
REGION_OPTIONS = [*REGIONS, "해외·원격", "정보없음"]
COMPANY_SIZES = ["대기업", "중견기업", "중소기업"]

# 한 요청이 통째로 DB 를 훑어가지 못하게 막는 상한.
MAX_QUERY_CHARS = 200
PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 200
SEMANTIC_HITS = 100          # 의미 검색으로 먼저 뽑아 올 후보 수(그 안에서 필터를 건다)

# 목록에는 본문을 싣지 않는다. 184MB 중 90% 가 이 다섯 필드다(full_jd 만 115MB) —
# 상세 화면에서 한 건씩 받는다.
HEAVY_FIELDS = ("full_jd", "main_tasks", "qualifications", "preferences", "benefits")
