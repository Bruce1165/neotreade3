"""Formal M3 assembly helpers for NeoTrade3 decision engine."""

from __future__ import annotations

from typing import Any, Mapping

from neotrade3.cycle_intelligence import SmallCycle
from neotrade3.data_control import (
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
)
from .contracts import EntryState, IdentifyState, TrackingState


def _require_text(value: object, *, field_name: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{field_name} must be a non-empty string")
    return raw


def _copy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    return {str(key): item for key, item in value.items()}


def _copy_text_list(value: list[str] | None) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _cycle_ref(cycle: SmallCycle) -> dict[str, Any]:
    return {
        "object_type": cycle.object_type,
        "object_version": cycle.object_version,
        "stock_code": cycle.stock_code,
        "trade_date": cycle.trade_date,
        "cycle_state": cycle.cycle_state,
        "state_stability_level": cycle.state_stability_level,
    }


def build_m1_constraints_ref(
    *,
    d1_fact: D1DailyPriceFact | None,
    security_master: D7SecurityMasterMinimal | None,
    trading_day_status: D7TradingDayStatus | None,
    trading_profile: PF1TradingProfile | None,
) -> dict[str, Any]:
    """Build a minimal formal M1 constraint snapshot for M3 translation."""

    price_fact_ready = d1_fact is not None
    security_ready = security_master is not None and not bool(security_master.is_delisted)
    trading_day_ready = trading_day_status is not None and trading_day_status.is_trading_day is True
    profile_window_ready = bool(
        trading_profile is not None
        and trading_profile.avg_amount_20d is not None
        and trading_profile.return_20d is not None
    )

    blocking_reasons: list[str] = []
    if not price_fact_ready:
        blocking_reasons.append("d1_fact_missing")
    if not security_ready:
        blocking_reasons.append("security_not_ready")
    if not trading_day_ready:
        blocking_reasons.append("target_date_not_trading_day")
    if not profile_window_ready:
        blocking_reasons.append("pf1_window_not_ready")

    return {
        "price_fact_ready": price_fact_ready,
        "security_ready": security_ready,
        "trading_day_ready": trading_day_ready,
        "profile_window_ready": profile_window_ready,
        "blocked": bool(blocking_reasons),
        "blocking_reasons": blocking_reasons,
    }


def build_identify_state_from_formal_inputs(
    *,
    cycle: SmallCycle,
    m1_constraints_ref: Mapping[str, Any],
) -> IdentifyState:
    """Translate a formal small-cycle into a formal identify-state."""

    blocked = bool(m1_constraints_ref.get("blocked"))
    identify_ready = cycle.cycle_state in {
        "S1 Emerging",
        "S2 Advancing",
        "S3 Maturing",
    }
    status = "identified" if identify_ready and not blocked else "not_identified"
    reason = (
        "m1_constraints_blocked"
        if blocked
        else "small_cycle_not_actionable"
        if not identify_ready
        else "small_cycle_enters_formal_watch_scope"
    )
    return build_identify_state(
        stock_code=cycle.stock_code,
        trade_date=cycle.trade_date,
        status=status,
        reason=reason,
        evidence_ref={
            "confidence_level": cycle.confidence.get("level"),
            "support_score": cycle.confidence.get("score"),
            "cycle_state": cycle.cycle_state,
        },
        m2_cycle_ref=_cycle_ref(cycle),
        m1_constraints_ref=m1_constraints_ref,
    )


def build_tracking_state_from_formal_inputs(
    *,
    cycle: SmallCycle,
    m1_constraints_ref: Mapping[str, Any],
) -> TrackingState:
    """Translate a formal small-cycle into a formal tracking-state."""

    blocked = bool(m1_constraints_ref.get("blocked"))
    if blocked or cycle.cycle_state in {"S0 Neutral", "S4 Exhausting_or_Invalidated"}:
        status = "not_tracking"
        maturity = "not_ready"
        transition_reason = (
            "m1_constraints_blocked"
            if blocked
            else "small_cycle_not_suitable_for_tracking"
        )
    elif cycle.cycle_state == "S1 Emerging":
        status = "tracking"
        maturity = "observe"
        transition_reason = "small_cycle_requires_more_confirmation"
    else:
        status = "tracking"
        maturity = "ready_for_entry"
        transition_reason = "small_cycle_supports_formal_action"

    return build_tracking_state(
        stock_code=cycle.stock_code,
        trade_date=cycle.trade_date,
        status=status,
        maturity=maturity,
        transition_reason=transition_reason,
        evidence_ref={
            "cycle_state": cycle.cycle_state,
            "state_stability_level": cycle.state_stability_level,
        },
        m2_cycle_ref=_cycle_ref(cycle),
        m1_constraints_ref=m1_constraints_ref,
    )


def build_entry_state_from_formal_inputs(
    *,
    cycle: SmallCycle,
    m1_constraints_ref: Mapping[str, Any],
) -> EntryState:
    """Translate a formal small-cycle into a formal entry-state."""

    blocked = bool(m1_constraints_ref.get("blocked"))
    blocking_reasons = _copy_text_list(list(m1_constraints_ref.get("blocking_reasons") or []))
    actionable = False
    status = "not_ready"
    decision = "wait"

    if blocked:
        status = "blocked"
    elif cycle.cycle_state in {"S2 Advancing", "S3 Maturing"}:
        actionable = True
        status = "ready"
        decision = "enter"
    elif cycle.cycle_state == "S1 Emerging":
        blocking_reasons.append("tracking_not_mature")
    else:
        blocking_reasons.append("small_cycle_not_actionable")

    return build_entry_state(
        stock_code=cycle.stock_code,
        trade_date=cycle.trade_date,
        status=status,
        decision=decision,
        actionable=actionable,
        blocking_reasons=blocking_reasons,
        evidence_ref={
            "cycle_state": cycle.cycle_state,
            "confidence_level": cycle.confidence.get("level"),
        },
        m2_cycle_ref=_cycle_ref(cycle),
        m1_constraints_ref=m1_constraints_ref,
    )


def build_identify_state(
    *,
    stock_code: str,
    trade_date: str,
    status: str,
    reason: str,
    evidence_ref: Mapping[str, Any] | None = None,
    m2_cycle_ref: Mapping[str, Any] | None = None,
    m1_constraints_ref: Mapping[str, Any] | None = None,
) -> IdentifyState:
    """Build a formal M3 identify-state object from already-decided inputs."""

    return IdentifyState(
        stock_code=_require_text(stock_code, field_name="stock_code"),
        trade_date=_require_text(trade_date, field_name="trade_date"),
        status=_require_text(status, field_name="status"),
        reason=_require_text(reason, field_name="reason"),
        evidence_ref=_copy_mapping(evidence_ref),
        m2_cycle_ref=_copy_mapping(m2_cycle_ref),
        m1_constraints_ref=_copy_mapping(m1_constraints_ref),
    )


def build_tracking_state(
    *,
    stock_code: str,
    trade_date: str,
    status: str,
    maturity: str,
    transition_reason: str,
    evidence_ref: Mapping[str, Any] | None = None,
    m2_cycle_ref: Mapping[str, Any] | None = None,
    m1_constraints_ref: Mapping[str, Any] | None = None,
) -> TrackingState:
    """Build a formal M3 tracking-state object from already-decided inputs."""

    return TrackingState(
        stock_code=_require_text(stock_code, field_name="stock_code"),
        trade_date=_require_text(trade_date, field_name="trade_date"),
        status=_require_text(status, field_name="status"),
        maturity=_require_text(maturity, field_name="maturity"),
        transition_reason=_require_text(
            transition_reason,
            field_name="transition_reason",
        ),
        evidence_ref=_copy_mapping(evidence_ref),
        m2_cycle_ref=_copy_mapping(m2_cycle_ref),
        m1_constraints_ref=_copy_mapping(m1_constraints_ref),
    )


def build_entry_state(
    *,
    stock_code: str,
    trade_date: str,
    status: str,
    decision: str,
    actionable: bool,
    blocking_reasons: list[str] | None = None,
    evidence_ref: Mapping[str, Any] | None = None,
    m2_cycle_ref: Mapping[str, Any] | None = None,
    m1_constraints_ref: Mapping[str, Any] | None = None,
) -> EntryState:
    """Build a formal M3 entry-state object from already-decided inputs."""

    return EntryState(
        stock_code=_require_text(stock_code, field_name="stock_code"),
        trade_date=_require_text(trade_date, field_name="trade_date"),
        status=_require_text(status, field_name="status"),
        decision=_require_text(decision, field_name="decision"),
        actionable=bool(actionable),
        blocking_reasons=_copy_text_list(blocking_reasons),
        evidence_ref=_copy_mapping(evidence_ref),
        m2_cycle_ref=_copy_mapping(m2_cycle_ref),
        m1_constraints_ref=_copy_mapping(m1_constraints_ref),
    )
