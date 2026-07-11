from __future__ import annotations

from neotrade3.decision_engine.trade_block_reason import resolve_trade_block_reason


def test_resolve_trade_block_reason_returns_missing_price_bar_for_none() -> None:
    reason = resolve_trade_block_reason(
        bar=None,
        side="buy",
        trade_value=1e6,
        limit_up_pct=9.8,
        limit_down_pct=-9.8,
        block_on_limit_up=True,
        block_on_limit_down=True,
        only_one_price_limit=False,
        min_amount_cny=0.0,
        max_participation_rate=1.0,
    )

    assert reason == "missing_price_bar"


def test_resolve_trade_block_reason_blocks_buy_limit_up_on_one_price_board() -> None:
    reason = resolve_trade_block_reason(
        bar={"close": 10.98, "high": 10.98, "low": 10.98, "pct_change": 10.0, "amount": 1e9},
        side="buy",
        trade_value=1e6,
        limit_up_pct=9.8,
        limit_down_pct=-9.8,
        block_on_limit_up=True,
        block_on_limit_down=True,
        only_one_price_limit=True,
        min_amount_cny=0.0,
        max_participation_rate=1.0,
    )

    assert reason == "limit_up"


def test_resolve_trade_block_reason_allows_non_one_price_limit_up_when_required() -> None:
    reason = resolve_trade_block_reason(
        bar={"close": 10.98, "high": 11.2, "low": 10.5, "pct_change": 10.0, "amount": 1e9},
        side="buy",
        trade_value=1e6,
        limit_up_pct=9.8,
        limit_down_pct=-9.8,
        block_on_limit_up=True,
        block_on_limit_down=True,
        only_one_price_limit=True,
        min_amount_cny=0.0,
        max_participation_rate=1.0,
    )

    assert reason is None


def test_resolve_trade_block_reason_blocks_sell_limit_down() -> None:
    reason = resolve_trade_block_reason(
        bar={"close": 8.9, "high": 8.9, "low": 8.9, "pct_change": -10.0, "amount": 1e9},
        side="sell",
        trade_value=1e6,
        limit_up_pct=9.8,
        limit_down_pct=-9.8,
        block_on_limit_up=True,
        block_on_limit_down=True,
        only_one_price_limit=True,
        min_amount_cny=0.0,
        max_participation_rate=1.0,
    )

    assert reason == "limit_down"


def test_resolve_trade_block_reason_blocks_low_amount() -> None:
    reason = resolve_trade_block_reason(
        bar={"close": 10.0, "high": 10.2, "low": 9.8, "pct_change": 1.0, "amount": 5e5},
        side="buy",
        trade_value=1e5,
        limit_up_pct=9.8,
        limit_down_pct=-9.8,
        block_on_limit_up=True,
        block_on_limit_down=True,
        only_one_price_limit=False,
        min_amount_cny=1e6,
        max_participation_rate=1.0,
    )

    assert reason == "min_amount"


def test_resolve_trade_block_reason_blocks_participation_rate() -> None:
    reason = resolve_trade_block_reason(
        bar={"close": 10.0, "high": 10.2, "low": 9.8, "pct_change": 1.0, "amount": 1e6},
        side="buy",
        trade_value=6e5,
        limit_up_pct=9.8,
        limit_down_pct=-9.8,
        block_on_limit_up=True,
        block_on_limit_down=True,
        only_one_price_limit=False,
        min_amount_cny=0.0,
        max_participation_rate=0.5,
    )

    assert reason == "participation_rate"


def test_resolve_trade_block_reason_returns_none_for_valid_bar() -> None:
    reason = resolve_trade_block_reason(
        bar={"close": 10.0, "high": 10.2, "low": 9.8, "pct_change": 1.0, "amount": 1e9},
        side="buy",
        trade_value=1e5,
        limit_up_pct=9.8,
        limit_down_pct=-9.8,
        block_on_limit_up=True,
        block_on_limit_down=True,
        only_one_price_limit=False,
        min_amount_cny=0.0,
        max_participation_rate=1.0,
    )

    assert reason is None
