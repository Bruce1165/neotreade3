from __future__ import annotations

from pathlib import Path

import pytest

from neotrade3.benchmark import (
    BenchmarkBatchRunResult,
    load_benchmark_run_manifest,
    materialize_benchmark_batch_run,
    read_benchmark_batch_run_result,
    run_benchmark_manifest,
)
from neotrade3.benchmark.batch_runner import (
    BENCHMARK_M1_CONTEXT_SOURCE_TYPE,
    DECISION_ENGINE_M3_FRONT_CONTEXT_SOURCE_TYPE,
    INLINE_REPLAY_REGISTRY_PATH,
    M2_SMALL_CYCLE_SOURCE_TYPE,
    M2_SHADOW_BUNDLE_SOURCE_TYPE,
    RESOLVER_STUB_SOURCE_TYPE,
    BenchmarkRunManifest,
)
from neotrade3.benchmark import (
    BenchmarkM1ContextProjection,
    build_benchmark_m1_context_projection_record_id,
    materialize_benchmark_m1_context_projection,
)
from neotrade3.cycle_intelligence import (
    ShadowCycleIntelligenceBundle,
    build_shadow_cycle_intelligence_bundle_record_id,
    build_shadow_cycle_intelligence_from_m1,
    SmallCycle,
    materialize_shadow_cycle_intelligence_bundle,
    build_small_cycle_record_id,
    materialize_small_cycle,
)
from neotrade3.data_control import D7SecurityMasterMinimal, PF1TradingProfile
from neotrade3.data_control import D1DailyPriceFact, D7TradingDayStatus
from neotrade3.decision_engine import (
    DecisionM3FrontContext,
    build_decision_m3_front_context_record_id,
    materialize_decision_m3_front_context,
    build_entry_state_from_formal_inputs,
    build_identify_state_from_formal_inputs,
    build_m1_constraints_ref,
    build_tracking_state_from_formal_inputs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPLAY_MANIFEST = PROJECT_ROOT / "config" / "benchmark" / "formal_replay_manifest.json"
REPLAY_REFS_MANIFEST = (
    PROJECT_ROOT / "config" / "benchmark" / "formal_replay_refs_manifest.json"
)


def _build_shadow_bundle_from_cycle(
    *,
    cycle: SmallCycle,
) -> ShadowCycleIntelligenceBundle:
    security = D7SecurityMasterMinimal(
        stock_code=cycle.stock_code,
        stock_name="浦发银行",
        asset_type="stock",
        is_delisted=False,
        sector_lv1="金融",
        sector_lv2="银行",
        last_trade_date=cycle.trade_date,
    )
    profile = PF1TradingProfile(
        stock_code=cycle.stock_code,
        as_of_trade_date=cycle.trade_date,
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
    return ShadowCycleIntelligenceBundle.from_bundle(
        build_shadow_cycle_intelligence_from_m1(
            cycle=cycle,
            security_master=security,
            trading_profile=profile,
        )
    )


def _build_m3_front_context_from_cycle(
    *,
    cycle: SmallCycle,
    cycle_linkage_state_ref: dict[str, object],
) -> DecisionM3FrontContext:
    d1_fact = D1DailyPriceFact(
        stock_code=cycle.stock_code,
        trade_date=cycle.trade_date,
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
        stock_code=cycle.stock_code,
        stock_name="浦发银行",
        asset_type="stock",
        is_delisted=False,
        sector_lv1="金融",
        sector_lv2="银行",
        last_trade_date=cycle.trade_date,
    )
    trading_day_status = D7TradingDayStatus(
        target_date=cycle.trade_date,
        is_trading_day=True,
        nearest_trading_day=cycle.trade_date,
        min_trading_day="2026-06-01",
        max_trading_day=cycle.trade_date,
        calendar_covered_until=cycle.trade_date,
        calendar_source="trading_calendar_cache",
    )
    profile = PF1TradingProfile(
        stock_code=cycle.stock_code,
        as_of_trade_date=cycle.trade_date,
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


def test_replay_manifest_parses_without_registry_path() -> None:
    manifest = load_benchmark_run_manifest(REPLAY_MANIFEST)

    assert manifest.run_id == "formal_replay_v1_batch"
    assert manifest.registry_path == INLINE_REPLAY_REGISTRY_PATH
    assert manifest.replay_sample is not None
    assert manifest.replay_sample.sample_id == "formal_front_replay_seed_v1"
    assert manifest.replay_sample.sample_bucket == "R1_formal_front_replay"


def test_replay_manifest_materializes_benchmark_artifact(tmp_path: Path) -> None:
    manifest = load_benchmark_run_manifest(REPLAY_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )
    materialize_benchmark_batch_run(
        project_root=tmp_path,
        batch_result=batch_result,
    )

    reconstructed = read_benchmark_batch_run_result(
        project_root=tmp_path,
        run_id=batch_result.run_id,
    )

    assert batch_result.executed_sample_ids == ("formal_front_replay_seed_v1",)
    assert batch_result.grade_summary == {"pass": 1}
    assert batch_result.bucket_summary == {"R1_formal_front_replay": 1}
    assert reconstructed == batch_result
    assert reconstructed is not None
    assert reconstructed.results[0].summary.assessment_grade == "pass"


def test_replay_manifest_fails_closed_when_inline_payload_is_incomplete() -> None:
    with pytest.raises(
        ValueError,
        match="replay_sample must include complete inline payloads or resolver_refs",
    ):
        BenchmarkRunManifest.from_dict(
            {
                "run_id": "broken_replay_batch",
                "replay_sample": {
                    "sample_id": "broken_replay_seed",
                    "sample_bucket": "R1_formal_front_replay",
                    "stock_code": "600000",
                    "trade_date": "2026-07-07",
                    "target_state_type": "T3_strong_target",
                    "expected_target_state": {},
                    "m2_cycle": {},
                    "m3_context": {},
                },
            }
        )


def test_replay_artifact_round_trips_from_dict_with_inline_registry_marker() -> None:
    manifest = load_benchmark_run_manifest(REPLAY_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )

    reconstructed = BenchmarkBatchRunResult.from_dict(
        {
            **batch_result.to_payload(),
            "sample_count": 1,
            "written_at": "2026-07-14T12:00:00Z",
        }
    )

    assert reconstructed == batch_result
    assert reconstructed.registry_path == INLINE_REPLAY_REGISTRY_PATH


def test_replay_refs_manifest_parses_contract_without_inline_payloads() -> None:
    manifest = load_benchmark_run_manifest(REPLAY_REFS_MANIFEST)

    assert manifest.run_id == "formal_replay_refs_v1_batch"
    assert manifest.registry_path == INLINE_REPLAY_REGISTRY_PATH
    assert manifest.replay_sample is not None
    assert manifest.replay_sample.inline_payload_complete is False
    assert manifest.replay_sample.resolver_refs is not None
    assert (
        manifest.replay_sample.resolver_refs.m2_cycle_ref.source_type
        == RESOLVER_STUB_SOURCE_TYPE
    )
    assert manifest.replay_sample.resolver_refs.m3_context_ref.object_type == (
        "m3_context_bundle"
    )


def test_replay_refs_manifest_materializes_benchmark_artifact(tmp_path: Path) -> None:
    manifest = load_benchmark_run_manifest(REPLAY_REFS_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )
    materialize_benchmark_batch_run(
        project_root=tmp_path,
        batch_result=batch_result,
    )

    reconstructed = read_benchmark_batch_run_result(
        project_root=tmp_path,
        run_id=batch_result.run_id,
    )

    assert batch_result.executed_sample_ids == ("formal_front_replay_refs_seed_v1",)
    assert batch_result.grade_summary == {"pass": 1}
    assert batch_result.bucket_summary == {"R2_formal_refs_replay": 1}
    assert reconstructed == batch_result
    assert reconstructed.results[0].summary.assessment_grade == "pass"


def test_replay_refs_materializes_with_real_m2_cycle_ref(tmp_path: Path) -> None:
    small_cycle = SmallCycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"e1_price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[],
        input_data_version="m1_phase1.v1",
        rule_version="m2_small_cycle.v1alpha1",
    )
    record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    materialize_small_cycle(project_root=tmp_path, small_cycle=small_cycle)

    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "real_m2_cycle_replay_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {
                    "small_cycle_state": {"allowed": ["S2 Advancing"]}
                },
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": M2_SMALL_CYCLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": record_id,
                        "object_type": "small_cycle",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m2-shadow-ref-600000-2026-07-07",
                        "object_type": "m2_shadow_bundle",
                        "object_version": 1
                    },
                    "m1_context_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "ledger_projection",
                        "ref_id": "m1-context-ref-600000-2026-07-07",
                        "object_type": "m1_context_projection",
                        "object_version": 1
                    },
                    "m3_context_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m3-context-ref-600000-2026-07-07",
                        "object_type": "m3_context_bundle",
                        "object_version": 1
                    }
                }
            }
        }
    )

    batch_result = run_benchmark_manifest(
        project_root=tmp_path,
        manifest=manifest,
    )

    assert batch_result.executed_sample_ids == ("formal_front_replay_refs_seed_v1",)
    assert batch_result.grade_summary == {"pass": 1}


