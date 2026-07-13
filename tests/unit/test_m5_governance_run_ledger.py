from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from neotrade3.governance.handoff import GovernanceHandoffBundle
from neotrade3.governance.run_ledger import (
    GovernanceRunLedgerRecord,
    list_governance_run_ledgers,
    materialize_governance_handoff,
    read_governance_handoff_artifact,
    read_governance_run_ledger,
)
from tests.unit.test_m5_governance_handoff_adapter import (
    _build_b4_assessment,
)


def _build_reference_bundle() -> GovernanceHandoffBundle:
    from neotrade3.governance import build_governance_handoff_from_assessment

    assessment = _build_b4_assessment(
        stock_code="600000",
        trade_date="2026-07-07",
        misread_local_global=True,
    )
    return build_governance_handoff_from_assessment(assessment=assessment)


def test_materialize_governance_handoff_persists_ledger_and_artifact(
    tmp_path: Path,
) -> None:
    bundle = _build_reference_bundle()

    record = materialize_governance_handoff(
        project_root=tmp_path,
        bundle=bundle,
    )

    ledger = read_governance_run_ledger(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    artifact = read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    assert isinstance(record, GovernanceRunLedgerRecord)
    assert record.source_run_id == bundle.source_run_id
    assert record.status == "completed"
    assert record.source_layer == bundle.source_layer
    assert record.projected_assessment_count == bundle.projected_assessment_count
    assert record.projected_issue_count == bundle.projected_issue_count
    assert record.diagnostic_count == len(bundle.diagnostics)
    assert record.change_request_count == len(bundle.change_requests)
    assert record.experiment_request_count == len(bundle.experiment_requests)
    assert record.validation_result_count == len(bundle.validation_results)
    assert record.promotion_blocker_count == len(bundle.promotion_blockers)
    assert record.attention_item_count == len(bundle.attention_items)
    assert record.decision_record_count == len(bundle.decision_records)
    assert (
        tmp_path / record.ledger_path
    ).exists()
    assert (
        tmp_path / record.artifact_path
    ).exists()
    assert ledger == record
    assert artifact == {
        **bundle.to_payload(),
        "written_at": record.written_at,
    }


def test_materialize_governance_handoff_dry_run_writes_nothing(tmp_path: Path) -> None:
    bundle = _build_reference_bundle()

    record = materialize_governance_handoff(
        project_root=tmp_path,
        bundle=bundle,
        dry_run=True,
    )

    assert record.source_run_id == bundle.source_run_id
    assert not (tmp_path / record.ledger_path).exists()
    assert not (tmp_path / record.artifact_path).exists()
    assert read_governance_run_ledger(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    ) is None
    assert read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    ) is None


def test_read_governance_run_ledger_returns_persisted_summary(tmp_path: Path) -> None:
    bundle = _build_reference_bundle()
    record = materialize_governance_handoff(
        project_root=tmp_path,
        bundle=bundle,
    )

    ledger = read_governance_run_ledger(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    assert ledger == record


def test_read_governance_handoff_artifact_returns_persisted_payload(
    tmp_path: Path,
) -> None:
    bundle = _build_reference_bundle()
    record = materialize_governance_handoff(
        project_root=tmp_path,
        bundle=bundle,
    )

    artifact = read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    assert artifact == {
        **bundle.to_payload(),
        "written_at": record.written_at,
    }


def test_list_governance_run_ledgers_returns_latest_run_first(tmp_path: Path) -> None:
    base_bundle = _build_reference_bundle()
    alternate_bundle = replace(
        base_bundle,
        source_run_id="governance-batch-v2",
    )
    earliest_bundle = replace(
        base_bundle,
        source_run_id="governance-batch-v1",
    )

    materialize_governance_handoff(
        project_root=tmp_path,
        bundle=earliest_bundle,
    )
    materialize_governance_handoff(
        project_root=tmp_path,
        bundle=alternate_bundle,
    )

    records = list_governance_run_ledgers(project_root=tmp_path)

    assert [item.source_run_id for item in records] == [
        "governance-batch-v2",
        "governance-batch-v1",
    ]


def test_materialize_governance_handoff_rejects_empty_source_run_id(
    tmp_path: Path,
) -> None:
    bundle = GovernanceHandoffBundle(
        source_run_id="   ",
        source_layer="M4",
        projected_assessment_count=1,
        projected_issue_count=0,
    )

    with pytest.raises(
        ValueError,
        match="source_run_id cannot be empty",
    ):
        materialize_governance_handoff(
            project_root=tmp_path,
            bundle=bundle,
        )
