#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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


def _extract_horizon(report: dict[str, Any], *, horizon: int) -> dict[str, Any]:
    for h in list(report.get("horizons") or []):
        if int(h.get("horizon") or 0) == int(horizon):
            return dict(h)
    return {}


def _spread(h: dict[str, Any]) -> float | None:
    up = h.get("avg_return_pred_up")
    down = h.get("avg_return_pred_down")
    if up is None or down is None:
        return None
    try:
        return float(up) - float(down)
    except Exception:
        return None


def _spread_valid_by_ratio(h: dict[str, Any], *, min_group_ratio: float) -> bool:
    evaluable = int(h.get("evaluable") or 0)
    up = int(h.get("pred_up_count") or 0)
    down = int(h.get("pred_down_count") or 0)
    r = float(min_group_ratio)
    if evaluable <= 0:
        return False
    if r <= 0:
        return up > 0 and down > 0
    min_cnt = int(math.ceil(float(evaluable) * float(r)))
    return up >= min_cnt and down >= min_cnt


def _write_ledger_and_artifact(*, project_root: Path, target_date: str, payload: dict) -> None:
    suffix = str(payload.get("_meta", {}).get("report_suffix") or "").strip()
    name = f"m4_gate_v1_sweep_report_{suffix}.json" if suffix else "m4_gate_v1_sweep_report.json"
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
    parser.add_argument("--lambdas", default="0,0.1,0.25,0.5,1,2")
    parser.add_argument("--betas", default="-2,-1,-0.5,-0.25,-0.1,0,0.1,0.25,0.5,1,2")
    parser.add_argument("--min-group-ratio", type=float, default=0.1)
    parser.add_argument("--actual-eps-pct", type=float, default=0.0)
    parser.add_argument("--report-suffix", default="")
    args = parser.parse_args()

    stock_db = PROJECT_ROOT / "var" / "db" / "stock_data.db"
    chaos_db = PROJECT_ROOT / "var" / "db" / "chaos_factor_matrix.db"
    if not stock_db.is_file():
        raise SystemExit(f"stock db not found: {stock_db}")
    if not chaos_db.is_file():
        raise SystemExit(f"chaos db not found: {chaos_db}")

    lambdas = [float(x) for x in str(args.lambdas).split(",") if str(x).strip() != ""]
    betas = [float(x) for x in str(args.betas).split(",") if str(x).strip() != ""]

    with sqlite3.connect(str(stock_db)) as stock_conn, sqlite3.connect(str(chaos_db)) as chaos_conn:
        trade_dates = _load_trade_dates(stock_conn, start_date=str(args.start_date), end_date=str(args.end_date))
        codes = _load_codes_top_by_amount(
            stock_conn,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            limit=int(args.code_limit),
        )

        base_report, _ = evaluate_chaos_m4_monitor(
            chaos_conn=chaos_conn,
            stock_conn=stock_conn,
            codes=codes,
            trade_dates=trade_dates,
            thresholds_version=str(args.thresholds_version),
            registry_version=str(args.registry_version).strip() or None,
            weights_version=str(args.weights_version).strip() or None,
            horizons=[5, 10],
            signal_mode="point",
            actual_eps=float(args.actual_eps_pct) / 100.0,
        )
        base5 = _extract_horizon(base_report, horizon=5)
        base10 = _extract_horizon(base_report, horizon=10)
        base10_acc = float(base10.get("accuracy_direction") or 0.0)
        base10_spread = _spread(base10) if _spread_valid_by_ratio(base10, min_group_ratio=float(args.min_group_ratio)) else None

        candidates: list[dict[str, Any]] = []
        for lam in lambdas:
            for beta in betas:
                rep, _ = evaluate_chaos_m4_monitor(
                    chaos_conn=chaos_conn,
                    stock_conn=stock_conn,
                    codes=codes,
                    trade_dates=trade_dates,
                    thresholds_version=str(args.thresholds_version),
                    registry_version=str(args.registry_version).strip() or None,
                    weights_version=str(args.weights_version).strip() or None,
                    horizons=[5, 10],
                    signal_mode="regime_combo",
                    combo_lambda=float(lam),
                    combo_beta=float(beta),
                    actual_eps=float(args.actual_eps_pct) / 100.0,
                )
                h5 = _extract_horizon(rep, horizon=5)
                h10 = _extract_horizon(rep, horizon=10)
                h10_acc = float(h10.get("accuracy_direction") or 0.0)
                h10_spread = _spread(h10) if _spread_valid_by_ratio(h10, min_group_ratio=float(args.min_group_ratio)) else None

                ok_acc = bool(float(h10_acc) + 1e-12 >= float(base10_acc))
                ok_spread = True
                if base10_spread is not None:
                    ok_spread = bool(h10_spread is not None and float(h10_spread) + 1e-12 >= float(base10_spread))
                if not (ok_acc and ok_spread):
                    continue
                candidates.append(
                    {
                        "lambda": float(lam),
                        "beta": float(beta),
                        "h5_accuracy_direction": float(h5.get("accuracy_direction") or 0.0),
                        "h10_accuracy_direction": float(h10_acc),
                        "h5_return_spread": _spread(h5),
                        "h10_return_spread": h10_spread,
                        "h5_pred_up_count": int(h5.get("pred_up_count") or 0),
                        "h5_pred_down_count": int(h5.get("pred_down_count") or 0),
                        "h10_pred_up_count": int(h10.get("pred_up_count") or 0),
                        "h10_pred_down_count": int(h10.get("pred_down_count") or 0),
                    }
                )

    candidates.sort(
        key=lambda x: (
            -float(x.get("h5_accuracy_direction") or 0.0),
            -(float(x.get("h5_return_spread") or 0.0) if x.get("h5_return_spread") is not None else -1e9),
            float(x.get("lambda") or 0.0),
            float(x.get("beta") or 0.0),
        )
    )
    best = candidates[0] if candidates else None

    payload = {
        "_meta": {
            "status": "ok",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "requested_by": "run_chaos_m4_gate_v1_sweep",
            "report_suffix": str(args.report_suffix).strip(),
        },
        "range": {"start_date": str(args.start_date), "end_date": str(args.end_date)},
        "universe": {"mode": "top_by_amount", "code_limit": int(args.code_limit)},
        "versions": {
            "thresholds_version": str(args.thresholds_version),
            "registry_version": str(args.registry_version),
            "weights_version": str(args.weights_version),
        },
        "gate_v1": {
            "constraints": {
                "10d_accuracy_direction_not_decrease_vs_point": True,
                "10d_return_spread_not_decrease_vs_point": base10_spread is not None,
                "min_group_ratio": float(args.min_group_ratio),
                "actual_eps_pct": float(args.actual_eps_pct),
            },
            "objective": ["maximize_5d_accuracy_direction", "maximize_5d_return_spread"],
        },
        "baseline_point": {
            "h5": {
                "accuracy_direction": float(base5.get("accuracy_direction") or 0.0),
                "return_spread": _spread(base5),
                "pred_up_count": int(base5.get("pred_up_count") or 0),
                "pred_down_count": int(base5.get("pred_down_count") or 0),
            },
            "h10": {
                "accuracy_direction": float(base10_acc),
                "return_spread": base10_spread,
                "pred_up_count": int(base10.get("pred_up_count") or 0),
                "pred_down_count": int(base10.get("pred_down_count") or 0),
            },
        },
        "grid": {"lambdas": lambdas, "betas": betas},
        "candidates_count": int(len(candidates)),
        "best": best,
        "top10": candidates[:10],
    }
    _write_ledger_and_artifact(project_root=PROJECT_ROOT, target_date=str(args.end_date), payload=payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
