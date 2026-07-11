from __future__ import annotations

from typing import Any


def build_thesis_invalidation_snapshot(
    *,
    buy_price: float,
    sell_price: float,
    stop_loss_pct: float,
    hold_days: int,
) -> dict[str, Any] | None:
    normalized_buy_price = float(buy_price or 0.0)
    if normalized_buy_price <= 0.0:
        return None
    current_return_pct = (
        (float(sell_price) - normalized_buy_price) / max(normalized_buy_price, 1e-9) * 100.0
    )
    normalized_stop_loss_pct = float(stop_loss_pct)
    if float(current_return_pct) > float(normalized_stop_loss_pct):
        return None
    normalized_hold_days = int(hold_days)
    invalidated_window = "early" if int(normalized_hold_days) < 12 else "late"
    window_label = "建仓早期" if invalidated_window == "early" else "持仓期"
    details = (
        f"{window_label}硬证伪退出：跌破买入价{current_return_pct:.1f}%"
        f"（阈值{normalized_stop_loss_pct:.1f}%）"
    )
    return {
        "condition_pass": True,
        "current_return_pct": round(float(current_return_pct), 2),
        "stop_loss_pct": round(float(normalized_stop_loss_pct), 2),
        "hold_days": int(normalized_hold_days),
        "invalidated_window": invalidated_window,
        "window_label": window_label,
        "details": details,
    }
