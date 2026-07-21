#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime
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


def _mean(values: list[float]) -> float:
    items = [float(x) for x in list(values or []) if isinstance(x, (int, float))]
    if not items:
        return 0.0
    return float(sum(items)) / float(len(items))


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


def _load_codes_from_file(path: str) -> list[str]:
    p = Path(str(path))
    if not p.is_file():
        raise SystemExit(f"codes file not found: {p}")
    txt = p.read_text(encoding="utf-8").strip()
    if not txt:
        return []
    try:
        data = json.loads(txt)
    except Exception:
        data = None
    if isinstance(data, list):
        return [str(x).strip() for x in data if str(x).strip()]
    return [line.strip() for line in txt.splitlines() if line.strip()]


def _extract_horizon(report: dict[str, Any], horizon: int) -> dict[str, Any]:
    for h in list(report.get("horizons") or []):
        if int(h.get("horizon") or 0) == int(horizon):
            return dict(h)
    return {}


def _extract_spread(h: dict[str, Any]) -> float | None:
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


@dataclass(frozen=True)
class RollingWindowResult:
    start_date: str
    end_date: str
    h10_gate_pass: bool
    h10_accuracy_not_decrease_vs_point: bool
    h10_spread_constraint_applicable: bool
    h10_spread_not_decrease_vs_point: bool | None
    h5_coverage: float
    h10_coverage: float


