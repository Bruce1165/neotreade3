from __future__ import annotations

from typing import Any


def resolve_trade_block_reason(
    *,
    bar: dict[str, Any] | None,
    side: str,
    trade_value: float,
    limit_up_pct: float,
    limit_down_pct: float,
    block_on_limit_up: bool,
    block_on_limit_down: bool,
    only_one_price_limit: bool,
    min_amount_cny: float,
    max_participation_rate: float,
) -> str | None:
    if not isinstance(bar, dict):
        return "missing_price_bar"

    pct = bar.get("pct_change")
    if pct is not None:
        high = bar.get("high")
        low = bar.get("low")
        close = bar.get("close")
        is_one_price_board = (
            isinstance(high, (int, float))
            and isinstance(low, (int, float))
            and isinstance(close, (int, float))
            and abs(float(high) - float(low)) <= 1e-9
            and abs(float(high) - float(close)) <= 1e-9
        )
        buy_limit_hit = float(pct) >= float(limit_up_pct) and (
            is_one_price_board if bool(only_one_price_limit) else True
        )
        sell_limit_hit = float(pct) <= float(limit_down_pct) and (
            is_one_price_board if bool(only_one_price_limit) else True
        )
        if str(side) == "buy" and bool(block_on_limit_up) and buy_limit_hit:
            return "limit_up"
        if str(side) == "sell" and bool(block_on_limit_down) and sell_limit_hit:
            return "limit_down"

    amount = bar.get("amount")
    normalized_min_amount_cny = float(min_amount_cny or 0.0)
    if (
        normalized_min_amount_cny > 0.0
        and isinstance(amount, (int, float))
        and float(amount) < normalized_min_amount_cny
    ):
        return "min_amount"

    normalized_max_participation_rate = float(max_participation_rate or 1.0)
    if (
        normalized_max_participation_rate < 1.0
        and isinstance(amount, (int, float))
        and float(amount) > 0.0
        and float(trade_value) > float(amount) * normalized_max_participation_rate
    ):
        return "participation_rate"

    return None
