from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class T2Config:
    accel_window_days: int
    accel_return_threshold: float
    break_pct_threshold: float
    confirm_window_days: int
    prebreak_lookback_days: int


def _ensure_schema(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_top_hazard_labels_t2 (
          obs_date TEXT NOT NULL,
          code TEXT NOT NULL,
          horizon_days INTEGER NOT NULL,
          hit INTEGER NOT NULL,
          first_event_date TEXT,
          label_status TEXT NOT NULL,
          label_ready_at TEXT,
          accel_window_days INTEGER NOT NULL,
          accel_return_threshold REAL NOT NULL,
          break_pct_threshold REAL NOT NULL,
          confirm_window_days INTEGER NOT NULL,
          prebreak_lookback_days INTEGER NOT NULL,
          repair_rule TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (obs_date, code, horizon_days)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stock_top_hazard_labels_t2_code_date
        ON stock_top_hazard_labels_t2 (code, obs_date)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stock_top_hazard_labels_t2_date
        ON stock_top_hazard_labels_t2 (obs_date)
        """
    )
    conn.commit()


def _latest_trade_date(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()
    value = str((row or [None])[0] or "").strip()
    if not value:
        raise RuntimeError("daily_prices_missing_trade_date")
    return value


def _iter_price_rows(conn: sqlite3.Connection) -> Iterable[tuple[str, str, float, float, float]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT code, trade_date, close, high, pct_change
        FROM daily_prices
        WHERE trade_date IS NOT NULL AND TRIM(trade_date) != ''
        ORDER BY code, trade_date
        """
    )
    while True:
        rows = cursor.fetchmany(10000)
        if not rows:
            break
        for code, trade_date, close, high, pct_change in rows:
            code_s = str(code or "").strip()
            date_s = str(trade_date or "").strip()
            if not code_s or not date_s:
                continue
            yield (code_s, date_s, float(close or 0.0), float(high or 0.0), float(pct_change or 0.0))


def _confirmed_event_indices(
    *,
    dates: list[str],
    closes: list[float],
    highs: list[float],
    pct_changes: list[float],
    cfg: T2Config,
) -> list[int]:
    out: list[int] = []
    n = len(dates)
    for i in range(n):
        if i < cfg.accel_window_days:
            continue
        if i < cfg.prebreak_lookback_days:
            continue
        if float(pct_changes[i]) > float(cfg.break_pct_threshold):
            continue
        base_close = float(closes[i - cfg.accel_window_days])
        now_close = float(closes[i])
        if base_close <= 0 or now_close <= 0:
            continue
        ret = now_close / base_close - 1.0
        if ret < float(cfg.accel_return_threshold):
            continue
        pre_start = max(0, i - cfg.prebreak_lookback_days)
        pre_end = i
        if pre_end <= pre_start:
            continue
        pre_high = max(float(x) for x in highs[pre_start:pre_end])
        if pre_high <= 0:
            continue
        future_end = min(n - 1, i + cfg.confirm_window_days)
        if future_end <= i:
            continue
        recovered = False
        for j in range(i + 1, future_end + 1):
            if float(highs[j]) > float(pre_high):
                recovered = True
                break
        if not recovered:
            out.append(i)
    return out


def _write_labels_for_code(
    *,
    conn: sqlite3.Connection,
    code: str,
    dates: list[str],
    closes: list[float],
    highs: list[float],
    pct_changes: list[float],
    cfg: T2Config,
    horizons: list[int],
    latest_trade_date: str,
    batch_size: int = 5000,
) -> int:
    event_indices = _confirmed_event_indices(
        dates=dates,
        closes=closes,
        highs=highs,
        pct_changes=pct_changes,
        cfg=cfg,
    )
    event_set = set(event_indices)
    n = len(dates)
    now_iso = datetime.now(timezone.utc).isoformat()
    updated_rows: list[tuple] = []
    affected = 0
    for i in range(n):
        obs_date = dates[i]
        for horizon in horizons:
            required = i + int(horizon) + int(cfg.confirm_window_days)
            ready = required < n and obs_date <= latest_trade_date
            label_status = "ready" if ready else "pending"
            label_ready_at = dates[required] if ready else ""
            hit = 0
            first_event_date = ""
            if ready:
                window_end = min(n - 1, i + int(horizon))
                first_idx = None
                for j in range(i + 1, window_end + 1):
                    if j in event_set:
                        first_idx = j
                        break
                if first_idx is not None:
                    hit = 1
                    first_event_date = dates[first_idx]
            updated_rows.append(
                (
                    obs_date,
                    code,
                    int(horizon),
                    int(hit),
                    str(first_event_date),
                    str(label_status),
                    str(label_ready_at),
                    int(cfg.accel_window_days),
                    float(cfg.accel_return_threshold),
                    float(cfg.break_pct_threshold),
                    int(cfg.confirm_window_days),
                    int(cfg.prebreak_lookback_days),
                    "prebreak_5d_high_breakout",
                    now_iso,
                )
            )
            affected += 1
        if len(updated_rows) >= int(batch_size):
            conn.executemany(
                """
                INSERT OR REPLACE INTO stock_top_hazard_labels_t2 (
                  obs_date, code, horizon_days, hit, first_event_date,
                  label_status, label_ready_at,
                  accel_window_days, accel_return_threshold, break_pct_threshold,
                  confirm_window_days, prebreak_lookback_days, repair_rule, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                updated_rows,
            )
            conn.commit()
            updated_rows = []
    if updated_rows:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stock_top_hazard_labels_t2 (
              obs_date, code, horizon_days, hit, first_event_date,
              label_status, label_ready_at,
              accel_window_days, accel_return_threshold, break_pct_threshold,
              confirm_window_days, prebreak_lookback_days, repair_rule, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            updated_rows,
        )
        conn.commit()
    return affected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="var/db/stock_data.db")
    parser.add_argument("--horizons", default="5,20")
    parser.add_argument("--limit-codes", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    db_path = Path(str(args.db_path)).expanduser().resolve()
    horizons = [int(x) for x in str(args.horizons).split(",") if str(x).strip()]
    if not horizons:
        raise RuntimeError("horizons_empty")

    cfg = T2Config(
        accel_window_days=15,
        accel_return_threshold=0.30,
        break_pct_threshold=-7.0,
        confirm_window_days=10,
        prebreak_lookback_days=5,
    )

    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_schema(conn)
        latest_trade_date = _latest_trade_date(conn)
        resume_after = ""
        if bool(args.resume):
            try:
                row = conn.execute("SELECT MAX(code) FROM stock_top_hazard_labels_t2").fetchone()
                resume_after = str((row or [None])[0] or "").strip()
            except Exception:
                resume_after = ""
        current_code = ""
        dates: list[str] = []
        closes: list[float] = []
        highs: list[float] = []
        pct_changes: list[float] = []
        processed_codes = 0
        total_rows = 0
        for code, trade_date, close, high, pct_change in _iter_price_rows(conn):
            if resume_after and code <= resume_after:
                continue
            if current_code and code != current_code:
                total_rows += _write_labels_for_code(
                    conn=conn,
                    code=current_code,
                    dates=dates,
                    closes=closes,
                    highs=highs,
                    pct_changes=pct_changes,
                    cfg=cfg,
                    horizons=horizons,
                    latest_trade_date=latest_trade_date,
                )
                processed_codes += 1
                if processed_codes % 100 == 0:
                    print("processed_codes", processed_codes, "rows", total_rows)
                if int(args.limit_codes or 0) > 0 and processed_codes >= int(args.limit_codes):
                    break
                dates = []
                closes = []
                highs = []
                pct_changes = []
            current_code = code
            dates.append(trade_date)
            closes.append(float(close))
            highs.append(float(high))
            pct_changes.append(float(pct_change))

        if current_code and (int(args.limit_codes or 0) <= 0 or processed_codes < int(args.limit_codes)):
            total_rows += _write_labels_for_code(
                conn=conn,
                code=current_code,
                dates=dates,
                closes=closes,
                highs=highs,
                pct_changes=pct_changes,
                cfg=cfg,
                horizons=horizons,
                latest_trade_date=latest_trade_date,
            )
            processed_codes += 1

        print("done_codes", processed_codes, "label_rows_written", total_rows)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