def test_replay_refs_materializes_with_real_m2_cycle_ref_and_real_m2_shadow_bundle_ref_and_real_m1_context_ref_and_real_m3_context_ref(
    tmp_path: Path,
) -> None:
    small_cycle = SmallCycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"e1_price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[],
        input_data_version="m1_phase1.v1",
        rule_version="m2_small_cycle.v1alpha1",
    )
    small_cycle_record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    materialize_small_cycle(project_root=tmp_path, small_cycle=small_cycle)
    shadow_bundle = _build_shadow_bundle_from_cycle(cycle=small_cycle)
    shadow_bundle_record_id = build_shadow_cycle_intelligence_bundle_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_shadow_cycle_intelligence_bundle(
        project_root=tmp_path,
        bundle=shadow_bundle,
    )
    m3_context_record_id = build_decision_m3_front_context_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_decision_m3_front_context(
        project_root=tmp_path,
        record_id=m3_context_record_id,
        front_context=_build_m3_front_context_from_cycle(
            cycle=small_cycle,
            cycle_linkage_state_ref=shadow_bundle.to_replay_payload()["cycle_linkage_state"],
        ),
    )

    m1_context_record_id = build_benchmark_m1_context_projection_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_benchmark_m1_context_projection(
        project_root=tmp_path,
        record_id=m1_context_record_id,
        projection=BenchmarkM1ContextProjection(source="benchmark_local_projection"),
    )

    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "real_m2_cycle_real_m1_context_replay_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {
                    "small_cycle_state": {"allowed": ["S2 Advancing"]}
                },
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": M2_SMALL_CYCLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": small_cycle_record_id,
                        "object_type": "small_cycle",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": M2_SHADOW_BUNDLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": shadow_bundle_record_id,
                        "object_type": "m2_shadow_bundle",
                        "object_version": 1
                    },
                    "m1_context_ref": {
                        "source_type": BENCHMARK_M1_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": m1_context_record_id,
                        "object_type": "m1_context_projection",
                        "object_version": 1
                    },
                    "m3_context_ref": {
                        "source_type": DECISION_ENGINE_M3_FRONT_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": m3_context_record_id,
                        "object_type": "m3_front_context",
                        "object_version": 1
                    }
                }
            }
        }
    )

    batch_result = run_benchmark_manifest(
        project_root=tmp_path,
        manifest=manifest,
    )

    assert batch_result.executed_sample_ids == ("formal_front_replay_refs_seed_v1",)
    assert batch_result.grade_summary == {"pass": 1}
    assert batch_result.bucket_summary == {"R2_formal_refs_replay": 1}


