from __future__ import annotations

from pathlib import Path

from neotrade3.benchmark import (
    ASSESSMENT_GRADE_PASS,
    B1_TARGET_OPPORTUNITY_SAMPLE,
    B2_CONTROL_FAILURE_SAMPLE,
    B3_BOUNDARY_COMPLEX_SAMPLE,
    B4_INTERACTION_GUARDRAIL_SAMPLE,
    BenchmarkSeedRegistry,
    build_benchmark_assessment_from_m2_shadow,
    load_benchmark_seed_registry,
)
from neotrade3.cycle_intelligence import (
    build_cycle_linkage_state,
    build_growth_potential_profile_from_formal_inputs,
    build_mid_cycle_states_from_m1,
    build_shadow_cycle_intelligence_from_m1,
    build_small_cycle_from_m1,
    build_small_cycle_wave_hypothesis_from_formal_inputs,
    build_top_risk_profile_from_formal_inputs,
)
from neotrade3.data_control import (
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
)
from neotrade3.decision_engine import (
    build_entry_state_from_formal_inputs,
    build_identify_state_from_formal_inputs,
    build_m1_constraints_ref,
    build_tracking_state_from_formal_inputs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_SAMPLE_REGISTRY = (
    PROJECT_ROOT / "config/benchmark/validation_seed_samples.json"
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


def _build_reference_cycle_and_shadow_bundle() -> tuple[
    object,
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    d1, security, trading_day, profile = _sample_m1_objects()
    cycle = build_small_cycle_from_m1(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )
    shadow_bundle = build_shadow_cycle_intelligence_from_m1(
        cycle=cycle,
        security_master=security,
        trading_profile=profile,
    )
    m1_context = {
        "d1_fact": {
            "stock_code": d1.stock_code,
            "trade_date": d1.trade_date,
            "pct_change": d1.pct_change,
        },
        "security_master": {
            "sector_lv1": security.sector_lv1,
            "sector_lv2": security.sector_lv2,
        },
        "trading_profile": {
            "return_20d": profile.return_20d,
            "positive_days_5d": profile.positive_days_5d,
        },
    }
    constraints = build_m1_constraints_ref(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )
    cycle_linkage_state_ref = shadow_bundle["cycle_linkage_state"].to_payload()
    m3_context = {
        "m1_constraints_ref": dict(constraints),
        "identify_state": build_identify_state_from_formal_inputs(
            cycle=cycle,
            run_id=cycle.trade_date,
            source_run_id=cycle.trade_date,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
        "tracking_state": build_tracking_state_from_formal_inputs(
            cycle=cycle,
            run_id=cycle.trade_date,
            source_run_id=cycle.trade_date,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
        "entry_state": build_entry_state_from_formal_inputs(
            cycle=cycle,
            run_id=cycle.trade_date,
            source_run_id=cycle.trade_date,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
    }
    return cycle, shadow_bundle, m1_context, m3_context


def test_benchmark_seed_registry_loads_b1_to_b4_samples() -> None:
    registry = load_benchmark_seed_registry(BENCHMARK_SAMPLE_REGISTRY)
    b2_sample = registry.get_sample("b2_control_failure_seed")
    b4_sample = registry.get_sample("b4_local_global_guardrail_seed")

    assert isinstance(registry, BenchmarkSeedRegistry)
    assert registry.version == 1
    assert len(registry.samples) == 4
    assert registry.get_sample("b1_target_opportunity_seed").sample_bucket == (
        B1_TARGET_OPPORTUNITY_SAMPLE
    )
    assert b2_sample.sample_bucket == B2_CONTROL_FAILURE_SAMPLE
    assert registry.get_sample("b3_boundary_complex_advancing_seed").sample_bucket == (
        B3_BOUNDARY_COMPLEX_SAMPLE
    )
    assert b4_sample.sample_bucket == B4_INTERACTION_GUARDRAIL_SAMPLE
    assert b2_sample.expected_target_state["tracking_state"]["allowed_maturity"] == [
        "not_ready"
    ]
    assert b2_sample.expected_target_state["entry_state"]["allowed_decision"] == ["wait"]
    assert b4_sample.expected_target_state["tracking_state"]["allowed_status"] == [
        "tracking"
    ]
    assert b4_sample.expected_target_state["entry_state"]["actionable"] is False


def test_benchmark_seed_registry_builds_repeatable_b3_sample_for_assessment() -> None:
    cycle, shadow_bundle, m1_context, m3_context = _build_reference_cycle_and_shadow_bundle()
    registry = load_benchmark_seed_registry(BENCHMARK_SAMPLE_REGISTRY)
    sample = registry.get_sample("b3_boundary_complex_advancing_seed").to_benchmark_sample()

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
        m3_context=m3_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["assessment_grade"] == ASSESSMENT_GRADE_PASS
    assert payload["summary"]["sample_bucket_summary"] == {B3_BOUNDARY_COMPLEX_SAMPLE: 1}


def test_benchmark_seed_registry_filters_bucket_and_keeps_fixture_metadata() -> None:
    registry = load_benchmark_seed_registry(BENCHMARK_SAMPLE_REGISTRY)

    b1_only = registry.samples_for_bucket(B1_TARGET_OPPORTUNITY_SAMPLE)
    b4_only = registry.samples_for_bucket(B4_INTERACTION_GUARDRAIL_SAMPLE)

    assert len(b1_only) == 1
    assert b1_only[0].fixture_id == "m2_target_opportunity_reference"
    assert b1_only[0].scenario_tags == ["B1", "target_opportunity", "continuation_candidate"]
    assert len(b4_only) == 1
    assert b4_only[0].fixture_id == "m2_local_global_guardrail_reference"
    assert b4_only[0].scenario_tags == ["B4", "guardrail", "local_global_end"]


def test_benchmark_seed_registry_b4_sample_can_drive_guardrail_path() -> None:
    cycle, _, m1_context, _ = _build_reference_cycle_and_shadow_bundle()
    d1, security, trading_day, profile = _sample_m1_objects()
    mid_cycles = build_mid_cycle_states_from_m1(
        cycle=cycle,
        security_master=security,
        trading_profile=profile,
    )
    bad_linkage = build_cycle_linkage_state(
        stock_code=cycle.stock_code,
        trade_date=cycle.trade_date,
        small_cycle_ref={
            "object_type": cycle.object_type,
            "stock_code": cycle.stock_code,
            "cycle_state": cycle.cycle_state,
        },
        mid_cycle_ref={
            "fund_cycle_state": mid_cycles["fund_cycle"].to_payload()["state"],
            "industry_cycle_state": mid_cycles["industry_cycle"].to_payload()["state"],
        },
        linkage_phase="possible_global_transition",
        supports_continuation=False,
        local_end_vs_global_end="possible_global_end",
        confidence={"level": "low"},
        evidence_bundle={"override": "registry_driven_b4_guardrail_test"},
        rule_version="m2_cycle_linkage.v1alpha1",
    )
    shadow_bundle = {
        "wave_hypothesis": build_small_cycle_wave_hypothesis_from_formal_inputs(cycle=cycle),
        "mid_cycle_states": mid_cycles,
        "cycle_linkage_state": bad_linkage,
        "growth_potential_profile": build_growth_potential_profile_from_formal_inputs(
            cycle=cycle,
            fund_cycle_state=mid_cycles["fund_cycle"],
            industry_cycle_state=mid_cycles["industry_cycle"],
        ),
        "top_risk_profile": build_top_risk_profile_from_formal_inputs(
            cycle=cycle,
            fund_cycle_state=mid_cycles["fund_cycle"],
            industry_cycle_state=mid_cycles["industry_cycle"],
        ),
    }
    constraints = build_m1_constraints_ref(
        d1_fact=d1,
        security_master=security,
        trading_day_status=trading_day,
        trading_profile=profile,
    )
    cycle_linkage_state_ref = bad_linkage.to_payload()
    m3_context = {
        "m1_constraints_ref": dict(constraints),
        "identify_state": build_identify_state_from_formal_inputs(
            cycle=cycle,
            run_id=cycle.trade_date,
            source_run_id=cycle.trade_date,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
        "tracking_state": build_tracking_state_from_formal_inputs(
            cycle=cycle,
            run_id=cycle.trade_date,
            source_run_id=cycle.trade_date,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
        "entry_state": build_entry_state_from_formal_inputs(
            cycle=cycle,
            run_id=cycle.trade_date,
            source_run_id=cycle.trade_date,
            m1_constraints_ref=constraints,
            cycle_linkage_state_ref=cycle_linkage_state_ref,
        ).to_payload(),
    }
    registry = load_benchmark_seed_registry(BENCHMARK_SAMPLE_REGISTRY)
    sample = registry.get_sample("b4_local_global_guardrail_seed").to_benchmark_sample()

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
        m3_context=m3_context,
    )

    payload = result.to_payload()
    assert payload["interaction_guardrail_breaches"]
    assert payload["summary"]["hard_violation_count"] >= 1


def test_benchmark_seed_registry_b1_sample_can_drive_target_opportunity_path() -> None:
    cycle, shadow_bundle, m1_context, m3_context = _build_reference_cycle_and_shadow_bundle()
    registry = load_benchmark_seed_registry(BENCHMARK_SAMPLE_REGISTRY)
    sample = registry.get_sample("b1_target_opportunity_seed").to_benchmark_sample()

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
        m3_context=m3_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["assessment_grade"] == ASSESSMENT_GRADE_PASS
    assert payload["summary"]["sample_bucket_summary"] == {B1_TARGET_OPPORTUNITY_SAMPLE: 1}
