from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from neotrade3.chaos.m4_eval_monitor import evaluate_chaos_m4_monitor
from neotrade3.chaos.store import ensure_chaos_schema, upsert_daily_snapshot, upsert_factor_values


def _make_stock_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE daily_prices (
          trade_date TEXT NOT NULL,
          code TEXT NOT NULL,
          close REAL,
          amount REAL
        )
        """
    )
    return conn


def _insert_bar(conn: sqlite3.Connection, *, code: str, d: date, close: float, amount: float) -> None:
    conn.execute(
        "INSERT INTO daily_prices(trade_date, code, close, amount) VALUES (?, ?, ?, ?)",
        (d.isoformat(), str(code), float(close), float(amount)),
    )


def test_m4_eval_monitor_outputs_5d_and_10d_metrics() -> None:
    stock_conn = _make_stock_conn()
    chaos_conn = sqlite3.connect(":memory:")
    try:
        ensure_chaos_schema(chaos_conn)
        start = date(2026, 1, 1)
        codes = ["000001"]
        trade_dates: list[str] = []
        price = 10.0
        for i in range(40):
            d = start + timedelta(days=i)
            trade_dates.append(d.isoformat())
            price = price * 1.01
            _insert_bar(stock_conn, code="000001", d=d, close=price, amount=1e9)
        stock_conn.commit()

        for d in trade_dates[:20]:
            upsert_daily_snapshot(
                chaos_conn,
                code="000001",
                trade_date=d,
                registry_version="chaos_registry_v0",
                weights_version="chaos_weights_v0",
                thresholds_version="chaos_thresholds_v0",
                snapshot={
                    "chaos_status": "ready",
                    "yin_value": 0.0,
                    "yang_value": 1.0,
                    "net_energy": 1.0,
                    "yin_yang_ratio": "0:1",
                    "reference_mode": "test",
                    "self_history_reference": {
                        "regime_anchor_date": trade_dates[0],
                        "flip_rate_in_window": 0.0,
                        "yang_speed_mean_in_window": 1.0,
                    },
                    "raw_factors": {"net_energy_adjusted": 1.0},
                    "evidence": [],
                },
            )
            upsert_factor_values(
                chaos_conn,
                code="000001",
                trade_date=d,
                registry_version="chaos_registry_v0",
                values={"net_energy_adjusted": 1.0},
            )

        report, metrics = evaluate_chaos_m4_monitor(
            chaos_conn=chaos_conn,
            stock_conn=stock_conn,
            codes=codes,
            trade_dates=trade_dates[:20],
            thresholds_version="chaos_thresholds_v0",
            horizons=[5, 10],
        )
        assert report["code_count"] == 1
        assert len(metrics) == 2
        by_h = {m.horizon: m for m in metrics}
        assert by_h[5].evaluable > 0
        assert by_h[10].evaluable > 0
        assert by_h[5].accuracy_direction == 1.0
        assert by_h[10].accuracy_direction == 1.0
    finally:
        stock_conn.close()
        chaos_conn.close()


def test_m4_eval_monitor_supports_regime_speed_signal_mode() -> None:
    stock_conn = _make_stock_conn()
    chaos_conn = sqlite3.connect(":memory:")
    try:
        ensure_chaos_schema(chaos_conn)
        start = date(2026, 1, 1)
        codes = ["000001"]
        trade_dates: list[str] = []
        price = 10.0
        for i in range(40):
            d = start + timedelta(days=i)
            trade_dates.append(d.isoformat())
            price = price * 1.01
            _insert_bar(stock_conn, code="000001", d=d, close=price, amount=1e9)
        stock_conn.commit()

        for d in trade_dates[:20]:
            upsert_daily_snapshot(
                chaos_conn,
                code="000001",
                trade_date=d,
                registry_version="chaos_registry_v0",
                weights_version="chaos_weights_v0",
                thresholds_version="chaos_thresholds_v0",
                snapshot={
                    "chaos_status": "ready",
                    "yin_value": 0.0,
                    "yang_value": 1.0,
                    "net_energy": -1.0,
                    "yin_yang_ratio": "0:1",
                    "reference_mode": "test",
                    "self_history_reference": {
                        "regime_anchor_date": trade_dates[0],
                        "flip_rate_in_window": 0.0,
                        "yang_speed_mean_in_window": 1.0,
                    },
                    "raw_factors": {"net_energy_adjusted": -1.0},
                    "evidence": [],
                },
            )
            upsert_factor_values(
                chaos_conn,
                code="000001",
                trade_date=d,
                registry_version="chaos_registry_v0",
                values={"net_energy_adjusted": -1.0},
            )

        report_point, metrics_point = evaluate_chaos_m4_monitor(
            chaos_conn=chaos_conn,
            stock_conn=stock_conn,
            codes=codes,
            trade_dates=trade_dates[:20],
            thresholds_version="chaos_thresholds_v0",
            horizons=[5],
            signal_mode="point",
        )
        assert report_point["signal_mode"] == "point"
        assert metrics_point[0].accuracy_direction == 0.0

        report_speed, metrics_speed = evaluate_chaos_m4_monitor(
            chaos_conn=chaos_conn,
            stock_conn=stock_conn,
            codes=codes,
            trade_dates=trade_dates[:20],
            thresholds_version="chaos_thresholds_v0",
            horizons=[5],
            signal_mode="regime_speed",
        )
        assert report_speed["signal_mode"] == "regime_speed"
        assert metrics_speed[0].accuracy_direction == 1.0
    finally:
        stock_conn.close()
        chaos_conn.close()


def test_m4_eval_monitor_supports_regime_combo_signal_mode() -> None:
    stock_conn = _make_stock_conn()
    chaos_conn = sqlite3.connect(":memory:")
    try:
        ensure_chaos_schema(chaos_conn)
        start = date(2026, 1, 1)
        codes = ["000001"]
        trade_dates: list[str] = []
        price = 10.0
        for i in range(40):
            d = start + timedelta(days=i)
            trade_dates.append(d.isoformat())
            price = price * 1.01
            _insert_bar(stock_conn, code="000001", d=d, close=price, amount=1e9)
        stock_conn.commit()

        for d in trade_dates[:20]:
            upsert_daily_snapshot(
                chaos_conn,
                code="000001",
                trade_date=d,
                registry_version="chaos_registry_v0",
                weights_version="chaos_weights_v0",
                thresholds_version="chaos_thresholds_v0",
                snapshot={
                    "chaos_status": "ready",
                    "yin_value": 0.0,
                    "yang_value": 1.0,
                    "net_energy": -1.0,
                    "yin_yang_ratio": "0:1",
                    "reference_mode": "test",
                    "self_history_reference": {
                        "regime_anchor_date": trade_dates[0],
                        "flip_rate_in_window": 0.0,
                        "yang_speed_mean_in_window": 0.0,
                        "net_energy_zscore_in_window": 1.0,
                    },
                    "raw_factors": {"net_energy_adjusted": -1.0},
                    "evidence": [],
                },
            )
            upsert_factor_values(
                chaos_conn,
                code="000001",
                trade_date=d,
                registry_version="chaos_registry_v0",
                values={"net_energy_adjusted": -1.0},
            )

        report, metrics = evaluate_chaos_m4_monitor(
            chaos_conn=chaos_conn,
            stock_conn=stock_conn,
            codes=codes,
            trade_dates=trade_dates[:20],
            thresholds_version="chaos_thresholds_v0",
            horizons=[5],
            signal_mode="regime_combo",
            combo_lambda=1.0,
            combo_beta=0.0,
        )
        assert report["signal_mode"] == "regime_combo"
        assert float(report["combo_lambda"] or 0.0) == 1.0
        assert metrics[0].accuracy_direction == 1.0

        report_b, metrics_b = evaluate_chaos_m4_monitor(
            chaos_conn=chaos_conn,
            stock_conn=stock_conn,
            codes=codes,
            trade_dates=trade_dates[:20],
            thresholds_version="chaos_thresholds_v0",
            horizons=[5],
            signal_mode="regime_combo",
            combo_lambda=0.0,
            combo_beta=1.0,
        )
        assert report_b["signal_mode"] == "regime_combo"
        assert float(report_b["combo_beta"] or 0.0) == 1.0
        assert metrics_b[0].accuracy_direction == 0.0
    finally:
        stock_conn.close()
        chaos_conn.close()


def test_m4_eval_monitor_actual_eps_skips_small_moves() -> None:
    stock_conn = _make_stock_conn()
    chaos_conn = sqlite3.connect(":memory:")
    try:
        ensure_chaos_schema(chaos_conn)
        start = date(2026, 1, 1)
        codes = ["000001"]
        trade_dates: list[str] = []
        price = 10.0
        for i in range(40):
            d = start + timedelta(days=i)
            trade_dates.append(d.isoformat())
            price = price * 1.0005
            _insert_bar(stock_conn, code="000001", d=d, close=price, amount=1e9)
        stock_conn.commit()

        for d in trade_dates[:20]:
            upsert_daily_snapshot(
                chaos_conn,
                code="000001",
                trade_date=d,
                registry_version="chaos_registry_v0",
                weights_version="chaos_weights_v0",
                thresholds_version="chaos_thresholds_v0",
                snapshot={
                    "chaos_status": "ready",
                    "yin_value": 0.0,
                    "yang_value": 1.0,
                    "net_energy": 1.0,
                    "yin_yang_ratio": "0:1",
                    "reference_mode": "test",
                    "self_history_reference": {
                        "regime_anchor_date": trade_dates[0],
                        "flip_rate_in_window": 0.0,
                        "yang_speed_mean_in_window": 1.0,
                        "net_energy_zscore_in_window": 1.0,
                    },
                    "raw_factors": {"net_energy_adjusted": 1.0},
                    "evidence": [],
                },
            )
            upsert_factor_values(
                chaos_conn,
                code="000001",
                trade_date=d,
                registry_version="chaos_registry_v0",
                values={"net_energy_adjusted": 1.0},
            )

        report1, metrics1 = evaluate_chaos_m4_monitor(
            chaos_conn=chaos_conn,
            stock_conn=stock_conn,
            codes=codes,
            trade_dates=trade_dates[:20],
            thresholds_version="chaos_thresholds_v0",
            horizons=[5],
            signal_mode="point",
            actual_eps=0.002,
        )
        assert float(report1["actual_eps"] or 0.0) == 0.002
        assert metrics1[0].evaluable > 0

        report2, metrics2 = evaluate_chaos_m4_monitor(
            chaos_conn=chaos_conn,
            stock_conn=stock_conn,
            codes=codes,
            trade_dates=trade_dates[:20],
            thresholds_version="chaos_thresholds_v0",
            horizons=[5],
            signal_mode="point",
            actual_eps=0.005,
        )
        assert float(report2["actual_eps"] or 0.0) == 0.005
        assert metrics2[0].evaluable == 0
        assert metrics2[0].skipped_small_move > 0
    finally:
        stock_conn.close()
        chaos_conn.close()
