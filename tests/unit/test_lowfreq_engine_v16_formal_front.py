from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16, StockCandidate, WavePhase


class _FakeConn:
    def cursor(self):
        return object()

    def close(self):
        return None


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


def _seed_formal_front_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT,
                asset_type TEXT,
                is_delisted INTEGER,
                sector_lv1 TEXT,
                sector_lv2 TEXT,
                last_trade_date TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE daily_prices (
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                turnover REAL,
                preclose REAL,
                pct_change REAL,
                updated_at TEXT
            )
            """
        )
        conn.execute("CREATE TABLE trading_calendar_cache (trade_date TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE trading_calendar_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            """
            INSERT INTO stocks(code, name, asset_type, is_delisted, sector_lv1, sector_lv2, last_trade_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("600460", "士兰微", "stock", 0, "电子", "半导体", "2026-07-07"),
        )
        conn.execute(
            "INSERT INTO trading_calendar_meta(key, value) VALUES (?, ?)",
            ("calendar_source", "trading_calendar_cache"),
        )
        conn.execute(
            "INSERT INTO trading_calendar_meta(key, value) VALUES (?, ?)",
            ("calendar_covered_until", "2026-07-07"),
        )
        target = date(2026, 7, 7)
        for i in range(20):
            trade_dt = target - timedelta(days=i)
            trade_date = trade_dt.isoformat()
            conn.execute(
                "INSERT INTO trading_calendar_cache(trade_date) VALUES (?)",
                (trade_date,),
            )
            close = 20.0 - i * 0.3
            preclose = close - 0.2
            conn.execute(
                """
                INSERT INTO daily_prices(
                    code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "600460",
                    trade_date,
                    close - 0.1,
                    close + 0.3,
                    close - 0.4,
                    close,
                    1_000_000.0 + i * 1000.0,
                    200_000_000.0 - i * 2_000_000.0,
                    3.0 - i * 0.03,
                    preclose,
                    2.0 if i < 5 else 0.6,
                    "2026-07-07T15:00:00Z",
                ),
            )
        conn.commit()
    finally:
        conn.close()


def test_generate_buy_signals_marks_formal_error_when_m1_inputs_are_unavailable() -> None:
    engine = _make_engine()

    engine.get_hot_sectors = lambda target_date, top_n, cursor=None: [
        SimpleNamespace(sector="C39", heat_score=80.0)
    ]
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

    assert out["formal"]["status"] == "error"
    assert out["candidate_signals"][0]["formal"]["status"] == "error"


def test_generate_buy_signals_emits_formal_front_chain_when_m1_inputs_are_available(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    _seed_formal_front_db(db_path)

    engine = _make_engine()
    engine._conn = lambda: sqlite3.connect(str(db_path))
    engine.CROSS_SECTOR_SCAN_ENABLED = False

    engine.get_hot_sectors = lambda target_date, top_n, cursor=None: [
        SimpleNamespace(sector="C39", heat_score=80.0)
    ]
    engine.get_sector_candidates = lambda sector, target_date, top_n, cursor=None: [
        StockCandidate(
            code="600460",
            name="士兰微",
            sector="C39",
            market_cap_yi=320.0,
            role="龙头",
            buy_score=96.0,
            buy_reasons=["半导体主线"],
            wave_phase=WavePhase.WAVE_3.value,
            sector_resonance=0.9,
        )
    ]
    engine.get_global_candidates = lambda *args, **kwargs: []

    out = engine.generate_buy_signals(date(2026, 7, 7))

    assert out["formal"]["status"] == "ok"
    assert out["formal"]["summary"] == {"total": 1, "ok": 1, "error": 0}
    candidate = out["candidate_signals"][0]
    assert candidate["formal"]["status"] == "ok"
    assert candidate["formal"]["small_cycle"]["cycle_state"] == "S2 Advancing"
    assert candidate["formal"]["identify_state"]["status"] == "identified"
    assert candidate["formal"]["tracking_state"]["maturity"] == "ready_for_entry"
    assert candidate["formal"]["entry_state"]["status"] == "ready"
