from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import lowfreq_engine_v16_advanced as lowfreq_engine_module
from lowfreq_engine_v16_advanced import (
    LowFreqTradingEngineV16,
    LowFreqV16Config,
    SellSignal,
    StockCandidate,
    WavePhase,
)
from neotrade3.cycle_intelligence.legacy_recognition import apply_strong_leader_soft_release


class _FakeConn:
    def cursor(self):
        return object()

    def close(self):
        return None


class _GlobalCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *_args, **_kwargs):
        return self

    def fetchall(self):
        return list(self._rows)


class _GlobalConn:
    def __init__(self, rows):
        self._cursor = _GlobalCursor(rows)

    def cursor(self):
        return self._cursor

    def close(self):
        return None


class _SingleRowCursor:
    def __init__(self, row):
        self._row = row

    def execute(self, *_args, **_kwargs):
        return self

    def fetchone(self):
        return self._row


def _make_engine() -> LowFreqTradingEngineV16:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.MARKET_FILTER_ENABLED = False
    engine.HOT_SECTOR_COUNT = 5
    engine.HOT_SECTOR_CANDIDATE_LIMIT = 4
    engine.BUY_THRESHOLD = 85.0
    engine.MIN_RESONANCE = 0.7
    engine.CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS = 0.0
    engine.CROSS_SECTOR_SCAN_ENABLED = True
    engine.CROSS_SECTOR_MAX_SIGNALS = 2
    engine.CROSS_SECTOR_CANDIDATE_TOP_N = 40
    engine.CROSS_SECTOR_WAVE3_ONLY = True
    engine.CROSS_SECTOR_ALLOW_WAVE1 = True
    engine.WAVE1_TRACKING_ONLY_ENABLED = True
    engine.STRONG_LEADER_SOFT_RELEASE_ENABLED = False
    engine.CROSS_SECTOR_SCORE_MARGIN = 8.0
    engine._conn = lambda: _FakeConn()
    return engine

def test_calc_metrics_clamps_annual_return_when_total_return_below_negative_100() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)

    metrics = engine._calc_metrics(
        [
            {"date": "2026-06-01", "total_value": 1_000_000.0},
            {"date": "2026-06-02", "total_value": -500_000.0},
        ],
        [],
        1_000_000.0,
    )

    assert metrics["final_value"] == -500000.0
    assert metrics["total_return_pct"] == -150.0
    assert metrics["annual_return_pct"] == -100.0
    assert metrics["total_trades"] == 0
    assert metrics["sell_reasons"] == {}


