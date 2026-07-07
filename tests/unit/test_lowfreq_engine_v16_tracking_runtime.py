from __future__ import annotations

from datetime import date, timedelta

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16, LowFreqV16Config


def test_run_backtest_records_tracking_audit_without_polluting_execution_action_summary() -> None:
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
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 2
    engine.TRACKING_MIN_DAYS = 2
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = False
    engine.EXECUTION_RESERVATION_ENABLED = False
    engine._conn = lambda: _FakeConn()
    engine._get_trading_dates = lambda start, end: [day1, day2, day3]
    engine._count_trading_days = lambda start, end: 2
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine._get_bar = lambda cursor, code, d: {"close": 10.0, "pct_change": 0.0, "amount": 1e9}
    engine.get_config_snapshot = lambda: {}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}

    def _signals(current_date):
        if current_date in {day1, day2}:
            ready = {
                "code": "600001",
                "name": "成熟龙头",
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
            observe = {
                "code": "300001",
                "name": "观察候选",
                "sector": "B",
                "buy_score": 70.0,
                "wave_phase": "未知",
                "role": "龙头",
                "reasons": ["继续观察"],
                "soft_flags": ["wave_uncertain"],
                "candidate_tier": "soft_retained",
                "entry_ready": False,
                "tracking_ready": False,
                "tracking_state": "tracking_observe",
                "tracking_transition_reason": "candidate_retained_for_tracking",
                "tracking_evidence_bundle": ["继续观察"],
            }
            return {
                "buy_signals": [ready],
                "candidate_signals": [ready, observe],
                "entry_signals": [ready],
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

    events = [row["event"] for row in result["buy_signal_audit"]]
    assert "tracking_started" in events
    assert "tracking_promoted_to_entry" in events
    assert "tracking_dropped" in events
    promoted = next(row for row in result["buy_signal_audit"] if row["event"] == "tracking_promoted_to_entry")
    dropped = next(row for row in result["buy_signal_audit"] if row["event"] == "tracking_dropped")
    assert promoted["source_layer"] == "tracking"
    assert promoted["tracking_ready"] is True
    assert promoted["funnel_stage"] == "entry_ready"
    assert promoted["date"] == day2.isoformat()
    assert promoted["tracking_days"] == 2
    bought = next(row for row in result["buy_signal_audit"] if row["event"] == "buy_executed")
    assert bought["date"] == day3.isoformat()
    assert dropped["source_layer"] == "tracking"
    assert dropped["tracking_state"] == "tracking_dropped"
    assert dropped["code"] == "300001"
    assert result["execution_action_summary"] == {"buy": 1}
