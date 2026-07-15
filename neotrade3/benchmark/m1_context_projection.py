"""Local persisted projection owner for benchmark replay m1_context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


BENCHMARK_M1_CONTEXT_PROJECTION_OBJECT_TYPE = "m1_context_projection"
BENCHMARK_M1_CONTEXT_PROJECTION_OBJECT_VERSION = 1


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass(frozen=True)
class BenchmarkM1ContextProjection:
    source: str
    object_type: str = BENCHMARK_M1_CONTEXT_PROJECTION_OBJECT_TYPE
    object_version: int = BENCHMARK_M1_CONTEXT_PROJECTION_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "BenchmarkM1ContextProjection":
        if not isinstance(payload, dict):
            raise TypeError("m1_context_projection must be a JSON object")
        source = str(payload.get("source") or "").strip()
        if not source:
            raise ValueError("m1_context_projection.source must be non-empty")
        return cls(
            source=source,
            object_type=str(
                payload.get("object_type") or BENCHMARK_M1_CONTEXT_PROJECTION_OBJECT_TYPE
            ),
            object_version=int(
                payload.get(
                    "object_version",
                    BENCHMARK_M1_CONTEXT_PROJECTION_OBJECT_VERSION,
                )
            ),
        )


@dataclass(frozen=True)
class BenchmarkM1ContextProjectionArtifactRecord:
    record_id: str
    written_at: str
    artifact_path: str


@dataclass(frozen=True)
class BenchmarkM1ContextProjectionLedgerRecord:
    record_id: str
    written_at: str
    source: str
    artifact_path: str
    ledger_path: str

    @classmethod
    def from_dict(cls, payload: Any) -> "BenchmarkM1ContextProjectionLedgerRecord":
        if not isinstance(payload, dict):
            raise TypeError("m1_context_projection ledger root must be a JSON object")
        return cls(
            record_id=str(payload.get("record_id") or "").strip(),
            written_at=str(payload.get("written_at") or "").strip(),
            source=str(payload.get("source") or "").strip(),
            artifact_path=str(payload.get("artifact_path") or "").strip(),
            ledger_path=str(payload.get("ledger_path") or "").strip(),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "written_at": self.written_at,
            "source": self.source,
            "artifact_path": self.artifact_path,
            "ledger_path": self.ledger_path,
        }


def build_benchmark_m1_context_projection_record_id(
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
        / "var/artifacts/benchmark_m1_contexts"
        / record_id
        / "m1_context_projection.json"
    )


def _ledger_file(*, project_root: Path, record_id: str) -> Path:
    return (
        project_root
        / "var/ledgers/benchmark_m1_contexts"
        / record_id
        / "m1_context_projection.json"
    )


def write_benchmark_m1_context_projection_artifact(
    *,
    project_root: str | Path,
    record_id: str,
    projection: BenchmarkM1ContextProjection,
    dry_run: bool = False,
) -> BenchmarkM1ContextProjectionArtifactRecord:
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

    return BenchmarkM1ContextProjectionArtifactRecord(
        record_id=record_id,
        written_at=written_at,
        artifact_path=str(artifact_file.relative_to(project_root_path)),
    )


def write_benchmark_m1_context_projection_ledger(
    *,
    project_root: str | Path,
    record_id: str,
    projection: BenchmarkM1ContextProjection,
    artifact_record: BenchmarkM1ContextProjectionArtifactRecord,
    dry_run: bool = False,
) -> BenchmarkM1ContextProjectionLedgerRecord:
    project_root_path = Path(project_root)
    ledger_file = _ledger_file(project_root=project_root_path, record_id=record_id)
    payload = {
        "record_id": record_id,
        "written_at": artifact_record.written_at,
        "source": projection.source,
        "artifact_path": artifact_record.artifact_path,
        "ledger_path": str(ledger_file.relative_to(project_root_path)),
    }

    if not dry_run:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return BenchmarkM1ContextProjectionLedgerRecord.from_dict(payload)


def materialize_benchmark_m1_context_projection(
    *,
    project_root: str | Path,
    record_id: str,
    projection: BenchmarkM1ContextProjection,
    dry_run: bool = False,
) -> BenchmarkM1ContextProjectionLedgerRecord:
    artifact_record = write_benchmark_m1_context_projection_artifact(
        project_root=project_root,
        record_id=record_id,
        projection=projection,
        dry_run=dry_run,
    )
    return write_benchmark_m1_context_projection_ledger(
        project_root=project_root,
        record_id=record_id,
        projection=projection,
        artifact_record=artifact_record,
        dry_run=dry_run,
    )


def read_benchmark_m1_context_projection_artifact(
    *,
    project_root: str | Path,
    record_id: str,
) -> dict[str, Any] | None:
    artifact_file = _artifact_file(project_root=Path(project_root), record_id=record_id)
    if not artifact_file.exists():
        return None
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def read_benchmark_m1_context_projection(
    *,
    project_root: str | Path,
    record_id: str,
) -> BenchmarkM1ContextProjection | None:
    payload = read_benchmark_m1_context_projection_artifact(
        project_root=project_root,
        record_id=record_id,
    )
    if payload is None:
        return None
    return BenchmarkM1ContextProjection.from_dict(payload)


def read_benchmark_m1_context_projection_ledger(
    *,
    project_root: str | Path,
    record_id: str,
) -> BenchmarkM1ContextProjectionLedgerRecord | None:
    ledger_file = _ledger_file(project_root=Path(project_root), record_id=record_id)
    if not ledger_file.exists():
        return None
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return BenchmarkM1ContextProjectionLedgerRecord.from_dict(payload)
