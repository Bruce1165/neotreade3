"""Formal M2 contract objects for NeoTrade3 cycle intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SMALL_CYCLE_OBJECT_TYPE = "small_cycle"
SMALL_CYCLE_OBJECT_VERSION = 1
MID_CYCLE_STATE_OBJECT_TYPE = "mid_cycle_state"
SMALL_CYCLE_WAVE_HYPOTHESIS_OBJECT_TYPE = "small_cycle_wave_hypothesis"
CYCLE_LINKAGE_STATE_OBJECT_TYPE = "cycle_linkage_state"
GROWTH_POTENTIAL_PROFILE_OBJECT_TYPE = "growth_potential_profile"
TOP_RISK_PROFILE_OBJECT_TYPE = "top_risk_profile"
SHADOW_OBJECT_VERSION = 1


def _copy_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _copy_mapping_list(value: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _copy_text_list(value: list[str] | None) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


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


@dataclass(frozen=True)
class MidCycleState:
    """Minimal M2 shadow mid-cycle state object."""

    stock_code: str
    trade_date: str
    scope: str
    state: str
    confidence: dict[str, Any]
    evidence_bundle: dict[str, Any]
    rule_version: str
    object_type: str = MID_CYCLE_STATE_OBJECT_TYPE
    object_version: int = SHADOW_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "scope": self.scope,
            "state": self.state,
            "confidence": _copy_mapping(self.confidence),
            "evidence_bundle": _copy_mapping(self.evidence_bundle),
            "rule_version": self.rule_version,
        }


@dataclass(frozen=True)
class SmallCycleWaveHypothesis:
    """Minimal M2 shadow wave hypothesis object."""

    stock_code: str
    trade_date: str
    replay_consistency_status: str
    wave_label_candidate: str
    evidence_bundle: dict[str, Any]
    rule_version: str
    object_type: str = SMALL_CYCLE_WAVE_HYPOTHESIS_OBJECT_TYPE
    object_version: int = SHADOW_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "replay_consistency_status": self.replay_consistency_status,
            "wave_label_candidate": self.wave_label_candidate,
            "evidence_bundle": _copy_mapping(self.evidence_bundle),
            "rule_version": self.rule_version,
        }


@dataclass(frozen=True)
class CycleLinkageState:
    """Minimal M2 shadow cycle-linkage object."""

    stock_code: str
    trade_date: str
    small_cycle_ref: dict[str, Any]
    mid_cycle_ref: dict[str, Any]
    linkage_phase: str
    supports_continuation: bool
    local_end_vs_global_end: str
    confidence: dict[str, Any]
    evidence_bundle: dict[str, Any]
    rule_version: str
    object_type: str = CYCLE_LINKAGE_STATE_OBJECT_TYPE
    object_version: int = SHADOW_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "small_cycle_ref": _copy_mapping(self.small_cycle_ref),
            "mid_cycle_ref": _copy_mapping(self.mid_cycle_ref),
            "linkage_phase": self.linkage_phase,
            "supports_continuation": self.supports_continuation,
            "local_end_vs_global_end": self.local_end_vs_global_end,
            "confidence": _copy_mapping(self.confidence),
            "evidence_bundle": _copy_mapping(self.evidence_bundle),
            "rule_version": self.rule_version,
        }


@dataclass(frozen=True)
class GrowthPotentialProfile:
    """Minimal M2 shadow growth-potential object."""

    stock_code: str
    trade_date: str
    status: str
    confidence: dict[str, Any]
    evidence_bundle: dict[str, Any]
    rule_version: str
    object_type: str = GROWTH_POTENTIAL_PROFILE_OBJECT_TYPE
    object_version: int = SHADOW_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "status": self.status,
            "confidence": _copy_mapping(self.confidence),
            "evidence_bundle": _copy_mapping(self.evidence_bundle),
            "rule_version": self.rule_version,
        }


@dataclass(frozen=True)
class TopRiskProfile:
    """Minimal M2 shadow top-risk object."""

    stock_code: str
    trade_date: str
    risk_level: str
    risk_flags: list[str]
    evidence_bundle: dict[str, Any]
    rule_version: str
    object_type: str = TOP_RISK_PROFILE_OBJECT_TYPE
    object_version: int = SHADOW_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "risk_level": self.risk_level,
            "risk_flags": _copy_text_list(self.risk_flags),
            "evidence_bundle": _copy_mapping(self.evidence_bundle),
            "rule_version": self.rule_version,
        }
