from __future__ import annotations

import pytest

from neotrade3.cycle_intelligence import (
    SMALL_CYCLE_OBJECT_TYPE,
    SmallCycle,
    build_small_cycle,
    build_small_cycle_from_m1,
)
from neotrade3.data_control import (
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
)
from neotrade3.decision_engine import (
    ENTRY_STATE_OBJECT_TYPE,
    IDENTIFY_STATE_OBJECT_TYPE,
    TRACKING_STATE_OBJECT_TYPE,
    EntryState,
    IdentifyState,
    TrackingState,
    build_entry_state,
    build_entry_state_from_formal_inputs,
    build_identify_state,
    build_identify_state_from_formal_inputs,
    build_m1_constraints_ref,
    build_tracking_state,
    build_tracking_state_from_formal_inputs,
)


def test_build_small_cycle_returns_formal_payload() -> None:
    cycle = build_small_cycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S1 Emerging",
        state_stability_level="watch",
        evidence_bundle={"price_structure": {"status": "present"}},
        confidence={"level": "low"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[{"from": "S0", "to": "S1"}],
    )

    assert isinstance(cycle, SmallCycle)
    payload = cycle.to_payload()
    assert payload["object_type"] == SMALL_CYCLE_OBJECT_TYPE
    assert payload["stock_code"] == "600000"
    assert payload["cycle_state"] == "S1 Emerging"
    assert payload["evidence_bundle"]["price_structure"]["status"] == "present"
    assert payload["state_transition_log"][0]["to"] == "S1"


def test_build_m3_front_states_returns_formal_payloads() -> None:
    identify = build_identify_state(
        stock_code="600000",
        trade_date="2026-07-07",
        status="identified",
        reason="small_cycle_emerging",
        m2_cycle_ref={"object_type": "small_cycle", "stock_code": "600000"},
    )
    tracking = build_tracking_state(
        stock_code="600000",
        trade_date="2026-07-07",
        status="tracking",
        maturity="observe",
        transition_reason="await_more_confirmation",
        m2_cycle_ref={"object_type": "small_cycle", "stock_code": "600000"},
    )
    entry = build_entry_state(
        stock_code="600000",
        trade_date="2026-07-07",
        status="blocked",
        decision="wait",
        actionable=False,
        blocking_reasons=["m1_constraint_not_ready"],
        m2_cycle_ref={"object_type": "small_cycle", "stock_code": "600000"},
    )

    assert isinstance(identify, IdentifyState)
    assert identify.to_payload()["object_type"] == IDENTIFY_STATE_OBJECT_TYPE

    assert isinstance(tracking, TrackingState)
    tracking_payload = tracking.to_payload()
    assert tracking_payload["object_type"] == TRACKING_STATE_OBJECT_TYPE
    assert tracking_payload["maturity"] == "observe"

    assert isinstance(entry, EntryState)
    entry_payload = entry.to_payload()
    assert entry_payload["object_type"] == ENTRY_STATE_OBJECT_TYPE
    assert entry_payload["actionable"] is False
    assert entry_payload["blocking_reasons"] == ["m1_constraint_not_ready"]


def test_build_small_cycle_requires_key_identifiers() -> None:
    with pytest.raises(ValueError, match="stock_code"):
        build_small_cycle(
            stock_code="",
            trade_date="2026-07-07",
            cycle_state="S0 Neutral",
            state_stability_level="unknown",
        )


def test_build_tracking_state_requires_transition_reason() -> None:
    with pytest.raises(ValueError, match="transition_reason"):
        build_tracking_state(
            stock_code="600000",
            trade_date="2026-07-07",
            status="tracking",
            maturity="observe",
            transition_reason="",
        )


def _sample_m1_objects(*, return_20d: float = 0.12, positive_days_5d: int = 4) -> tuple[
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
]:
    d1 = D1DailyPriceFact(
        stock_code="600000",
        trade_date="2026-07-07",
        open_price=10.0,
        high_price=10.5,
        low_price=9.9,
        close_price=10.3,
        preclose_price=10.0,
        pct_change=2.0,
        volume_shares=1_000_000.0,
        amount_cny=200_000_000.0,
        turnover_rate=3.0,
        updated_at="2026-07-07T15:00:00Z",
    )
    security = D7SecurityMasterMinimal(
        stock_code="600000",
        stock_name="浦发银行",
        asset_type="stock",
        is_delisted=False,
        sector_lv1="金融",
        sector_lv2="银行",
        last_trade_date="2026-07-07",
    )
    trading_day = D7TradingDayStatus(
        target_date="2026-07-07",
        is_trading_day=True,
        nearest_trading_day="2026-07-07",
        min_trading_day="2026-06-01",
        max_trading_day="2026-07-07",
        calendar_covered_until="2026-07-07",
        calendar_source="trading_calendar_cache",
    )
    profile = PF1TradingProfile(
        stock_code="600000",
        as_of_trade_date="2026-07-07",
        latest_amount=220_000_000.0,
        avg_amount_5d=210_000_000.0,
        avg_amount_20d=180_000_000.0,
        latest_turnover=3.1,
        avg_turnover_5d=3.0,
        median_turnover_20d=2.2,
        return_20d=return_20d,
        avg_pct_change_5d=0.8,
        positive_days_5d=positive_days_5d,
        window_5d_ready=True,
        window_20d_ready=True,
    )
    return d1, security, trading_day, profile


