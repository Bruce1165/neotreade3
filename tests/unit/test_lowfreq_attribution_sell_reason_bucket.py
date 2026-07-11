from __future__ import annotations

from neotrade3.analysis.attribution_reasoning import resolve_sell_reason_bucket


def test_resolve_sell_reason_bucket_maps_current_contract() -> None:
    assert resolve_sell_reason_bucket("回测结束平仓") == "回测结束平仓"
    assert resolve_sell_reason_bucket("回测结束平仓（清仓）") == "回测结束平仓"
    assert resolve_sell_reason_bucket("板块见顶确认：AI退潮") == "sector_top_confirmed"
    assert resolve_sell_reason_bucket("创业板见顶确认候选：趋势转弱=是 | 广度转弱=是") == "market_top_confirmed"
    assert resolve_sell_reason_bucket("创业板见顶：广度转弱") == "market_top_confirmed"
    assert resolve_sell_reason_bucket("早窗硬证伪退出：跌破买入价-5.2%（阈值-5.0%）") == "thesis_invalidated"
    assert resolve_sell_reason_bucket("跌破买入价止损：-5.1%") == "thesis_invalidated"


def test_resolve_sell_reason_bucket_keeps_other_fallback() -> None:
    assert resolve_sell_reason_bucket("自定义原因") == "other"
