#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_OUTPUT_ROOT = PROJECT_ROOT / ".runtime_outputs"
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


def _parse_int_list(raw: str) -> list[int]:
    values: list[int] = []
    for token in str(raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        values.append(int(token))
    return values


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


def _load_codes_all_a_share(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        f"""
        SELECT s.code
        FROM stocks s
        WHERE {_a_share_universe_sql()}
        ORDER BY s.code ASC
        """
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


def _summarize_by_horizon(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in metrics:
        h = int(item.get("horizon") or 0)
        out[str(h)] = {
            "return_spread": item.get("return_spread"),
            "accuracy_direction": item.get("accuracy_direction"),
            "evaluable": item.get("evaluable"),
            "pred_up_count": item.get("pred_up_count"),
            "pred_down_count": item.get("pred_down_count"),
            "skipped_missing_snapshot": item.get("skipped_missing_snapshot"),
            "skipped_missing_price": item.get("skipped_missing_price"),
            "skipped_quality_gate": item.get("skipped_quality_gate"),
            "skipped_small_move": item.get("skipped_small_move"),
        }
    return out


def _build_context_gain_summary(
    *,
    stock_only: dict[str, Any],
    stock_theme: dict[str, Any],
    stock_theme_market: dict[str, Any],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    stock_only_h = _summarize_by_horizon(stock_only["horizons"])
    stock_theme_h = _summarize_by_horizon(stock_theme["horizons"])
    stock_theme_market_h = _summarize_by_horizon(stock_theme_market["horizons"])
    all_horizons = sorted({*stock_only_h.keys(), *stock_theme_h.keys(), *stock_theme_market_h.keys()}, key=int)
    for horizon in all_horizons:
        base = stock_only_h.get(horizon, {})
        theme = stock_theme_h.get(horizon, {})
        market = stock_theme_market_h.get(horizon, {})
        base_spread = base.get("return_spread")
        theme_spread = theme.get("return_spread")
        market_spread = market.get("return_spread")
        summary[horizon] = {
            "stock_only_spread": base_spread,
            "stock_theme_spread": theme_spread,
            "stock_theme_market_spread": market_spread,
            "theme_gain_vs_stock_only": (
                float(theme_spread) - float(base_spread)
                if theme_spread is not None and base_spread is not None
                else None
            ),
            "theme_market_gain_vs_stock_only": (
                float(market_spread) - float(base_spread)
                if market_spread is not None and base_spread is not None
                else None
            ),
        }
    return summary


def _build_short_vs_midterm_summary(
    *,
    short_reports: dict[str, dict[str, Any]],
    midterm_reports: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for context_mode, short_report in short_reports.items():
        midterm_report = midterm_reports.get(context_mode) or {}
        summary[context_mode] = {
            "short": _summarize_by_horizon(short_report.get("horizons", [])),
            "midterm": _summarize_by_horizon(midterm_report.get("horizons", [])),
        }
    return summary


def _resolve_output_roots(
    *,
    project_root: Path,
    output_root: str,
) -> tuple[Path, Path, dict[str, Any]]:
    raw_output_root = str(output_root or "").strip()
    if not raw_output_root:
        return (
            project_root / "var" / "ledgers",
            project_root / "var" / "artifacts",
            {
                "output_mode": "var_symlink_default",
                "output_root": "",
                "canonical_output_mode": "var_symlink_default",
                "temporary_output": False,
            },
        )

    base_root = Path(raw_output_root).expanduser()
    if not base_root.is_absolute():
        base_root = (project_root / base_root).resolve()
    else:
        base_root = base_root.resolve()
    runtime_root = (project_root / ".runtime_outputs").resolve()
    try:
        base_root.relative_to(runtime_root)
    except ValueError as exc:
        raise SystemExit(
            f"output_root must stay under dedicated runtime root: {runtime_root}"
        ) from exc
    return (
        base_root / "ledgers",
        base_root / "artifacts",
        {
            "output_mode": "override_local",
            "output_root": str(base_root),
            "canonical_output_mode": "var_symlink_default",
            "temporary_output": True,
        },
    )


def _write_outputs(
    *,
    ledger_root: Path,
    artifact_root: Path,
    target_date: str,
    payload: dict[str, Any],
    suffix: str,
) -> None:
    name = f"chaos_midterm_validation_{suffix}.json" if suffix else "chaos_midterm_validation.json"
    ledger_dir = ledger_root / "chaos_midterm_validation" / target_date
    ledger_dir.mkdir(parents=True, exist_ok=True)
    (ledger_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_dir = artifact_root / "chaos_midterm_validation" / target_date
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--universe", choices=["all_a_share", "top_by_amount"], default="all_a_share")
    parser.add_argument("--code-limit", type=int, default=200)
    parser.add_argument("--thresholds-version", default="chaos_thresholds_v0")
    parser.add_argument("--registry-version", default="")
    parser.add_argument("--weights-version", default="")
    parser.add_argument("--signal-mode", choices=["point", "regime_speed", "regime_combo"], default="regime_combo")
    parser.add_argument("--combo-lambda", type=float, default=0.5)
    parser.add_argument("--combo-beta", type=float, default=-0.5)
    parser.add_argument("--midterm-horizons", default="20,40,60")
    parser.add_argument("--short-horizons", default="5,10")
    parser.add_argument("--actual-eps-pct", type=float, default=0.0)
    parser.add_argument("--stock-db", default=str(PROJECT_ROOT / "var" / "db" / "stock_data.db"))
    parser.add_argument("--chaos-db", default=str(PROJECT_ROOT / "var" / "db" / "chaos_factor_matrix_a_share.db"))
    parser.add_argument("--report-suffix", default="")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--retention-days", type=int, default=14)
    args = parser.parse_args()

    stock_db = Path(str(args.stock_db))
    chaos_db = Path(str(args.chaos_db))
    if not stock_db.is_file():
        raise SystemExit(f"stock db not found: {stock_db}")
    if not chaos_db.is_file():
        raise SystemExit(f"chaos db not found: {chaos_db}")

    midterm_horizons = _parse_int_list(str(args.midterm_horizons))
    short_horizons = _parse_int_list(str(args.short_horizons))
    context_modes = ["stock_only", "stock_theme", "stock_theme_market"]
    retention_days = max(1, int(args.retention_days))
    ledger_root, artifact_root, output_meta = _resolve_output_roots(
        project_root=PROJECT_ROOT,
        output_root=str(args.output_root),
    )
    generated_at = datetime.utcnow()
    expires_after = (generated_at + timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with sqlite3.connect(str(stock_db)) as stock_conn, sqlite3.connect(str(chaos_db)) as chaos_conn:
        trade_dates = _load_trade_dates(stock_conn, start_date=str(args.start_date), end_date=str(args.end_date))
        if str(args.universe) == "all_a_share":
            codes = _load_codes_all_a_share(stock_conn)
        else:
            codes = _load_codes_top_by_amount(
                stock_conn,
                start_date=str(args.start_date),
                end_date=str(args.end_date),
                limit=int(args.code_limit),
            )

        midterm_reports: dict[str, dict[str, Any]] = {}
        short_reports: dict[str, dict[str, Any]] = {}
        for context_mode in context_modes:
            report, _ = evaluate_chaos_m4_monitor(
                chaos_conn=chaos_conn,
                stock_conn=stock_conn,
                codes=codes,
                trade_dates=trade_dates,
                thresholds_version=str(args.thresholds_version),
                registry_version=str(args.registry_version).strip() or None,
                weights_version=str(args.weights_version).strip() or None,
                horizons=midterm_horizons,
                signal_mode=str(args.signal_mode),
                combo_lambda=float(args.combo_lambda) if args.combo_lambda is not None else None,
                combo_beta=float(args.combo_beta) if args.combo_beta is not None else None,
                actual_eps=float(args.actual_eps_pct) / 100.0,
                context_mode=context_mode,
            )
            report["theme_context_source_mode"] = (
                "none"
                if context_mode == "stock_only"
                else "provisional_theme_context_source"
            )
            report["theme_context_source_details"] = (
                "stock_only"
                if context_mode == "stock_only"
                else "sector facts from stock_data.db; concept facts from ths_concept_daily plus warmed concept caches"
            )
            report["version_lock_scope"] = "run_level_only"
            midterm_reports[context_mode] = report

            short_report, _ = evaluate_chaos_m4_monitor(
                chaos_conn=chaos_conn,
                stock_conn=stock_conn,
                codes=codes,
                trade_dates=trade_dates,
                thresholds_version=str(args.thresholds_version),
                registry_version=str(args.registry_version).strip() or None,
                weights_version=str(args.weights_version).strip() or None,
                horizons=short_horizons,
                signal_mode=str(args.signal_mode),
                combo_lambda=float(args.combo_lambda) if args.combo_lambda is not None else None,
                combo_beta=float(args.combo_beta) if args.combo_beta is not None else None,
                actual_eps=float(args.actual_eps_pct) / 100.0,
                context_mode=context_mode,
            )
            short_reports[context_mode] = short_report

    payload = {
        "_meta": {
            "status": "ok",
            "generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "requested_by": "run_chaos_midterm_validation",
            "report_suffix": str(args.report_suffix).strip(),
            "output_mode": output_meta["output_mode"],
            "output_root": output_meta["output_root"],
            "canonical_output_mode": output_meta["canonical_output_mode"],
            "temporary_output": output_meta["temporary_output"],
            "retention_days": retention_days,
            "expires_after": expires_after,
        },
        "validation_contract": {
            "midterm_horizons": midterm_horizons,
            "short_horizons": short_horizons,
            "contexts": context_modes,
            "version_lock_scope": "run_level_only",
        },
        "universe": {
            "mode": str(args.universe),
            "code_count": int(len(codes)),
            "code_limit": int(args.code_limit) if str(args.universe) == "top_by_amount" else None,
            "trade_date_count": int(len(trade_dates)),
        },
        "reports": {
            "midterm": midterm_reports,
            "short": short_reports,
        },
        "summaries": {
            "context_gain_midterm": _build_context_gain_summary(
                stock_only=midterm_reports["stock_only"],
                stock_theme=midterm_reports["stock_theme"],
                stock_theme_market=midterm_reports["stock_theme_market"],
            ),
            "short_vs_midterm": _build_short_vs_midterm_summary(
                short_reports=short_reports,
                midterm_reports=midterm_reports,
            ),
        },
    }
    _write_outputs(
        ledger_root=ledger_root,
        artifact_root=artifact_root,
        target_date=str(args.end_date),
        payload=payload,
        suffix=str(args.report_suffix).strip(),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
