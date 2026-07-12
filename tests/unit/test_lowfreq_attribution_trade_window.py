from __future__ import annotations

from neotrade3.analysis.attribution_trade_window import build_attribution_trade_window


def test_build_attribution_trade_window_sorts_trades_before_deriving_first_fields() -> None:
    out = build_attribution_trade_window(
        [
            {"buy_date": "2025-09-03", "sell_date": "2025-09-04", "sell_reason": "late_exit"},
            {"buy_date": "2025-09-01", "sell_date": "2025-09-02", "sell_reason": "early_exit"},
        ],
        segment_start_date="2025-09-01",
        segment_top_date="2025-09-03",
    )

    assert [item["buy_date"] for item in out["code_trades"]] == ["2025-09-01", "2025-09-03"]
    assert [item["buy_date"] for item in out["relevant_trades"]] == ["2025-09-01", "2025-09-03"]
    assert out["first_buy_date"] == "2025-09-01"
    assert out["first_sell_date"] == "2025-09-02"


def test_build_attribution_trade_window_derives_overlap_hold_and_latest_exit_reason() -> None:
    out = build_attribution_trade_window(
        [
            {"buy_date": "2025-09-01", "sell_date": "2025-09-06", "sell_reason": "take_profit"},
            {"buy_date": "2025-09-04", "sell_date": "", "sell_reason": ""},
            {"buy_date": "2025-09-07", "sell_date": "2025-09-08", "sell_reason": "too_late"},
        ],
        segment_start_date="2025-09-02",
        segment_top_date="2025-09-05",
    )

    assert [item["buy_date"] for item in out["relevant_trades"]] == ["2025-09-01", "2025-09-04"]
    assert out["bought"] is True
    assert out["held_to_top"] is True
    assert out["latest_exit_reason"] == "take_profit"


def test_build_attribution_trade_window_returns_empty_defaults_without_relevant_trade() -> None:
    out = build_attribution_trade_window(
        [
            {"buy_date": "2025-08-30", "sell_date": "2025-09-01", "sell_reason": "old_trade"},
            {"buy_date": "2025-09-08", "sell_date": "2025-09-09", "sell_reason": "future_trade"},
        ],
        segment_start_date="2025-09-03",
        segment_top_date="2025-09-05",
    )

    assert out["relevant_trades"] == []
    assert out["bought"] is False
    assert out["held_to_top"] is False
    assert out["first_buy_date"] == ""
    assert out["first_sell_date"] == ""
    assert out["latest_exit_reason"] == ""
