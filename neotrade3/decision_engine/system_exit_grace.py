from __future__ import annotations


def resolve_buy_progress_label(
    *,
    signal_label: str | None = None,
    trade_label: str | None = None,
    signal_wave_phase: str | None = None,
    trade_wave_phase: str | None = None,
    wave1_value: str = "1浪",
    wave3_value: str = "3浪",
) -> str:
    raw_signal_label = str(signal_label or "").strip()
    if raw_signal_label:
        return raw_signal_label
    raw_trade_label = str(trade_label or "").strip()
    if raw_trade_label:
        return raw_trade_label
    raw_wave_phase = str(signal_wave_phase or "").strip() or str(trade_wave_phase or "").strip()
    if raw_wave_phase == str(wave1_value):
        return "前置布局"
    if raw_wave_phase == str(wave3_value):
        return "早窗"
    return "其它"


def profit_keep_ratio(*, current_return_pct: float, peak_return_pct: float) -> float:
    if float(peak_return_pct) <= 0.0:
        return 0.0
    return float(current_return_pct) / max(float(peak_return_pct), 1e-9)


def system_exit_grace_thresholds(
    *,
    scope: str,
    market_min_peak_return_pct: float,
    market_min_current_profit_pct: float,
    market_min_profit_keep_ratio: float,
    sector_min_peak_return_pct: float,
    sector_min_current_profit_pct: float,
    sector_min_profit_keep_ratio: float,
    sector_max_hold_days: int,
) -> tuple[float, float, float, int]:
    if str(scope) == "sector":
        return (
            float(sector_min_peak_return_pct),
            float(sector_min_current_profit_pct),
            float(sector_min_profit_keep_ratio),
            int(sector_max_hold_days),
        )
    return (
        float(market_min_peak_return_pct),
        float(market_min_current_profit_pct),
        float(market_min_profit_keep_ratio),
        0,
    )


def is_leader_hold_candidate(
    *,
    role: str,
    peak_return_pct: float,
    leader_hold_min_peak_return_pct: float,
) -> bool:
    if str(role or "").strip() != "龙头":
        return False
    return float(peak_return_pct) >= float(leader_hold_min_peak_return_pct)


def is_eligible_for_system_exit_grace(
    *,
    enabled: bool,
    grace_used: bool,
    scope: str,
    role: str,
    sell_price: float,
    peak_return_pct: float,
    buy_progress_label: str,
    current_return_pct: float,
    min_peak_return_pct: float,
    legacy_market_min_peak_return_pct: float,
    min_current_profit_pct: float,
    min_profit_keep_ratio: float,
    max_hold_days: int,
    hold_days: int,
    require_positive_return: bool,
    leader_hold_candidate: bool,
) -> bool:
    if not bool(enabled):
        return False
    if bool(grace_used):
        return False
    grace_scope = str(scope or "")
    normalized_role = str(role or "").strip()
    if grace_scope == "sector":
        if normalized_role not in {"龙头", "中军"}:
            return False
    elif not bool(leader_hold_candidate):
        return False
    if float(sell_price or 0.0) <= 0.0:
        return False
    if str(buy_progress_label or "") not in {"早窗", "前置布局"}:
        return False
    if bool(require_positive_return) and float(current_return_pct) <= 0.0:
        return False
    effective_min_peak_return_pct = float(min_peak_return_pct)
    if grace_scope != "sector":
        effective_min_peak_return_pct = max(
            effective_min_peak_return_pct,
            float(legacy_market_min_peak_return_pct),
        )
    if float(peak_return_pct) < effective_min_peak_return_pct:
        return False
    if float(current_return_pct) < float(min_current_profit_pct):
        return False
    if profit_keep_ratio(
        current_return_pct=float(current_return_pct),
        peak_return_pct=float(peak_return_pct),
    ) < float(min_profit_keep_ratio):
        return False
    if int(max_hold_days) > 0 and int(hold_days) > int(max_hold_days):
        return False
    return True
