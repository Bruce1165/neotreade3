"""Ledger/readback helpers for NeoTrade3 M5 governance handoff bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_writer import (
    GovernanceArtifactRecord,
    GovernanceRejectExecutionArtifactRecord,
    GovernanceStatusTransitionArtifactRecord,
    write_governance_handoff_artifact,
    write_governance_reject_execution_artifact,
    write_governance_status_transition_artifact,
)
from .contracts import AttentionItem, GovernanceDecisionRecord, PromotionBlocker, ValidationResult
from .handoff import GovernanceHandoffBundle


@dataclass(frozen=True)
class GovernanceRunLedgerRecord:
    source_run_id: str
    status: str
    written_at: str
    artifact_path: str
    ledger_path: str
    source_layer: str
    projected_assessment_count: int
    projected_issue_count: int
    diagnostic_count: int = 0
    change_request_count: int = 0
    experiment_request_count: int = 0
    validation_result_count: int = 0
    promotion_blocker_count: int = 0
    attention_item_count: int = 0
    decision_record_count: int = 0

    @classmethod
    def from_dict(cls, payload: Any) -> "GovernanceRunLedgerRecord":
        if not isinstance(payload, dict):
            raise TypeError("governance run ledger root must be a JSON object")
        return cls(
            source_run_id=str(payload.get("source_run_id") or "").strip(),
            status=str(payload.get("status") or "").strip(),
            written_at=str(payload.get("written_at") or "").strip(),
            artifact_path=str(payload.get("artifact_path") or "").strip(),
            ledger_path=str(payload.get("ledger_path") or "").strip(),
            source_layer=str(payload.get("source_layer") or "").strip(),
            projected_assessment_count=int(
                payload.get("projected_assessment_count", 0)
            ),
            projected_issue_count=int(payload.get("projected_issue_count", 0)),
            diagnostic_count=int(payload.get("diagnostic_count", 0)),
            change_request_count=int(payload.get("change_request_count", 0)),
            experiment_request_count=int(payload.get("experiment_request_count", 0)),
            validation_result_count=int(payload.get("validation_result_count", 0)),
            promotion_blocker_count=int(payload.get("promotion_blocker_count", 0)),
            attention_item_count=int(payload.get("attention_item_count", 0)),
            decision_record_count=int(payload.get("decision_record_count", 0)),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "source_run_id": self.source_run_id,
            "status": self.status,
            "written_at": self.written_at,
            "artifact_path": self.artifact_path,
            "ledger_path": self.ledger_path,
            "source_layer": self.source_layer,
            "projected_assessment_count": self.projected_assessment_count,
            "projected_issue_count": self.projected_issue_count,
            "diagnostic_count": self.diagnostic_count,
            "change_request_count": self.change_request_count,
            "experiment_request_count": self.experiment_request_count,
            "validation_result_count": self.validation_result_count,
            "promotion_blocker_count": self.promotion_blocker_count,
            "attention_item_count": self.attention_item_count,
            "decision_record_count": self.decision_record_count,
        }


@dataclass(frozen=True)
class GovernanceRejectExecutionLedgerRecord:
    validation_id: str
    source_run_id: str
    status: str
    written_at: str
    artifact_path: str
    ledger_path: str
    baseline_run_id: str
    candidate_run_id: str
    decision_id: str
    decision: str

    @classmethod
    def from_dict(cls, payload: Any) -> "GovernanceRejectExecutionLedgerRecord":
        if not isinstance(payload, dict):
            raise TypeError("governance reject execution ledger root must be a JSON object")
        return cls(
            validation_id=str(payload.get("validation_id") or "").strip(),
            source_run_id=str(payload.get("source_run_id") or "").strip(),
            status=str(payload.get("status") or "").strip(),
            written_at=str(payload.get("written_at") or "").strip(),
            artifact_path=str(payload.get("artifact_path") or "").strip(),
            ledger_path=str(payload.get("ledger_path") or "").strip(),
            baseline_run_id=str(payload.get("baseline_run_id") or "").strip(),
            candidate_run_id=str(payload.get("candidate_run_id") or "").strip(),
            decision_id=str(payload.get("decision_id") or "").strip(),
            decision=str(payload.get("decision") or "").strip(),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "source_run_id": self.source_run_id,
            "status": self.status,
            "written_at": self.written_at,
            "artifact_path": self.artifact_path,
            "ledger_path": self.ledger_path,
            "baseline_run_id": self.baseline_run_id,
            "candidate_run_id": self.candidate_run_id,
            "decision_id": self.decision_id,
            "decision": self.decision,
        }


@dataclass(frozen=True)
class GovernanceStatusTransitionRecord:
    validation_id: str
    source_run_id: str
    status: str
    written_at: str
    artifact_path: str
    ledger_path: str
    baseline_run_id: str
    candidate_run_id: str
    decision_id: str
    effective_attention_id: str
    effective_attention_status: str
    effective_blocker_id: str
    effective_blocker_active: bool

    @classmethod
    def from_dict(cls, payload: Any) -> "GovernanceStatusTransitionRecord":
        if not isinstance(payload, dict):
            raise TypeError("governance status transition ledger root must be a JSON object")
        return cls(
            validation_id=str(payload.get("validation_id") or "").strip(),
            source_run_id=str(payload.get("source_run_id") or "").strip(),
            status=str(payload.get("status") or "").strip(),
            written_at=str(payload.get("written_at") or "").strip(),
            artifact_path=str(payload.get("artifact_path") or "").strip(),
            ledger_path=str(payload.get("ledger_path") or "").strip(),
            baseline_run_id=str(payload.get("baseline_run_id") or "").strip(),
            candidate_run_id=str(payload.get("candidate_run_id") or "").strip(),
            decision_id=str(payload.get("decision_id") or "").strip(),
            effective_attention_id=str(payload.get("effective_attention_id") or "").strip(),
            effective_attention_status=str(
                payload.get("effective_attention_status") or ""
            ).strip(),
            effective_blocker_id=str(payload.get("effective_blocker_id") or "").strip(),
            effective_blocker_active=bool(payload.get("effective_blocker_active", False)),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "source_run_id": self.source_run_id,
            "status": self.status,
            "written_at": self.written_at,
            "artifact_path": self.artifact_path,
            "ledger_path": self.ledger_path,
            "baseline_run_id": self.baseline_run_id,
            "candidate_run_id": self.candidate_run_id,
            "decision_id": self.decision_id,
            "effective_attention_id": self.effective_attention_id,
            "effective_attention_status": self.effective_attention_status,
            "effective_blocker_id": self.effective_blocker_id,
            "effective_blocker_active": self.effective_blocker_active,
        }


def _normalized_source_run_id(source_run_id: str) -> str:
    normalized = str(source_run_id or "").strip()
    if not normalized:
        raise ValueError("Governance handoff bundle source_run_id cannot be empty")
    return normalized


def _normalized_validation_id(validation_id: str) -> str:
    normalized = str(validation_id or "").strip()
    if not normalized:
        raise ValueError("validation_id must be non-empty")
    return normalized


def _ledger_file(*, project_root: Path, source_run_id: str) -> Path:
    return (
        project_root
        / "var/ledgers/governance_handoffs"
        / source_run_id
        / "governance_handoff_run.json"
    )


def _artifact_file(*, project_root: Path, source_run_id: str) -> Path:
    return (
        project_root
        / "var/artifacts/governance_handoffs"
        / source_run_id
        / "governance_handoff_bundle.json"
    )


def _reject_ledger_file(*, project_root: Path, validation_id: str) -> Path:
    return (
        project_root
        / "var/ledgers/governance_rejections"
        / validation_id
        / "governance_reject_execution_run.json"
    )


def _reject_artifact_file(*, project_root: Path, validation_id: str) -> Path:
    return (
        project_root
        / "var/artifacts/governance_rejections"
        / validation_id
        / "governance_reject_execution.json"
    )


def _status_transition_ledger_file(*, project_root: Path, validation_id: str) -> Path:
    return (
        project_root
        / "var/ledgers/governance_status_transitions"
        / validation_id
        / "governance_status_transition_run.json"
    )


def _status_transition_artifact_file(*, project_root: Path, validation_id: str) -> Path:
    return (
        project_root
        / "var/artifacts/governance_status_transitions"
        / validation_id
        / "governance_status_transition.json"
    )


def write_governance_run_ledger(
    *,
    project_root: str | Path,
    bundle: GovernanceHandoffBundle,
    artifact_record: GovernanceArtifactRecord,
    dry_run: bool = False,
) -> GovernanceRunLedgerRecord:
    project_root_path = Path(project_root)
    source_run_id = _normalized_source_run_id(bundle.source_run_id)
    ledger_file = _ledger_file(
        project_root=project_root_path,
        source_run_id=source_run_id,
    )
    payload = {
        "source_run_id": source_run_id,
        "status": "completed",
        "written_at": artifact_record.written_at,
        "artifact_path": artifact_record.artifact_path,
        "ledger_path": str(ledger_file.relative_to(project_root_path)),
        "source_layer": bundle.source_layer,
        "projected_assessment_count": bundle.projected_assessment_count,
        "projected_issue_count": bundle.projected_issue_count,
        "diagnostic_count": len(bundle.diagnostics),
        "change_request_count": len(bundle.change_requests),
        "experiment_request_count": len(bundle.experiment_requests),
        "validation_result_count": len(bundle.validation_results),
        "promotion_blocker_count": len(bundle.promotion_blockers),
        "attention_item_count": len(bundle.attention_items),
        "decision_record_count": len(bundle.decision_records),
    }

    if not dry_run:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return GovernanceRunLedgerRecord.from_dict(payload)


def materialize_governance_handoff(
    *,
    project_root: str | Path,
    bundle: GovernanceHandoffBundle,
    dry_run: bool = False,
) -> GovernanceRunLedgerRecord:
    artifact_record = write_governance_handoff_artifact(
        project_root=project_root,
        bundle=bundle,
        dry_run=dry_run,
    )
    return write_governance_run_ledger(
        project_root=project_root,
        bundle=bundle,
        artifact_record=artifact_record,
        dry_run=dry_run,
    )


def write_governance_reject_execution_ledger(
    *,
    project_root: str | Path,
    source_run_id: str,
    validation_result: ValidationResult,
    decision_record: GovernanceDecisionRecord,
    artifact_record: GovernanceRejectExecutionArtifactRecord,
    dry_run: bool = False,
) -> GovernanceRejectExecutionLedgerRecord:
    project_root_path = Path(project_root)
    validation_id = _normalized_validation_id(validation_result.validation_id)
    ledger_file = _reject_ledger_file(
        project_root=project_root_path,
        validation_id=validation_id,
    )
    payload = {
        "validation_id": validation_id,
        "source_run_id": _normalized_source_run_id(source_run_id),
        "status": "completed",
        "written_at": artifact_record.written_at,
        "artifact_path": artifact_record.artifact_path,
        "ledger_path": str(ledger_file.relative_to(project_root_path)),
        "baseline_run_id": validation_result.baseline_run_id,
        "candidate_run_id": validation_result.candidate_run_id,
        "decision_id": decision_record.decision_id,
        "decision": decision_record.decision,
    }

    if not dry_run:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return GovernanceRejectExecutionLedgerRecord.from_dict(payload)


def materialize_governance_reject_execution(
    *,
    project_root: str | Path,
    source_run_id: str,
    validation_result: ValidationResult,
    decision_record: GovernanceDecisionRecord,
    dry_run: bool = False,
) -> GovernanceRejectExecutionLedgerRecord:
    artifact_record = write_governance_reject_execution_artifact(
        project_root=project_root,
        source_run_id=source_run_id,
        validation_result=validation_result,
        decision_record=decision_record,
        dry_run=dry_run,
    )
    return write_governance_reject_execution_ledger(
        project_root=project_root,
        source_run_id=source_run_id,
        validation_result=validation_result,
        decision_record=decision_record,
        artifact_record=artifact_record,
        dry_run=dry_run,
    )


def write_governance_status_transition_ledger(
    *,
    project_root: str | Path,
    source_run_id: str,
    validation_result: ValidationResult,
    decision_record: GovernanceDecisionRecord,
    effective_attention_item: AttentionItem,
    effective_promotion_blocker: PromotionBlocker,
    artifact_record: GovernanceStatusTransitionArtifactRecord,
    dry_run: bool = False,
) -> GovernanceStatusTransitionRecord:
    project_root_path = Path(project_root)
    validation_id = _normalized_validation_id(validation_result.validation_id)
    ledger_file = _status_transition_ledger_file(
        project_root=project_root_path,
        validation_id=validation_id,
    )
    payload = {
        "validation_id": validation_id,
        "source_run_id": _normalized_source_run_id(source_run_id),
        "status": "completed",
        "written_at": artifact_record.written_at,
        "artifact_path": artifact_record.artifact_path,
        "ledger_path": str(ledger_file.relative_to(project_root_path)),
        "baseline_run_id": validation_result.baseline_run_id,
        "candidate_run_id": validation_result.candidate_run_id,
        "decision_id": decision_record.decision_id,
        "effective_attention_id": effective_attention_item.attention_id,
        "effective_attention_status": effective_attention_item.status,
        "effective_blocker_id": effective_promotion_blocker.blocker_id,
        "effective_blocker_active": effective_promotion_blocker.active,
    }

    if not dry_run:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return GovernanceStatusTransitionRecord.from_dict(payload)


def materialize_governance_status_transition(
    *,
    project_root: str | Path,
    source_run_id: str,
    validation_result: ValidationResult,
    decision_record: GovernanceDecisionRecord,
    effective_attention_item: AttentionItem,
    effective_promotion_blocker: PromotionBlocker,
    trigger_artifact_path: str,
    dry_run: bool = False,
) -> GovernanceStatusTransitionRecord:
    artifact_record = write_governance_status_transition_artifact(
        project_root=project_root,
        source_run_id=source_run_id,
        validation_result=validation_result,
        decision_record=decision_record,
        effective_attention_item=effective_attention_item,
        effective_promotion_blocker=effective_promotion_blocker,
        trigger_artifact_path=trigger_artifact_path,
        dry_run=dry_run,
    )
    return write_governance_status_transition_ledger(
        project_root=project_root,
        source_run_id=source_run_id,
        validation_result=validation_result,
        decision_record=decision_record,
        effective_attention_item=effective_attention_item,
        effective_promotion_blocker=effective_promotion_blocker,
        artifact_record=artifact_record,
        dry_run=dry_run,
    )


def read_governance_run_ledger(
    *,
    project_root: str | Path,
    source_run_id: str,
) -> GovernanceRunLedgerRecord | None:
    try:
        normalized_source_run_id = _normalized_source_run_id(source_run_id)
    except ValueError:
        return None
    ledger_file = _ledger_file(
        project_root=Path(project_root),
        source_run_id=normalized_source_run_id,
    )
    if not ledger_file.exists():
        return None
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return GovernanceRunLedgerRecord.from_dict(payload)


def read_governance_handoff_artifact(
    *,
    project_root: str | Path,
    source_run_id: str,
) -> dict[str, Any] | None:
    try:
        normalized_source_run_id = _normalized_source_run_id(source_run_id)
    except ValueError:
        return None
    artifact_file = _artifact_file(
        project_root=Path(project_root),
        source_run_id=normalized_source_run_id,
    )
    if not artifact_file.exists():
        return None
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def read_governance_handoff_bundle(
    *,
    project_root: str | Path,
    source_run_id: str,
) -> GovernanceHandoffBundle | None:
    payload = read_governance_handoff_artifact(
        project_root=project_root,
        source_run_id=source_run_id,
    )
    if payload is None:
        return None
    return GovernanceHandoffBundle.from_dict(payload)


def read_governance_reject_execution_artifact(
    *,
    project_root: str | Path,
    validation_id: str,
) -> dict[str, Any] | None:
    try:
        normalized_validation_id = _normalized_validation_id(validation_id)
    except ValueError:
        return None
    artifact_file = _reject_artifact_file(
        project_root=Path(project_root),
        validation_id=normalized_validation_id,
    )
    if not artifact_file.exists():
        return None
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def read_governance_reject_execution_ledger(
    *,
    project_root: str | Path,
    validation_id: str,
) -> GovernanceRejectExecutionLedgerRecord | None:
    try:
        normalized_validation_id = _normalized_validation_id(validation_id)
    except ValueError:
        return None
    ledger_file = _reject_ledger_file(
        project_root=Path(project_root),
        validation_id=normalized_validation_id,
    )
    if not ledger_file.exists():
        return None
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return GovernanceRejectExecutionLedgerRecord.from_dict(payload)


def read_governance_status_transition_artifact(
    *,
    project_root: str | Path,
    validation_id: str,
) -> dict[str, Any] | None:
    try:
        normalized_validation_id = _normalized_validation_id(validation_id)
    except ValueError:
        return None
    artifact_file = _status_transition_artifact_file(
        project_root=Path(project_root),
        validation_id=normalized_validation_id,
    )
    if not artifact_file.exists():
        return None
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def read_governance_status_transition_ledger(
    *,
    project_root: str | Path,
    validation_id: str,
) -> GovernanceStatusTransitionRecord | None:
    try:
        normalized_validation_id = _normalized_validation_id(validation_id)
    except ValueError:
        return None
    ledger_file = _status_transition_ledger_file(
        project_root=Path(project_root),
        validation_id=normalized_validation_id,
    )
    if not ledger_file.exists():
        return None
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return GovernanceStatusTransitionRecord.from_dict(payload)


def list_governance_run_ledgers(
    *,
    project_root: str | Path,
) -> list[GovernanceRunLedgerRecord]:
    root = Path(project_root) / "var/ledgers/governance_handoffs"
    if not root.exists():
        return []

    records: list[GovernanceRunLedgerRecord] = []
    for ledger_file in sorted(root.glob("*/governance_handoff_run.json")):
        try:
            payload = json.loads(ledger_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            records.append(GovernanceRunLedgerRecord.from_dict(payload))

    records.sort(
        key=lambda item: (item.written_at, item.source_run_id),
        reverse=True,
    )
    return records
