from __future__ import annotations

from pathlib import Path

import neotrade3.benchmark as benchmark
from neotrade3.benchmark import (
    BenchmarkBatchRunResult,
    load_benchmark_run_manifest,
    materialize_benchmark_batch_run,
    read_benchmark_batch_run_result,
    read_benchmark_run_artifact,
    run_benchmark_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_RUN_MANIFEST = (
    PROJECT_ROOT / "config/benchmark/validation_seed_manifest.json"
)


def test_read_benchmark_batch_run_result_round_trips_persisted_artifact(tmp_path) -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)
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

    assert reconstructed == batch_result
    assert reconstructed is not None
    assert reconstructed.results[0].summary == batch_result.results[0].summary
    assert (
        reconstructed.results[0].summary.front_quality_risk_summary
        == batch_result.results[0].summary.front_quality_risk_summary
    )
    assert reconstructed.results[0].gap_records == batch_result.results[0].gap_records
    assert reconstructed.results[0].trace_bundle == batch_result.results[0].trace_bundle
    assert (
        reconstructed.results[1].interaction_guardrail_breaches
        == batch_result.results[1].interaction_guardrail_breaches
    )


def test_benchmark_batch_run_result_from_dict_ignores_artifact_envelope_keys(
    tmp_path,
) -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )
    materialize_benchmark_batch_run(
        project_root=tmp_path,
        batch_result=batch_result,
    )

    artifact = read_benchmark_run_artifact(
        project_root=tmp_path,
        run_id=batch_result.run_id,
    )
    assert artifact is not None
    assert "written_at" in artifact
    assert artifact["sample_count"] == len(batch_result.executed_sample_ids)

    reconstructed = BenchmarkBatchRunResult.from_dict(artifact)

    assert reconstructed == batch_result
    assert not hasattr(reconstructed, "written_at")
    assert not hasattr(reconstructed, "sample_count")


def test_read_benchmark_batch_run_result_returns_none_for_missing_artifact(
    tmp_path,
) -> None:
    assert (
        read_benchmark_batch_run_result(
            project_root=tmp_path,
            run_id="missing_batch_run",
        )
        is None
    )


def test_benchmark_package_exports_typed_readback_helper() -> None:
    assert benchmark.read_benchmark_batch_run_result is read_benchmark_batch_run_result
