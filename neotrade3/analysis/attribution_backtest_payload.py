"""Backtest payload helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any


def build_attribution_backtest_payload(
    *,
    requested_by: str,
    generated_at: str,
    summary: Any,
    trades: Any,
) -> dict[str, Any]:
    normalized_summary = summary if isinstance(summary, dict) else {}
    normalized_trades = trades if isinstance(trades, list) else []
    return {
        "_meta": {
            "status": "ok",
            "requested_by": str(requested_by or ""),
            "model": "lowfreq_engine_v16_advanced",
            "generated_at": str(generated_at or ""),
        },
        "summary": normalized_summary,
        "trade_blocks": normalized_summary.get("trade_blocks", {}),
        "config_snapshot": normalized_summary.get("config_snapshot", {}),
        "coverage_gaps": normalized_summary.get("coverage_gaps", {}),
        "trades": normalized_trades,
    }
