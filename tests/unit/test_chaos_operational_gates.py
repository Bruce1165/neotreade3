from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from neotrade3.chaos.operational_gates import verify_chaos_operational_gates
from neotrade3.chaos.store import ensure_chaos_schema, upsert_daily_snapshot, upsert_factor_values
from neotrade3.decision_engine.chaos_model_v0 import build_chaos_snapshot_v0


def _make_stock_conn() -> sqlite3.Connection:
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


def test_operational_gates_pass_for_ready_rows() -> None:
    stock_conn = _make_stock_conn()
    chaos_conn = sqlite3.connect(":memory:")
    try:
        ensure_chaos_schema(chaos_conn)
        start = date(2026, 1, 1)
        vol = 1000.0
        codes = ["000001", "000002"]
        trade_dates: list[str] = []
        for i in range(20):
            d = start + timedelta(days=i)
            trade_dates.append(d.isoformat())
            for c in codes:
                vol = vol * 1.01
                pct = 1.0 if i % 5 != 0 else -0.5
                _insert_bar(stock_conn, code=c, d=d, volume=vol, pct=pct)
        stock_conn.commit()

        for d in trade_dates:
            d_obj = date.fromisoformat(d)
            for c in codes:
                snap = build_chaos_snapshot_v0(stock_conn.cursor(), code=c, target_date=d_obj)
                upsert_daily_snapshot(
                    chaos_conn,
                    code=c,
                    trade_date=d,
                    registry_version=str(snap.get("factor_registry_version") or "chaos_registry_v0"),
                    weights_version=str(snap.get("weights_version") or "chaos_weights_v0"),
                    thresholds_version="chaos_thresholds_v0",
                    snapshot=snap,
                )
                raw = snap.get("raw_factors") if isinstance(snap, dict) else {}
                upsert_factor_values(
                    chaos_conn,
                    code=c,
                    trade_date=d,
                    registry_version=str(snap.get("factor_registry_version") or "chaos_registry_v0"),
                    values={str(k): float(v) for k, v in raw.items() if isinstance(v, (int, float))},
                )

        report = verify_chaos_operational_gates(
            chaos_conn,
            start_date=trade_dates[0],
            end_date=trade_dates[-1],
            codes=codes,
            trade_dates=trade_dates,
            thresholds_version="chaos_thresholds_v0",
            allow_missing_ratio=0.0,
            min_ready_ratio=0.5,
        )
        assert report.expected_rows == report.snapshot_rows
        assert report.ready_rows >= 1
    finally:
        stock_conn.close()
        chaos_conn.close()


def test_operational_gates_fail_when_missing_snapshot_rows() -> None:
    chaos_conn = sqlite3.connect(":memory:")
    try:
        ensure_chaos_schema(chaos_conn)
        with pytest.raises(RuntimeError, match="chaos_snapshot_rows_missing"):
            verify_chaos_operational_gates(
                chaos_conn,
                start_date="2026-01-01",
                end_date="2026-01-02",
                codes=["000001"],
                trade_dates=["2026-01-01", "2026-01-02"],
                thresholds_version="chaos_thresholds_v0",
                allow_missing_ratio=0.0,
                min_ready_ratio=0.0,
            )
    finally:
        chaos_conn.close()

