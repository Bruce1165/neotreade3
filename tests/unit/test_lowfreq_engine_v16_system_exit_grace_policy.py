from __future__ import annotations

from neotrade3.decision_engine.system_exit_grace import (
    is_eligible_for_system_exit_grace,
    is_leader_hold_candidate,
    profit_keep_ratio,
    resolve_buy_progress_label,
    system_exit_grace_thresholds,
)


def test_resolve_buy_progress_label_prefers_explicit_label() -> None:
    assert (
        resolve_buy_progress_label(
            signal_label="早窗",
            trade_label="前置布局",
            signal_wave_phase="1浪",
            trade_wave_phase="3浪",
        )
        == "早窗"
    )


def test_resolve_buy_progress_label_maps_wave1_to_pre_layout() -> None:
    assert resolve_buy_progress_label(signal_wave_phase="1浪") == "前置布局"


def test_resolve_buy_progress_label_maps_wave3_to_early_window() -> None:
    assert resolve_buy_progress_label(trade_wave_phase="3浪") == "早窗"


def test_profit_keep_ratio_returns_zero_when_peak_return_is_not_positive() -> None:
    assert profit_keep_ratio(current_return_pct=10.0, peak_return_pct=0.0) == 0.0


def test_system_exit_grace_thresholds_returns_sector_tuple() -> None:
    assert system_exit_grace_thresholds(
        scope="sector",
        market_min_peak_return_pct=20.0,
        market_min_current_profit_pct=10.0,
        market_min_profit_keep_ratio=0.5,
        sector_min_peak_return_pct=12.0,
        sector_min_current_profit_pct=11.0,
        sector_min_profit_keep_ratio=0.6,
        sector_max_hold_days=8,
    ) == (12.0, 11.0, 0.6, 8)


def test_system_exit_grace_thresholds_returns_market_tuple() -> None:
    assert system_exit_grace_thresholds(
        scope="market",
        market_min_peak_return_pct=20.0,
        market_min_current_profit_pct=10.0,
        market_min_profit_keep_ratio=0.5,
        sector_min_peak_return_pct=12.0,
        sector_min_current_profit_pct=11.0,
        sector_min_profit_keep_ratio=0.6,
        sector_max_hold_days=8,
    ) == (20.0, 10.0, 0.5, 0)


def test_is_leader_hold_candidate_requires_leader_role_and_peak_return() -> None:
    assert is_leader_hold_candidate(role="龙头", peak_return_pct=18.0, leader_hold_min_peak_return_pct=15.0) is True
    assert is_leader_hold_candidate(role="中军", peak_return_pct=18.0, leader_hold_min_peak_return_pct=15.0) is False


def test_is_eligible_for_system_exit_grace_accepts_valid_market_leader_case() -> None:
    assert (
        is_eligible_for_system_exit_grace(
            enabled=True,
            grace_used=False,
            scope="market",
            role="龙头",
            sell_price=110.0,
            peak_return_pct=20.0,
            buy_progress_label="早窗",
            current_return_pct=10.0,
            min_peak_return_pct=18.0,
            legacy_market_min_peak_return_pct=20.0,
            min_current_profit_pct=10.0,
            min_profit_keep_ratio=0.5,
            max_hold_days=0,
            hold_days=6,
            require_positive_return=True,
            leader_hold_candidate=True,
        )
        is True
    )


def test_is_eligible_for_system_exit_grace_rejects_non_early_label() -> None:
    assert (
        is_eligible_for_system_exit_grace(
            enabled=True,
            grace_used=False,
            scope="market",
            role="龙头",
            sell_price=110.0,
            peak_return_pct=20.0,
            buy_progress_label="其它",
            current_return_pct=10.0,
            min_peak_return_pct=18.0,
            legacy_market_min_peak_return_pct=20.0,
            min_current_profit_pct=10.0,
            min_profit_keep_ratio=0.5,
            max_hold_days=0,
            hold_days=6,
            require_positive_return=True,
            leader_hold_candidate=True,
        )
        is False
    )


def test_is_eligible_for_system_exit_grace_rejects_low_profit_keep_ratio() -> None:
    assert (
        is_eligible_for_system_exit_grace(
            enabled=True,
            grace_used=False,
            scope="market",
            role="龙头",
            sell_price=112.0,
            peak_return_pct=40.0,
            buy_progress_label="早窗",
            current_return_pct=12.0,
            min_peak_return_pct=18.0,
            legacy_market_min_peak_return_pct=20.0,
            min_current_profit_pct=10.0,
            min_profit_keep_ratio=0.5,
            max_hold_days=0,
            hold_days=6,
            require_positive_return=True,
            leader_hold_candidate=True,
        )
        is False
    )


def test_is_eligible_for_system_exit_grace_rejects_sector_case_with_excessive_hold_days() -> None:
    assert (
        is_eligible_for_system_exit_grace(
            enabled=True,
            grace_used=False,
            scope="sector",
            role="中军",
            sell_price=124.0,
            peak_return_pct=30.0,
            buy_progress_label="前置布局",
            current_return_pct=24.0,
            min_peak_return_pct=10.0,
            legacy_market_min_peak_return_pct=20.0,
            min_current_profit_pct=10.0,
            min_profit_keep_ratio=0.6,
            max_hold_days=10,
            hold_days=33,
            require_positive_return=True,
            leader_hold_candidate=False,
        )
        is False
    )
