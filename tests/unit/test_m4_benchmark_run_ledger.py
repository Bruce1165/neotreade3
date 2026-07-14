from __future__ import annotations

from pathlib import Path

from neotrade3.benchmark import (
    ASSESSMENT_GRADE_FAIL,
    ASSESSMENT_GRADE_PASS,
    B3_BOUNDARY_COMPLEX_SAMPLE,
    B4_INTERACTION_GUARDRAIL_SAMPLE,
    BenchmarkBatchRunResult,
    BenchmarkCandidateRunContext,
    list_benchmark_run_ledgers,
    load_benchmark_run_manifest,
    materialize_benchmark_batch_run,
    read_benchmark_run_artifact,
    read_benchmark_run_ledger,
    run_benchmark_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_RUN_MANIFEST = (
    PROJECT_ROOT / "config/benchmark/validation_seed_manifest.json"
)


def test_materialize_benchmark_batch_run_persists_ledger_and_artifact(tmp_path) -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )

    record = materialize_benchmark_batch_run(
        project_root=tmp_path,
        batch_result=batch_result,
    )

    ledger = read_benchmark_run_ledger(
        project_root=tmp_path,
        run_id=batch_result.run_id,
    )
    artifact = read_benchmark_run_artifact(
        project_root=tmp_path,
        run_id=batch_result.run_id,
    )

    assert record.run_id == "validation_seed_v1_batch"
    assert record.status == "completed"
    assert record.sample_count == 2
    assert record.grade_summary == {
        ASSESSMENT_GRADE_PASS: 1,
        ASSESSMENT_GRADE_FAIL: 1,
    }
    assert record.bucket_summary == {
        B3_BOUNDARY_COMPLEX_SAMPLE: 1,
        B4_INTERACTION_GUARDRAIL_SAMPLE: 1,
    }
    assert ledger == record
    assert artifact is not None
    assert artifact["run_id"] == "validation_seed_v1_batch"
    assert artifact["sample_count"] == 2


def test_materialize_benchmark_batch_run_dry_run_writes_nothing(tmp_path) -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )

    record = materialize_benchmark_batch_run(
        project_root=tmp_path,
        batch_result=batch_result,
        dry_run=True,
    )

    assert record.run_id == "validation_seed_v1_batch"
    assert read_benchmark_run_ledger(
        project_root=tmp_path,
        run_id=batch_result.run_id,
    ) is None
    assert read_benchmark_run_artifact(
        project_root=tmp_path,
        run_id=batch_result.run_id,
    ) is None


def test_list_benchmark_run_ledgers_returns_latest_run_first(tmp_path) -> None:
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )
    alternate_result = BenchmarkBatchRunResult(
        run_id="validation_seed_v2_batch",
        registry_path=batch_result.registry_path,
        executed_sample_ids=("b3_boundary_complex_advancing_seed",),
        grade_summary={ASSESSMENT_GRADE_PASS: 1},
        bucket_summary={B3_BOUNDARY_COMPLEX_SAMPLE: 1},
        results=(batch_result.results[0],),
    )

    materialize_benchmark_batch_run(
        project_root=tmp_path,
        batch_result=batch_result,
    )
    materialize_benchmark_batch_run(
        project_root=tmp_path,
        batch_result=alternate_result,
    )

    records = list_benchmark_run_ledgers(project_root=tmp_path)

    assert [item.run_id for item in records] == [
        "validation_seed_v2_batch",
        "validation_seed_v1_batch",
    ]


def test_materialize_benchmark_batch_run_projects_candidate_run_context_into_ledger(
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
            experiment_id="exp-lowfreq-003",
            candidate_run_id="candidate-run-003",
            source_run_id=batch_result.run_id,
        ),
    )

    record = materialize_benchmark_batch_run(
        project_root=tmp_path,
        batch_result=batch_result,
    )

    assert record.experiment_id == "exp-lowfreq-003"
    assert record.candidate_run_id == "candidate-run-003"
    assert record.source_run_id == batch_result.run_id