def test_cup_handle_picks_prefers_local_artifact(tmp_path: Path) -> None:
    artifact_path = (
        tmp_path
        / "var"
        / "artifacts"
        / "screener_runs"
        / "2026-06-18"
        / "screener_cup_handle_v4_result.json"
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "picks": [
                    "000887",
                    {"code": "300024.SZ"},
                    {"code": "bad"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.CUP_HANDLE_ENABLED = True
    engine.project_root = tmp_path
    engine._cup_handle_cache = {}

    picks = engine._cup_handle_picks(date(2026, 6, 18))

    assert picks == {"000887", "300024"}


def test_generate_buy_signals_uses_relaxed_convergence_settings() -> None:
    engine = _make_engine()
    seen: dict[str, int] = {}

    def _get_hot_sectors(target_date, top_n, cursor=None):
        return [SimpleNamespace(sector="C39", heat_score=80.0)]

    def _get_sector_candidates(sector, target_date, top_n, cursor=None):
        seen["sector_top_n"] = int(top_n)
        return []

    def _get_global_candidates(target_date, top_n=10, exclude_sectors=None, exclude_codes=None):
        seen["global_top_n"] = int(top_n)
        return [
            StockCandidate(
                code="600460",
                name="士兰微",
                sector="C39",
                market_cap_yi=320.0,
                role="龙头",
                buy_score=96.0,
                buy_reasons=["跨板块样本"],
                wave_phase=WavePhase.WAVE_1.value,
                sector_resonance=0.9,
            )
        ]

    engine.get_hot_sectors = _get_hot_sectors
    engine.get_sector_candidates = _get_sector_candidates
    engine.get_global_candidates = _get_global_candidates

    out = engine.generate_buy_signals(SimpleNamespace(isoformat=lambda: "2026-06-15"))

    assert seen["sector_top_n"] == 4
    assert seen["global_top_n"] == 40
    assert out["buy_signals"] == []
    assert [row["code"] for row in out["candidate_signals"]] == ["600460"]
    assert out["entry_signals"] == []
    assert out["signal_summary"]["candidate_count"] == 1
    assert out["signal_summary"]["entry_count"] == 0
    candidate = out["candidate_signals"][0]
    assert candidate["tracking_ready"] is False
    assert candidate["tracking_state"] == "tracking_observe"
    assert candidate["tracking_days"] == 1
    assert candidate["tracking_transition_reason"] == "candidate_retained_for_tracking"
    assert candidate["tracking_contract"]["source_layer"] == "tracking"
    assert candidate["tracking_contract"]["decision"] == "tracking_continue"
    assert candidate["candidate_tier"] == "soft_retained"
    assert "capture-first: 1浪仅保留 tracking，不进入正式建仓" in candidate["reasons"]


def test_generate_buy_signals_keeps_wave1_as_soft_penalty_when_disabled() -> None:
    engine = _make_engine()
    engine.CROSS_SECTOR_ALLOW_WAVE1 = False
    engine.get_hot_sectors = lambda target_date, top_n, cursor=None: [SimpleNamespace(sector="C39", heat_score=80.0)]
    engine.get_sector_candidates = lambda sector, target_date, top_n, cursor=None: []
    engine.get_global_candidates = lambda target_date, top_n=10, exclude_sectors=None, exclude_codes=None: [
        StockCandidate(
            code="600460",
            name="士兰微",
            sector="C39",
            market_cap_yi=320.0,
            role="龙头",
            buy_score=96.0,
            buy_reasons=["跨板块样本"],
            wave_phase=WavePhase.WAVE_1.value,
            sector_resonance=0.9,
        )
    ]

    out = engine.generate_buy_signals(SimpleNamespace(isoformat=lambda: "2026-06-15"))

    assert out["buy_signals"] == []
    assert [row["code"] for row in out["candidate_signals"]] == ["600460"]
    assert out["entry_signals"] == []
    assert out["candidate_signals"][0]["entry_ready"] is False
    assert out["candidate_signals"][0]["candidate_tier"] == "soft_retained"
    assert out["candidate_signals"][0]["tracking_ready"] is False
    assert out["candidate_signals"][0]["tracking_state"] == "tracking_observe"
    assert out["candidate_signals"][0]["tracking_days"] == 1
    assert out["candidate_signals"][0]["tracking_transition_reason"] == "candidate_retained_for_tracking"
    assert out["candidate_signals"][0]["tracking_contract"]["source_layer"] == "tracking"
    assert out["candidate_signals"][0]["tracking_contract"]["decision"] == "tracking_continue"
    assert "capture-first: 波段不符，降权保留" in out["candidate_signals"][0]["reasons"]
    assert out["signal_summary"]["soft_retained_count"] == 1


def test_generate_buy_signals_allows_two_cross_sector_signals() -> None:
    engine = _make_engine()
    engine.get_hot_sectors = lambda target_date, top_n, cursor=None: [SimpleNamespace(sector="C39", heat_score=80.0)]
    engine.get_sector_candidates = lambda sector, target_date, top_n, cursor=None: []
    engine.get_global_candidates = lambda target_date, top_n=10, exclude_sectors=None, exclude_codes=None: [
        StockCandidate(
            code="600460",
            name="士兰微",
            sector="C39",
            market_cap_yi=320.0,
            role="龙头",
            buy_score=98.0,
            buy_reasons=["跨板块样本1"],
            wave_phase=WavePhase.WAVE_1.value,
            sector_resonance=0.9,
        ),
        StockCandidate(
            code="300308",
            name="中际旭创",
            sector="C40",
            market_cap_yi=330.0,
            role="龙头",
            buy_score=101.0,
            buy_reasons=["跨板块样本2"],
            wave_phase=WavePhase.WAVE_3.value,
            sector_resonance=0.85,
        ),
    ]

    out = engine.generate_buy_signals(SimpleNamespace(isoformat=lambda: "2026-06-15"))

    assert [row["code"] for row in out["buy_signals"]] == ["300308"]
    assert [row["code"] for row in out["candidate_signals"]] == ["300308", "600460"]
    assert [row["code"] for row in out["entry_signals"]] == ["300308"]


def test_generate_buy_signals_no_longer_hard_caps_cross_sector_signal_count() -> None:
    engine = _make_engine()
    engine.get_hot_sectors = lambda target_date, top_n, cursor=None: [SimpleNamespace(sector="C39", heat_score=80.0)]
    engine.get_sector_candidates = lambda sector, target_date, top_n, cursor=None: []
    engine.get_global_candidates = lambda target_date, top_n=10, exclude_sectors=None, exclude_codes=None: [
        StockCandidate(
            code="600460",
            name="士兰微",
            sector="C39",
            market_cap_yi=320.0,
            role="龙头",
            buy_score=98.0,
            buy_reasons=["跨板块样本1"],
            wave_phase=WavePhase.WAVE_1.value,
            sector_resonance=0.9,
        ),
        StockCandidate(
            code="300308",
            name="中际旭创",
            sector="C40",
            market_cap_yi=330.0,
            role="龙头",
            buy_score=101.0,
            buy_reasons=["跨板块样本2"],
            wave_phase=WavePhase.WAVE_3.value,
            sector_resonance=0.85,
        ),
        StockCandidate(
            code="300394",
            name="天孚通信",
            sector="C41",
            market_cap_yi=340.0,
            role="龙头",
            buy_score=103.0,
            buy_reasons=["跨板块样本3"],
            wave_phase=WavePhase.WAVE_3.value,
            sector_resonance=0.88,
        ),
    ]

    out = engine.generate_buy_signals(SimpleNamespace(isoformat=lambda: "2026-06-15"))

    assert [row["code"] for row in out["buy_signals"]] == ["300394", "300308"]
    assert [row["code"] for row in out["entry_signals"]] == ["300394", "300308"]


def test_run_backtest_executes_pending_buys_in_score_order() -> None:
    class _FakeCursor:
        pass

    class _FakeConn2:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXECUTION_MODE = "bounded"
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 1
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine._conn = lambda: _FakeConn2()
    engine._get_trading_dates = lambda start, end: [start, start + timedelta(days=1)]
    engine._count_trading_days = lambda start, end: 2
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine._get_bar = lambda cursor, code, d: {"close": 10.0, "pct_change": 0.0, "amount": 1e9}
    engine.get_config_snapshot = lambda: {}
    engine.generate_buy_signals = lambda current_date: {
        "buy_signals": [
            {"code": "600001", "name": "低分", "sector": "A", "buy_score": 90.0, "wave_phase": "1浪", "role": "龙头"},
            {"code": "300001", "name": "高分", "sector": "B", "buy_score": 100.0, "wave_phase": "3浪", "role": "龙头"},
        ]
    }

    result = engine.run_backtest(
        date(2026, 6, 1),
        date(2026, 6, 2),
        initial_capital=100000.0,
        include_trades=True,
    )

    assert [trade["code"] for trade in result["trades"]] == ["300001"]
    assert result["trades"][0]["buy_score"] == 100.0


def test_chase_entry_snapshot_requires_near_high_and_fast_runup() -> None:
    class _PriceCursor:
        def execute(self, *_args, **_kwargs):
            self._rows = [(10.0,), (10.2,), (10.4,), (10.6,), (10.8,), (11.0,), (11.2,), (11.4,), (11.6,), (11.8,)]
            return self

        def fetchall(self):
            return list(self._rows)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.CHASE_ENTRY_BLOCK_ENABLED = True
    engine.CHASE_ENTRY_NEAR_HIGH_RATIO = 0.98
    engine.CHASE_ENTRY_PRE3_RUNUP_PCT = 8.0
    engine.CHASE_ENTRY_PRE5_RUNUP_PCT = 12.0

    blocked = engine._chase_entry_snapshot(
        _PriceCursor(),
        code="300001",
        target_date=date(2026, 6, 18),
        ref_price=11.7,
    )
    allowed = engine._chase_entry_snapshot(
        _PriceCursor(),
        code="300001",
        target_date=date(2026, 6, 18),
        ref_price=11.1,
    )

    assert blocked is not None and blocked["blocked"] is True
    assert blocked["near_high_flag"] is True
    assert blocked["recent_runup_flag"] is True
    assert allowed is not None and allowed["blocked"] is False


def test_run_backtest_blocks_chase_entry_at_final_queue() -> None:
    class _FakeCursor:
        pass

    class _FakeConn2:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXECUTION_MODE = "bounded"
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 1
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine._conn = lambda: _FakeConn2()
    engine._get_trading_dates = lambda start, end: [start, start + timedelta(days=1)]
    engine._count_trading_days = lambda start, end: 2
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine._get_bar = lambda cursor, code, d: {"close": 10.0, "pct_change": 0.0, "amount": 1e9}
    engine.get_config_snapshot = lambda: {}
    engine.generate_buy_signals = lambda current_date: {
        "buy_signals": [
            {"code": "600001", "name": "低分", "sector": "A", "buy_score": 90.0, "wave_phase": "1浪", "role": "龙头"},
            {"code": "300001", "name": "高分", "sector": "B", "buy_score": 100.0, "wave_phase": "3浪", "role": "龙头"},
        ]
    }
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: (
        {
            "blocked": True,
            "near_high_flag": True,
            "recent_runup_flag": True,
            "near_5d_high": True,
            "near_10d_high": True,
            "pre3_return_pct": 9.5,
            "pre5_return_pct": 14.0,
            "details": "追高型买点硬禁",
        }
        if str(code) == "300001"
        else {"blocked": False}
    )

    result = engine.run_backtest(
        date(2026, 6, 1),
        date(2026, 6, 2),
        initial_capital=100000.0,
        include_trades=True,
    )

    assert [trade["code"] for trade in result["trades"]] == ["600001"]
    assert result["trade_blocks"]["buy_chase_entry_blocked"] == 1
    assert result["buy_signal_audit"][0]["event"] == "chase_entry_blocked"
    assert result["buy_signal_audit"][0]["code"] == "300001"


def test_run_backtest_blocks_weak_soft_signal_at_execution_queue() -> None:
    class _FakeCursor:
        pass

    class _FakeConn2:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXECUTION_MODE = "bounded"
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 2
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = True
    engine.EXECUTION_FOLLOWER_MIN_BUY_SCORE = 75.0
    engine.EXECUTION_UNKNOWN_WAVE_MIN_BUY_SCORE = 80.0
    engine._conn = lambda: _FakeConn2()
    engine._get_trading_dates = lambda start, end: [day1, day2, day3]
    engine._count_trading_days = lambda start, end: 2
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine._get_bar = lambda cursor, code, d: {"close": 10.0, "pct_change": 0.0, "amount": 1e9}
    engine.get_config_snapshot = lambda: {}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}

    def _signals(current_date):
        if current_date == day1:
            return {
                "buy_signals": [
                    {
                        "code": "600001",
                        "name": "弱跟随",
                        "sector": "A",
                        "buy_score": 60.0,
                        "wave_phase": "未知",
                        "role": "跟随",
                    }
                ]
            }
        if current_date == day2:
            return {
                "buy_signals": [
                    {
                        "code": "300001",
                        "name": "强龙头",
                        "sector": "B",
                        "buy_score": 92.0,
                        "wave_phase": "3浪",
                        "role": "龙头",
                    }
                ]
            }
        return {"buy_signals": []}

    engine.generate_buy_signals = _signals

    result = engine.run_backtest(
        day1,
        day3,
        initial_capital=100000.0,
        include_trades=True,
    )

    assert [trade["code"] for trade in result["trades"]] == ["300001"]
    assert result["trade_blocks"]["buy_execution_signal_gate_blocked"] == 2
    assert result["buy_signal_audit"][0]["event"] == "execution_signal_gate_blocked"
    assert result["buy_signal_audit"][0]["code"] == "600001"


def test_run_backtest_allows_strong_unknown_wave_leader() -> None:
    class _FakeCursor:
        pass

    class _FakeConn2:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXECUTION_MODE = "bounded"
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 1
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = True
    engine.EXECUTION_FOLLOWER_MIN_BUY_SCORE = 75.0
    engine.EXECUTION_UNKNOWN_WAVE_MIN_BUY_SCORE = 80.0
    engine._conn = lambda: _FakeConn2()
    engine._get_trading_dates = lambda start, end: [day1, day2, day3]
    engine._count_trading_days = lambda start, end: 2
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine._get_bar = lambda cursor, code, d: {"close": 10.0, "pct_change": 0.0, "amount": 1e9}
    engine.get_config_snapshot = lambda: {}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}
    engine.generate_buy_signals = lambda current_date: {
        "buy_signals": [
            {
                "code": "300001",
                "name": "高分未知波段龙头",
                "sector": "B",
                "buy_score": 82.0,
                "wave_phase": "未知",
                "role": "龙头",
            }
        ]
    }

    result = engine.run_backtest(
        day1,
        day2,
        initial_capital=100000.0,
        include_trades=True,
    )

    assert [trade["code"] for trade in result["trades"]] == ["300001"]
    assert result["trade_blocks"]["buy_execution_signal_gate_blocked"] == 0


def test_run_backtest_reserves_elite_signal_and_releases_when_slot_opens() -> None:
    class _FakeCursor:
        pass

    class _FakeConn2:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)
    day4 = day3 + timedelta(days=1)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXECUTION_MODE = "bounded"
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 2
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = True
    engine.EXECUTION_FOLLOWER_MIN_BUY_SCORE = 75.0
    engine.EXECUTION_UNKNOWN_WAVE_MIN_BUY_SCORE = 80.0
    engine.EXECUTION_ELITE_MIN_BUY_SCORE = 80.0
    engine.EXECUTION_ELITE_UNKNOWN_LEADER_MIN_BUY_SCORE = 90.0
    engine.EXECUTION_RESERVATION_ENABLED = True
    engine.EXECUTION_RESERVATION_MEMORY_DAYS = 2
    engine._conn = lambda: _FakeConn2()
    engine._get_trading_dates = lambda start, end: [day1, day2, day3, day4]
    engine._count_trading_days = lambda start, end: 4
    engine.check_sell_signal_v2 = lambda trade, current_date: (
        SellSignal(reason="slot_opened", confidence=1.0, details="释放 reserved 槽位")
        if str(trade.code) == "600001" and current_date == day4
        else None
    )
    engine._get_bar = lambda cursor, code, d: {"close": 10.0, "pct_change": 0.0, "amount": 1e9}
    engine.get_config_snapshot = lambda: {}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}

    def _signals(current_date):
        if current_date == day1:
            return {
                "buy_signals": [
                    {
                        "code": "600001",
                        "name": "旧持仓",
                        "sector": "A",
                        "buy_score": 88.0,
                        "wave_phase": "1浪",
                        "role": "龙头",
                    }
                ]
            }
        if current_date == day2:
            return {
                "buy_signals": [
                    {
                        "code": "300001",
                        "name": "预留龙头",
                        "sector": "B",
                        "buy_score": 95.0,
                        "wave_phase": "3浪",
                        "role": "龙头",
                    }
                ]
            }
        return {"buy_signals": []}

    engine.generate_buy_signals = _signals

    result = engine.run_backtest(
        day1,
        day4,
        initial_capital=100000.0,
        include_trades=True,
    )

    assert result["trade_blocks"]["buy_reserved_due_to_full_book"] == 1
    assert result["trade_blocks"]["buy_reserved_released_into_buy"] == 1
    assert result["trade_blocks"]["buy_reserved_expired"] == 0
    assert {trade["code"] for trade in result["trades"]} == {"600001", "300001"}
    released_trade = next(trade for trade in result["trades"] if trade["code"] == "300001")
    assert released_trade["buy_date"] == day4.isoformat()
    assert released_trade["sell_reason"] == "回测结束平仓"
    assert released_trade["status"] == "closed"

    reservation_created = next(
        row for row in result["buy_signal_audit"] if row["event"] == "reservation_created"
    )
    reservation_released = next(
        row for row in result["buy_signal_audit"] if row["event"] == "reservation_released_into_buy"
    )
    direct_buy = next(row for row in result["buy_signal_audit"] if row["event"] == "buy_executed")
    assert reservation_created["code"] == "300001"
    assert reservation_created["date"] == day3.isoformat()
    assert reservation_created["signal_date"] == day2.isoformat()
    assert reservation_created["source_layer"] == "execution"
    assert reservation_created["action_type"] == "reserve"
    assert reservation_created["order_action"] == "block"
    assert reservation_created["reserve_action"] == "reserve"
    assert reservation_created["funnel_stage"] == "reserved"
    assert reservation_created["execution_block_reason"] == "positions_full"
    assert reservation_released["code"] == "300001"
    assert reservation_released["date"] == day4.isoformat()
    assert reservation_released["action_type"] == "buy"
    assert reservation_released["order_action"] == "buy"
    assert reservation_released["reserve_action"] == "release"
    assert reservation_released["position_delta"] == 10000
    assert reservation_released["funnel_stage"] == "released"
    assert direct_buy["code"] == "600001"
    assert direct_buy["action_type"] == "buy"
    assert direct_buy["order_action"] == "buy"
    assert direct_buy["reserve_action"] == ""
    assert result["execution_action_keys"] == ["buy", "reserve", "release", "hold", "exit", "block"]
    assert result["execution_action_summary"]["reserve"] == 1
    assert result["execution_action_summary"]["buy"] == 2
    assert result["funnel_stage_keys"] == [
        "candidate_detected",
        "entry_ready",
        "reserved",
        "released",
        "bought",
        "hold_confirmed",
        "exit_ready",
        "exited",
        "blocked",
        "expired",
    ]


