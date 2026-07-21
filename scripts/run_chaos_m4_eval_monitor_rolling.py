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


def _mean(values: list[float]) -> float:
    items = [float(x) for x in list(values or []) if isinstance(x, (int, float))]
    if not items:
        return 0.0
    return float(sum(items)) / float(len(items))


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


def _load_trade_dates_upto(conn: sqlite3.Connection, *, end_date: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE trade_date <= ?
        ORDER BY trade_date ASC
        """,
        (str(end_date),),
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
    name = f"m4_eval_rolling_report_{suffix}.json" if suffix else "m4_eval_rolling_report.json"
    ledger_dir = project_root / "var" / "ledgers" / "chaos_m4_eval" / target_date
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / name
    ledger_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_dir = project_root / "var" / "artifacts" / "chaos_m4_eval" / target_date
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / name
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_horizon_accuracy(report: dict[str, Any], horizon: int) -> float:
    for h in list(report.get("horizons") or []):
        if int(h.get("horizon") or 0) == int(horizon):
            return float(h.get("accuracy_direction") or 0.0)
    return 0.0


def _extract_horizon(report: dict[str, Any], horizon: int) -> dict[str, Any]:
    for h in list(report.get("horizons") or []):
        if int(h.get("horizon") or 0) == int(horizon):
            return dict(h)
    return {}


def _extract_horizon_spread(report: dict[str, Any], horizon: int) -> float | None:
    for h in list(report.get("horizons") or []):
        if int(h.get("horizon") or 0) != int(horizon):
            continue
        up = h.get("avg_return_pred_up")
        down = h.get("avg_return_pred_down")
        if up is None or down is None:
            return None
        try:
            return float(up) - float(down)
        except Exception:
            return None
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--window-days", type=int, default=20)
    parser.add_argument("--num-windows", type=int, default=20)
    parser.add_argument("--step-days", type=int, default=1)
    parser.add_argument("--code-limit", type=int, default=200)
    parser.add_argument("--thresholds-version", default="chaos_thresholds_v0")
    parser.add_argument("--registry-version", default="")
    parser.add_argument("--weights-version", default="")
    parser.add_argument("--signal-mode", choices=["point", "regime_speed", "regime_combo"], default="point")
    parser.add_argument("--combo-lambda", type=float, default=None)
    parser.add_argument("--combo-beta", type=float, default=None)
    parser.add_argument("--min-group-ratio", type=float, default=0.1)
    parser.add_argument("--actual-eps-pct", type=float, default=0.0)
    parser.add_argument("--recent-k", type=int, default=8)
    parser.add_argument("--report-suffix", default="")
    args = parser.parse_args()

    stock_db = PROJECT_ROOT / "var" / "db" / "stock_data.db"
    chaos_db = PROJECT_ROOT / "var" / "db" / "chaos_factor_matrix.db"
    if not stock_db.is_file():
        raise SystemExit(f"stock db not found: {stock_db}")
    if not chaos_db.is_file():
        raise SystemExit(f"chaos db not found: {chaos_db}")

    with sqlite3.connect(str(stock_db)) as stock_conn, sqlite3.connect(str(chaos_db)) as chaos_conn:
        all_dates = _load_trade_dates_upto(stock_conn, end_date=str(args.end_date))
        if not all_dates:
            raise SystemExit("no trade_dates found")
        if str(args.end_date) not in set(all_dates):
            raise SystemExit(f"end_date not found in trade_dates: {args.end_date}")
        end_idx = all_dates.index(str(args.end_date))

        window_days = int(args.window_days)
        if window_days < 11:
            raise SystemExit("window_days must be >= 11 to evaluate horizon=10")
        step = int(args.step_days)
        num_windows = int(args.num_windows)
        need = (window_days - 1) + step * (num_windows - 1)
        if end_idx < need:
            raise SystemExit("not enough trade_dates for requested rolling windows")

        windows: list[dict[str, Any]] = []
        for k in range(num_windows):
            e = end_idx - step * k
            s = e - (window_days - 1)
            trade_dates = all_dates[s : e + 1]
            windows.append(
                {
                    "start_date": trade_dates[0],
                    "end_date": trade_dates[-1],
                    "trade_dates": trade_dates,
                }
            )
        windows = list(reversed(windows))
        overall_start = windows[0]["start_date"]
        overall_end = windows[-1]["end_date"]
        codes = _load_codes_top_by_amount(
            stock_conn,
            start_date=str(overall_start),
            end_date=str(overall_end),
            limit=int(args.code_limit),
        )

        per_window: list[dict[str, Any]] = []
        sum_5 = 0.0
        sum_10 = 0.0
        sum_5_spread = 0.0
        sum_10_spread = 0.0
        n_5_spread = 0
        n_10_spread = 0
        h10_acc_not_decrease_count = 0
        h10_spread_applicable_count = 0
        h10_spread_not_decrease_count = 0
        h10_gate_pass_count = 0
        ok_10_count = 0
        for w in windows:
            report, _ = evaluate_chaos_m4_monitor(
                chaos_conn=chaos_conn,
                stock_conn=stock_conn,
                codes=codes,
                trade_dates=list(w["trade_dates"]),
                thresholds_version=str(args.thresholds_version),
                registry_version=str(args.registry_version).strip() or None,
                weights_version=str(args.weights_version).strip() or None,
                horizons=[5, 10],
                signal_mode=str(args.signal_mode),
                combo_lambda=float(args.combo_lambda) if args.combo_lambda is not None else None,
                combo_beta=float(args.combo_beta) if args.combo_beta is not None else None,
                actual_eps=float(args.actual_eps_pct) / 100.0,
            )
            baseline, _ = evaluate_chaos_m4_monitor(
                chaos_conn=chaos_conn,
                stock_conn=stock_conn,
                codes=codes,
                trade_dates=list(w["trade_dates"]),
                thresholds_version=str(args.thresholds_version),
                registry_version=str(args.registry_version).strip() or None,
                weights_version=str(args.weights_version).strip() or None,
                horizons=[5, 10],
                signal_mode="point",
                actual_eps=float(args.actual_eps_pct) / 100.0,
            )
            a5 = _extract_horizon_accuracy(report, 5)
            a10 = _extract_horizon_accuracy(report, 10)
            h5 = _extract_horizon(report, 5)
            h10 = _extract_horizon(report, 10)
            b5 = _extract_horizon(baseline, 5)
            b10 = _extract_horizon(baseline, 10)
            valid5 = _spread_valid_by_ratio(h5, min_group_ratio=float(args.min_group_ratio))
            valid10 = _spread_valid_by_ratio(h10, min_group_ratio=float(args.min_group_ratio))
            b_valid10 = _spread_valid_by_ratio(b10, min_group_ratio=float(args.min_group_ratio))
            s5 = _extract_horizon_spread(report, 5) if valid5 else None
            s10 = _extract_horizon_spread(report, 10) if valid10 else None
            b5_acc = float(b5.get("accuracy_direction") or 0.0)
            b10_acc = float(b10.get("accuracy_direction") or 0.0)
            b5_spread = _extract_horizon_spread(baseline, 5) if _spread_valid_by_ratio(b5, min_group_ratio=float(args.min_group_ratio)) else None
            b10_spread = _extract_horizon_spread(baseline, 10) if b_valid10 else None
            sum_5 += float(a5)
            sum_10 += float(a10)
            if s5 is not None:
                sum_5_spread += float(s5)
                n_5_spread += 1
            if s10 is not None:
                sum_10_spread += float(s10)
                n_10_spread += 1
            h10_acc_ok = bool(float(a10) + 1e-12 >= float(b10_acc))
            if h10_acc_ok:
                h10_acc_not_decrease_count += 1
            spread_applicable = bool(b10_spread is not None and s10 is not None)
            if spread_applicable:
                h10_spread_applicable_count += 1
            h10_spread_ok = True
            if spread_applicable:
                h10_spread_ok = bool(float(s10) + 1e-12 >= float(b10_spread))
                if h10_spread_ok:
                    h10_spread_not_decrease_count += 1
            if h10_acc_ok and h10_spread_ok:
                h10_gate_pass_count += 1
            per_window.append(
                {
                    "start_date": w["start_date"],
                    "end_date": w["end_date"],
                    "h5_accuracy_direction": float(a5),
                    "h10_accuracy_direction": float(a10),
                    "h5_return_spread": float(s5) if s5 is not None else None,
                    "h10_return_spread": float(s10) if s10 is not None else None,
                    "h5_spread_valid": bool(valid5),
                    "h10_spread_valid": bool(valid10),
                    "baseline_point_h5_accuracy_direction": float(b5_acc),
                    "baseline_point_h10_accuracy_direction": float(b10_acc),
                    "baseline_point_h5_return_spread": float(b5_spread) if b5_spread is not None else None,
                    "baseline_point_h10_return_spread": float(b10_spread) if b10_spread is not None else None,
                    "h10_accuracy_not_decrease_vs_point": bool(h10_acc_ok),
                    "h10_spread_not_decrease_vs_point": bool(h10_spread_ok) if spread_applicable else None,
                    "h10_spread_constraint_applicable": bool(spread_applicable),
                    "h10_gate_pass": bool(h10_acc_ok and h10_spread_ok),
                    "h5_coverage": float(h5.get("evaluable") or 0) / float(h5.get("total") or 1),
                    "h10_coverage": float(h10.get("evaluable") or 0) / float(h10.get("total") or 1),
                }
            )
            if float(a10) >= 0:
                ok_10_count += 1

        avg_5 = float(sum_5) / float(len(windows)) if windows else 0.0
        avg_10 = float(sum_10) / float(len(windows)) if windows else 0.0
        avg_5_spread = float(sum_5_spread) / float(n_5_spread) if n_5_spread > 0 else None
        avg_10_spread = float(sum_10_spread) / float(n_10_spread) if n_10_spread > 0 else None
        avg_5_cov = float(_mean([w.get("h5_coverage") for w in per_window if isinstance(w.get("h5_coverage"), (int, float))])) if per_window else 0.0
        avg_10_cov = float(_mean([w.get("h10_coverage") for w in per_window if isinstance(w.get("h10_coverage"), (int, float))])) if per_window else 0.0
        k = int(args.recent_k)
        recent = per_window[-k:] if k > 0 else []
        recent_k_h10_gate_pass = bool(recent and all(bool(w.get("h10_gate_pass")) for w in recent))
        payload = {
            "_meta": {
                "status": "ok",
                "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "requested_by": "run_chaos_m4_eval_monitor_rolling",
                "report_suffix": str(args.report_suffix).strip(),
            },
            "rolling": {
                "end_date": str(args.end_date),
                "window_days": int(args.window_days),
                "num_windows": int(args.num_windows),
                "step_days": int(args.step_days),
                "start_date": str(overall_start),
                "end_date_range": str(overall_end),
            },
            "universe": {"mode": "top_by_amount", "code_limit": int(args.code_limit)},
            "versions": {
                "thresholds_version": str(args.thresholds_version),
                "registry_version": str(args.registry_version),
                "weights_version": str(args.weights_version),
            },
            "signal": {
                "mode": str(args.signal_mode),
                "combo_lambda": float(args.combo_lambda) if args.combo_lambda is not None else None,
                "combo_beta": float(args.combo_beta) if args.combo_beta is not None else None,
                "min_group_ratio": float(args.min_group_ratio),
                "actual_eps_pct": float(args.actual_eps_pct),
            },
            "summary": {
                "avg_h5_accuracy_direction": float(avg_5),
                "avg_h10_accuracy_direction": float(avg_10),
                "avg_h5_return_spread": float(avg_5_spread) if avg_5_spread is not None else None,
                "avg_h10_return_spread": float(avg_10_spread) if avg_10_spread is not None else None,
                "avg_h5_coverage": float(avg_5_cov),
                "avg_h10_coverage": float(avg_10_cov),
                "h5_spread_valid_window_count": int(n_5_spread),
                "h10_spread_valid_window_count": int(n_10_spread),
                "h10_accuracy_not_decrease_window_count": int(h10_acc_not_decrease_count),
                "h10_spread_constraint_applicable_window_count": int(h10_spread_applicable_count),
                "h10_spread_not_decrease_window_count": int(h10_spread_not_decrease_count),
                "h10_gate_pass_window_count": int(h10_gate_pass_count),
                "recent_k": int(k),
                "recent_k_h10_gate_pass": bool(recent_k_h10_gate_pass),
                "window_count": int(len(windows)),
                "h10_nonnegative_count": int(ok_10_count),
            },
            "per_window": per_window,
        }

    _write_ledger_and_artifact(project_root=PROJECT_ROOT, target_date=str(args.end_date), payload=payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
