from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .step8_governance import (
    build_adjustment_proposal_id,
    build_adjustment_proposal_v0,
    build_governance_decision_log_id,
    build_governance_decision_log_v0,
)


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass(frozen=True)
class Step8AdjustmentProposalArtifactRecord:
    proposal_id: str
    written_at: str
    artifact_path: str
    asof_date: str
    source_report_id: str


@dataclass(frozen=True)
class Step8GovernanceDecisionLogArtifactRecord:
    log_id: str
    written_at: str
    artifact_path: str
    asof_date: str
    source_proposal_id: str
    decision: str


def write_step8_adjustment_proposal_artifact(
    *,
    project_root: str | Path,
    asof_date: str,
    source_report_id: str,
    rb_ids_touched: list[str] | None = None,
    proposed_changes: list[dict[str, str]] | None = None,
    risk_notes: str | None = None,
    upstream_evidence_paths: list[str] | None = None,
    dry_run: bool = False,
) -> Step8AdjustmentProposalArtifactRecord:
    project_root_path = Path(project_root)
    normalized_asof_date = str(asof_date or "").strip()
    normalized_source_report_id = str(source_report_id or "").strip()
    proposal_id = build_adjustment_proposal_id(source_report_id=normalized_source_report_id)
    artifacts_dir = project_root_path / "var/artifacts/step8_adjustment_proposals" / proposal_id
    artifact_file = artifacts_dir / "adjustment_proposal.json"
    artifact_path = str(artifact_file.relative_to(project_root_path))
    written_at = _now_iso()
    normalized_upstream_evidence = [
        str(p).strip() for p in list(upstream_evidence_paths or []) if str(p).strip()
    ]
    evidence_paths = [artifact_path, *normalized_upstream_evidence]
    proposal = build_adjustment_proposal_v0(
        asof_date=normalized_asof_date,
        source_report_id=normalized_source_report_id,
        proposal_id=proposal_id,
        rb_ids_touched=rb_ids_touched,
        proposed_changes=proposed_changes,
        risk_notes=risk_notes,
        evidence_paths=evidence_paths,
    )
    payload = {
        "adjustment_proposal": dict(proposal),
        "written_at": written_at,
    }

    if not dry_run:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return Step8AdjustmentProposalArtifactRecord(
        proposal_id=proposal_id,
        written_at=written_at,
        artifact_path=artifact_path,
        asof_date=normalized_asof_date,
        source_report_id=normalized_source_report_id,
    )


def write_step8_governance_decision_log_artifact(
    *,
    project_root: str | Path,
    asof_date: str,
    source_proposal_id: str,
    decision: str = "defer",
    rationale: str = "v0 default defer",
    application_record_id: str | None = None,
    upstream_evidence_paths: list[str] | None = None,
    dry_run: bool = False,
) -> Step8GovernanceDecisionLogArtifactRecord:
    project_root_path = Path(project_root)
    normalized_asof_date = str(asof_date or "").strip()
    normalized_source_proposal_id = str(source_proposal_id or "").strip()
    log_id = build_governance_decision_log_id(source_proposal_id=normalized_source_proposal_id)
    artifacts_dir = project_root_path / "var/artifacts/step8_governance_decision_logs" / log_id
    artifact_file = artifacts_dir / "governance_decision_log.json"
    artifact_path = str(artifact_file.relative_to(project_root_path))
    written_at = _now_iso()
    normalized_upstream_evidence = [
        str(p).strip() for p in list(upstream_evidence_paths or []) if str(p).strip()
    ]
    evidence_paths = [artifact_path, *normalized_upstream_evidence]
    decision_log = build_governance_decision_log_v0(
        asof_date=normalized_asof_date,
        source_proposal_id=normalized_source_proposal_id,
        log_id=log_id,
        decision=decision,
        rationale=rationale,
        evidence_paths=evidence_paths,
        application_record_id=application_record_id,
    )
    payload = {
        "governance_decision_log": dict(decision_log),
        "written_at": written_at,
    }

    if not dry_run:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return Step8GovernanceDecisionLogArtifactRecord(
        log_id=log_id,
        written_at=written_at,
        artifact_path=artifact_path,
        asof_date=normalized_asof_date,
        source_proposal_id=normalized_source_proposal_id,
        decision=str(decision_log.get("decision") or "").strip(),
    )
