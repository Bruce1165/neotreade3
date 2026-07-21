from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BacktestVersions:
    thresholds_version: str
    registry_version: str
    weights_version: str


@dataclass(frozen=True)
class BacktestSignalConfig:
    signal_mode: str
    combo_lambda: float | None
    combo_beta: float | None


@dataclass(frozen=True)
class BacktestConfig:
    start_date: str
    end_date: str
    initial_capital: float
    max_positions: int
    position_size_pct: float
    versions: BacktestVersions
    signal: BacktestSignalConfig


@dataclass(frozen=True)
class SnapshotRef:
    trade_date: str
    reference_mode: str
    registry_version: str
    weights_version: str
    thresholds_version: str
    net_energy: float
    score: float
    pred: int


@dataclass
class TradeRecord:
    code: str
    name: str
    signal_date: str
    entry_date: str
    entry_price_close: float
    entry_reason: str
    entry_snapshot_ref: SnapshotRef
    timeline: list[dict[str, str]]
    exit_signal_date: str | None = None
    exit_date: str | None = None
    exit_price_close: float | None = None
    exit_reason: str | None = None
    exit_snapshot_ref: SnapshotRef | None = None
    holding_days: int = 0
    peak_close_price: float | None = None
    peak_close_date: str | None = None
    exit_return_pct: float | None = None
    max_runup_pct_during_hold: float | None = None
    giveback_pct: float | None = None
    max_drawdown_from_peak_pct: float | None = None


@dataclass(frozen=True)
class WindowSummary:
    window_type: str
    window_start_date: str
    window_end_date: str
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    avg_return_pct: float
    median_return_pct: float
    avg_giveback_pct: float
    p90_giveback_pct: float
    skipped_missing_snapshot: int
    skipped_pending_snapshot: int


@dataclass(frozen=True)
class FiltersEvalBucket:
    bucket_id: str
    lower_pct: float
    upper_pct: float
    trigger_event_count: int
    trigger_code_count: int


@dataclass(frozen=True)
class FiltersEval120D:
    label_horizon_trading_days: int
    asof_date: str
    future_date: str
    labeled_codes: int
    skipped_label_missing: int
    buckets: list[FiltersEvalBucket]


@dataclass(frozen=True)
class BacktestRunResult:
    config: BacktestConfig
    trade_dates: list[str]
    trades: list[TradeRecord]
    window_summaries_weekly: list[WindowSummary]
    window_summaries_regime: list[WindowSummary]
    filters_eval_120d: list[FiltersEval120D]
    meta: dict[str, Any]
