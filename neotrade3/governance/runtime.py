"""Shared runtime helpers for NeoTrade3 governance execution."""

from __future__ import annotations

from pathlib import Path

from neotrade3.benchmark.batch_runner import (
    load_benchmark_run_manifest,
    run_benchmark_manifest,
)

from .handoff import build_governance_handoff_from_batch_run
from .run_ledger import GovernanceRunLedgerRecord, materialize_governance_handoff


DEFAULT_GOVERNANCE_MANIFEST = "config/benchmark/validation_seed_manifest.json"


def resolve_governance_manifest_path(
    *,
    project_root: str | Path,
    manifest_path: str | Path = DEFAULT_GOVERNANCE_MANIFEST,
) -> Path:
    project_root_path = Path(project_root)
    candidate = Path(manifest_path)
    if candidate.is_absolute():
        return candidate
    return project_root_path / candidate


def run_governance_manifest(
    *,
    project_root: str | Path,
    manifest_path: str | Path = DEFAULT_GOVERNANCE_MANIFEST,
    dry_run: bool = False,
) -> GovernanceRunLedgerRecord:
    project_root_path = Path(project_root)
    resolved_manifest_path = resolve_governance_manifest_path(
        project_root=project_root_path,
        manifest_path=manifest_path,
    )
    manifest = load_benchmark_run_manifest(resolved_manifest_path)
    batch_result = run_benchmark_manifest(
        project_root=project_root_path,
        manifest=manifest,
    )
    bundle = build_governance_handoff_from_batch_run(batch_result=batch_result)
    return materialize_governance_handoff(
        project_root=project_root_path,
        bundle=bundle,
        dry_run=dry_run,
    )
