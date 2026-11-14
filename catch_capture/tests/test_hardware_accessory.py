"""crawl_hardware.drop_accessories — 그래픽카드 분류에 섞여 오는 액세서리를 뺀다."""
from __future__ import annotations

from crawlers.crawl_hardware import drop_accessories

GPU = {"id": "gpu-rtx-4090", "category": "gpu", "perf": {"index": 100}}


def _o(name: str, price: int) -> dict:
    return {"name": name, "price": price, "pcode": "1", "rank": 1}


def test_drops_named_accessories():
    offers = [
        _o("PCIE 4.0 X16 라이저 케이블 RTX 4090", 438_100),
        _o("12cm 팬 위치 그래픽 카드 홀더 RTX 4090 처짐 방지", 199_700),
        _o("갤럭시 RTX4090 시리즈 그래픽카드 팬 수리 교체 쿨러", 180_000),
        _o("RTX 4090 OC 24GB ROG Strix", 3_500_000),
    ]
    assert [o["name"] for o in drop_accessories(offers, GPU)] == ["RTX 4090 OC 24GB ROG Strix"]


def test_price_floor_for_fast_gpus_only():
    cheap = [_o("ZOTAC RTX4090 Apocalypse용 GPU 쿨러 팬", 42_830)]
    assert drop_accessories(cheap, GPU) == []
    slow = {"category": "gpu", "perf": {"index": 8}}          # GT 급은 10만원 아래도 진짜 카드다
    assert drop_accessories([_o("GT 1030 2GB", 89_000)], slow)


def test_other_categories_untouched():
    ssd = {"category": "ssd", "perf": {"index": 50}}
    assert drop_accessories([_o("990 PRO 2TB 케이블 포함", 30_000)], ssd)


def test_forget_junk_clears_all_accessory_record():
    from crawlers.crawl_hardware import _forget_junk
    rec = {"day": "2026-11-12", "min": 9970, "median": 56400, "n": 2,
           "offers": [_o("RTX 4090 그래픽 카드 홀더", 9970), _o("RTX 4090 라이저 케이블", 43810)],
           "history": [{"d": "2026-11-11", "min": 2_000_000}, {"d": "2026-11-12", "min": 9970}]}
    assert _forget_junk(rec, GPU) == "2026-11-12"
    assert "min" not in rec and "offers" not in rec
    assert rec["history"] == [{"d": "2026-11-11", "min": 2_000_000}]


def test_relative_floor_drops_far_below_median():
    offers = [_o(f"RX 7900 XTX 24GB {i}", 1_300_000 + i * 10_000) for i in range(5)] + [_o("RX 7900 XTX 헬하운드", 163_190)]
    assert all(o["price"] > 1_000_000 for o in drop_accessories(offers, GPU))
