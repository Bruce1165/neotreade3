from __future__ import annotations

import json
from pathlib import Path

import pytest

from neotrade3.governance.assembler import build_validation_result
from neotrade3.governance.run_ledger import (
    read_governance_handoff_artifact,
    read_governance_reject_execution_artifact,
    read_governance_reject_execution_ledger,
)
from neotrade3.governance.runtime import run_governance_reject_execution
from tests.unit.test_m5_governance_run_ledger import _build_reference_bundle
from neotrade3.governance.run_ledger import materialize_governance_handoff


def _materialize_reference_handoff(tmp_path: Path):
    bundle = _build_reference_bundle()
    record = materialize_governance_handoff(
        project_root=tmp_path,
        bundle=bundle,
    )
    return bundle, record


def test_run_governance_reject_execution_materializes_independent_artifacts(
    tmp_path: Path,
) -> None:
    bundle, handoff_record = _materialize_reference_handoff(tmp_path)
    validation = build_validation_result(
        validation_id="validation-final-reject",
        experiment_id=bundle.experiment_requests[0].experiment_id,
        baseline_run_id=bundle.source_run_id,
        candidate_run_id="candidate-run-1",
        outcome="rejected",
        introduced_risk_count=2,
        cleared_guardrail_codes=[],
        remaining_guardrail_codes=["interaction.local_global"],
        evidence_refs=[{"kind": "validation_result"}],
    )
    bundle_payload = read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    assert bundle_payload is not None
    bundle_payload["validation_results"].append(validation.to_payload())
    artifact_file = (
        tmp_path
        / "var/artifacts/governance_handoffs"
        / bundle.source_run_id
        / "governance_handoff_bundle.json"
    )
    artifact_file.write_text(
        json.dumps(bundle_payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
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
    validation = build_validation_result(
        validation_id="validation-final-reject",
        experiment_id=bundle.experiment_requests[0].experiment_id,
        baseline_run_id=bundle.source_run_id,
        candidate_run_id="candidate-run-1",
        outcome="rejected",
        introduced_risk_count=1,
        cleared_guardrail_codes=[],
        remaining_guardrail_codes=["interaction.local_global"],
        evidence_refs=[],
    )
    artifact_file = (
        tmp_path
        / "var/artifacts/governance_handoffs"
        / bundle.source_run_id
        / "governance_handoff_bundle.json"
    )
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    payload["validation_results"].append(validation.to_payload())
    artifact_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
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
    validation = build_validation_result(
        validation_id="validation-final-pass",
        experiment_id=bundle.experiment_requests[0].experiment_id,
        baseline_run_id=bundle.source_run_id,
        candidate_run_id="candidate-run-2",
        outcome="passed",
        introduced_risk_count=0,
        cleared_guardrail_codes=["interaction.local_global"],
        remaining_guardrail_codes=[],
        evidence_refs=[],
    )
    artifact_file = (
        tmp_path
        / "var/artifacts/governance_handoffs"
        / bundle.source_run_id
        / "governance_handoff_bundle.json"
    )
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    payload["validation_results"].append(validation.to_payload())
    artifact_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
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
