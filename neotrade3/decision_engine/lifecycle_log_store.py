"""Persisted canonical owner for M3 decision-lifecycle logs."""

from __future__ import annotations

import hashlib
import base64
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .contracts import DecisionLifecycleLog


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_decision_m3_lifecycle_log_record_id(*, stock_code: str, run_id: str) -> str:
    normalized_stock_code = str(stock_code or "").strip()
    normalized_run_id = str(run_id or "").strip()
    if not normalized_stock_code:
        raise ValueError("stock_code must be non-empty")
    if not normalized_run_id:
        raise ValueError("run_id must be non-empty")
    record_id = f"{normalized_stock_code}-{normalized_run_id}"
    parsed = Path(record_id)
    if parsed.is_absolute() or len(parsed.parts) != 1 or parsed.name != record_id or record_id in {".", ".."}:
        raise ValueError("invalid record_id")
    return record_id


def build_decision_m3_lifecycle_log_record_id_from_report_id(
    *,
    stock_code: str,
    report_id: str,
) -> str:
    return build_decision_m3_lifecycle_log_record_id(stock_code=stock_code, run_id=report_id)


def encode_decision_m3_lifecycle_log_list_cursor(*, written_at: str, record_id: str) -> str:
    normalized_written_at = str(written_at or "").strip()
    normalized_record_id = str(record_id or "").strip()
    if not normalized_written_at:
        raise ValueError("written_at must be non-empty")
    if not normalized_record_id:
        raise ValueError("record_id must be non-empty")
    parsed = Path(normalized_record_id)
    if (
        parsed.is_absolute()
        or len(parsed.parts) != 1
        or parsed.name != normalized_record_id
        or normalized_record_id in {".", ".."}
    ):
        raise ValueError("invalid record_id")
    raw = json.dumps(
        {"v": 1, "written_at": normalized_written_at, "record_id": normalized_record_id},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_decision_m3_lifecycle_log_list_cursor(cursor: str) -> tuple[str, str]:
    normalized = str(cursor or "").strip()
    if not normalized:
        raise ValueError("cursor must be non-empty")
    padded = normalized + ("=" * (-len(normalized) % 4))
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:
        raise ValueError("invalid cursor") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid cursor") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid cursor")
    if int(payload.get("v", 0)) != 1:
        raise ValueError("invalid cursor")
    written_at = str(payload.get("written_at") or "").strip()
    record_id = str(payload.get("record_id") or "").strip()
    if not written_at or not record_id:
        raise ValueError("invalid cursor")
    parsed = Path(record_id)
    if parsed.is_absolute() or len(parsed.parts) != 1 or parsed.name != record_id or record_id in {".", ".."}:
        raise ValueError("invalid cursor")
    return written_at, record_id


@dataclass(frozen=True)
class DecisionM3LifecycleLogArtifactRecord:
    record_id: str
    written_at: str
    artifact_path: str
    artifact_sha256: str