def test_run_backtest_expires_reserved_elite_signal_when_slot_never_opens() -> None:
    class _FakeCursor:
        pass

    class _FakeConn2:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)
    day4 = day3 + timedelta(days=1)
    day5 = day4 + timedelta(days=1)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXECUTION_MODE = "bounded"
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 2
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = True
    engine.EXECUTION_FOLLOWER_MIN_BUY_SCORE = 75.0
    engine.EXECUTION_UNKNOWN_WAVE_MIN_BUY_SCORE = 80.0
    engine.EXECUTION_ELITE_MIN_BUY_SCORE = 80.0
    engine.EXECUTION_ELITE_UNKNOWN_LEADER_MIN_BUY_SCORE = 90.0
    engine.EXECUTION_RESERVATION_ENABLED = True
    engine.EXECUTION_RESERVATION_MEMORY_DAYS = 1
    engine._conn = lambda: _FakeConn2()
    engine._get_trading_dates = lambda start, end: [day1, day2, day3, day4, day5]
    engine._count_trading_days = lambda start, end: 5
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine._get_bar = lambda cursor, code, d: {"close": 10.0, "pct_change": 0.0, "amount": 1e9}
    engine.get_config_snapshot = lambda: {}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}

    def _signals(current_date):
        if current_date == day1:
            return {
                "buy_signals": [
                    {
                        "code": "600001",
                        "name": "旧持仓",
                        "sector": "A",
                        "buy_score": 88.0,
                        "wave_phase": "1浪",
                        "role": "龙头",
                    }
                ]
            }
        if current_date == day2:
            return {
                "buy_signals": [
                    {
                        "code": "300001",
                        "name": "过期预留龙头",
                        "sector": "B",
                        "buy_score": 95.0,
                        "wave_phase": "3浪",
                        "role": "龙头",
                    }
                ]
            }
        return {"buy_signals": []}

    engine.generate_buy_signals = _signals

    result = engine.run_backtest(
        day1,
        day5,
        initial_capital=100000.0,
        include_trades=True,
    )

    assert [trade["code"] for trade in result["trades"]] == ["600001"]
    assert result["trade_blocks"]["buy_reserved_due_to_full_book"] == 1
    assert result["trade_blocks"]["buy_reserved_expired"] == 1
    assert result["trade_blocks"]["buy_reserved_released_into_buy"] == 0

    reservation_expired = next(
        row for row in result["buy_signal_audit"] if row["event"] == "reservation_expired"
    )
    assert reservation_expired["code"] == "300001"
    assert reservation_expired["date"] == day5.isoformat()
    assert reservation_expired["signal_date"] == day2.isoformat()
    assert reservation_expired["action_type"] == "block"
    assert reservation_expired["order_action"] == "block"
    assert reservation_expired["reserve_action"] == "expire"
    assert reservation_expired["execution_block_reason"] == "entry_window_missed"
    assert reservation_expired["funnel_stage"] == "expired"


