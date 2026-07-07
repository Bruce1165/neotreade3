"""Formal M3 contract objects for NeoTrade3 decision engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


IDENTIFY_STATE_OBJECT_TYPE = "identify_state"
TRACKING_STATE_OBJECT_TYPE = "tracking_state"
ENTRY_STATE_OBJECT_TYPE = "entry_state"
M3_OBJECT_VERSION = 1


def _copy_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _copy_text_list(value: list[str] | None) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


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
