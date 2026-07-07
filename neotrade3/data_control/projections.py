"""Formal M1 phase-1 projection helpers for NeoTrade3 data control."""

from __future__ import annotations

import statistics
from typing import Any, Iterable, Optional

from .contracts import (
    D1DailyPriceFact,
    D7SecurityMasterMinimal,
    D7TradingDayStatus,
    PF1TradingProfile,
)


def _as_float(value: object) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_str(value: object) -> Optional[str]:
    raw = str(value or "").strip()
    return raw or None


def _as_optional_bool(value: object) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    raw = str(value or "").strip().lower()
    if raw in {"true", "1", "yes"}:
        return True
    if raw in {"false", "0", "no"}:
        return False
    return None


def project_d1_daily_price_fact(row: dict[str, Any]) -> D1DailyPriceFact:
    return D1DailyPriceFact(
        stock_code=str(row.get("code") or "").strip(),
        trade_date=str(row.get("trade_date") or "").strip(),
        open_price=_as_float(row.get("open")),
        high_price=_as_float(row.get("high")),
        low_price=_as_float(row.get("low")),
        close_price=_as_float(row.get("close")),
        preclose_price=_as_float(row.get("preclose")),
        pct_change=_as_float(row.get("pct_change")),
        volume_shares=_as_float(row.get("volume")),
        amount_cny=_as_float(row.get("amount")),
        turnover_rate=_as_float(row.get("turnover")),
        updated_at=_as_str(row.get("updated_at")),
    )


def project_d7_security_master_minimal(row: dict[str, Any]) -> D7SecurityMasterMinimal:
    return D7SecurityMasterMinimal(
        stock_code=str(row.get("code") or "").strip(),
        stock_name=_as_str(row.get("name")),
        asset_type=str(row.get("asset_type") or "stock").strip() or "stock",
        is_delisted=bool(int(row.get("is_delisted") or 0)),
        sector_lv1=_as_str(row.get("sector_lv1")),
        sector_lv2=_as_str(row.get("sector_lv2")),
        last_trade_date=_as_str(row.get("last_trade_date")),
    )


def project_d7_trading_day_status(payload: dict[str, Any]) -> D7TradingDayStatus:
    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    calendar_source = str(meta.get("calendar_source") or "unknown").strip() or "unknown"
    return D7TradingDayStatus(
        target_date=str(payload.get("target_date") or "").strip(),
        is_trading_day=_as_optional_bool(payload.get("is_trading_day")),
        nearest_trading_day=_as_str(payload.get("nearest_trading_day")),
        min_trading_day=_as_str(payload.get("min_trading_day")),
        max_trading_day=_as_str(payload.get("max_trading_day")),
        calendar_covered_until=_as_str(payload.get("calendar_covered_until")),
        calendar_source=calendar_source,
    )


def project_pf1_trading_profile(
    *, stock_code: str, price_rows: Iterable[dict[str, Any]]
) -> Optional[PF1TradingProfile]:
    rows = list(price_rows)
    if not rows:
        return None

    as_of_trade_date = _as_str(rows[0].get("trade_date"))
    if as_of_trade_date is None:
        return None

    first_5 = rows[:5]
    first_20 = rows[:20]

    amounts_5 = [_as_float(item.get("amount")) for item in first_5]
    amounts_20 = [_as_float(item.get("amount")) for item in first_20]
    turnovers_5 = [_as_float(item.get("turnover")) for item in first_5]
    turnovers_20 = [_as_float(item.get("turnover")) for item in first_20]
    pct_changes_5 = [_as_float(item.get("pct_change")) for item in first_5]
    closes_20 = [_as_float(item.get("close")) for item in first_20]

    window_5d_ready = (
        len(first_5) == 5
        and all(value is not None for value in amounts_5)
        and all(value is not None for value in turnovers_5)
        and all(value is not None for value in pct_changes_5)
    )
    window_20d_ready = (
        len(first_20) == 20
        and all(value is not None for value in amounts_20)
        and all(value is not None for value in turnovers_20)
        and all(value is not None for value in closes_20)
    )

    return_20d: Optional[float] = None
    if window_20d_ready:
        latest_close = closes_20[0]
        baseline_close = closes_20[19]
        if isinstance(latest_close, float) and isinstance(baseline_close, float) and baseline_close > 0:
            return_20d = (latest_close / baseline_close) - 1.0

    latest_turnover = _as_float(rows[0].get("turnover"))
    latest_amount = _as_float(rows[0].get("amount"))

    return PF1TradingProfile(
        stock_code=stock_code,
        as_of_trade_date=as_of_trade_date,
        latest_amount=latest_amount,
        avg_amount_5d=statistics.fmean(amounts_5) if window_5d_ready else None,
        avg_amount_20d=statistics.fmean(amounts_20) if window_20d_ready else None,
        latest_turnover=latest_turnover,
        avg_turnover_5d=statistics.fmean(turnovers_5) if window_5d_ready else None,
        median_turnover_20d=statistics.median(turnovers_20) if window_20d_ready else None,
        return_20d=return_20d,
        avg_pct_change_5d=statistics.fmean(pct_changes_5) if window_5d_ready else None,
        positive_days_5d=(
            sum(1 for value in pct_changes_5 if value is not None and value > 0)
            if window_5d_ready
            else None
        ),
        window_5d_ready=window_5d_ready,
        window_20d_ready=window_20d_ready,
    )
