"""크롤 회차의 진입점이 불러와지는가 — 문법 오류 하나가 회차 전체를 멈춘다.

2026-11-21: 공모전 단계를 붙이며 crawl_all.py 의 print(f"\n…") 이 실제 줄바꿈으로 들어가 커밋됐고,
부가 단계 시험들은 crawl_all 을 import 하지 않아 아무도 못 잡았다. launchd 의 다음 회차부터 크롤이 통째로 죽는다.
"""
import importlib

import pytest


@pytest.mark.parametrize("mod", ["automation.crawl_all", "automation.auto_crawl", "automation.loops",
                                 "crawlers.crawl_alba", "crawlers.crawl_contests", "crawlers.crawl_daangn_alba"])
def test_cycle_entry_points_import(mod):
    importlib.import_module(mod)
