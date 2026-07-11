from __future__ import annotations

from neotrade3.benchmark import (
    ASSESSMENT_GRADE_FAIL,
    ASSESSMENT_GRADE_PASS,
    B1_TARGET_OPPORTUNITY_SAMPLE,
    B2_CONTROL_FAILURE_SAMPLE,
    B3_BOUNDARY_COMPLEX_SAMPLE,
    B4_INTERACTION_GUARDRAIL_SAMPLE,
    BENCHMARK_SAMPLE_OBJECT_TYPE,
    GAP_GROUP_INTERACTION,
    GAP_LABEL_LOCAL_GLOBAL_MISREAD,
    GUARDRAIL_CODE_LOCAL_GLOBAL_END,
    T3_STRONG_TARGET,
    TRACE_BUNDLE_OBJECT_TYPE,
    T1_PROHIBITION_TARGET,
    T2_RANGE_TARGET,
    build_benchmark_assessment_from_m2_shadow,
    build_benchmark_sample,
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


def _build_reference_cycle_and_shadow_bundle() -> tuple[object, dict[str, object], dict[str, object]]:
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
    return cycle, shadow_bundle, m1_context


def test_build_benchmark_sample_returns_formal_payload() -> None:
    sample = build_benchmark_sample(
        stock_code="600000",
        trade_date="2026-07-07",
        sample_bucket=B3_BOUNDARY_COMPLEX_SAMPLE,
        target_state_type=T2_RANGE_TARGET,
        expected_target_state={
            "small_cycle_state": {"allowed": ["S2 Advancing"]},
        },
        scenario_tags=["boundary_complex", "shadow_validation"],
        note="首批 B3 样本",
    )

    payload = sample.to_payload()
    assert payload["object_type"] == BENCHMARK_SAMPLE_OBJECT_TYPE
    assert payload["sample_bucket"] == B3_BOUNDARY_COMPLEX_SAMPLE
    assert payload["expected_target_state"]["small_cycle_state"]["allowed"] == [
        "S2 Advancing"
    ]


def test_build_benchmark_assessment_from_m2_shadow_passes_b3_seed() -> None:
    cycle, shadow_bundle, m1_context = _build_reference_cycle_and_shadow_bundle()
    sample = build_benchmark_sample(
        stock_code="600000",
        trade_date="2026-07-07",
        sample_bucket=B3_BOUNDARY_COMPLEX_SAMPLE,
        target_state_type=T2_RANGE_TARGET,
        expected_target_state={
            "small_cycle_state": {"allowed": ["S2 Advancing"]},
            "wave_hypothesis": {"replay_consistency_status": "pending_benchmark"},
            "fund_cycle": {"allowed": ["advancing", "repairing"]},
            "industry_cycle": {"allowed": ["advancing", "repairing"]},
            "cycle_linkage_state": {
                "supports_continuation": True,
                "local_end_vs_global_end": [
                    "local_end_only",
                    "needs_global_confirmation",
                ],
            },
            "growth_potential_profile": {"allowed_status": ["promising", "uncertain"]},
            "top_risk_profile": {"max_risk_level": "watch"},
        },
        scenario_tags=["B3", "boundary_complex"],
    )

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["assessment_grade"] == ASSESSMENT_GRADE_PASS
    assert payload["summary"]["hard_violation_count"] == 0
    assert payload["gap_records"] == []
    assert payload["interaction_guardrail_breaches"] == []
    assert payload["trace_bundle"]["object_type"] == TRACE_BUNDLE_OBJECT_TYPE
    assert payload["trace_bundle"]["m2_shadow"]["cycle_linkage_state"][
        "supports_continuation"
    ] is True


def test_build_benchmark_assessment_from_m2_shadow_passes_b1_seed() -> None:
    cycle, shadow_bundle, m1_context = _build_reference_cycle_and_shadow_bundle()
    sample = build_benchmark_sample(
        stock_code="600000",
        trade_date="2026-07-07",
        sample_bucket=B1_TARGET_OPPORTUNITY_SAMPLE,
        target_state_type=T3_STRONG_TARGET,
        expected_target_state={
            "small_cycle_state": {"allowed": ["S2 Advancing"]},
            "wave_hypothesis": {"replay_consistency_status": "pending_benchmark"},
            "fund_cycle": {"allowed": ["advancing", "repairing"]},
            "industry_cycle": {"allowed": ["advancing", "repairing"]},
            "cycle_linkage_state": {
                "supports_continuation": True,
                "local_end_vs_global_end": [
                    "local_end_only",
                    "needs_global_confirmation",
                ],
            },
            "growth_potential_profile": {"allowed_status": ["promising", "uncertain"]},
            "top_risk_profile": {"max_risk_level": "watch"},
        },
        scenario_tags=["B1", "target_opportunity"],
    )

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["assessment_grade"] == ASSESSMENT_GRADE_PASS
    assert payload["summary"]["hard_violation_count"] == 0
    assert payload["gap_records"] == []
    assert payload["trace_bundle"]["m2_shadow"]["growth_potential_profile"]["status"] == (
        "promising"
    )
    assert payload["trace_bundle"]["m2_shadow"]["cycle_linkage_state"][
        "supports_continuation"
    ] is True


def test_build_benchmark_assessment_from_m2_shadow_fails_b2_seed() -> None:
    cycle, shadow_bundle, m1_context = _build_reference_cycle_and_shadow_bundle()
    bad_linkage = build_cycle_linkage_state(
        stock_code=cycle.stock_code,
        trade_date=cycle.trade_date,
        small_cycle_ref={
            "object_type": cycle.object_type,
            "stock_code": cycle.stock_code,
            "cycle_state": cycle.cycle_state,
        },
        mid_cycle_ref={
            "fund_cycle_state": shadow_bundle["cycle_linkage_state"].mid_cycle_ref[
                "fund_cycle_state"
            ],
            "industry_cycle_state": shadow_bundle["cycle_linkage_state"].mid_cycle_ref[
                "industry_cycle_state"
            ],
        },
        linkage_phase="continuation_blocked",
        supports_continuation=False,
        local_end_vs_global_end="local_end_only",
        confidence={"level": "medium"},
        evidence_bundle={"override": "forced_for_b2_control_failure_test"},
        rule_version="m2_cycle_linkage.v1alpha1",
    )
    sample = build_benchmark_sample(
        stock_code="600000",
        trade_date="2026-07-07",
        sample_bucket=B2_CONTROL_FAILURE_SAMPLE,
        target_state_type=T1_PROHIBITION_TARGET,
        expected_target_state={
            "cycle_linkage_state": {
                "supports_continuation": True,
                "local_end_vs_global_end": [
                    "local_end_only",
                    "needs_global_confirmation",
                ],
            }
        },
        scenario_tags=["B2", "control_failure"],
    )

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle={**shadow_bundle, "cycle_linkage_state": bad_linkage},
        m1_context=m1_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["assessment_grade"] == ASSESSMENT_GRADE_FAIL
    assert payload["summary"]["hard_violation_count"] >= 1
    assert payload["interaction_guardrail_breaches"] == []
    assert payload["gap_records"][0]["actual_state"]["cycle_linkage_state"][
        "supports_continuation"
    ] is False


def test_build_benchmark_assessment_from_m2_shadow_flags_b4_guardrail_breach() -> None:
    cycle, shadow_bundle, m1_context = _build_reference_cycle_and_shadow_bundle()
    mid_cycles = build_mid_cycle_states_from_m1(
        cycle=cycle,
        security_master=_sample_m1_objects()[1],
        trading_profile=_sample_m1_objects()[3],
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
        evidence_bundle={"override": "forced_for_b4_guardrail_test"},
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
    sample = build_benchmark_sample(
        stock_code="600000",
        trade_date="2026-07-07",
        sample_bucket=B4_INTERACTION_GUARDRAIL_SAMPLE,
        target_state_type=T1_PROHIBITION_TARGET,
        expected_target_state={
            "cycle_linkage_state": {
                "supports_continuation": True,
                "local_end_vs_global_end": [
                    "local_end_only",
                    "needs_global_confirmation",
                ],
            }
        },
        scenario_tags=["B4", "guardrail"],
    )

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["assessment_grade"] == ASSESSMENT_GRADE_FAIL
    assert payload["summary"]["hard_violation_count"] >= 1
    assert payload["gap_records"][0]["gap_group"] == GAP_GROUP_INTERACTION
    assert payload["gap_records"][0]["gap_label"] == GAP_LABEL_LOCAL_GLOBAL_MISREAD
    assert (
        payload["interaction_guardrail_breaches"][0]["guardrail_code"]
        == GUARDRAIL_CODE_LOCAL_GLOBAL_END
    )
