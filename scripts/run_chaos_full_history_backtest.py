#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neotrade3.chaos.backtest.contracts import BacktestConfig, BacktestSignalConfig, BacktestVersions
from neotrade3.chaos.backtest.engine import ChaosBacktestEngine, write_backtest_artifacts


def _infer_trade_date_bounds(conn: sqlite3.Connection) -> tuple[str, str]:
    row = conn.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_prices").fetchone()
    if not row or not row[0] or not row[1]:
        raise RuntimeError("daily_prices is empty; cannot infer trade date bounds")
    return str(row[0]), str(row[1])


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start-date", default="")
    p.add_argument("--end-date", default="")
    p.add_argument("--initial-capital", type=float, default=1_000_000.0)
    p.add_argument("--max-positions", type=int, default=10)
    p.add_argument("--position-size-pct", type=float, default=10.0)
    p.add_argument("--chaos-db", default="")

    p.add_argument("--thresholds-version", default="chaos_thresholds_v0")
    p.add_argument("--registry-version", default="chaos_registry_v1")
    p.add_argument("--weights-version", default="chaos_weights_v1_2")

    p.add_argument("--signal-mode", choices=["point", "regime_speed", "regime_combo"], default="regime_combo")
    p.add_argument("--combo-lambda", type=float, default=0.5)
    p.add_argument("--combo-beta", type=float, default=-0.5)

    p.add_argument("--report-suffix", default="")
    args = p.parse_args()

    stock_db = PROJECT_ROOT / "var" / "db" / "stock_data.db"
    chaos_db = Path(str(args.chaos_db).strip()) if str(args.chaos_db).strip() else (PROJECT_ROOT / "var" / "db" / "chaos_factor_matrix.db")
    if not stock_db.is_file():
        raise SystemExit(f"stock db not found: {stock_db}")
    if not chaos_db.is_file():
        raise SystemExit(f"chaos db not found: {chaos_db}")

    with sqlite3.connect(str(stock_db)) as stock_conn, sqlite3.connect(str(chaos_db)) as chaos_conn:
        inferred_start, inferred_end = _infer_trade_date_bounds(stock_conn)
        start_date = str(args.start_date).strip() or inferred_start
        end_date = str(args.end_date).strip() or inferred_end

        cfg = BacktestConfig(
            start_date=str(start_date),
            end_date=str(end_date),
            initial_capital=float(args.initial_capital),
            max_positions=int(args.max_positions),
            position_size_pct=float(args.position_size_pct),
            versions=BacktestVersions(
                thresholds_version=str(args.thresholds_version),
                registry_version=str(args.registry_version),
                weights_version=str(args.weights_version),
            ),
            signal=BacktestSignalConfig(
                signal_mode=str(args.signal_mode),
                combo_lambda=float(args.combo_lambda) if str(args.signal_mode) == "regime_combo" else None,
                combo_beta=float(args.combo_beta) if str(args.signal_mode) == "regime_combo" else None,
            ),
        )

        engine = ChaosBacktestEngine(project_root=PROJECT_ROOT)
        result = engine.run(stock_conn=stock_conn, chaos_conn=chaos_conn, config=cfg)
        write_backtest_artifacts(project_root=PROJECT_ROOT, end_date=str(end_date), suffix=str(args.report_suffix), result=result)
        print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
