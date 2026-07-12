"""Ranking payload helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any


def build_attribution_ranking_row(
    *,
    rank: Any,
    code: Any,
    name: Any,
    sector: Any,
    first_trade_date: Any,
    last_trade_date: Any,
    first_close: Any,
    last_close: Any,
    annual_return_pct: Any,
) -> dict[str, Any]:
    return {
        "rank": int(rank),
        "code": str(code),
        "name": str(name or ""),
        "sector": str(sector or ""),
        "first_trade_date": str(first_trade_date),
        "last_trade_date": str(last_trade_date),
        "first_close": round(float(first_close), 4),
        "last_close": round(float(last_close), 4),
        "annual_return_pct": round(float(annual_return_pct), 2),
        "price_basis": "未复权收盘价",
    }
