from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from neotrade3.strategy_config import load_strategy_config
from neotrade3.strategy_exports import export_lowfreq_model_store_to_strategy_config


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run NeoTrade3 strategy utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export-lowfreq-model-store-to-strategy",
        help="Export lowfreq_model_store params_json to config/strategies/lowfreq_v16.json.",
    )
    export_parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (defaults to repository root).",
    )
    export_parser.add_argument(
        "--model-id",
        default="lowfreq_engine_v16_advanced",
        help="lowfreq_model_store.model_id to export.",
    )
    export_parser.add_argument(
        "--strategy-id",
        default="lowfreq_v16",
        help="Strategy id (must be lowfreq_v16).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    project_root = Path(args.project_root) if args.project_root else _default_project_root()
    command = str(args.command or "").strip()

    try:
        if command == "export-lowfreq-model-store-to-strategy":
            strategy_id = str(args.strategy_id or "").strip()
            if strategy_id != "lowfreq_v16":
                raise ValueError("strategy_id must be lowfreq_v16")
            model_id = str(args.model_id or "").strip()
            dest_path = export_lowfreq_model_store_to_strategy_config(
                project_root=project_root,
                model_id=model_id,
                strategy_id=strategy_id,
            )
            exported = load_strategy_config(project_root=project_root, strategy_id=strategy_id)
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "command": command,
                        "project_root": str(project_root),
                        "model_id": model_id,
                        "strategy_id": strategy_id,
                        "path": str(dest_path),
                        "parameter_keys_count": len(exported.parameters),
                        "parameter_keys": sorted(exported.parameters.keys()),
                    },
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        raise ValueError(f"unknown command: {command}")
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "command": command,
                    "project_root": str(project_root),
                    "reason": str(exc),
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