def test_replay_refs_contract_fails_closed_when_required_ref_missing() -> None:
    with pytest.raises(
        TypeError,
        match="resolver_refs.m3_context_ref must be a JSON object",
    ):
        BenchmarkRunManifest.from_dict(
            {
                "run_id": "broken_replay_refs_batch",
                "replay_sample": {
                    "sample_id": "formal_front_replay_refs_seed_v1",
                    "sample_bucket": "R2_formal_refs_replay",
                    "stock_code": "600000",
                    "trade_date": "2026-07-07",
                    "target_state_type": "T3_strong_target",
                    "expected_target_state": {},
                    "resolver_refs": {
                        "m2_cycle_ref": {
                            "source_type": "resolver_stub",
                            "ref_kind": "artifact",
                            "ref_id": "m2-cycle",
                            "object_type": "small_cycle",
                            "object_version": 1
                        },
                        "m2_shadow_bundle_ref": {
                            "source_type": "resolver_stub",
                            "ref_kind": "artifact",
                            "ref_id": "m2-shadow",
                            "object_type": "m2_shadow_bundle",
                            "object_version": 1
                        },
                        "m1_context_ref": {
                            "source_type": "resolver_stub",
                            "ref_kind": "ledger_projection",
                            "ref_id": "m1-context",
                            "object_type": "m1_context_projection",
                            "object_version": 1
                        }
                    }
                }
            }
        )