def test_run_backtest_does_not_reserve_non_elite_signals_when_book_is_full() -> None:
    class _FakeCursor:
        pass

    class _FakeConn2:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)
    day4 = day3 + timedelta(days=1)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXECUTION_MODE = "bounded"
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 2
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = True
    engine.EXECUTION_FOLLOWER_MIN_BUY_SCORE = 75.0
    engine.EXECUTION_UNKNOWN_WAVE_MIN_BUY_SCORE = 80.0
    engine.EXECUTION_ELITE_MIN_BUY_SCORE = 80.0
    engine.EXECUTION_ELITE_UNKNOWN_LEADER_MIN_BUY_SCORE = 90.0
    engine.EXECUTION_RESERVATION_ENABLED = True
    engine.EXECUTION_RESERVATION_MEMORY_DAYS = 2
    engine._conn = lambda: _FakeConn2()
    engine._get_trading_dates = lambda start, end: [day1, day2, day3, day4]
    engine._count_trading_days = lambda start, end: 4
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine._get_bar = lambda cursor, code, d: {"close": 10.0, "pct_change": 0.0, "amount": 1e9}
    engine.get_config_snapshot = lambda: {}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}

    def _signals(current_date):
        if current_date == day1:
            return {
                "buy_signals": [
                    {
                        "code": "600001",
                        "name": "旧持仓",
                        "sector": "A",
                        "buy_score": 88.0,
                        "wave_phase": "1浪",
                        "role": "龙头",
                    }
                ]
            }
        if current_date == day2:
            return {
                "buy_signals": [
                    {
                        "code": "300001",
                        "name": "高分跟随",
                        "sector": "B",
                        "buy_score": 88.0,
                        "wave_phase": "3浪",
                        "role": "跟随",
                    },
                    {
                        "code": "300002",
                        "name": "带软标记龙头",
                        "sector": "C",
                        "buy_score": 95.0,
                        "wave_phase": "3浪",
                        "role": "龙头",
                        "soft_flags": ["history_short"],
                    },
                    {
                        "code": "300003",
                        "name": "低分未知波段龙头",
                        "sector": "D",
                        "buy_score": 85.0,
                        "wave_phase": "未知",
                        "role": "龙头",
                    },
                ]
            }
        return {"buy_signals": []}

    engine.generate_buy_signals = _signals

    result = engine.run_backtest(
        day1,
        day4,
        initial_capital=100000.0,
        include_trades=True,
    )

    assert [trade["code"] for trade in result["trades"]] == ["600001"]
    assert result["trade_blocks"]["buy_reserved_due_to_full_book"] == 0
    assert result["trade_blocks"]["buy_reserved_expired"] == 0
    assert result["trade_blocks"]["buy_reserved_released_into_buy"] == 0
    assert not any(
        row["event"] == "reservation_created" and row["code"] in {"300001", "300002", "300003"}
        for row in result["buy_signal_audit"]
    )


