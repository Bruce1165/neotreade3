"""Execution limit-window helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any

from neotrade3.decision_engine.trade_block_reason import resolve_trade_block_reason


def is_execution_limit_up_window(
    *,
    bars: list[dict[str, Any]],
    limit_up_pct: float,
    one_price_only: bool,
) -> bool:
    if not bars:
        return False
    return all(
        resolve_trade_block_reason(
            bar=bar,
            side="buy",
            trade_value=0.0,
            limit_up_pct=float(limit_up_pct),
            limit_down_pct=0.0,
            block_on_limit_up=True,
            block_on_limit_down=False,
            only_one_price_limit=bool(one_price_only),
            min_amount_cny=0.0,
            max_participation_rate=1.0,
        )
        == "limit_up"
        for bar in bars
    )
