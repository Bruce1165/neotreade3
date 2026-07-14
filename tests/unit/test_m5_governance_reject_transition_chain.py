from __future__ import annotations

from pathlib import Path

import pytest

from neotrade3.governance.run_ledger import (
    read_governance_final_validation_artifact,
    read_governance_final_validation_record,
    read_governance_reject_execution_artifact,
    read_governance_reject_execution_ledger,
    read_governance_status_transition_artifact,
    read_governance_status_transition_ledger,
)
from neotrade3.governance.runtime import run_governance_reject_transition_chain
from tests.unit.test_m5_governance_candidate_validation_outcome import (
    _materialize_candidate_validation_outcome,
    _materialize_reference_handoff,
)


def test_run_governance_reject_transition_chain_executes_rejected_chain(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-chain-001",
    )

    result = run_governance_reject_transition_chain(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    final_record = read_governance_final_validation_record(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    reject_record = read_governance_reject_execution_ledger(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )
    transition_record = read_governance_status_transition_ledger(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )

    assert result["source_run_id"] == bundle.source_run_id
    assert result["selected_validation_id"] == validation.validation_id
    assert result["outcome"] == "rejected"
    assert result["executed_reject_execution"] is True
    assert result["executed_status_transition"] is True
    assert final_record is not None
    assert final_record.selected_validation_id == validation.validation_id
    assert reject_record is not None
    assert reject_record.validation_id == validation.validation_id
    assert transition_record is not None
    assert transition_record.validation_id == validation.validation_id


def test_run_governance_reject_transition_chain_stops_after_passed_selection(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="passed",
        candidate_run_id="candidate-run-chain-002",
    )

    result = run_governance_reject_transition_chain(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    assert result["selected_validation_id"] == validation.validation_id
    assert result["outcome"] == "passed"
    assert result["executed_reject_execution"] is False
    assert result["executed_status_transition"] is False
    assert read_governance_final_validation_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    ) is not None
    assert read_governance_reject_execution_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    ) is None
    assert read_governance_status_transition_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    ) is None


def test_run_governance_reject_transition_chain_dry_run_writes_nothing(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-chain-003",
    )

    result = run_governance_reject_transition_chain(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        dry_run=True,
    )

    assert result["selected_validation_id"] == validation.validation_id
    assert result["executed_reject_execution"] is True
    assert result["executed_status_transition"] is True
    assert read_governance_final_validation_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    ) is None
    assert read_governance_reject_execution_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    ) is None
    assert read_governance_status_transition_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    ) is None


def test_run_governance_reject_transition_chain_fails_without_candidate_validation(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)

    with pytest.raises(
        ValueError,
        match="no persisted candidate validation outcome found",
    ):
        run_governance_reject_transition_chain(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
        )
