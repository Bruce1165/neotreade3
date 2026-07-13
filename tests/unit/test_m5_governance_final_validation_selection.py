from __future__ import annotations

import json
from pathlib import Path

import pytest

from neotrade3.governance.assembler import build_validation_result
from neotrade3.governance.run_ledger import (
    list_governance_candidate_validation_records_for_source_run,
    read_governance_candidate_validation_artifact,
    read_governance_candidate_validation_record,
    read_governance_final_validation_artifact,
    read_governance_final_validation_record,
    read_governance_handoff_artifact,
)
from neotrade3.governance.runtime import (
    run_governance_candidate_validation_outcome,
    run_governance_final_validation_selection,
)
from tests.unit.test_m5_governance_candidate_validation_outcome import (
    _materialize_candidate_validation_outcome,
    _materialize_reference_handoff,
)


def _candidate_validation_ledger_file(*, tmp_path: Path, validation_id: str) -> Path:
    return (
        tmp_path
        / "var/ledgers/governance_candidate_validations"
        / validation_id
        / "governance_candidate_validation_run.json"
    )


def _handoff_artifact_file(*, tmp_path: Path, source_run_id: str) -> Path:
    return (
        tmp_path
        / "var/artifacts/governance_handoffs"
        / source_run_id
        / "governance_handoff_bundle.json"
    )


def _append_second_baseline_validation(*, tmp_path: Path, source_run_id: str) -> str:
    handoff_file = _handoff_artifact_file(tmp_path=tmp_path, source_run_id=source_run_id)
    payload = json.loads(handoff_file.read_text(encoding="utf-8"))
    baseline_validation = payload["validation_results"][0]
    second_validation = build_validation_result(
        validation_id="validation-second",
        experiment_id="diagnostic-second:cr:experiment",
        baseline_run_id=source_run_id,
        candidate_run_id="",
        outcome="awaiting_candidate_validation",
        introduced_risk_count=0,
        cleared_guardrail_codes=[],
        remaining_guardrail_codes=[],
        evidence_refs=[{"kind": "candidate_validation"}],
    ).to_payload()
    payload["validation_results"] = [baseline_validation, second_validation]
    handoff_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(second_validation["validation_id"])


def test_run_governance_final_validation_selection_materializes_independent_projection(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    handoff_before = read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    validation, candidate_record = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="passed",
        candidate_run_id="candidate-run-1",
    )
    candidate_artifact_before = read_governance_candidate_validation_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )
    candidate_ledger_before = read_governance_candidate_validation_record(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )

    record = run_governance_final_validation_selection(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    artifact = read_governance_final_validation_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    ledger = read_governance_final_validation_record(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    handoff_after = read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    candidate_artifact_after = read_governance_candidate_validation_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )
    candidate_ledger_after = read_governance_candidate_validation_record(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    )

    assert record.source_run_id == bundle.source_run_id
    assert record.selected_validation_id == validation.validation_id
    assert record.outcome == "passed"
    assert record.artifact_path.endswith("governance_final_validation.json")
    assert record.ledger_path.endswith("governance_final_validation_run.json")
    assert artifact is not None
    assert ledger == record
    assert artifact["source_run_id"] == bundle.source_run_id
    assert artifact["selected_validation_id"] == validation.validation_id
    assert artifact["baseline_run_id"] == bundle.source_run_id
    assert artifact["candidate_run_id"] == "candidate-run-1"
    assert artifact["outcome"] == "passed"
    assert artifact["selection_basis"] == "unique_persisted_candidate_validation"
    assert artifact["candidate_validation_artifact_path"] == candidate_record.artifact_path
    assert artifact["candidate_validation_ledger_path"] == candidate_record.ledger_path
    assert artifact["handoff_artifact_path"].endswith("governance_handoff_bundle.json")
    assert handoff_after == handoff_before
    assert candidate_artifact_after == candidate_artifact_before
    assert candidate_ledger_after == candidate_ledger_before


def test_run_governance_final_validation_selection_dry_run_writes_nothing(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-2",
    )

    record = run_governance_final_validation_selection(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        dry_run=True,
    )

    assert record.source_run_id == bundle.source_run_id
    assert record.selected_validation_id == validation.validation_id
    assert read_governance_final_validation_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    ) is None
    assert read_governance_final_validation_record(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    ) is None


def test_list_governance_candidate_validation_records_for_source_run_returns_stable_records(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, candidate_record = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="passed",
        candidate_run_id="candidate-run-1",
    )

    records = list_governance_candidate_validation_records_for_source_run(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    assert len(records) == 1
    assert records[0] == candidate_record
    assert records[0].validation_id == validation.validation_id


def test_run_governance_final_validation_selection_rejects_missing_candidate_validation(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)

    with pytest.raises(
        ValueError,
        match="no persisted candidate validation outcome found",
    ):
        run_governance_final_validation_selection(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
        )


def test_run_governance_final_validation_selection_rejects_ambiguous_candidate_validations(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="passed",
        candidate_run_id="candidate-run-1",
    )
    second_validation_id = _append_second_baseline_validation(
        tmp_path=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    second_validation = build_validation_result(
        validation_id=second_validation_id,
        experiment_id="diagnostic-second:cr:experiment",
        baseline_run_id=bundle.source_run_id,
        candidate_run_id="candidate-run-2",
        outcome="rejected",
        introduced_risk_count=1,
        cleared_guardrail_codes=[],
        remaining_guardrail_codes=["interaction.local_global"],
        evidence_refs=[{"kind": "candidate_validation"}],
    )
    run_governance_candidate_validation_outcome(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
        validation_result=second_validation,
    )

    with pytest.raises(ValueError, match="ambiguous candidate validation outcomes"):
        run_governance_final_validation_selection(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
        )


def test_run_governance_final_validation_selection_rejects_baseline_run_mismatch(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="passed",
        candidate_run_id="candidate-run-1",
    )
    ledger_file = _candidate_validation_ledger_file(
        tmp_path=tmp_path,
        validation_id=validation.validation_id,
    )
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    payload["baseline_run_id"] = "foreign-run"
    ledger_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="persisted candidate validation baseline_run_id does not match source_run_id",
    ):
        run_governance_final_validation_selection(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
        )


def test_run_governance_final_validation_selection_rejects_validation_missing_from_handoff(
    tmp_path: Path,
) -> None:
    bundle, _ = _materialize_reference_handoff(tmp_path)
    validation, _ = _materialize_candidate_validation_outcome(
        tmp_path=tmp_path,
        bundle=bundle,
        outcome="rejected",
        candidate_run_id="candidate-run-1",
    )
    handoff_file = (
        tmp_path
        / "var/artifacts/governance_handoffs"
        / bundle.source_run_id
        / "governance_handoff_bundle.json"
    )
    payload = json.loads(handoff_file.read_text(encoding="utf-8"))
    payload["validation_results"] = []
    handoff_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="validation_result not found"):
        run_governance_final_validation_selection(
            project_root=tmp_path,
            source_run_id=bundle.source_run_id,
        )

    assert read_governance_candidate_validation_artifact(
        project_root=tmp_path,
        validation_id=validation.validation_id,
    ) is not None
