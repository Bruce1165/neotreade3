"""Artifact writer for NeoTrade3 M4 benchmark batch results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .batch_runner import BenchmarkBatchRunResult


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass(frozen=True)
class BenchmarkArtifactRecord:
    run_id: str
    written_at: str
    sample_count: int
    artifact_path: str


def write_benchmark_batch_run_artifact(
    *,
    project_root: str | Path,
    batch_result: BenchmarkBatchRunResult,
    dry_run: bool = False,
) -> BenchmarkArtifactRecord:
    project_root_path = Path(project_root)
    artifacts_dir = project_root_path / "var/artifacts/benchmark_runs" / batch_result.run_id
    artifact_file = artifacts_dir / "benchmark_batch_result.json"
    written_at = _now_iso()

    payload = {
        **batch_result.to_payload(),
        "written_at": written_at,
        "sample_count": len(batch_result.executed_sample_ids),
    }

    if not dry_run:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return BenchmarkArtifactRecord(
        run_id=batch_result.run_id,
        written_at=written_at,
        sample_count=len(batch_result.executed_sample_ids),
        artifact_path=str(artifact_file.relative_to(project_root_path)),
    )
