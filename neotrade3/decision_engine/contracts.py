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
