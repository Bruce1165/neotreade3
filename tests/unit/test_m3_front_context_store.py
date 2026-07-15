from __future__ import annotations

from pathlib import Path

from neotrade3.cycle_intelligence import (
    ShadowCycleIntelligenceBundle,
    build_shadow_cycle_intelligence_from_m1,
    build_small_cycle,
)
from neotrade3.data_control import D1DailyPriceFact, D7SecurityMasterMinimal, D7TradingDayStatus, PF1TradingProfile
from neotrade3.decision_engine import (
    DecisionM3FrontContext,
    build_decision_m3_front_context_record_id,
    build_entry_state_from_formal_inputs,
    build_identify_state_from_formal_inputs,
    build_m1_constraints_ref,
    build_tracking_state_from_formal_inputs,
    materialize_decision_m3_front_context,
    read_decision_m3_front_context,
    read_decision_m3_front_context_artifact,
    read_decision_m3_front_context_ledger,
)


def _build_front_context() -> DecisionM3FrontContext:
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
    trading_day_status = D7TradingDayStatus(
        target_date="2026-07-07",
        is_trading_day=True,
        nearest_trading_day="2026-07-07",
        min_trading_day="2026-06-01",
        max_trading_day="2026-07-07",
        calendar_covered_until="2026-07-07",
        calendar_source="trading_calendar_cache",
    )
    d1_fact = D1DailyPriceFact(
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
    shadow_bundle = ShadowCycleIntelligenceBundle.from_bundle(
        build_shadow_cycle_intelligence_from_m1(
            cycle=cycle,
            security_master=security,
            trading_profile=profile,
        )
    )
    cycle_linkage_state_ref = shadow_bundle.to_replay_payload()["cycle_linkage_state"]
    constraints = build_m1_constraints_ref(
        d1_fact=d1_fact,
        security_master=security,
        trading_day_status=trading_day_status,
        trading_profile=profile,
    )
    return DecisionM3FrontContext(
        m1_constraints_ref=dict(constraints),
        identify_state=build_identify_state_from_formal_inputs(
            cycle=cycle,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
        tracking_state=build_tracking_state_from_formal_inputs(
            cycle=cycle,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
        entry_state=build_entry_state_from_formal_inputs(
            cycle=cycle,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
    )


def test_materialize_decision_m3_front_context(tmp_path: Path) -> None:
    front_context = _build_front_context()
    record_id = build_decision_m3_front_context_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )

    ledger_record = materialize_decision_m3_front_context(
        project_root=tmp_path,
        record_id=record_id,
        front_context=front_context,
    )
    artifact_payload = read_decision_m3_front_context_artifact(
        project_root=tmp_path,
        record_id=record_id,
    )
    reconstructed = read_decision_m3_front_context(
        project_root=tmp_path,
        record_id=record_id,
    )
    reconstructed_ledger = read_decision_m3_front_context_ledger(
        project_root=tmp_path,
        record_id=record_id,
    )

    assert ledger_record.record_id == record_id
    assert artifact_payload is not None
    assert artifact_payload["identify_state"]["object_type"] == "identify_state"
    assert reconstructed == front_context
    assert reconstructed_ledger == ledger_record