def test_run_backtest_uses_end_flattened_cash_for_final_metrics() -> None:
    class _FakeCursor:
        pass

    class _FakeConn2:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXECUTION_MODE = "bounded"
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 1
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = False
    engine.EXECUTION_RESERVATION_ENABLED = False
    engine._conn = lambda: _FakeConn2()
    engine._get_trading_dates = lambda start, end: [day1, day2, day3]
    engine._count_trading_days = lambda start, end: 3
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine.get_config_snapshot = lambda: {}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}
    engine._slippage_adjust_price = (
        lambda price, side: float(price) if side == "buy" else float(price) - 1.0
    )

    def _get_bar(cursor, code, d):
        if d in {day1, day2}:
            return {"close": 10.0, "pct_change": 0.0, "amount": 1e9}
        return {"close": 11.0, "pct_change": 0.0, "amount": 1e9}

    engine._get_bar = _get_bar
    engine.generate_buy_signals = lambda current_date: (
        {
            "buy_signals": [
                {
                    "code": "600001",
                    "name": "尾盘持仓",
                    "sector": "A",
                    "buy_score": 90.0,
                    "wave_phase": "3浪",
                    "role": "龙头",
                }
            ]
        }
        if current_date == day1
        else {"buy_signals": []}
    )

    result = engine.run_backtest(
        day1,
        day3,
        initial_capital=100000.0,
        include_daily_values=True,
        include_trades=True,
    )

    gross_daily = result["daily_values_gross"]
    net_daily = result["daily_values_net"]
    assert gross_daily[-1]["date"] == day3.isoformat()
    assert gross_daily[-1]["positions"] == 0
    assert result["final_value"] == gross_daily[-1]["total_value"]
    assert result["net_metrics"]["final_value"] == net_daily[-1]["total_value"]
    assert result["net_metrics"]["final_value"] < gross_daily[-1]["total_value"]
    closed_trade = next(trade for trade in result["trades"] if trade["code"] == "600001")
    assert closed_trade["sell_reason"] == "回测结束平仓"


