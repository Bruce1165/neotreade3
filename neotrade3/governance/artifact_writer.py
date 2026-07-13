"""Artifact writer for NeoTrade3 M5 governance handoff bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .contracts import AttentionItem, GovernanceDecisionRecord, PromotionBlocker, ValidationResult
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


@dataclass(frozen=True)
class GovernanceCandidateValidationArtifactRecord:
    validation_id: str
    source_run_id: str
    written_at: str
    artifact_path: str
    baseline_run_id: str
    candidate_run_id: str
    outcome: str


@dataclass(frozen=True)
class GovernanceStatusTransitionArtifactRecord:
    validation_id: str
    source_run_id: str
    written_at: str
    artifact_path: str
    baseline_run_id: str
    candidate_run_id: str
    decision_id: str
    effective_attention_id: str
    effective_blocker_id: str


@dataclass(frozen=True)
class GovernanceFinalValidationArtifactRecord:
    source_run_id: str
    written_at: str
    artifact_path: str
    selected_validation_id: str
    baseline_run_id: str
    candidate_run_id: str
    outcome: str


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


def write_governance_candidate_validation_artifact(
    *,
    project_root: str | Path,
    source_run_id: str,
    validation_result: ValidationResult,
    dry_run: bool = False,
) -> GovernanceCandidateValidationArtifactRecord:
    project_root_path = Path(project_root)
    normalized_source_run_id = str(source_run_id or "").strip()
    validation_id = str(validation_result.validation_id or "").strip()
    if not normalized_source_run_id:
        raise ValueError("source_run_id must be non-empty")
    if not validation_id:
        raise ValueError("validation_id must be non-empty")

    artifacts_dir = (
        project_root_path
        / "var/artifacts/governance_candidate_validations"
        / validation_id
    )
    artifact_file = artifacts_dir / "governance_candidate_validation.json"
    written_at = _now_iso()
    payload = {
        "source_run_id": normalized_source_run_id,
        "validation_id": validation_id,
        "baseline_run_id": validation_result.baseline_run_id,
        "candidate_run_id": validation_result.candidate_run_id,
        "outcome": validation_result.outcome,
        "validation_result": validation_result.to_payload(),
        "written_at": written_at,
    }

    if not dry_run:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return GovernanceCandidateValidationArtifactRecord(
        validation_id=validation_id,
        source_run_id=normalized_source_run_id,
        written_at=written_at,
        artifact_path=str(artifact_file.relative_to(project_root_path)),
        baseline_run_id=validation_result.baseline_run_id,
        candidate_run_id=validation_result.candidate_run_id,
        outcome=validation_result.outcome,
    )


def write_governance_status_transition_artifact(
    *,
    project_root: str | Path,
    source_run_id: str,
    validation_result: ValidationResult,
    decision_record: GovernanceDecisionRecord,
    effective_attention_item: AttentionItem,
    effective_promotion_blocker: PromotionBlocker,
    trigger_artifact_path: str,
    dry_run: bool = False,
) -> GovernanceStatusTransitionArtifactRecord:
    project_root_path = Path(project_root)
    normalized_source_run_id = str(source_run_id or "").strip()
    validation_id = str(validation_result.validation_id or "").strip()
    normalized_trigger_artifact_path = str(trigger_artifact_path or "").strip()
    if not normalized_source_run_id:
        raise ValueError("source_run_id must be non-empty")
    if not validation_id:
        raise ValueError("validation_id must be non-empty")
    if not normalized_trigger_artifact_path:
        raise ValueError("trigger_artifact_path must be non-empty")

    artifacts_dir = (
        project_root_path
        / "var/artifacts/governance_status_transitions"
        / validation_id
    )
    artifact_file = artifacts_dir / "governance_status_transition.json"
    written_at = _now_iso()
    payload = {
        "source_run_id": normalized_source_run_id,
        "validation_id": validation_id,
        "decision_id": decision_record.decision_id,
        "baseline_run_id": validation_result.baseline_run_id,
        "candidate_run_id": validation_result.candidate_run_id,
        "trigger_artifact_path": normalized_trigger_artifact_path,
        "effective_attention_item": effective_attention_item.to_payload(),
        "effective_promotion_blocker": effective_promotion_blocker.to_payload(),
        "written_at": written_at,
    }

    if not dry_run:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return GovernanceStatusTransitionArtifactRecord(
        validation_id=validation_id,
        source_run_id=normalized_source_run_id,
        written_at=written_at,
        artifact_path=str(artifact_file.relative_to(project_root_path)),
        baseline_run_id=validation_result.baseline_run_id,
        candidate_run_id=validation_result.candidate_run_id,
        decision_id=decision_record.decision_id,
        effective_attention_id=effective_attention_item.attention_id,
        effective_blocker_id=effective_promotion_blocker.blocker_id,
    )


def write_governance_final_validation_artifact(
    *,
    project_root: str | Path,
    source_run_id: str,
    validation_result: ValidationResult,
    candidate_validation_artifact_path: str,
    candidate_validation_ledger_path: str,
    handoff_artifact_path: str,
    selection_basis: str = "unique_persisted_candidate_validation",
    dry_run: bool = False,
) -> GovernanceFinalValidationArtifactRecord:
    project_root_path = Path(project_root)
    normalized_source_run_id = str(source_run_id or "").strip()
    validation_id = str(validation_result.validation_id or "").strip()
    normalized_candidate_validation_artifact_path = str(
        candidate_validation_artifact_path or ""
    ).strip()
    normalized_candidate_validation_ledger_path = str(
        candidate_validation_ledger_path or ""
    ).strip()
    normalized_handoff_artifact_path = str(handoff_artifact_path or "").strip()
    normalized_selection_basis = str(selection_basis or "").strip()
    if not normalized_source_run_id:
        raise ValueError("source_run_id must be non-empty")
    if not validation_id:
        raise ValueError("validation_id must be non-empty")
    if not normalized_candidate_validation_artifact_path:
        raise ValueError("candidate_validation_artifact_path must be non-empty")
    if not normalized_candidate_validation_ledger_path:
        raise ValueError("candidate_validation_ledger_path must be non-empty")
    if not normalized_handoff_artifact_path:
        raise ValueError("handoff_artifact_path must be non-empty")
    if not normalized_selection_basis:
        raise ValueError("selection_basis must be non-empty")

    artifacts_dir = (
        project_root_path / "var/artifacts/governance_final_validations" / normalized_source_run_id
    )
    artifact_file = artifacts_dir / "governance_final_validation.json"
    written_at = _now_iso()
    payload = {
        "source_run_id": normalized_source_run_id,
        "selected_validation_id": validation_id,
        "baseline_run_id": validation_result.baseline_run_id,
        "candidate_run_id": validation_result.candidate_run_id,
        "outcome": validation_result.outcome,
        "selection_basis": normalized_selection_basis,
        "candidate_validation_artifact_path": normalized_candidate_validation_artifact_path,
        "candidate_validation_ledger_path": normalized_candidate_validation_ledger_path,
        "handoff_artifact_path": normalized_handoff_artifact_path,
        "written_at": written_at,
    }

    if not dry_run:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return GovernanceFinalValidationArtifactRecord(
        source_run_id=normalized_source_run_id,
        written_at=written_at,
        artifact_path=str(artifact_file.relative_to(project_root_path)),
        selected_validation_id=validation_id,
        baseline_run_id=validation_result.baseline_run_id,
        candidate_run_id=validation_result.candidate_run_id,
        outcome=validation_result.outcome,
    )
