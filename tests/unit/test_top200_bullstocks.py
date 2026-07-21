import sqlite3

import pytest

from neotrade3.analysis.top200_bullstocks import extract_codes, load_global_top_bullstocks


def _seed_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE stocks (
            code TEXT PRIMARY KEY,
            name TEXT,
            sector_lv1 TEXT,
            is_delisted INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE daily_prices (
            code TEXT,
            trade_date TEXT,
            close REAL
        )
        """
    )
    conn.executemany(
        "INSERT INTO stocks(code, name, sector_lv1, is_delisted) VALUES(?,?,?,?)",
        [
            ("600001", "A", "S1", 0),
            ("600002", "B", "S1", 0),
            ("688001", "C", "S2", 0),
            ("123456", "X", "S9", 0),
        ],
    )
    conn.executemany(
        "INSERT INTO daily_prices(code, trade_date, close) VALUES(?,?,?)",
        [
            ("600001", "2026-01-01", 10.0),
            ("600001", "2026-01-02", 20.0),
            ("600002", "2026-01-01", 10.0),
            ("600002", "2026-01-02", 15.0),
            ("688001", "2026-01-01", 5.0),
            ("688001", "2026-01-02", 6.0),
            ("123456", "2026-01-01", 1.0),
            ("123456", "2026-01-02", 2.0),
        ],
    )
    conn.commit()


def test_load_global_top_bullstocks_orders_by_max_runup() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        _seed_db(conn)
        rows = load_global_top_bullstocks(conn, limit=3)
        codes = extract_codes(rows)
        assert codes == ["600001", "600002", "688001"]
        assert rows[0].max_runup_pct > rows[1].max_runup_pct
    finally:
        conn.close()


def test_load_global_top_bullstocks_fail_closed_when_insufficient() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        _seed_db(conn)
        with pytest.raises(RuntimeError):
            _ = load_global_top_bullstocks(conn, limit=10)
    finally:
        conn.close()

