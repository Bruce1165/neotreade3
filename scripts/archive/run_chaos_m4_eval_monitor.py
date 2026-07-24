#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neotrade3.chaos.m4_eval_monitor import evaluate_chaos_m4_monitor


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


def _write_ledger_and_artifact(*, project_root: Path, target_date: str, payload: dict) -> None:
    suffix = str(payload.get("_meta", {}).get("report_suffix") or "").strip()
    name = f"m4_eval_report_{suffix}.json" if suffix else "m4_eval_report.json"
    ledger_dir = project_root / "var" / "ledgers" / "chaos_m4_eval" / target_date
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / name
    ledger_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_dir = project_root / "var" / "artifacts" / "chaos_m4_eval" / target_date
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / name
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--code-limit", type=int, default=200)
    parser.add_argument("--thresholds-version", default="chaos_thresholds_v0")
    parser.add_argument("--registry-version", default="")
    parser.add_argument("--weights-version", default="")
    parser.add_argument("--universe", choices=["top_by_amount"], default="top_by_amount")
    parser.add_argument("--signal-mode", choices=["point", "regime_speed", "regime_combo"], default="point")
    parser.add_argument("--combo-lambda", type=float, default=None)
    parser.add_argument("--combo-beta", type=float, default=None)
    parser.add_argument("--report-suffix", default="")
    parser.add_argument("--actual-eps-pct", type=float, default=0.0)
    args = parser.parse_args()

    stock_db = PROJECT_ROOT / "var" / "db" / "stock_data.db"
    chaos_db = PROJECT_ROOT / "var" / "db" / "chaos_factor_matrix.db"
    if not stock_db.is_file():
        raise SystemExit(f"stock db not found: {stock_db}")
    if not chaos_db.is_file():
        raise SystemExit(f"chaos db not found: {chaos_db}")

    with sqlite3.connect(str(stock_db)) as stock_conn, sqlite3.connect(str(chaos_db)) as chaos_conn:
        trade_dates = _load_trade_dates(stock_conn, start_date=str(args.start_date), end_date=str(args.end_date))
        codes = _load_codes_top_by_amount(
            stock_conn,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            limit=int(args.code_limit),
        )
        report, _ = evaluate_chaos_m4_monitor(
            chaos_conn=chaos_conn,
            stock_conn=stock_conn,
            codes=codes,
            trade_dates=trade_dates,
            thresholds_version=str(args.thresholds_version),
            registry_version=str(args.registry_version).strip() or None,
            weights_version=str(args.weights_version).strip() or None,
            horizons=[5, 10],
            signal_mode=str(args.signal_mode),
            combo_lambda=float(args.combo_lambda) if args.combo_lambda is not None else None,
            combo_beta=float(args.combo_beta) if args.combo_beta is not None else None,
            actual_eps=float(args.actual_eps_pct) / 100.0,
        )

    payload = {
        "_meta": {
            "status": "ok",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "requested_by": "run_chaos_m4_eval_monitor",
            "report_suffix": str(args.report_suffix).strip(),
        },
        "universe": {"mode": str(args.universe), "code_limit": int(args.code_limit)},
        "report": report,
    }
    _write_ledger_and_artifact(project_root=PROJECT_ROOT, target_date=str(args.end_date), payload=payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
