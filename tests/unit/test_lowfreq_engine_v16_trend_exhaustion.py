from __future__ import annotations

from neotrade3.decision_engine.trend_exhaustion import build_trend_exhaustion_snapshot


def test_build_trend_exhaustion_snapshot_accepts_profitable_matured_drawdown_case() -> None:
    snapshot = build_trend_exhaustion_snapshot(
        buy_price=100.0,
        peak_price=130.0,
        current_price=116.0,
        hold_days=20,
        buy_progress_label="其它",
        trailing_profit_level=20.0,
        partial_profit_level=25.0,
        trailing_stop_pct=-5.0,
        min_hold_days=15,
    )

    assert snapshot is not None
    assert snapshot["armed"] is True
    assert snapshot["drawdown_from_peak_triggered"] is True
    assert snapshot["hold_ready"] is True
    assert snapshot["condition_pass"] is True


def test_build_trend_exhaustion_snapshot_rejects_before_min_hold_days() -> None:
    snapshot = build_trend_exhaustion_snapshot(
        buy_price=100.0,
        peak_price=130.0,
        current_price=116.0,
        hold_days=8,
        buy_progress_label="其它",
        trailing_profit_level=20.0,
        partial_profit_level=25.0,
        trailing_stop_pct=-5.0,
        min_hold_days=15,
    )

    assert snapshot is not None
    assert snapshot["hold_ready"] is False
    assert snapshot["condition_pass"] is False


def test_build_trend_exhaustion_snapshot_rejects_early_quality_entry() -> None:
    snapshot = build_trend_exhaustion_snapshot(
        buy_price=100.0,
        peak_price=130.0,
        current_price=116.0,
        hold_days=20,
        buy_progress_label="早窗",
        trailing_profit_level=20.0,
        partial_profit_level=25.0,
        trailing_stop_pct=-5.0,
        min_hold_days=15,
    )

    assert snapshot is not None
    assert snapshot["early_quality_entry"] is True
    assert snapshot["condition_pass"] is False


def test_build_trend_exhaustion_snapshot_rejects_non_positive_current_profit() -> None:
    snapshot = build_trend_exhaustion_snapshot(
        buy_price=100.0,
        peak_price=130.0,
        current_price=98.0,
        hold_days=20,
        buy_progress_label="其它",
        trailing_profit_level=20.0,
        partial_profit_level=25.0,
        trailing_stop_pct=-5.0,
        min_hold_days=15,
    )

    assert snapshot is not None
    assert snapshot["current_profit_positive"] is False
    assert snapshot["condition_pass"] is False


def test_build_trend_exhaustion_snapshot_returns_none_for_non_positive_prices() -> None:
    assert (
        build_trend_exhaustion_snapshot(
            buy_price=0.0,
            peak_price=130.0,
            current_price=116.0,
            hold_days=20,
            buy_progress_label="其它",
            trailing_profit_level=20.0,
            partial_profit_level=25.0,
            trailing_stop_pct=-5.0,
            min_hold_days=15,
        )
        is None
    )
    assert (
        build_trend_exhaustion_snapshot(
            buy_price=100.0,
            peak_price=130.0,
            current_price=0.0,
            hold_days=20,
            buy_progress_label="其它",
            trailing_profit_level=20.0,
            partial_profit_level=25.0,
            trailing_stop_pct=-5.0,
            min_hold_days=15,
        )
        is None
    )


def test_build_trend_exhaustion_snapshot_falls_back_peak_price_to_buy_price() -> None:
    snapshot = build_trend_exhaustion_snapshot(
        buy_price=100.0,
        peak_price=0.0,
        current_price=105.0,
        hold_days=20,
        buy_progress_label="其它",
        trailing_profit_level=20.0,
        partial_profit_level=25.0,
        trailing_stop_pct=-5.0,
        min_hold_days=15,
    )

    assert snapshot is not None
    assert snapshot["peak_return_pct"] == 0.0
    assert snapshot["drawdown_from_peak_pct"] == 5.0
