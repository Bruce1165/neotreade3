"""Wave-segment payload helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from datetime import date
from typing import Any


def build_missing_wave_segment(*, code: str) -> dict[str, Any]:
    return {
        "status": "missing_2025_prices",
        "code": str(code),
    }


def build_insufficient_history_wave_segment(
    *,
    code: str,
    top_date: date,
    top_close: float,
) -> dict[str, Any]:
    return {
        "status": "insufficient_history",
        "code": str(code),
        "top_date": top_date.isoformat(),
        "top_close": round(float(top_close), 4),
    }


def build_ok_wave_segment(
    *,
    code: str,
    lookback_trading_days: int,
    start_date: str,
    start_close: float,
    top_date: date,
    top_close: float,
    segment_return_pct: float,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "code": str(code),
        "segment_window_trading_days": int(lookback_trading_days),
        "start_date": str(start_date),
        "start_close": round(float(start_close), 4),
        "top_date": top_date.isoformat(),
        "top_close": round(float(top_close), 4),
        "segment_return_pct": round(float(segment_return_pct), 2),
        "segment_basis": "见顶日前180交易日窗口内最低收盘价 -> 2025年最高收盘价",
    }
