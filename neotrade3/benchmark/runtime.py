"""Shared runtime owner for NeoTrade3 M4 benchmark execution."""

from __future__ import annotations

from pathlib import Path

from .batch_runner import load_benchmark_run_manifest, run_benchmark_manifest
from .run_ledger import BenchmarkRunLedgerRecord, materialize_benchmark_batch_run

DEFAULT_BENCHMARK_MANIFEST = "config/benchmark/validation_seed_manifest.json"


def resolve_benchmark_manifest_path(
    *,
    project_root: str | Path,
    manifest: str | Path = DEFAULT_BENCHMARK_MANIFEST,
) -> Path:
    """Resolve a benchmark manifest path against the given project root."""

    project_root_path = Path(project_root)
    manifest_path = Path(manifest)
    if not manifest_path.is_absolute():
        manifest_path = project_root_path / manifest_path
    return manifest_path


def run_benchmark_for_manifest(
    *,
    project_root: str | Path,
    manifest: str | Path = DEFAULT_BENCHMARK_MANIFEST,
    dry_run: bool = False,
) -> BenchmarkRunLedgerRecord:
    """Run one benchmark manifest and materialize its artifact plus ledger."""

    project_root_path = Path(project_root)
    manifest_path = resolve_benchmark_manifest_path(
        project_root=project_root_path,
        manifest=manifest,
    )
    loaded_manifest = load_benchmark_run_manifest(manifest_path)
    batch_result = run_benchmark_manifest(
        project_root=project_root_path,
        manifest=loaded_manifest,
    )
    return materialize_benchmark_batch_run(
        project_root=project_root_path,
        batch_result=batch_result,
        dry_run=bool(dry_run),
    )