def _compute_rolling_for_end_date(
    *,
    chaos_conn: sqlite3.Connection,
    stock_conn: sqlite3.Connection,
    end_date: str,
    window_days: int,
    num_windows: int,
    step_days: int,
    codes: list[str],
    thresholds_version: str,
    registry_version: str | None,
    weights_version: str | None,
    signal_mode: str,
    combo_lambda: float | None,
    combo_beta: float | None,
    min_group_ratio: float,
    actual_eps_pct: float,
    recent_k: int,
) -> dict[str, Any]:
    all_dates = _load_trade_dates_upto(stock_conn, end_date=str(end_date))
    if str(end_date) not in set(all_dates):
        return {"end_date": str(end_date), "status": "skip", "reason": "end_date_not_found"}
    end_idx = all_dates.index(str(end_date))
    need = (int(window_days) - 1) + int(step_days) * (int(num_windows) - 1)
    if end_idx < need:
        return {"end_date": str(end_date), "status": "skip", "reason": "not_enough_trade_dates"}

    windows: list[dict[str, Any]] = []
    for k in range(int(num_windows)):
        e = end_idx - int(step_days) * k
        s = e - (int(window_days) - 1)
        trade_dates = all_dates[s : e + 1]
        windows.append({"start_date": trade_dates[0], "end_date": trade_dates[-1], "trade_dates": trade_dates})
    windows = list(reversed(windows))
    overall_start = windows[0]["start_date"]
    overall_end = windows[-1]["end_date"]
    normalized_codes = [str(c).strip() for c in list(codes or []) if str(c).strip()]
    if not normalized_codes:
        return {"end_date": str(end_date), "status": "skip", "reason": "empty_codes"}

    per_window: list[RollingWindowResult] = []
    h10_acc_not_decrease_count = 0
    h10_spread_applicable_count = 0
    h10_spread_not_decrease_count = 0
    h10_gate_pass_count = 0
    cov5_list: list[float] = []
    cov10_list: list[float] = []

    for w in windows:
        rep, _ = evaluate_chaos_m4_monitor(
            chaos_conn=chaos_conn,
            stock_conn=stock_conn,
            codes=normalized_codes,
            trade_dates=list(w["trade_dates"]),
            thresholds_version=str(thresholds_version),
            registry_version=str(registry_version).strip() or None,
            weights_version=str(weights_version).strip() or None,
            horizons=[5, 10],
            signal_mode=str(signal_mode),
            combo_lambda=float(combo_lambda) if combo_lambda is not None else None,
            combo_beta=float(combo_beta) if combo_beta is not None else None,
            actual_eps=float(actual_eps_pct) / 100.0,
        )
        base, _ = evaluate_chaos_m4_monitor(
            chaos_conn=chaos_conn,
            stock_conn=stock_conn,
            codes=normalized_codes,
            trade_dates=list(w["trade_dates"]),
            thresholds_version=str(thresholds_version),
            registry_version=str(registry_version).strip() or None,
            weights_version=str(weights_version).strip() or None,
            horizons=[5, 10],
            signal_mode="point",
            actual_eps=float(actual_eps_pct) / 100.0,
        )

        h5 = _extract_horizon(rep, 5)
        h10 = _extract_horizon(rep, 10)
        b10 = _extract_horizon(base, 10)

        a10 = float(h10.get("accuracy_direction") or 0.0)
        b10_acc = float(b10.get("accuracy_direction") or 0.0)
        h10_acc_ok = bool(float(a10) + 1e-12 >= float(b10_acc))
        if h10_acc_ok:
            h10_acc_not_decrease_count += 1

        valid10 = _spread_valid_by_ratio(h10, min_group_ratio=float(min_group_ratio))
        b_valid10 = _spread_valid_by_ratio(b10, min_group_ratio=float(min_group_ratio))
        s10 = _extract_spread(h10) if valid10 else None
        b10_spread = _extract_spread(b10) if b_valid10 else None
        spread_applicable = bool(s10 is not None and b10_spread is not None)
        if spread_applicable:
            h10_spread_applicable_count += 1
        h10_spread_ok = True
        if spread_applicable:
            h10_spread_ok = bool(float(s10) + 1e-12 >= float(b10_spread))
            if h10_spread_ok:
                h10_spread_not_decrease_count += 1
        if h10_acc_ok and h10_spread_ok:
            h10_gate_pass_count += 1

        cov5 = float(h5.get("evaluable") or 0) / float(h5.get("total") or 1)
        cov10 = float(h10.get("evaluable") or 0) / float(h10.get("total") or 1)
        cov5_list.append(float(cov5))
        cov10_list.append(float(cov10))

        per_window.append(
            RollingWindowResult(
                start_date=str(w["start_date"]),
                end_date=str(w["end_date"]),
                h10_gate_pass=bool(h10_acc_ok and h10_spread_ok),
                h10_accuracy_not_decrease_vs_point=bool(h10_acc_ok),
                h10_spread_constraint_applicable=bool(spread_applicable),
                h10_spread_not_decrease_vs_point=bool(h10_spread_ok) if spread_applicable else None,
                h5_coverage=float(cov5),
                h10_coverage=float(cov10),
            )
        )

    recent = per_window[-int(recent_k) :] if int(recent_k) > 0 else []
    recent_k_pass = bool(recent and all(bool(w.h10_gate_pass) for w in recent))

    return {
        "end_date": str(end_date),
        "status": "ok",
        "overall_start": str(overall_start),
        "overall_end": str(overall_end),
        "summary": {
            "h10_accuracy_not_decrease_window_count": int(h10_acc_not_decrease_count),
            "h10_spread_constraint_applicable_window_count": int(h10_spread_applicable_count),
            "h10_spread_not_decrease_window_count": int(h10_spread_not_decrease_count),
            "h10_gate_pass_window_count": int(h10_gate_pass_count),
            "window_count": int(len(per_window)),
            "recent_k": int(recent_k),
            "recent_k_h10_gate_pass": bool(recent_k_pass),
            "avg_h5_coverage": float(_mean(cov5_list)),
            "avg_h10_coverage": float(_mean(cov10_list)),
        },
        "recent_k": [w.__dict__ for w in recent],
    }


