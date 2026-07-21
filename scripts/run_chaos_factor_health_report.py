#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neotrade3.chaos.registry import load_chaos_factor_registry


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


def _percentile(values: list[float], p: float) -> float | None:
    items = sorted([float(x) for x in list(values or []) if isinstance(x, (int, float))])
    if not items:
        return None
    q = max(0.0, min(1.0, float(p)))
    idx = int(round(q * float(len(items) - 1)))
    return float(items[idx])


def _write_ledger_and_artifact(*, project_root: Path, target_date: str, payload: dict) -> None:
    ledger_dir = project_root / "var" / "ledgers" / "chaos_factor_health" / target_date
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "factor_health_report.json"
    ledger_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_dir = project_root / "var" / "artifacts" / "chaos_factor_health" / target_date
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "factor_health_report.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--code-limit", type=int, default=200)
    parser.add_argument("--registry-id", default="v1")
    parser.add_argument("--registry-version", default="chaos_registry_v1")
    parser.add_argument("--weights-version", default="chaos_weights_v1")
    parser.add_argument("--thresholds-version", default="chaos_thresholds_v0")
    args = parser.parse_args()

    stock_db = PROJECT_ROOT / "var" / "db" / "stock_data.db"
    chaos_db = PROJECT_ROOT / "var" / "db" / "chaos_factor_matrix.db"
    if not stock_db.is_file():
        raise SystemExit(f"stock db not found: {stock_db}")
    if not chaos_db.is_file():
        raise SystemExit(f"chaos db not found: {chaos_db}")

    registry = load_chaos_factor_registry(project_root=PROJECT_ROOT, registry_id=str(args.registry_id))

    with sqlite3.connect(str(stock_db)) as stock_conn, sqlite3.connect(str(chaos_db)) as chaos_conn:
        trade_dates = _load_trade_dates(stock_conn, start_date=str(args.start_date), end_date=str(args.end_date))
        codes = _load_codes_top_by_amount(
            stock_conn,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            limit=int(args.code_limit),
        )
        expected_rows = int(len(codes)) * int(len(trade_dates))
        placeholders_codes = ",".join(["?"] * len(codes))
        placeholders_dates = ",".join(["?"] * len(trade_dates))

        by_factor: list[dict[str, Any]] = []
        for f in registry.factors:
            fid = str(f.factor_id or "").strip()
            if not fid:
                continue
            rows = chaos_conn.execute(
                f"""
                SELECT factor_value
                FROM chaos_factor_values
                WHERE registry_version = ?
                  AND factor_id = ?
                  AND code IN ({placeholders_codes})
                  AND trade_date IN ({placeholders_dates})
                """,
                [str(args.registry_version), str(fid)] + list(codes) + list(trade_dates),
            ).fetchall()
            values = [float(r[0]) for r in rows if r and isinstance(r[0], (int, float))]
            cnt = int(len(values))
            nz = int(sum(1 for x in values if float(x) != 0.0))
            cov = float(cnt) / float(expected_rows) if expected_rows > 0 else 0.0
            zero_ratio = float(cnt - nz) / float(cnt) if cnt > 0 else 1.0
            by_factor.append(
                {
                    "factor_id": fid,
                    "yin_or_yang": str(f.yin_or_yang),
                    "category": str(f.category),
                    "normalization": str(f.normalization),
                    "default_weight": float(f.default_weight),
                    "expected_rows": int(expected_rows),
                    "rows_present": int(cnt),
                    "coverage": float(cov),
                    "zero_ratio": float(zero_ratio),
                    "min": min(values) if values else None,
                    "p25": _percentile(values, 0.25),
                    "median": float(median(values)) if values else None,
                    "p75": _percentile(values, 0.75),
                    "max": max(values) if values else None,
                }
            )

    payload = {
        "_meta": {
            "status": "ok",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "requested_by": "run_chaos_factor_health_report",
        },
        "range": {"start_date": str(args.start_date), "end_date": str(args.end_date)},
        "universe": {"mode": "top_by_amount", "code_limit": int(args.code_limit)},
        "registry": {
            "registry_id": str(args.registry_id),
            "registry_version": str(args.registry_version),
            "weights_version": str(args.weights_version),
            "thresholds_version": str(args.thresholds_version),
            "factor_count": int(len(list(registry.factors))),
        },
        "summary": {
            "code_count": int(len(codes)),
            "trade_date_count": int(len(trade_dates)),
            "expected_rows": int(expected_rows),
        },
        "factors": by_factor,
    }
    _write_ledger_and_artifact(project_root=PROJECT_ROOT, target_date=str(args.end_date), payload=payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

