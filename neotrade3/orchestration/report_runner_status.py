"""Stage payload helpers for lowfreq report-runner status writes."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ReportRunnerStage(str, Enum):
    """Visible stage names emitted by the lowfreq attribution report runner."""

    INITIALIZING = "initializing"
    RANKING_READY = "ranking_ready"
    BACKTEST_READY = "backtest_ready"
    ANALYSIS_READY = "analysis_ready"
    DONE = "done"


def build_initializing_report_status(
    *,
    year: Any,
    limit: Any,
    report_id: Any,
) -> dict[str, Any]:
    return {
        "stage": ReportRunnerStage.INITIALIZING.value,
        "year": int(year),
        "limit": int(limit),
        "report_id": str(report_id or ""),
    }


def build_ranking_ready_report_status(*, ranking_count: Any) -> dict[str, Any]:
    return {
        "stage": ReportRunnerStage.RANKING_READY.value,
        "ranking_count": int(ranking_count),
    }


def build_backtest_ready_report_status(
    *,
    ranking_count: Any,
    total_return_pct: Any,
    total_trades: Any,
) -> dict[str, Any]:
    return {
        "stage": ReportRunnerStage.BACKTEST_READY.value,
        "ranking_count": int(ranking_count),
        "total_return_pct": total_return_pct,
        "total_trades": total_trades,
    }


def build_analysis_ready_report_status(
    *,
    ranking_count: Any,
    aggregate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "stage": ReportRunnerStage.ANALYSIS_READY.value,
        "ranking_count": int(ranking_count),
        "aggregate": aggregate,
    }


def build_done_report_status(
    *,
    report_id: Any,
    ranking_path: Any,
    segments_path: Any,
    attribution_path: Any,
    report_path: Any,
) -> dict[str, Any]:
    return {
        "stage": ReportRunnerStage.DONE.value,
        "report_id": str(report_id or ""),
        "ranking_path": str(ranking_path),
        "segments_path": str(segments_path),
        "attribution_path": str(attribution_path),
        "report_path": str(report_path),
    }
