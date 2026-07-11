from __future__ import annotations

from pathlib import Path

from neotrade3.benchmark import (
    ASSESSMENT_GRADE_FAIL,
    ASSESSMENT_GRADE_PASS,
    B1_TARGET_OPPORTUNITY_SAMPLE,
    B2_CONTROL_FAILURE_SAMPLE,
    B3_BOUNDARY_COMPLEX_SAMPLE,
    B4_INTERACTION_GUARDRAIL_SAMPLE,
    BenchmarkRunManifest,
    load_benchmark_run_manifest,
    run_benchmark_manifest,
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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_RUN_MANIFEST = (
    PROJECT_ROOT / "config/benchmark/validation_seed_manifest.json"
)
BENCHMARK_RUN_MANIFEST_V2 = (
    PROJECT_ROOT / "config/benchmark/validation_seed_v2_manifest.json"
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


def _fixture_provider(registration):
    cycle, shadow_bundle, m1_context = _build_reference_cycle_and_shadow_bundle()
    if registration.sample_id == "b1_target_opportunity_seed":
        return {
            "cycle": cycle,
            "shadow_bundle": shadow_bundle,
            "m1_context": m1_context,
        }

    if registration.sample_id == "b2_control_failure_seed":
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
            evidence_bundle={"override": "batch_runner_control_failure_test"},
            rule_version="m2_cycle_linkage.v1alpha1",
        )
        return {
            "cycle": cycle,
            "shadow_bundle": {**shadow_bundle, "cycle_linkage_state": bad_linkage},
            "m1_context": m1_context,
        }

    if registration.sample_id == "b3_boundary_complex_advancing_seed":
        return {
            "cycle": cycle,
            "shadow_bundle": shadow_bundle,
            "m1_context": m1_context,
        }

    if registration.sample_id == "b4_local_global_guardrail_seed":
        _, security, _, profile = _sample_m1_objects()
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
            evidence_bundle={"override": "batch_runner_guardrail_test"},
            rule_version="m2_cycle_linkage.v1alpha1",
        )
        return {
            "cycle": cycle,
            "shadow_bundle": {
                "wave_hypothesis": build_small_cycle_wave_hypothesis_from_formal_inputs(
                    cycle=cycle
                ),
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
            },
            "m1_context": m1_context,
        }

    raise KeyError(f"unsupported sample_id for fixture provider: {registration.sample_id}")


def test_load_benchmark_run_manifest_reads_registered_seed_batch() -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)

    assert isinstance(manifest, BenchmarkRunManifest)
    assert manifest.run_id == "validation_seed_v1_batch"
    assert manifest.registry_path == "config/benchmark/validation_seed_samples.json"
    assert manifest.sample_ids == (
        "b3_boundary_complex_advancing_seed",
        "b4_local_global_guardrail_seed",
    )


def test_load_benchmark_run_manifest_reads_b1_b2_seed_batch() -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST_V2)

    assert isinstance(manifest, BenchmarkRunManifest)
    assert manifest.run_id == "validation_seed_v2_batch"
    assert manifest.registry_path == "config/benchmark/validation_seed_samples.json"
    assert manifest.sample_ids == (
        "b1_target_opportunity_seed",
        "b2_control_failure_seed",
    )


def test_run_benchmark_manifest_executes_seed_batch_and_aggregates_summary() -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)

    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
        fixture_provider=_fixture_provider,
    )

    payload = batch_result.to_payload()
    assert payload["run_id"] == "validation_seed_v1_batch"
    assert payload["executed_sample_ids"] == [
        "b3_boundary_complex_advancing_seed",
        "b4_local_global_guardrail_seed",
    ]
    assert payload["grade_summary"] == {
        ASSESSMENT_GRADE_PASS: 1,
        ASSESSMENT_GRADE_FAIL: 1,
    }
    assert payload["bucket_summary"] == {
        B3_BOUNDARY_COMPLEX_SAMPLE: 1,
        B4_INTERACTION_GUARDRAIL_SAMPLE: 1,
    }
    assert len(payload["results"]) == 2


def test_run_benchmark_manifest_executes_b1_b2_seed_batch_and_aggregates_summary() -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST_V2)

    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
        fixture_provider=_fixture_provider,
    )

    payload = batch_result.to_payload()
    assert payload["run_id"] == "validation_seed_v2_batch"
    assert payload["executed_sample_ids"] == [
        "b1_target_opportunity_seed",
        "b2_control_failure_seed",
    ]
    assert payload["grade_summary"] == {
        ASSESSMENT_GRADE_PASS: 1,
        ASSESSMENT_GRADE_FAIL: 1,
    }
    assert payload["bucket_summary"] == {
        B1_TARGET_OPPORTUNITY_SAMPLE: 1,
        B2_CONTROL_FAILURE_SAMPLE: 1,
    }
    assert len(payload["results"]) == 2


def test_run_benchmark_manifest_uses_formal_fixture_catalog_by_default() -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)

    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )

    payload = batch_result.to_payload()
    assert payload["grade_summary"] == {
        ASSESSMENT_GRADE_PASS: 1,
        ASSESSMENT_GRADE_FAIL: 1,
    }
    assert payload["bucket_summary"] == {
        B3_BOUNDARY_COMPLEX_SAMPLE: 1,
        B4_INTERACTION_GUARDRAIL_SAMPLE: 1,
    }


def test_run_benchmark_manifest_v2_uses_formal_fixture_catalog_by_default() -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST_V2)

    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )

    payload = batch_result.to_payload()
    assert payload["grade_summary"] == {
        ASSESSMENT_GRADE_PASS: 1,
        ASSESSMENT_GRADE_FAIL: 1,
    }
    assert payload["bucket_summary"] == {
        B1_TARGET_OPPORTUNITY_SAMPLE: 1,
        B2_CONTROL_FAILURE_SAMPLE: 1,
    }


def test_run_benchmark_manifest_only_executes_selected_sample_ids() -> None:
    manifest = BenchmarkRunManifest(
        run_id="validation_seed_v1_b3_only",
        registry_path="config/benchmark/validation_seed_samples.json",
        sample_ids=("b3_boundary_complex_advancing_seed",),
        description="only run the B3 seed",
    )

    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
        fixture_provider=_fixture_provider,
    )

    payload = batch_result.to_payload()
    assert payload["executed_sample_ids"] == ["b3_boundary_complex_advancing_seed"]
    assert payload["grade_summary"] == {ASSESSMENT_GRADE_PASS: 1}
    assert payload["bucket_summary"] == {B3_BOUNDARY_COMPLEX_SAMPLE: 1}