def test_run_backtest_unbounded_mode_executes_all_entry_opportunities_without_full_book_or_cash_blocks() -> None:
    class _FakeCursor:
        pass

    class _FakeConn2:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 1
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = False
    engine.EXECUTION_RESERVATION_ENABLED = True
    engine._conn = lambda: _FakeConn2()
    engine._get_trading_dates = lambda start, end: [day1, day2]
    engine._count_trading_days = lambda start, end: 2
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine._get_bar = lambda cursor, code, d: {"close": 10.0, "pct_change": 0.0, "amount": 1e9}
    engine.get_config_snapshot = lambda: {"execution_mode": "unbounded_opportunity"}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}
    engine.generate_buy_signals = lambda current_date: {
        "buy_signals": [
            {"code": "600001", "name": "机会一", "sector": "A", "buy_score": 90.0, "wave_phase": "1浪", "role": "龙头"},
            {"code": "300001", "name": "机会二", "sector": "B", "buy_score": 100.0, "wave_phase": "3浪", "role": "龙头"},
        ]
    }

    result = engine.run_backtest(
        day1,
        day2,
        initial_capital=1000.0,
        include_trades=True,
    )

    assert {trade["code"] for trade in result["trades"]} == {"600001", "300001"}
    assert result["trade_blocks"]["buy_reserved_due_to_full_book"] == 0
    assert result["trade_blocks"]["buy_insufficient_cash"] == 0
    assert result["execution_action_summary"]["buy"] == 2
    assert result["config_snapshot"]["execution_mode"] == "unbounded_opportunity"


