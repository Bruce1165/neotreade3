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
    GAP_GROUP_TIMING,
    GUARDRAIL_CODE_LOCAL_GLOBAL_END,
    T3_STRONG_TARGET,
    TRACE_BUNDLE_OBJECT_TYPE,
    T1_PROHIBITION_TARGET,
    T2_RANGE_TARGET,
    build_benchmark_assessment_from_m2_shadow,
    build_benchmark_sample,
)
from neotrade3.decision_engine import (
    build_entry_state_from_formal_inputs,
    build_identify_state_from_formal_inputs,
    build_m1_constraints_ref,
    build_m3_hold_exit_bridge,
    build_tracking_state_from_formal_inputs,
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
    m3_context = {
        "m1_constraints_ref": dict(constraints),
        "identify_state": build_identify_state_from_formal_inputs(
            cycle=cycle,
            m1_constraints_ref=constraints,
        ).to_payload(),
        "tracking_state": build_tracking_state_from_formal_inputs(
            cycle=cycle,
            m1_constraints_ref=constraints,
        ).to_payload(),
        "entry_state": build_entry_state_from_formal_inputs(
            cycle=cycle,
            m1_constraints_ref=constraints,
        ).to_payload(),
    }
    return cycle, shadow_bundle, m1_context, m3_context


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
    cycle, shadow_bundle, m1_context, m3_context = _build_reference_cycle_and_shadow_bundle()
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
            "identify_state": {"allowed_status": ["identified"]},
            "tracking_state": {
                "allowed_status": ["tracking"],
                "allowed_maturity": ["ready_for_entry"],
            },
            "entry_state": {
                "allowed_status": ["ready"],
                "allowed_decision": ["enter"],
                "actionable": True,
            },
        },
        scenario_tags=["B3", "boundary_complex"],
    )

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
        m3_context=m3_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["assessment_grade"] == ASSESSMENT_GRADE_PASS
    assert payload["summary"]["hard_violation_count"] == 0
    assert payload["gap_records"] == []
    assert payload["interaction_guardrail_breaches"] == []
    assert payload["summary"]["hold_quality_risk_summary"]["status"] == (
        "missing_m3_hold_exit_bridge"
    )
    assert payload["summary"]["front_quality_risk_summary"]["status"] == "available"
    assert payload["summary"]["front_quality_risk_summary"]["entry_decision"] == "enter"
    assert payload["trace_bundle"]["object_type"] == TRACE_BUNDLE_OBJECT_TYPE
    assert payload["trace_bundle"]["m2_shadow"]["cycle_linkage_state"][
        "supports_continuation"
    ] is True


def test_build_benchmark_assessment_from_m2_shadow_passes_b1_seed() -> None:
    cycle, shadow_bundle, m1_context, m3_context = _build_reference_cycle_and_shadow_bundle()
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
            "identify_state": {"allowed_status": ["identified"]},
            "tracking_state": {
                "allowed_status": ["tracking"],
                "allowed_maturity": ["ready_for_entry"],
            },
            "entry_state": {
                "allowed_status": ["ready"],
                "allowed_decision": ["enter"],
                "actionable": True,
            },
        },
        scenario_tags=["B1", "target_opportunity"],
    )

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
        m3_context=m3_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["assessment_grade"] == ASSESSMENT_GRADE_PASS
    assert payload["summary"]["hard_violation_count"] == 0
    assert payload["gap_records"] == []
    assert payload["summary"]["front_quality_risk_summary"]["identify_status"] == (
        "identified"
    )
    assert payload["trace_bundle"]["m2_shadow"]["growth_potential_profile"]["status"] == (
        "promising"
    )
    assert payload["trace_bundle"]["m2_shadow"]["cycle_linkage_state"][
        "supports_continuation"
    ] is True


def test_build_benchmark_assessment_from_m2_shadow_projects_watch_hold_summary() -> None:
    cycle, shadow_bundle, m1_context, _ = _build_reference_cycle_and_shadow_bundle()
    sample = build_benchmark_sample(
        stock_code="600000",
        trade_date="2026-07-07",
        sample_bucket=B3_BOUNDARY_COMPLEX_SAMPLE,
        target_state_type=T2_RANGE_TARGET,
        expected_target_state={
            "small_cycle_state": {"allowed": ["S2 Advancing"]},
        },
        scenario_tags=["B3", "watch_hold"],
    )
    m3_context = build_m3_hold_exit_bridge(
        stock_code="600000",
        trade_date="2026-07-07",
        position_snapshot={
            "hold_state": "review_watch",
            "warning_flags": ["market_exit_state:review"],
            "not_exit_reasons": ["系统退出证据尚未达到正式确认门槛"],
            "noise_evidence": ["market breadth weakening"],
            "hold_attribution_bucket": "hold_noise_watch",
            "exit_evidence_bundle": ["market breadth weakening"],
            "current_stage": "hold_confirmed",
            "decision": "hold",
            "next_action": "hold",
            "last_transition": "2026-07-06",
            "source_layer": "hold",
            "exit_ready": False,
        },
    )

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
        m3_context=m3_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["hold_quality_risk_summary"]["status"] == "watch"
    assert payload["summary"]["hold_quality_risk_summary"]["risk_level"] == "watch"
    assert payload["summary"]["hold_quality_risk_summary"]["hold_state"] == "review_watch"
    assert payload["trace_bundle"]["m3_context"]["position_status"] == "watch"


