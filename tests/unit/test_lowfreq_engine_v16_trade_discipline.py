from __future__ import annotations

from datetime import date, timedelta

import pytest

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16, LowFreqV16Config


def test_trade_discipline_guard_blocks_new_entry_when_recent_trade_count_reaches_window_limit() -> None:
    class _FakeCursor:
        pass

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.MAX_POSITIONS = 2
    engine.BUY_SIGNAL_MEMORY_DAYS = 1
    engine.TRACKING_MIN_DAYS = 1
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = False
    engine.EXECUTION_RESERVATION_ENABLED = False
    engine.DISCIPLINE_ENABLED = True
    engine.DISCIPLINE_WINDOW_DAYS = 2
    engine.DISCIPLINE_MAX_TRADES_WINDOW = 1
    engine._conn = lambda: _FakeConn()
    engine._get_trading_dates = lambda start, end: [day1, day2, day3]
    engine._count_trading_days = lambda start, end: 1
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine._get_bar = lambda cursor, code, d: {"close": 10.0, "pct_change": 0.0, "amount": 1e9}
    engine.get_config_snapshot = lambda: {}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}

    def _signals(current_date):
        if current_date == day1:
            a = {
                "code": "600001",
                "name": "候选A",
                "sector": "A",
                "buy_score": 92.0,
                "wave_phase": "3浪",
                "role": "龙头",
                "reasons": ["成熟候选"],
                "candidate_tier": "execution_eligible",
                "entry_ready": True,
                "tracking_ready": True,
                "tracking_state": "tracking_mature",
                "tracking_transition_reason": "candidate_meets_current_entry_contract",
                "tracking_evidence_bundle": ["成熟候选"],
            }
            return {
                "buy_signals": [a],
                "candidate_signals": [a],
                "entry_signals": [a],
            }
        if current_date == day2:
            b = {
                "code": "600002",
                "name": "候选B",
                "sector": "B",
                "buy_score": 91.0,
                "wave_phase": "3浪",
                "role": "龙头",
                "reasons": ["成熟候选"],
                "candidate_tier": "execution_eligible",
                "entry_ready": True,
                "tracking_ready": True,
                "tracking_state": "tracking_mature",
                "tracking_transition_reason": "candidate_meets_current_entry_contract",
                "tracking_evidence_bundle": ["成熟候选"],
            }
            return {
                "buy_signals": [b],
                "candidate_signals": [b],
                "entry_signals": [b],
            }
        return {
            "buy_signals": [],
            "candidate_signals": [],
            "entry_signals": [],
        }

    engine.generate_buy_signals = _signals

    result = engine.run_backtest(
        day1,
        day3,
        initial_capital=100000.0,
        include_trades=True,
    )

    bought = next(row for row in result["buy_signal_audit"] if row["event"] == "buy_executed")
    assert bought["code"] == "600001"
    assert bought["date"] == day2.isoformat()

    blocked = next(
        row for row in result["buy_signal_audit"] if row["event"] == "trade_discipline_guard_blocked"
    )
    assert blocked["code"] == "600002"
    assert blocked["date"] == day3.isoformat()
    assert blocked["execution_block_reason"] == "execution_rule_blocked"

    assert result["execution_action_summary"] == {"buy": 1}

    day3_audit = next(
        row for row in result["trade_discipline_audit"] if row.get("asof_date") == day3.isoformat()
    )
    assert day3_audit["guard_verdict"]["status"] == "block"


def test_run_backtest_fail_closed_when_end_flat_has_missing_price_bar() -> None:
    class _FakeCursor:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return None

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.MAX_POSITIONS = 2
    engine.BUY_SIGNAL_MEMORY_DAYS = 1
    engine.TRACKING_MIN_DAYS = 1
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = False
    engine.EXECUTION_RESERVATION_ENABLED = False
    engine.DISCIPLINE_ENABLED = False
    engine._conn = lambda: _FakeConn()
    engine._get_trading_dates = lambda start, end: [day1, day2, day3]
    engine._count_trading_days = lambda start, end: 1
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine.get_config_snapshot = lambda: {}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}

    def _get_bar(_cursor, code, d):
        if str(code) == "600001" and d == day3:
            return None
        return {"close": 10.0, "pct_change": 0.0, "amount": 1e9}

    engine._get_bar = _get_bar

    def _signals(current_date):
        if current_date == day1:
            a = {
                "code": "600001",
                "name": "候选A",
                "sector": "A",
                "buy_score": 92.0,
                "wave_phase": "3浪",
                "role": "龙头",
                "reasons": ["成熟候选"],
                "candidate_tier": "execution_eligible",
                "entry_ready": True,
                "tracking_ready": True,
                "tracking_state": "tracking_mature",
                "tracking_transition_reason": "candidate_meets_current_entry_contract",
                "tracking_evidence_bundle": ["成熟候选"],
            }
            return {
                "buy_signals": [a],
                "candidate_signals": [a],
                "entry_signals": [a],
            }
        return {
            "buy_signals": [],
            "candidate_signals": [],
            "entry_signals": [],
        }

    engine.generate_buy_signals = _signals

    with pytest.raises(RuntimeError, match="backtest_end_flat_missing_price"):
        engine.run_backtest(
            day1,
            day3,
            initial_capital=100000.0,
            include_trades=True,
        )
