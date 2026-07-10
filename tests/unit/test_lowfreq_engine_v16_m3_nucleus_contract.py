from __future__ import annotations

from datetime import date, timedelta

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16, LowFreqV16Config, TradeRecord


def _make_runtime_engine() -> LowFreqTradingEngineV16:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.WAVE1_TRACKING_ONLY_ENABLED = True
    engine.TRACKING_MIN_DAYS = 2
    engine._buy_signal_audit_current_run = []
    return engine


def _make_sell_engine(
    *,
    price: float,
    market_exit_snapshot: dict | None = None,
    sector_exit_snapshot: dict | None = None,
) -> LowFreqTradingEngineV16:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine._get_price = lambda code, current_date: float(price)
    engine._market_exit_snapshot = lambda trade, current_date, market_key=None: market_exit_snapshot
    engine._sector_exit_snapshot = lambda trade, current_date: sector_exit_snapshot
    engine._resolve_market_proxy = lambda code: "cyb"
    engine._get_trading_dates = lambda start, end: [
        start + timedelta(days=i) for i in range(max((end - start).days, 0) + 1)
    ]
    engine._count_trading_days = lambda start, end: (end - start).days + 1
    engine._sell_signal_audit_current_run = []
    engine.STOP_LOSS_PCT = -5.0
    engine.TRAILING_PROFIT_LEVEL = 20.0
    engine.TRAILING_STOP_PCT = -5.0
    engine.MIN_HOLD_DAYS = 15
    engine.MARKET_EXIT_CONFIRM_WINDOW = 5
    engine.MARKET_EXIT_CONFIRM_HITS = 3
    engine.SECTOR_EXIT_CONFIRM_WINDOW = 4
    engine.SECTOR_EXIT_CONFIRM_HITS = 3
    engine.LEADER_HOLD_MIN_PEAK_RETURN_PCT = 15.0
    engine.LEADER_CONFIRM_EXTRA_HITS = 1
    engine.SYSTEM_EXIT_GRACE_ENABLED = True
    engine.SYSTEM_EXIT_GRACE_MIN_PEAK_RETURN_PCT = 20.0
    engine.SYSTEM_EXIT_GRACE_REQUIRE_POSITIVE_RETURN = True
    engine.SYSTEM_EXIT_GRACE_MARKET_MIN_PEAK_RETURN_PCT = 20.0
    engine.SYSTEM_EXIT_GRACE_MARKET_MIN_CURRENT_PROFIT_PCT = 10.0
    engine.SYSTEM_EXIT_GRACE_MARKET_MIN_PROFIT_KEEP_RATIO = 0.50
    engine.SYSTEM_EXIT_GRACE_SECTOR_MIN_PEAK_RETURN_PCT = 10.0
    engine.SYSTEM_EXIT_GRACE_SECTOR_MIN_CURRENT_PROFIT_PCT = 10.0
    engine.SYSTEM_EXIT_GRACE_SECTOR_MIN_PROFIT_KEEP_RATIO = 0.60
    engine.SYSTEM_EXIT_GRACE_SECTOR_MAX_HOLD_DAYS = 10
    return engine


def _make_trade(
    *,
    code: str = "300001",
    buy_price: float = 100.0,
    peak_price: float = 100.0,
    role: str = "普通",
    wave_phase: str = "3浪",
    buy_progress_label: str = "早窗",
    hold_days: int = 0,
) -> TradeRecord:
    return TradeRecord(
        code=str(code),
        name="测试标的",
        sector="AI",
        buy_date="2026-01-05",
        buy_price=float(buy_price),
        peak_price=float(peak_price),
        shares=200,
        role=str(role),
        wave_phase=str(wave_phase),
        buy_progress_label=str(buy_progress_label),
        hold_days=int(hold_days),
    )


def _market_exit_hit_snapshot() -> dict:
    return {
        "scope": "market",
        "market_key": "cyb",
        "market_label": "创业板",
        "condition_pass": True,
        "evidence_count": 2,
        "details": "创业板见顶确认候选：趋势转弱=是 | 广度转弱=是 | 代理回撤-10.5%",
    }


def test_m3_nucleus_tracking_snapshot_preserves_transition_contract() -> None:
    engine = _make_runtime_engine()

    snapshot = engine._tracking_snapshot_from_signal(
        {
            "code": "600001",
            "reasons": ["成熟候选"],
            "candidate_tier": "execution_eligible",
            "entry_ready": True,
        }
    )

    assert snapshot["tracking_ready"] is True
    assert snapshot["tracking_state"] == "tracking_mature"
    assert snapshot["tracking_transition_reason"] == "candidate_meets_current_entry_contract"
    assert snapshot["tracking_decision"] == "tracking_ready_for_entry"
    assert snapshot["tracking_next_action"] == "promote_to_entry"


