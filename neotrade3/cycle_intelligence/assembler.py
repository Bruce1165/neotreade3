"""Formal M2 assembly helpers for NeoTrade3 cycle intelligence."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from neotrade3.data_control import (
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
)
from .contracts import SmallCycle


DEFAULT_SMALL_CYCLE_INPUT_DATA_VERSION = "m1_phase1.v1"
DEFAULT_SMALL_CYCLE_RULE_VERSION = "m2_small_cycle.v1alpha1"


def _require_text(value: object, *, field_name: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{field_name} must be a non-empty string")
    return raw


def _copy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    return {str(key): item for key, item in value.items()}


def _copy_transition_log(value: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if value is None:
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            items.append({str(key): val for key, val in item.items()})
    return items


def _as_float(value: object) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_positive_days(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _trading_profile_window_ready(profile: PF1TradingProfile | None) -> bool:
    if profile is None:
        return False
    return (
        profile.avg_amount_20d is not None
        and profile.median_turnover_20d is not None
        and profile.return_20d is not None
    )


def build_small_cycle_from_m1(
    *,
    d1_fact: D1DailyPriceFact | None,
    security_master: D7SecurityMasterMinimal | None,
    trading_day_status: D7TradingDayStatus | None,
    trading_profile: PF1TradingProfile | None,
    input_data_version: str = DEFAULT_SMALL_CYCLE_INPUT_DATA_VERSION,
    rule_version: str = DEFAULT_SMALL_CYCLE_RULE_VERSION,
) -> SmallCycle:
    """Build a formal small-cycle object from formal M1 inputs only.

    The first production version intentionally stays conservative and only
    uses already-frozen M1 inputs plus thresholds that are already present in
    current compatibility logic.
    """

    if d1_fact is None:
        raise ValueError("d1_fact is required")
    if security_master is None:
        raise ValueError("security_master is required")
    if trading_day_status is None:
        raise ValueError("trading_day_status is required")

    latest_amount = _as_float(getattr(trading_profile, "latest_amount", None))
    avg_amount_20d = _as_float(getattr(trading_profile, "avg_amount_20d", None))
    avg_turnover_5d = _as_float(getattr(trading_profile, "avg_turnover_5d", None))
    median_turnover_20d = _as_float(getattr(trading_profile, "median_turnover_20d", None))
    return_20d = _as_float(getattr(trading_profile, "return_20d", None))
    avg_pct_change_5d = _as_float(getattr(trading_profile, "avg_pct_change_5d", None))
    positive_days_5d = _normalize_positive_days(
        getattr(trading_profile, "positive_days_5d", None)
    )
    latest_pct_change = _as_float(getattr(d1_fact, "pct_change", None))

    is_trading_day = trading_day_status.is_trading_day is True
    security_ready = not bool(security_master.is_delisted)
    data_ready = _trading_profile_window_ready(trading_profile)

    price_structure_support = bool(
        isinstance(latest_pct_change, float)
        and latest_pct_change > 0
        and (
            (isinstance(return_20d, float) and return_20d > 0)
            or (isinstance(avg_pct_change_5d, float) and avg_pct_change_5d > 0)
        )
    )
    activity_support = bool(
        (
            isinstance(latest_amount, float)
            and isinstance(avg_amount_20d, float)
            and avg_amount_20d > 0
            and latest_amount >= avg_amount_20d
        )
        or (
            isinstance(avg_turnover_5d, float)
            and isinstance(median_turnover_20d, float)
            and median_turnover_20d > 0
            and avg_turnover_5d >= median_turnover_20d
        )
    )
    continuity_support = bool(
        (isinstance(return_20d, float) and return_20d > 0)
        or ((positive_days_5d or 0) >= 3)
    )
    weakening = bool(
        isinstance(return_20d, float)
        and return_20d > 0
        and (
            (isinstance(latest_pct_change, float) and latest_pct_change <= 0)
            or (isinstance(avg_pct_change_5d, float) and avg_pct_change_5d <= 0)
        )
    )
    invalidated = bool(
        is_trading_day
        and security_ready
        and data_ready
        and isinstance(return_20d, float)
        and return_20d <= 0
        and ((positive_days_5d or 0) <= 1)
    )

    if not is_trading_day or not security_ready or not data_ready:
        cycle_state = "S0 Neutral"
        state_stability_level = "not_ready"
    elif invalidated:
        cycle_state = "S4 Exhausting_or_Invalidated"
        state_stability_level = "invalidated"
    elif price_structure_support and activity_support and continuity_support and not weakening:
        cycle_state = "S2 Advancing"
        state_stability_level = "stable"
    elif price_structure_support and continuity_support and weakening:
        cycle_state = "S3 Maturing"
        state_stability_level = "weakening"
    elif price_structure_support or activity_support or continuity_support:
        cycle_state = "S1 Emerging"
        state_stability_level = "watch"
    else:
        cycle_state = "S0 Neutral"
        state_stability_level = "insufficient_evidence"

    evidence_bundle = {
        "e1_price_structure": {
            "status": "supported" if price_structure_support else "insufficient",
            "latest_pct_change": latest_pct_change,
            "avg_pct_change_5d": avg_pct_change_5d,
            "return_20d": return_20d,
        },
        "e2_activity": {
            "status": "supported" if activity_support else "insufficient",
            "latest_amount": latest_amount,
            "avg_amount_20d": avg_amount_20d,
            "avg_turnover_5d": avg_turnover_5d,
            "median_turnover_20d": median_turnover_20d,
        },
        "e3_stability": {
            "status": "supported" if continuity_support else "insufficient",
            "positive_days_5d": positive_days_5d,
            "avg_pct_change_5d": avg_pct_change_5d,
            "weakening": weakening,
        },
        "e4_relative_strength": {
            "status": "not_available",
            "note": "首批正式 M1 未提供横截面对比输入，本项暂不进入主判定。",
        },
        "e5_tradeability": {
            "status": "supported" if (is_trading_day and security_ready and data_ready) else "blocked",
            "is_trading_day": trading_day_status.is_trading_day,
            "is_delisted": security_master.is_delisted,
            "calendar_source": trading_day_status.calendar_source,
            "profile_window_ready": data_ready,
        },
    }

    support_count = sum(
        1 for flag in (price_structure_support, activity_support, continuity_support) if flag
    )
    confidence = {
        "level": (
            "high"
            if cycle_state == "S2 Advancing"
            else "medium"
            if cycle_state in {"S1 Emerging", "S3 Maturing"}
            else "low"
        ),
        "score": support_count,
        "source_sufficiency": "ready" if data_ready else "partial",
        "direction_consistency": support_count,
        "time_continuity": positive_days_5d,
        "structure_stability": state_stability_level,
        "data_reliability": "ready" if (is_trading_day and security_ready) else "not_ready",
    }

    invalidation_reasons: list[str] = []
    invalidation_type = "not_triggered"
    if not is_trading_day:
        invalidation_reasons.append("target_date_not_trading_day")
        invalidation_type = "I4 数据可用性破坏"
    if not security_ready:
        invalidation_reasons.append("security_delisted")
        invalidation_type = "I4 数据可用性破坏"
    if not data_ready:
        invalidation_reasons.append("pf1_window_not_ready")
        invalidation_type = "I4 数据可用性破坏"
    if invalidated:
        invalidation_reasons.append("price_and_continuity_broken")
        invalidation_type = "I1 结构破坏"
    invalidation = {
        "status": "triggered" if invalidation_reasons else "not_triggered",
        "type": invalidation_type,
        "reasons": invalidation_reasons,
    }

    return build_small_cycle(
        stock_code=d1_fact.stock_code,
        trade_date=d1_fact.trade_date,
        cycle_state=cycle_state,
        state_stability_level=state_stability_level,
        evidence_bundle=evidence_bundle,
        confidence=confidence,
        invalidation=invalidation,
        state_transition_log=[
            {
                "from": "S0 Neutral",
                "to": cycle_state,
                "trigger": "formal_m1_snapshot",
            }
        ],
        input_data_version=input_data_version,
        rule_version=rule_version,
    )


def build_small_cycle(
    *,
    stock_code: str,
    trade_date: str,
    cycle_state: str,
    state_stability_level: str,
    evidence_bundle: Mapping[str, Any] | None = None,
    confidence: Mapping[str, Any] | None = None,
    invalidation: Mapping[str, Any] | None = None,
    state_transition_log: Iterable[Mapping[str, Any]] | None = None,
    input_data_version: str = DEFAULT_SMALL_CYCLE_INPUT_DATA_VERSION,
    rule_version: str = DEFAULT_SMALL_CYCLE_RULE_VERSION,
) -> SmallCycle:
    """Build a formal M2 small-cycle object from already-decided inputs.

    Phase `P2-A` only freezes the object boundary and builder entrypoint.
    Real production derivation from formal `M1` inputs lands in later phases.
    """

    return SmallCycle(
        stock_code=_require_text(stock_code, field_name="stock_code"),
        trade_date=_require_text(trade_date, field_name="trade_date"),
        cycle_state=_require_text(cycle_state, field_name="cycle_state"),
        state_stability_level=_require_text(
            state_stability_level,
            field_name="state_stability_level",
        ),
        evidence_bundle=_copy_mapping(evidence_bundle),
        confidence=_copy_mapping(confidence),
        invalidation=_copy_mapping(invalidation),
        state_transition_log=_copy_transition_log(state_transition_log),
        input_data_version=_require_text(
            input_data_version,
            field_name="input_data_version",
        ),
        rule_version=_require_text(rule_version, field_name="rule_version"),
    )
