from __future__ import annotations

import json
from pathlib import Path

import pytest

from neotrade3.governance.artifact_writer import (
    GovernanceArtifactRecord,
    write_governance_handoff_artifact,
)
from neotrade3.governance.handoff import GovernanceHandoffBundle
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


def test_artifact_writer_dry_run_returns_record_without_creating_files(
    tmp_path: Path,
) -> None:
    bundle = _build_reference_bundle()

    record = write_governance_handoff_artifact(
        project_root=tmp_path,
        bundle=bundle,
        dry_run=True,
    )

    assert isinstance(record, GovernanceArtifactRecord)
    assert record.source_run_id == bundle.source_run_id
    assert record.projected_assessment_count == bundle.projected_assessment_count
    assert record.projected_issue_count == bundle.projected_issue_count
    assert (
        record.artifact_path
        == f"var/artifacts/governance_handoffs/{bundle.source_run_id}/governance_handoff_bundle.json"
    )
    assert not (tmp_path / record.artifact_path).exists()
    assert not (tmp_path / "var/artifacts/governance_handoffs").exists()


def test_artifact_writer_writes_canonical_json_payload(tmp_path: Path) -> None:
    bundle = _build_reference_bundle()

    record = write_governance_handoff_artifact(
        project_root=tmp_path,
        bundle=bundle,
    )

    artifact_file = tmp_path / record.artifact_path
    assert artifact_file.exists()
    assert artifact_file.name == "governance_handoff_bundle.json"

    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    assert payload == {
        **bundle.to_payload(),
        "written_at": record.written_at,
    }


def test_artifact_writer_returns_project_root_relative_path(tmp_path: Path) -> None:
    bundle = _build_reference_bundle()

    record = write_governance_handoff_artifact(
        project_root=tmp_path,
        bundle=bundle,
        dry_run=True,
    )

    assert not record.artifact_path.startswith(str(tmp_path))
    assert record.artifact_path.endswith("governance_handoff_bundle.json")
    assert Path(record.artifact_path).parts[:3] == (
        "var",
        "artifacts",
        "governance_handoffs",
    )


def test_artifact_writer_rejects_empty_source_run_id(tmp_path: Path) -> None:
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
        write_governance_handoff_artifact(
            project_root=tmp_path,
            bundle=bundle,
        )
