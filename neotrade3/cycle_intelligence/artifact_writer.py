"""Artifact writer for NeoTrade3 M2 small-cycle persisted snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .contracts import SmallCycle


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def build_small_cycle_record_id(*, small_cycle: SmallCycle) -> str:
    return f"{small_cycle.stock_code}-{small_cycle.trade_date}"


@dataclass(frozen=True)
class SmallCycleArtifactRecord:
    record_id: str
    written_at: str
    artifact_path: str


def write_small_cycle_artifact(
    *,
    project_root: str | Path,
    small_cycle: SmallCycle,
    dry_run: bool = False,
) -> SmallCycleArtifactRecord:
    project_root_path = Path(project_root)
    record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    artifacts_dir = project_root_path / "var/artifacts/m2_small_cycles" / record_id
    artifact_file = artifacts_dir / "small_cycle.json"
    written_at = _now_iso()
    payload = {
        **small_cycle.to_payload(),
        "written_at": written_at,
        "record_id": record_id,
    }

    if not dry_run:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return SmallCycleArtifactRecord(
        record_id=record_id,
        written_at=written_at,
        artifact_path=str(artifact_file.relative_to(project_root_path)),
    )
