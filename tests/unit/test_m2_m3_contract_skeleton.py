from __future__ import annotations

import pytest

from neotrade3.cycle_intelligence import (
    SMALL_CYCLE_OBJECT_TYPE,
    SmallCycle,
    build_cycle_linkage_state,
    build_small_cycle,
    build_small_cycle_from_m1,
)
from neotrade3.cycle_intelligence.contracts import (
    SMALL_CYCLE_QUALITY_REASON_PF1_WINDOW_NOT_READY,
    SMALL_CYCLE_QUALITY_REASON_SECURITY_DELISTED,
    SMALL_CYCLE_QUALITY_REASON_TARGET_DATE_NOT_TRADING_DAY,
)
from neotrade3.data_control import (
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
)
from neotrade3.decision_engine import (
    ENTRY_STATE_OBJECT_TYPE,
    EXIT_STATE_OBJECT_TYPE,
    HOLD_STATE_OBJECT_TYPE,
    IDENTIFY_STATE_OBJECT_TYPE,
    TRACKING_STATE_OBJECT_TYPE,
    ExitState,
    EntryState,
    HoldState,
    IdentifyState,
    TrackingState,
    build_exit_state,
    build_entry_state,
    build_entry_state_from_formal_inputs,
    build_hold_state,
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


def test_build_m3_hold_exit_states_returns_formal_payloads() -> None:
    hold = build_hold_state(
        stock_code="600000",
        trade_date="2026-07-07",
        status="watch",
        hold_state="review_watch",
        warning_flags=["market_exit_state:review"],
        not_exit_reasons=["系统退出证据尚未达到正式确认门槛"],
        evidence_ref={"noise_evidence": ["market breadth weakening"]},
        m2_cycle_ref={"object_type": "small_cycle", "stock_code": "600000"},
    )
    exit_state = build_exit_state(
        stock_code="600000",
        trade_date="2026-07-07",
        status="exit_ready",
        exit_ready=True,
        exit_scope="position_only",
        exit_reason_type="trend_exhausted",
        exit_attribution_bucket="trend_exhaustion_exit",
        local_exit_semantics="local_end_only",
        global_thesis_end_semantics="needs_global_confirmation",
        evidence_ref={"exit_evidence_bundle": ["trend exhausted"]},
        m2_cycle_ref={"object_type": "small_cycle", "stock_code": "600000"},
    )

    assert isinstance(hold, HoldState)
    hold_payload = hold.to_payload()
    assert hold_payload["object_type"] == HOLD_STATE_OBJECT_TYPE
    assert hold_payload["hold_state"] == "review_watch"
    assert hold_payload["warning_flags"] == ["market_exit_state:review"]

    assert isinstance(exit_state, ExitState)
    exit_payload = exit_state.to_payload()
    assert exit_payload["object_type"] == EXIT_STATE_OBJECT_TYPE
    assert exit_payload["exit_ready"] is True
    assert exit_payload["exit_reason_type"] == "trend_exhausted"


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
    assert payload["quality_status"] == "ok"
    assert payload["quality_reasons"] == []
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
    assert payload["quality_status"] == "blocked"
    assert payload["invalidation"]["status"] == "triggered"
    assert payload["invalidation"]["reasons"] == [SMALL_CYCLE_QUALITY_REASON_PF1_WINDOW_NOT_READY]
    assert payload["quality_reasons"] == [SMALL_CYCLE_QUALITY_REASON_PF1_WINDOW_NOT_READY]


def test_build_small_cycle_from_m1_blocks_when_target_date_not_trading_day() -> None:
    d1, security, trading_day, profile = _sample_m1_objects()
    trading_day = D7TradingDayStatus(
        target_date=trading_day.target_date,
        is_trading_day=False,
        nearest_trading_day=trading_day.nearest_trading_day,
        min_trading_day=trading_day.min_trading_day,
        max_trading_day=trading_day.max_trading_day,
        calendar_covered_until=trading_day.calendar_covered_until,
        calendar_source=trading_day.calendar_source,
    )
    cycle = build_small_cycle_from_m1(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )
    payload = cycle.to_payload()
    assert payload["quality_status"] == "blocked"
    assert payload["invalidation"]["reasons"] == [SMALL_CYCLE_QUALITY_REASON_TARGET_DATE_NOT_TRADING_DAY]


def test_build_small_cycle_from_m1_blocks_when_security_delisted() -> None:
    d1, security, trading_day, profile = _sample_m1_objects()
    security = D7SecurityMasterMinimal(
        stock_code=security.stock_code,
        stock_name=security.stock_name,
        asset_type=security.asset_type,
        is_delisted=True,
        sector_lv1=security.sector_lv1,
        sector_lv2=security.sector_lv2,
        last_trade_date=security.last_trade_date,
    )
    cycle = build_small_cycle_from_m1(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )
    payload = cycle.to_payload()
    assert payload["quality_status"] == "blocked"
    assert payload["invalidation"]["reasons"] == [SMALL_CYCLE_QUALITY_REASON_SECURITY_DELISTED]


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


def test_build_front_states_from_formal_inputs_respects_linkage_blocking() -> None:
    d1, security, trading_day, profile = _sample_m1_objects(return_20d=0.12, positive_days_5d=4)
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
    linkage_state = build_cycle_linkage_state(
        stock_code=cycle.stock_code,
        trade_date=cycle.trade_date,
        small_cycle_ref={
            "object_type": cycle.object_type,
            "stock_code": cycle.stock_code,
            "cycle_state": cycle.cycle_state,
        },
        mid_cycle_ref={
            "fund_cycle_state": "advancing",
            "industry_cycle_state": "advancing",
        },
        linkage_phase="continuation_blocked",
        supports_continuation=False,
        local_end_vs_global_end="possible_global_end",
        confidence={"level": "medium"},
        evidence_bundle={"override": "linkage_blocked_test"},
        rule_version="m2_cycle_linkage.v1alpha1",
    )

    tracking = build_tracking_state_from_formal_inputs(
        cycle=cycle,
        m1_constraints_ref=constraints,
        cycle_linkage_state_ref=linkage_state.to_payload(),
    )
    entry = build_entry_state_from_formal_inputs(
        cycle=cycle,
        m1_constraints_ref=constraints,
        cycle_linkage_state_ref=linkage_state.to_payload(),
    )

    assert tracking.to_payload()["status"] == "tracking"
    assert tracking.to_payload()["maturity"] == "not_ready"
    assert tracking.to_payload()["transition_reason"] == (
        "cycle_linkage_blocks_continuation"
    )
    assert tracking.to_payload()["evidence_ref"]["supports_continuation"] is False
    assert entry.to_payload()["status"] == "not_ready"
    assert entry.to_payload()["decision"] == "wait"
    assert entry.to_payload()["actionable"] is False
    assert "cycle_linkage_blocks_continuation" in entry.to_payload()["blocking_reasons"]
    assert entry.to_payload()["evidence_ref"]["local_end_vs_global_end"] == (
        "possible_global_end"
    )
