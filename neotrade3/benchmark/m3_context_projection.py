"""Local persisted projection owner for benchmark replay m3_context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


BENCHMARK_M3_CONTEXT_PROJECTION_OBJECT_TYPE = "m3_context_projection"
BENCHMARK_M3_CONTEXT_PROJECTION_OBJECT_VERSION = 1


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _copy_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a JSON object")
    return {str(key): item for key, item in value.items()}


@dataclass(frozen=True)
class BenchmarkM3ContextProjection:
    m1_constraints_ref: dict[str, Any]
    identify_state: dict[str, Any]
    tracking_state: dict[str, Any]
    entry_state: dict[str, Any]
    object_type: str = BENCHMARK_M3_CONTEXT_PROJECTION_OBJECT_TYPE
    object_version: int = BENCHMARK_M3_CONTEXT_PROJECTION_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "m1_constraints_ref": _copy_mapping(
                self.m1_constraints_ref,
                field_name="m3_context_projection.m1_constraints_ref",
            ),
            "identify_state": _copy_mapping(
                self.identify_state,
                field_name="m3_context_projection.identify_state",
            ),
            "tracking_state": _copy_mapping(
                self.tracking_state,
                field_name="m3_context_projection.tracking_state",
            ),
            "entry_state": _copy_mapping(
                self.entry_state,
                field_name="m3_context_projection.entry_state",
            ),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "BenchmarkM3ContextProjection":
        if not isinstance(payload, Mapping):
            raise TypeError("m3_context_projection must be a JSON object")
        object_type = str(
            payload.get("object_type") or BENCHMARK_M3_CONTEXT_PROJECTION_OBJECT_TYPE
        )
        if object_type != BENCHMARK_M3_CONTEXT_PROJECTION_OBJECT_TYPE:
            raise ValueError(
                "m3_context_projection.object_type must equal "
                f"{BENCHMARK_M3_CONTEXT_PROJECTION_OBJECT_TYPE}"
            )
        object_version = int(
            payload.get(
                "object_version",
                BENCHMARK_M3_CONTEXT_PROJECTION_OBJECT_VERSION,
            )
        )
        if object_version != BENCHMARK_M3_CONTEXT_PROJECTION_OBJECT_VERSION:
            raise ValueError(
                "m3_context_projection.object_version must equal "
                f"{BENCHMARK_M3_CONTEXT_PROJECTION_OBJECT_VERSION}"
            )
        return cls(
            m1_constraints_ref=_copy_mapping(
                payload.get("m1_constraints_ref"),
                field_name="m3_context_projection.m1_constraints_ref",
            ),
            identify_state=_copy_mapping(
                payload.get("identify_state"),
                field_name="m3_context_projection.identify_state",
            ),
            tracking_state=_copy_mapping(
                payload.get("tracking_state"),
                field_name="m3_context_projection.tracking_state",
            ),
            entry_state=_copy_mapping(
                payload.get("entry_state"),
                field_name="m3_context_projection.entry_state",
            ),
            object_type=object_type,
            object_version=object_version,
        )


@dataclass(frozen=True)
class BenchmarkM3ContextProjectionArtifactRecord:
    record_id: str
    written_at: str
    artifact_path: str


@dataclass(frozen=True)
class BenchmarkM3ContextProjectionLedgerRecord:
    record_id: str
    written_at: str
    artifact_path: str
    ledger_path: str

    @classmethod
    def from_dict(cls, payload: Any) -> "BenchmarkM3ContextProjectionLedgerRecord":
        if not isinstance(payload, Mapping):
            raise TypeError("m3_context_projection ledger root must be a JSON object")
        return cls(
            record_id=str(payload.get("record_id") or "").strip(),
            written_at=str(payload.get("written_at") or "").strip(),
            artifact_path=str(payload.get("artifact_path") or "").strip(),
            ledger_path=str(payload.get("ledger_path") or "").strip(),
        )


def build_benchmark_m3_context_projection_record_id(
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
        / "var/artifacts/benchmark_m3_contexts"
        / record_id
        / "m3_context_projection.json"
    )


def _ledger_file(*, project_root: Path, record_id: str) -> Path:
    return (
        project_root
        / "var/ledgers/benchmark_m3_contexts"
        / record_id
        / "m3_context_projection.json"
    )


def write_benchmark_m3_context_projection_artifact(
    *,
    project_root: str | Path,
    record_id: str,
    projection: BenchmarkM3ContextProjection,
    dry_run: bool = False,
) -> BenchmarkM3ContextProjectionArtifactRecord:
    project_root_path = Path(project_root)
    artifact_file = _artifact_file(project_root=project_root_path, record_id=record_id)
    written_at = _now_iso()
    payload = {
        **projection.to_payload(),
        "record_id": record_id,
        "written_at": written_at,
    }
    if not dry_run:
        artifact_file.parent.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return BenchmarkM3ContextProjectionArtifactRecord(
        record_id=record_id,
        written_at=written_at,
        artifact_path=str(artifact_file.relative_to(project_root_path)),
    )


def write_benchmark_m3_context_projection_ledger(
    *,
    project_root: str | Path,
    record_id: str,
    projection: BenchmarkM3ContextProjection,
    artifact_record: BenchmarkM3ContextProjectionArtifactRecord,
    dry_run: bool = False,
) -> BenchmarkM3ContextProjectionLedgerRecord:
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
    return BenchmarkM3ContextProjectionLedgerRecord.from_dict(payload)


def materialize_benchmark_m3_context_projection(
    *,
    project_root: str | Path,
    record_id: str,
    projection: BenchmarkM3ContextProjection,
    dry_run: bool = False,
) -> BenchmarkM3ContextProjectionLedgerRecord:
    artifact_record = write_benchmark_m3_context_projection_artifact(
        project_root=project_root,
        record_id=record_id,
        projection=projection,
        dry_run=dry_run,
    )
    return write_benchmark_m3_context_projection_ledger(
        project_root=project_root,
        record_id=record_id,
        projection=projection,
        artifact_record=artifact_record,
        dry_run=dry_run,
    )


def read_benchmark_m3_context_projection_artifact(
    *,
    project_root: str | Path,
    record_id: str,
) -> dict[str, Any] | None:
    artifact_file = _artifact_file(project_root=Path(project_root), record_id=record_id)
    if not artifact_file.exists():
        return None
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def read_benchmark_m3_context_projection(
    *,
    project_root: str | Path,
    record_id: str,
) -> BenchmarkM3ContextProjection | None:
    payload = read_benchmark_m3_context_projection_artifact(
        project_root=project_root,
        record_id=record_id,
    )
    if payload is None:
        return None
    return BenchmarkM3ContextProjection.from_dict(payload)


def read_benchmark_m3_context_projection_ledger(
    *,
    project_root: str | Path,
    record_id: str,
) -> BenchmarkM3ContextProjectionLedgerRecord | None:
    ledger_file = _ledger_file(project_root=Path(project_root), record_id=record_id)
    if not ledger_file.exists():
        return None
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return BenchmarkM3ContextProjectionLedgerRecord.from_dict(payload)
