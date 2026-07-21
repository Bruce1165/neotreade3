from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from neotrade3.decision_engine.chaos_model_v0 import build_chaos_snapshot_v0


class _SpyCursor:
    def __init__(self, cursor: sqlite3.Cursor) -> None:
        self._cursor = cursor
        self.statements: list[str] = []

    def execute(self, sql: str, parameters: object = None):
        self.statements.append(str(sql))
        if parameters is None:
            return self._cursor.execute(sql)
        return self._cursor.execute(sql, parameters)


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE daily_prices (
          trade_date TEXT NOT NULL,
          code TEXT NOT NULL,
          volume REAL,
          pct_change REAL
        )
        """
    )
    return conn


def _insert_bar(conn: sqlite3.Connection, *, code: str, d: date, volume: float, pct: float) -> None:
    conn.execute(
        "INSERT INTO daily_prices(trade_date, code, volume, pct_change) VALUES (?, ?, ?, ?)",
        (d.isoformat(), str(code), float(volume), float(pct)),
    )


def test_chaos_snapshot_returns_pending_when_history_insufficient() -> None:
    conn = _make_conn()
    try:
        start = date(2026, 1, 1)
        for i in range(5):
            d = start + timedelta(days=i)
            _insert_bar(conn, code="000001", d=d, volume=1000 + i, pct=1.0)
        snap = build_chaos_snapshot_v0(conn.cursor(), code="000001", target_date=start + timedelta(days=4))
        assert snap["chaos_status"] == "pending"
        assert snap["yin_value"] == 0.0
        assert snap["yang_value"] == 0.0
    finally:
        conn.close()


def test_chaos_snapshot_never_queries_offline_label_table() -> None:
    conn = _make_conn()
    try:
        start = date(2026, 1, 1)
        vol = 1000.0
        for i in range(20):
            d = start + timedelta(days=i)
            vol = vol * 1.01
            pct = 1.0 if i % 5 != 0 else -0.5
            _insert_bar(conn, code="000001", d=d, volume=vol, pct=pct)
        spy = _SpyCursor(conn.cursor())
        build_chaos_snapshot_v0(spy, code="000001", target_date=start + timedelta(days=19))
        combined = "\n".join(spy.statements)
        assert "stock_top_hazard_labels_t2" not in combined
        assert "trade_date <= ?" in combined
    finally:
        conn.close()

