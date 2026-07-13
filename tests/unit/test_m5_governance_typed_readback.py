from __future__ import annotations

from pathlib import Path

import pytest

from neotrade3.governance import build_governance_handoff_from_assessment
from neotrade3.governance.handoff import GovernanceHandoffBundle
from neotrade3.governance.run_ledger import (
    materialize_governance_handoff,
    read_governance_handoff_artifact,
    read_governance_handoff_bundle,
)
from tests.unit.test_m5_governance_handoff_adapter import _build_b4_assessment


def _build_reference_bundle() -> GovernanceHandoffBundle:
    assessment = _build_b4_assessment(
        stock_code="600000",
        trade_date="2026-07-07",
        misread_local_global=True,
    )
    return build_governance_handoff_from_assessment(assessment=assessment)


def test_read_governance_handoff_bundle_round_trips_materialized_payload(
    tmp_path: Path,
) -> None:
    bundle = _build_reference_bundle()
    record = materialize_governance_handoff(
        project_root=tmp_path,
        bundle=bundle,
    )

    typed_bundle = read_governance_handoff_bundle(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )

    assert typed_bundle == bundle
    assert typed_bundle is not None
    assert typed_bundle.diagnostics[0].diagnostic_id == bundle.diagnostics[0].diagnostic_id
    assert (
        typed_bundle.validation_results[0].outcome
        == "awaiting_candidate_validation"
    )
    assert typed_bundle.attention_items[0].attention_id.endswith(":attention")
    assert typed_bundle.decision_records[0].decision == "block"
    raw_artifact = read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id=bundle.source_run_id,
    )
    assert raw_artifact is not None
    assert raw_artifact["written_at"] == record.written_at
    assert not hasattr(typed_bundle, "written_at")


def test_governance_handoff_bundle_from_dict_tolerates_artifact_envelope() -> None:
    bundle = _build_reference_bundle()
    payload = {
        **bundle.to_payload(),
        "written_at": "2026-07-13T12:00:00Z",
    }

    restored = GovernanceHandoffBundle.from_dict(payload)

    assert restored == bundle


def test_read_governance_handoff_bundle_returns_none_for_missing_artifact(
    tmp_path: Path,
) -> None:
    assert read_governance_handoff_bundle(
        project_root=tmp_path,
        source_run_id="missing-governance-run",
    ) is None


def test_read_governance_handoff_bundle_rejects_non_object_root(
    tmp_path: Path,
) -> None:
    artifact_file = (
        tmp_path
        / "var/artifacts/governance_handoffs/bad-run/governance_handoff_bundle.json"
    )
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text("[]\n", encoding="utf-8")

    assert read_governance_handoff_artifact(
        project_root=tmp_path,
        source_run_id="bad-run",
    ) is None
    assert read_governance_handoff_bundle(
        project_root=tmp_path,
        source_run_id="bad-run",
    ) is None


def test_governance_handoff_bundle_from_dict_rejects_invalid_nested_payloads() -> None:
    bundle = _build_reference_bundle()
    payload = bundle.to_payload()
    payload["validation_results"] = ["bad-item"]

    with pytest.raises(TypeError, match="validation_results items must be JSON objects"):
        GovernanceHandoffBundle.from_dict(payload)
