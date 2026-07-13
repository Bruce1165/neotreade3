from __future__ import annotations

from pathlib import Path

import pytest

from neotrade3.governance.run_ledger import (
    read_governance_handoff_artifact,
    read_governance_reject_execution_artifact,
    read_governance_reject_execution_ledger,
)
from neotrade3.governance.runtime import run_governance_reject_execution
from tests.unit.test_m5_governance_candidate_validation_outcome import (
    _materialize_candidate_validation_outcome,
    _materialize_reference_handoff,
)


def test_run_governance_reject_execution_materializes_independent_artifacts(
    tmp_path: Path,
) -> None:
    bundle, handoff_record = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-1",
    )

    record = run_governance_reject_execution(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        validation_id=validation.validation_id,
    )

    reject_artifact = read_governance_reject_execution_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )
    reject_ledger = read_governance_reject_execution_ledger(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )
    handoff_after = read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    assert record.validation_id == validation.validation_id
    assert record.source_run_id == bundle.source_run_id
    assert record.decision == "reject"
    assert record.artifact_path.endswith("governance_reject_execution.json")
    assert record.ledger_path.endswith("governance_reject_execution_run.json")
    assert reject_artifact is not None
    assert reject_ledger is not None
    assert reject_artifact["validation_id"] == validation.validation_id
    assert reject_artifact["decision_record"]["decision"] == "reject"
    assert reject_artifact["validation_result"]["outcome"] == "rejected"
    assert reject_ledger == record
    assert handoff_after is not None
    assert handoff_after["written_at"] == handoff_record.written_at
    assert (
        tmp_path / "var/artifacts/governance_handoffs" / bundle.source_run_id / "governance_handoff_bundle.json"
    ).exists()


def test_run_governance_reject_execution_dry_run_writes_nothing(tmp_path: Path) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-1",
    )

    record = run_governance_reject_execution(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        validation_id=validation.validation_id,
        dry_run=True,
    )

    assert record.validation_id == validation.validation_id
    assert read_governance_reject_execution_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    ) is None
    assert read_governance_reject_execution_ledger(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    ) is None


def test_run_governance_reject_execution_rejects_missing_validation_id(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)

    with pytest.raises(ValueError, match="validation_result not found"):
        run_governance_reject_execution(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
            validation_id="missing-validation",
        )


def test_run_governance_reject_execution_rejects_non_rejected_outcome(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="passed",
        candidate_run_id="candidate-run-2",
    )

    with pytest.raises(ValueError, match="validation_result.outcome must be rejected"):
        run_governance_reject_execution(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
            validation_id=validation.validation_id,
        )


def test_run_governance_reject_execution_rejects_missing_handoff_bundle(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="persisted governance handoff not found"):
        run_governance_reject_execution(
            project_root=tmp_path,
            source_run_id="missing-source-run",
            validation_id="validation-final-reject",
        )
