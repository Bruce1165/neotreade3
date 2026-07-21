#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neotrade3.chaos.projection_v1 import ChaosProjectionContext, compute_factor_contributions_v1
from neotrade3.chaos.registry import load_chaos_factor_registry
from neotrade3.chaos.weights import load_chaos_weights


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


def _sign(v: float) -> int:
    if float(v) > 0:
        return 1
    if float(v) < 0:
        return -1
    return 0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(v)))


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


def _load_stock_sector_map(conn: sqlite3.Connection, *, codes: list[str]) -> dict[str, str]:
    if not codes:
        return {}
    placeholders = ",".join(["?"] * len(codes))
    rows = conn.execute(
        f"SELECT code, sector_lv1 FROM stocks WHERE code IN ({placeholders})",
        tuple(codes),
    ).fetchall()
    return {str(r[0]): str(r[1] or "") for r in rows if r and r[0]}


def _load_amount_rank_map(conn: sqlite3.Connection, *, trade_date: str) -> dict[str, int]:
    rows = conn.execute(
        f"""
        SELECT dp.code, dp.amount
        FROM daily_prices dp
        JOIN stocks s ON s.code = dp.code
        WHERE dp.trade_date = ?
          AND {_a_share_universe_sql()}
          AND dp.amount IS NOT NULL
          AND dp.amount > 0
        """,
        (str(trade_date),),
    ).fetchall()
    items = [(str(r[0]), float(r[1])) for r in rows if r and r[0] and isinstance(r[1], (int, float))]
    items.sort(key=lambda x: (-x[1], x[0]))
    out: dict[str, int] = {}
    for idx, (code, _amount) in enumerate(items, start=1):
        out[code] = int(idx)
    return out


def _load_sector_amount_rank_map(conn: sqlite3.Connection, *, trade_date: str) -> dict[str, int]:
    rows = conn.execute(
        f"""
        SELECT s.sector_lv1, SUM(COALESCE(dp.amount, 0.0)) AS total_amount
        FROM daily_prices dp
        JOIN stocks s ON s.code = dp.code
        WHERE dp.trade_date = ?
          AND {_a_share_universe_sql()}
        GROUP BY s.sector_lv1
        HAVING total_amount > 0
        """,
        (str(trade_date),),
    ).fetchall()
    items = [(str(r[0] or ""), float(r[1] or 0.0)) for r in rows if r and r[0]]
    items.sort(key=lambda x: (-x[1], x[0]))
    out: dict[str, int] = {}
    for idx, (sector, _amount) in enumerate(items, start=1):
        out[sector] = int(idx)
    return out


