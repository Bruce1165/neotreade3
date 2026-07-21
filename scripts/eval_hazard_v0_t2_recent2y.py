from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from neotrade3.decision_engine.hazard_predictor_v0 import (
    HazardT2OnlineConfig,
    compute_hazard_snapshots_v0_t2_for_series,
)


@dataclass
class BinStats:
    n: int = 0
    hit_n: int = 0


def _bin_key(score: int) -> tuple[int, int]:
    s = max(0, min(100, int(score)))
    low = min(90, (s // 10) * 10)
    high = 100 if low == 90 else low + 9
    return (int(low), int(high))


def _latest_trade_date(conn: sqlite3.Connection) -> date:
    row = conn.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()
    value = str((row or [None])[0] or "").strip()
    if not value:
        raise RuntimeError("daily_prices_missing_trade_date")
    return date.fromisoformat(value)


def _iter_codes(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT code FROM daily_prices WHERE code IS NOT NULL AND TRIM(code) != '' ORDER BY code ASC"
    ).fetchall()
    return [str(r[0]) for r in rows if r and str(r[0] or "").strip()]


def _load_prices_for_code(
    conn: sqlite3.Connection,
    *,
    code: str,
    start_date: date,
    end_date: date,
) -> tuple[list[str], list[float], list[float], list[float]]:
    rows = conn.execute(
        """
        SELECT trade_date, close, high, pct_change
        FROM daily_prices
        WHERE code = ?
          AND trade_date BETWEEN ? AND ?
          AND trade_date IS NOT NULL
          AND TRIM(trade_date) != ''
        ORDER BY trade_date ASC
        """,
        (str(code), start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    dates: list[str] = []
    closes: list[float] = []
    highs: list[float] = []
    pct_changes: list[float] = []
    for d, c, h, p in rows:
        ds = str(d or "").strip()
        if not ds:
            continue
        dates.append(ds)
        closes.append(float(c or 0.0))
        highs.append(float(h or 0.0))
        pct_changes.append(float(p or 0.0))
    return (dates, closes, highs, pct_changes)


def _load_ready_labels_for_code(
    conn: sqlite3.Connection,
    *,
    code: str,
    start_date: date,
    end_date: date,
) -> list[tuple[str, int, int]]:
    rows = conn.execute(
        """
        SELECT obs_date, horizon_days, hit
        FROM stock_top_hazard_labels_t2
        WHERE code = ?
          AND obs_date BETWEEN ? AND ?
          AND label_status = 'ready'
          AND horizon_days IN (5, 20)
        ORDER BY obs_date ASC, horizon_days ASC
        """,
        (str(code), start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    out: list[tuple[str, int, int]] = []
    for obs_date, horizon_days, hit in rows:
        d = str(obs_date or "").strip()
        if not d:
            continue
        out.append((d, int(horizon_days or 0), int(hit or 0)))
    return out


def _format_bin_line(low: int, high: int, stats: BinStats) -> str:
    if stats.n <= 0:
        return f"{low:>3}-{high:<3} n=0 hit_rate=NA"
    rate = float(stats.hit_n) / float(stats.n)
    return f"{low:>3}-{high:<3} n={stats.n} hit_rate={rate:.4f}"


def _print_horizon_summary(
    *,
    horizon_days: int,
    overall_n: int,
    overall_hit: int,
    excluded_not_ready: int,
    excluded_by_state: int,
    missing_price: int,
    bins: dict[tuple[int, int], BinStats],
) -> None:
    print()
    print(f"horizon_days={int(horizon_days)}")
    print(
        f"n_ready={int(overall_n)} hit_n={int(overall_hit)} excluded_not_ready={int(excluded_not_ready)} excluded_by_state={int(excluded_by_state)} missing_price={int(missing_price)}"
    )
    overall_rate = float(overall_hit) / float(overall_n) if overall_n > 0 else 0.0
    print(f"overall_hit_rate={overall_rate:.6f}")
    if overall_n > 0:
        top = bins.get((90, 100))
        if top and top.n > 0:
            top_rate = float(top.hit_n) / float(top.n)
            lift = top_rate / overall_rate if overall_rate > 0 else 0.0
            print(f"top_bin_hit_rate={top_rate:.6f} lift_vs_overall={lift:.3f}")
    print("bins:")
    for low in range(0, 100, 10):
        high = 100 if low == 90 else low + 9
        stats = bins.get((low, high), BinStats())
        print("  " + _format_bin_line(low, high, stats))


def _bins_to_rows(bins: dict[tuple[int, int], BinStats]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for low in range(0, 100, 10):
        high = 100 if low == 90 else low + 9
        stats = bins.get((low, high), BinStats())
        hit_rate = float(stats.hit_n) / float(stats.n) if stats.n > 0 else None
        out.append(
            {
                "bin_low": int(low),
                "bin_high": int(high),
                "n": int(stats.n),
                "hit_n": int(stats.hit_n),
                "hit_rate": float(hit_rate) if hit_rate is not None else None,
            }
        )
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="var/db/stock_data.db")
    parser.add_argument("--lookback-days", type=int, default=730)
    parser.add_argument("--buffer-days", type=int, default=120)
    parser.add_argument("--limit-codes", type=int, default=0)
    parser.add_argument("--write-artifacts", action="store_true")
    parser.add_argument("--output-root", default="var/artifacts/evals/hazard_v0_t2")
    args = parser.parse_args()

    db_path = Path(str(args.db_path)).expanduser().resolve()
    conn = sqlite3.connect(str(db_path))
    try:
        end_date = _latest_trade_date(conn)
        start_date = end_date - timedelta(days=int(args.lookback_days))
        buffer_start = start_date - timedelta(days=max(int(args.buffer_days), 0))
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        print("hazard_v0_eval_t2_recent2y")
        print("run_id", run_id)
        print("date_range", start_date.isoformat(), end_date.isoformat())
        print("buffer_start", buffer_start.isoformat())

        cfg = HazardT2OnlineConfig()

        bins: dict[int, dict[tuple[int, int], BinStats]] = {
            5: defaultdict(BinStats),
            20: defaultdict(BinStats),
        }
        overall_n: dict[int, int] = {5: 0, 20: 0}
        overall_hit: dict[int, int] = {5: 0, 20: 0}
        excluded_not_ready: dict[int, int] = {5: 0, 20: 0}
        excluded_by_state: dict[int, int] = {5: 0, 20: 0}
        missing_price: dict[int, int] = {5: 0, 20: 0}
        state_stats: dict[int, dict[str, BinStats]] = {5: defaultdict(BinStats), 20: defaultdict(BinStats)}

        codes = _iter_codes(conn)
        total_codes = len(codes)
        processed = 0
        for code in codes:
            processed += 1
            if int(args.limit_codes or 0) > 0 and processed > int(args.limit_codes):
                break
            dates, closes, highs, pct_changes = _load_prices_for_code(
                conn,
                code=code,
                start_date=buffer_start,
                end_date=end_date,
            )
            if not dates:
                continue
            labels = _load_ready_labels_for_code(conn, code=code, start_date=start_date, end_date=end_date)
            if not labels:
                continue

            snapshots = compute_hazard_snapshots_v0_t2_for_series(
                dates=dates,
                closes=closes,
                highs=highs,
                pct_changes=pct_changes,
                cfg=cfg,
                include_evidence=False,
            )
            by_date: dict[str, dict[str, Any]] = {
                str(dates[i]): dict(snapshots[i]) for i in range(min(len(dates), len(snapshots)))
            }
            for obs_date, horizon_days, hit in labels:
                snap = by_date.get(str(obs_date))
                if not isinstance(snap, dict):
                    missing_price[int(horizon_days)] = int(missing_price.get(int(horizon_days), 0)) + 1
                    continue
                if str(snap.get("risk_status") or "") != "ready":
                    excluded_not_ready[int(horizon_days)] = int(excluded_not_ready.get(int(horizon_days), 0)) + 1
                    continue
                hz_state = str(snap.get("hazard_state") or "").strip() or "unknown"
                s_stats = state_stats[int(horizon_days)][hz_state]
                s_stats.n += 1
                s_stats.hit_n += int(hit or 0)

                if hz_state not in {"neutral", "accel_only"}:
                    excluded_by_state[int(horizon_days)] = int(excluded_by_state.get(int(horizon_days), 0)) + 1
                    continue
                score_key = "stock_top_risk_5d" if int(horizon_days) == 5 else "stock_top_risk_20d"
                try:
                    score = int(snap.get(score_key) or 0)
                except Exception:
                    score = 0
                low, high = _bin_key(score)
                stats = bins[int(horizon_days)][(low, high)]
                stats.n += 1
                stats.hit_n += int(hit or 0)
                overall_n[int(horizon_days)] = int(overall_n.get(int(horizon_days), 0)) + 1
                overall_hit[int(horizon_days)] = int(overall_hit.get(int(horizon_days), 0)) + int(hit or 0)

            if processed % 200 == 0:
                print("processed_codes", processed, "/", total_codes)

        bins_5_rows = _bins_to_rows(dict(bins[5]))
        bins_20_rows = _bins_to_rows(dict(bins[20]))

        _print_horizon_summary(
            horizon_days=5,
            overall_n=int(overall_n.get(5, 0)),
            overall_hit=int(overall_hit.get(5, 0)),
            excluded_not_ready=int(excluded_not_ready.get(5, 0)),
            excluded_by_state=int(excluded_by_state.get(5, 0)),
            missing_price=int(missing_price.get(5, 0)),
            bins=dict(bins[5]),
        )
        print()
        print("state_stats_horizon_5d:")
        for k in sorted(state_stats[5].keys()):
            v = state_stats[5][k]
            rate = float(v.hit_n) / float(v.n) if v.n > 0 else 0.0
            print(f"  {k} n={v.n} hit_rate={rate:.6f}")
        _print_horizon_summary(
            horizon_days=20,
            overall_n=int(overall_n.get(20, 0)),
            overall_hit=int(overall_hit.get(20, 0)),
            excluded_not_ready=int(excluded_not_ready.get(20, 0)),
            excluded_by_state=int(excluded_by_state.get(20, 0)),
            missing_price=int(missing_price.get(20, 0)),
            bins=dict(bins[20]),
        )
        print()
        print("state_stats_horizon_20d:")
        for k in sorted(state_stats[20].keys()):
            v = state_stats[20][k]
            rate = float(v.hit_n) / float(v.n) if v.n > 0 else 0.0
            print(f"  {k} n={v.n} hit_rate={rate:.6f}")

        if bool(args.write_artifacts):
            output_root = Path(str(args.output_root)).expanduser()
            out_dir = (output_root / str(run_id)).resolve()
            summary: dict[str, Any] = {
                "run_id": str(run_id),
                "db_path": str(db_path),
                "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "buffer_start": buffer_start.isoformat(),
                "label_table": "stock_top_hazard_labels_t2",
                "label_filters": {"label_status": "ready", "horizon_days": [5, 20]},
                "score_eval_state_filter": ["neutral", "accel_only"],
                "horizons": {
                    "5": {
                        "n_ready": int(overall_n.get(5, 0)),
                        "hit_n": int(overall_hit.get(5, 0)),
                        "excluded_not_ready": int(excluded_not_ready.get(5, 0)),
                        "excluded_by_state": int(excluded_by_state.get(5, 0)),
                        "missing_price": int(missing_price.get(5, 0)),
                        "bins": bins_5_rows,
                        "state_stats": {
                            k: {
                                "n": int(state_stats[5][k].n),
                                "hit_n": int(state_stats[5][k].hit_n),
                                "hit_rate": (
                                    float(state_stats[5][k].hit_n) / float(state_stats[5][k].n)
                                    if state_stats[5][k].n > 0
                                    else None
                                ),
                            }
                            for k in sorted(state_stats[5].keys())
                        },
                    },
                    "20": {
                        "n_ready": int(overall_n.get(20, 0)),
                        "hit_n": int(overall_hit.get(20, 0)),
                        "excluded_not_ready": int(excluded_not_ready.get(20, 0)),
                        "excluded_by_state": int(excluded_by_state.get(20, 0)),
                        "missing_price": int(missing_price.get(20, 0)),
                        "bins": bins_20_rows,
                        "state_stats": {
                            k: {
                                "n": int(state_stats[20][k].n),
                                "hit_n": int(state_stats[20][k].hit_n),
                                "hit_rate": (
                                    float(state_stats[20][k].hit_n) / float(state_stats[20][k].n)
                                    if state_stats[20][k].n > 0
                                    else None
                                ),
                            }
                            for k in sorted(state_stats[20].keys())
                        },
                    },
                },
            }
            config_snapshot: dict[str, Any] = {
                "hazard_predictor": "t2_online_v0",
                "cfg": {
                    "accel_window_days": int(cfg.accel_window_days),
                    "accel_return_threshold": float(cfg.accel_return_threshold),
                    "break_pct_threshold": float(cfg.break_pct_threshold),
                    "confirm_window_days": int(cfg.confirm_window_days),
                    "prebreak_lookback_days": int(cfg.prebreak_lookback_days),
                },
                "hold_watch_policy": {
                    "by_state": {
                        "stale_break": {"level": 3, "stage": "review_watch"},
                        "break_armed": {"level": 2, "stage": "observe_watch"},
                        "recovering": {"level": 1, "stage": "noise_watch"},
                    },
                    "by_score_when_state_neutral_or_accel": {"level1": 40, "level2": 70, "level3": 90},
                },
            }
            _write_json(out_dir / "summary.json", summary)
            _write_json(out_dir / "config_snapshot.json", config_snapshot)
            _write_csv(
                out_dir / "bins_5d.csv",
                bins_5_rows,
                fieldnames=["bin_low", "bin_high", "n", "hit_n", "hit_rate"],
            )
            _write_csv(
                out_dir / "bins_20d.csv",
                bins_20_rows,
                fieldnames=["bin_low", "bin_high", "n", "hit_n", "hit_rate"],
            )
            print()
            print("artifacts_written", str(out_dir))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
