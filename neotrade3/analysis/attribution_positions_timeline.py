"""Timeline helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any


def build_positions_timeline(trades: list[dict[str, Any]], trading_dates: list[str]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {d: set() for d in trading_dates}
    for trade in trades:
        code = str(trade.get("code") or "").strip()
        buy_date = str(trade.get("buy_date") or "").strip()
        sell_date = str(trade.get("sell_date") or "").strip()
        if not code or not buy_date or buy_date not in out:
            continue
        for day in trading_dates:
            if day < buy_date:
                continue
            if sell_date and day >= sell_date:
                break
            out[day].add(code)
    return out
