"""Shared runtime helpers for NeoTrade3 governance execution."""

from __future__ import annotations

from pathlib import Path

from neotrade3.benchmark.run_ledger import read_benchmark_batch_run_result

from .handoff import build_governance_handoff_from_batch_run
from .run_ledger import GovernanceRunLedgerRecord, materialize_governance_handoff


DEFAULT_GOVERNANCE_BENCHMARK_RUN_ID = "validation_seed_v1_batch"


def resolve_governance_benchmark_run_id(
    *,
    benchmark_run_id: str,
) -> str:
    normalized = str(benchmark_run_id or "").strip()
    if not normalized:
        raise ValueError("benchmark_run_id must be non-empty")
    return normalized


def run_governance_for_benchmark_run(
    *,
    project_root: str | Path,
    benchmark_run_id: str,
    dry_run: bool = False,
) -> GovernanceRunLedgerRecord:
    project_root_path = Path(project_root)
    resolved_benchmark_run_id = resolve_governance_benchmark_run_id(
        benchmark_run_id=benchmark_run_id,
    )

    batch_result = read_benchmark_batch_run_result(
        project_root=project_root_path,
        run_id=resolved_benchmark_run_id,
    )
    if batch_result is None:
        raise FileNotFoundError(
            f"persisted benchmark artifact not found for run_id={resolved_benchmark_run_id}"
        )

    bundle = build_governance_handoff_from_batch_run(batch_result=batch_result)
    return materialize_governance_handoff(
        project_root=project_root_path,
        bundle=bundle,
        dry_run=dry_run,
    )