def _load_ready_raw_factors(
    conn: sqlite3.Connection,
    *,
    codes: list[str],
    trade_dates: list[str],
    thresholds_version: str,
    registry_version: str,
    weights_version: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    if not codes or not trade_dates:
        return {}
    placeholders_codes = ",".join(["?"] * len(codes))
    placeholders_dates = ",".join(["?"] * len(trade_dates))
    rows = conn.execute(
        f"""
        SELECT code, trade_date, raw_factors_json
        FROM chaos_daily_snapshot
        WHERE chaos_status = 'ready'
          AND thresholds_version = ?
          AND registry_version = ?
          AND weights_version = ?
          AND code IN ({placeholders_codes})
          AND trade_date IN ({placeholders_dates})
        """,
        [str(thresholds_version), str(registry_version), str(weights_version)] + list(codes) + list(trade_dates),
    ).fetchall()
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for code, trade_date, raw_json in rows:
        if not code or not trade_date:
            continue
        try:
            payload = json.loads(raw_json) if isinstance(raw_json, str) else {}
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        out[(str(code), str(trade_date))] = payload
    return out


def _load_distinct_versions(
    conn: sqlite3.Connection,
    *,
    trade_dates: list[str],
    thresholds_version: str,
) -> list[dict[str, Any]]:
    if not trade_dates:
        return []
    placeholders_dates = ",".join(["?"] * len(trade_dates))
    rows = conn.execute(
        f"""
        SELECT registry_version, weights_version, COUNT(1) AS rows_cnt
        FROM chaos_daily_snapshot
        WHERE chaos_status = 'ready'
          AND thresholds_version = ?
          AND trade_date IN ({placeholders_dates})
        GROUP BY registry_version, weights_version
        ORDER BY rows_cnt DESC, registry_version ASC, weights_version ASC
        """,
        [str(thresholds_version)] + list(trade_dates),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for rv, wv, cnt in rows:
        out.append({"registry_version": str(rv or ""), "weights_version": str(wv or ""), "rows": int(cnt or 0)})
    return out


def _assert_versions_consistent(*, registry, base_weights, registry_version: str, base_weights_version: str) -> None:
    rv = str(registry_version).strip()
    wv = str(base_weights_version).strip()
    if rv and str(registry.version).strip() and rv != str(registry.version).strip():
        raise ValueError(f"registry_version mismatch: args={rv} loaded={registry.version}")
    if wv and str(base_weights.version).strip() and wv != str(base_weights.version).strip():
        raise ValueError(f"base_weights_version mismatch: args={wv} loaded={base_weights.version}")


def _load_close_map(conn: sqlite3.Connection, *, codes: list[str], trade_dates_all: list[str]) -> dict[tuple[str, str], float]:
    if not codes or not trade_dates_all:
        return {}
    placeholders_codes = ",".join(["?"] * len(codes))
    placeholders_dates = ",".join(["?"] * len(trade_dates_all))
    rows = conn.execute(
        f"""
        SELECT trade_date, code, close
        FROM daily_prices
        WHERE code IN ({placeholders_codes})
          AND trade_date IN ({placeholders_dates})
        """,
        list(codes) + list(trade_dates_all),
    ).fetchall()
    out: dict[tuple[str, str], float] = {}
    for d, c, close in rows:
        if not d or not c or close is None:
            continue
        if isinstance(close, (int, float)):
            out[(str(c), str(d))] = float(close)
    return out


def _evaluate_window(
    *,
    registry,
    weights_map: dict[str, float],
    codes: list[str],
    trade_dates: list[str],
    stock_sector_map: dict[str, str],
    amount_rank_by_date: dict[str, dict[str, int]],
    sector_rank_by_date: dict[str, dict[str, int]],
    raw_by_key: dict[tuple[str, str], dict[str, Any]],
    close_by_key: dict[tuple[str, str], float],
    horizon: int,
) -> dict[str, Any]:
    evaluable = 0
    correct = 0
    skipped_missing_price = 0
    factor_weighted_score_sum: dict[str, float] = {}
    factor_weight_sum: dict[str, float] = {}
    date_to_index = {d: i for i, d in enumerate(trade_dates)}

    for code in codes:
        for d in trade_dates:
            raw = raw_by_key.get((code, d))
            if raw is None:
                continue
            i = date_to_index.get(d)
            if i is None:
                continue
            j = i + int(horizon)
            if j >= len(trade_dates):
                skipped_missing_price += 1
                continue
            d2 = trade_dates[j]
            c0 = close_by_key.get((code, d))
            c1 = close_by_key.get((code, d2))
            if c0 is None or c1 is None or float(c0) <= 0:
                skipped_missing_price += 1
                continue
            ret = float(c1) / float(c0) - 1.0
            y = _sign(ret)
            if y == 0:
                continue
            sector = str(stock_sector_map.get(code) or "")
            am_map = amount_rank_by_date.get(d) or {}
            sm_map = sector_rank_by_date.get(d) or {}
            ctx = ChaosProjectionContext(
                amount_rank=int(am_map.get(code) or 0),
                amount_universe_size=int(len(am_map)),
                sector_amount_rank=int(sm_map.get(sector) or 0),
                sector_count=int(len(sm_map)),
            )
            contribs = compute_factor_contributions_v1(raw_factors=raw, registry=registry, ctx=ctx, weights_override=weights_map)
            net = float(sum(c.contrib_signed for c in contribs))
            pred = _sign(net)
            evaluable += 1
            if pred == y:
                correct += 1
            for c in contribs:
                abs_c = abs(float(c.contrib_signed))
                if abs_c <= 0:
                    continue
                fid = c.factor_id
                factor_weighted_score_sum[fid] = float(factor_weighted_score_sum.get(fid, 0.0)) + abs_c * float(y)
                factor_weight_sum[fid] = float(factor_weight_sum.get(fid, 0.0)) + abs_c

    acc = float(correct) / float(evaluable) if evaluable > 0 else 0.0
    factor_scores: dict[str, float] = {}
    for fid, wsum in factor_weight_sum.items():
        if float(wsum) <= 0:
            continue
        score = float(factor_weighted_score_sum.get(fid, 0.0)) / float(wsum)
        factor_scores[fid] = float(_clamp(score, -1.0, 1.0))

    return {
        "horizon": int(horizon),
        "evaluable": int(evaluable),
        "correct": int(correct),
        "accuracy_direction": float(acc),
        "skipped_missing_price": int(skipped_missing_price),
        "factor_scores": factor_scores,
    }


def _write_weights_file(*, project_root: Path, weights_version: str, weights_map: dict[str, float], payload: dict[str, Any]) -> Path:
    ver = str(weights_version).strip()
    suffix = ver[len("chaos_weights_") :] if ver.startswith("chaos_weights_") else ver
    p = project_root / "config" / "chaos" / f"chaos_weights_{suffix}.json"
    out = {
        "version": str(ver),
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "weights": {k: float(v) for k, v in sorted(weights_map.items())},
        "tuning_payload": payload,
    }
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _write_ledger_and_artifact(*, project_root: Path, target_date: str, payload: dict) -> None:
    ledger_dir = project_root / "var" / "ledgers" / "chaos_m5" / target_date
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "weights_tuning_rolling_report.json"
    ledger_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_dir = project_root / "var" / "artifacts" / "chaos_m5" / target_date
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "weights_tuning_rolling_report.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--window-days", type=int, default=20)
    parser.add_argument("--num-windows", type=int, default=20)
    parser.add_argument("--step-days", type=int, default=1)
    parser.add_argument("--code-limit", type=int, default=200)
    parser.add_argument("--thresholds-version", default="chaos_thresholds_v0")
    parser.add_argument("--registry-id", default="v1")
    parser.add_argument("--registry-version", default="chaos_registry_v1")
    parser.add_argument("--base-weights-version", default="chaos_weights_v1_1")
    parser.add_argument("--out-weights-version", default="chaos_weights_v1_2")
    parser.add_argument("--allow-empty-windows", action="store_true")
    args = parser.parse_args()

    stock_db = PROJECT_ROOT / "var" / "db" / "stock_data.db"
    chaos_db = PROJECT_ROOT / "var" / "db" / "chaos_factor_matrix.db"
    if not stock_db.is_file():
        raise SystemExit(f"stock db not found: {stock_db}")
    if not chaos_db.is_file():
        raise SystemExit(f"chaos db not found: {chaos_db}")

    registry = load_chaos_factor_registry(project_root=PROJECT_ROOT, registry_id=str(args.registry_id))
    base_weights = load_chaos_weights(project_root=PROJECT_ROOT, weights_version=str(args.base_weights_version))
    _assert_versions_consistent(
        registry=registry,
        base_weights=base_weights,
        registry_version=str(args.registry_version),
        base_weights_version=str(args.base_weights_version),
    )

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
        stock_sector_map = _load_stock_sector_map(stock_conn, codes=codes)

        date_set: set[str] = set()
        for w in windows:
            date_set.update(list(w["trade_dates"]))
        tail_len = 10
        tail_dates = []
        for d in all_dates[end_idx + 1 :]:
            tail_dates.append(d)
            if len(tail_dates) >= tail_len:
                break
        close_dates = sorted(list(date_set | set(tail_dates)))
        close_by_key = _load_close_map(stock_conn, codes=codes, trade_dates_all=close_dates)

        amount_rank_by_date = {d: _load_amount_rank_map(stock_conn, trade_date=d) for d in sorted(date_set)}
        sector_rank_by_date = {d: _load_sector_amount_rank_map(stock_conn, trade_date=d) for d in sorted(date_set)}
        raw_by_key = _load_ready_raw_factors(
            chaos_conn,
            codes=codes,
            trade_dates=sorted(date_set),
            thresholds_version=str(args.thresholds_version),
            registry_version=str(registry.version),
            weights_version=str(base_weights.version),
        )
        if not raw_by_key:
            versions = _load_distinct_versions(
                chaos_conn,
                trade_dates=sorted(date_set),
                thresholds_version=str(args.thresholds_version),
            )
            raise SystemExit(
                json.dumps(
                    {
                        "error": "no ready raw_factors matched",
                        "filters": {
                            "thresholds_version": str(args.thresholds_version),
                            "registry_version": str(registry.version),
                            "weights_version": str(base_weights.version),
                        },
                        "available_versions_sample": versions[:20],
                        "hint": "rebuild chaos_daily_snapshot for the date range with matching registry_version/weights_version, or pass matching --registry-version/--base-weights-version.",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )

        base_scores_sum: dict[str, float] = {}
        base_scores_w: dict[str, float] = {}
        base_5_correct = 0
        base_5_evaluable = 0
        base_10_correct = 0
        base_10_evaluable = 0
        per_window_baseline: list[dict[str, Any]] = []

        for w in windows:
            trade_dates = list(w["trade_dates"])
            ev5 = _evaluate_window(
                registry=registry,
                weights_map=dict(base_weights.weights),
                codes=codes,
                trade_dates=trade_dates,
                stock_sector_map=stock_sector_map,
                amount_rank_by_date=amount_rank_by_date,
                sector_rank_by_date=sector_rank_by_date,
                raw_by_key=raw_by_key,
                close_by_key=close_by_key,
                horizon=5,
            )
            ev10 = _evaluate_window(
                registry=registry,
                weights_map=dict(base_weights.weights),
                codes=codes,
                trade_dates=trade_dates,
                stock_sector_map=stock_sector_map,
                amount_rank_by_date=amount_rank_by_date,
                sector_rank_by_date=sector_rank_by_date,
                raw_by_key=raw_by_key,
                close_by_key=close_by_key,
                horizon=10,
            )
            base_5_correct += int(ev5["correct"])
            base_5_evaluable += int(ev5["evaluable"])
            base_10_correct += int(ev10["correct"])
            base_10_evaluable += int(ev10["evaluable"])
            wgt = float(ev5["evaluable"]) if int(ev5["evaluable"]) > 0 else 0.0
            for fid, s in dict(ev5["factor_scores"]).items():
                base_scores_sum[fid] = float(base_scores_sum.get(fid, 0.0)) + float(s) * float(wgt)
                base_scores_w[fid] = float(base_scores_w.get(fid, 0.0)) + float(wgt)
            per_window_baseline.append(
                {
                    "start_date": w["start_date"],
                    "end_date": w["end_date"],
                    "h5_accuracy_direction": float(ev5["accuracy_direction"]),
                    "h10_accuracy_direction": float(ev10["accuracy_direction"]),
                    "h5_evaluable": int(ev5["evaluable"]),
                    "h10_evaluable": int(ev10["evaluable"]),
                }
            )
            if not bool(args.allow_empty_windows) and (int(ev5["evaluable"]) <= 0 or int(ev10["evaluable"]) <= 0):
                versions = _load_distinct_versions(
                    chaos_conn,
                    trade_dates=sorted(date_set),
                    thresholds_version=str(args.thresholds_version),
                )
                raise SystemExit(
                    json.dumps(
                        {
                            "error": "empty window evaluable",
                            "window": {"start_date": w["start_date"], "end_date": w["end_date"]},
                            "baseline": {
                                "h5_evaluable": int(ev5["evaluable"]),
                                "h10_evaluable": int(ev10["evaluable"]),
                                "h5_skipped_missing_price": int(ev5["skipped_missing_price"]),
                                "h10_skipped_missing_price": int(ev10["skipped_missing_price"]),
                            },
                            "filters": {
                                "thresholds_version": str(args.thresholds_version),
                                "registry_version": str(registry.version),
                                "weights_version": str(base_weights.version),
                            },
                            "available_versions_sample": versions[:20],
                            "hint": "rebuild chaos_daily_snapshot for the date range with matching registry_version/weights_version, or re-run with --allow-empty-windows if you only want a partial-window diagnostic.",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )

        base_acc_5 = float(base_5_correct) / float(base_5_evaluable) if base_5_evaluable > 0 else 0.0
        base_acc_10 = float(base_10_correct) / float(base_10_evaluable) if base_10_evaluable > 0 else 0.0
        base_score_5: dict[str, float] = {}
        for fid, ssum in base_scores_sum.items():
            wsum = float(base_scores_w.get(fid, 0.0))
            if wsum <= 0:
                continue
            base_score_5[fid] = float(ssum) / float(wsum)

        alphas = [0.5, 0.25, 0.1, 0.05, 0.0]
        best_alpha = 0.0
        best_weights = dict(base_weights.weights)
        best_acc_5 = float(base_acc_5)
        best_acc_10 = float(base_acc_10)
        per_window_best: list[dict[str, Any]] = []

        for a in alphas:
            cand: dict[str, float] = {}
            for f in registry.factors:
                fid = str(f.factor_id or "").strip()
                if not fid:
                    continue
                w0 = float(base_weights.weights.get(fid, f.default_weight))
                if w0 <= 0:
                    cand[fid] = 0.0
                    continue
                s = float(base_score_5.get(fid, 0.0))
                w1 = float(w0) * (1.0 + float(a) * float(s))
                cand[fid] = float(_clamp(w1, 0.0, 10.0))

            cand_5_correct = 0
            cand_5_evaluable = 0
            cand_10_correct = 0
            cand_10_evaluable = 0
            per_window_cand: list[dict[str, Any]] = []
            for w in windows:
                trade_dates = list(w["trade_dates"])
                ev5 = _evaluate_window(
                    registry=registry,
                    weights_map=cand,
                    codes=codes,
                    trade_dates=trade_dates,
                    stock_sector_map=stock_sector_map,
                    amount_rank_by_date=amount_rank_by_date,
                    sector_rank_by_date=sector_rank_by_date,
                    raw_by_key=raw_by_key,
                    close_by_key=close_by_key,
                    horizon=5,
                )
                ev10 = _evaluate_window(
                    registry=registry,
                    weights_map=cand,
                    codes=codes,
                    trade_dates=trade_dates,
                    stock_sector_map=stock_sector_map,
                    amount_rank_by_date=amount_rank_by_date,
                    sector_rank_by_date=sector_rank_by_date,
                    raw_by_key=raw_by_key,
                    close_by_key=close_by_key,
                    horizon=10,
                )
                cand_5_correct += int(ev5["correct"])
                cand_5_evaluable += int(ev5["evaluable"])
                cand_10_correct += int(ev10["correct"])
                cand_10_evaluable += int(ev10["evaluable"])
                per_window_cand.append(
                    {
                        "start_date": w["start_date"],
                        "end_date": w["end_date"],
                        "h5_accuracy_direction": float(ev5["accuracy_direction"]),
                        "h10_accuracy_direction": float(ev10["accuracy_direction"]),
                        "h5_evaluable": int(ev5["evaluable"]),
                        "h10_evaluable": int(ev10["evaluable"]),
                    }
                )
            acc5 = float(cand_5_correct) / float(cand_5_evaluable) if cand_5_evaluable > 0 else 0.0
            acc10 = float(cand_10_correct) / float(cand_10_evaluable) if cand_10_evaluable > 0 else 0.0
            if float(acc10) + 1e-12 < float(base_acc_10):
                continue
            if float(acc5) > float(best_acc_5) + 1e-12:
                best_acc_5 = float(acc5)
                best_acc_10 = float(acc10)
                best_alpha = float(a)
                best_weights = cand
                per_window_best = per_window_cand

        payload = {
            "_meta": {
                "status": "ok",
                "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "requested_by": "run_chaos_m5_tune_weights_v1_rolling",
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
                "registry_id": str(args.registry_id),
                "registry_version": str(args.registry_version),
                "thresholds_version": str(args.thresholds_version),
                "base_weights_version": str(args.base_weights_version),
                "out_weights_version": str(args.out_weights_version),
            },
            "objective": {"primary": "5d_accuracy_direction", "constraint": "10d_accuracy_direction_not_decrease"},
            "tuning": {"alphas_tried": alphas, "alpha_chosen": float(best_alpha)},
            "baseline": {
                "h5_accuracy_direction": float(base_acc_5),
                "h10_accuracy_direction": float(base_acc_10),
                "per_window": per_window_baseline,
            },
            "candidate": {
                "h5_accuracy_direction": float(best_acc_5),
                "h10_accuracy_direction": float(best_acc_10),
                "per_window": per_window_best,
            },
        }

    _write_weights_file(project_root=PROJECT_ROOT, weights_version=str(args.out_weights_version), weights_map=best_weights, payload=payload)
    _write_ledger_and_artifact(project_root=PROJECT_ROOT, target_date=str(args.end_date), payload=payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