def test_replay_refs_runtime_fails_closed_on_object_type_mismatch() -> None:
    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "mismatch_replay_refs_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {},
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m2-cycle-ref-600000-2026-07-07",
                        "object_type": "wrong_cycle_type",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m2-shadow-ref-600000-2026-07-07",
                        "object_type": "m2_shadow_bundle",
                        "object_version": 1
                    },
                    "m1_context_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "ledger_projection",
                        "ref_id": "m1-context-ref-600000-2026-07-07",
                        "object_type": "m1_context_projection",
                        "object_version": 1
                    },
                    "m3_context_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m3-context-ref-600000-2026-07-07",
                        "object_type": "m3_context_bundle",
                        "object_version": 1
                    }
                }
            }
        }
    )

    with pytest.raises(
        ValueError,
        match="resolver_refs.m2_cycle_ref.object_type mismatch",
    ):
        run_benchmark_manifest(
            project_root=PROJECT_ROOT,
            manifest=manifest,
        )


def test_replay_refs_runtime_fails_closed_when_real_m2_cycle_missing(tmp_path: Path) -> None:
    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "missing_real_m2_cycle_replay_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {},
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": M2_SMALL_CYCLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": "missing-small-cycle-record",
                        "object_type": "small_cycle",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m2-shadow-ref-600000-2026-07-07",
                        "object_type": "m2_shadow_bundle",
                        "object_version": 1
                    },
                    "m1_context_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "ledger_projection",
                        "ref_id": "m1-context-ref-600000-2026-07-07",
                        "object_type": "m1_context_projection",
                        "object_version": 1
                    },
                    "m3_context_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m3-context-ref-600000-2026-07-07",
                        "object_type": "m3_context_bundle",
                        "object_version": 1
                    }
                }
            }
        }
    )

    with pytest.raises(
        ValueError,
        match="resolver_refs.m2_cycle_ref.ref_id is not resolvable in small-cycle owner",
    ):
        run_benchmark_manifest(
            project_root=tmp_path,
            manifest=manifest,
        )


def test_replay_refs_runtime_fails_closed_when_real_m1_context_missing(
    tmp_path: Path,
) -> None:
    small_cycle = SmallCycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"e1_price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[],
        input_data_version="m1_phase1.v1",
        rule_version="m2_small_cycle.v1alpha1",
    )
    small_cycle_record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    materialize_small_cycle(project_root=tmp_path, small_cycle=small_cycle)

    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "missing_real_m1_context_replay_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {},
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": M2_SMALL_CYCLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": small_cycle_record_id,
                        "object_type": "small_cycle",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m2-shadow-ref-600000-2026-07-07",
                        "object_type": "m2_shadow_bundle",
                        "object_version": 1
                    },
                    "m1_context_ref": {
                        "source_type": BENCHMARK_M1_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": "missing-benchmark-m1-context-record",
                        "object_type": "m1_context_projection",
                        "object_version": 1
                    },
                    "m3_context_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m3-context-ref-600000-2026-07-07",
                        "object_type": "m3_context_bundle",
                        "object_version": 1
                    }
                }
            }
        }
    )

    with pytest.raises(
        ValueError,
        match="resolver_refs.m1_context_ref.ref_id is not resolvable in benchmark m1_context owner",
    ):
        run_benchmark_manifest(
            project_root=tmp_path,
            manifest=manifest,
        )


def test_replay_refs_runtime_fails_closed_when_real_m1_context_object_type_mismatches(
    tmp_path: Path,
) -> None:
    small_cycle = SmallCycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"e1_price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[],
        input_data_version="m1_phase1.v1",
        rule_version="m2_small_cycle.v1alpha1",
    )
    small_cycle_record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    materialize_small_cycle(project_root=tmp_path, small_cycle=small_cycle)

    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "mismatch_real_m1_context_object_type_replay_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {},
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": M2_SMALL_CYCLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": small_cycle_record_id,
                        "object_type": "small_cycle",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m2-shadow-ref-600000-2026-07-07",
                        "object_type": "m2_shadow_bundle",
                        "object_version": 1
                    },
                    "m1_context_ref": {
                        "source_type": BENCHMARK_M1_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": "missing-benchmark-m1-context-record",
                        "object_type": "wrong_m1_context_projection",
                        "object_version": 1
                    },
                    "m3_context_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m3-context-ref-600000-2026-07-07",
                        "object_type": "m3_context_bundle",
                        "object_version": 1
                    }
                }
            }
        }
    )

    with pytest.raises(
        ValueError,
        match="resolver_refs.m1_context_ref.object_type mismatch: expected m1_context_projection",
    ):
        run_benchmark_manifest(
            project_root=tmp_path,
            manifest=manifest,
        )


