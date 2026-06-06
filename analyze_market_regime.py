#!/usr/bin/env python3
"""Analyze market regime differences between training and test periods."""

import sqlite3
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

DB_PATH = Path("var/db/stock_data.db")

def get_market_stats(start_date: date, end_date: date) -> dict:
    """Get market statistics for a period."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Get all daily returns for the period
    cursor.execute(
        """
        SELECT dp.code, dp.close, dp.volume,
               LAG(dp.close) OVER (PARTITION BY dp.code ORDER BY dp.trade_date) as prev_close
        FROM daily_prices dp
        JOIN stocks s ON dp.code = s.code
        WHERE dp.trade_date BETWEEN ? AND ?
          AND (s.is_delisted IS NULL OR s.is_delisted = 0)
        ORDER BY dp.trade_date
    """,
        (start_date.isoformat(), end_date.isoformat()),
    )

    returns = []
    volumes = []
    for row in cursor.fetchall():
        code, close, volume, prev_close = row
        if prev_close and prev_close > 0 and close:
            ret = (close - prev_close) / prev_close * 100
            returns.append(ret)
            volumes.append(volume or 0)

    conn.close()

    if not returns:
        return {}

    returns = np.array(returns)
    return {
        "mean_return": np.mean(returns),
        "std_return": np.std(returns),
        "median_return": np.median(returns),
        "up_days_pct": np.mean(returns > 0) * 100,
        "down_days_pct": np.mean(returns < 0) * 100,
        "samples": len(returns),
    }

def main():
    print("=" * 60)
    print("Market Regime Analysis")
    print("=" * 60)

    # Training period (approximate from dataset)
    train_periods = [
        ("Training (Jan-Feb 2025)", date(2025, 1, 1), date(2025, 2, 28)),
        ("Test (April 2025)", date(2025, 4, 1), date(2025, 4, 30)),
    ]

    for name, start, end in train_periods:
        stats = get_market_stats(start, end)
        print(f"\n{name}:")
        if stats:
            print(f"  Mean return: {stats['mean_return']:.3f}%")
            print(f"  Std return: {stats['std_return']:.3f}%")
            print(f"  Median return: {stats['median_return']:.3f}%")
            print(f"  Up days: {stats['up_days_pct']:.1f}%")
            print(f"  Down days: {stats['down_days_pct']:.1f}%")
            print(f"  Samples: {stats['samples']}")

    # Check 5-day forward return distribution
    print("\n" + "=" * 60)
    print("5-Day Forward Return Distribution")
    print("=" * 60)

    for name, start, end in train_periods:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT dp.code, dp.trade_date, dp.close
            FROM daily_prices dp
            JOIN stocks s ON dp.code = s.code
            WHERE dp.trade_date BETWEEN ? AND ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
            ORDER BY dp.code, dp.trade_date
        """,
            (start.isoformat(), end.isoformat()),
        )

        rows = cursor.fetchall()
        conn.close()

        # Calculate 5-day forward returns
        forward_returns = []
        for i, (code, trade_date, close) in enumerate(rows):
            # Find price 5 days later
            for j in range(i + 1, min(i + 10, len(rows))):
                if rows[j][0] == code:
                    days_diff = (date.fromisoformat(rows[j][1]) - date.fromisoformat(trade_date)).days
                    if days_diff >= 5:
                        future_close = rows[j][2]
                        if close and future_close:
                            fwd_ret = (future_close - close) / close * 100
                            forward_returns.append(fwd_ret)
                        break

        if forward_returns:
            fwd = np.array(forward_returns)
            print(f"\n{name}:")
            print(f"  Mean 5d return: {np.mean(fwd):.3f}%")
            print(f"  Std 5d return: {np.std(fwd):.3f}%")
            print(f"  > 2% (bullish): {np.mean(fwd > 2) * 100:.1f}%")
            print(f"  < -2% (bearish): {np.mean(fwd < -2) * 100:.1f}%")
            print(f"  -2% to 2% (neutral): {np.mean((fwd >= -2) & (fwd <= 2)) * 100:.1f}%")

if __name__ == "__main__":
    main()
