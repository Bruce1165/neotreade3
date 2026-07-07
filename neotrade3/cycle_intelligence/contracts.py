"""Formal M2 contract objects for NeoTrade3 cycle intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SMALL_CYCLE_OBJECT_TYPE = "small_cycle"
SMALL_CYCLE_OBJECT_VERSION = 1


def _copy_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _copy_mapping_list(value: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


@dataclass(frozen=True)
class SmallCycle:
    """Formal M2 small-cycle object skeleton."""

    stock_code: str
    trade_date: str
    cycle_state: str
    state_stability_level: str
    evidence_bundle: dict[str, Any]
    confidence: dict[str, Any]
    invalidation: dict[str, Any]
    state_transition_log: list[dict[str, Any]]
    input_data_version: str
    rule_version: str
    object_type: str = SMALL_CYCLE_OBJECT_TYPE
    object_version: int = SMALL_CYCLE_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "cycle_state": self.cycle_state,
            "state_stability_level": self.state_stability_level,
            "evidence_bundle": _copy_mapping(self.evidence_bundle),
            "confidence": _copy_mapping(self.confidence),
            "invalidation": _copy_mapping(self.invalidation),
            "state_transition_log": _copy_mapping_list(self.state_transition_log),
            "input_data_version": self.input_data_version,
            "rule_version": self.rule_version,
        }