def test_replay_refs_runtime_fails_closed_when_real_m1_context_version_mismatches(
    tmp_path: Path,
) -> None:
    small_cycle = SmallCycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"e1_price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[],
        input_data_version="m1_phase1.v1",
        rule_version="m2_small_cycle.v1alpha1",
    )
    small_cycle_record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    materialize_small_cycle(project_root=tmp_path, small_cycle=small_cycle)

    m1_context_record_id = build_benchmark_m1_context_projection_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_benchmark_m1_context_projection(
        project_root=tmp_path,
        record_id=m1_context_record_id,
        projection=BenchmarkM1ContextProjection(source="benchmark_local_projection"),
    )

    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "mismatch_real_m1_context_version_replay_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {},
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": M2_SMALL_CYCLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": small_cycle_record_id,
                        "object_type": "small_cycle",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m2-shadow-ref-600000-2026-07-07",
                        "object_type": "m2_shadow_bundle",
                        "object_version": 1
                    },
                    "m1_context_ref": {
                        "source_type": BENCHMARK_M1_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": m1_context_record_id,
                        "object_type": "m1_context_projection",
                        "object_version": 999
                    },
                    "m3_context_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m3-context-ref-600000-2026-07-07",
                        "object_type": "m3_context_bundle",
                        "object_version": 1
                    }
                }
            }
        }
    )

    with pytest.raises(
        ValueError,
        match="resolver_refs.m1_context_ref.object_version mismatch: expected 1",
    ):
        run_benchmark_manifest(
            project_root=tmp_path,
            manifest=manifest,
        )


def test_replay_refs_runtime_fails_closed_when_real_m2_shadow_bundle_missing(
    tmp_path: Path,
) -> None:
    small_cycle = SmallCycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"e1_price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[],
        input_data_version="m1_phase1.v1",
        rule_version="m2_small_cycle.v1alpha1",
    )
    small_cycle_record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    materialize_small_cycle(project_root=tmp_path, small_cycle=small_cycle)

    m1_context_record_id = build_benchmark_m1_context_projection_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_benchmark_m1_context_projection(
        project_root=tmp_path,
        record_id=m1_context_record_id,
        projection=BenchmarkM1ContextProjection(source="benchmark_local_projection"),
    )

    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "missing_real_m2_shadow_bundle_replay_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {},
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": M2_SMALL_CYCLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": small_cycle_record_id,
                        "object_type": "small_cycle",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": M2_SHADOW_BUNDLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": "missing-shadow-bundle-record",
                        "object_type": "m2_shadow_bundle",
                        "object_version": 1
                    },
                    "m1_context_ref": {
                        "source_type": BENCHMARK_M1_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": m1_context_record_id,
                        "object_type": "m1_context_projection",
                        "object_version": 1
                    },
                    "m3_context_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m3-context-ref-600000-2026-07-07",
                        "object_type": "m3_context_bundle",
                        "object_version": 1
                    }
                }
            }
        }
    )

    with pytest.raises(
        ValueError,
        match="resolver_refs.m2_shadow_bundle_ref.ref_id is not resolvable in shadow-bundle owner",
    ):
        run_benchmark_manifest(
            project_root=tmp_path,
            manifest=manifest,
        )


