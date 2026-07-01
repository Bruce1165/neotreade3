#!/usr/bin/env python3
"""Test v4 model on out-of-sample data (April 2025)."""

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from neotrade3.ml.trainer import MLTrainer, TrainingConfig

DB_PATH = Path("var/db/stock_data.db")
MODEL_NAME = "rf_model_v4.pkl"

# Out-of-sample period: April 2025
TEST_START = date(2025, 4, 1)
TEST_END = date(2025, 4, 30)

def get_trading_dates(start: date, end: date) -> list[date]:
    """Get all trading dates in range."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT trade_date FROM daily_prices
        WHERE trade_date BETWEEN ? AND ?
        ORDER BY trade_date
    """,
        (start.isoformat(), end.isoformat()),
    )
    dates = [date.fromisoformat(r[0]) for r in cursor.fetchall()]
    conn.close()
    return dates

def get_universe(test_date: date) -> list[str]:
    """Get top 100 stocks by volume for a date."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.code FROM stocks s
        JOIN daily_prices dp ON s.code = dp.code
        WHERE dp.trade_date = ? AND (s.is_delisted IS NULL OR s.is_delisted = 0)
        ORDER BY dp.amount DESC LIMIT 100
    """,
        (test_date.isoformat(),),
    )
    codes = [r[0] for r in cursor.fetchall()]
    conn.close()
    return codes

def get_forward_return(code: str, from_date: date, days: int = 5) -> float | None:
    """Get forward return for labeling."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT close FROM daily_prices
        WHERE code = ? AND trade_date >= ?
        ORDER BY trade_date ASC
        LIMIT ?
    """,
        (code, from_date.isoformat(), days + 1),
    )
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < days + 1:
        return None

    start_price = rows[0][0]
    end_price = rows[days][0]
    if start_price is None or end_price is None or start_price == 0:
        return None
    return (end_price - start_price) / start_price * 100

def main():
    print("=" * 60)
    print("V4 Model Out-of-Sample Backtest (April 2025)")
    print("=" * 60)

    # Load trained v4 model
    trainer = MLTrainer(DB_PATH)
    if not trainer.load_model(MODEL_NAME):
        print(f"ERROR: Could not load model {MODEL_NAME}")
        return

    print(f"Loaded model: {MODEL_NAME}")
    print(f"Feature count: {len(trainer._feature_names)}")
    print(f"Features: {trainer._feature_names}")
    print()

    # Get test dates
    test_dates = get_trading_dates(TEST_START, TEST_END)
    print(f"Test period: {TEST_START} to {TEST_END}")
    print(f"Trading days: {len(test_dates)}")
    print()

    # Weekly sampling
    sample_dates = test_dates[::5]
    print(f"Sample dates ({len(sample_dates)}): {[d.isoformat() for d in sample_dates]}")
    print()

    predictions = []
    actuals = []
    probs_up = []

    for sample_date in sample_dates:
        universe = get_universe(sample_date)
        print(f"\n{sample_date}: {len(universe)} stocks")

        for code in universe:
            features = trainer._extract_features_for_date(code, sample_date)
            if features is None:
                continue

            forward_return = get_forward_return(code, sample_date, 5)
            if forward_return is None:
                continue

            # Predict
            prob_down, prob_up = trainer.predict_proba(features)
            probs_up.append(prob_up)

            # Threshold 0.6 for signal
            if prob_up >= 0.6:
                pred = 1  # Bullish
            elif prob_up <= 0.4:
                pred = 0  # Bearish
            else:
                pred = None  # Neutral - skip

            if pred is not None:
                actual = 1 if forward_return > 2.0 else (0 if forward_return < -2.0 else None)
                if actual is not None:
                    predictions.append(pred)
                    actuals.append(actual)

    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)

    if len(predictions) < 10:
        print(f"Insufficient predictions: {len(predictions)}")
        return

    # Calculate metrics
    correct = sum(1 for p, a in zip(predictions, actuals) if p == a)
    total = len(predictions)
    accuracy = correct / total * 100

    bullish_correct = sum(1 for p, a in zip(predictions, actuals) if p == 1 and a == 1)
    bullish_total = sum(1 for p in predictions if p == 1)
    bullish_precision = bullish_correct / bullish_total * 100 if bullish_total > 0 else 0

    bearish_correct = sum(1 for p, a in zip(predictions, actuals) if p == 0 and a == 0)
    bearish_total = sum(1 for p in predictions if p == 0)
    bearish_precision = bearish_correct / bearish_total * 100 if bearish_total > 0 else 0

    print(f"Total predictions: {total}")
    print(f"Overall accuracy: {accuracy:.1f}% ({correct}/{total})")
    print(f"Bullish signals: {bullish_total} (precision: {bullish_precision:.1f}%)")
    print(f"Bearish signals: {bearish_total} (precision: {bearish_precision:.1f}%)")

    # Distribution
    actual_up = sum(1 for a in actuals if a == 1)
    actual_down = sum(1 for a in actuals if a == 0)
    print(f"\nActual distribution: {actual_up} up, {actual_down} down")
    print(f"Predicted distribution: {bullish_total} up, {bearish_total} down")

    # Probability distribution
    import numpy as np
    print(f"\nProbability distribution:")
    print(f"  Mean prob_up: {np.mean(probs_up):.3f}")
    print(f"  Std prob_up: {np.std(probs_up):.3f}")
    print(f"  Prob_up > 0.6: {sum(1 for p in probs_up if p > 0.6)} ({sum(1 for p in probs_up if p > 0.6)/len(probs_up)*100:.1f}%)")
    print(f"  Prob_up < 0.4: {sum(1 for p in probs_up if p < 0.4)} ({sum(1 for p in probs_up if p < 0.4)/len(probs_up)*100:.1f}%)")

if __name__ == "__main__":
    main()
