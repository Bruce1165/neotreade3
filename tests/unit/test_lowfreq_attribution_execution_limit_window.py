from __future__ import annotations

from neotrade3.analysis.attribution_execution_limit_window import is_execution_limit_up_window


def test_is_execution_limit_up_window_returns_false_for_empty_bars() -> None:
    assert is_execution_limit_up_window(bars=[], limit_up_pct=9.8, one_price_only=False) is False


def test_is_execution_limit_up_window_returns_true_when_all_bars_hit_limit_up() -> None:
    bars = [
        {"pct_change": 10.0, "high": 10.98, "low": 10.98, "close": 10.98},
        {"pct_change": 9.9, "high": 12.08, "low": 12.08, "close": 12.08},
        {"pct_change": 10.1, "high": 13.29, "low": 13.29, "close": 13.29},
    ]

    assert is_execution_limit_up_window(bars=bars, limit_up_pct=9.8, one_price_only=False) is True


def test_is_execution_limit_up_window_returns_false_when_any_bar_misses_limit_up() -> None:
    bars = [
        {"pct_change": 10.0, "high": 10.98, "low": 10.98, "close": 10.98},
        {"pct_change": 3.2, "high": 10.5, "low": 10.2, "close": 10.3},
    ]

    assert is_execution_limit_up_window(bars=bars, limit_up_pct=9.8, one_price_only=False) is False


def test_is_execution_limit_up_window_respects_one_price_only() -> None:
    bars = [
        {"pct_change": 10.0, "high": 11.2, "low": 10.5, "close": 10.98},
        {"pct_change": 10.0, "high": 10.98, "low": 10.98, "close": 10.98},
    ]

    assert is_execution_limit_up_window(bars=bars, limit_up_pct=9.8, one_price_only=True) is False
