"""Trade-window helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any


def build_attribution_trade_window(
    trades: list[dict[str, Any]],
    *,
    segment_start_date: str,
    segment_top_date: str,
) -> dict[str, Any]:
    code_trades = sorted(
        trades,
        key=lambda item: (str(item.get("buy_date") or ""), str(item.get("sell_date") or "")),
    )
    relevant_trades = [
        item
        for item in code_trades
        if str(item.get("buy_date") or "") <= str(segment_top_date or "")
        and str(item.get("sell_date") or "9999-12-31") >= str(segment_start_date or "")
    ]
    held_to_top = any(
        str(item.get("buy_date") or "") <= str(segment_top_date or "") <= str(item.get("sell_date") or "9999-12-31")
        for item in relevant_trades
    )
    first_buy_date = str(relevant_trades[0].get("buy_date") or "") if relevant_trades else ""
    first_sell_date = str(relevant_trades[0].get("sell_date") or "") if relevant_trades else ""
    latest_exit_reason = ""
    if relevant_trades:
        latest_trade = max(relevant_trades, key=lambda item: str(item.get("sell_date") or ""))
        latest_exit_reason = str(latest_trade.get("sell_reason") or "")
    return {
        "code_trades": code_trades,
        "relevant_trades": relevant_trades,
        "bought": bool(relevant_trades),
        "held_to_top": held_to_top,
        "first_buy_date": first_buy_date,
        "first_sell_date": first_sell_date,
        "latest_exit_reason": latest_exit_reason,
    }
