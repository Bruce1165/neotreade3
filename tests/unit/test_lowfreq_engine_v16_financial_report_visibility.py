from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from apps.api.main import BootstrapApiService
import lowfreq_engine_v16_advanced as lowfreq_engine_module
from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16


def test_ensure_financial_reports_table_adds_ann_date_column(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE financial_reports (
                code TEXT NOT NULL,
                report_date TEXT NOT NULL,
                pe_ttm REAL,
                profit_growth_yoy REAL,
                revenue_growth_yoy REAL,
                roe REAL,
                source TEXT,
                metadata_json TEXT,
                updated_at TEXT,
                PRIMARY KEY (code, report_date)
            )
            """
        )
        BootstrapApiService._ensure_financial_reports_tables(conn=conn)
        cols = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(financial_reports)").fetchall()
            if row and len(row) > 1 and row[1] is not None
        }
    finally:
        conn.close()

    assert "ann_date" in cols


def test_get_fundamentals_uses_ann_date_visibility(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        BootstrapApiService._ensure_financial_reports_tables(conn=conn)
        conn.executemany(
            """
            INSERT INTO financial_reports (
                code, report_date, ann_date, pe_ttm, profit_growth_yoy, revenue_growth_yoy, roe, source, metadata_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "000001",
                    "2024-12-31",
                    "2025-01-20",
                    8.0,
                    11.0,
                    12.0,
                    13.0,
                    "unit.test",
                    "{}",
                    "2026-06-19T00:00:00",
                ),
                (
                    "000001",
                    "2025-03-31",
                    "2025-04-20",
                    10.0,
                    21.0,
                    22.0,
                    23.0,
                    "unit.test",
                    "{}",
                    "2026-06-19T00:00:00",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    engine = LowFreqTradingEngineV16(db_path=Path(db_path))

    before = engine.get_fundamentals("000001", date(2025, 4, 19))
    after = engine.get_fundamentals("000001", date(2025, 4, 20))

    assert before["pe_ttm"] == 8.0
    assert before["profit_growth"] == 11.0
    assert after["pe_ttm"] == 10.0
    assert after["profit_growth"] == 21.0


def test_get_fundamentals_batch_uses_ann_date_visibility(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        BootstrapApiService._ensure_financial_reports_tables(conn=conn)
        conn.executemany(
            """
            INSERT INTO financial_reports (
                code, report_date, ann_date, pe_ttm, profit_growth_yoy, revenue_growth_yoy, roe, source, metadata_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "000001",
                    "2024-12-31",
                    "2025-01-20",
                    8.0,
                    11.0,
                    12.0,
                    13.0,
                    "unit.test",
                    "{}",
                    "2026-06-19T00:00:00",
                ),
                (
                    "000001",
                    "2025-03-31",
                    "2025-04-20",
                    10.0,
                    21.0,
                    22.0,
                    23.0,
                    "unit.test",
                    "{}",
                    "2026-06-19T00:00:00",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    engine = LowFreqTradingEngineV16(db_path=Path(db_path))
    conn = sqlite3.connect(str(db_path))
    try:
        before = engine._get_fundamentals_batch(conn.cursor(), ["000001"], date(2025, 4, 19))
        after = engine._get_fundamentals_batch(conn.cursor(), ["000001"], date(2025, 4, 20))
    finally:
        conn.close()

    assert before["000001"]["pe_ttm"] == 8.0
    assert before["000001"]["profit_growth"] == 11.0
    assert after["000001"]["pe_ttm"] == 10.0
    assert after["000001"]["profit_growth"] == 21.0


def test_get_global_candidates_uses_batch_fundamentals(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT,
                sector_lv1 TEXT,
                total_market_cap REAL,
                is_delisted INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE daily_prices (
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                close REAL,
                pct_change REAL,
                amount REAL,
                volume REAL,
                high REAL,
                low REAL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO stocks (code, name, sector_lv1, total_market_cap, is_delisted)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("000001", "测试龙头", "机器人", 25_000_000_000.0, 0),
        )
        rows = []
        start_date = date(2026, 5, 20)
        for day in range(30):
            close = 10.0 + day * 0.2
            trade_date = (start_date + timedelta(days=day)).isoformat()
            rows.append(
                (
                    "000001",
                    trade_date,
                    close,
                    1.2 if day == 29 else 0.4,
                    1000000.0 + day * 1000.0,
                    100000.0 + day * 500.0,
                    close * 1.02,
                    close * 0.98,
                )
            )
        conn.executemany(
            """
            INSERT INTO daily_prices (code, trade_date, close, pct_change, amount, volume, high, low)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()

    engine = LowFreqTradingEngineV16(db_path=Path(db_path))
    monkeypatch.setattr(engine, "CUP_HANDLE_ENABLED", False, raising=False)
    monkeypatch.setattr(engine, "get_fundamentals", lambda code, target_date: (_ for _ in ()).throw(AssertionError("should not call per-code get_fundamentals")))
    monkeypatch.setattr(engine, "_structure_confirm", lambda **kwargs: {"passed": True, "reasons": []})
    monkeypatch.setattr(
        lowfreq_engine_module,
        "passes_core_focus_gate",
        lambda cursor, code, stock_name, role, target_date, market_focus_snapshot_loader: (
            True,
            [],
            {"focus_bonus": 0.0},
        ),
    )
    monkeypatch.setattr(engine, "_weekly_returns_view", lambda code, target_date: {"status": "insufficient"})

    candidates = engine.get_global_candidates(target_date=date(2026, 6, 18), top_n=10)

    assert len(candidates) == 1
    assert candidates[0].code == "000001"
