"""CLI entrypoint for NeoTrade3 benchmark runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .runtime import DEFAULT_BENCHMARK_MANIFEST, run_benchmark_for_manifest


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a NeoTrade3 M4 benchmark manifest."
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (defaults to repository root).",
    )
    parser.add_argument(
        "--manifest",
        default=DEFAULT_BENCHMARK_MANIFEST,
        help="Benchmark run manifest path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute without writing artifact/ledger outputs under var/.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    project_root = (
        Path(args.project_root) if args.project_root else _default_project_root()
    )
    record = run_benchmark_for_manifest(
        project_root=project_root,
        manifest=Path(args.manifest),
        dry_run=bool(args.dry_run),
    )

    print(
        json.dumps(
            {
                "run_id": record.run_id,
                "status": record.status,
                "sample_count": record.sample_count,
                "executed_sample_ids": list(record.executed_sample_ids),
                "grade_summary": dict(record.grade_summary),
                "bucket_summary": dict(record.bucket_summary),
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
