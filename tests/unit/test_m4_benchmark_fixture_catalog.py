from __future__ import annotations

from pathlib import Path

from neotrade3.benchmark import (
    BenchmarkFixtureCatalog,
    build_benchmark_fixture_bundle,
    build_default_benchmark_fixture_catalog,
    load_benchmark_seed_registry,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_SAMPLE_REGISTRY = (
    PROJECT_ROOT / "config/benchmark/validation_seed_samples.json"
)


def test_build_default_benchmark_fixture_catalog_contains_b1_to_b4_fixture_ids() -> None:
    catalog = build_default_benchmark_fixture_catalog()

    assert isinstance(catalog, BenchmarkFixtureCatalog)
    assert "m2_target_opportunity_reference" in catalog.builders
    assert "m2_control_failure_reference" in catalog.builders
    assert "m2_advancing_reference" in catalog.builders
    assert "m2_local_global_guardrail_reference" in catalog.builders


def test_build_benchmark_fixture_bundle_for_b3_seed_returns_reference_fixture() -> None:
    registry = load_benchmark_seed_registry(BENCHMARK_SAMPLE_REGISTRY)
    registration = registry.get_sample("b3_boundary_complex_advancing_seed")

    fixture = build_benchmark_fixture_bundle(registration)

    assert fixture["cycle"].stock_code == "600000"
    assert fixture["shadow_bundle"]["cycle_linkage_state"].supports_continuation is True
    assert fixture["m1_context"]["trading_profile"]["return_20d"] == 0.12


def test_build_benchmark_fixture_bundle_for_b1_seed_returns_target_opportunity_fixture() -> None:
    registry = load_benchmark_seed_registry(BENCHMARK_SAMPLE_REGISTRY)
    registration = registry.get_sample("b1_target_opportunity_seed")

    fixture = build_benchmark_fixture_bundle(registration)
    linkage_state = fixture["shadow_bundle"]["cycle_linkage_state"]
    growth_profile = fixture["shadow_bundle"]["growth_potential_profile"]
    risk_profile = fixture["shadow_bundle"]["top_risk_profile"]

    assert linkage_state.supports_continuation is True
    assert linkage_state.local_end_vs_global_end == "local_end_only"
    assert growth_profile.status == "promising"
    assert risk_profile.risk_level == "low"


def test_build_benchmark_fixture_bundle_for_b2_seed_returns_control_failure_fixture() -> None:
    registry = load_benchmark_seed_registry(BENCHMARK_SAMPLE_REGISTRY)
    registration = registry.get_sample("b2_control_failure_seed")

    fixture = build_benchmark_fixture_bundle(registration)
    linkage_state = fixture["shadow_bundle"]["cycle_linkage_state"]

    assert linkage_state.supports_continuation is False
    assert linkage_state.local_end_vs_global_end == "local_end_only"


def test_build_benchmark_fixture_bundle_for_b4_seed_returns_guardrail_fixture() -> None:
    registry = load_benchmark_seed_registry(BENCHMARK_SAMPLE_REGISTRY)
    registration = registry.get_sample("b4_local_global_guardrail_seed")

    fixture = build_benchmark_fixture_bundle(registration)
    linkage_state = fixture["shadow_bundle"]["cycle_linkage_state"]

    assert linkage_state.supports_continuation is False
    assert linkage_state.local_end_vs_global_end == "possible_global_end"
