from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from neotrade3.chaos.backtest.contracts import (
    BacktestConfig,
    BacktestRunResult,
    FiltersEval120D,
    FiltersEvalBucket,
    SnapshotRef,
    TradeRecord,
    WindowSummary,
)


def _sign(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


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


def load_trade_dates(
    stock_conn: sqlite3.Connection, *, start_date: str, end_date: str
) -> list[str]:
    rows = stock_conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE trade_date BETWEEN ? AND ?
        ORDER BY trade_date ASC
        """,
        (str(start_date), str(end_date)),
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def load_all_a_share_codes(stock_conn: sqlite3.Connection) -> list[str]:
    rows = stock_conn.execute(
        f"""
        SELECT s.code
        FROM stocks s
        WHERE {_a_share_universe_sql()}
        ORDER BY s.code ASC
        """
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def load_stock_name_map(stock_conn: sqlite3.Connection) -> dict[str, str]:
    rows = stock_conn.execute(
        f"""
        SELECT s.code, s.name
        FROM stocks s
        WHERE {_a_share_universe_sql()}
        """
    ).fetchall()
    out: dict[str, str] = {}
    for code, name in rows:
        if not code:
            continue
        out[str(code)] = str(name or "")
    return out


def _load_close(
    stock_conn: sqlite3.Connection, *, code: str, trade_date: str
) -> float | None:
    row = stock_conn.execute(
        """
        SELECT close
        FROM daily_prices
        WHERE code = ?
          AND trade_date = ?
          AND close IS NOT NULL
        """,
        (str(code), str(trade_date)),
    ).fetchone()
    if not row or row[0] is None:
        return None
    try:
        return float(row[0])
    except Exception:
        return None


def _load_close_range(
    stock_conn: sqlite3.Connection, *, code: str, start_date: str, end_date: str
) -> list[tuple[str, float]]:
    rows = stock_conn.execute(
        """
        SELECT trade_date, close
        FROM daily_prices
        WHERE code = ?
          AND trade_date BETWEEN ? AND ?
          AND close IS NOT NULL
        ORDER BY trade_date ASC
        """,
        (str(code), str(start_date), str(end_date)),
    ).fetchall()
    out: list[tuple[str, float]] = []
    for d, c in rows:
        if not d or c is None:
            continue
        out.append((str(d), float(c)))
    return out


def _load_ready_chaos_snapshots_for_date(
    chaos_conn: sqlite3.Connection,
    *,
    trade_date: str,
    thresholds_version: str,
    registry_version: str,
    weights_version: str,
) -> list[dict[str, Any]]:
    rows = chaos_conn.execute(
        """
        SELECT code, net_energy, reference_mode, self_history_reference_json
        FROM chaos_daily_snapshot
        WHERE trade_date = ?
          AND chaos_status = 'ready'
          AND thresholds_version = ?
          AND registry_version = ?
          AND weights_version = ?
        """,
        (str(trade_date), str(thresholds_version), str(registry_version), str(weights_version)),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for code, net_energy, reference_mode, self_ref_json in rows:
        if not code:
            continue
        out.append(
            {
                "code": str(code),
                "net_energy": float(net_energy or 0.0),
                "reference_mode": str(reference_mode or ""),
                "self_history_reference_json": str(self_ref_json or "{}"),
            }
        )
    return out


def _count_chaos_snapshots_for_date(
    chaos_conn: sqlite3.Connection,
    *,
    trade_date: str,
    thresholds_version: str,
    registry_version: str,
    weights_version: str,
) -> tuple[int, int]:
    rows = chaos_conn.execute(
        """
        SELECT chaos_status, COUNT(*)
        FROM chaos_daily_snapshot
        WHERE trade_date = ?
          AND thresholds_version = ?
          AND registry_version = ?
          AND weights_version = ?
        GROUP BY chaos_status
        """,
        (str(trade_date), str(thresholds_version), str(registry_version), str(weights_version)),
    ).fetchall()
    ready_n = 0
    pending_n = 0
    for status, n in rows:
        s = str(status or "").strip().lower()
        if s == "ready":
            ready_n = int(n or 0)
        elif s == "pending":
            pending_n = int(n or 0)
    return int(ready_n), int(pending_n)


def _compute_score_and_pred(
    *,
    snap: dict[str, Any],
    signal_mode: str,
    combo_lambda: float | None,
    combo_beta: float | None,
) -> tuple[float, int]:
    mode = str(signal_mode or "").strip() or "point"
    net = float(snap.get("net_energy") or 0.0)
    if mode == "point":
        score = float(net)
        return score, _sign(score)
    ref_raw = snap.get("self_history_reference_json")
    try:
        ref = json.loads(str(ref_raw or "{}"))
    except Exception:
        ref = {}
    speed = float(ref.get("yang_speed_mean_in_window") or 0.0) if isinstance(ref, dict) else 0.0
    if mode == "regime_speed":
        score = float(speed)
        return score, _sign(score)
    if mode == "regime_combo":
        lam = float(combo_lambda) if combo_lambda is not None else 0.0
        beta = float(combo_beta) if combo_beta is not None else 0.0
        z = float(ref.get("net_energy_zscore_in_window") or 0.0) if isinstance(ref, dict) else 0.0
        point_dir = _sign(float(net))
        score = float(speed) + lam * float(z) + beta * float(point_dir)
        return score, _sign(score)
    raise RuntimeError(f"unknown signal_mode: {mode}")


def _weekly_endpoints(trade_dates: list[str]) -> list[str]:
    from datetime import date as dt_date

    last_by_week: dict[tuple[int, int], str] = {}
    for d in list(trade_dates or []):
        di = dt_date.fromisoformat(str(d))
        y, w, _ = di.isocalendar()
        last_by_week[(int(y), int(w))] = str(d)
    return [str(last_by_week[k]) for k in sorted(last_by_week.keys())]


def _weekly_windows(trade_dates: list[str]) -> list[tuple[str, str]]:
    from datetime import date as dt_date

    out: list[tuple[str, str]] = []
    if not trade_dates:
        return out
    cur_key: tuple[int, int] | None = None
    cur_start = ""
    cur_end = ""
    for d in list(trade_dates or []):
        di = dt_date.fromisoformat(str(d))
        key = (int(di.isocalendar()[0]), int(di.isocalendar()[1]))
        if cur_key is None:
            cur_key = key
            cur_start = str(d)
            cur_end = str(d)
            continue
        if key == cur_key:
            cur_end = str(d)
            continue
        out.append((str(cur_start), str(cur_end)))
        cur_key = key
        cur_start = str(d)
        cur_end = str(d)
    if cur_key is not None:
        out.append((str(cur_start), str(cur_end)))
    return out


def _median(values: list[float]) -> float:
    items = sorted([float(x) for x in list(values or []) if isinstance(x, (int, float))])
    if not items:
        return 0.0
    m = len(items) // 2
    if len(items) % 2 == 1:
        return float(items[m])
    return (float(items[m - 1]) + float(items[m])) / 2.0


def _percentile(values: list[float], p: float) -> float:
    items = sorted([float(x) for x in list(values or []) if isinstance(x, (int, float))])
    if not items:
        return 0.0
    if p <= 0:
        return float(items[0])
    if p >= 100:
        return float(items[-1])
    k = (len(items) - 1) * (float(p) / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(items[int(k)])
    d0 = items[int(f)] * (c - k)
    d1 = items[int(c)] * (k - f)
    return float(d0 + d1)


def _build_weekly_window_summaries(
    *,
    trade_dates: list[str],
    trades: list[TradeRecord],
    skipped_missing_snapshot_by_date: dict[str, int],
    skipped_pending_snapshot_by_date: dict[str, int],
) -> list[WindowSummary]:
    windows = _weekly_windows(trade_dates)
    idx = {d: i for i, d in enumerate(trade_dates)}
    out: list[WindowSummary] = []
    for start_d, end_d in windows:
        start_i = idx.get(start_d)
        end_i = idx.get(end_d)
        if end_i is None:
            continue
        if start_i is None:
            start_i = 0
        w_trades = [t for t in trades if t.exit_date and start_d <= str(t.exit_date) <= end_d]
        rets = [float(t.exit_return_pct or 0.0) * 100.0 for t in w_trades if t.exit_return_pct is not None]
        givebacks = [float(t.giveback_pct or 0.0) * 100.0 for t in w_trades if t.giveback_pct is not None]
        win = sum(1 for t in w_trades if (t.exit_return_pct or 0.0) > 0)
        loss = sum(1 for t in w_trades if (t.exit_return_pct or 0.0) < 0)
        total = len(w_trades)
        win_rate = float(win) / float(total) if total > 0 else 0.0
        avg_ret = float(sum(rets)) / float(len(rets)) if rets else 0.0
        med_ret = _median(rets) if rets else 0.0
        avg_give = float(sum(givebacks)) / float(len(givebacks)) if givebacks else 0.0
        p90_give = _percentile(givebacks, 90.0) if givebacks else 0.0
        miss = sum(int(skipped_missing_snapshot_by_date.get(d) or 0) for d in trade_dates[start_i : end_i + 1])
        pend = sum(int(skipped_pending_snapshot_by_date.get(d) or 0) for d in trade_dates[start_i : end_i + 1])
        out.append(
            WindowSummary(
                window_type="weekly",
                window_start_date=str(start_d),
                window_end_date=str(end_d),
                trade_count=int(total),
                win_count=int(win),
                loss_count=int(loss),
                win_rate=float(win_rate),
                avg_return_pct=float(avg_ret),
                median_return_pct=float(med_ret),
                avg_giveback_pct=float(avg_give),
                p90_giveback_pct=float(p90_give),
                skipped_missing_snapshot=int(miss),
                skipped_pending_snapshot=int(pend),
            )
        )
    return out


def _load_regime_anchor(
    chaos_conn: sqlite3.Connection,
    *,
    code: str,
    trade_date: str,
    thresholds_version: str,
    registry_version: str,
    weights_version: str,
) -> str:
    row = chaos_conn.execute(
        """
        SELECT self_history_reference_json
        FROM chaos_daily_snapshot
        WHERE code = ?
          AND trade_date = ?
          AND chaos_status = 'ready'
          AND thresholds_version = ?
          AND registry_version = ?
          AND weights_version = ?
        """,
        (str(code), str(trade_date), str(thresholds_version), str(registry_version), str(weights_version)),
    ).fetchone()
    if not row or not row[0]:
        return ""
    try:
        ref = json.loads(str(row[0] or "{}"))
    except Exception:
        ref = {}
    if not isinstance(ref, dict):
        return ""
    return str(ref.get("regime_anchor_date") or "")


def _build_regime_window_summaries(
    *,
    chaos_conn: sqlite3.Connection,
    trades: list[TradeRecord],
    thresholds_version: str,
    registry_version: str,
    weights_version: str,
) -> list[WindowSummary]:
    grouped: dict[tuple[str, str], list[TradeRecord]] = {}
    for t in trades:
        if not t.exit_date:
            continue
        anchor = _load_regime_anchor(
            chaos_conn,
            code=str(t.code),
            trade_date=str(t.exit_signal_date or t.signal_date),
            thresholds_version=str(thresholds_version),
            registry_version=str(registry_version),
            weights_version=str(weights_version),
        )
        key = (str(t.code), str(anchor))
        grouped.setdefault(key, []).append(t)

    out: list[WindowSummary] = []
    for (code, anchor), items in grouped.items():
        end_date = max([str(t.exit_date) for t in items if t.exit_date] or [""])
        rets = [float(t.exit_return_pct or 0.0) * 100.0 for t in items if t.exit_return_pct is not None]
        givebacks = [float(t.giveback_pct or 0.0) * 100.0 for t in items if t.giveback_pct is not None]
        win = sum(1 for t in items if (t.exit_return_pct or 0.0) > 0)
        loss = sum(1 for t in items if (t.exit_return_pct or 0.0) < 0)
        total = len(items)
        win_rate = float(win) / float(total) if total > 0 else 0.0
        avg_ret = float(sum(rets)) / float(len(rets)) if rets else 0.0
        med_ret = _median(rets) if rets else 0.0
        avg_give = float(sum(givebacks)) / float(len(givebacks)) if givebacks else 0.0
        p90_give = _percentile(givebacks, 90.0) if givebacks else 0.0
        out.append(
            WindowSummary(
                window_type="regime",
                window_start_date=str(anchor or ""),
                window_end_date=str(end_date),
                trade_count=int(total),
                win_count=int(win),
                loss_count=int(loss),
                win_rate=float(win_rate),
                avg_return_pct=float(avg_ret),
                median_return_pct=float(med_ret),
                avg_giveback_pct=float(avg_give),
                p90_giveback_pct=float(p90_give),
                skipped_missing_snapshot=0,
                skipped_pending_snapshot=0,
            )
        )
    return out


def _compute_trade_metrics_close_only(
    *,
    stock_conn: sqlite3.Connection,
    trade: TradeRecord,
    trade_dates: list[str],
) -> None:
    entry_date = str(trade.entry_date)
    exit_date = str(trade.exit_date or "")
    if not exit_date:
        return
    entry_price = float(trade.entry_price_close)
    exit_price = float(trade.exit_price_close or 0.0)
    idx = {d: i for i, d in enumerate(trade_dates)}
    e_i = idx.get(entry_date)
    x_i = idx.get(exit_date)
    if e_i is None or x_i is None or x_i < e_i:
        return
    trade.holding_days = int(x_i - e_i + 1)
    closes = _load_close_range(stock_conn, code=str(trade.code), start_date=entry_date, end_date=exit_date)
    if closes:
        peak_d, peak_c = max(closes, key=lambda x: float(x[1]))
        trade.peak_close_date = str(peak_d)
        trade.peak_close_price = float(peak_c)
        max_runup = float(peak_c) / float(entry_price) - 1.0 if float(entry_price) > 0 else 0.0
        trade.max_runup_pct_during_hold = float(max_runup)
        exit_ret = float(exit_price) / float(entry_price) - 1.0 if float(entry_price) > 0 else 0.0
        trade.exit_return_pct = float(exit_ret)
        trade.giveback_pct = float(max_runup - exit_ret)
        max_dd = 0.0
        for _d, c in closes:
            if float(peak_c) > 0:
                dd = float(c) / float(peak_c) - 1.0
                if dd < max_dd:
                    max_dd = float(dd)
        trade.max_drawdown_from_peak_pct = float(max_dd)


def _build_filters_eval_120d_for_date(
    *,
    stock_conn: sqlite3.Connection,
    chaos_conn: sqlite3.Connection,
    all_codes: list[str],
    trade_dates: list[str],
    asof_date: str,
    label_horizon_trading_days: int,
    thresholds_version: str,
    registry_version: str,
    weights_version: str,
    signal_mode: str,
    combo_lambda: float | None,
    combo_beta: float | None,
) -> FiltersEval120D | None:
    idx = {d: i for i, d in enumerate(trade_dates)}
    i = idx.get(str(asof_date))
    if i is None:
        return None
    j = i + int(label_horizon_trading_days)
    if j >= len(trade_dates):
        return None
    future_date = trade_dates[j]
    total_codes = int(len(all_codes))
    rows = stock_conn.execute(
        f"""
        SELECT p0.code, (p1.close / p0.close - 1.0) AS ret_120d
        FROM daily_prices p0
        JOIN daily_prices p1 ON p1.code = p0.code
        JOIN stocks s ON s.code = p0.code
        WHERE p0.trade_date = ?
          AND p1.trade_date = ?
          AND p0.close IS NOT NULL
          AND p1.close IS NOT NULL
          AND p0.close > 0
          AND {_a_share_universe_sql()}
        """,
        (str(asof_date), str(future_date)),
    ).fetchall()
    labels = [(str(code), float(ret)) for code, ret in rows if code is not None and ret is not None]
    skipped_label_missing = int(total_codes) - int(len(labels))
    if not labels:
        return FiltersEval120D(
            label_horizon_trading_days=int(label_horizon_trading_days),
            asof_date=str(asof_date),
            future_date=str(future_date),
            labeled_codes=0,
            skipped_label_missing=int(skipped_label_missing),
            buckets=[],
        )
    labels.sort(key=lambda x: float(x[1]))
    bucket_edges = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    bucket_ranges = [(bucket_edges[k], bucket_edges[k + 1]) for k in range(len(bucket_edges) - 1)]
    bucket_id_by_code: dict[str, str] = {}
    n = len(labels)
    for rank, (code, _v) in enumerate(labels):
        pct = (float(rank) + 0.5) / float(n) * 100.0
        b = None
        for lo, hi in bucket_ranges:
            if pct >= float(lo) and pct < float(hi):
                b = (lo, hi)
                break
        if b is None:
            b = (90, 100)
        bucket_id_by_code[str(code)] = f"p{int(b[0])}_{int(b[1])}"
    snaps = _load_ready_chaos_snapshots_for_date(
        chaos_conn,
        trade_date=str(asof_date),
        thresholds_version=str(thresholds_version),
        registry_version=str(registry_version),
        weights_version=str(weights_version),
    )
    triggered_codes: set[str] = set()
    triggered_events: dict[str, int] = {}
    triggered_code_sets: dict[str, set[str]] = {}
    for snap in snaps:
        score, pred = _compute_score_and_pred(
            snap=snap,
            signal_mode=str(signal_mode),
            combo_lambda=combo_lambda,
            combo_beta=combo_beta,
        )
        if int(pred) != 1:
            continue
        code = str(snap.get("code") or "")
        if not code:
            continue
        bucket_id = bucket_id_by_code.get(code)
        if not bucket_id:
            continue
        triggered_events[bucket_id] = int(triggered_events.get(bucket_id) or 0) + 1
        triggered_code_sets.setdefault(bucket_id, set()).add(code)
        triggered_codes.add(code)
    buckets: list[FiltersEvalBucket] = []
    for lo, hi in bucket_ranges:
        bid = f"p{int(lo)}_{int(hi)}"
        buckets.append(
            FiltersEvalBucket(
                bucket_id=str(bid),
                lower_pct=float(lo),
                upper_pct=float(hi),
                trigger_event_count=int(triggered_events.get(bid) or 0),
                trigger_code_count=int(len(triggered_code_sets.get(bid) or set())),
            )
        )
    return FiltersEval120D(
        label_horizon_trading_days=int(label_horizon_trading_days),
        asof_date=str(asof_date),
        future_date=str(future_date),
        labeled_codes=int(len(labels)),
        skipped_label_missing=int(skipped_label_missing),
        buckets=buckets,
    )


class ChaosBacktestEngine:
    def __init__(self, *, project_root: Path) -> None:
        self._project_root = Path(project_root)

    def run(
        self,
        *,
        stock_conn: sqlite3.Connection,
        chaos_conn: sqlite3.Connection,
        config: BacktestConfig,
    ) -> BacktestRunResult:
        trade_dates = load_trade_dates(stock_conn, start_date=str(config.start_date), end_date=str(config.end_date))
        if len(trade_dates) < 3:
            raise RuntimeError("insufficient trade dates for backtest")

        all_codes = load_all_a_share_codes(stock_conn)
        name_map = load_stock_name_map(stock_conn)
        idx = {d: i for i, d in enumerate(trade_dates)}

        positions: dict[str, TradeRecord] = {}
        trades: list[TradeRecord] = []
        skipped_missing_snapshot_by_date: dict[str, int] = {}
        skipped_pending_snapshot_by_date: dict[str, int] = {}
        filters_eval: list[FiltersEval120D] = []

        for i, d in enumerate(trade_dates):
            if i >= len(trade_dates) - 1:
                break
            exec_date = trade_dates[i + 1]

            ready_n, pending_n = _count_chaos_snapshots_for_date(
                chaos_conn,
                trade_date=str(d),
                thresholds_version=str(config.versions.thresholds_version),
                registry_version=str(config.versions.registry_version),
                weights_version=str(config.versions.weights_version),
            )
            snaps = _load_ready_chaos_snapshots_for_date(
                chaos_conn,
                trade_date=str(d),
                thresholds_version=str(config.versions.thresholds_version),
                registry_version=str(config.versions.registry_version),
                weights_version=str(config.versions.weights_version),
            )

            snap_map: dict[str, dict[str, Any]] = {str(s["code"]): s for s in snaps if s.get("code")}

            missing_snapshot = int(len(all_codes)) - int(ready_n) - int(pending_n)
            skipped_missing_snapshot_by_date[str(d)] = int(max(0, missing_snapshot))
            skipped_pending_snapshot_by_date[str(d)] = int(max(0, pending_n))

            exits: list[tuple[str, SnapshotRef]] = []
            for code, pos in list(positions.items()):
                snap = snap_map.get(str(code))
                if not snap:
                    continue
                score, pred = _compute_score_and_pred(
                    snap=snap,
                    signal_mode=str(config.signal.signal_mode),
                    combo_lambda=config.signal.combo_lambda,
                    combo_beta=config.signal.combo_beta,
                )
                if int(pred) == -1:
                    exits.append(
                        (
                            str(code),
                            SnapshotRef(
                                trade_date=str(d),
                                reference_mode=str(snap.get("reference_mode") or ""),
                                registry_version=str(config.versions.registry_version),
                                weights_version=str(config.versions.weights_version),
                                thresholds_version=str(config.versions.thresholds_version),
                                net_energy=float(snap.get("net_energy") or 0.0),
                                score=float(score),
                                pred=int(pred),
                            ),
                        )
                    )

            for code, exit_ref in exits:
                pos = positions.get(str(code))
                if not pos:
                    continue
                px = _load_close(stock_conn, code=str(code), trade_date=str(exec_date))
                if px is None:
                    continue
                pos.exit_signal_date = str(d)
                pos.exit_date = str(exec_date)
                pos.exit_price_close = float(px)
                pos.exit_reason = "signal_exit"
                pos.exit_snapshot_ref = exit_ref
                pos.timeline.append({"date": str(d), "event": "exit_signal"})
                pos.timeline.append({"date": str(exec_date), "event": "exit"})
                trades.append(pos)
                positions.pop(str(code), None)

            candidates: list[tuple[float, str, SnapshotRef]] = []
            for code, snap in snap_map.items():
                if code in positions:
                    continue
                score, pred = _compute_score_and_pred(
                    snap=snap,
                    signal_mode=str(config.signal.signal_mode),
                    combo_lambda=config.signal.combo_lambda,
                    combo_beta=config.signal.combo_beta,
                )
                if int(pred) != 1:
                    continue
                candidates.append(
                    (
                        float(score),
                        str(code),
                        SnapshotRef(
                            trade_date=str(d),
                            reference_mode=str(snap.get("reference_mode") or ""),
                            registry_version=str(config.versions.registry_version),
                            weights_version=str(config.versions.weights_version),
                            thresholds_version=str(config.versions.thresholds_version),
                            net_energy=float(snap.get("net_energy") or 0.0),
                            score=float(score),
                            pred=int(pred),
                        ),
                    )
                )
            candidates.sort(key=lambda x: (-float(x[0]), str(x[1])))

            slots = int(config.max_positions) - int(len(positions))
            if slots > 0:
                picked = candidates[: int(slots)]
            else:
                picked = []

            capital_per_pos = float(config.initial_capital) * float(config.position_size_pct) / 100.0
            for _score, code, entry_ref in picked:
                px = _load_close(stock_conn, code=str(code), trade_date=str(exec_date))
                if px is None or float(px) <= 0:
                    continue
                qty = int(float(capital_per_pos) // float(px))
                if qty <= 0:
                    continue
                t = TradeRecord(
                    code=str(code),
                    name=str(name_map.get(str(code)) or ""),
                    signal_date=str(d),
                    entry_date=str(exec_date),
                    entry_price_close=float(px),
                    entry_reason="entry_signal",
                    entry_snapshot_ref=entry_ref,
                    timeline=[{"date": str(d), "event": "pool_in"}, {"date": str(exec_date), "event": "entry"}],
                )
                positions[str(code)] = t

            fe = _build_filters_eval_120d_for_date(
                stock_conn=stock_conn,
                chaos_conn=chaos_conn,
                all_codes=all_codes,
                trade_dates=trade_dates,
                asof_date=str(d),
                label_horizon_trading_days=120,
                thresholds_version=str(config.versions.thresholds_version),
                registry_version=str(config.versions.registry_version),
                weights_version=str(config.versions.weights_version),
                signal_mode=str(config.signal.signal_mode),
                combo_lambda=config.signal.combo_lambda,
                combo_beta=config.signal.combo_beta,
            )
            if fe is not None:
                filters_eval.append(fe)

        last_date = trade_dates[-1]
        for code, pos in list(positions.items()):
            px = _load_close(stock_conn, code=str(code), trade_date=str(last_date))
            if px is None:
                continue
            pos.exit_signal_date = str(last_date)
            pos.exit_date = str(last_date)
            pos.exit_price_close = float(px)
            pos.exit_reason = "end_of_test"
            pos.exit_snapshot_ref = SnapshotRef(
                trade_date=str(last_date),
                reference_mode=str(pos.entry_snapshot_ref.reference_mode),
                registry_version=str(config.versions.registry_version),
                weights_version=str(config.versions.weights_version),
                thresholds_version=str(config.versions.thresholds_version),
                net_energy=float(pos.entry_snapshot_ref.net_energy),
                score=float(pos.entry_snapshot_ref.score),
                pred=int(pos.entry_snapshot_ref.pred),
            )
            pos.timeline.append({"date": str(last_date), "event": "exit_signal"})
            pos.timeline.append({"date": str(last_date), "event": "exit"})
            trades.append(pos)
            positions.pop(str(code), None)

        for t in trades:
            _compute_trade_metrics_close_only(stock_conn=stock_conn, trade=t, trade_dates=trade_dates)

        weekly = _build_weekly_window_summaries(
            trade_dates=trade_dates,
            trades=trades,
            skipped_missing_snapshot_by_date=skipped_missing_snapshot_by_date,
            skipped_pending_snapshot_by_date=skipped_pending_snapshot_by_date,
        )
        regime = _build_regime_window_summaries(
            chaos_conn=chaos_conn,
            trades=trades,
            thresholds_version=str(config.versions.thresholds_version),
            registry_version=str(config.versions.registry_version),
            weights_version=str(config.versions.weights_version),
        )
        meta = {
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "project_root": str(self._project_root),
            "no_lookahead": True,
            "execution_price": "t_plus_1_close",
            "holding_days": "trading_days",
            "summary": {
                "trade_days": int(len(trade_dates)),
                "trades": int(len(trades)),
            },
        }
        return BacktestRunResult(
            config=config,
            trade_dates=list(trade_dates),
            trades=list(trades),
            window_summaries_weekly=list(weekly),
            window_summaries_regime=list(regime),
            filters_eval_120d=list(filters_eval),
            meta=dict(meta),
        )


def write_backtest_artifacts(
    *,
    project_root: Path,
    end_date: str,
    suffix: str,
    result: BacktestRunResult,
) -> dict[str, str]:
    root = Path(project_root)
    name_suffix = str(suffix).strip()
    tag = f"_{name_suffix}" if name_suffix else ""
    ledger_dir = root / "var" / "ledgers" / "chaos_backtest" / str(end_date)
    artifact_dir = root / "var" / "artifacts" / "chaos_backtest" / str(end_date)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    meta = dict(result.meta or {})
    meta["config"] = asdict(result.config)

    paths: dict[str, str] = {}
    items = [
        (f"chaos_backtest_meta{tag}.json", meta),
        (f"chaos_backtest_trades{tag}.json", [asdict(t) for t in list(result.trades or [])]),
        (f"chaos_backtest_window_summary_weekly{tag}.json", [asdict(w) for w in list(result.window_summaries_weekly or [])]),
        (f"chaos_backtest_window_summary_regime{tag}.json", [asdict(w) for w in list(result.window_summaries_regime or [])]),
        (f"chaos_backtest_filters_eval_120d{tag}.json", [asdict(f) for f in list(result.filters_eval_120d or [])]),
    ]
    for fn, payload in items:
        lp = ledger_dir / fn
        ap = artifact_dir / fn
        txt = json.dumps(payload, ensure_ascii=False, indent=2)
        lp.write_text(txt, encoding="utf-8")
        ap.write_text(txt, encoding="utf-8")
        paths[fn] = str(ap)
    return paths
