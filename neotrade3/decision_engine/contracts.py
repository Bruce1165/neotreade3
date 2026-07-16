"""Formal M3 contract objects for NeoTrade3 decision engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


IDENTIFY_STATE_OBJECT_TYPE = "identify_state"
TRACKING_STATE_OBJECT_TYPE = "tracking_state"
ENTRY_STATE_OBJECT_TYPE = "entry_state"
HOLD_STATE_OBJECT_TYPE = "hold_state"
EXIT_STATE_OBJECT_TYPE = "exit_state"
DECISION_LIFECYCLE_EVENT_OBJECT_TYPE = "decision_lifecycle_event"
DECISION_LIFECYCLE_LOG_OBJECT_TYPE = "decision_lifecycle_log"
M3_OBJECT_VERSION = 1


def _copy_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _copy_text_list(value: list[str] | None) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _copy_payload_list(value: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_copy_mapping(item) for item in value if isinstance(item, dict)]


def _require_json_object(payload: Any, *, object_name: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError(f"{object_name} must be a JSON object")
    return payload


def _reject_unknown_fields(
    payload: dict[str, Any],
    *,
    allowed_keys: set[str],
    object_name: str,
) -> None:
    unknown = sorted(str(key) for key in payload.keys() if str(key) not in allowed_keys)
    if unknown:
        raise ValueError(f"{object_name} contains unknown fields: {unknown}")


def _require_non_empty_str(payload: dict[str, Any], *, field_name: str, object_name: str) -> str:
    value = str(payload.get(field_name) or "").strip()
    if not value:
        raise ValueError(f"{object_name}.{field_name} must be non-empty")
    return value


def _require_object_header(
    payload: dict[str, Any],
    *,
    object_type: str,
    object_version: int,
    object_name: str,
) -> None:
    if "object_type" not in payload:
        raise ValueError(f"{object_name}.object_type must be non-empty")
    if "object_version" not in payload:
        raise ValueError(f"{object_name}.object_version must be {object_version}")
    actual_type = str(payload.get("object_type") or "").strip()
    if actual_type != object_type:
        raise ValueError(f"{object_name}.object_type must be {object_type}")
    try:
        actual_version = int(payload.get("object_version", -1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{object_name}.object_version must be {object_version}") from exc
    if actual_version != object_version:
        raise ValueError(f"{object_name}.object_version must be {object_version}")


def _require_mapping(payload: dict[str, Any], *, field_name: str, object_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"{object_name}.{field_name} must be a JSON object")
    return dict(value)


def _require_bool(payload: dict[str, Any], *, field_name: str, object_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{object_name}.{field_name} must be a boolean")
    return value


def _require_str_list(payload: dict[str, Any], *, field_name: str, object_name: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{object_name}.{field_name} must be a list of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{object_name}.{field_name} must be a list of strings")
        normalized = item.strip()
        if not normalized:
            raise ValueError(f"{object_name}.{field_name} must not contain empty strings")
        out.append(normalized)
    return out


@dataclass(frozen=True)
class IdentifyState:
    """Formal M3 identify-state object skeleton."""

    stock_code: str
    trade_date: str
    status: str
    reason: str
    evidence_ref: dict[str, Any]
    m2_cycle_ref: dict[str, Any]
    m1_constraints_ref: dict[str, Any]
    object_type: str = IDENTIFY_STATE_OBJECT_TYPE
    object_version: int = M3_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "status": self.status,
            "reason": self.reason,
            "evidence_ref": _copy_mapping(self.evidence_ref),
            "m2_cycle_ref": _copy_mapping(self.m2_cycle_ref),
            "m1_constraints_ref": _copy_mapping(self.m1_constraints_ref),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "IdentifyState":
        obj = _require_json_object(payload, object_name="identify_state")
        allowed = {
            "object_type",
            "object_version",
            "stock_code",
            "trade_date",
            "status",
            "reason",
            "evidence_ref",
            "m2_cycle_ref",
            "m1_constraints_ref",
        }
        _reject_unknown_fields(obj, allowed_keys=allowed, object_name="identify_state")
        _require_object_header(
            obj,
            object_type=IDENTIFY_STATE_OBJECT_TYPE,
            object_version=M3_OBJECT_VERSION,
            object_name="identify_state",
        )
        return cls(
            stock_code=_require_non_empty_str(obj, field_name="stock_code", object_name="identify_state"),
            trade_date=_require_non_empty_str(obj, field_name="trade_date", object_name="identify_state"),
            status=_require_non_empty_str(obj, field_name="status", object_name="identify_state"),
            reason=_require_non_empty_str(obj, field_name="reason", object_name="identify_state"),
            evidence_ref=_require_mapping(obj, field_name="evidence_ref", object_name="identify_state"),
            m2_cycle_ref=_require_mapping(obj, field_name="m2_cycle_ref", object_name="identify_state"),
            m1_constraints_ref=_require_mapping(obj, field_name="m1_constraints_ref", object_name="identify_state"),
            object_type=IDENTIFY_STATE_OBJECT_TYPE,
            object_version=M3_OBJECT_VERSION,
        )


@dataclass(frozen=True)
class TrackingState:
    """Formal M3 tracking-state object skeleton."""

    stock_code: str
    trade_date: str
    status: str
    maturity: str
    transition_reason: str
    evidence_ref: dict[str, Any]
    m2_cycle_ref: dict[str, Any]
    m1_constraints_ref: dict[str, Any]
    object_type: str = TRACKING_STATE_OBJECT_TYPE
    object_version: int = M3_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "status": self.status,
            "maturity": self.maturity,
            "transition_reason": self.transition_reason,
            "evidence_ref": _copy_mapping(self.evidence_ref),
            "m2_cycle_ref": _copy_mapping(self.m2_cycle_ref),
            "m1_constraints_ref": _copy_mapping(self.m1_constraints_ref),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "TrackingState":
        obj = _require_json_object(payload, object_name="tracking_state")
        allowed = {
            "object_type",
            "object_version",
            "stock_code",
            "trade_date",
            "status",
            "maturity",
            "transition_reason",
            "evidence_ref",
            "m2_cycle_ref",
            "m1_constraints_ref",
        }
        _reject_unknown_fields(obj, allowed_keys=allowed, object_name="tracking_state")
        _require_object_header(
            obj,
            object_type=TRACKING_STATE_OBJECT_TYPE,
            object_version=M3_OBJECT_VERSION,
            object_name="tracking_state",
        )
        return cls(
            stock_code=_require_non_empty_str(obj, field_name="stock_code", object_name="tracking_state"),
            trade_date=_require_non_empty_str(obj, field_name="trade_date", object_name="tracking_state"),
            status=_require_non_empty_str(obj, field_name="status", object_name="tracking_state"),
            maturity=_require_non_empty_str(obj, field_name="maturity", object_name="tracking_state"),
            transition_reason=_require_non_empty_str(obj, field_name="transition_reason", object_name="tracking_state"),
            evidence_ref=_require_mapping(obj, field_name="evidence_ref", object_name="tracking_state"),
            m2_cycle_ref=_require_mapping(obj, field_name="m2_cycle_ref", object_name="tracking_state"),
            m1_constraints_ref=_require_mapping(obj, field_name="m1_constraints_ref", object_name="tracking_state"),
            object_type=TRACKING_STATE_OBJECT_TYPE,
            object_version=M3_OBJECT_VERSION,
        )


@dataclass(frozen=True)
class EntryState:
    """Formal M3 entry-state object skeleton."""

    stock_code: str
    trade_date: str
    status: str
    decision: str
    actionable: bool
    blocking_reasons: list[str]
    evidence_ref: dict[str, Any]
    m2_cycle_ref: dict[str, Any]
    m1_constraints_ref: dict[str, Any]
    object_type: str = ENTRY_STATE_OBJECT_TYPE
    object_version: int = M3_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "status": self.status,
            "decision": self.decision,
            "actionable": self.actionable,
            "blocking_reasons": _copy_text_list(self.blocking_reasons),
            "evidence_ref": _copy_mapping(self.evidence_ref),
            "m2_cycle_ref": _copy_mapping(self.m2_cycle_ref),
            "m1_constraints_ref": _copy_mapping(self.m1_constraints_ref),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "EntryState":
        obj = _require_json_object(payload, object_name="entry_state")
        allowed = {
            "object_type",
            "object_version",
            "stock_code",
            "trade_date",
            "status",
            "decision",
            "actionable",
            "blocking_reasons",
            "evidence_ref",
            "m2_cycle_ref",
            "m1_constraints_ref",
        }
        _reject_unknown_fields(obj, allowed_keys=allowed, object_name="entry_state")
        _require_object_header(
            obj,
            object_type=ENTRY_STATE_OBJECT_TYPE,
            object_version=M3_OBJECT_VERSION,
            object_name="entry_state",
        )
        return cls(
            stock_code=_require_non_empty_str(obj, field_name="stock_code", object_name="entry_state"),
            trade_date=_require_non_empty_str(obj, field_name="trade_date", object_name="entry_state"),
            status=_require_non_empty_str(obj, field_name="status", object_name="entry_state"),
            decision=_require_non_empty_str(obj, field_name="decision", object_name="entry_state"),
            actionable=_require_bool(obj, field_name="actionable", object_name="entry_state"),
            blocking_reasons=_require_str_list(obj, field_name="blocking_reasons", object_name="entry_state"),
            evidence_ref=_require_mapping(obj, field_name="evidence_ref", object_name="entry_state"),
            m2_cycle_ref=_require_mapping(obj, field_name="m2_cycle_ref", object_name="entry_state"),
            m1_constraints_ref=_require_mapping(obj, field_name="m1_constraints_ref", object_name="entry_state"),
            object_type=ENTRY_STATE_OBJECT_TYPE,
            object_version=M3_OBJECT_VERSION,
        )


@dataclass(frozen=True)
class HoldState:
    """Formal M3 hold-state object skeleton."""

    stock_code: str
    trade_date: str
    status: str
    hold_state: str
    warning_flags: list[str]
    not_exit_reasons: list[str]
    evidence_ref: dict[str, Any]
    m2_cycle_ref: dict[str, Any]
    m1_constraints_ref: dict[str, Any]
    object_type: str = HOLD_STATE_OBJECT_TYPE
    object_version: int = M3_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "status": self.status,
            "hold_state": self.hold_state,
            "warning_flags": _copy_text_list(self.warning_flags),
            "not_exit_reasons": _copy_text_list(self.not_exit_reasons),
            "evidence_ref": _copy_mapping(self.evidence_ref),
            "m2_cycle_ref": _copy_mapping(self.m2_cycle_ref),
            "m1_constraints_ref": _copy_mapping(self.m1_constraints_ref),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "HoldState":
        obj = _require_json_object(payload, object_name="hold_state")
        allowed = {
            "object_type",
            "object_version",
            "stock_code",
            "trade_date",
            "status",
            "hold_state",
            "warning_flags",
            "not_exit_reasons",
            "evidence_ref",
            "m2_cycle_ref",
            "m1_constraints_ref",
        }
        _reject_unknown_fields(obj, allowed_keys=allowed, object_name="hold_state")
        _require_object_header(
            obj,
            object_type=HOLD_STATE_OBJECT_TYPE,
            object_version=M3_OBJECT_VERSION,
            object_name="hold_state",
        )
        return cls(
            stock_code=_require_non_empty_str(obj, field_name="stock_code", object_name="hold_state"),
            trade_date=_require_non_empty_str(obj, field_name="trade_date", object_name="hold_state"),
            status=_require_non_empty_str(obj, field_name="status", object_name="hold_state"),
            hold_state=_require_non_empty_str(obj, field_name="hold_state", object_name="hold_state"),
            warning_flags=_require_str_list(obj, field_name="warning_flags", object_name="hold_state"),
            not_exit_reasons=_require_str_list(obj, field_name="not_exit_reasons", object_name="hold_state"),
            evidence_ref=_require_mapping(obj, field_name="evidence_ref", object_name="hold_state"),
            m2_cycle_ref=_require_mapping(obj, field_name="m2_cycle_ref", object_name="hold_state"),
            m1_constraints_ref=_require_mapping(obj, field_name="m1_constraints_ref", object_name="hold_state"),
            object_type=HOLD_STATE_OBJECT_TYPE,
            object_version=M3_OBJECT_VERSION,
        )


@dataclass(frozen=True)
class ExitState:
    """Formal M3 exit-state object skeleton."""

    stock_code: str
    trade_date: str
    status: str
    exit_ready: bool
    exit_scope: str
    exit_reason_type: str
    exit_attribution_bucket: str
    local_exit_semantics: str
    global_thesis_end_semantics: str
    evidence_ref: dict[str, Any]
    m2_cycle_ref: dict[str, Any]
    m1_constraints_ref: dict[str, Any]
    object_type: str = EXIT_STATE_OBJECT_TYPE
    object_version: int = M3_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "status": self.status,
            "exit_ready": self.exit_ready,
            "exit_scope": self.exit_scope,
            "exit_reason_type": self.exit_reason_type,
            "exit_attribution_bucket": self.exit_attribution_bucket,
            "local_exit_semantics": self.local_exit_semantics,
            "global_thesis_end_semantics": self.global_thesis_end_semantics,
            "evidence_ref": _copy_mapping(self.evidence_ref),
            "m2_cycle_ref": _copy_mapping(self.m2_cycle_ref),
            "m1_constraints_ref": _copy_mapping(self.m1_constraints_ref),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "ExitState":
        obj = _require_json_object(payload, object_name="exit_state")
        allowed = {
            "object_type",
            "object_version",
            "stock_code",
            "trade_date",
            "status",
            "exit_ready",
            "exit_scope",
            "exit_reason_type",
            "exit_attribution_bucket",
            "local_exit_semantics",
            "global_thesis_end_semantics",
            "evidence_ref",
            "m2_cycle_ref",
            "m1_constraints_ref",
        }
        _reject_unknown_fields(obj, allowed_keys=allowed, object_name="exit_state")
        _require_object_header(
            obj,
            object_type=EXIT_STATE_OBJECT_TYPE,
            object_version=M3_OBJECT_VERSION,
            object_name="exit_state",
        )
        return cls(
            stock_code=_require_non_empty_str(obj, field_name="stock_code", object_name="exit_state"),
            trade_date=_require_non_empty_str(obj, field_name="trade_date", object_name="exit_state"),
            status=_require_non_empty_str(obj, field_name="status", object_name="exit_state"),
            exit_ready=_require_bool(obj, field_name="exit_ready", object_name="exit_state"),
            exit_scope=_require_non_empty_str(obj, field_name="exit_scope", object_name="exit_state"),
            exit_reason_type=_require_non_empty_str(obj, field_name="exit_reason_type", object_name="exit_state"),
            exit_attribution_bucket=_require_non_empty_str(
                obj, field_name="exit_attribution_bucket", object_name="exit_state"
            ),
            local_exit_semantics=_require_non_empty_str(obj, field_name="local_exit_semantics", object_name="exit_state"),
            global_thesis_end_semantics=_require_non_empty_str(
                obj, field_name="global_thesis_end_semantics", object_name="exit_state"
            ),
            evidence_ref=_require_mapping(obj, field_name="evidence_ref", object_name="exit_state"),
            m2_cycle_ref=_require_mapping(obj, field_name="m2_cycle_ref", object_name="exit_state"),
            m1_constraints_ref=_require_mapping(obj, field_name="m1_constraints_ref", object_name="exit_state"),
            object_type=EXIT_STATE_OBJECT_TYPE,
            object_version=M3_OBJECT_VERSION,
        )

@dataclass(frozen=True)
class DecisionLifecycleEvent:
    """Formal M3 decision-lifecycle event object skeleton."""

    stock_code: str
    trade_date: str
    event: str
    source_layer: str
    stage: str
    decision: str
    exit_scope: str
    details: str
    position_contract_snapshot: dict[str, Any]
    evidence_ref: dict[str, Any]
    object_type: str = DECISION_LIFECYCLE_EVENT_OBJECT_TYPE
    object_version: int = M3_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "event": self.event,
            "source_layer": self.source_layer,
            "stage": self.stage,
            "decision": self.decision,
            "exit_scope": self.exit_scope,
            "details": self.details,
            "position_contract_snapshot": _copy_mapping(self.position_contract_snapshot),
            "evidence_ref": _copy_mapping(self.evidence_ref),
        }


@dataclass(frozen=True)
class DecisionLifecycleLog:
    """Formal M3 per-stock decision-lifecycle log object skeleton."""

    stock_code: str
    events: list[dict[str, Any]]
    object_type: str = DECISION_LIFECYCLE_LOG_OBJECT_TYPE
    object_version: int = M3_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "events": _copy_payload_list(self.events),
        }
