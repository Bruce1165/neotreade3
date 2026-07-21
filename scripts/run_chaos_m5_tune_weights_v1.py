#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import asdict
from datetime import date, datetime
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


def _load_close_map(
    conn: sqlite3.Connection,
    *,
    codes: list[str],
    trade_dates: list[str],
    extra_forward_days: int,
) -> dict[tuple[str, str], float]:
    if not codes or not trade_dates:
        return {}
    start = trade_dates[0]
    end = trade_dates[-1]
    rows = conn.execute(
        """
        SELECT trade_date, code, close
        FROM daily_prices
        WHERE trade_date BETWEEN ? AND ?
        """,
        (str(start), str(end)),
    ).fetchall()
    out: dict[tuple[str, str], float] = {}
    codes_set = set(codes)
    dates_set = set(trade_dates)
    for d, c, close in rows:
        if not d or not c or close is None:
            continue
        ds = str(d)
        cs = str(c)
        if cs not in codes_set:
            continue
        if ds not in dates_set:
            continue
        if isinstance(close, (int, float)):
            out[(cs, ds)] = float(close)

    tail_start = trade_dates[-1]
    tail_rows = conn.execute(
        """
        SELECT trade_date, code, close
        FROM daily_prices
        WHERE trade_date > ?
        ORDER BY trade_date ASC
        """,
        (str(tail_start),),
    ).fetchall()
    added_dates: list[str] = []
    for d, _c, _close in tail_rows:
        if not d:
            continue
        ds = str(d)
        if ds not in dates_set and ds not in added_dates:
            added_dates.append(ds)
        if len(added_dates) >= int(extra_forward_days):
            break
    if not added_dates:
        return out
    all_dates = set(trade_dates + added_dates)
    rows2 = conn.execute(
        """
        SELECT trade_date, code, close
        FROM daily_prices
        WHERE trade_date IN ({})
        """.format(
            ",".join(["?"] * len(all_dates))
        ),
        tuple(sorted(all_dates)),
    ).fetchall()
    for d, c, close in rows2:
        if not d or not c or close is None:
            continue
        ds = str(d)
        cs = str(c)
        if cs not in codes_set:
            continue
        if ds not in all_dates:
            continue
        if isinstance(close, (int, float)):
            out[(cs, ds)] = float(close)
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


