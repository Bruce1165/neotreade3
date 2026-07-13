from __future__ import annotations

from pathlib import Path

import pytest

from neotrade3.governance.assembler import build_validation_result
from neotrade3.governance.run_ledger import (
    read_governance_candidate_validation_artifact,
    read_governance_candidate_validation_record,
    read_governance_handoff_artifact,
    materialize_governance_handoff,
)
from neotrade3.governance.runtime import run_governance_candidate_validation_outcome
from tests.unit.test_m5_governance_run_ledger import _build_reference_bundle


def _materialize_reference_handoff(tmp_path: Path):
    bundle = _build_reference_bundle()
    record = materialize_governance_handoff(
        project_root=tmp_path,
        bundle=bundle,
    )
    return bundle, record


def _build_final_validation_result(
    *,
    bundle,
    outcome: str = "rejected",
    candidate_run_id: str = "candidate-run-1",
):
    baseline_validation = bundle.validation_results[0]
    return build_validation_result(
        validation_id=baseline_validation.validation_id,
        experiment_id=baseline_validation.experiment_id,
        baseline_run_id=bundle.source_run_id,
        candidate_run_id=candidate_run_id,
        outcome=outcome,
        introduced_risk_count=2 if outcome == "rejected" else 0,
        cleared_guardrail_codes=[] if outcome == "rejected" else ["interaction.local_global"],
        remaining_guardrail_codes=(
            ["interaction.local_global"] if outcome == "rejected" else []
        ),
        evidence_refs=[{"kind": "candidate_validation"}],
    )


def _materialize_candidate_validation_outcome(
    *,
    tmp_path: Path,
    bundle,
    outcome: str = "rejected",
    candidate_run_id: str = "candidate-run-1",
    dry_run: bool = False,
):
    validation = _build_final_validation_result(
        bundle=bundle,
        outcome=outcome,
        candidate_run_id=candidate_run_id,
    )
    record = run_governance_candidate_validation_outcome(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        validation_result=validation,
        dry_run=dry_run,
    )
    return validation, record


def test_run_governance_candidate_validation_outcome_materializes_rejected_artifacts(
    tmp_path: Path,
) -> None:
    bundle, handoff_record = _materialize_reference_handoff(tmp_path)
    handoff_before = read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    validation, record = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-1",
    )

    artifact = read_governance_candidate_validation_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )
    ledger = read_governance_candidate_validation_record(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )
    handoff_after = read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    assert record.validation_id == validation.validation_id
    assert record.source_run_id == bundle.source_run_id
    assert record.outcome == "rejected"
    assert record.artifact_path.endswith("governance_candidate_validation.json")
    assert record.ledger_path.endswith("governance_candidate_validation_run.json")
    assert artifact is not None
    assert ledger == record
    assert artifact["validation_id"] == validation.validation_id
    assert artifact["source_run_id"] == bundle.source_run_id
    assert artifact["outcome"] == "rejected"
    assert artifact["validation_result"]["candidate_run_id"] == "candidate-run-1"
    assert handoff_before == handoff_after
    assert handoff_after is not None
    assert handoff_after["written_at"] == handoff_record.written_at


def test_run_governance_candidate_validation_outcome_materializes_passed_artifacts(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)

    validation, record = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="passed",
        candidate_run_id="candidate-run-2",
    )

    artifact = read_governance_candidate_validation_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )

    assert record.outcome == "passed"
    assert artifact is not None
    assert artifact["outcome"] == "passed"
    assert artifact["validation_result"]["candidate_run_id"] == "candidate-run-2"


def test_run_governance_candidate_validation_outcome_dry_run_writes_nothing(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)

    validation, record = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        dry_run=True,
    )

    assert record.validation_id == validation.validation_id
    assert read_governance_candidate_validation_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    ) is None
    assert read_governance_candidate_validation_record(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    ) is None


def test_run_governance_candidate_validation_outcome_rejects_missing_handoff(
    tmp_path: Path,
) -> None:
    validation = build_validation_result(
        validation_id="validation-missing",
        experiment_id="diag:cr:experiment",
        baseline_run_id="missing-source-run",
        candidate_run_id="candidate-run-1",
        outcome="rejected",
        introduced_risk_count=1,
        cleared_guardrail_codes=[],
        remaining_guardrail_codes=["interaction.local_global"],
        evidence_refs=[],
    )

    with pytest.raises(ValueError, match="persisted governance handoff not found"):
        run_governance_candidate_validation_outcome(
            project_root=tmp_path,
            source_run_id="missing-source-run",
            validation_result=validation,
        )


def test_run_governance_candidate_validation_outcome_rejects_missing_baseline_validation(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation = build_validation_result(
        validation_id="validation-missing",
        experiment_id=bundle.validation_results[0].experiment_id,
        baseline_run_id=bundle.source_run_id,
        candidate_run_id="candidate-run-1",
        outcome="rejected",
        introduced_risk_count=1,
        cleared_guardrail_codes=[],
        remaining_guardrail_codes=["interaction.local_global"],
        evidence_refs=[],
    )

    with pytest.raises(ValueError, match="validation_result not found"):
        run_governance_candidate_validation_outcome(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
            validation_result=validation,
        )


def test_run_governance_candidate_validation_outcome_rejects_pending_outcome(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    pending_validation = _build_final_validation_result(
        bundle=bundle,
        outcome="awaiting_candidate_validation",
        candidate_run_id="",
    )

    with pytest.raises(
        ValueError,
        match="validation_result.outcome must not be awaiting_candidate_validation",
    ):
        run_governance_candidate_validation_outcome(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
            validation_result=pending_validation,
        )
