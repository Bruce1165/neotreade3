from __future__ import annotations

from neotrade3.decision_engine.chase_entry import build_chase_entry_snapshot


def test_build_chase_entry_snapshot_returns_none_when_disabled() -> None:
    snapshot = build_chase_entry_snapshot(
        enabled=False,
        closes=[10.0, 10.2, 10.4, 10.6, 10.8],
        ref_price=11.0,
        near_high_ratio=0.98,
        pre3_threshold=8.0,
        pre5_threshold=12.0,
    )

    assert snapshot is None


def test_build_chase_entry_snapshot_returns_none_for_non_positive_ref_price() -> None:
    snapshot = build_chase_entry_snapshot(
        enabled=True,
        closes=[10.0, 10.2, 10.4, 10.6, 10.8],
        ref_price=0.0,
        near_high_ratio=0.98,
        pre3_threshold=8.0,
        pre5_threshold=12.0,
    )

    assert snapshot is None


def test_build_chase_entry_snapshot_returns_none_for_insufficient_history() -> None:
    snapshot = build_chase_entry_snapshot(
        enabled=True,
        closes=[10.0, 10.2, 10.4, 10.6],
        ref_price=11.0,
        near_high_ratio=0.98,
        pre3_threshold=8.0,
        pre5_threshold=12.0,
    )

    assert snapshot is None


def test_build_chase_entry_snapshot_blocks_near_high_with_fast_runup() -> None:
    snapshot = build_chase_entry_snapshot(
        enabled=True,
        closes=[11.8, 11.6, 11.4, 11.2, 11.0, 10.8, 10.6, 10.4, 10.2, 10.0],
        ref_price=11.7,
        near_high_ratio=0.98,
        pre3_threshold=8.0,
        pre5_threshold=12.0,
    )

    assert snapshot is not None
    assert snapshot["blocked"] is True
    assert snapshot["near_high_flag"] is True
    assert snapshot["recent_runup_flag"] is True
    assert snapshot["near_5d_high"] is True
    assert snapshot["near_10d_high"] is True


def test_build_chase_entry_snapshot_does_not_block_near_high_without_enough_runup() -> None:
    snapshot = build_chase_entry_snapshot(
        enabled=True,
        closes=[11.55, 11.5, 11.45, 11.4, 11.3, 11.2, 11.1, 11.0, 10.9, 10.8],
        ref_price=11.5,
        near_high_ratio=0.98,
        pre3_threshold=8.0,
        pre5_threshold=12.0,
    )

    assert snapshot is not None
    assert snapshot["near_high_flag"] is True
    assert snapshot["recent_runup_flag"] is False
    assert snapshot["blocked"] is False


def test_build_chase_entry_snapshot_does_not_block_runup_without_near_high() -> None:
    snapshot = build_chase_entry_snapshot(
        enabled=True,
        closes=[13.0, 12.5, 12.0, 11.5, 11.0, 11.2, 8.0, 8.1, 8.2, 8.3],
        ref_price=10.3,
        near_high_ratio=0.98,
        pre3_threshold=10.0,
        pre5_threshold=15.0,
    )

    assert snapshot is not None
    assert snapshot["near_high_flag"] is False
    assert snapshot["recent_runup_flag"] is True
    assert snapshot["blocked"] is False


def test_build_chase_entry_snapshot_preserves_details_copy_and_rounding() -> None:
    snapshot = build_chase_entry_snapshot(
        enabled=True,
        closes=[11.8, 11.6, 11.4, 11.2, 11.0, 10.8, 10.6, 10.4, 10.2, 10.0],
        ref_price=11.7,
        near_high_ratio=0.98,
        pre3_threshold=8.0,
        pre5_threshold=12.0,
    )

    assert snapshot is not None
    assert snapshot["pre3_return_pct"] == 12.5
    assert snapshot["pre5_return_pct"] == 8.33
    assert snapshot["details"] == "追高型买点硬禁：近5日高位=是 | 近10日高位=是 | 前3日涨幅12.5% | 前5日涨幅8.3%"