def test_replay_refs_runtime_fails_closed_when_real_m2_shadow_bundle_version_mismatches(
    tmp_path: Path,
) -> None:
    small_cycle = SmallCycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"e1_price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[],
        input_data_version="m1_phase1.v1",
        rule_version="m2_small_cycle.v1alpha1",
    )
    small_cycle_record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    materialize_small_cycle(project_root=tmp_path, small_cycle=small_cycle)

    shadow_bundle = _build_shadow_bundle_from_cycle(cycle=small_cycle)
    shadow_bundle_record_id = build_shadow_cycle_intelligence_bundle_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_shadow_cycle_intelligence_bundle(
        project_root=tmp_path,
        bundle=shadow_bundle,
    )

    m1_context_record_id = build_benchmark_m1_context_projection_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_benchmark_m1_context_projection(
        project_root=tmp_path,
        record_id=m1_context_record_id,
        projection=BenchmarkM1ContextProjection(source="benchmark_local_projection"),
    )

    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "mismatch_real_m2_shadow_bundle_version_replay_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {},
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": M2_SMALL_CYCLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": small_cycle_record_id,
                        "object_type": "small_cycle",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": M2_SHADOW_BUNDLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": shadow_bundle_record_id,
                        "object_type": "m2_shadow_bundle",
                        "object_version": 999
                    },
                    "m1_context_ref": {
                        "source_type": BENCHMARK_M1_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": m1_context_record_id,
                        "object_type": "m1_context_projection",
                        "object_version": 1
                    },
                    "m3_context_ref": {
                        "source_type": "resolver_stub",
                        "ref_kind": "artifact",
                        "ref_id": "m3-context-ref-600000-2026-07-07",
                        "object_type": "m3_context_bundle",
                        "object_version": 1
                    }
                }
            }
        }
    )

    with pytest.raises(
        ValueError,
        match="resolver_refs.m2_shadow_bundle_ref.object_version mismatch: expected 1",
    ):
        run_benchmark_manifest(
            project_root=tmp_path,
            manifest=manifest,
        )


def test_replay_refs_runtime_fails_closed_when_real_m3_context_missing(
    tmp_path: Path,
) -> None:
    small_cycle = SmallCycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"e1_price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[],
        input_data_version="m1_phase1.v1",
        rule_version="m2_small_cycle.v1alpha1",
    )
    small_cycle_record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    materialize_small_cycle(project_root=tmp_path, small_cycle=small_cycle)
    shadow_bundle = _build_shadow_bundle_from_cycle(cycle=small_cycle)
    shadow_bundle_record_id = build_shadow_cycle_intelligence_bundle_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_shadow_cycle_intelligence_bundle(
        project_root=tmp_path,
        bundle=shadow_bundle,
    )
    m1_context_record_id = build_benchmark_m1_context_projection_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_benchmark_m1_context_projection(
        project_root=tmp_path,
        record_id=m1_context_record_id,
        projection=BenchmarkM1ContextProjection(source="benchmark_local_projection"),
    )

    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "missing_real_m3_context_replay_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {},
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": M2_SMALL_CYCLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": small_cycle_record_id,
                        "object_type": "small_cycle",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": M2_SHADOW_BUNDLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": shadow_bundle_record_id,
                        "object_type": "m2_shadow_bundle",
                        "object_version": 1
                    },
                    "m1_context_ref": {
                        "source_type": BENCHMARK_M1_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": m1_context_record_id,
                        "object_type": "m1_context_projection",
                        "object_version": 1
                    },
                    "m3_context_ref": {
                        "source_type": DECISION_ENGINE_M3_FRONT_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": "missing-decision-engine-m3-front-context-record",
                        "object_type": "m3_front_context",
                        "object_version": 1
                    }
                }
            }
        }
    )

    with pytest.raises(
        ValueError,
        match="resolver_refs.m3_context_ref.ref_id is not resolvable in decision_engine m3 front owner",
    ):
        run_benchmark_manifest(
            project_root=tmp_path,
            manifest=manifest,
        )


def test_replay_refs_runtime_fails_closed_when_real_m3_context_version_mismatches(
    tmp_path: Path,
) -> None:
    small_cycle = SmallCycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"e1_price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[],
        input_data_version="m1_phase1.v1",
        rule_version="m2_small_cycle.v1alpha1",
    )
    small_cycle_record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    materialize_small_cycle(project_root=tmp_path, small_cycle=small_cycle)
    shadow_bundle = _build_shadow_bundle_from_cycle(cycle=small_cycle)
    shadow_bundle_record_id = build_shadow_cycle_intelligence_bundle_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_shadow_cycle_intelligence_bundle(
        project_root=tmp_path,
        bundle=shadow_bundle,
    )
    m1_context_record_id = build_benchmark_m1_context_projection_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_benchmark_m1_context_projection(
        project_root=tmp_path,
        record_id=m1_context_record_id,
        projection=BenchmarkM1ContextProjection(source="benchmark_local_projection"),
    )
    m3_context_record_id = build_decision_m3_front_context_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_decision_m3_front_context(
        project_root=tmp_path,
        record_id=m3_context_record_id,
        front_context=_build_m3_front_context_from_cycle(
            cycle=small_cycle,
            cycle_linkage_state_ref=shadow_bundle.to_replay_payload()["cycle_linkage_state"],
        ),
    )

    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "mismatch_real_m3_context_version_replay_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {},
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": M2_SMALL_CYCLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": small_cycle_record_id,
                        "object_type": "small_cycle",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": M2_SHADOW_BUNDLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": shadow_bundle_record_id,
                        "object_type": "m2_shadow_bundle",
                        "object_version": 1
                    },
                    "m1_context_ref": {
                        "source_type": BENCHMARK_M1_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": m1_context_record_id,
                        "object_type": "m1_context_projection",
                        "object_version": 1
                    },
                    "m3_context_ref": {
                        "source_type": DECISION_ENGINE_M3_FRONT_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": m3_context_record_id,
                        "object_type": "m3_front_context",
                        "object_version": 999
                    }
                }
            }
        }
    )

    with pytest.raises(
        ValueError,
        match="resolver_refs.m3_context_ref.object_version mismatch: expected 1",
    ):
        run_benchmark_manifest(
            project_root=tmp_path,
            manifest=manifest,
        )


