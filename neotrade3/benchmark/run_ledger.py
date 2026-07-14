"""Ledger/index helpers for NeoTrade3 M4 benchmark batch runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .artifact_writer import BenchmarkArtifactRecord, write_benchmark_batch_run_artifact
from .batch_runner import BenchmarkBatchRunResult


@dataclass(frozen=True)
class BenchmarkRunLedgerRecord:
    run_id: str
    status: str
    written_at: str
    sample_count: int
    registry_path: str
    artifact_path: str
    ledger_path: str
    experiment_id: str = ""
    candidate_run_id: str = ""
    source_run_id: str = ""
    executed_sample_ids: tuple[str, ...] = ()
    grade_summary: dict[str, int] = field(default_factory=dict)
    bucket_summary: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Any) -> "BenchmarkRunLedgerRecord":
        if not isinstance(payload, dict):
            raise TypeError("benchmark run ledger root must be a JSON object")
        return cls(
            run_id=str(payload.get("run_id") or "").strip(),
            status=str(payload.get("status") or "").strip(),
            written_at=str(payload.get("written_at") or "").strip(),
            sample_count=int(payload.get("sample_count", 0)),
            registry_path=str(payload.get("registry_path") or "").strip(),
            artifact_path=str(payload.get("artifact_path") or "").strip(),
            ledger_path=str(payload.get("ledger_path") or "").strip(),
            experiment_id=str(payload.get("experiment_id") or "").strip(),
            candidate_run_id=str(payload.get("candidate_run_id") or "").strip(),
            source_run_id=str(payload.get("source_run_id") or "").strip(),
            executed_sample_ids=tuple(
                str(item).strip()
                for item in payload.get("executed_sample_ids", [])
                if str(item).strip()
            ),
            grade_summary={
                str(key): int(value)
                for key, value in dict(payload.get("grade_summary") or {}).items()
            },
            bucket_summary={
                str(key): int(value)
                for key, value in dict(payload.get("bucket_summary") or {}).items()
            },
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "written_at": self.written_at,
            "sample_count": self.sample_count,
            "registry_path": self.registry_path,
            "artifact_path": self.artifact_path,
            "ledger_path": self.ledger_path,
            "experiment_id": self.experiment_id,
            "candidate_run_id": self.candidate_run_id,
            "source_run_id": self.source_run_id,
            "executed_sample_ids": list(self.executed_sample_ids),
            "grade_summary": dict(self.grade_summary),
            "bucket_summary": dict(self.bucket_summary),
        }


def _ledger_file(*, project_root: Path, run_id: str) -> Path:
    return (
        project_root
        / "var/ledgers/benchmark_runs"
        / run_id
        / "benchmark_batch_run.json"
    )


def _artifact_file(*, project_root: Path, run_id: str) -> Path:
    return (
        project_root
        / "var/artifacts/benchmark_runs"
        / run_id
        / "benchmark_batch_result.json"
    )


def write_benchmark_run_ledger(
    *,
    project_root: str | Path,
    batch_result: BenchmarkBatchRunResult,
    artifact_record: BenchmarkArtifactRecord,
    dry_run: bool = False,
) -> BenchmarkRunLedgerRecord:
    project_root_path = Path(project_root)
    ledger_file = _ledger_file(project_root=project_root_path, run_id=batch_result.run_id)
    candidate_run_context = batch_result.candidate_run_context
    payload = {
        "run_id": batch_result.run_id,
        "status": "completed",
        "written_at": artifact_record.written_at,
        "sample_count": artifact_record.sample_count,
        "registry_path": batch_result.registry_path,
        "artifact_path": artifact_record.artifact_path,
        "ledger_path": str(ledger_file.relative_to(project_root_path)),
        "experiment_id": (
            candidate_run_context.experiment_id if candidate_run_context is not None else ""
        ),
        "candidate_run_id": (
            candidate_run_context.candidate_run_id
            if candidate_run_context is not None
            else ""
        ),
        "source_run_id": (
            candidate_run_context.source_run_id if candidate_run_context is not None else ""
        ),
        "executed_sample_ids": list(batch_result.executed_sample_ids),
        "grade_summary": dict(batch_result.grade_summary),
        "bucket_summary": dict(batch_result.bucket_summary),
    }

    if not dry_run:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return BenchmarkRunLedgerRecord.from_dict(payload)


def materialize_benchmark_batch_run(
    *,
    project_root: str | Path,
    batch_result: BenchmarkBatchRunResult,
    dry_run: bool = False,
) -> BenchmarkRunLedgerRecord:
    artifact_record = write_benchmark_batch_run_artifact(
        project_root=project_root,
        batch_result=batch_result,
        dry_run=dry_run,
    )
    return write_benchmark_run_ledger(
        project_root=project_root,
        batch_result=batch_result,
        artifact_record=artifact_record,
        dry_run=dry_run,
    )


def read_benchmark_run_ledger(
    *,
    project_root: str | Path,
    run_id: str,
) -> BenchmarkRunLedgerRecord | None:
    ledger_file = _ledger_file(project_root=Path(project_root), run_id=run_id)
    if not ledger_file.exists():
        return None
    payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return BenchmarkRunLedgerRecord.from_dict(payload)


def read_benchmark_run_artifact(
    *,
    project_root: str | Path,
    run_id: str,
) -> dict[str, Any] | None:
    artifact_file = _artifact_file(project_root=Path(project_root), run_id=run_id)
    if not artifact_file.exists():
        return None
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def read_benchmark_batch_run_result(
    *,
    project_root: str | Path,
    run_id: str,
) -> BenchmarkBatchRunResult | None:
    artifact_file = _artifact_file(project_root=Path(project_root), run_id=run_id)
    if not artifact_file.exists():
        return None
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    return BenchmarkBatchRunResult.from_dict(payload)


def list_benchmark_run_ledgers(
    *,
    project_root: str | Path,
) -> list[BenchmarkRunLedgerRecord]:
    root = Path(project_root) / "var/ledgers/benchmark_runs"
    if not root.exists():
        return []

    records: list[BenchmarkRunLedgerRecord] = []
    for ledger_file in sorted(root.glob("*/benchmark_batch_run.json")):
        try:
            payload = json.loads(ledger_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            records.append(BenchmarkRunLedgerRecord.from_dict(payload))

    records.sort(key=lambda item: (item.written_at, item.run_id), reverse=True)
    return records