def test_build_small_cycle_from_m1_uses_formal_inputs_only() -> None:
    d1, security, trading_day, profile = _sample_m1_objects()

    cycle = build_small_cycle_from_m1(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )

    payload = cycle.to_payload()
    assert payload["cycle_state"] == "S2 Advancing"
    assert payload["evidence_bundle"]["e2_activity"]["status"] == "supported"
    assert payload["evidence_bundle"]["e4_relative_strength"]["status"] == "not_available"
    assert payload["confidence"]["level"] == "high"


def test_build_small_cycle_from_m1_blocks_when_profile_window_missing() -> None:
    d1, security, trading_day, profile = _sample_m1_objects()
    profile = PF1TradingProfile(
        stock_code=profile.stock_code,
        as_of_trade_date=profile.as_of_trade_date,
        latest_amount=profile.latest_amount,
        avg_amount_5d=profile.avg_amount_5d,
        avg_amount_20d=None,
        latest_turnover=profile.latest_turnover,
        avg_turnover_5d=profile.avg_turnover_5d,
        median_turnover_20d=None,
        return_20d=None,
        avg_pct_change_5d=profile.avg_pct_change_5d,
        positive_days_5d=profile.positive_days_5d,
    )

    cycle = build_small_cycle_from_m1(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )

    payload = cycle.to_payload()
    assert payload["cycle_state"] == "S0 Neutral"
    assert payload["invalidation"]["status"] == "triggered"
    assert "pf1_window_not_ready" in payload["invalidation"]["reasons"]


def test_build_front_states_from_formal_inputs_respects_constraints() -> None:
    d1, security, trading_day, profile = _sample_m1_objects(return_20d=0.04, positive_days_5d=3)
    cycle = build_small_cycle_from_m1(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )
    constraints = build_m1_constraints_ref(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )

    identify = build_identify_state_from_formal_inputs(
        cycle=cycle,
        m1_constraints_ref=constraints,
    )
    tracking = build_tracking_state_from_formal_inputs(
        cycle=cycle,
        m1_constraints_ref=constraints,
    )
    entry = build_entry_state_from_formal_inputs(
        cycle=cycle,
        m1_constraints_ref=constraints,
    )

    assert identify.to_payload()["status"] == "identified"
    assert tracking.to_payload()["status"] == "tracking"
    assert tracking.to_payload()["maturity"] == "ready_for_entry"
    assert entry.to_payload()["status"] == "ready"
    assert entry.to_payload()["actionable"] is True


def test_build_front_states_from_formal_inputs_waits_when_cycle_only_emerging() -> None:
    d1, security, trading_day, profile = _sample_m1_objects(return_20d=None if False else 0.12, positive_days_5d=2)
    profile = PF1TradingProfile(
        stock_code=profile.stock_code,
        as_of_trade_date=profile.as_of_trade_date,
        latest_amount=100_000_000.0,
        avg_amount_5d=120_000_000.0,
        avg_amount_20d=180_000_000.0,
        latest_turnover=1.8,
        avg_turnover_5d=1.5,
        median_turnover_20d=2.2,
        return_20d=0.12,
        avg_pct_change_5d=0.2,
        positive_days_5d=2,
        window_5d_ready=True,
        window_20d_ready=True,
    )
    cycle = build_small_cycle_from_m1(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )
    constraints = build_m1_constraints_ref(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )

    tracking = build_tracking_state_from_formal_inputs(
        cycle=cycle,
        m1_constraints_ref=constraints,
    )
    entry = build_entry_state_from_formal_inputs(
        cycle=cycle,
        m1_constraints_ref=constraints,
    )

    assert cycle.to_payload()["cycle_state"] == "S1 Emerging"
    assert tracking.to_payload()["maturity"] == "observe"
    assert entry.to_payload()["status"] == "not_ready"
    assert "tracking_not_mature" in entry.to_payload()["blocking_reasons"]
