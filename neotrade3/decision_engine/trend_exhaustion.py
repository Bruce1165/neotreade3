from __future__ import annotations

from typing import Any


def build_trend_exhaustion_snapshot(
    *,
    buy_price: float,
    peak_price: float,
    current_price: float,
    hold_days: int,
    buy_progress_label: str,
    trailing_profit_level: float,
    partial_profit_level: float,
    trailing_stop_pct: float,
    min_hold_days: int,
) -> dict[str, Any] | None:
    normalized_buy_price = float(buy_price or 0.0)
    normalized_current_price = float(current_price or 0.0)
    if normalized_buy_price <= 0.0 or normalized_current_price <= 0.0:
        return None
    normalized_peak_price = float(peak_price or 0.0)
    if normalized_peak_price <= 0.0:
        normalized_peak_price = float(normalized_buy_price)
    peak_return_pct = (normalized_peak_price - normalized_buy_price) / max(normalized_buy_price, 1e-9) * 100.0
    current_return_pct = (normalized_current_price - normalized_buy_price) / max(normalized_buy_price, 1e-9) * 100.0
    drawdown_from_peak_pct = float(current_return_pct) - float(peak_return_pct)
    armed_level = max(float(trailing_profit_level), float(partial_profit_level))
    drawdown_trigger = float(trailing_stop_pct)
    required_hold_days = max(int(min_hold_days), 0)
    normalized_hold_days = int(hold_days)
    normalized_label = str(buy_progress_label or "").strip()
    armed = float(peak_return_pct) > float(armed_level)
    drawdown_triggered = float(drawdown_from_peak_pct) <= float(drawdown_trigger)
    hold_ready = int(normalized_hold_days) >= int(required_hold_days)
    current_profit_positive = float(current_return_pct) > 0.0
    early_quality_entry = normalized_label in {"早窗", "前置布局"}
    condition_pass = bool(armed and drawdown_triggered and hold_ready and current_profit_positive and not early_quality_entry)
    details = (
        f"趋势衰竭候选：峰值收益{peak_return_pct:.1f}% | 当前收益{current_return_pct:.1f}% | "
        f"距峰值回撤{drawdown_from_peak_pct:.1f}pct | 最小持有{normalized_hold_days}天"
    )
    return {
        "armed": bool(armed),
        "hold_ready": bool(hold_ready),
        "current_profit_positive": bool(current_profit_positive),
        "early_quality_entry": bool(early_quality_entry),
        "drawdown_from_peak_triggered": bool(drawdown_triggered),
        "condition_pass": bool(condition_pass),
        "peak_return_pct": round(float(peak_return_pct), 2),
        "current_return_pct": round(float(current_return_pct), 2),
        "drawdown_from_peak_pct": round(float(drawdown_from_peak_pct), 2),
        "details": details,
    }
