"""Formal M1 phase-1 contract objects for NeoTrade3 data control."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class D1DailyPriceFact:
    """Formal D1 daily price fact projection."""

    stock_code: str
    trade_date: str
    open_price: Optional[float]
    high_price: Optional[float]
    low_price: Optional[float]
    close_price: Optional[float]
    preclose_price: Optional[float]
    pct_change: Optional[float]
    volume_shares: Optional[float]
    amount_cny: Optional[float]
    turnover_rate: Optional[float]
    updated_at: Optional[str]
    object_version: int = 1

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "preclose_price": self.preclose_price,
            "pct_change": self.pct_change,
            "volume_shares": self.volume_shares,
            "amount_cny": self.amount_cny,
            "turnover_rate": self.turnover_rate,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class D7SecurityMasterMinimal:
    """Formal D7 minimal security master projection."""

    stock_code: str
    stock_name: Optional[str]
    asset_type: str
    is_delisted: bool
    sector_lv1: Optional[str]
    sector_lv2: Optional[str]
    last_trade_date: Optional[str]
    object_version: int = 1

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "asset_type": self.asset_type,
            "is_delisted": self.is_delisted,
            "sector_lv1": self.sector_lv1,
            "sector_lv2": self.sector_lv2,
            "last_trade_date": self.last_trade_date,
        }


@dataclass(frozen=True)
class D7TradingDayStatus:
    """Formal D7 trading-day status projection."""

    target_date: str
    is_trading_day: Optional[bool]
    nearest_trading_day: Optional[str]
    min_trading_day: Optional[str]
    max_trading_day: Optional[str]
    calendar_covered_until: Optional[str]
    calendar_source: str
    object_version: int = 1

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_version": self.object_version,
            "target_date": self.target_date,
            "is_trading_day": self.is_trading_day,
            "nearest_trading_day": self.nearest_trading_day,
            "min_trading_day": self.min_trading_day,
            "max_trading_day": self.max_trading_day,
            "calendar_covered_until": self.calendar_covered_until,
            "calendar_source": self.calendar_source,
        }


@dataclass(frozen=True)
class PF1TradingProfile:
    """Formal PF1 trading-profile projection."""

    stock_code: str
    as_of_trade_date: str
    latest_amount: Optional[float]
    avg_amount_5d: Optional[float]
    avg_amount_20d: Optional[float]
    latest_turnover: Optional[float]
    avg_turnover_5d: Optional[float]
    median_turnover_20d: Optional[float]
    return_20d: Optional[float]
    avg_pct_change_5d: Optional[float]
    positive_days_5d: Optional[int]
    object_version: int = 1
    window_5d_ready: bool = field(default=False, repr=False, compare=False)
    window_20d_ready: bool = field(default=False, repr=False, compare=False)

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_version": self.object_version,
            "stock_code": self.stock_code,
            "as_of_trade_date": self.as_of_trade_date,
            "latest_amount": self.latest_amount,
            "avg_amount_5d": self.avg_amount_5d,
            "avg_amount_20d": self.avg_amount_20d,
            "latest_turnover": self.latest_turnover,
            "avg_turnover_5d": self.avg_turnover_5d,
            "median_turnover_20d": self.median_turnover_20d,
            "return_20d": self.return_20d,
            "avg_pct_change_5d": self.avg_pct_change_5d,
            "positive_days_5d": self.positive_days_5d,
        }
