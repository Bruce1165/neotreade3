"""Persisted canonical owner for M3 front-only decision context."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


DECISION_M3_FRONT_CONTEXT_OBJECT_TYPE = "m3_front_context"
DECISION_M3_FRONT_CONTEXT_OBJECT_VERSION = 2


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _copy_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a JSON object")
    return {str(key): item for key, item in value.items()}


@dataclass(frozen=True)
class DecisionM3FrontContext:
    run_id: str
    source_run_id: str
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
            "run_id": self.run_id,
            "source_run_id": self.source_run_id,
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
        allowed_keys = {
            "object_type",
            "object_version",
            "record_id",
            "written_at",
            "run_id",
            "source_run_id",
            "m1_constraints_ref",
            "identify_state",
            "tracking_state",
            "entry_state",
        }
        unknown_keys = sorted(
            str(key)
            for key in payload.keys()
            if str(key) not in allowed_keys
        )
        if unknown_keys:
            raise ValueError(
                "m3_front_context contains unknown fields: "
                f"{unknown_keys}"
            )

        object_type = str(payload.get("object_type") or "").strip()
        if object_type != DECISION_M3_FRONT_CONTEXT_OBJECT_TYPE:
            raise ValueError(
                "m3_front_context.object_type must equal "
                f"{DECISION_M3_FRONT_CONTEXT_OBJECT_TYPE}"
            )
        try:
            object_version = int(payload.get("object_version", -1))
        except (TypeError, ValueError) as exc:
            raise ValueError("m3_front_context.object_version must be an integer") from exc
        if object_version != DECISION_M3_FRONT_CONTEXT_OBJECT_VERSION:
            raise ValueError(
                "m3_front_context.object_version must equal "
                f"{DECISION_M3_FRONT_CONTEXT_OBJECT_VERSION}"
            )
        run_id = str(payload.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("m3_front_context.run_id must be non-empty")
        source_run_id = str(payload.get("source_run_id") or "").strip()
        if not source_run_id:
            raise ValueError("m3_front_context.source_run_id must be non-empty")
        return cls(
            run_id=run_id,
            source_run_id=source_run_id,
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
    stock_code: str
    trade_date: str
    run_id: str
    source_run_id: str
    identify_status: str
    tracking_status: str
    entry_status: str
    entry_decision: str
    entry_actionable: bool
    entry_blocking_reasons: list[str]
    m1_blocked: bool
    m1_blocking_reasons: list[str]
    m2_cycle_record_id: str
    m2_cycle_state: str
    m2_state_stability_level: str
    artifact_sha256: str
    artifact_path: str
    ledger_path: str

    @classmethod
    def from_dict(cls, payload: Any) -> "DecisionM3FrontContextLedgerRecord":
        if not isinstance(payload, Mapping):
            raise TypeError("m3_front_context ledger root must be a JSON object")
        entry_actionable = payload.get("entry_actionable", False)
        if not isinstance(entry_actionable, bool):
            raise TypeError("m3_front_context.entry_actionable must be a boolean")
        m1_blocked = payload.get("m1_blocked", False)
        if not isinstance(m1_blocked, bool):
            raise TypeError("m3_front_context.m1_blocked must be a boolean")

        raw_entry_blocking_reasons = payload.get("entry_blocking_reasons")
        if raw_entry_blocking_reasons is None:
            entry_blocking_reasons: list[str] = []
        elif not isinstance(raw_entry_blocking_reasons, list):
            raise TypeError("m3_front_context.entry_blocking_reasons must be a list of strings")
        else:
            entry_blocking_reasons = []
            for item in raw_entry_blocking_reasons:
                if not isinstance(item, str):
                    raise TypeError("m3_front_context.entry_blocking_reasons must be a list of strings")
                normalized = item.strip()
                if not normalized:
                    raise ValueError("m3_front_context.entry_blocking_reasons must not contain empty strings")
                entry_blocking_reasons.append(normalized)

        raw_m1_blocking_reasons = payload.get("m1_blocking_reasons")
        if raw_m1_blocking_reasons is None:
            m1_blocking_reasons: list[str] = []
        elif not isinstance(raw_m1_blocking_reasons, list):
            raise TypeError("m3_front_context.m1_blocking_reasons must be a list of strings")
        else:
            m1_blocking_reasons = []
            for item in raw_m1_blocking_reasons:
                if not isinstance(item, str):
                    raise TypeError("m3_front_context.m1_blocking_reasons must be a list of strings")
                normalized = item.strip()
                if not normalized:
                    raise ValueError("m3_front_context.m1_blocking_reasons must not contain empty strings")
                m1_blocking_reasons.append(normalized)
        return cls(
            record_id=str(payload.get("record_id") or "").strip(),
            written_at=str(payload.get("written_at") or "").strip(),
            stock_code=str(payload.get("stock_code") or "").strip(),
            trade_date=str(payload.get("trade_date") or "").strip(),
            run_id=str(payload.get("run_id") or "").strip(),
            source_run_id=str(payload.get("source_run_id") or "").strip(),
            identify_status=str(payload.get("identify_status") or "").strip(),
            tracking_status=str(payload.get("tracking_status") or "").strip(),
            entry_status=str(payload.get("entry_status") or "").strip(),
            entry_decision=str(payload.get("entry_decision") or "").strip(),
            entry_actionable=entry_actionable,
            entry_blocking_reasons=entry_blocking_reasons,
            m1_blocked=m1_blocked,
            m1_blocking_reasons=m1_blocking_reasons,
            m2_cycle_record_id=str(payload.get("m2_cycle_record_id") or "").strip(),
            m2_cycle_state=str(payload.get("m2_cycle_state") or "").strip(),
            m2_state_stability_level=str(payload.get("m2_state_stability_level") or "").strip(),
            artifact_sha256=str(payload.get("artifact_sha256") or "").strip(),
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
            _dump_json(payload),
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
    identify_state = _copy_mapping(
        front_context.identify_state,
        field_name="m3_front_context.identify_state",
    )
    tracking_state = _copy_mapping(
        front_context.tracking_state,
        field_name="m3_front_context.tracking_state",
    )
    entry_state = _copy_mapping(
        front_context.entry_state,
        field_name="m3_front_context.entry_state",
    )
    stock_code = str(
        entry_state.get("stock_code")
        or tracking_state.get("stock_code")
        or identify_state.get("stock_code")
        or ""
    ).strip()
    trade_date = str(
        entry_state.get("trade_date")
        or tracking_state.get("trade_date")
        or identify_state.get("trade_date")
        or ""
    ).strip()
    identify_status = str(identify_state.get("status") or "").strip()
    tracking_status = str(tracking_state.get("status") or "").strip()
    entry_status = str(entry_state.get("status") or "").strip()
    entry_decision = str(entry_state.get("decision") or "").strip()
    entry_actionable = entry_state.get("actionable", False)
    if not isinstance(entry_actionable, bool):
        raise TypeError("m3_front_context.entry_state.actionable must be a boolean")
    raw_entry_blocking_reasons = entry_state.get("blocking_reasons")
    if raw_entry_blocking_reasons is None:
        entry_blocking_reasons: list[str] = []
    elif not isinstance(raw_entry_blocking_reasons, list):
        raise TypeError("m3_front_context.entry_state.blocking_reasons must be a list of strings")
    else:
        entry_blocking_reasons = []
        for item in raw_entry_blocking_reasons:
            if not isinstance(item, str):
                raise TypeError("m3_front_context.entry_state.blocking_reasons must be a list of strings")
            normalized = item.strip()
            if not normalized:
                raise ValueError("m3_front_context.entry_state.blocking_reasons must not contain empty strings")
            entry_blocking_reasons.append(normalized)

    m1_constraints_ref = _copy_mapping(
        front_context.m1_constraints_ref,
        field_name="m3_front_context.m1_constraints_ref",
    )
    m1_blocked = m1_constraints_ref.get("blocked", False)
    if not isinstance(m1_blocked, bool):
        raise TypeError("m3_front_context.m1_constraints_ref.blocked must be a boolean")
    raw_m1_blocking_reasons = m1_constraints_ref.get("blocking_reasons")
    if raw_m1_blocking_reasons is None:
        m1_blocking_reasons: list[str] = []
    elif not isinstance(raw_m1_blocking_reasons, list):
        raise TypeError("m3_front_context.m1_constraints_ref.blocking_reasons must be a list of strings")
    else:
        m1_blocking_reasons = []
        for item in raw_m1_blocking_reasons:
            if not isinstance(item, str):
                raise TypeError("m3_front_context.m1_constraints_ref.blocking_reasons must be a list of strings")
            normalized = item.strip()
            if not normalized:
                raise ValueError("m3_front_context.m1_constraints_ref.blocking_reasons must not contain empty strings")
            m1_blocking_reasons.append(normalized)

    raw_m2_cycle_ref = (
        entry_state.get("m2_cycle_ref")
        or tracking_state.get("m2_cycle_ref")
        or identify_state.get("m2_cycle_ref")
        or {}
    )
    m2_cycle_ref = _copy_mapping(
        raw_m2_cycle_ref,
        field_name="m3_front_context.m2_cycle_ref",
    )
    m2_cycle_record_id = str(m2_cycle_ref.get("record_id") or "").strip()
    if not m2_cycle_record_id and stock_code and trade_date:
        m2_cycle_record_id = f"{stock_code}-{trade_date}"
    m2_cycle_state = str(m2_cycle_ref.get("cycle_state") or "").strip()
    m2_state_stability_level = str(m2_cycle_ref.get("state_stability_level") or "").strip()

    artifact_payload = {
        **front_context.to_payload(),
        "record_id": record_id,
        "written_at": artifact_record.written_at,
    }
    artifact_text = _dump_json(artifact_payload)
    artifact_sha256 = _sha256_hex(artifact_text)
    payload = {
        "record_id": record_id,
        "written_at": artifact_record.written_at,
        "stock_code": stock_code,
        "trade_date": trade_date,
        "run_id": front_context.run_id,
        "source_run_id": front_context.source_run_id,
        "identify_status": identify_status,
        "tracking_status": tracking_status,
        "entry_status": entry_status,
        "entry_decision": entry_decision,
        "entry_actionable": entry_actionable,
        "entry_blocking_reasons": entry_blocking_reasons,
        "m1_blocked": m1_blocked,
        "m1_blocking_reasons": m1_blocking_reasons,
        "m2_cycle_record_id": m2_cycle_record_id,
        "m2_cycle_state": m2_cycle_state,
        "m2_state_stability_level": m2_state_stability_level,
        "artifact_sha256": artifact_sha256,
        "artifact_path": artifact_record.artifact_path,
        "ledger_path": str(ledger_file.relative_to(project_root_path)),
    }
    if not dry_run:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_file.write_text(
            _dump_json(payload),
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
    try:
        raw = artifact_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(
            f"failed to read m3_front_context artifact: {artifact_file}"
        ) from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON in m3_front_context artifact: {artifact_file}"
        ) from exc
    if not isinstance(payload, dict):
        raise TypeError(
            f"m3_front_context artifact root must be a JSON object: {artifact_file}"
        )
    return payload


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
    try:
        raw = ledger_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(
            f"failed to read m3_front_context ledger: {ledger_file}"
        ) from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON in m3_front_context ledger: {ledger_file}"
        ) from exc
    if not isinstance(payload, dict):
        raise TypeError(
            f"m3_front_context ledger root must be a JSON object: {ledger_file}"
        )
    record = DecisionM3FrontContextLedgerRecord.from_dict(payload)
    if not record.record_id:
        raise ValueError(f"m3_front_context ledger missing record_id: {ledger_file}")
    if not record.written_at:
        raise ValueError(f"m3_front_context ledger missing written_at: {ledger_file}")
    if not record.artifact_path:
        raise ValueError(f"m3_front_context ledger missing artifact_path: {ledger_file}")
    if not record.ledger_path:
        raise ValueError(f"m3_front_context ledger missing ledger_path: {ledger_file}")
    return record


def list_decision_m3_front_context_ledgers(
    *,
    project_root: str | Path,
    limit: int = 200,
) -> list[DecisionM3FrontContextLedgerRecord]:
    if limit <= 0:
        raise ValueError("limit must be a positive integer")
    root = Path(project_root) / "var/ledgers/m3_front_contexts"
    if not root.exists():
        return []

    records: list[DecisionM3FrontContextLedgerRecord] = []
    for ledger_file in root.glob("*/front_context.json"):
        try:
            raw = ledger_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(
                f"failed to read m3_front_context ledger: {ledger_file}"
            ) from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid JSON in m3_front_context ledger: {ledger_file}"
            ) from exc
        if not isinstance(payload, dict):
            raise TypeError(
                f"m3_front_context ledger root must be a JSON object: {ledger_file}"
            )
        try:
            record = DecisionM3FrontContextLedgerRecord.from_dict(payload)
        except Exception as exc:
            raise ValueError(
                f"invalid m3_front_context ledger payload: {ledger_file}"
            ) from exc
        if not record.record_id:
            raise ValueError(f"m3_front_context ledger missing record_id: {ledger_file}")
        if not record.written_at:
            raise ValueError(f"m3_front_context ledger missing written_at: {ledger_file}")
        if not record.artifact_path:
            raise ValueError(
                f"m3_front_context ledger missing artifact_path: {ledger_file}"
            )
        if not record.ledger_path:
            raise ValueError(
                f"m3_front_context ledger missing ledger_path: {ledger_file}"
            )
        records.append(record)

    records.sort(key=lambda item: (item.written_at, item.record_id), reverse=True)
    if len(records) > limit:
        records = records[:limit]
    return records
