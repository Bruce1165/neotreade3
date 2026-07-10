from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import neotrade3.data_control.formal_input_adapter as formal_input_adapter
from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16


def _seed_formal_input_db(db_path: Path) -> date:
    target = date(2026, 7, 7)
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
            ("000001", "平安银行", "stock", 0, "金融", "银行", target.isoformat()),
        )
        conn.execute(
            """
            INSERT INTO stocks(code, name, asset_type, is_delisted, sector_lv1, sector_lv2, last_trade_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("000002", "万科A", "stock", 0, "地产", "开发", target.isoformat()),
        )
        conn.execute(
            "INSERT INTO trading_calendar_meta(key, value) VALUES (?, ?)",
            ("calendar_source", "trading_calendar_cache"),
        )
        conn.execute(
            "INSERT INTO trading_calendar_meta(key, value) VALUES (?, ?)",
            ("calendar_covered_until", target.isoformat()),
        )
        for i in range(20):
            trade_date = (target - timedelta(days=i)).isoformat()
            conn.execute(
                "INSERT INTO trading_calendar_cache(trade_date) VALUES (?)",
                (trade_date,),
            )
            conn.execute(
                """
                INSERT INTO daily_prices(
                    code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "000001",
                    trade_date,
                    10.0 + i,
                    10.5 + i,
                    9.8 + i,
                    10.2 + i,
                    1000000.0 + i,
                    20000000.0 + i * 1000.0,
                    3.0 + i * 0.1,
                    10.0 + i,
                    0.5,
                    "2026-07-07T15:00:00Z",
                ),
            )
            if i < 4:
                conn.execute(
                    """
                    INSERT INTO daily_prices(
                        code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "000002",
                        trade_date,
                        20.0 + i,
                        20.5 + i,
                        19.8 + i,
                        20.2 + i,
                        500000.0 + i,
                        10000000.0 + i * 500.0,
                        1.5 + i * 0.1,
                        20.0 + i,
                        -0.2,
                        "2026-07-07T15:00:00Z",
                    ),
                )
        conn.commit()
    finally:
        conn.close()
    return target


def test_load_formal_m1_inputs_returns_projected_batches(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    target = _seed_formal_input_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        out = formal_input_adapter.load_formal_m1_inputs(
            conn.cursor(),
            ["000001", "000002"],
            target_date=target,
            history_limit=20,
        )
    finally:
        conn.close()

    assert sorted(out.keys()) == [
        "d1_by_code",
        "history_by_code",
        "security_by_code",
        "trading_day_status",
    ]
    assert out["d1_by_code"]["000001"].stock_code == "000001"
    assert out["security_by_code"]["000001"].stock_name == "平安银行"
    assert out["trading_day_status"].target_date == target.isoformat()
    assert out["trading_day_status"].calendar_source == "trading_calendar_cache"
    assert len(out["history_by_code"]["000001"]) == 20
    assert out["history_by_code"]["000001"][0]["trade_date"] == target.isoformat()
    assert len(out["history_by_code"]["000002"]) == 4


def test_load_formal_m1_inputs_uses_trading_day_projection(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    target = _seed_formal_input_db(db_path)
    seen: dict[str, object] = {}
    real_projection = formal_input_adapter.project_d7_trading_day_status

    def _spy(payload: dict[str, object]):
        seen["payload"] = dict(payload)
        return real_projection(payload)

    monkeypatch.setattr(formal_input_adapter, "project_d7_trading_day_status", _spy)

    conn = sqlite3.connect(str(db_path))
    try:
        out = formal_input_adapter.load_formal_m1_inputs(
            conn.cursor(),
            ["000001"],
            target_date=target,
            history_limit=20,
        )
    finally:
        conn.close()

    raw_payload = seen["payload"]
    assert isinstance(raw_payload, dict)
    assert raw_payload["target_date"] == target.isoformat()
    assert raw_payload["_meta"]["calendar_source"] == "trading_calendar_cache"
    assert out["trading_day_status"].calendar_source == "trading_calendar_cache"


def test_build_formal_front_chain_payload_consumes_adapter_output(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    target = _seed_formal_input_db(db_path)

    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine._conn = lambda: sqlite3.connect(str(db_path))

    out = engine._build_formal_front_chain_payload(
        target_date=target,
        candidate_signals=[{"code": "000001"}],
    )

    assert out["status"] == "ok"
    assert out["summary"] == {"total": 1, "ok": 1, "error": 0}
    assert out["items_by_code"]["000001"]["status"] == "ok"
    assert "small_cycle" in out["items_by_code"]["000001"]
    assert "m1_constraints_ref" in out["items_by_code"]["000001"]
