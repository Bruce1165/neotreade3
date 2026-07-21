#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neotrade3.chaos.operational_gates import verify_chaos_operational_gates


def _a_share_universe_sql() -> str:
    return """
        length(s.code) = 6
        AND (s.is_delisted IS NULL OR s.is_delisted = 0)
        AND (
            s.code GLOB '60[0-9][0-9][0-9][0-9]'
            OR s.code GLOB '688[0-9][0-9][0-9]'
            OR s.code GLOB '300[0-9][0-9][0-9]'
            OR s.code GLOB '301[0-9][0-9][0-9]'
            OR s.code GLOB '00[0-9][0-9][0-9][0-9]'
        )
    """


def _load_trade_dates(conn: sqlite3.Connection, *, start_date: str, end_date: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE trade_date BETWEEN ? AND ?
        ORDER BY trade_date ASC
        """,
        (str(start_date), str(end_date)),
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _load_codes_code_asc(conn: sqlite3.Connection, *, limit: int) -> list[str]:
    rows = conn.execute(
        f"""
        SELECT s.code
        FROM stocks s
        WHERE {_a_share_universe_sql()}
        ORDER BY s.code ASC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _load_codes_top_by_amount(
    conn: sqlite3.Connection,
    *,
    start_date: str,
    end_date: str,
    limit: int,
) -> list[str]:
    rows = conn.execute(
        f"""
        WITH universe AS (
          SELECT s.code
          FROM stocks s
          WHERE {_a_share_universe_sql()}
        ),
        agg AS (
          SELECT d.code, SUM(COALESCE(d.amount, 0.0)) AS amount_sum
          FROM daily_prices d
          JOIN universe u ON u.code = d.code
          WHERE d.trade_date BETWEEN ? AND ?
          GROUP BY d.code
        )
        SELECT a.code
        FROM agg a
        WHERE a.amount_sum > 0
        ORDER BY a.amount_sum DESC, a.code ASC
        LIMIT ?
        """,
        (str(start_date), str(end_date), int(limit)),
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--code-limit", type=int, default=200)
    parser.add_argument("--universe", choices=["top_by_amount", "code_asc"], default="code_asc")
    parser.add_argument("--chaos-db", default="")
    parser.add_argument("--thresholds-version", default="chaos_thresholds_v0")
    parser.add_argument("--registry-version", default="")
    parser.add_argument("--weights-version", default="")
    parser.add_argument("--allow-missing-ratio", type=float, default=0.0)
    parser.add_argument("--min-ready-ratio", type=float, default=0.0)
    args = parser.parse_args()

    stock_db = PROJECT_ROOT / "var" / "db" / "stock_data.db"
    chaos_db = Path(str(args.chaos_db).strip()) if str(args.chaos_db).strip() else (PROJECT_ROOT / "var" / "db" / "chaos_factor_matrix.db")
    if not stock_db.is_file():
        raise SystemExit(f"stock db not found: {stock_db}")
    if not chaos_db.is_file():
        raise SystemExit(f"chaos db not found: {chaos_db}")

    with sqlite3.connect(str(stock_db)) as stock_conn, sqlite3.connect(str(chaos_db)) as chaos_conn:
        trade_dates = _load_trade_dates(stock_conn, start_date=str(args.start_date), end_date=str(args.end_date))
        if str(args.universe) == "top_by_amount":
            codes = _load_codes_top_by_amount(
                stock_conn,
                start_date=str(args.start_date),
                end_date=str(args.end_date),
                limit=int(args.code_limit),
            )
            if not codes:
                codes = _load_codes_code_asc(stock_conn, limit=int(args.code_limit))
        else:
            codes = _load_codes_code_asc(stock_conn, limit=int(args.code_limit))
        report = verify_chaos_operational_gates(
            chaos_conn,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            codes=codes,
            trade_dates=trade_dates,
            thresholds_version=str(args.thresholds_version),
            registry_version=str(args.registry_version).strip() or None,
            weights_version=str(args.weights_version).strip() or None,
            allow_missing_ratio=float(args.allow_missing_ratio),
            min_ready_ratio=float(args.min_ready_ratio),
        )
        print(json.dumps(report.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
