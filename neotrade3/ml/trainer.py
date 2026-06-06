"""ML model training for stock return prediction.

Trains a RandomForest classifier to predict 5-day forward returns.
Features: momentum, volatility, valuation, market context
Label: binary (1 if return > 2%, 0 otherwise)
"""

from __future__ import annotations

import logging
import pickle
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for model training."""

    lookback_days: int = 180  # Use last 6 months for training
    forward_days: int = 5  # Predict 5-day forward return
    threshold_up: float = 2.0  # Label=1 if return > 2%
    threshold_down: float = -2.0  # Label=0 if return < -2%
    test_size: float = 0.2  # 20% for validation
    random_state: int = 42


class MLTrainer:
    """Train and manage ML models for stock prediction."""

    def __init__(self, db_path: str | Path, model_dir: str | Path = "var/models") -> None:
        self.db_path = Path(db_path)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._model: Any | None = None
        self._feature_names: list[str] = [
            # Momentum
            "return_5d",
            "return_20d",
            "return_60d",
            # Volatility
            "volatility_20d",
            "volatility_regime",  # Current vol vs 60d avg
            # Volume
            "volume_ratio",
            "volume_trend_5d",
            # Technical indicators
            "rsi_14",
            "macd_histogram",
            "bollinger_position",
            # Fundamentals
            "pe_ratio",
            "pb_ratio",
            "roe",
            # Market context
            "market_return_5d",
            "market_return_20d",
            "market_volatility",
            "sector_return_5d",
            "market_breadth",  # % of stocks above 20d MA
            # Money flow
            "money_flow_5d",
            "money_flow_ratio",
        ]

    def _extract_features_for_date(
        self, code: str, target_date: date
    ) -> dict[str, float] | None:
        """Extract features for a single stock on a specific date."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # Get price history (need 70 days for MACD/60d return)
            cursor.execute(
                """
                SELECT close, volume, amount
                FROM daily_prices
                WHERE code = ? AND trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT 70
            """,
                (code, target_date.isoformat()),
            )
            rows = cursor.fetchall()
            if len(rows) < 60:
                return None

            closes = [r[0] for r in rows if r[0] is not None]
            volumes = [r[1] or 0 for r in rows]

            if len(closes) < 60:
                return None

            # --- Momentum ---
            return_5d = (closes[0] - closes[4]) / closes[4] * 100 if closes[4] > 0 else 0
            return_20d = (closes[0] - closes[19]) / closes[19] * 100 if closes[19] > 0 else 0
            return_60d = (closes[0] - closes[59]) / closes[59] * 100 if closes[59] > 0 else 0

            # --- Volatility ---
            daily_returns = []
            for i in range(min(19, len(closes) - 1)):
                if closes[i + 1] > 0:
                    daily_returns.append((closes[i] - closes[i + 1]) / closes[i + 1])
            volatility_20d = np.std(daily_returns) * np.sqrt(252) * 100 if daily_returns else 0

            # Volatility regime: current vol vs 60d average
            vol_60d_list = []
            for start in range(0, min(40, len(closes) - 20)):
                window = closes[start:start+20]
                if len(window) >= 2:
                    rets = [(window[i] - window[i+1]) / window[i+1] for i in range(len(window)-1) if window[i+1] > 0]
                    if rets:
                        vol_60d_list.append(np.std(rets) * np.sqrt(252) * 100)
            vol_60d_avg = np.mean(vol_60d_list) if vol_60d_list else volatility_20d
            volatility_regime = volatility_20d / vol_60d_avg if vol_60d_avg > 0 else 1.0

            # --- Volume ---
            valid_volumes = [v for v in volumes[1:20] if v > 0]
            volume_ratio = volumes[0] / np.mean(valid_volumes) if valid_volumes else 1.0
            # Volume trend: ratio of recent 5d avg to previous 15d avg
            recent_vol = np.mean(volumes[:5]) if volumes[:5] else 0
            older_vol = np.mean(volumes[5:20]) if volumes[5:20] else 0
            volume_trend_5d = recent_vol / older_vol if older_vol > 0 else 1.0

            # --- RSI 14 ---
            rsi_14 = self._calc_rsi(closes, period=14)

            # --- MACD Histogram ---
            macd_histogram = self._calc_macd_histogram(closes)

            # --- Bollinger Position ---
            bollinger_position = self._calc_bollinger_position(closes, period=20, num_std=2)

            # --- Fundamentals ---
            cursor.execute(
                "SELECT pe_ratio, pb_ratio, roe FROM stocks WHERE code = ?", (code,)
            )
            fund = cursor.fetchone()
            pe_ratio = fund[0] if fund and fund[0] else 0
            pb_ratio = fund[1] if fund and fund[1] else 0
            roe = fund[2] if fund and fund[2] else 0

            # --- Market context ---
            cursor.execute(
                """
                SELECT close FROM daily_prices
                WHERE code = '000001' AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 21
            """,
                (target_date.isoformat(),),
            )
            market_rows = cursor.fetchall()
            market_return_5d = 0
            market_return_20d = 0
            market_volatility = 0
            if len(market_rows) >= 21:
                m_closes = [r[0] for r in market_rows]
                market_return_5d = (m_closes[0] - m_closes[5]) / m_closes[5] * 100
                market_return_20d = (m_closes[0] - m_closes[20]) / m_closes[20] * 100
                m_rets = [(m_closes[i] - m_closes[i+1]) / m_closes[i+1] for i in range(min(20, len(m_closes)-1)) if m_closes[i+1] != 0]
                market_volatility = np.std(m_rets) * np.sqrt(252) * 100 if m_rets else 0

            # --- Sector context ---
            cursor.execute(
                "SELECT sector_lv1 FROM stocks WHERE code = ?", (code,)
            )
            sector_row = cursor.fetchone()
            sector_return_5d = 0
            if sector_row and sector_row[0]:
                cursor.execute(
                    """
                    SELECT AVG(dp.close) FROM daily_prices dp
                    JOIN stocks s ON dp.code = s.code
                    WHERE s.sector_lv1 = ? AND dp.trade_date IN (?, ?)
                    GROUP BY dp.trade_date ORDER BY dp.trade_date DESC LIMIT 2
                """,
                    (sector_row[0], target_date.isoformat(), (target_date - timedelta(days=5)).isoformat()),
                )
                sector_closes = cursor.fetchall()
                if len(sector_closes) >= 2:
                    sector_return_5d = (sector_closes[0][0] - sector_closes[1][0]) / sector_closes[1][0] * 100

            # --- Market breadth: % of stocks above 20d MA ---
            cursor.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT dp.code,
                           dp.close,
                           AVG(dp2.close) as ma20
                    FROM daily_prices dp
                    JOIN daily_prices dp2 ON dp.code = dp2.code
                        AND dp2.trade_date <= dp.trade_date
                        AND dp2.trade_date > date(dp.trade_date, '-20 days')
                    WHERE dp.trade_date = ?
                    GROUP BY dp.code, dp.close
                    HAVING dp.close > AVG(dp2.close)
                )
            """,
                (target_date.isoformat(),),
            )
            above_ma = cursor.fetchone()[0] or 0
            cursor.execute(
                """
                SELECT COUNT(DISTINCT code) FROM daily_prices
                WHERE trade_date = ?
            """,
                (target_date.isoformat(),),
            )
            total_stocks = cursor.fetchone()[0] or 1
            market_breadth = above_ma / total_stocks * 100

            # --- Money flow features ---
            money_flow_5d = 0.0
            money_flow_ratio = 1.0
            # 5日资金流向 = 近5日成交额均值 / 前15日成交额均值
            if len(volumes) >= 20:
                recent_amount = np.mean(volumes[:5])
                older_amount = np.mean(volumes[5:20])
                money_flow_ratio = recent_amount / older_amount if older_amount > 0 else 1.0
            # 结合价格变化判断资金方向
            if len(closes) >= 5 and closes[4] > 0:
                price_change = (closes[0] - closes[4]) / closes[4] * 100
                money_flow_5d = money_flow_ratio * (1 if price_change > 0 else -1)

            return {
                "return_5d": return_5d,
                "return_20d": return_20d,
                "return_60d": return_60d,
                "volatility_20d": volatility_20d,
                "volatility_regime": volatility_regime,
                "volume_ratio": volume_ratio,
                "volume_trend_5d": volume_trend_5d,
                "rsi_14": rsi_14,
                "macd_histogram": macd_histogram,
                "bollinger_position": bollinger_position,
                "pe_ratio": pe_ratio,
                "pb_ratio": pb_ratio,
                "roe": roe,
                "market_return_5d": market_return_5d,
                "market_return_20d": market_return_20d,
                "market_volatility": market_volatility,
                "sector_return_5d": sector_return_5d,
                "market_breadth": market_breadth,
                "money_flow_5d": money_flow_5d,
                "money_flow_ratio": money_flow_ratio,
            }

        finally:
            conn.close()

    @staticmethod
    def _calc_rsi(closes: list[float], period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index)."""
        if len(closes) < period + 1:
            return 50.0
        deltas = [closes[i] - closes[i + 1] for i in range(period)]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0.001
        rs = avg_gain / avg_loss
        return 100 - 100 / (1 + rs)

    @staticmethod
    def _calc_macd_histogram(closes: list[float]) -> float:
        """Calculate MACD histogram (12-26 EMA difference)."""
        if len(closes) < 26:
            return 0.0
        # Simple EMA calculation
        def ema(data, period):
            result = [data[0]]
            k = 2 / (period + 1)
            for i in range(1, len(data)):
                result.append(data[i] * k + result[-1] * (1 - k))
            return result[-1]

        ema12 = ema(closes[:30], 12)
        ema26 = ema(closes[:30], 26)
        macd_line = ema12 - ema26
        # Normalize by price
        return macd_line / closes[0] * 100 if closes[0] > 0 else 0

    @staticmethod
    def _calc_bollinger_position(closes: list[float], period: int = 20, num_std: float = 2.0) -> float:
        """Calculate position within Bollinger Bands (0=lower, 1=upper)."""
        if len(closes) < period:
            return 0.5
        recent = closes[:period]
        mean = np.mean(recent)
        std = np.std(recent)
        if std == 0:
            return 0.5
        upper = mean + num_std * std
        lower = mean - num_std * std
        position = (closes[0] - lower) / (upper - lower)
        return max(0.0, min(1.0, position))

    def _get_forward_return(self, code: str, from_date: date, days: int = 5) -> float | None:
        """Get forward return for labeling."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
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
            if len(rows) < days + 1:
                return None

            start_price = rows[0][0]
            end_price = rows[days][0]
            if start_price is None or end_price is None or start_price == 0:
                return None
            return (end_price - start_price) / start_price * 100

        finally:
            conn.close()

    def build_dataset(
        self, config: TrainingConfig | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Build training dataset from historical data.

        Returns:
            (X, y) where X is feature matrix, y is binary labels
        """
        if config is None:
            config = TrainingConfig()

        end_date = date.today()
        start_date = end_date - timedelta(days=config.lookback_days)

        logger.info("Building dataset from %s to %s", start_date, end_date)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get all trading dates in range
        cursor.execute(
            """
            SELECT DISTINCT trade_date FROM daily_prices
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        """,
            (start_date.isoformat(), end_date.isoformat()),
        )
        trading_dates = [date.fromisoformat(r[0]) for r in cursor.fetchall()]
        conn.close()

        # Sample dates (weekly to reduce correlation)
        sample_dates = trading_dates[::5]

        X_list = []
        y_list = []

        for sample_date in sample_dates:
            # Get universe for this date
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.code FROM stocks s
                JOIN daily_prices dp ON s.code = dp.code
                WHERE dp.trade_date = ? AND (s.is_delisted IS NULL OR s.is_delisted = 0)
                ORDER BY dp.amount DESC LIMIT 100
            """,
                (sample_date.isoformat(),),
            )
            codes = [r[0] for r in cursor.fetchall()]
            conn.close()

            for code in codes:
                features = self._extract_features_for_date(code, sample_date)
                if features is None:
                    continue

                forward_return = self._get_forward_return(code, sample_date, config.forward_days)
                if forward_return is None:
                    continue

                # Label: 1 if return > threshold_up, 0 if return < threshold_down, skip otherwise
                if forward_return > config.threshold_up:
                    label = 1
                elif forward_return < config.threshold_down:
                    label = 0
                else:
                    continue  # Skip neutral samples

                X_list.append([features[f] for f in self._feature_names])
                y_list.append(label)

        X = np.array(X_list)
        y = np.array(y_list)

        # Balance classes by downsampling majority class
        pos_idx = np.where(y == 1)[0]
        neg_idx = np.where(y == 0)[0]
        n_pos, n_neg = len(pos_idx), len(neg_idx)
        min_samples = min(n_pos, n_neg)

        if min_samples > 0:
            np.random.seed(42)
            pos_sample = np.random.choice(pos_idx, min_samples, replace=False)
            neg_sample = np.random.choice(neg_idx, min_samples, replace=False)
            balanced_idx = np.concatenate([pos_sample, neg_sample])
            np.random.shuffle(balanced_idx)
            X = X[balanced_idx]
            y = y[balanced_idx]

        logger.info("Dataset built: %d samples (positive: %d, negative: %d, balanced: %s)",
                    len(y), sum(y), len(y) - sum(y), "yes" if min_samples > 0 else "no")
        return X, y

    def train(self, config: TrainingConfig | None = None) -> dict[str, float]:
        """Train the model and return metrics.

        Returns:
            Dict with accuracy, precision, recall, f1
        """
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

        X, y = self.build_dataset(config)
        if len(X) < 100:
            raise ValueError(f"Insufficient training data: {len(X)} samples")

        if config is None:
            config = TrainingConfig()

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=config.test_size, random_state=config.random_state, stratify=y
        )

        # Train RandomForest
        self._model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=config.random_state,
            n_jobs=-1,
        )
        self._model.fit(X_train, y_train)

        # Evaluate
        y_pred = self._model.predict(X_test)
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1": f1_score(y_test, y_pred, zero_division=0),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
        }

        logger.info("Model trained: accuracy=%.3f, precision=%.3f, recall=%.3f", metrics["accuracy"], metrics["precision"], metrics["recall"])
        return metrics

    def save_model(self, filename: str = "rf_model.pkl") -> Path:
        """Save trained model to disk."""
        if self._model is None:
            raise RuntimeError("No model trained yet")

        path = self.model_dir / filename
        with open(path, "wb") as f:
            pickle.dump({"model": self._model, "features": self._feature_names}, f)

        logger.info("Model saved to %s", path)
        return path

    def load_model(self, filename: str = "rf_model.pkl") -> bool:
        """Load model from disk."""
        path = self.model_dir / filename
        if not path.exists():
            return False

        with open(path, "rb") as f:
            data = pickle.load(f)
            self._model = data["model"]
            self._feature_names = data["features"]

        logger.info("Model loaded from %s", path)
        return True

    def predict_proba(self, features: dict[str, float]) -> tuple[float, float]:
        """Predict probability of up/down.

        Returns:
            (prob_down, prob_up)
        """
        if self._model is None:
            raise RuntimeError("No model loaded")

        X = np.array([[features[f] for f in self._feature_names]])
        proba = self._model.predict_proba(X)[0]
        return proba[0], proba[1]  # (down, up)
