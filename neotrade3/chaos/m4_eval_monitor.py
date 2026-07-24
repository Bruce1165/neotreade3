from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HorizonMetrics:
    horizon: int
    total: int
    evaluable: int
    skipped_missing_price: int
    skipped_missing_snapshot: int
    skipped_quality_gate: int
    skipped_small_move: int
    accuracy_direction: float
    avg_return: float
    avg_return_pred_up: float | None
    avg_return_pred_down: float | None
    return_spread: float | None
    pred_up_count: int
    pred_down_count: int


def _sign(x: float, *, eps: float = 0.0) -> int:
    if x > eps:
        return 1
    if x < -eps:
        return -1
    return 0


def _load_close_map(
    conn: sqlite3.Connection,
    *,
    code: str,
    start_date: str,
    end_date: str,
) -> dict[str, float]:
    rows = conn.execute(
        """
        SELECT trade_date, close
        FROM daily_prices
        WHERE code = ?
          AND trade_date BETWEEN ? AND ?
          AND close IS NOT NULL
        """,
        (str(code), str(start_date), str(end_date)),
    ).fetchall()
    out: dict[str, float] = {}
    for d, c in rows:
        if d is None or c is None:
            continue
        out[str(d)] = float(c)
    return out


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _parse_json_object(raw: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(raw or "{}"))
    except Exception:
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _theme_context_score(raw_factors: dict[str, Any]) -> float:
    rps = _clamp(float(raw_factors.get("sector_rps_120") or 0.0) / 100.0, 0.0, 1.0)
    avg_pct_today = _clamp(float(raw_factors.get("sector_avg_pct_today") or 0.0) / 5.0, -1.0, 1.0)
    avg_pct_20d = _clamp(float(raw_factors.get("sector_avg_pct_20d") or 0.0) / 20.0, -1.0, 1.0)
    amount_ratio = _clamp(float(raw_factors.get("sector_amount_ratio_today_over_avg20") or 1.0) - 1.0, -1.0, 1.0)
    cooldown = _clamp(float(raw_factors.get("sector_cooldown_detected") or 0.0), 0.0, 1.0)
    deteriorating = _clamp(float(raw_factors.get("sector_trend_deteriorating") or 0.0), 0.0, 1.0)
    rollover = _clamp(float(raw_factors.get("sector_leader_rollover") or 0.0), 0.0, 1.0)
    positive = 0.40 * rps + 0.25 * avg_pct_today + 0.20 * avg_pct_20d + 0.15 * amount_ratio
    negative = 0.45 * cooldown + 0.35 * deteriorating + 0.20 * rollover
    return float(positive - negative)


def _market_context_score(raw_factors: dict[str, Any]) -> float:
    breadth_weak = _clamp(float(raw_factors.get("market_breadth_weak") or 0.0), 0.0, 1.0)
    trend_weak = _clamp(float(raw_factors.get("market_price_trend_weak") or 0.0), 0.0, 1.0)
    drawdown_weak = _clamp(float(raw_factors.get("market_drawdown_weak") or 0.0), 0.0, 1.0)
    return float(-(0.40 * breadth_weak + 0.40 * trend_weak + 0.20 * drawdown_weak))