def test_m3_nucleus_phase1_contract_keeps_tracking_and_entry_layers() -> None:
    engine = _make_runtime_engine()

    signal = engine._decorate_signal_with_phase1_contracts(
        {
            "code": "600001",
            "name": "成熟龙头",
            "sector": "AI",
            "buy_score": 92.0,
            "wave_phase": "3浪",
            "role": "龙头",
            "reasons": ["成熟候选"],
        }
    )

    assert signal["candidate_tier"] == "execution_eligible"
    assert signal["tracking_ready"] is True
    assert signal["tracking_state"] == "tracking_mature"
    assert signal["candidate_contract"]["source_layer"] == "discovery"
    assert signal["tracking_contract"]["source_layer"] == "tracking"
    assert signal["entry_contract"]["source_layer"] == "entry"
    assert signal["tracking_contract"]["decision"] == "tracking_ready_for_entry"
    assert signal["entry_contract"]["decision"] == "entry_ready"


def test_m3_nucleus_tracking_runtime_records_start_promote_and_drop() -> None:
    engine = _make_runtime_engine()
    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)
    runtime_state: dict[str, dict] = {}

    candidate = {
        "code": "600001",
        "name": "成熟龙头",
        "sector": "AI",
        "buy_score": 92.0,
        "wave_phase": "3浪",
        "role": "龙头",
        "reasons": ["成熟候选"],
        "candidate_tier": "execution_eligible",
        "entry_ready": True,
    }

    first = engine._record_tracking_candidate_events(
        current_date=day1,
        signals={"candidate_signals": [candidate]},
        tracking_runtime_state=runtime_state,
        positions={},
    )
    second = engine._record_tracking_candidate_events(
        current_date=day2,
        signals={"candidate_signals": [candidate]},
        tracking_runtime_state=runtime_state,
        positions={},
    )
    third = engine._record_tracking_candidate_events(
        current_date=day3,
        signals={"candidate_signals": []},
        tracking_runtime_state=runtime_state,
        positions={},
    )

    assert first == []
    assert len(second) == 1
    assert second[0]["tracking_ready"] is True
    assert third == []

    events = [row["event"] for row in engine._buy_signal_audit_current_run]
    assert events == [
        "tracking_started",
        "tracking_promoted_to_entry",
        "tracking_dropped",
    ]
    promoted = engine._buy_signal_audit_current_run[1]
    dropped = engine._buy_signal_audit_current_run[2]
    assert promoted["tracking_state"] == "tracking_mature"
    assert promoted["tracking_days"] == 2
    assert promoted["source_layer"] == "tracking"
    assert dropped["tracking_state"] == "tracking_dropped"
    assert dropped["tracking_transition_reason"] == "candidate_missing_from_current_tracking_set"


def test_m3_nucleus_exit_chain_keeps_thesis_invalidation_priority() -> None:
    engine = _make_sell_engine(
        price=94.0,
        market_exit_snapshot=_market_exit_hit_snapshot(),
        sector_exit_snapshot={
            "scope": "sector",
            "sector": "AI",
            "condition_pass": True,
            "trend_state": "diverging",
            "evidence_count": 2,
            "details": "板块见顶确认候选：AI | 趋势=diverging | 跟随股弱势70% | 龙头强度48%",
        },
    )
    trade = _make_trade(role="龙头", peak_price=120.0)
    trade.buy_date = "2026-06-16"

    sell = engine.check_sell_signal_v2(trade, date(2026, 6, 18))

    assert sell is not None
    assert sell.reason == "thesis_invalidated"
    assert sell.source_layer == "invalidation"
    assert sell.invalidated_reason == "entry_stop_loss"
    assert trade.market_exit_state == ""
    assert trade.sector_exit_state == ""


def test_m3_nucleus_run_backtest_keeps_core_runtime_outputs() -> None:
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
    engine.get_config_snapshot = lambda: {"version": "m3-nucleus"}
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

    assert result["config_snapshot"] == {"version": "m3-nucleus"}
    assert result["execution_action_summary"] == {"buy": 1}
    events = [row["event"] for row in result["buy_signal_audit"]]
    assert events.count("tracking_started") == 2
    assert "tracking_promoted_to_entry" in events
    assert "tracking_dropped" in events
    assert "buy_executed" in events
    assert len(result["trades"]) == 1
    assert result["trades"][0]["code"] == "600001"