def test_run_backtest_maps_min_amount_block_reason_into_trade_blocks() -> None:
    class _FakeCursor:
        pass

    class _FakeConn2:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXECUTION_MODE = "bounded"
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 1
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = False
    engine.EXECUTION_RESERVATION_ENABLED = False
    engine.EXEC_MIN_AMOUNT_CNY = 1e6
    engine.EXEC_MAX_PARTICIPATION_RATE = 1.0
    engine._conn = lambda: _FakeConn2()
    engine._get_trading_dates = lambda start, end: [day1, day2]
    engine._count_trading_days = lambda start, end: 2
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine._get_bar = lambda cursor, code, d: {
        "close": 10.0,
        "high": 10.2,
        "low": 9.8,
        "pct_change": 1.0,
        "amount": 5e5,
    }
    engine.get_config_snapshot = lambda: {}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}
    engine.generate_buy_signals = lambda current_date: (
        {
            "buy_signals": [
                {
                    "code": "300001",
                    "name": "低成交额样本",
                    "sector": "B",
                    "buy_score": 92.0,
                    "wave_phase": "3浪",
                    "role": "龙头",
                }
            ]
        }
        if current_date == day1
        else {"buy_signals": []}
    )

    result = engine.run_backtest(
        day1,
        day2,
        initial_capital=100000.0,
        include_trades=True,
    )

    assert result["trades"] == []
    assert result["trade_blocks"]["buy_min_amount"] == 1
    assert result["trade_blocks"]["buy_participation_rate"] == 0


def test_run_backtest_maps_participation_rate_block_reason_into_trade_blocks() -> None:
    class _FakeCursor:
        pass

    class _FakeConn2:
        def cursor(self):
            return _FakeCursor()

        def close(self):
            return None

    day1 = date(2026, 6, 1)
    day2 = day1 + timedelta(days=1)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXECUTION_MODE = "bounded"
    engine.MAX_POSITIONS = 1
    engine.BUY_SIGNAL_MEMORY_DAYS = 1
    engine.REBALANCE_DAYS = 1
    engine.COMMISSION_RATE = 0.0
    engine.STAMP_TAX_RATE = 0.0
    engine.SLIPPAGE_BPS = 0.0
    engine.MIN_COMMISSION = 0.0
    engine.EXECUTION_SIGNAL_GATE_ENABLED = False
    engine.EXECUTION_RESERVATION_ENABLED = False
    engine.EXEC_MIN_AMOUNT_CNY = 0.0
    engine.EXEC_MAX_PARTICIPATION_RATE = 0.5
    engine._conn = lambda: _FakeConn2()
    engine._get_trading_dates = lambda start, end: [day1, day2]
    engine._count_trading_days = lambda start, end: 2
    engine.check_sell_signal_v2 = lambda trade, current_date: None
    engine._get_bar = lambda cursor, code, d: {
        "close": 10.0,
        "high": 10.2,
        "low": 9.8,
        "pct_change": 1.0,
        "amount": 1e6,
    }
    engine.get_config_snapshot = lambda: {}
    engine._chase_entry_snapshot = lambda cursor, code, target_date, ref_price: {"blocked": False}
    engine.generate_buy_signals = lambda current_date: (
        {
            "buy_signals": [
                {
                    "code": "300001",
                    "name": "高参与率样本",
                    "sector": "B",
                    "buy_score": 92.0,
                    "wave_phase": "3浪",
                    "role": "龙头",
                }
            ]
        }
        if current_date == day1
        else {"buy_signals": []}
    )

    result = engine.run_backtest(
        day1,
        day2,
        initial_capital=1000000.0,
        include_trades=True,
    )

    assert result["trades"] == []
    assert result["trade_blocks"]["buy_min_amount"] == 0
    assert result["trade_blocks"]["buy_participation_rate"] == 1


def test_strong_leader_soft_release_clears_focus_and_structure_soft_flags() -> None:

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.STRONG_LEADER_SOFT_RELEASE_ENABLED = True

    score, soft_flags, reasons = apply_strong_leader_soft_release(
        score=83.5,
        role="龙头",
        wave_phase=WavePhase.WAVE_3.value,
        soft_flags=["structure_soft_fail", "focus_soft_fail"],
        reasons=[
            "3浪主升浪",
            "capture-first: 结构未确认，降权保留",
            "capture-first: focus gate 未过，降权保留",
            "soft:weekly_breakout_not_confirmed",
            "soft:未同时满足核心范围、配置高配与细分赛道龙头闸门",
        ],
        release_enabled=engine.STRONG_LEADER_SOFT_RELEASE_ENABLED,
        release_min_score=engine.EXECUTION_ELITE_MIN_BUY_SCORE,
    )

    assert score == 101.5
    assert soft_flags == []
    assert "capture-first: 结构未确认，降权保留" not in reasons
    assert "capture-first: focus gate 未过，降权保留" not in reasons
    assert "soft:weekly_breakout_not_confirmed" not in reasons
    assert "soft:未同时满足核心范围、配置高配与细分赛道龙头闸门" not in reasons
    assert any("capture-first: 高分龙头窄例外放行" in row for row in reasons)


def test_strong_leader_soft_release_keeps_other_soft_blockers() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.STRONG_LEADER_SOFT_RELEASE_ENABLED = True
    engine.EXECUTION_ELITE_MIN_BUY_SCORE = 80.0

    score, soft_flags, reasons = apply_strong_leader_soft_release(
        score=96.0,
        role="龙头",
        wave_phase=WavePhase.WAVE_3.value,
        soft_flags=["focus_soft_fail", "wave_uncertain"],
        reasons=[
            "3浪主升浪",
            "capture-first: focus gate 未过，降权保留",
            "capture-first: 波段不符，降权保留",
            "soft:未同时满足核心范围、配置高配与细分赛道龙头闸门",
        ],
        release_enabled=engine.STRONG_LEADER_SOFT_RELEASE_ENABLED,
        release_min_score=engine.EXECUTION_ELITE_MIN_BUY_SCORE,
    )

    assert score == 96.0
    assert soft_flags == ["focus_soft_fail", "wave_uncertain"]
    assert "capture-first: focus gate 未过，降权保留" in reasons
    assert "capture-first: 波段不符，降权保留" in reasons
    assert not any("capture-first: 高分龙头窄例外放行" in row for row in reasons)


