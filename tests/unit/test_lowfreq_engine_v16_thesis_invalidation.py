from __future__ import annotations

from neotrade3.decision_engine.thesis_invalidation import build_thesis_invalidation_snapshot


def test_build_thesis_invalidation_snapshot_accepts_stop_loss_breach_with_early_window() -> None:
    snapshot = build_thesis_invalidation_snapshot(
        buy_price=100.0,
        sell_price=94.0,
        stop_loss_pct=-5.0,
        hold_days=3,
    )

    assert snapshot is not None
    assert snapshot["condition_pass"] is True
    assert snapshot["invalidated_window"] == "early"
    assert snapshot["current_return_pct"] == -6.0
    assert snapshot["details"] == "建仓早期硬证伪退出：跌破买入价-6.0%（阈值-5.0%）"


def test_build_thesis_invalidation_snapshot_uses_late_window_at_or_above_twelve_days() -> None:
    snapshot = build_thesis_invalidation_snapshot(
        buy_price=100.0,
        sell_price=95.0,
        stop_loss_pct=-5.0,
        hold_days=12,
    )

    assert snapshot is not None
    assert snapshot["invalidated_window"] == "late"
    assert snapshot["window_label"] == "持仓期"
    assert snapshot["details"] == "持仓期硬证伪退出：跌破买入价-5.0%（阈值-5.0%）"


def test_build_thesis_invalidation_snapshot_returns_none_when_return_is_above_threshold() -> None:
    assert (
        build_thesis_invalidation_snapshot(
            buy_price=100.0,
            sell_price=96.0,
            stop_loss_pct=-5.0,
            hold_days=5,
        )
        is None
    )


def test_build_thesis_invalidation_snapshot_returns_none_for_non_positive_buy_price() -> None:
    assert (
        build_thesis_invalidation_snapshot(
            buy_price=0.0,
            sell_price=94.0,
            stop_loss_pct=-5.0,
            hold_days=5,
        )
        is None
    )


def test_build_thesis_invalidation_snapshot_preserves_negative_hold_days_as_early_window() -> None:
    snapshot = build_thesis_invalidation_snapshot(
        buy_price=100.0,
        sell_price=94.0,
        stop_loss_pct=-5.0,
        hold_days=-1,
    )

    assert snapshot is not None
    assert snapshot["hold_days"] == -1
    assert snapshot["invalidated_window"] == "early"