@dataclass(frozen=True)
class DecisionM3LifecycleLogLedgerRecord:
    record_id: str
    written_at: str
    stock_code: str
    run_id: str
    source_run_id: str
    events_count: int
    first_trade_date: str
    last_trade_date: str
    last_event: str
    last_stage: str
    last_decision: str
    last_exit_scope: str
    artifact_sha256: str
    artifact_path: str
    ledger_path: str

    @classmethod
    def from_dict(cls, payload: Any) -> "DecisionM3LifecycleLogLedgerRecord":
        if not isinstance(payload, dict):
            raise TypeError("m3_lifecycle_log ledger root must be a JSON object")
        try:
            events_count = int(payload.get("events_count", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("m3_lifecycle_log.events_count must be an integer") from exc
        return cls(
            record_id=str(payload.get("record_id") or "").strip(),
            written_at=str(payload.get("written_at") or "").strip(),
            stock_code=str(payload.get("stock_code") or "").strip(),
            run_id=str(payload.get("run_id") or "").strip(),
            source_run_id=str(payload.get("source_run_id") or "").strip(),
            events_count=events_count,
            first_trade_date=str(payload.get("first_trade_date") or "").strip(),
            last_trade_date=str(payload.get("last_trade_date") or "").strip(),
            last_event=str(payload.get("last_event") or "").strip(),
            last_stage=str(payload.get("last_stage") or "").strip(),
            last_decision=str(payload.get("last_decision") or "").strip(),
            last_exit_scope=str(payload.get("last_exit_scope") or "").strip(),
            artifact_sha256=str(payload.get("artifact_sha256") or "").strip(),
            artifact_path=str(payload.get("artifact_path") or "").strip(),
            ledger_path=str(payload.get("ledger_path") or "").strip(),
        )


def _artifact_file(*, project_root: Path, record_id: str) -> Path:
    return (
        project_root
        / "var/artifacts/m3_lifecycle_logs"
        / record_id
        / "lifecycle_log.json"
    )


def _ledger_file(*, project_root: Path, record_id: str) -> Path:
    return (
        project_root
        / "var/ledgers/m3_lifecycle_logs"
        / record_id
        / "lifecycle_log.json"
    )


def write_decision_m3_lifecycle_log_artifact(
    *,
    project_root: str | Path,
    record_id: str,
    lifecycle_log: DecisionLifecycleLog,
    dry_run: bool = False,
) -> DecisionM3LifecycleLogArtifactRecord:
    project_root_path = Path(project_root)
    artifact_file = _artifact_file(project_root=project_root_path, record_id=record_id)
    written_at = _now_iso()
    payload = lifecycle_log.to_payload()
    artifact_text = _dump_json(payload)
    artifact_sha256 = _sha256_hex(artifact_text)
    if not dry_run:
        artifact_file.parent.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(artifact_text, encoding="utf-8")
    return DecisionM3LifecycleLogArtifactRecord(
        record_id=record_id,
        written_at=written_at,
        artifact_path=str(artifact_file.relative_to(project_root_path)),
        artifact_sha256=artifact_sha256,
    )


def write_decision_m3_lifecycle_log_ledger(
    *,
    project_root: str | Path,
    record_id: str,
    lifecycle_log: DecisionLifecycleLog,
    artifact_record: DecisionM3LifecycleLogArtifactRecord,
    dry_run: bool = False,
) -> DecisionM3LifecycleLogLedgerRecord:
    project_root_path = Path(project_root)
    ledger_file = _ledger_file(project_root=project_root_path, record_id=record_id)
    events_count = len(lifecycle_log.events)
    if lifecycle_log.events:
        first_trade_date = lifecycle_log.events[0].trade_date
        last_trade_date = lifecycle_log.events[-1].trade_date
        last_event = lifecycle_log.events[-1].event
        last_stage = lifecycle_log.events[-1].stage
        last_decision = lifecycle_log.events[-1].decision
        last_exit_scope = lifecycle_log.events[-1].exit_scope
    else:
        first_trade_date = ""
        last_trade_date = ""
        last_event = ""
        last_stage = ""
        last_decision = ""
        last_exit_scope = ""

    payload = {
        "record_id": record_id,
        "written_at": artifact_record.written_at,
        "stock_code": lifecycle_log.stock_code,
        "run_id": lifecycle_log.run_id,
        "source_run_id": lifecycle_log.source_run_id,
        "events_count": events_count,
        "first_trade_date": first_trade_date,
        "last_trade_date": last_trade_date,
        "last_event": last_event,
        "last_stage": last_stage,
        "last_decision": last_decision,
        "last_exit_scope": last_exit_scope,
        "artifact_sha256": artifact_record.artifact_sha256,
        "artifact_path": artifact_record.artifact_path,
        "ledger_path": str(ledger_file.relative_to(project_root_path)),
    }
    if not dry_run:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_file.write_text(_dump_json(payload), encoding="utf-8")
    return DecisionM3LifecycleLogLedgerRecord.from_dict(payload)


def materialize_decision_m3_lifecycle_log(
    *,
    project_root: str | Path,
    record_id: str,
    lifecycle_log: DecisionLifecycleLog,
    dry_run: bool = False,
) -> DecisionM3LifecycleLogLedgerRecord:
    artifact_record = write_decision_m3_lifecycle_log_artifact(
        project_root=project_root,
        record_id=record_id,
        lifecycle_log=lifecycle_log,
        dry_run=dry_run,
    )
    return write_decision_m3_lifecycle_log_ledger(
        project_root=project_root,
        record_id=record_id,
        lifecycle_log=lifecycle_log,
        artifact_record=artifact_record,
        dry_run=dry_run,
    )


def read_decision_m3_lifecycle_log_artifact(
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
        raise ValueError(f"failed to read m3_lifecycle_log artifact: {artifact_file}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in m3_lifecycle_log artifact: {artifact_file}") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"m3_lifecycle_log artifact root must be a JSON object: {artifact_file}")
    return payload


def read_decision_m3_lifecycle_log(
    *,
    project_root: str | Path,
    record_id: str,
) -> DecisionLifecycleLog | None:
    payload = read_decision_m3_lifecycle_log_artifact(project_root=project_root, record_id=record_id)
    if payload is None:
        return None
    return DecisionLifecycleLog.from_dict(payload)


def read_decision_m3_lifecycle_log_ledger(
    *,
    project_root: str | Path,
    record_id: str,
) -> DecisionM3LifecycleLogLedgerRecord | None:
    ledger_file = _ledger_file(project_root=Path(project_root), record_id=record_id)
    if not ledger_file.exists():
        return None
    try:
        raw = ledger_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"failed to read m3_lifecycle_log ledger: {ledger_file}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in m3_lifecycle_log ledger: {ledger_file}") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"m3_lifecycle_log ledger root must be a JSON object: {ledger_file}")
    record = DecisionM3LifecycleLogLedgerRecord.from_dict(payload)
    if not record.record_id:
        raise ValueError(f"m3_lifecycle_log ledger missing record_id: {ledger_file}")
    if not record.written_at:
        raise ValueError(f"m3_lifecycle_log ledger missing written_at: {ledger_file}")
    if not record.stock_code:
        raise ValueError(f"m3_lifecycle_log ledger missing stock_code: {ledger_file}")
    if not record.run_id:
        raise ValueError(f"m3_lifecycle_log ledger missing run_id: {ledger_file}")
    if not record.source_run_id:
        raise ValueError(f"m3_lifecycle_log ledger missing source_run_id: {ledger_file}")
    if record.events_count < 0:
        raise ValueError(f"m3_lifecycle_log ledger invalid events_count: {ledger_file}")
    if record.events_count > 0:
        if not record.first_trade_date:
            raise ValueError(f"m3_lifecycle_log ledger missing first_trade_date: {ledger_file}")
        if not record.last_trade_date:
            raise ValueError(f"m3_lifecycle_log ledger missing last_trade_date: {ledger_file}")
        if not record.last_event:
            raise ValueError(f"m3_lifecycle_log ledger missing last_event: {ledger_file}")
        if not record.last_stage:
            raise ValueError(f"m3_lifecycle_log ledger missing last_stage: {ledger_file}")
        if not record.last_decision:
            raise ValueError(f"m3_lifecycle_log ledger missing last_decision: {ledger_file}")
    if not record.artifact_sha256:
        raise ValueError(f"m3_lifecycle_log ledger missing artifact_sha256: {ledger_file}")
    if not record.artifact_path:
        raise ValueError(f"m3_lifecycle_log ledger missing artifact_path: {ledger_file}")
    if not record.ledger_path:
        raise ValueError(f"m3_lifecycle_log ledger missing ledger_path: {ledger_file}")
    return record


