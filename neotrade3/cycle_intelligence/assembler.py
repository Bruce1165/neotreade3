"""Formal M2 assembly helpers for NeoTrade3 cycle intelligence."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from neotrade3.data_control import (
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
)
from .contracts import (
    CycleLinkageState,
    GrowthPotentialProfile,
    MidCycleState,
    SmallCycle,
    SmallCycleWaveHypothesis,
    TopRiskProfile,
)


DEFAULT_SMALL_CYCLE_INPUT_DATA_VERSION = "m1_phase1.v1"
DEFAULT_SMALL_CYCLE_RULE_VERSION = "m2_small_cycle.v1alpha1"
DEFAULT_MID_CYCLE_RULE_VERSION = "m2_mid_cycle_shadow.v1alpha1"
DEFAULT_WAVE_HYPOTHESIS_RULE_VERSION = "m2_wave_hypothesis_shadow.v1alpha1"
DEFAULT_CYCLE_LINKAGE_RULE_VERSION = "m2_cycle_linkage.v1alpha1"
DEFAULT_GROWTH_POTENTIAL_RULE_VERSION = "m2_growth_potential_shadow.v1alpha1"
DEFAULT_TOP_RISK_RULE_VERSION = "m2_top_risk_shadow.v1alpha1"


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


def _copy_text_list(value: Iterable[object] | None) -> list[str]:
    if value is None:
        return []
    result: list[str] = []
    for item in value:
        normalized = str(item).strip()
        if normalized:
            result.append(normalized)
    return result


def _build_mid_cycle_state_value(
    *,
    cycle_state: str,
    return_20d: float | None,
    positive_days_5d: int | None,
) -> str:
    if cycle_state == "S2 Advancing" and isinstance(return_20d, float) and return_20d > 0:
        return "advancing"
    if isinstance(return_20d, float) and return_20d < 0:
        return "weakening"
    if isinstance(positive_days_5d, int) and positive_days_5d <= 2:
        return "weakening"
    if isinstance(return_20d, float) and return_20d >= 0:
        return "repairing"
    return "neutral"


def _build_risk_level(
    *,
    return_20d: float | None,
    positive_days_5d: int | None,
) -> str:
    if (isinstance(return_20d, float) and return_20d < 0) or (
        isinstance(positive_days_5d, int) and positive_days_5d <= 1
    ):
        return "high"
    if isinstance(positive_days_5d, int) and positive_days_5d <= 3:
        return "watch"
    return "low"


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


def build_mid_cycle_states_from_m1(
    *,
    cycle: SmallCycle,
    security_master: D7SecurityMasterMinimal | None,
    trading_profile: PF1TradingProfile | None,
    rule_version: str = DEFAULT_MID_CYCLE_RULE_VERSION,
) -> dict[str, MidCycleState]:
    """Build the minimal shadow mid-cycle states needed by current M4 consumers."""

    return_20d = _as_float(getattr(trading_profile, "return_20d", None))
    positive_days_5d = _normalize_positive_days(
        getattr(trading_profile, "positive_days_5d", None)
    )
    sector_lv1 = str(getattr(security_master, "sector_lv1", "") or "").strip()
    sector_lv2 = str(getattr(security_master, "sector_lv2", "") or "").strip()
    fund_state = _build_mid_cycle_state_value(
        cycle_state=cycle.cycle_state,
        return_20d=return_20d,
        positive_days_5d=positive_days_5d,
    )
    industry_state = _build_mid_cycle_state_value(
        cycle_state=cycle.cycle_state,
        return_20d=return_20d,
        positive_days_5d=positive_days_5d,
    )
    confidence = {
        "level": "medium" if fund_state in {"advancing", "repairing"} else "low",
        "return_20d": return_20d,
        "positive_days_5d": positive_days_5d,
    }

    return {
        "fund_cycle": MidCycleState(
            stock_code=cycle.stock_code,
            trade_date=cycle.trade_date,
            scope="fund_cycle",
            state=fund_state,
            confidence=confidence,
            evidence_bundle={
                "small_cycle_state": cycle.cycle_state,
                "sector_lv1": sector_lv1,
                "source": "small_cycle_plus_pf1",
            },
            rule_version=rule_version,
        ),
        "industry_cycle": MidCycleState(
            stock_code=cycle.stock_code,
            trade_date=cycle.trade_date,
            scope="industry_cycle",
            state=industry_state,
            confidence=confidence,
            evidence_bundle={
                "small_cycle_state": cycle.cycle_state,
                "sector_lv2": sector_lv2,
                "source": "small_cycle_plus_pf1",
            },
            rule_version=rule_version,
        ),
    }


def build_small_cycle_wave_hypothesis_from_formal_inputs(
    *,
    cycle: SmallCycle,
    rule_version: str = DEFAULT_WAVE_HYPOTHESIS_RULE_VERSION,
) -> SmallCycleWaveHypothesis:
    """Build the minimal shadow wave hypothesis used by M4 benchmark."""

    return SmallCycleWaveHypothesis(
        stock_code=cycle.stock_code,
        trade_date=cycle.trade_date,
        replay_consistency_status="pending_benchmark",
        wave_label_candidate=(
            "advance_wave" if cycle.cycle_state == "S2 Advancing" else "unclassified_wave"
        ),
        evidence_bundle={
            "small_cycle_state": cycle.cycle_state,
            "state_stability_level": cycle.state_stability_level,
        },
        rule_version=rule_version,
    )


def build_cycle_linkage_state(
    *,
    stock_code: str,
    trade_date: str,
    small_cycle_ref: Mapping[str, Any] | None,
    mid_cycle_ref: Mapping[str, Any] | None,
    linkage_phase: str,
    supports_continuation: bool,
    local_end_vs_global_end: str,
    confidence: Mapping[str, Any] | None = None,
    evidence_bundle: Mapping[str, Any] | None = None,
    rule_version: str = DEFAULT_CYCLE_LINKAGE_RULE_VERSION,
) -> CycleLinkageState:
    """Build the minimal shadow cycle linkage object."""

    return CycleLinkageState(
        stock_code=_require_text(stock_code, field_name="stock_code"),
        trade_date=_require_text(trade_date, field_name="trade_date"),
        small_cycle_ref=_copy_mapping(small_cycle_ref),
        mid_cycle_ref=_copy_mapping(mid_cycle_ref),
        linkage_phase=_require_text(linkage_phase, field_name="linkage_phase"),
        supports_continuation=bool(supports_continuation),
        local_end_vs_global_end=_require_text(
            local_end_vs_global_end,
            field_name="local_end_vs_global_end",
        ),
        confidence=_copy_mapping(confidence),
        evidence_bundle=_copy_mapping(evidence_bundle),
        rule_version=_require_text(rule_version, field_name="rule_version"),
    )


def build_growth_potential_profile_from_formal_inputs(
    *,
    cycle: SmallCycle,
    fund_cycle_state: MidCycleState,
    industry_cycle_state: MidCycleState,
    rule_version: str = DEFAULT_GROWTH_POTENTIAL_RULE_VERSION,
) -> GrowthPotentialProfile:
    """Build the minimal shadow growth-potential profile used by M4 benchmark."""

    states = {fund_cycle_state.state, industry_cycle_state.state}
    if "weakening" in states:
        status = "negative"
    elif states <= {"advancing", "repairing"} and cycle.cycle_state == "S2 Advancing":
        status = "promising"
    else:
        status = "uncertain"
    return GrowthPotentialProfile(
        stock_code=cycle.stock_code,
        trade_date=cycle.trade_date,
        status=status,
        confidence={
            "level": "medium" if status in {"promising", "uncertain"} else "low",
            "fund_cycle_state": fund_cycle_state.state,
            "industry_cycle_state": industry_cycle_state.state,
        },
        evidence_bundle={
            "small_cycle_state": cycle.cycle_state,
            "fund_cycle_state": fund_cycle_state.state,
            "industry_cycle_state": industry_cycle_state.state,
        },
        rule_version=rule_version,
    )


def build_top_risk_profile_from_formal_inputs(
    *,
    cycle: SmallCycle,
    fund_cycle_state: MidCycleState,
    industry_cycle_state: MidCycleState,
    trading_profile: PF1TradingProfile | None = None,
    rule_version: str = DEFAULT_TOP_RISK_RULE_VERSION,
) -> TopRiskProfile:
    """Build the minimal shadow top-risk profile used by M4 benchmark."""

    return_20d = _as_float(getattr(trading_profile, "return_20d", None))
    positive_days_5d = _normalize_positive_days(
        getattr(trading_profile, "positive_days_5d", None)
    )
    risk_level = _build_risk_level(
        return_20d=return_20d,
        positive_days_5d=positive_days_5d,
    )
    risk_flags: list[str] = []
    if fund_cycle_state.state == "weakening":
        risk_flags.append("fund_cycle_weakening")
    if industry_cycle_state.state == "weakening":
        risk_flags.append("industry_cycle_weakening")
    if risk_level == "high":
        risk_flags.append("momentum_breakdown")
    elif risk_level == "watch":
        risk_flags.append("momentum_watch")
    return TopRiskProfile(
        stock_code=cycle.stock_code,
        trade_date=cycle.trade_date,
        risk_level=risk_level,
        risk_flags=risk_flags,
        evidence_bundle={
            "small_cycle_state": cycle.cycle_state,
            "fund_cycle_state": fund_cycle_state.state,
            "industry_cycle_state": industry_cycle_state.state,
            "return_20d": return_20d,
            "positive_days_5d": positive_days_5d,
        },
        rule_version=rule_version,
    )


def build_shadow_cycle_intelligence_from_m1(
    *,
    cycle: SmallCycle,
    security_master: D7SecurityMasterMinimal | None,
    trading_profile: PF1TradingProfile | None,
) -> dict[str, Any]:
    """Build the minimum M2 shadow bundle required by current benchmark consumers."""

    mid_cycle_states = build_mid_cycle_states_from_m1(
        cycle=cycle,
        security_master=security_master,
        trading_profile=trading_profile,
    )
    linkage_phase = (
        "continuation_supported"
        if all(
            state.state in {"advancing", "repairing"}
            for state in mid_cycle_states.values()
        )
        else "continuation_at_risk"
    )
    supports_continuation = linkage_phase == "continuation_supported"
    local_end_vs_global_end = (
        "local_end_only" if supports_continuation else "needs_global_confirmation"
    )
    cycle_linkage_state = build_cycle_linkage_state(
        stock_code=cycle.stock_code,
        trade_date=cycle.trade_date,
        small_cycle_ref={
            "object_type": cycle.object_type,
            "stock_code": cycle.stock_code,
            "cycle_state": cycle.cycle_state,
        },
        mid_cycle_ref={
            "fund_cycle_state": mid_cycle_states["fund_cycle"].state,
            "industry_cycle_state": mid_cycle_states["industry_cycle"].state,
        },
        linkage_phase=linkage_phase,
        supports_continuation=supports_continuation,
        local_end_vs_global_end=local_end_vs_global_end,
        confidence={
            "level": "medium" if supports_continuation else "low",
            "small_cycle_state": cycle.cycle_state,
        },
        evidence_bundle={
            "fund_cycle_state": mid_cycle_states["fund_cycle"].state,
            "industry_cycle_state": mid_cycle_states["industry_cycle"].state,
        },
    )
    growth_potential_profile = build_growth_potential_profile_from_formal_inputs(
        cycle=cycle,
        fund_cycle_state=mid_cycle_states["fund_cycle"],
        industry_cycle_state=mid_cycle_states["industry_cycle"],
    )
    top_risk_profile = build_top_risk_profile_from_formal_inputs(
        cycle=cycle,
        fund_cycle_state=mid_cycle_states["fund_cycle"],
        industry_cycle_state=mid_cycle_states["industry_cycle"],
        trading_profile=trading_profile,
    )
    return {
        "wave_hypothesis": build_small_cycle_wave_hypothesis_from_formal_inputs(cycle=cycle),
        "mid_cycle_states": mid_cycle_states,
        "cycle_linkage_state": cycle_linkage_state,
        "growth_potential_profile": growth_potential_profile,
        "top_risk_profile": top_risk_profile,
    }
