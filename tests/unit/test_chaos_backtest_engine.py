import json
import sqlite3
from pathlib import Path

from neotrade3.chaos.backtest.contracts import BacktestConfig, BacktestSignalConfig, BacktestVersions
from neotrade3.chaos.backtest.engine import ChaosBacktestEngine


def _init_stock_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE stocks(
          code TEXT PRIMARY KEY,
          name TEXT,
          is_delisted INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE daily_prices(
          code TEXT NOT NULL,
          trade_date TEXT NOT NULL,
          close REAL,
          PRIMARY KEY (code, trade_date)
        )
        """
    )
    conn.commit()


def _init_chaos_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE chaos_daily_snapshot(
          code TEXT NOT NULL,
          trade_date TEXT NOT NULL,
          registry_version TEXT NOT NULL,
          weights_version TEXT NOT NULL,
          thresholds_version TEXT NOT NULL,
          chaos_status TEXT NOT NULL,
          net_energy REAL,
          reference_mode TEXT,
          self_history_reference_json TEXT NOT NULL,
          PRIMARY KEY (code, trade_date, registry_version, weights_version, thresholds_version)
        )
        """
    )
    conn.commit()


def test_chaos_backtest_tplus1_close_and_trading_days(tmp_path: Path) -> None:
    stock_conn = sqlite3.connect(":memory:")
    chaos_conn = sqlite3.connect(":memory:")
    _init_stock_db(stock_conn)
    _init_chaos_db(chaos_conn)

    stock_conn.execute("INSERT INTO stocks(code, name, is_delisted) VALUES (?,?,NULL)", ("000001", "A",))
    stock_conn.execute("INSERT INTO stocks(code, name, is_delisted) VALUES (?,?,NULL)", ("000002", "B",))

    dates = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-06", "2026-01-07", "2026-06-29"]
    closes_1 = [10.0, 10.0, 11.0, 12.0, 11.0, 13.0]
    closes_2 = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
    for d, c1, c2 in zip(dates, closes_1, closes_2):
        stock_conn.execute("INSERT INTO daily_prices(code, trade_date, close) VALUES (?,?,?)", ("000001", d, c1))
        stock_conn.execute("INSERT INTO daily_prices(code, trade_date, close) VALUES (?,?,?)", ("000002", d, c2))
    stock_conn.commit()

    def ins(trade_date: str, code: str, net: float) -> None:
        ref = {"yang_speed_mean_in_window": 0.0, "net_energy_zscore_in_window": 0.0, "regime_anchor_date": "2026-01-01"}
        chaos_conn.execute(
            """
            INSERT INTO chaos_daily_snapshot(
              code, trade_date, registry_version, weights_version, thresholds_version,
              chaos_status, net_energy, reference_mode, self_history_reference_json
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                code,
                trade_date,
                "chaos_registry_v1",
                "chaos_weights_v1_2",
                "chaos_thresholds_v0",
                "ready",
                float(net),
                "projection_v1_regime_any_flip",
                json.dumps(ref, ensure_ascii=False, separators=(",", ":")),
            ),
        )

    for d in dates[:5]:
        ins(d, "000001", 1.0 if d in {"2026-01-01"} else (-1.0 if d in {"2026-01-06"} else 0.0))
        ins(d, "000002", 0.0)
    chaos_conn.commit()

    cfg = BacktestConfig(
        start_date="2026-01-01",
        end_date="2026-01-07",
        initial_capital=10000.0,
        max_positions=1,
        position_size_pct=100.0,
        versions=BacktestVersions(
            thresholds_version="chaos_thresholds_v0",
            registry_version="chaos_registry_v1",
            weights_version="chaos_weights_v1_2",
        ),
        signal=BacktestSignalConfig(signal_mode="point", combo_lambda=None, combo_beta=None),
    )
    engine = ChaosBacktestEngine(project_root=tmp_path)
    result = engine.run(stock_conn=stock_conn, chaos_conn=chaos_conn, config=cfg)
    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.signal_date == "2026-01-01"
    assert t.entry_date == "2026-01-02"
    assert t.entry_price_close == 10.0
    assert t.exit_signal_date == "2026-01-06"
    assert t.exit_date == "2026-01-07"
    assert t.exit_price_close == 11.0
    assert t.holding_days == 4
    assert round(float(t.exit_return_pct or 0.0), 6) == round(0.1, 6)
    assert round(float(t.max_runup_pct_during_hold or 0.0), 6) == round(0.2, 6)
    assert round(float(t.giveback_pct or 0.0), 6) == round(0.1, 6)