def list_decision_m3_lifecycle_log_ledgers(
    *,
    project_root: str | Path,
    limit: int = 200,
    run_id: str | None = None,
    offset: int = 0,
    cursor_key: tuple[str, str] | None = None,
) -> list[DecisionM3LifecycleLogLedgerRecord]:
    records, _, _ = list_decision_m3_lifecycle_log_ledgers_with_count(
        project_root=project_root,
        limit=limit,
        run_id=run_id,
        offset=offset,
        cursor_key=cursor_key,
    )
    return records


def list_decision_m3_lifecycle_log_ledgers_with_count(
    *,
    project_root: str | Path,
    limit: int = 200,
    run_id: str | None = None,
    offset: int = 0,
    cursor_key: tuple[str, str] | None = None,
) -> tuple[list[DecisionM3LifecycleLogLedgerRecord], int, str | None]:
    if limit <= 0:
        raise ValueError("limit must be a positive integer")
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if cursor_key is not None and offset != 0:
        raise ValueError("invalid pagination")
    normalized_run_id: str | None = None
    if run_id is not None:
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            raise ValueError("run_id must be non-empty")
        parsed = Path(normalized_run_id)
        if (
            parsed.is_absolute()
            or len(parsed.parts) != 1
            or parsed.name != normalized_run_id
            or normalized_run_id in {".", ".."}
        ):
            raise ValueError("invalid run_id")
    root = Path(project_root) / "var/ledgers/m3_lifecycle_logs"
    if not root.exists():
        return [], 0, None

    records: list[DecisionM3LifecycleLogLedgerRecord] = []
    for ledger_file in root.glob("*/lifecycle_log.json"):
        try:
            raw = ledger_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"failed to read m3_lifecycle_log ledger: {ledger_file}") from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in m3_lifecycle_log ledger: {ledger_file}") from exc
        if not isinstance(payload, dict):
            raise TypeError(f"m3_lifecycle_log ledger root must be a JSON object: {ledger_file}")
        try:
            record = DecisionM3LifecycleLogLedgerRecord.from_dict(payload)
        except Exception as exc:
            raise ValueError(f"invalid m3_lifecycle_log ledger payload: {ledger_file}") from exc
        if not record.record_id:
            raise ValueError(f"m3_lifecycle_log ledger missing record_id: {ledger_file}")
        if not record.written_at:
            raise ValueError(f"m3_lifecycle_log ledger missing written_at: {ledger_file}")
        if not record.artifact_path:
            raise ValueError(f"m3_lifecycle_log ledger missing artifact_path: {ledger_file}")
        if not record.ledger_path:
            raise ValueError(f"m3_lifecycle_log ledger missing ledger_path: {ledger_file}")
        if normalized_run_id is not None and record.run_id != normalized_run_id:
            continue
        records.append(record)

    records.sort(key=lambda item: (item.written_at, item.record_id), reverse=True)
    matched_count = len(records)
    if cursor_key is not None:
        cursor_written_at, cursor_record_id = cursor_key
        records = [
            record
            for record in records
            if (record.written_at, record.record_id) < (cursor_written_at, cursor_record_id)
        ]
    if offset:
        records = records[offset:]
    next_cursor: str | None = None
    if len(records) > limit:
        returned = records[:limit]
        if returned:
            last = returned[-1]
            next_cursor = encode_decision_m3_lifecycle_log_list_cursor(
                written_at=last.written_at,
                record_id=last.record_id,
            )
        records = returned
    return records, matched_count, next_cursor
