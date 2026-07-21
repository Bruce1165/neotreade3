from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from neotrade3.decision_engine.hazard_predictor_v0 import build_hazard_snapshot_v0_t2


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
          close REAL,
          high REAL,
          pct_change REAL
        )
        """
    )
    return conn


def _insert_bar(conn: sqlite3.Connection, *, code: str, d: date, close: float, high: float, pct: float) -> None:
    conn.execute(
        "INSERT INTO daily_prices(trade_date, code, close, high, pct_change) VALUES (?, ?, ?, ?, ?)",
        (d.isoformat(), str(code), float(close), float(high), float(pct)),
    )


def test_hazard_predictor_returns_pending_when_history_insufficient() -> None:
    conn = _make_conn()
    try:
        start = date(2026, 1, 1)
        close = 100.0
        for i in range(10):
            d = start + timedelta(days=i)
            close *= 1.01
            _insert_bar(conn, code="000001", d=d, close=close, high=close, pct=1.0)
        snap = build_hazard_snapshot_v0_t2(conn.cursor(), code="000001", target_date=start + timedelta(days=9))
        assert snap["risk_status"] == "pending"
        assert snap["hazard_state"] == "not_ready"
        assert snap["stock_top_risk_5d"] == 0
        assert snap["stock_top_risk_20d"] == 0
    finally:
        conn.close()


def test_hazard_predictor_marks_accel_only_as_ready() -> None:
    conn = _make_conn()
    try:
        start = date(2026, 1, 1)
        close = 100.0
        for i in range(16):
            d = start + timedelta(days=i)
            close *= 1.02
            _insert_bar(conn, code="000001", d=d, close=close, high=close, pct=2.0)
        snap = build_hazard_snapshot_v0_t2(conn.cursor(), code="000001", target_date=start + timedelta(days=15))
        assert snap["risk_status"] == "ready"
        assert snap["hazard_state"] == "accel_only"
        assert snap["stock_top_risk_5d"] >= 40
        assert snap["first_event_date"] == ""
    finally:
        conn.close()


def test_hazard_predictor_marks_break_armed_as_high_risk() -> None:
    conn = _make_conn()
    try:
        start = date(2026, 1, 1)
        close = 100.0
        for i in range(15):
            d = start + timedelta(days=i)
            close *= 1.03
            _insert_bar(conn, code="000001", d=d, close=close, high=close, pct=3.0)
        d_break = start + timedelta(days=15)
        close = close * 0.92
        _insert_bar(conn, code="000001", d=d_break, close=close, high=close, pct=-8.0)
        snap = build_hazard_snapshot_v0_t2(conn.cursor(), code="000001", target_date=d_break)
        assert snap["risk_status"] == "ready"
        assert snap["hazard_state"] == "break_armed"
        assert snap["stock_top_risk_5d"] == 0
        assert snap["first_event_date"] == d_break.isoformat()
    finally:
        conn.close()


def test_hazard_predictor_never_queries_offline_label_table() -> None:
    conn = _make_conn()
    try:
        start = date(2026, 1, 1)
        close = 100.0
        for i in range(20):
            d = start + timedelta(days=i)
            close *= 1.01
            _insert_bar(conn, code="000001", d=d, close=close, high=close, pct=1.0)
        spy = _SpyCursor(conn.cursor())
        build_hazard_snapshot_v0_t2(spy, code="000001", target_date=start + timedelta(days=19))
        combined = "\n".join(spy.statements)
        assert "stock_top_hazard_labels_t2" not in combined
        assert "trade_date <= ?" in combined
    finally:
        conn.close()