def _evaluate_accuracy(
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
    contrib_sum_abs: dict[str, float] = {}
    contrib_sum_signed: dict[str, float] = {}
    contrib_sum_abs_y: dict[str, float] = {}
    contrib_sum_abs_count: dict[str, int] = {}

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
                fid = c.factor_id
                s = float(c.contrib_signed)
                contrib_sum_signed[fid] = float(contrib_sum_signed.get(fid, 0.0)) + s
                contrib_sum_abs[fid] = float(contrib_sum_abs.get(fid, 0.0)) + abs(s)
                contrib_sum_abs_y[fid] = float(contrib_sum_abs_y.get(fid, 0.0)) + abs(s) * float(y)
                contrib_sum_abs_count[fid] = int(contrib_sum_abs_count.get(fid, 0)) + 1

    acc = float(correct) / float(evaluable) if evaluable > 0 else 0.0
    factor_scores: dict[str, float] = {}
    factor_abs_mean: dict[str, float] = {}
    for fid, abs_sum in contrib_sum_abs.items():
        if float(abs_sum) <= 0:
            continue
        score = float(contrib_sum_abs_y.get(fid, 0.0)) / float(abs_sum)
        factor_scores[fid] = float(_clamp(score, -1.0, 1.0))
        cnt = int(contrib_sum_abs_count.get(fid, 0))
        factor_abs_mean[fid] = float(abs_sum) / float(cnt) if cnt > 0 else 0.0

    return {
        "horizon": int(horizon),
        "evaluable": int(evaluable),
        "correct": int(correct),
        "accuracy_direction": float(acc),
        "skipped_missing_price": int(skipped_missing_price),
        "factor_scores": factor_scores,
        "factor_abs_mean": factor_abs_mean,
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
    ledger_path = ledger_dir / "weights_tuning_report.json"
    ledger_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_dir = project_root / "var" / "artifacts" / "chaos_m5" / target_date
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "weights_tuning_report.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--code-limit", type=int, default=200)
    parser.add_argument("--thresholds-version", default="chaos_thresholds_v0")
    parser.add_argument("--registry-id", default="v1")
    parser.add_argument("--registry-version", default="chaos_registry_v1")
    parser.add_argument("--base-weights-version", default="chaos_weights_v1")
    parser.add_argument("--out-weights-version", default="chaos_weights_v1_1")
    args = parser.parse_args()

    stock_db = PROJECT_ROOT / "var" / "db" / "stock_data.db"
    chaos_db = PROJECT_ROOT / "var" / "db" / "chaos_factor_matrix.db"
    if not stock_db.is_file():
        raise SystemExit(f"stock db not found: {stock_db}")
    if not chaos_db.is_file():
        raise SystemExit(f"chaos db not found: {chaos_db}")

    registry = load_chaos_factor_registry(project_root=PROJECT_ROOT, registry_id=str(args.registry_id))
    base_weights = load_chaos_weights(project_root=PROJECT_ROOT, weights_version=str(args.base_weights_version))

    with sqlite3.connect(str(stock_db)) as stock_conn, sqlite3.connect(str(chaos_db)) as chaos_conn:
        trade_dates = _load_trade_dates(stock_conn, start_date=str(args.start_date), end_date=str(args.end_date))
        codes = _load_codes_top_by_amount(
            stock_conn,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            limit=int(args.code_limit),
        )
        stock_sector_map = _load_stock_sector_map(stock_conn, codes=codes)
        amount_rank_by_date = {d: _load_amount_rank_map(stock_conn, trade_date=d) for d in trade_dates}
        sector_rank_by_date = {d: _load_sector_amount_rank_map(stock_conn, trade_date=d) for d in trade_dates}
        raw_by_key = _load_ready_raw_factors(
            chaos_conn,
            codes=codes,
            trade_dates=trade_dates,
            thresholds_version=str(args.thresholds_version),
            registry_version=str(args.registry_version),
            weights_version=str(args.base_weights_version),
        )
        close_by_key = _load_close_map(
            stock_conn,
            codes=codes,
            trade_dates=trade_dates,
            extra_forward_days=10,
        )

        base_eval_5 = _evaluate_accuracy(
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
        base_eval_10 = _evaluate_accuracy(
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

        base_acc_5 = float(base_eval_5["accuracy_direction"])
        base_acc_10 = float(base_eval_10["accuracy_direction"])
        score5 = dict(base_eval_5["factor_scores"])

        alphas = [0.5, 0.25, 0.1, 0.05, 0.0]
        best_weights = dict(base_weights.weights)
        best_alpha = 0.0
        best_acc_5 = base_acc_5
        best_acc_10 = base_acc_10

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
                s = float(score5.get(fid, 0.0))
                w1 = float(w0) * (1.0 + float(a) * float(s))
                cand[fid] = float(_clamp(w1, 0.0, 10.0))
            ev5 = _evaluate_accuracy(
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
            ev10 = _evaluate_accuracy(
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
            acc5 = float(ev5["accuracy_direction"])
            acc10 = float(ev10["accuracy_direction"])
            if acc10 + 1e-12 < base_acc_10:
                continue
            if acc5 > best_acc_5 + 1e-12:
                best_acc_5 = acc5
                best_acc_10 = acc10
                best_alpha = float(a)
                best_weights = cand

        factor_abs_mean = dict(base_eval_5["factor_abs_mean"])
        factor_rows: list[dict[str, Any]] = []
        for f in registry.factors:
            fid = str(f.factor_id or "").strip()
            if not fid:
                continue
            w0 = float(base_weights.weights.get(fid, f.default_weight))
            w1 = float(best_weights.get(fid, w0))
            factor_rows.append(
                {
                    "factor_id": fid,
                    "yin_or_yang": str(f.yin_or_yang),
                    "category": str(f.category),
                    "normalization": str(f.normalization),
                    "score_5d": float(score5.get(fid, 0.0)),
                    "abs_contrib_mean_5d": float(factor_abs_mean.get(fid, 0.0)),
                    "weight_before": float(w0),
                    "weight_after": float(w1),
                }
            )

    payload = {
        "_meta": {
            "status": "ok",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "requested_by": "run_chaos_m5_tune_weights_v1",
        },
        "range": {"start_date": str(args.start_date), "end_date": str(args.end_date)},
        "universe": {"mode": "top_by_amount", "code_limit": int(args.code_limit)},
        "versions": {
            "registry_id": str(args.registry_id),
            "registry_version": str(args.registry_version),
            "thresholds_version": str(args.thresholds_version),
            "base_weights_version": str(args.base_weights_version),
            "out_weights_version": str(args.out_weights_version),
        },
        "objective": {
            "primary": "5d_accuracy_direction",
            "constraint": "10d_accuracy_direction_not_decrease",
        },
        "tuning": {
            "alphas_tried": [0.5, 0.25, 0.1, 0.05, 0.0],
            "alpha_chosen": float(best_alpha),
        },
        "baseline": {
            "h5": {k: v for k, v in base_eval_5.items() if k != "factor_scores" and k != "factor_abs_mean"},
            "h10": {k: v for k, v in base_eval_10.items() if k != "factor_scores" and k != "factor_abs_mean"},
        },
        "candidate": {
            "h5_accuracy_direction": float(best_acc_5),
            "h10_accuracy_direction": float(best_acc_10),
        },
        "factors": factor_rows,
    }

    _write_weights_file(
        project_root=PROJECT_ROOT,
        weights_version=str(args.out_weights_version),
        weights_map=best_weights,
        payload=payload,
    )
    _write_ledger_and_artifact(project_root=PROJECT_ROOT, target_date=str(args.end_date), payload=payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

