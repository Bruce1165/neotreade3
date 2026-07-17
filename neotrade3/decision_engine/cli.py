from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from .formal_front import build_lowfreq_formal_front_payload
from .front_context_store import (
    DecisionM3FrontContext,
    build_decision_m3_front_context_record_id,
    materialize_decision_m3_front_context,
)


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_db_path(project_root: Path) -> Path:
    return project_root / "var/db/stock_data.db"


def _parse_codes(value: str) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("codes must be non-empty")
    items = [item.strip() for item in raw.split(",")]
    codes = [item for item in items if item]
    if not codes:
        raise ValueError("codes must be non-empty")
    return codes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run NeoTrade3 M3 decision utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    materialize_parser = subparsers.add_parser(
        "materialize-front-contexts",
        help="Materialize persisted m3_front_context artifacts/ledgers from a sqlite db.",
    )
    materialize_parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (defaults to repository root).",
    )
    materialize_parser.add_argument(
        "--db-path",
        default=None,
        help="SQLite database path (defaults to var/db/stock_data.db).",
    )
    materialize_parser.add_argument(
        "--target-date",
        required=True,
        help="Target date in YYYY-MM-DD format.",
    )
    materialize_parser.add_argument(
        "--codes",
        required=True,
        help="Comma separated stock codes.",
    )
    materialize_parser.add_argument(
        "--run-id",
        required=True,
        help="Run id (required; propagated into M3 payloads).",
    )
    materialize_parser.add_argument(
        "--source-run-id",
        required=True,
        help="Source run id (required; propagated into M3 payloads).",
    )
    materialize_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute without writing artifact/ledger outputs under var/.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    project_root = Path(args.project_root) if args.project_root else _default_project_root()
    command = str(args.command or "").strip()

    try:
        if command != "materialize-front-contexts":
            raise ValueError(f"unknown command: {command}")

        target_date = date.fromisoformat(str(args.target_date))
        run_id = str(args.run_id or "").strip()
        source_run_id = str(args.source_run_id or "").strip()
        if not run_id:
            raise ValueError("run_id must be non-empty")
        if not source_run_id:
            raise ValueError("source_run_id must be non-empty")
        codes = _parse_codes(str(args.codes))

        db_path = Path(args.db_path) if args.db_path else _default_db_path(project_root)
        conn = sqlite3.connect(str(db_path))
        try:
            formal_payload = build_lowfreq_formal_front_payload(
                conn.cursor(),
                target_date=target_date,
                candidate_signals=[{"code": code} for code in codes],
                run_id=run_id,
                source_run_id=source_run_id,
                history_limit=20,
            )
        finally:
            conn.close()

        items_by_code = dict(formal_payload.get("items_by_code") or {})
        contexts: dict[str, DecisionM3FrontContext] = {}
        errors: list[dict[str, Any]] = []
        for code in codes:
            item = items_by_code.get(code) or {}
            if not isinstance(item, dict):
                raise TypeError("formal_front.items_by_code must be a JSON object map")
            if str(item.get("status") or "").strip() != "ok":
                errors.append(
                    {
                        "code": code,
                        "status": str(item.get("status") or "").strip() or "error",
                        "error_type": str(item.get("error_type") or "").strip(),
                        "message": str(item.get("message") or "").strip(),
                    }
                )
                continue
            contexts[code] = DecisionM3FrontContext(
                run_id=run_id,
                source_run_id=source_run_id,
                m1_constraints_ref=dict(item.get("m1_constraints_ref") or {}),
                identify_state=dict(item.get("identify_state") or {}),
                tracking_state=dict(item.get("tracking_state") or {}),
                entry_state=dict(item.get("entry_state") or {}),
            )

        if errors:
            raise ValueError(
                f"failed to build m3_front_context for codes: {[err['code'] for err in errors]}"
            )

        records = []
        for code in codes:
            record_id = build_decision_m3_front_context_record_id(
                stock_code=code,
                trade_date=target_date.isoformat(),
            )
            record = materialize_decision_m3_front_context(
                project_root=project_root,
                record_id=record_id,
                front_context=contexts[code],
                dry_run=bool(args.dry_run),
            )
            records.append(
                {
                    "stock_code": code,
                    "record_id": record.record_id,
                    "artifact_path": record.artifact_path,
                    "ledger_path": record.ledger_path,
                    "written_at": record.written_at,
                }
            )

        print(
            json.dumps(
                {
                    "status": "ok",
                    "command": command,
                    "project_root": str(project_root),
                    "db_path": str(db_path),
                    "target_date": target_date.isoformat(),
                    "run_id": run_id,
                    "source_run_id": source_run_id,
                    "codes": list(codes),
                    "records": records,
                    "dry_run": bool(args.dry_run),
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
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