def _load_snapshots(
    conn: sqlite3.Connection,
    *,
    codes: list[str],
    trade_dates: list[str],
    thresholds_version: str,
    registry_version: str | None = None,
    weights_version: str | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    if not codes or not trade_dates:
        return {}
    placeholders_codes = ",".join(["?"] * len(codes))
    placeholders_dates = ",".join(["?"] * len(trade_dates))
    rv = str(registry_version or "").strip()
    wv = str(weights_version or "").strip()
    rv_sql = " AND registry_version = ?" if rv else ""
    wv_sql = " AND weights_version = ?" if wv else ""
    params: list[Any] = [str(thresholds_version)] + list(codes) + list(trade_dates)
    if rv:
        params.append(rv)
    if wv:
        params.append(wv)
    rows = conn.execute(
        f"""
        SELECT
          code,
          trade_date,
          chaos_status,
          net_energy,
          registry_version,
          weights_version,
          self_history_reference_json,
          raw_factors_json
        FROM chaos_daily_snapshot
        WHERE thresholds_version = ?
          AND code IN ({placeholders_codes})
          AND trade_date IN ({placeholders_dates})
          {rv_sql}
          {wv_sql}
        """,
        params,
    ).fetchall()
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for code, trade_date, chaos_status, net_energy, rv, wv, self_ref_json, raw_factors_json in rows:
        if not code or not trade_date:
            continue
        out[(str(code), str(trade_date))] = {
            "chaos_status": str(chaos_status or ""),
            "net_energy": float(net_energy or 0.0),
            "registry_version": str(rv or ""),
            "weights_version": str(wv or ""),
            "self_history_reference_json": str(self_ref_json or "{}"),
            "raw_factors_json": str(raw_factors_json or "{}"),
        }
    return out


def _compute_predicted_direction(
    *,
    snap: dict[str, Any],
    signal_mode: str,
    combo_lambda: float | None,
    combo_beta: float | None,
    context_mode: str,
) -> int:
    ref = _parse_json_object(snap.get("self_history_reference_json"))
    raw_factors = _parse_json_object(snap.get("raw_factors_json"))
    base_score = 0.0
    if signal_mode == "point":
        base_score = float(snap.get("net_energy") or 0.0)
    elif signal_mode == "regime_speed":
        base_score = float(ref.get("yang_speed_mean_in_window") or 0.0)
    elif signal_mode == "regime_combo":
        speed = float(ref.get("yang_speed_mean_in_window") or 0.0)
        z = float(ref.get("net_energy_zscore_in_window") or 0.0)
        point_dir = _sign(float(snap.get("net_energy") or 0.0))
        base_score = (
            float(speed)
            + float(combo_lambda or 0.0) * float(z)
            + float(combo_beta or 0.0) * float(point_dir)
        )
    else:
        raise RuntimeError(f"unknown signal_mode: {signal_mode}")

    score = float(base_score)
    if context_mode in {"stock_theme", "stock_theme_market"}:
        score += _theme_context_score(raw_factors)
    if context_mode == "stock_theme_market":
        score += _market_context_score(raw_factors)
    return _sign(float(score))


def evaluate_chaos_m4_monitor(
    *,
    chaos_conn: sqlite3.Connection,
    stock_conn: sqlite3.Connection,
    codes: list[str],
    trade_dates: list[str],
    thresholds_version: str,
    registry_version: str | None = None,
    weights_version: str | None = None,
    horizons: list[int],
    signal_mode: str = "point",
    combo_lambda: float | None = None,
    combo_beta: float | None = None,
    actual_eps: float = 0.0,
    context_mode: str = "stock_only",
) -> tuple[dict[str, Any], list[HorizonMetrics]]:
    normalized_codes = [str(c).strip() for c in list(codes or []) if str(c).strip()]
    normalized_dates = [str(d).strip() for d in list(trade_dates or []) if str(d).strip()]
    horizons_norm = sorted({int(h) for h in list(horizons or []) if int(h) > 0})
    if not normalized_codes or not normalized_dates or not horizons_norm:
        raise RuntimeError("missing inputs for m4 monitor")

    max_h = int(max(horizons_norm))
    start_date = normalized_dates[0]
    end_date = normalized_dates[-1]
    end_with_buffer = normalized_dates[min(len(normalized_dates) - 1, len(normalized_dates) - 1)]
    calendar_all = list(normalized_dates)

    extra_rows = stock_conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE trade_date > ?
        ORDER BY trade_date ASC
        LIMIT ?
        """,
        (str(end_date), int(max_h)),
    ).fetchall()
    for r in extra_rows:
        if r and r[0]:
            calendar_all.append(str(r[0]))

    date_index = {d: i for i, d in enumerate(calendar_all)}
    end_with_buffer = calendar_all[-1]

    snaps = _load_snapshots(
        chaos_conn,
        codes=normalized_codes,
        trade_dates=normalized_dates,
        thresholds_version=str(thresholds_version),
        registry_version=str(registry_version).strip() if registry_version else None,
        weights_version=str(weights_version).strip() if weights_version else None,
    )

    close_map_by_code: dict[str, dict[str, float]] = {}
    for code in normalized_codes:
        close_map_by_code[str(code)] = _load_close_map(
            stock_conn,
            code=str(code),
            start_date=str(start_date),
            end_date=str(end_with_buffer),
        )

    expected_total = int(len(normalized_codes)) * int(len(normalized_dates))
    metrics_list: list[HorizonMetrics] = []
    signal_mode_v = str(signal_mode or "").strip() or "point"
    if signal_mode_v not in {"point", "regime_speed", "regime_combo"}:
        raise RuntimeError(f"unknown signal_mode: {signal_mode_v}")
    context_mode_v = str(context_mode or "").strip() or "stock_only"
    if context_mode_v not in {"stock_only", "stock_theme", "stock_theme_market"}:
        raise RuntimeError(f"unknown context_mode: {context_mode_v}")
    combo_lambda_v = None
    combo_beta_v = None
    if signal_mode_v == "regime_combo":
        if combo_lambda is None:
            raise RuntimeError("combo_lambda is required for signal_mode=regime_combo")
        combo_lambda_v = float(combo_lambda)
        combo_beta_v = float(combo_beta) if combo_beta is not None else 0.0
    for h in horizons_norm:
        evaluable = 0
        skipped_missing_price = 0
        skipped_missing_snapshot = 0
        skipped_quality_gate = 0
        skipped_small_move = 0
        correct_dir = 0
        sum_ret = 0.0
        sum_ret_up = 0.0
        n_up = 0
        sum_ret_down = 0.0
        n_down = 0

        for code in normalized_codes:
            close_map = close_map_by_code.get(str(code)) or {}
            for d in normalized_dates:
                snap = snaps.get((str(code), str(d)))
                if not isinstance(snap, dict):
                    skipped_missing_snapshot += 1
                    continue
                if str(snap.get("chaos_status") or "") != "ready":
                    skipped_quality_gate += 1
                    continue
                idx = date_index.get(str(d))
                if idx is None:
                    skipped_missing_price += 1
                    continue
                f_idx = idx + int(h)
                if f_idx >= len(calendar_all):
                    skipped_missing_price += 1
                    continue
                d_f = calendar_all[f_idx]
                c0 = close_map.get(str(d))
                c1 = close_map.get(str(d_f))
                if c0 is None or c1 is None or float(c0) <= 0:
                    skipped_missing_price += 1
                    continue
                ret = float(c1) / float(c0) - 1.0
                actual = _sign(float(ret), eps=float(actual_eps))
                if actual == 0:
                    skipped_small_move += 1
                    continue
                pred = _compute_predicted_direction(
                    snap=snap,
                    signal_mode=signal_mode_v,
                    combo_lambda=combo_lambda_v,
                    combo_beta=combo_beta_v,
                    context_mode=context_mode_v,
                )
                evaluable += 1
                sum_ret += float(ret)
                if pred == 1:
                    sum_ret_up += float(ret)
                    n_up += 1
                if pred == -1:
                    sum_ret_down += float(ret)
                    n_down += 1
                if pred == actual:
                    correct_dir += 1

        acc = float(correct_dir) / float(evaluable) if evaluable > 0 else 0.0
        avg = float(sum_ret) / float(evaluable) if evaluable > 0 else 0.0
        avg_up = float(sum_ret_up) / float(n_up) if n_up > 0 else None
        avg_down = float(sum_ret_down) / float(n_down) if n_down > 0 else None
        return_spread = (
            float(avg_up) - float(avg_down)
            if avg_up is not None and avg_down is not None
            else None
        )
        metrics_list.append(
            HorizonMetrics(
                horizon=int(h),
                total=int(expected_total),
                evaluable=int(evaluable),
                skipped_missing_price=int(skipped_missing_price),
                skipped_missing_snapshot=int(skipped_missing_snapshot),
                skipped_quality_gate=int(skipped_quality_gate),
                skipped_small_move=int(skipped_small_move),
                accuracy_direction=float(acc),
                avg_return=float(avg),
                avg_return_pred_up=avg_up,
                avg_return_pred_down=avg_down,
                return_spread=return_spread,
                pred_up_count=int(n_up),
                pred_down_count=int(n_down),
            )
        )

    report = {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "thresholds_version": str(thresholds_version),
        "registry_version": str(registry_version or ""),
        "weights_version": str(weights_version or ""),
        "signal_mode": str(signal_mode_v),
        "context_mode": str(context_mode_v),
        "combo_lambda": float(combo_lambda_v) if combo_lambda_v is not None else None,
        "combo_beta": float(combo_beta_v) if combo_beta_v is not None else None,
        "actual_eps": float(actual_eps),
        "code_count": int(len(normalized_codes)),
        "trade_date_count": int(len(normalized_dates)),
        "horizons": [m.__dict__ for m in metrics_list],
    }
    return report, metrics_list
