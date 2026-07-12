"""Artifact writer for NeoTrade3 M5 governance handoff bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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