def _weekly_endpoints(trade_dates: list[str]) -> list[str]:
    out: list[str] = []
    last_by_week: dict[tuple[int, int], str] = {}
    for d in list(trade_dates or []):
        di = date.fromisoformat(str(d))
        y, w, _ = di.isocalendar()
        last_by_week[(int(y), int(w))] = str(d)
    for k in sorted(last_by_week.keys()):
        out.append(str(last_by_week[k]))
    return out


def _write_ledger_and_artifact(*, project_root: Path, target_date: str, payload: dict) -> None:
    suffix = str(payload.get("_meta", {}).get("report_suffix") or "").strip()
    name = f"m4_eval_rolling_series_{suffix}.json" if suffix else "m4_eval_rolling_series.json"
    ledger_dir = project_root / "var" / "ledgers" / "chaos_m4_eval" / target_date
    ledger_dir.mkdir(parents=True, exist_ok=True)
    (ledger_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    artifact_dir = project_root / "var" / "artifacts" / "chaos_m4_eval" / target_date
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--window-days", type=int, default=20)
    parser.add_argument("--num-windows", type=int, default=20)
    parser.add_argument("--step-days", type=int, default=1)
    parser.add_argument("--code-limit", type=int, default=200)
    parser.add_argument("--codes-file", default="")
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
        codes_file = str(args.codes_file).strip()
        if codes_file:
            codes = _load_codes_from_file(codes_file)
            universe_payload = {"mode": "fixed_codes", "code_limit": int(len(codes)), "codes_file": str(codes_file)}
        else:
            codes = _load_codes_top_by_amount(
                stock_conn,
                start_date=str(args.start_date),
                end_date=str(args.end_date),
                limit=int(args.code_limit),
            )
            universe_payload = {"mode": "top_by_amount", "code_limit": int(args.code_limit)}

        trade_dates = _load_trade_dates(stock_conn, start_date=str(args.start_date), end_date=str(args.end_date))
        endpoints = _weekly_endpoints(trade_dates)
        results: list[dict[str, Any]] = []
        for ed in endpoints:
            results.append(
                _compute_rolling_for_end_date(
                    chaos_conn=chaos_conn,
                    stock_conn=stock_conn,
                    end_date=str(ed),
                    window_days=int(args.window_days),
                    num_windows=int(args.num_windows),
                    step_days=int(args.step_days),
                    codes=list(codes),
                    thresholds_version=str(args.thresholds_version),
                    registry_version=str(args.registry_version).strip() or None,
                    weights_version=str(args.weights_version).strip() or None,
                    signal_mode=str(args.signal_mode),
                    combo_lambda=float(args.combo_lambda) if args.combo_lambda is not None else None,
                    combo_beta=float(args.combo_beta) if args.combo_beta is not None else None,
                    min_group_ratio=float(args.min_group_ratio),
                    actual_eps_pct=float(args.actual_eps_pct),
                    recent_k=int(args.recent_k),
                )
            )

    payload = {
        "_meta": {
            "status": "ok",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "requested_by": "run_chaos_m4_eval_monitor_rolling_series",
            "report_suffix": str(args.report_suffix).strip(),
        },
        "range": {"start_date": str(args.start_date), "end_date": str(args.end_date)},
        "rolling": {"window_days": int(args.window_days), "num_windows": int(args.num_windows), "step_days": int(args.step_days), "recent_k": int(args.recent_k)},
    "universe": dict(universe_payload),
        "versions": {"thresholds_version": str(args.thresholds_version), "registry_version": str(args.registry_version), "weights_version": str(args.weights_version)},
        "signal": {
            "mode": str(args.signal_mode),
            "combo_lambda": float(args.combo_lambda) if args.combo_lambda is not None else None,
            "combo_beta": float(args.combo_beta) if args.combo_beta is not None else None,
            "min_group_ratio": float(args.min_group_ratio),
            "actual_eps_pct": float(args.actual_eps_pct),
        },
        "weekly_end_dates": results,
    }
    _write_ledger_and_artifact(project_root=PROJECT_ROOT, target_date=str(args.end_date), payload=payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
