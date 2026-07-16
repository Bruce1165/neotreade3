"""Ledger/readback helpers for NeoTrade3 M2 small-cycle persisted snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_writer import (
    SmallCycleArtifactRecord,
    build_small_cycle_record_id,
    write_small_cycle_artifact,
)
from .contracts import SmallCycle


@dataclass(frozen=True)
class SmallCycleLedgerRecord:
    record_id: str
    written_at: str
    stock_code: str
    trade_date: str
    cycle_state: str
    artifact_path: str
    ledger_path: str

    @classmethod
    def from_dict(cls, payload: Any) -> "SmallCycleLedgerRecord":
        if not isinstance(payload, dict):
            raise TypeError("small_cycle ledger root must be a JSON object")
        return cls(
            record_id=str(payload.get("record_id") or "").strip(),
            written_at=str(payload.get("written_at") or "").strip(),
            stock_code=str(payload.get("stock_code") or "").strip(),
            trade_date=str(payload.get("trade_date") or "").strip(),
            cycle_state=str(payload.get("cycle_state") or "").strip(),
            artifact_path=str(payload.get("artifact_path") or "").strip(),
            ledger_path=str(payload.get("ledger_path") or "").strip(),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "written_at": self.written_at,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "cycle_state": self.cycle_state,
            "artifact_path": self.artifact_path,
            "ledger_path": self.ledger_path,
        }


def _artifact_file(*, project_root: Path, record_id: str) -> Path:
    return project_root / "var/artifacts/m2_small_cycles" / record_id / "small_cycle.json"


def _ledger_file(*, project_root: Path, record_id: str) -> Path:
    return project_root / "var/ledgers/m2_small_cycles" / record_id / "small_cycle.json"


def write_small_cycle_ledger(
    *,
    project_root: str | Path,
    small_cycle: SmallCycle,
    artifact_record: SmallCycleArtifactRecord,
    dry_run: bool = False,
) -> SmallCycleLedgerRecord:
    project_root_path = Path(project_root)
    record_id = build_small_cycle_record_id(small_cycle=small_cycle)
    ledger_file = _ledger_file(project_root=project_root_path, record_id=record_id)
    payload = {
        "record_id": record_id,
        "written_at": artifact_record.written_at,
        "stock_code": small_cycle.stock_code,
        "trade_date": small_cycle.trade_date,
        "cycle_state": small_cycle.cycle_state,
        "artifact_path": artifact_record.artifact_path,
        "ledger_path": str(ledger_file.relative_to(project_root_path)),
    }

    if not dry_run:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return SmallCycleLedgerRecord.from_dict(payload)


def materialize_small_cycle(
    *,
    project_root: str | Path,
    small_cycle: SmallCycle,
    dry_run: bool = False,
) -> SmallCycleLedgerRecord:
    artifact_record = write_small_cycle_artifact(
        project_root=project_root,
        small_cycle=small_cycle,
        dry_run=dry_run,
    )
    return write_small_cycle_ledger(
        project_root=project_root,
        small_cycle=small_cycle,
        artifact_record=artifact_record,
        dry_run=dry_run,
    )


def read_small_cycle_artifact(
    *,
    project_root: str | Path,
    record_id: str,
) -> dict[str, Any] | None:
    artifact_file = _artifact_file(project_root=Path(project_root), record_id=record_id)
    if not artifact_file.exists():
        return None
    try:
        raw = artifact_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"failed to read m2_small_cycle artifact: {artifact_file}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in m2_small_cycle artifact: {artifact_file}") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"m2_small_cycle artifact root must be a JSON object: {artifact_file}")
    return payload


def read_small_cycle(
    *,
    project_root: str | Path,
    record_id: str,
) -> SmallCycle | None:
    payload = read_small_cycle_artifact(project_root=project_root, record_id=record_id)
    if payload is None:
        return None
    return SmallCycle.from_dict(payload)


def read_small_cycle_ledger(
    *,
    project_root: str | Path,
    record_id: str,
) -> SmallCycleLedgerRecord | None:
    ledger_file = _ledger_file(project_root=Path(project_root), record_id=record_id)
    if not ledger_file.exists():
        return None
    try:
        raw = ledger_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"failed to read m2_small_cycle ledger: {ledger_file}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in m2_small_cycle ledger: {ledger_file}") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"m2_small_cycle ledger root must be a JSON object: {ledger_file}")
    return SmallCycleLedgerRecord.from_dict(payload)


def list_small_cycle_ledgers(
    *,
    project_root: str | Path,
    limit: int = 200,
) -> list[SmallCycleLedgerRecord]:
    if limit <= 0:
        raise ValueError("limit must be a positive integer")
    root = Path(project_root) / "var/ledgers/m2_small_cycles"
    if not root.exists():
        return []

    records: list[SmallCycleLedgerRecord] = []
    for ledger_file in root.glob("*/small_cycle.json"):
        try:
            raw = ledger_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(
                f"failed to read m2_small_cycle ledger: {ledger_file}"
            ) from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid JSON in m2_small_cycle ledger: {ledger_file}"
            ) from exc
        if not isinstance(payload, dict):
            raise TypeError(
                f"m2_small_cycle ledger root must be a JSON object: {ledger_file}"
            )
        try:
            records.append(SmallCycleLedgerRecord.from_dict(payload))
        except Exception as exc:
            raise ValueError(
                f"invalid m2_small_cycle ledger payload: {ledger_file}"
            ) from exc

    records.sort(key=lambda item: (item.written_at, item.record_id), reverse=True)
    if len(records) > limit:
        records = records[:limit]
    return records
