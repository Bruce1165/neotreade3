"""Authoritative models for the low-frequency score system operation layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


LOWFREQ_SCORE_STATES: tuple[str, ...] = ("跟踪", "持有中", "已清仓")


@dataclass
class PoolCurrentRecord:
    code: str
    name: str = ""
    sector: str = ""
    state: str = "跟踪"
    state_since: str = ""
    tracking_since: str = ""
    buy_date: Optional[str] = None
    buy_price: Optional[float] = None
    sell_date: Optional[str] = None
    sell_price: Optional[float] = None
    last_trade_date: Optional[str] = None
    last_price: Optional[float] = None
    current_return_pct: Optional[float] = None
    realized_return_pct: Optional[float] = None
    top_signal_date: Optional[str] = None
    engine_snapshot_ref: str = ""
    updated_at: str = ""

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PoolEventRecord:
    event_id: str
    code: str
    event_type: str
    event_date: str
    from_state: str = ""
    to_state: str = ""
    trigger_source: str = ""
    engine_evidence_ref: str = ""
    price: Optional[float] = None
    note: str = ""
    created_at: str = ""

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyPriceSnapshotRecord:
    trade_date: str
    code: str
    state: str
    close_price: Optional[float] = None
    buy_price: Optional[float] = None
    sell_price: Optional[float] = None
    unrealized_return_pct: Optional[float] = None
    realized_return_pct: Optional[float] = None
    snapshot_refreshed_at: str = ""

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PeriodSummaryRecord:
    period_type: str
    period_start: str
    period_end: str
    tracked_count: int = 0
    holding_count: int = 0
    closed_count: int = 0
    entered_count: int = 0
    holding_return_pct: Optional[float] = None
    realized_return_pct: Optional[float] = None
    pool_return_pct: Optional[float] = None
    capture_quality: Optional[float] = None
    top_exit_quality: Optional[float] = None
    updated_at: str = ""

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)
