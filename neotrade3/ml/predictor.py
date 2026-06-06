"""ML-based stock return predictor using simple features.

A lightweight ML module that predicts 5-day forward returns using:
- Technical features: momentum, volatility, volume trends
- Fundamental features: PE, PB, ROE
- Market context: sector performance, market phase

Uses a simple RandomForest model (no heavy dependencies like PyTorch/TensorFlow).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class PredictionResult:
    """ML prediction result for a single stock."""

    code: str
    name: str
    predicted_return_5d: float  # Predicted 5-day return (%)
    confidence: float  # 0-1, model confidence
    probability_up: float  # Probability of positive return
    feature_importance: dict[str, float]  # Which features drove the prediction
    model_version: str = "v1.0"


class MLPredictor:
    """Lightweight ML predictor for stock returns.

    Uses trained RandomForest model if available, falls back to heuristic.
    """

    def __init__(self, db_path: str | Path, model_dir: str | Path = "var/models") -> None:
        self.db_path = Path(db_path)
        self.model_dir = Path(model_dir)
        self._model: Any | None = None
        self._feature_names: list[str] = []
        self._sklearn_available = self._check_sklearn()
        self._load_trained_model()

    def _check_sklearn(self) -> bool:
        """Check if scikit-learn is available."""
        try:
            import sklearn  # noqa: F401
            return True
        except ImportError:
            return False

    def _load_trained_model(self) -> bool:
        """Load trained model from disk if available."""
        if not self._sklearn_available:
            return False

        model_path = self.model_dir / "rf_model_v1.pkl"
        if not model_path.exists():
            return False

        try:
            import pickle
            with open(model_path, "rb") as f:
                data = pickle.load(f)
                self._model = data["model"]
                self._feature_names = data["features"]
            return True
        except Exception:
            return False

    def _get_feature_names(self) -> list[str]:
        """Return list of feature names used by the model."""
        return [
            "return_5d",  # 5-day momentum
            "return_20d",  # 20-day momentum
            "volatility_20d",  # 20-day volatility
            "volume_ratio",  # Volume vs 20-day avg
            "pe_ratio",  # Valuation
            "pb_ratio",
            "roe",
            "market_return_5d",  # Market context
            "sector_return_5d",  # Sector context
        ]

    def _extract_features(
        self, code: str, target_date: date
    ) -> dict[str, float] | None:
        """Extract features for a single stock from database.

        Reuses MLTrainer's feature extraction for consistency.
        """
        from neotrade3.ml.trainer import MLTrainer
        trainer = MLTrainer(self.db_path, model_dir=self.model_dir)
        return trainer._extract_features_for_date(code, target_date)

    def _heuristic_predict(self, features: dict[str, float]) -> tuple[float, float, float]:
        """Simple heuristic prediction when sklearn not available.

        Uses a balanced mix of momentum, mean-reversion, and risk factors
        to avoid systematic bullish/bearish bias.

        Returns: (predicted_return, confidence, probability_up)
        """
        score = 0.0

        # --- Momentum signals (reduced weight) ---
        momentum_score = (
            features.get("return_5d", 0) * 0.06
            + features.get("return_20d", 0) * 0.05
        )

        # --- Mean-reversion signals (stronger weight) ---
        r5 = features.get("return_5d", 0)
        r20 = features.get("return_20d", 0)
        # Short-term overextension → expect pullback
        mean_reversion_score = -r5 * 0.12
        # If 5d gain >> 20d gain, stock is overextended
        if r20 != 0:
            overextension = r5 / max(abs(r20), 1)
            mean_reversion_score -= max(0, overextension - 1) * 2.0

        # --- Fundamental quality ---
        roe = features.get("roe", 0)
        pe = features.get("pe_ratio", 0)
        pb = features.get("pb_ratio", 0)
        fundamental_score = 0.0
        # ROE positive signal (capped)
        if 0 < roe < 200:
            fundamental_score += min(roe, 30) * 0.02
        # PE valuation penalty
        if 0 < pe < 200:
            fundamental_score -= max(0, pe - 25) * 0.008
        # PB valuation penalty
        if 0 < pb < 20:
            fundamental_score -= max(0, pb - 3) * 0.015

        # --- Risk penalty (stronger) ---
        vol = features.get("volatility_20d", 0)
        risk_penalty = -max(0, vol - 25) * 0.03

        # --- Volume signal (contrarian) ---
        vol_ratio = features.get("volume_ratio", 1.0)
        # Extremely high volume after rise = distribution
        if r5 > 3 and vol_ratio > 2:
            risk_penalty -= 1.5
        # Volume confirms trend
        elif r5 > 0 and 1.2 < vol_ratio < 2:
            fundamental_score += 0.3

        # --- Market context (moderate) ---
        market_score = (
            features.get("market_return_5d", 0) * 0.04
            + features.get("sector_return_5d", 0) * 0.04
        )

        # --- Combine ---
        score = momentum_score + mean_reversion_score + fundamental_score + risk_penalty + market_score

        # Normalize to reasonable return range (-8% to +8%)
        predicted_return = max(-8, min(8, score))

        # Confidence based on feature agreement
        signals = [r5, r20, features.get("market_return_5d", 0), features.get("sector_return_5d", 0)]
        positive_signals = sum(1 for s in signals if s > 0)
        negative_signals = sum(1 for s in signals if s < 0)
        agreement = max(positive_signals, negative_signals) / max(len(signals), 1)
        confidence = 0.3 + agreement * 0.4  # Range: 0.3 ~ 0.7

        # Probability up (centered around 0.5)
        prob_up = 0.5 + predicted_return / 16  # Map -8..8 to 0..1
        prob_up = max(0.15, min(0.85, prob_up))

        return predicted_return, confidence, prob_up

    def _model_predict(self, features: dict[str, float]) -> tuple[float, float, float]:
        """Predict using trained RandomForest model.

        Returns: (predicted_return, confidence, probability_up)
        """
        if self._model is None:
            raise RuntimeError("Model not loaded")

        # Build feature vector
        X = np.array([[features.get(f, 0) for f in self._feature_names]])

        # Get probability distribution
        proba = self._model.predict_proba(X)[0]
        prob_down, prob_up = proba[0], proba[1]

        # Use higher threshold (0.6) for bullish signal to reduce false positives
        # When prob_up >= 0.6, predict bullish with confidence proportional to excess
        # When prob_up <= 0.4, predict bearish
        # Otherwise neutral (return near 0)
        if prob_up >= 0.6:
            predicted_return = (prob_up - 0.6) * 20  # 0.6->0%, 0.8->+4%, 1.0->+8%
            confidence = (prob_up - 0.6) * 2.5  # 0.6->0, 1.0->1.0
        elif prob_up <= 0.4:
            predicted_return = (prob_up - 0.4) * 20  # 0.4->0%, 0.2->-4%, 0.0->-8%
            confidence = (0.4 - prob_up) * 2.5
        else:
            predicted_return = (prob_up - 0.5) * 4  # Small signal near 0
            confidence = 0.3

        predicted_return = max(-8, min(8, predicted_return))
        confidence = max(0.3, min(0.95, confidence))

        return predicted_return, confidence, prob_up

    def predict(
        self, code: str, name: str, target_date: date | None = None
    ) -> PredictionResult | None:
        """Predict 5-day forward return for a single stock.

        Args:
            code: Stock code
            name: Stock name
            target_date: Prediction date (default: today)

        Returns:
            PredictionResult or None if insufficient data
        """
        if target_date is None:
            target_date = date.today()

        features = self._extract_features(code, target_date)
        if features is None:
            return None

        if self._model is not None:
            # Use trained sklearn model
            pred_return, confidence, prob_up = self._model_predict(features)
        else:
            # Use heuristic model
            pred_return, confidence, prob_up = self._heuristic_predict(features)

        # Calculate feature importance (simplified)
        feature_importance = {
            "momentum": 0.35,  # return_5d + return_20d
            "fundamentals": 0.25,  # PE, PB, ROE
            "market_context": 0.30,  # market + sector
            "volume": 0.10,
        }

        return PredictionResult(
            code=code,
            name=name,
            predicted_return_5d=round(pred_return, 2),
            confidence=round(confidence, 2),
            probability_up=round(prob_up, 2),
            feature_importance=feature_importance,
        )

    def predict_batch(
        self, codes: list[tuple[str, str]], target_date: date | None = None
    ) -> list[PredictionResult]:
        """Predict for multiple stocks.

        Args:
            codes: List of (code, name) tuples
            target_date: Prediction date

        Returns:
            List of PredictionResult (None filtered out)
        """
        results = []
        for code, name in codes:
            result = self.predict(code, name, target_date)
            if result:
                results.append(result)
        return sorted(results, key=lambda x: x.predicted_return_5d, reverse=True)

    def get_top_picks(
        self,
        target_date: date | None = None,
        top_n: int = 10,
        min_confidence: float = 0.3,
    ) -> list[PredictionResult]:
        """Get top N stock picks for the given date.

        Args:
            target_date: Prediction date
            top_n: Number of stocks to return
            min_confidence: Minimum confidence threshold

        Returns:
            List of top PredictionResult
        """
        # Get universe from database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        if target_date is None:
            target_date = date.today()

        cursor.execute(
            """
            SELECT s.code, s.name
            FROM stocks s
            JOIN daily_prices dp ON s.code = dp.code
            WHERE dp.trade_date = ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
              AND s.name NOT LIKE '%ST%'
            ORDER BY dp.amount DESC
            LIMIT 300
        """,
            (target_date.isoformat(),),
        )

        stocks = cursor.fetchall()
        conn.close()

        # Predict for all
        predictions = self.predict_batch(stocks, target_date)

        # Filter by confidence and return top N
        filtered = [p for p in predictions if p.confidence >= min_confidence]
        return filtered[:top_n]
