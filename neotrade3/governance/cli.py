"""CLI entrypoint for NeoTrade3 governance handoff materialization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from neotrade3.benchmark.batch_runner import (
    load_benchmark_run_manifest,
    run_benchmark_manifest,
)

from .handoff import build_governance_handoff_from_batch_run
from .run_ledger import materialize_governance_handoff


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a NeoTrade3 M5 governance handoff from a benchmark manifest."
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (defaults to repository root).",
    )
    parser.add_argument(
        "--manifest",
        default="config/benchmark/validation_seed_manifest.json",
        help="Benchmark run manifest path used as the governance upstream input.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute without writing governance artifact/ledger outputs under var/.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    project_root = (
        Path(args.project_root) if args.project_root else _default_project_root()
    )
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = project_root / manifest_path

    manifest = load_benchmark_run_manifest(manifest_path)
    batch_result = run_benchmark_manifest(
        project_root=project_root,
        manifest=manifest,
    )
    bundle = build_governance_handoff_from_batch_run(batch_result=batch_result)
    record = materialize_governance_handoff(
        project_root=project_root,
        bundle=bundle,
        dry_run=bool(args.dry_run),
    )

    print(
        json.dumps(
            {
                "source_run_id": record.source_run_id,
                "status": record.status,
                "source_layer": record.source_layer,
                "projected_assessment_count": record.projected_assessment_count,
                "projected_issue_count": record.projected_issue_count,
                "diagnostic_count": record.diagnostic_count,
                "change_request_count": record.change_request_count,
                "experiment_request_count": record.experiment_request_count,
                "promotion_blocker_count": record.promotion_blocker_count,
                "artifact_path": record.artifact_path,
                "ledger_path": record.ledger_path,
                "dry_run": bool(args.dry_run),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
