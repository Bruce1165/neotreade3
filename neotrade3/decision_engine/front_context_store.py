"""Persisted canonical owner for M3 front-only decision context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


DECISION_M3_FRONT_CONTEXT_OBJECT_TYPE = "m3_front_context"
DECISION_M3_FRONT_CONTEXT_OBJECT_VERSION = 1


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _copy_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a JSON object")
    return {str(key): item for key, item in value.items()}


@dataclass(frozen=True)
class DecisionM3FrontContext:
    m1_constraints_ref: dict[str, Any]
    identify_state: dict[str, Any]
    tracking_state: dict[str, Any]
    entry_state: dict[str, Any]
    object_type: str = DECISION_M3_FRONT_CONTEXT_OBJECT_TYPE
    object_version: int = DECISION_M3_FRONT_CONTEXT_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "m1_constraints_ref": _copy_mapping(
                self.m1_constraints_ref,
                field_name="m3_front_context.m1_constraints_ref",
            ),
            "identify_state": _copy_mapping(
                self.identify_state,
                field_name="m3_front_context.identify_state",
            ),
            "tracking_state": _copy_mapping(
                self.tracking_state,
                field_name="m3_front_context.tracking_state",
            ),
            "entry_state": _copy_mapping(
                self.entry_state,
                field_name="m3_front_context.entry_state",
            ),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "DecisionM3FrontContext":
        if not isinstance(payload, Mapping):
            raise TypeError("m3_front_context must be a JSON object")
        object_type = str(
            payload.get("object_type") or DECISION_M3_FRONT_CONTEXT_OBJECT_TYPE
        )
        if object_type != DECISION_M3_FRONT_CONTEXT_OBJECT_TYPE:
            raise ValueError(
                "m3_front_context.object_type must equal "
                f"{DECISION_M3_FRONT_CONTEXT_OBJECT_TYPE}"
            )
        object_version = int(
            payload.get(
                "object_version",
                DECISION_M3_FRONT_CONTEXT_OBJECT_VERSION,
            )
        )
        if object_version != DECISION_M3_FRONT_CONTEXT_OBJECT_VERSION:
            raise ValueError(
                "m3_front_context.object_version must equal "
                f"{DECISION_M3_FRONT_CONTEXT_OBJECT_VERSION}"
            )
        return cls(
            m1_constraints_ref=_copy_mapping(
                payload.get("m1_constraints_ref"),
                field_name="m3_front_context.m1_constraints_ref",
            ),
            identify_state=_copy_mapping(
                payload.get("identify_state"),
                field_name="m3_front_context.identify_state",
            ),
            tracking_state=_copy_mapping(
                payload.get("tracking_state"),
                field_name="m3_front_context.tracking_state",
            ),
            entry_state=_copy_mapping(
                payload.get("entry_state"),
                field_name="m3_front_context.entry_state",
            ),
            object_type=object_type,
            object_version=object_version,
        )


@dataclass(frozen=True)
class DecisionM3FrontContextArtifactRecord:
    record_id: str
    written_at: str
    artifact_path: str


@dataclass(frozen=True)
class DecisionM3FrontContextLedgerRecord:
    record_id: str
    written_at: str
    artifact_path: str
    ledger_path: str

    @classmethod
    def from_dict(cls, payload: Any) -> "DecisionM3FrontContextLedgerRecord":
        if not isinstance(payload, Mapping):
            raise TypeError("m3_front_context ledger root must be a JSON object")
        return cls(
            record_id=str(payload.get("record_id") or "").strip(),
            written_at=str(payload.get("written_at") or "").strip(),
            artifact_path=str(payload.get("artifact_path") or "").strip(),
            ledger_path=str(payload.get("ledger_path") or "").strip(),
        )


def build_decision_m3_front_context_record_id(
    *,
    stock_code: str,
    trade_date: str,
) -> str:
    normalized_stock_code = str(stock_code or "").strip()
    normalized_trade_date = str(trade_date or "").strip()
    if not normalized_stock_code:
        raise ValueError("stock_code must be non-empty")
    if not normalized_trade_date:
        raise ValueError("trade_date must be non-empty")
    return f"{normalized_stock_code}-{normalized_trade_date}"


def _artifact_file(*, project_root: Path, record_id: str) -> Path:
    return (
        project_root
        / "var/artifacts/m3_front_contexts"
        / record_id
        / "front_context.json"
    )


def _ledger_file(*, project_root: Path, record_id: str) -> Path:
    return (
        project_root
        / "var/ledgers/m3_front_contexts"
        / record_id
        / "front_context.json"
    )


def write_decision_m3_front_context_artifact(
    *,
    project_root: str | Path,
    record_id: str,
    front_context: DecisionM3FrontContext,
    dry_run: bool = False,
) -> DecisionM3FrontContextArtifactRecord:
    project_root_path = Path(project_root)
    artifact_file = _artifact_file(project_root=project_root_path, record_id=record_id)
    written_at = _now_iso()
    payload = {
        **front_context.to_payload(),
        "record_id": record_id,
        "written_at": written_at,
    }
    if not dry_run:
        artifact_file.parent.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return DecisionM3FrontContextArtifactRecord(
        record_id=record_id,
        written_at=written_at,
        artifact_path=str(artifact_file.relative_to(project_root_path)),
    )


def write_decision_m3_front_context_ledger(
    *,
    project_root: str | Path,
    record_id: str,
    front_context: DecisionM3FrontContext,
    artifact_record: DecisionM3FrontContextArtifactRecord,
    dry_run: bool = False,
) -> DecisionM3FrontContextLedgerRecord:
    project_root_path = Path(project_root)
    ledger_file = _ledger_file(project_root=project_root_path, record_id=record_id)
    payload = {
        "record_id": record_id,
        "written_at": artifact_record.written_at,
        "artifact_path": artifact_record.artifact_path,
        "ledger_path": str(ledger_file.relative_to(project_root_path)),
    }
    if not dry_run:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return DecisionM3FrontContextLedgerRecord.from_dict(payload)


def materialize_decision_m3_front_context(
    *,
    project_root: str | Path,
    record_id: str,
    front_context: DecisionM3FrontContext,
    dry_run: bool = False,
) -> DecisionM3FrontContextLedgerRecord:
    artifact_record = write_decision_m3_front_context_artifact(
        project_root=project_root,
        record_id=record_id,
        front_context=front_context,
        dry_run=dry_run,
    )
    return write_decision_m3_front_context_ledger(
        project_root=project_root,
        record_id=record_id,
        front_context=front_context,
        artifact_record=artifact_record,
        dry_run=dry_run,
    )


def read_decision_m3_front_context_artifact(
    *,
    project_root: str | Path,
    record_id: str,
) -> dict[str, Any] | None:
    artifact_file = _artifact_file(project_root=Path(project_root), record_id=record_id)
    if not artifact_file.exists():
        return None
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def read_decision_m3_front_context(
    *,
    project_root: str | Path,
    record_id: str,
) -> DecisionM3FrontContext | None:
    payload = read_decision_m3_front_context_artifact(
        project_root=project_root,
        record_id=record_id,
    )
    if payload is None:
        return None
    return DecisionM3FrontContext.from_dict(payload)


def read_decision_m3_front_context_ledger(
    *,
    project_root: str | Path,
    record_id: str,
) -> DecisionM3FrontContextLedgerRecord | None:
    ledger_file = _ledger_file(project_root=Path(project_root), record_id=record_id)
    if not ledger_file.exists():
        return None
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return DecisionM3FrontContextLedgerRecord.from_dict(payload)
