"""Screener run record IO for NeoTrade3 bootstrap."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ScreenerRunRecord:
    target_date: str
    screener_id: str
    status: str
    requested_at: str
    finished_at: str | None
    picks_count: int
    artifact_path: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScreenerRunRecord":
        return cls(
            target_date=str(payload["target_date"]),
            screener_id=str(payload["screener_id"]),
            status=str(payload["status"]),
            requested_at=str(payload["requested_at"]),
            finished_at=(
                str(payload["finished_at"]) if payload.get("finished_at") else None
            ),
            picks_count=int(payload.get("picks_count", 0)),
            artifact_path=str(payload.get("artifact_path", "")),
        )


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def write_placeholder_run(
    *,
    project_root: Path,
    target_date: str,
    screener_id: str,
    requested_by: str,
    parameters: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> ScreenerRunRecord:
    ledgers_dir = project_root / "var/ledgers/screener_runs" / target_date
    artifacts_dir = project_root / "var/artifacts/screener_runs" / target_date

    requested_at = _now_iso()
    artifact_file = artifacts_dir / f"screener_{screener_id}_result.json"
    ledger_file = ledgers_dir / f"screener_{screener_id}_run.json"

    artifact_payload = {
        "target_date": target_date,
        "screener_id": screener_id,
        "requested_by": requested_by,
        "requested_at": requested_at,
        "status": "pending_implementation",
        "parameters": parameters or {},
        "picks": [],
        "decision_trace": [],
    }
    ledger_payload = {
        "target_date": target_date,
        "screener_id": screener_id,
        "status": "pending_implementation",
        "requested_at": requested_at,
        "finished_at": None,
        "picks_count": 0,
        "artifact_path": artifact_file.name,
    }

    if not dry_run:
        ledgers_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(artifact_payload, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        ledger_file.write_text(
            json.dumps(ledger_payload, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    return ScreenerRunRecord.from_dict(ledger_payload)


def write_screener_run(
    *,
    project_root: Path,
    target_date: str,
    screener_id: str,
    requested_by: str,
    parameters: dict[str, Any],
    runtime_result: dict[str, Any],
    dry_run: bool = False,
) -> ScreenerRunRecord:
    ledgers_dir = project_root / "var/ledgers/screener_runs" / target_date
    artifacts_dir = project_root / "var/artifacts/screener_runs" / target_date

    requested_at = _now_iso()
    finished_at = _now_iso()
    artifact_file = artifacts_dir / f"screener_{screener_id}_result.json"
    ledger_file = ledgers_dir / f"screener_{screener_id}_run.json"

    status = str(runtime_result.get("status", "failed"))
    picks = runtime_result.get("picks")
    picks_count = len(picks) if isinstance(picks, list) else 0

    artifact_payload = {
        **runtime_result,
        "target_date": target_date,
        "screener_id": screener_id,
        "requested_by": requested_by,
        "requested_at": requested_at,
        "finished_at": finished_at,
        "parameters": parameters,
    }
    ledger_payload = {
        "target_date": target_date,
        "screener_id": screener_id,
        "status": status,
        "requested_at": requested_at,
        "finished_at": finished_at,
        "picks_count": picks_count,
        "artifact_path": artifact_file.name,
    }

    if not dry_run:
        ledgers_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(artifact_payload, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        ledger_file.write_text(
            json.dumps(ledger_payload, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    return ScreenerRunRecord.from_dict(ledger_payload)


def list_screener_runs(
    *, project_root: Path, target_date: str | None = None
) -> list[ScreenerRunRecord]:
    root = project_root / "var/ledgers/screener_runs"
    if not root.exists():
        return []

    date_dirs = [root / target_date] if target_date else sorted(root.glob("*"))
    records: list[ScreenerRunRecord] = []

    for date_dir in date_dirs:
        if not date_dir.exists() or not date_dir.is_dir():
            continue
        for path in sorted(date_dir.glob("screener_*_run.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                records.append(ScreenerRunRecord.from_dict(payload))

    records.sort(
        key=lambda record: (record.target_date, record.screener_id), reverse=True
    )
    return records


def _run_paths(
    *, project_root: Path, target_date: str, screener_id: str
) -> tuple[Path, Path]:
    ledgers_dir = project_root / "var/ledgers/screener_runs" / target_date
    artifacts_dir = project_root / "var/artifacts/screener_runs" / target_date
    ledger_file = ledgers_dir / f"screener_{screener_id}_run.json"
    artifact_file = artifacts_dir / f"screener_{screener_id}_result.json"
    return ledger_file, artifact_file


def read_screener_run_ledger(
    *,
    project_root: Path,
    target_date: str,
    screener_id: str,
) -> ScreenerRunRecord | None:
    ledger_file, _ = _run_paths(
        project_root=project_root, target_date=target_date, screener_id=screener_id
    )
    if not ledger_file.exists():
        return None
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return ScreenerRunRecord.from_dict(payload)


def read_screener_run_artifact(
    *,
    project_root: Path,
    target_date: str,
    screener_id: str,
) -> dict[str, Any] | None:
    _, artifact_file = _run_paths(
        project_root=project_root, target_date=target_date, screener_id=screener_id
    )
    if not artifact_file.exists():
        return None
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _config_path(*, config_dir: Path, screener_id: str) -> Path:
    return config_dir / f"{screener_id}.json"


def read_screener_config(
    *, config_dir: Path, screener_id: str
) -> dict[str, Any] | None:
    path = _config_path(config_dir=config_dir, screener_id=screener_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def write_screener_config(
    *,
    config_dir: Path,
    screener_id: str,
    current_parameters: dict[str, Any],
    requested_by: str,
) -> dict[str, Any]:
    config_dir.mkdir(parents=True, exist_ok=True)
    path = _config_path(config_dir=config_dir, screener_id=screener_id)
    payload = read_screener_config(config_dir=config_dir, screener_id=screener_id) or {
        "version": 1,
        "screener_id": screener_id,
        "schema": {},
        "default_parameters": {},
        "current_parameters": {},
    }
    payload["current_parameters"] = current_parameters
    payload["updated_at"] = _now_iso()
    payload["updated_by"] = requested_by
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _bulk_run_paths(*, project_root: Path, target_date: str) -> tuple[Path, Path]:
    ledgers_dir = project_root / "var/ledgers/screener_runs" / target_date
    artifacts_dir = project_root / "var/artifacts/screener_runs" / target_date
    ledger_file = ledgers_dir / "bulk_run_ledger.json"
    artifact_file = artifacts_dir / "bulk_run_result.json"
    return ledger_file, artifact_file


def read_bulk_run_ledger(
    *, project_root: Path, target_date: str
) -> dict[str, Any] | None:
    ledger_file, _ = _bulk_run_paths(project_root=project_root, target_date=target_date)
    if not ledger_file.exists():
        return None
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def read_bulk_run_artifact(
    *, project_root: Path, target_date: str
) -> dict[str, Any] | None:
    _, artifact_file = _bulk_run_paths(
        project_root=project_root, target_date=target_date
    )
    if not artifact_file.exists():
        return None
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def list_bulk_runs(
    *, project_root: Path, target_date: str | None = None
) -> list[dict[str, Any]]:
    root = project_root / "var/ledgers/screener_runs"
    if not root.exists():
        return []

    date_dirs = [root / target_date] if target_date else sorted(root.glob("*"))
    ledgers: list[dict[str, Any]] = []

    for date_dir in date_dirs:
        if not date_dir.exists() or not date_dir.is_dir():
            continue
        ledger_file = date_dir / "bulk_run_ledger.json"
        if not ledger_file.exists():
            continue
        try:
            payload = json.loads(ledger_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            ledgers.append(payload)

    ledgers.sort(key=lambda item: str(item.get("target_date", "")), reverse=True)
    return ledgers
