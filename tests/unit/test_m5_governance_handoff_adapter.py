from __future__ import annotations

from neotrade3.benchmark import (
    ASSESSMENT_GRADE_FAIL,
    ASSESSMENT_GRADE_PASS,
    B4_INTERACTION_GUARDRAIL_SAMPLE,
    GUARDRAIL_CODE_LOCAL_GLOBAL_END,
    build_benchmark_assessment_from_m2_shadow,
    build_benchmark_sample,
)
from neotrade3.benchmark.batch_runner import BenchmarkBatchRunResult
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
    GOVERNANCE_HANDOFF_BUNDLE_OBJECT_TYPE,
    M4_SOURCE_LAYER,
    build_governance_handoff_from_assessment,
    build_governance_handoff_from_batch_run,
)


def _sample_m1_objects(
    *,
    stock_code: str,
    trade_date: str,
) -> tuple[
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
]:
    d1 = D1DailyPriceFact(
        stock_code=stock_code,
        trade_date=trade_date,
        open_price=10.0,
        high_price=10.5,
        low_price=9.9,
        close_price=10.3,
        preclose_price=10.0,
        pct_change=2.0,
        volume_shares=1_000_000.0,
        amount_cny=200_000_000.0,
        turnover_rate=3.0,
        updated_at=f"{trade_date}T15:00:00Z",
    )
    security = D7SecurityMasterMinimal(
        stock_code=stock_code,
        stock_name=f"Stock-{stock_code}",
        asset_type="stock",
        is_delisted=False,
        sector_lv1="finance",
        sector_lv2="bank",
        last_trade_date=trade_date,
    )
    trading_day = D7TradingDayStatus(
        target_date=trade_date,
        is_trading_day=True,
        nearest_trading_day=trade_date,
        min_trading_day="2026-06-01",
        max_trading_day=trade_date,
        calendar_covered_until=trade_date,
        calendar_source="trading_calendar_cache",
    )
    profile = PF1TradingProfile(
        stock_code=stock_code,
        as_of_trade_date=trade_date,
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
    return d1, security, trading_day, profile


def _build_reference_cycle_and_shadow_bundle(
    *,
    stock_code: str,
    trade_date: str,
) -> tuple[object, dict[str, object], dict[str, object]]:
    d1, security, trading_day, profile = _sample_m1_objects(
        stock_code=stock_code,
        trade_date=trade_date,
    )
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


def _build_b4_assessment(
    *,
    stock_code: str,
    trade_date: str,
    misread_local_global: bool,
):
    cycle, shadow_bundle, m1_context = _build_reference_cycle_and_shadow_bundle(
        stock_code=stock_code,
        trade_date=trade_date,
    )
    shadow_bundle["cycle_linkage_state"] = build_cycle_linkage_state(
        stock_code=stock_code,
        trade_date=trade_date,
        small_cycle_ref={"cycle_state": "S2 Advancing"},
        mid_cycle_ref={"fund_cycle": "advancing", "industry_cycle": "advancing"},
        linkage_phase=(
            "semantic_guardrail_violation"
            if misread_local_global
            else "continuation_confirmed"
        ),
        supports_continuation=not misread_local_global,
        local_end_vs_global_end=(
            "global_end_only" if misread_local_global else "local_end_only"
        ),
        confidence={"score": 0.38 if misread_local_global else 0.82},
        evidence_bundle={
            "reason": (
                "misread local end as global end"
                if misread_local_global
                else "local end preserved correctly"
            )
        },
    )
    sample = build_benchmark_sample(
        stock_code=stock_code,
        trade_date=trade_date,
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


def test_assessment_handoff_projects_full_b4_governance_chain() -> None:
    assessment = _build_b4_assessment(
        stock_code="600000",
        trade_date="2026-07-07",
        misread_local_global=True,
    )

    assert assessment.summary.assessment_grade == ASSESSMENT_GRADE_FAIL
    bundle = build_governance_handoff_from_assessment(assessment=assessment)
    payload = bundle.to_payload()

    assert payload["object_type"] == GOVERNANCE_HANDOFF_BUNDLE_OBJECT_TYPE
    assert payload["source_layer"] == M4_SOURCE_LAYER
    assert payload["source_run_id"] == assessment.summary.benchmark_run_id
    assert payload["projected_assessment_count"] == 1
    assert payload["projected_issue_count"] == 1
    assert len(payload["diagnostics"]) == 1
    assert len(payload["change_requests"]) == 1
    assert len(payload["experiment_requests"]) == 1
    assert len(payload["promotion_blockers"]) == 1
    assert (
        payload["promotion_blockers"][0]["blocker_code"]
        == GUARDRAIL_CODE_LOCAL_GLOBAL_END
    )


def test_assessment_handoff_returns_zero_projection_when_b4_is_clean() -> None:
    assessment = _build_b4_assessment(
        stock_code="600000",
        trade_date="2026-07-08",
        misread_local_global=False,
    )

    assert assessment.summary.assessment_grade == ASSESSMENT_GRADE_PASS
    bundle = build_governance_handoff_from_assessment(assessment=assessment)

    assert bundle.source_run_id == assessment.summary.benchmark_run_id
    assert bundle.projected_assessment_count == 1
    assert bundle.projected_issue_count == 0
    assert bundle.diagnostics == ()
    assert bundle.change_requests == ()
    assert bundle.experiment_requests == ()
    assert bundle.promotion_blockers == ()


def test_batch_handoff_preserves_deterministic_projection_order() -> None:
    first_failing = _build_b4_assessment(
        stock_code="600000",
        trade_date="2026-07-07",
        misread_local_global=True,
    )
    clean = _build_b4_assessment(
        stock_code="600002",
        trade_date="2026-07-08",
        misread_local_global=False,
    )
    second_failing = _build_b4_assessment(
        stock_code="600001",
        trade_date="2026-07-09",
        misread_local_global=True,
    )
    batch_result = BenchmarkBatchRunResult(
        run_id="b4_batch_v1",
        registry_path="config/benchmark/validation_seed_samples.json",
        executed_sample_ids=("sample-fail-1", "sample-clean", "sample-fail-2"),
        grade_summary={"fail": 2, "pass": 1},
        bucket_summary={B4_INTERACTION_GUARDRAIL_SAMPLE: 3},
        results=(first_failing, clean, second_failing),
    )

    bundle = build_governance_handoff_from_batch_run(batch_result=batch_result)
    payload = bundle.to_payload()

    assert bundle.source_run_id == "b4_batch_v1"
    assert bundle.projected_assessment_count == 3
    assert bundle.projected_issue_count == 2
    assert [item.symbol for item in bundle.diagnostics] == ["600000", "600001"]
    assert [item["symbol"] for item in payload["diagnostics"]] == ["600000", "600001"]
    assert len(payload["change_requests"]) == 2
    assert len(payload["experiment_requests"]) == 2
    assert len(payload["promotion_blockers"]) == 2


def test_handoff_payload_is_defensively_copied() -> None:
    assessment = _build_b4_assessment(
        stock_code="600000",
        trade_date="2026-07-07",
        misread_local_global=True,
    )
    bundle = build_governance_handoff_from_assessment(assessment=assessment)

    payload = bundle.to_payload()
    payload["diagnostics"].append({"diagnostic_id": "other"})
    payload["change_requests"].append({"cr_id": "other"})

    fresh_payload = bundle.to_payload()
    assert len(fresh_payload["diagnostics"]) == 1
    assert len(fresh_payload["change_requests"]) == 1