def test_build_benchmark_assessment_from_m2_shadow_projects_exit_ready_summary() -> None:
    cycle, shadow_bundle, m1_context, _ = _build_reference_cycle_and_shadow_bundle()
    sample = build_benchmark_sample(
        stock_code="600000",
        trade_date="2026-07-07",
        sample_bucket=B2_CONTROL_FAILURE_SAMPLE,
        target_state_type=T1_PROHIBITION_TARGET,
        expected_target_state={
            "small_cycle_state": {"allowed": ["S2 Advancing"]},
        },
        scenario_tags=["B2", "exit_ready"],
    )
    m3_context = build_m3_hold_exit_bridge(
        stock_code="600000",
        trade_date="2026-07-07",
        position_snapshot={
            "hold_state": "exit_ready",
            "warning_flags": ["market_exit_state:confirmed"],
            "exit_evidence_bundle": ["trend exhausted"],
            "current_stage": "exit_ready",
            "decision": "exit",
            "next_action": "exit",
            "last_transition": "2026-07-07",
            "source_layer": "exit",
            "exit_ready": True,
            "exit_scope": "portfolio",
            "exit_reason_type": "trend_exhausted",
            "exit_attribution_bucket": "trend_exhaustion_exit",
        },
    )

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
        m3_context=m3_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["hold_quality_risk_summary"]["status"] == "exit_ready"
    assert payload["summary"]["hold_quality_risk_summary"]["risk_level"] == "high"
    assert payload["summary"]["hold_quality_risk_summary"]["exit_reason_type"] == (
        "trend_exhausted"
    )
    assert payload["trace_bundle"]["m3_context"]["position_status"] == "exit_ready"


def test_build_benchmark_assessment_from_m2_shadow_fails_b2_seed() -> None:
    cycle, shadow_bundle, m1_context, _ = _build_reference_cycle_and_shadow_bundle()
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
    cycle, shadow_bundle, m1_context, _ = _build_reference_cycle_and_shadow_bundle()
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


def test_build_benchmark_assessment_from_m2_shadow_flags_identify_gap_for_front_formal_mismatch() -> None:
    cycle, shadow_bundle, m1_context, m3_context = _build_reference_cycle_and_shadow_bundle()
    sample = build_benchmark_sample(
        stock_code="600000",
        trade_date="2026-07-07",
        sample_bucket=B3_BOUNDARY_COMPLEX_SAMPLE,
        target_state_type=T2_RANGE_TARGET,
        expected_target_state={
            "identify_state": {"allowed_status": ["identified"]},
        },
        scenario_tags=["B3", "identify_gap"],
    )
    mismatched_m3_context = {
        **m3_context,
        "identify_state": {
            **m3_context["identify_state"],
            "status": "not_identified",
            "reason": "forced_for_test",
        },
    }

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
        m3_context=mismatched_m3_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["assessment_grade"] == "warn"
    assert payload["summary"]["front_quality_risk_summary"]["identify_gap_count"] == 1
    assert payload["gap_records"][0]["gap_group"] == "G1 Identify Gap"
    assert payload["gap_records"][0]["actual_state"]["identify_state"]["status"] == (
        "not_identified"
    )


def test_build_benchmark_assessment_from_m2_shadow_flags_timing_gap_for_entry_mismatch() -> None:
    cycle, shadow_bundle, m1_context, m3_context = _build_reference_cycle_and_shadow_bundle()
    sample = build_benchmark_sample(
        stock_code="600000",
        trade_date="2026-07-07",
        sample_bucket=B3_BOUNDARY_COMPLEX_SAMPLE,
        target_state_type=T2_RANGE_TARGET,
        expected_target_state={
            "entry_state": {
                "allowed_status": ["ready"],
                "allowed_decision": ["enter"],
                "actionable": True,
            },
        },
        scenario_tags=["B3", "timing_gap"],
    )
    mismatched_m3_context = {
        **m3_context,
        "entry_state": {
            **m3_context["entry_state"],
            "status": "not_ready",
            "decision": "wait",
            "actionable": False,
            "blocking_reasons": ["forced_for_test"],
        },
    }

    result = build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
        m3_context=mismatched_m3_context,
    )

    payload = result.to_payload()
    assert payload["summary"]["assessment_grade"] == "warn"
    assert payload["summary"]["front_quality_risk_summary"]["timing_gap_count"] == 1
    assert payload["gap_records"][0]["gap_group"] == GAP_GROUP_TIMING
    assert payload["gap_records"][0]["actual_state"]["entry_state"]["decision"] == "wait"