def test_replay_refs_runtime_fails_closed_when_real_m3_context_object_type_mismatches(
    tmp_path: Path,
) -> None:
    small_cycle = SmallCycle(
        stock_code="600000",
        trade_date="2026-07-07",
        cycle_state="S2 Advancing",
        state_stability_level="stable",
        evidence_bundle={"e1_price_structure": {"status": "supported"}},
        confidence={"level": "high"},
        invalidation={"status": "not_triggered"},
        state_transition_log=[],
        input_data_version="m1_phase1.v1",
        rule_version="m2_small_cycle.v1alpha1",
    )
    small_cycle_record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    materialize_small_cycle(project_root=tmp_path, small_cycle=small_cycle)
    shadow_bundle = _build_shadow_bundle_from_cycle(cycle=small_cycle)
    shadow_bundle_record_id = build_shadow_cycle_intelligence_bundle_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_shadow_cycle_intelligence_bundle(
        project_root=tmp_path,
        bundle=shadow_bundle,
    )
    m1_context_record_id = build_benchmark_m1_context_projection_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_benchmark_m1_context_projection(
        project_root=tmp_path,
        record_id=m1_context_record_id,
        projection=BenchmarkM1ContextProjection(source="benchmark_local_projection"),
    )
    m3_context_record_id = build_decision_m3_front_context_record_id(
        stock_code="600000",
        trade_date="2026-07-07",
    )
    materialize_decision_m3_front_context(
        project_root=tmp_path,
        record_id=m3_context_record_id,
        front_context=_build_m3_front_context_from_cycle(
            cycle=small_cycle,
            cycle_linkage_state_ref=shadow_bundle.to_replay_payload()["cycle_linkage_state"],
        ),
    )

    manifest = BenchmarkRunManifest.from_dict(
        {
            "run_id": "mismatch_real_m3_context_object_type_replay_batch",
            "replay_sample": {
                "sample_id": "formal_front_replay_refs_seed_v1",
                "sample_bucket": "R2_formal_refs_replay",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "target_state_type": "T3_strong_target",
                "expected_target_state": {},
                "resolver_refs": {
                    "m2_cycle_ref": {
                        "source_type": M2_SMALL_CYCLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": small_cycle_record_id,
                        "object_type": "small_cycle",
                        "object_version": 1
                    },
                    "m2_shadow_bundle_ref": {
                        "source_type": M2_SHADOW_BUNDLE_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": shadow_bundle_record_id,
                        "object_type": "m2_shadow_bundle",
                        "object_version": 1
                    },
                    "m1_context_ref": {
                        "source_type": BENCHMARK_M1_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": m1_context_record_id,
                        "object_type": "m1_context_projection",
                        "object_version": 1
                    },
                    "m3_context_ref": {
                        "source_type": DECISION_ENGINE_M3_FRONT_CONTEXT_SOURCE_TYPE,
                        "ref_kind": "artifact",
                        "ref_id": m3_context_record_id,
                        "object_type": "wrong_m3_front_context",
                        "object_version": 1
                    }
                }
            }
        }
    )

    with pytest.raises(
        ValueError,
        match="resolver_refs.m3_context_ref.object_type mismatch: expected m3_front_context",
    ):
        run_benchmark_manifest(
            project_root=tmp_path,
            manifest=manifest,
        )
