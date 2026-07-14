from __future__ import annotations

import json
from pathlib import Path

from neotrade3.benchmark import (
    ASSESSMENT_GRADE_FAIL,
    ASSESSMENT_GRADE_PASS,
    B3_BOUNDARY_COMPLEX_SAMPLE,
    B4_INTERACTION_GUARDRAIL_SAMPLE,
    BenchmarkBatchRunResult,
    BenchmarkCandidateRunContext,
    load_benchmark_run_manifest,
    run_benchmark_manifest,
    write_benchmark_batch_run_artifact,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_RUN_MANIFEST = (
    PROJECT_ROOT / "config/benchmark/validation_seed_manifest.json"
)


def test_write_benchmark_batch_run_artifact_persists_batch_summary(tmp_path) -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )

    record = write_benchmark_batch_run_artifact(
        project_root=tmp_path,
        batch_result=batch_result,
    )

    artifact_path = tmp_path / record.artifact_path
    assert artifact_path.exists()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "validation_seed_v1_batch"
    assert payload["sample_count"] == 2
    assert payload["grade_summary"] == {
        ASSESSMENT_GRADE_PASS: 1,
        ASSESSMENT_GRADE_FAIL: 1,
    }
    assert payload["bucket_summary"] == {
        B3_BOUNDARY_COMPLEX_SAMPLE: 1,
        B4_INTERACTION_GUARDRAIL_SAMPLE: 1,
    }


def test_write_benchmark_batch_run_artifact_dry_run_does_not_write_file(tmp_path) -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )

    record = write_benchmark_batch_run_artifact(
        project_root=tmp_path,
        batch_result=batch_result,
        dry_run=True,
    )

    artifact_path = tmp_path / record.artifact_path
    assert not artifact_path.exists()
    assert record.sample_count == 2


def test_write_benchmark_batch_run_artifact_persists_candidate_run_context(
    tmp_path,
) -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )
    batch_result = BenchmarkBatchRunResult(
        run_id=batch_result.run_id,
        registry_path=batch_result.registry_path,
        executed_sample_ids=batch_result.executed_sample_ids,
        grade_summary=batch_result.grade_summary,
        bucket_summary=batch_result.bucket_summary,
        results=batch_result.results,
        candidate_run_context=BenchmarkCandidateRunContext(
            experiment_id="exp-lowfreq-005",
            candidate_run_id="candidate-run-005",
            source_run_id=batch_result.run_id,
        ),
    )

    record = write_benchmark_batch_run_artifact(
        project_root=tmp_path,
        batch_result=batch_result,
    )

    payload = json.loads((tmp_path / record.artifact_path).read_text(encoding="utf-8"))
    assert payload["candidate_run_context"] == {
        "experiment_id": "exp-lowfreq-005",
        "candidate_run_id": "candidate-run-005",
        "source_run_id": batch_result.run_id,
    }