def test_strong_leader_soft_release_disabled_by_default() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.STRONG_LEADER_SOFT_RELEASE_ENABLED = False
    engine.EXECUTION_ELITE_MIN_BUY_SCORE = 80.0

    score, soft_flags, reasons = apply_strong_leader_soft_release(
        score=83.5,
        role="龙头",
        wave_phase=WavePhase.WAVE_3.value,
        soft_flags=["structure_soft_fail", "focus_soft_fail"],
        reasons=[
            "3浪主升浪",
            "capture-first: 结构未确认，降权保留",
            "capture-first: focus gate 未过，降权保留",
        ],
        release_enabled=engine.STRONG_LEADER_SOFT_RELEASE_ENABLED,
        release_min_score=engine.EXECUTION_ELITE_MIN_BUY_SCORE,
    )

    assert score == 83.5
    assert soft_flags == ["structure_soft_fail", "focus_soft_fail"]
    assert "capture-first: 结构未确认，降权保留" in reasons
    assert "capture-first: focus gate 未过，降权保留" in reasons
    assert not any("capture-first: 高分龙头窄例外放行" in row for row in reasons)


def test_get_global_candidates_keeps_short_history_candidate_without_crashing(monkeypatch) -> None:
    rows = [
        ("300001", "样本股", "C39", 320e8, 10.0, 3.0, 1e8, 1e7),
    ]
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine._conn = lambda: _GlobalConn(rows)
    engine.CUP_HANDLE_ENABLED = False
    engine.CUP_HANDLE_SCORE_BONUS = 6.0
    engine.MARKET_CAP_MIN = 200e8
    engine.MARKET_CAP_MAX = 500e8
    engine.CROSS_SECTOR_SCAN_LIMIT = 500
    engine.RELATIVE_STRENGTH_BONUS_CAP = 0.0
    engine._cup_handle_picks = lambda target_date: set()
    engine._get_fundamentals_batch = lambda cursor, codes, target_date: {
        "300001": {"pe_ttm": 20.0, "profit_growth": 20.0, "revenue_growth": 15.0, "roe": 10.0, "table_exists": True}
    }
    engine.check_fundamentals = lambda fundamentals: (True, 80.0, ["基本面通过"])
    engine._structure_confirm = lambda code, target_date: {"passed": True, "reasons": ["结构通过"]}
    engine._get_recent_price_history_batch = lambda cursor, codes, target_date, limit=60: {
        "300001": [
            {"close": 10.0 - i * 0.1, "volume": 1000.0 + i, "high": 10.2 - i * 0.1, "low": 9.8 - i * 0.1}
            for i in range(10)
        ]
    }
    engine._resonance_from_closes = lambda closes: 0.5
    engine._weekly_returns_view = lambda code, target_date: {"status": "insufficient"}
    monkeypatch.setattr(
        lowfreq_engine_module,
        "detect_wave_phase_from_series",
        lambda *, closes, highs, lows: (WavePhase.UNKNOWN.value, 0.0),
    )
    monkeypatch.setattr(
        lowfreq_engine_module,
        "passes_core_focus_gate",
        lambda cursor, code, stock_name, role, target_date, market_focus_snapshot_loader: (
            True,
            ["focus通过"],
            {"focus_bonus": 0.0},
        ),
    )

    candidates = engine.get_global_candidates(date(2026, 6, 15), top_n=5)

    assert [candidate.code for candidate in candidates] == ["300001"]
    assert "history_short" in candidates[0].soft_flags


def test_get_bar_rejects_zero_close_row() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    cursor = _SingleRowCursor((0.0, 6.5, 1e9))

    bar = engine._get_bar(cursor, code="301396", d=date(2026, 4, 1))

    assert bar is None


def test_trade_block_reason_blocks_one_price_limit_up_when_enabled() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXEC_BLOCK_ON_LIMIT_UP = True
    engine.EXEC_BLOCK_ON_LIMIT_DOWN = True
    engine.EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT = True
    engine.EXEC_LIMIT_UP_PCT = 9.8
    engine.EXEC_LIMIT_DOWN_PCT = -9.8
    engine.EXEC_MIN_AMOUNT_CNY = 0.0
    engine.EXEC_MAX_PARTICIPATION_RATE = 1.0

    reason = engine._trade_block_reason(
        bar={"close": 10.98, "high": 10.98, "low": 10.98, "pct_change": 10.0, "amount": 1e9},
        side="buy",
        trade_value=1e6,
    )

    assert reason == "limit_up"


def test_trade_block_reason_allows_non_one_price_limit_up_when_enabled() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    engine.EXEC_BLOCK_ON_LIMIT_UP = True
    engine.EXEC_BLOCK_ON_LIMIT_DOWN = True
    engine.EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT = True
    engine.EXEC_LIMIT_UP_PCT = 9.8
    engine.EXEC_LIMIT_DOWN_PCT = -9.8
    engine.EXEC_MIN_AMOUNT_CNY = 0.0
    engine.EXEC_MAX_PARTICIPATION_RATE = 1.0

    reason = engine._trade_block_reason(
        bar={"close": 10.98, "high": 11.2, "low": 10.5, "pct_change": 10.0, "amount": 1e9},
        side="buy",
        trade_value=1e6,
    )

    assert reason is None
