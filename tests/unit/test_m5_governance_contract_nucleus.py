from __future__ import annotations

import pytest

from neotrade3.benchmark import (
    ASSESSMENT_GRADE_FAIL,
    B4_INTERACTION_GUARDRAIL_SAMPLE,
    GAP_LABEL_LOCAL_GLOBAL_MISREAD,
    GUARDRAIL_CODE_LOCAL_GLOBAL_END,
    build_benchmark_assessment_from_m2_shadow,
    build_benchmark_sample,
)
from neotrade3.cycle_intelligence import (
    build_cycle_linkage_state,
    build_shadow_cycle_intelligence_from_m1,
    build_small_cycle_from_m1,
)
from neotrade3.data_control import (
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
)
from neotrade3.governance import (
    CHANGE_REQUEST_OBJECT_TYPE,
    DIAGNOSTIC_CHAIN_OBJECT_TYPE,
    GOVERNANCE_DECISION_RECORD_OBJECT_TYPE,
    PROMOTION_BLOCKER_OBJECT_TYPE,
    ROOT_LAYER_INTERACTION,
    VALIDATION_RESULT_OBJECT_TYPE,
    build_b4_local_global_guardrail_diagnostic,
    build_block_decision_record_from_promotion_blocker,
    build_change_request_from_diagnostic,
    build_experiment_request_from_change_request,
    build_governance_decision_record,
    build_pending_validation_result_from_experiment_request,
    build_promotion_blocker_from_diagnostic,
    build_validation_result,
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
        stock_name="PuFa",
        asset_type="stock",
        is_delisted=False,
        sector_lv1="finance",
        sector_lv2="bank",
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


def _build_b4_failing_assessment():
    cycle, shadow_bundle, m1_context = _build_reference_cycle_and_shadow_bundle()
    shadow_bundle["cycle_linkage_state"] = build_cycle_linkage_state(
        stock_code="600000",
        trade_date="2026-07-07",
        small_cycle_ref={"cycle_state": "S2 Advancing"},
        mid_cycle_ref={"fund_cycle": "advancing", "industry_cycle": "advancing"},
        linkage_phase="semantic_guardrail_violation",
        supports_continuation=False,
        local_end_vs_global_end="global_end_only",
        confidence={"score": 0.38},
        evidence_bundle={"reason": "misread local end as global end"},
    )
    sample = build_benchmark_sample(
        stock_code="600000",
        trade_date="2026-07-07",
        sample_bucket=B4_INTERACTION_GUARDRAIL_SAMPLE,
        target_state_type="T2_range_target",
        expected_target_state={
            "cycle_linkage_state": {
                "supports_continuation": True,
                "local_end_vs_global_end": [
                    "local_end_only",
                    "needs_global_confirmation",
                ],
            }
        },
        scenario_tags=["B4", "interaction_guardrail"],
    )
    return build_benchmark_assessment_from_m2_shadow(
        sample=sample,
        cycle=cycle,
        shadow_bundle=shadow_bundle,
        m1_context=m1_context,
    )


def test_governance_contract_payloads_are_stable() -> None:
    result = build_validation_result(
        validation_id="validation-1",
        experiment_id="experiment-1",
        baseline_run_id="baseline-run",
        candidate_run_id="candidate-run",
        outcome="rejected",
        introduced_risk_count=1,
        cleared_guardrail_codes=[],
        remaining_guardrail_codes=[GUARDRAIL_CODE_LOCAL_GLOBAL_END],
        evidence_refs=[{"kind": "benchmark_artifact"}],
    )
    decision = build_governance_decision_record(
        decision_id="decision-1",
        subject_type="change_request",
        subject_id="cr-1",
        decision="reject",
        decision_scope="promotion",
        rationale="guardrail still active",
        approver="human_reviewer",
        status="final",
        evidence_refs=[{"kind": "validation_result"}],
    )

    result_payload = result.to_payload()
    decision_payload = decision.to_payload()
    result_payload["remaining_guardrail_codes"].append("other")
    decision_payload["evidence_refs"].append({"kind": "other"})

    assert result.to_payload()["object_type"] == VALIDATION_RESULT_OBJECT_TYPE
    assert decision.to_payload()["object_type"] == GOVERNANCE_DECISION_RECORD_OBJECT_TYPE
    assert result.remaining_guardrail_codes == [GUARDRAIL_CODE_LOCAL_GLOBAL_END]
    assert decision.evidence_refs == [{"kind": "validation_result"}]


def test_governance_builders_reject_empty_ids() -> None:
    with pytest.raises(ValueError):
        build_governance_decision_record(
            decision_id="",
            subject_type="change_request",
            subject_id="cr-1",
            decision="reject",
            decision_scope="promotion",
            rationale="guardrail still active",
            approver="human_reviewer",
            status="final",
        )


def test_pending_validation_result_allows_empty_candidate_only_for_pending_outcome() -> None:
    assessment = _build_b4_failing_assessment()
    diagnostic = build_b4_local_global_guardrail_diagnostic(
        gap_records=assessment.gap_records,
        trace_bundle=assessment.trace_bundle,
        interaction_guardrail_breaches=assessment.interaction_guardrail_breaches,
    )
    experiment = build_experiment_request_from_change_request(
        change_request=build_change_request_from_diagnostic(diagnostic=diagnostic)
    )

    pending = build_pending_validation_result_from_experiment_request(
        experiment_request=experiment,
        baseline_run_id=assessment.trace_bundle.benchmark_run_id,
    )

    assert pending.candidate_run_id == ""
    assert pending.outcome == "awaiting_candidate_validation"
    assert pending.remaining_guardrail_codes == [GUARDRAIL_CODE_LOCAL_GLOBAL_END]

    with pytest.raises(ValueError, match="candidate_run_id must not be empty"):
        build_validation_result(
            validation_id="validation-2",
            experiment_id=experiment.experiment_id,
            baseline_run_id=assessment.trace_bundle.benchmark_run_id,
            candidate_run_id="",
            outcome="passed",
            introduced_risk_count=0,
            cleared_guardrail_codes=[],
            remaining_guardrail_codes=[],
            evidence_refs=[],
        )


def test_build_b4_local_global_guardrail_diagnostic_projects_formal_truth() -> None:
    assessment = _build_b4_failing_assessment()

    assert assessment.summary.assessment_grade == ASSESSMENT_GRADE_FAIL
    assert assessment.interaction_guardrail_breaches

    diagnostic = build_b4_local_global_guardrail_diagnostic(
        gap_records=assessment.gap_records,
        trace_bundle=assessment.trace_bundle,
        interaction_guardrail_breaches=assessment.interaction_guardrail_breaches,
    )
    payload = diagnostic.to_payload()

    assert payload["object_type"] == DIAGNOSTIC_CHAIN_OBJECT_TYPE
    assert payload["primary_root_layer"] == ROOT_LAYER_INTERACTION
    assert payload["sample_bucket"] == B4_INTERACTION_GUARDRAIL_SAMPLE
    assert payload["source_breach_ids"]
    assert payload["source_gap_ids"]
    assert payload["benchmark_run_id"] == assessment.trace_bundle.benchmark_run_id
    assert any(
        ref.get("object_type") == "cycle_linkage_state"
        and ref.get("field") == "supports_continuation"
        for ref in payload["evidence_refs"]
    )
    assert any(GAP_LABEL_LOCAL_GLOBAL_MISREAD in gap_id for gap_id in payload["source_gap_ids"])


def test_build_change_request_and_blocker_from_b4_diagnostic() -> None:
    assessment = _build_b4_failing_assessment()
    diagnostic = build_b4_local_global_guardrail_diagnostic(
        gap_records=assessment.gap_records,
        trace_bundle=assessment.trace_bundle,
        interaction_guardrail_breaches=assessment.interaction_guardrail_breaches,
    )

    change_request = build_change_request_from_diagnostic(diagnostic=diagnostic)
    experiment = build_experiment_request_from_change_request(
        change_request=change_request
    )
    blocker = build_promotion_blocker_from_diagnostic(diagnostic=diagnostic)

    assert change_request.to_payload()["object_type"] == CHANGE_REQUEST_OBJECT_TYPE
    assert change_request.target_layer == "M2-M3"
    assert change_request.requires_human_approval is True
    assert blocker.to_payload()["object_type"] == PROMOTION_BLOCKER_OBJECT_TYPE
    assert blocker.blocker_code == GUARDRAIL_CODE_LOCAL_GLOBAL_END
    assert blocker.active is True
    assert experiment.guardrail_codes == [GUARDRAIL_CODE_LOCAL_GLOBAL_END]


def test_block_decision_record_from_promotion_blocker_projects_payload() -> None:
    assessment = _build_b4_failing_assessment()
    diagnostic = build_b4_local_global_guardrail_diagnostic(
        gap_records=assessment.gap_records,
        trace_bundle=assessment.trace_bundle,
        interaction_guardrail_breaches=assessment.interaction_guardrail_breaches,
    )
    blocker = build_promotion_blocker_from_diagnostic(diagnostic=diagnostic)

    decision = build_block_decision_record_from_promotion_blocker(blocker=blocker)

    assert decision.subject_type == "promotion_blocker"
    assert decision.subject_id == blocker.blocker_id
    assert decision.decision == "block"
    assert decision.decision_scope == "promotion"
    assert decision.approver == "system_governance"
    assert decision.status == "recorded"
