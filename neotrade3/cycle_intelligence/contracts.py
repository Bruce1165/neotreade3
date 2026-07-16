"""Formal M2 contract objects for NeoTrade3 cycle intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SMALL_CYCLE_OBJECT_TYPE = "small_cycle"
SMALL_CYCLE_OBJECT_VERSION = 2
MID_CYCLE_STATE_OBJECT_TYPE = "mid_cycle_state"
SMALL_CYCLE_WAVE_HYPOTHESIS_OBJECT_TYPE = "small_cycle_wave_hypothesis"
CYCLE_LINKAGE_STATE_OBJECT_TYPE = "cycle_linkage_state"
GROWTH_POTENTIAL_PROFILE_OBJECT_TYPE = "growth_potential_profile"
TOP_RISK_PROFILE_OBJECT_TYPE = "top_risk_profile"
SHADOW_OBJECT_VERSION = 1

SMALL_CYCLE_QUALITY_STATUS_OK = "ok"
SMALL_CYCLE_QUALITY_STATUS_BLOCKED = "blocked"
SMALL_CYCLE_QUALITY_STATUS_INVALIDATED = "invalidated"
SMALL_CYCLE_QUALITY_STATUS_INSUFFICIENT_EVIDENCE = "insufficient_evidence"

SMALL_CYCLE_QUALITY_REASON_TARGET_DATE_NOT_TRADING_DAY = "target_date_not_trading_day"
SMALL_CYCLE_QUALITY_REASON_SECURITY_DELISTED = "security_delisted"
SMALL_CYCLE_QUALITY_REASON_PF1_WINDOW_NOT_READY = "pf1_window_not_ready"
SMALL_CYCLE_QUALITY_REASON_PRICE_AND_CONTINUITY_BROKEN = "price_and_continuity_broken"
SMALL_CYCLE_QUALITY_REASON_INSUFFICIENT_EVIDENCE = "insufficient_evidence"

_SMALL_CYCLE_QUALITY_STATUS_ALLOWLIST = {
    SMALL_CYCLE_QUALITY_STATUS_OK,
    SMALL_CYCLE_QUALITY_STATUS_BLOCKED,
    SMALL_CYCLE_QUALITY_STATUS_INVALIDATED,
    SMALL_CYCLE_QUALITY_STATUS_INSUFFICIENT_EVIDENCE,
}
_SMALL_CYCLE_QUALITY_REASON_ALLOWLIST = {
    SMALL_CYCLE_QUALITY_REASON_TARGET_DATE_NOT_TRADING_DAY,
    SMALL_CYCLE_QUALITY_REASON_SECURITY_DELISTED,
    SMALL_CYCLE_QUALITY_REASON_PF1_WINDOW_NOT_READY,
    SMALL_CYCLE_QUALITY_REASON_PRICE_AND_CONTINUITY_BROKEN,
    SMALL_CYCLE_QUALITY_REASON_INSUFFICIENT_EVIDENCE,
}


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
    quality_status: str
    quality_reasons: list[str]
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
            "quality_status": self.quality_status,
            "quality_reasons": _copy_text_list(self.quality_reasons),
            "evidence_bundle": _copy_mapping(self.evidence_bundle),
            "confidence": _copy_mapping(self.confidence),
            "invalidation": _copy_mapping(self.invalidation),
            "state_transition_log": _copy_mapping_list(self.state_transition_log),
            "input_data_version": self.input_data_version,
            "rule_version": self.rule_version,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "SmallCycle":
        if not isinstance(payload, dict):
            raise TypeError("small_cycle must be a JSON object")
        object_type = str(payload.get("object_type") or "").strip()
        object_version = int(payload.get("object_version", -1))
        if object_type != SMALL_CYCLE_OBJECT_TYPE:
            raise ValueError("small_cycle.object_type must be small_cycle")
        if object_version != SMALL_CYCLE_OBJECT_VERSION:
            raise ValueError(
                f"small_cycle.object_version must be {SMALL_CYCLE_OBJECT_VERSION}"
            )
        stock_code = str(payload.get("stock_code") or "").strip()
        trade_date = str(payload.get("trade_date") or "").strip()
        cycle_state = str(payload.get("cycle_state") or "").strip()
        state_stability_level = str(payload.get("state_stability_level") or "").strip()
        quality_status = str(payload.get("quality_status") or "").strip()
        quality_reasons = _copy_text_list(payload.get("quality_reasons"))
        input_data_version = str(payload.get("input_data_version") or "").strip()
        rule_version = str(payload.get("rule_version") or "").strip()
        if not stock_code:
            raise ValueError("small_cycle.stock_code must be non-empty")
        if not trade_date:
            raise ValueError("small_cycle.trade_date must be non-empty")
        if not cycle_state:
            raise ValueError("small_cycle.cycle_state must be non-empty")
        if not state_stability_level:
            raise ValueError("small_cycle.state_stability_level must be non-empty")
        if not quality_status:
            raise ValueError("small_cycle.quality_status must be non-empty")
        if quality_status not in _SMALL_CYCLE_QUALITY_STATUS_ALLOWLIST:
            raise ValueError(
                f"small_cycle.quality_status must be one of "
                f"{sorted(_SMALL_CYCLE_QUALITY_STATUS_ALLOWLIST)}"
            )
        if any(reason not in _SMALL_CYCLE_QUALITY_REASON_ALLOWLIST for reason in quality_reasons):
            raise ValueError(
                f"small_cycle.quality_reasons must be within "
                f"{sorted(_SMALL_CYCLE_QUALITY_REASON_ALLOWLIST)}"
            )
        if quality_status != SMALL_CYCLE_QUALITY_STATUS_OK and not quality_reasons:
            raise ValueError(
                "small_cycle.quality_reasons must be non-empty "
                "when quality_status is not ok"
            )
        if not input_data_version:
            raise ValueError("small_cycle.input_data_version must be non-empty")
        if not rule_version:
            raise ValueError("small_cycle.rule_version must be non-empty")
        return cls(
            stock_code=stock_code,
            trade_date=trade_date,
            cycle_state=cycle_state,
            state_stability_level=state_stability_level,
            quality_status=quality_status,
            quality_reasons=quality_reasons,
            evidence_bundle=_copy_mapping(payload.get("evidence_bundle")),
            confidence=_copy_mapping(payload.get("confidence")),
            invalidation=_copy_mapping(payload.get("invalidation")),
            state_transition_log=_copy_mapping_list(payload.get("state_transition_log")),
            input_data_version=input_data_version,
            rule_version=rule_version,
            object_type=object_type,
            object_version=object_version,
        )


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
