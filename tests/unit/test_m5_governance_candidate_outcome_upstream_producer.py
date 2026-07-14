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
from neotrade3.governance.run_ledger import materialize_governance_handoff
from neotrade3.governance.runtime import (
    run_governance_candidate_outcome_upstream_producer,
    run_governance_candidate_validation_outcome,
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
            candidate_run_id="candidate-run-upstream-001",
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


def test_run_governance_candidate_outcome_upstream_producer_returns_rejected_validation_result(
    tmp_path: Path,
) -> None:
    batch_result, bundle = _materialize_benchmark_and_handoff(tmp_path=tmp_path)

    validation_result = run_governance_candidate_outcome_upstream_producer(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    baseline_validation = bundle.validation_results[0]
    assert validation_result.validation_id == baseline_validation.validation_id
    assert validation_result.experiment_id == baseline_validation.experiment_id
    assert validation_result.baseline_run_id == bundle.source_run_id
    assert validation_result.candidate_run_id == "candidate-run-upstream-001"
    assert validation_result.outcome == "rejected"
    assert validation_result.cleared_guardrail_codes == []
    assert (
        validation_result.remaining_guardrail_codes
        == baseline_validation.remaining_guardrail_codes
    )
    assert validation_result.introduced_risk_count == len(
        baseline_validation.remaining_guardrail_codes
    )
    assert validation_result.evidence_refs
    assert batch_result.candidate_run_context is not None


def test_run_governance_candidate_outcome_upstream_producer_output_is_compatible_with_candidate_validation_persistence(
    tmp_path: Path,
) -> None:
    _, bundle = _materialize_benchmark_and_handoff(tmp_path=tmp_path)

    validation_result = run_governance_candidate_outcome_upstream_producer(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    record = run_governance_candidate_validation_outcome(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        validation_result=validation_result,
    )

    assert record.source_run_id == bundle.source_run_id
    assert record.validation_id == validation_result.validation_id
    assert record.candidate_run_id == validation_result.candidate_run_id
    assert record.outcome == "rejected"


def test_run_governance_candidate_outcome_upstream_producer_does_not_mutate_handoff_artifact(
    tmp_path: Path,
) -> None:
    _, bundle = _materialize_benchmark_and_handoff(tmp_path=tmp_path)
    handoff_file = (
        tmp_path
        / "var/artifacts/governance_handoffs"
        / bundle.source_run_id
        / "governance_handoff_bundle.json"
    )
    before = handoff_file.read_text(encoding="utf-8")

    run_governance_candidate_outcome_upstream_producer(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    after = handoff_file.read_text(encoding="utf-8")
    assert after == before


def test_run_governance_candidate_outcome_upstream_producer_fails_without_handoff(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="persisted governance handoff not found",
    ):
        run_governance_candidate_outcome_upstream_producer(
            project_root=tmp_path,
            source_run_id="missing-source-run",
        )


def test_run_governance_candidate_outcome_upstream_producer_fails_without_candidate_run_context(
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
        run_governance_candidate_outcome_upstream_producer(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
        )


def test_run_governance_candidate_outcome_upstream_producer_fails_for_ambiguous_pending_validations(
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
        run_governance_candidate_outcome_upstream_producer(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
        )
