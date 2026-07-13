from __future__ import annotations

import json
from pathlib import Path

import pytest

from neotrade3.governance.run_ledger import (
    materialize_governance_handoff,
    read_governance_handoff_artifact,
    read_governance_status_transition_artifact,
    read_governance_status_transition_ledger,
)
from neotrade3.governance.runtime import (
    run_governance_reject_execution,
    run_governance_status_transition,
)
from tests.unit.test_m5_governance_candidate_validation_outcome import (
    _materialize_candidate_validation_outcome,
)
from tests.unit.test_m5_governance_run_ledger import _build_reference_bundle


def _materialize_reference_handoff(tmp_path: Path):
    bundle = _build_reference_bundle()
    record = materialize_governance_handoff(
        project_root=tmp_path,
        bundle=bundle,
    )
    return bundle, record


def _handoff_artifact_file(*, tmp_path: Path, source_run_id: str) -> Path:
    return (
        tmp_path
        / "var/artifacts/governance_handoffs"
        / source_run_id
        / "governance_handoff_bundle.json"
    )


def test_run_governance_status_transition_materializes_independent_projection(
    tmp_path: Path,
) -> None:
    bundle, handoff_record = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-1",
    )
    handoff_file = _handoff_artifact_file(
        tmp_path=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    handoff_before = handoff_file.read_text(encoding="utf-8")

    reject_record = run_governance_reject_execution(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        validation_id=validation.validation_id,
    )
    record = run_governance_status_transition(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        validation_id=validation.validation_id,
    )

    transition_artifact = read_governance_status_transition_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )
    transition_ledger = read_governance_status_transition_ledger(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )
    handoff_after = handoff_file.read_text(encoding="utf-8")

    assert record.validation_id == validation.validation_id
    assert record.source_run_id == bundle.source_run_id
    assert record.decision_id == reject_record.decision_id
    assert record.effective_attention_status == "resolved"
    assert record.effective_blocker_active is True
    assert record.artifact_path.endswith("governance_status_transition.json")
    assert record.ledger_path.endswith("governance_status_transition_run.json")
    assert transition_artifact is not None
    assert transition_ledger == record
    assert transition_artifact["validation_id"] == validation.validation_id
    assert (
        transition_artifact["effective_attention_item"]["attention_id"]
        == bundle.attention_items[0].attention_id
    )
    assert transition_artifact["effective_attention_item"]["status"] == "resolved"
    assert (
        transition_artifact["effective_promotion_blocker"]["blocker_id"]
        == bundle.promotion_blockers[0].blocker_id
    )
    assert transition_artifact["effective_promotion_blocker"]["active"] is True
    assert transition_artifact["trigger_artifact_path"] == reject_record.artifact_path
    assert handoff_after == handoff_before
    assert read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    ) is not None
    assert handoff_record.artifact_path.endswith("governance_handoff_bundle.json")


def test_run_governance_status_transition_dry_run_writes_nothing(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-1",
    )
    run_governance_reject_execution(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        validation_id=validation.validation_id,
    )

    record = run_governance_status_transition(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        validation_id=validation.validation_id,
        dry_run=True,
    )

    assert record.validation_id == validation.validation_id
    assert read_governance_status_transition_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    ) is None
    assert read_governance_status_transition_ledger(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    ) is None


def test_run_governance_status_transition_rejects_missing_reject_proof(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-1",
    )

    with pytest.raises(ValueError, match="persisted governance reject execution not found"):
        run_governance_status_transition(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
            validation_id=validation.validation_id,
        )


def test_run_governance_status_transition_rejects_missing_blocker(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-1",
    )
    run_governance_reject_execution(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        validation_id=validation.validation_id,
    )
    artifact_file = _handoff_artifact_file(
        tmp_path=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    payload["promotion_blockers"] = []
    artifact_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="promotion_blocker not found"):
        run_governance_status_transition(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
            validation_id=validation.validation_id,
        )


def test_run_governance_status_transition_rejects_missing_attention_item(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-1",
    )
    run_governance_reject_execution(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        validation_id=validation.validation_id,
    )
    artifact_file = _handoff_artifact_file(
        tmp_path=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    payload["attention_items"] = []
    artifact_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="attention_item not found"):
        run_governance_status_transition(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
            validation_id=validation.validation_id,
        )
