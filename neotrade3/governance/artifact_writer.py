"""Artifact writer for NeoTrade3 M5 governance handoff bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .contracts import GovernanceDecisionRecord, ValidationResult
from .handoff import GovernanceHandoffBundle


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass(frozen=True)
class GovernanceArtifactRecord:
    source_run_id: str
    written_at: str
    artifact_path: str
    projected_assessment_count: int
    projected_issue_count: int


@dataclass(frozen=True)
class GovernanceRejectExecutionArtifactRecord:
    validation_id: str
    source_run_id: str
    written_at: str
    artifact_path: str
    baseline_run_id: str
    candidate_run_id: str
    decision_id: str


def write_governance_handoff_artifact(
    *,
    project_root: str | Path,
    bundle: GovernanceHandoffBundle,
    dry_run: bool = False,
) -> GovernanceArtifactRecord:
    project_root_path = Path(project_root)
    source_run_id = str(bundle.source_run_id or "").strip()
    if not source_run_id:
        raise ValueError("Governance handoff bundle source_run_id cannot be empty")

    artifacts_dir = (
        project_root_path / "var/artifacts/governance_handoffs" / source_run_id
    )
    artifact_file = artifacts_dir / "governance_handoff_bundle.json"
    written_at = _now_iso()
    payload = {
        **bundle.to_payload(),
        "written_at": written_at,
    }

    if not dry_run:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return GovernanceArtifactRecord(
        source_run_id=source_run_id,
        written_at=written_at,
        artifact_path=str(artifact_file.relative_to(project_root_path)),
        projected_assessment_count=bundle.projected_assessment_count,
        projected_issue_count=bundle.projected_issue_count,
    )


def write_governance_reject_execution_artifact(
    *,
    project_root: str | Path,
    source_run_id: str,
    validation_result: ValidationResult,
    decision_record: GovernanceDecisionRecord,
    dry_run: bool = False,
) -> GovernanceRejectExecutionArtifactRecord:
    project_root_path = Path(project_root)
    normalized_source_run_id = str(source_run_id or "").strip()
    validation_id = str(validation_result.validation_id or "").strip()
    if not normalized_source_run_id:
        raise ValueError("source_run_id must be non-empty")
    if not validation_id:
        raise ValueError("validation_id must be non-empty")

    artifacts_dir = (
        project_root_path / "var/artifacts/governance_rejections" / validation_id
    )
    artifact_file = artifacts_dir / "governance_reject_execution.json"
    written_at = _now_iso()
    payload = {
        "source_run_id": normalized_source_run_id,
        "validation_id": validation_id,
        "baseline_run_id": validation_result.baseline_run_id,
        "candidate_run_id": validation_result.candidate_run_id,
        "validation_result": validation_result.to_payload(),
        "decision_record": decision_record.to_payload(),
        "written_at": written_at,
    }

    if not dry_run:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return GovernanceRejectExecutionArtifactRecord(
        validation_id=validation_id,
        source_run_id=normalized_source_run_id,
        written_at=written_at,
        artifact_path=str(artifact_file.relative_to(project_root_path)),
        baseline_run_id=validation_result.baseline_run_id,
        candidate_run_id=validation_result.candidate_run_id,
        decision_id=decision_record.decision_id,
    )
