from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from neotrade3.benchmark import (
    BenchmarkBatchRunResult,
    BenchmarkCandidateRunContext,
    load_benchmark_run_manifest,
    materialize_benchmark_batch_run,
    run_benchmark_manifest,
)
from neotrade3.governance import build_validation_result
from neotrade3.governance.handoff import build_governance_handoff_from_batch_run
from neotrade3.governance.run_ledger import (
    materialize_governance_handoff,
    read_governance_candidate_validation_artifact,
    read_governance_candidate_validation_record,
)
from neotrade3.governance.runtime import (
    run_governance_candidate_outcome_bridge,
    run_governance_final_validation_selection,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_RUN_MANIFEST = (
    PROJECT_ROOT / "config/benchmark/validation_seed_manifest.json"
)


def _materialize_benchmark_and_handoff(
    *,
    tmp_path: Path,
    include_candidate_context: bool = True,
):
    manifest = load_benchmark_run_manifest(BENCHMARK_RUN_MANIFEST)
    batch_result = run_benchmark_manifest(
        project_root=PROJECT_ROOT,
        manifest=manifest,
    )
    baseline_bundle = build_governance_handoff_from_batch_run(batch_result=batch_result)
    assert len(baseline_bundle.validation_results) == 1
    baseline_validation = baseline_bundle.validation_results[0]
    candidate_run_context = None
    if include_candidate_context:
        candidate_run_context = BenchmarkCandidateRunContext(
            experiment_id=baseline_validation.experiment_id,
            candidate_run_id="candidate-run-bridge-001",
            source_run_id=batch_result.run_id,
        )
    batch_result = BenchmarkBatchRunResult(
        run_id=batch_result.run_id,
        registry_path=batch_result.registry_path,
        executed_sample_ids=batch_result.executed_sample_ids,
        grade_summary=batch_result.grade_summary,
        bucket_summary=batch_result.bucket_summary,
        results=batch_result.results,
        candidate_run_context=candidate_run_context,
    )
    materialize_benchmark_batch_run(
        project_root=tmp_path,
        batch_result=batch_result,
    )
    bundle = build_governance_handoff_from_batch_run(batch_result=batch_result)
    materialize_governance_handoff(
        project_root=tmp_path,
        bundle=bundle,
    )
    return batch_result, bundle


def test_run_governance_candidate_outcome_bridge_materializes_candidate_validation_record(
    tmp_path: Path,
) -> None:
    _, bundle = _materialize_benchmark_and_handoff(tmp_path=tmp_path)

    record = run_governance_candidate_outcome_bridge(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    artifact = read_governance_candidate_validation_artifact(
        project_root=tmp_path,
        validation_id=record.validation_id,
    )
    ledger = read_governance_candidate_validation_record(
        project_root=tmp_path,
        validation_id=record.validation_id,
    )

    assert record.source_run_id == bundle.source_run_id
    assert record.baseline_run_id == bundle.source_run_id
    assert record.candidate_run_id == "candidate-run-bridge-001"
    assert record.outcome == "rejected"
    assert artifact is not None
    assert ledger == record
    assert artifact["outcome"] == "rejected"
    assert artifact["validation_result"]["candidate_run_id"] == "candidate-run-bridge-001"


def test_run_governance_candidate_outcome_bridge_dry_run_writes_nothing(
    tmp_path: Path,
) -> None:
    _, bundle = _materialize_benchmark_and_handoff(tmp_path=tmp_path)

    record = run_governance_candidate_outcome_bridge(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        dry_run=True,
    )

    assert record.source_run_id == bundle.source_run_id
    assert read_governance_candidate_validation_artifact(
        project_root=tmp_path,
        validation_id=record.validation_id,
    ) is None
    assert read_governance_candidate_validation_record(
        project_root=tmp_path,
        validation_id=record.validation_id,
    ) is None


def test_run_governance_candidate_outcome_bridge_output_is_consumable_by_final_selection(
    tmp_path: Path,
) -> None:
    _, bundle = _materialize_benchmark_and_handoff(tmp_path=tmp_path)

    bridge_record = run_governance_candidate_outcome_bridge(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    final_record = run_governance_final_validation_selection(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    assert final_record.source_run_id == bundle.source_run_id
    assert final_record.selected_validation_id == bridge_record.validation_id
    assert final_record.candidate_run_id == bridge_record.candidate_run_id
    assert final_record.outcome == "rejected"


def test_run_governance_candidate_outcome_bridge_fails_without_candidate_run_context(
    tmp_path: Path,
) -> None:
    _, bundle = _materialize_benchmark_and_handoff(
        tmp_path=tmp_path,
        include_candidate_context=False,
    )

    with pytest.raises(
        ValueError,
        match="persisted benchmark candidate_run_context not found",
    ):
        run_governance_candidate_outcome_bridge(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
        )


def test_run_governance_candidate_outcome_bridge_fails_for_ambiguous_pending_validations(
    tmp_path: Path,
) -> None:
    _, bundle = _materialize_benchmark_and_handoff(tmp_path=tmp_path)
    second_validation = build_validation_result(
        validation_id="extra-diagnostic:cr:experiment:validation",
        experiment_id="extra-diagnostic:cr:experiment",
        baseline_run_id=bundle.source_run_id,
        candidate_run_id="",
        outcome="awaiting_candidate_validation",
        introduced_risk_count=0,
        cleared_guardrail_codes=[],
        remaining_guardrail_codes=["interaction.local_global"],
        evidence_refs=[],
    )
    ambiguous_bundle = replace(
        bundle,
        validation_results=bundle.validation_results + (second_validation,),
    )
    materialize_governance_handoff(
        project_root=tmp_path,
        bundle=ambiguous_bundle,
    )

    with pytest.raises(
        ValueError,
        match="ambiguous pending validation_results",
    ):
        run_governance_candidate_outcome_bridge(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
        )
