from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from neotrade3.chaos.store import ensure_chaos_schema, upsert_daily_snapshot, upsert_factor_values, upsert_registry
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


def test_chaos_store_can_upsert_registry_snapshot_and_factors() -> None:
    stock_conn = _make_stock_conn()
    chaos_conn = sqlite3.connect(":memory:")
    try:
        start = date(2026, 1, 1)
        vol = 1000.0
        for i in range(20):
            d = start + timedelta(days=i)
            vol = vol * 1.01
            pct = 1.0 if i % 5 != 0 else -0.5
            _insert_bar(stock_conn, code="000001", d=d, volume=vol, pct=pct)
        stock_conn.commit()

        ensure_chaos_schema(chaos_conn)
        upsert_registry(chaos_conn, registry_version="chaos_registry_v0", payload={"version": "chaos_registry_v0"})

        snap = build_chaos_snapshot_v0(stock_conn.cursor(), code="000001", target_date=start + timedelta(days=19))
        upsert_daily_snapshot(
            chaos_conn,
            code="000001",
            trade_date=(start + timedelta(days=19)).isoformat(),
            registry_version=str(snap.get("factor_registry_version") or "chaos_registry_v0"),
            weights_version=str(snap.get("weights_version") or "chaos_weights_v0"),
            thresholds_version="chaos_thresholds_v0",
            snapshot=snap,
        )
        raw = snap.get("raw_factors") if isinstance(snap, dict) else {}
        upsert_factor_values(
            chaos_conn,
            code="000001",
            trade_date=(start + timedelta(days=19)).isoformat(),
            registry_version=str(snap.get("factor_registry_version") or "chaos_registry_v0"),
            values={str(k): float(v) for k, v in raw.items() if isinstance(v, (int, float))},
        )

        row = chaos_conn.execute(
            """
            SELECT chaos_status, yin_value, yang_value, net_energy
            FROM chaos_daily_snapshot
            WHERE code = ? AND trade_date = ?
            """,
            ("000001", (start + timedelta(days=19)).isoformat()),
        ).fetchone()
        assert row is not None
        assert str(row[0]) in {"ready", "pending"}

        n = chaos_conn.execute(
            "SELECT COUNT(*) FROM chaos_factor_values WHERE code = ?",
            ("000001",),
        ).fetchone()
        assert n is not None
        assert int(n[0]) >= 1
    finally:
        stock_conn.close()
        chaos_conn.close()

