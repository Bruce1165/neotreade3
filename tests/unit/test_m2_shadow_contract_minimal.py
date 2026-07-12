from __future__ import annotations

from neotrade3.cycle_intelligence import (
    CYCLE_LINKAGE_STATE_OBJECT_TYPE,
    GROWTH_POTENTIAL_PROFILE_OBJECT_TYPE,
    MID_CYCLE_STATE_OBJECT_TYPE,
    SMALL_CYCLE_WAVE_HYPOTHESIS_OBJECT_TYPE,
    TOP_RISK_PROFILE_OBJECT_TYPE,
    build_shadow_cycle_intelligence_from_m1,
    build_small_cycle,
)
from neotrade3.data_control import D7SecurityMasterMinimal, PF1TradingProfile


def _build_reference_inputs():
    cycle = build_small_cycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[{"from": "S1 Emerging", "to": "S2 Advancing"}],
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
    profile = PF1TradingProfile(
        stock_code="600000",
        as_of_trade_date="2026-07-07",
        latest_amount=220_000_000.0,
        avg_amount_5d=210_000_000.0,
        avg_amount_20d=180_000_000.0,
        latest_turnover=3.1,
        avg_turnover_5d=3.0,
        median_turnover_20d=2.2,
        return_20d=0.12,
        avg_pct_change_5d=0.8,
        positive_days_5d=4,
        window_5d_ready=True,
        window_20d_ready=True,
    )
    return cycle, security, profile


def test_build_shadow_cycle_intelligence_from_m1_returns_minimal_bundle() -> None:
    cycle, security, profile = _build_reference_inputs()

    bundle = build_shadow_cycle_intelligence_from_m1(
        cycle=cycle,
        security_master=security,
        trading_profile=profile,
    )

    assert set(bundle.keys()) == {
        "wave_hypothesis",
        "mid_cycle_states",
        "cycle_linkage_state",
        "growth_potential_profile",
        "top_risk_profile",
    }
    assert bundle["wave_hypothesis"].to_payload()["object_type"] == (
        SMALL_CYCLE_WAVE_HYPOTHESIS_OBJECT_TYPE
    )
    assert bundle["mid_cycle_states"]["fund_cycle"].to_payload()["object_type"] == (
        MID_CYCLE_STATE_OBJECT_TYPE
    )
    assert bundle["mid_cycle_states"]["industry_cycle"].to_payload()["state"] == "advancing"
    assert bundle["cycle_linkage_state"].to_payload()["object_type"] == (
        CYCLE_LINKAGE_STATE_OBJECT_TYPE
    )
    assert bundle["growth_potential_profile"].to_payload()["object_type"] == (
        GROWTH_POTENTIAL_PROFILE_OBJECT_TYPE
    )
    assert bundle["top_risk_profile"].to_payload()["object_type"] == (
        TOP_RISK_PROFILE_OBJECT_TYPE
    )


def test_build_shadow_cycle_intelligence_from_m1_projects_positive_reference_status() -> None:
    cycle, security, profile = _build_reference_inputs()

    bundle = build_shadow_cycle_intelligence_from_m1(
        cycle=cycle,
        security_master=security,
        trading_profile=profile,
    )

    assert bundle["wave_hypothesis"].replay_consistency_status == "pending_benchmark"
    assert bundle["cycle_linkage_state"].supports_continuation is True
    assert bundle["cycle_linkage_state"].local_end_vs_global_end == "local_end_only"
    assert bundle["growth_potential_profile"].status == "promising"
    assert bundle["top_risk_profile"].risk_level == "low"
