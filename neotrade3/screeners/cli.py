"""CLI entrypoint for NeoTrade3 screener runs."""

from __future__ import annotations

import argparse
import importlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from .registry import load_screener_registry
from .storage import write_screener_run


def _resolve_runtime_fn(entrypoint: str):
    """Dynamically resolve a runtime function from an entrypoint string.

    Expected format: ``module.path:function_name``
    """
    module_path, _, func_name = entrypoint.partition(":")
    if not func_name:
        raise ValueError(f"invalid entrypoint (missing ':'): {entrypoint}")
    module = importlib.import_module(module_path)
    fn = getattr(module, func_name, None)
    if fn is None or not callable(fn):
        raise AttributeError(
            f"module {module_path!r} has no callable attribute {func_name!r}"
        )
    return fn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a NeoTrade3 screener against real data."
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (defaults to repository root).",
    )
    parser.add_argument(
        "--date",
        dest="target_date",
        default=None,
        help="Target date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--screener-id", required=True, help="Screener id registered in config."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write run ledgers/artifacts under var/.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    project_root = (
        Path(args.project_root)
        if args.project_root
        else Path(__file__).resolve().parents[2]
    )
    target_date = (
        date.fromisoformat(args.target_date) if args.target_date else date.today()
    )
    registry = load_screener_registry(
        project_root / "config/screeners/screeners_registry.json"
    )

    # Find the screener config
    screener_cfg = None
    for s in registry.screeners:
        if s.screener_id == args.screener_id and s.enabled:
            screener_cfg = s
            break
    if screener_cfg is None:
        raise SystemExit(f"unknown or disabled screener_id: {args.screener_id}")

    # Resolve the real runtime function via entrypoint
    entrypoint = getattr(screener_cfg, "entrypoint", None)
    if not entrypoint:
        raise SystemExit(
            f"screener {args.screener_id!r} has no entrypoint configured"
        )

    runtime_fn = _resolve_runtime_fn(entrypoint)

    # Load parameters from the screener's individual config if it exists
    parameters: dict[str, Any] = {}
    config_dir = project_root / "config" / "screeners"
    config_file = config_dir / f"{args.screener_id}.json"
    if config_file.exists():
        try:
            parameters = json.loads(config_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    # Execute the real runtime function
    runtime_result = runtime_fn(
        screener_id=args.screener_id,
        target_date=target_date,
        parameters=parameters,
    )

    # Persist the result
    record = write_screener_run(
        project_root=project_root,
        target_date=target_date.isoformat(),
        screener_id=args.screener_id,
        requested_by="cli",
        parameters=parameters,
        runtime_result=runtime_result,
        dry_run=bool(args.dry_run),
    )
    print(
        json.dumps(
            {
                "target_date": record.target_date,
                "screener_id": record.screener_id,
                "status": record.status,
                "picks_count": record.picks_count,
                "artifact_path": record.artifact_path,
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
