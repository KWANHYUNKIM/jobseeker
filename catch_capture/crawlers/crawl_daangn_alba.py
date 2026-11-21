"""옛 입구 — 당근알바 하나만 받던 크롤러. 지금은 출처 다섯 곳을 도는 crawl_alba 로 넘긴다.

맥에 이미 깔린 launchd(com.jobseeker.albacheck)가 `python -m crawlers.crawl_daangn_alba --check` 를
부르고 있어서 남겨 둔다 — deploy/setup-crawler.sh 를 다시 돌리면 crawl_alba 를 부르게 바뀐다.
당근 파서는 crawlers/alba/daangn.py, 분류 규칙은 crawlers/alba/common.py 로 옮겼다.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))  # catch_capture 루트

from crawlers.alba.common import classify, is_candidate  # noqa: E402,F401 — 옛 이름 그대로
from crawlers.alba.daangn import parse_detail, parse_sitemap, split_loc  # noqa: E402,F401
from crawlers.crawl_alba import check, main, run  # noqa: E402,F401

if __name__ == "__main__":
    main()
