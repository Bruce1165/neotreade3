"""Weight adaptation for NeoTrade3 self-evolution.

权重自适应 - 根据市场环境和因子表现动态调整权重
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class MarketAdaptiveWeights:
    """Adaptive weights for different market conditions."""
    
    # Market phase
    market_phase: str  # bull, bear, range, transition
    
    # Dimension weights (sum should be ~1.0)
    resonance_technical: float = 0.30
    resonance_capital: float = 0.30
    resonance_policy: float = 0.30
    elliott_wave: float = 0.25
    sector_rotation: float = 0.15
    stock_tiering: float = 0.15
    market_phase_weight: float = 0.10
    cup_handle: float = 0.05
    
    # Adjustment metadata
    adjusted_at: date | None = None
    adjustment_reason: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "market_phase": self.market_phase,
            "weights": {
                "resonance_technical": round(self.resonance_technical, 3),
                "resonance_capital": round(self.resonance_capital, 3),
                "resonance_policy": round(self.resonance_policy, 3),
                "elliott_wave": round(self.elliott_wave, 3),
                "sector_rotation": round(self.sector_rotation, 3),
                "stock_tiering": round(self.stock_tiering, 3),
                "market_phase": round(self.market_phase_weight, 3),
                "cup_handle": round(self.cup_handle, 3),
            },
            "adjusted_at": self.adjusted_at.isoformat() if self.adjusted_at else None,
            "adjustment_reason": self.adjustment_reason,
        }


class WeightAdaptationEngine:
    """Engine for adapting weights based on market conditions and factor performance."""
    
    # Base weights (neutral market)
    BASE_WEIGHTS = {
        "resonance_technical": 0.30,
        "resonance_capital": 0.30,
        "resonance_policy": 0.30,
        "elliott_wave": 0.25,
        "sector_rotation": 0.15,
        "stock_tiering": 0.15,
        "market_phase": 0.10,
        "cup_handle": 0.05,
    }
    
    # Market phase adjustments
    PHASE_ADJUSTMENTS: dict[str, dict[str, float]] = {
        "bull": {
            "resonance_technical": 1.1,   # 技术面更重要
            "resonance_capital": 1.2,     # 资金面更重要
            "resonance_policy": 0.9,
            "elliott_wave": 1.0,
            "sector_rotation": 1.2,       # 板块轮动更重要
            "stock_tiering": 1.1,
            "market_phase": 0.8,
            "cup_handle": 1.0,
        },
        "bear": {
            "resonance_technical": 0.9,
            "resonance_capital": 0.8,
            "resonance_policy": 1.3,      # 政策面更重要
            "elliott_wave": 0.9,
            "sector_rotation": 0.8,
            "stock_tiering": 0.9,
            "market_phase": 1.3,          # 市场相位更重要
            "cup_handle": 0.7,
        },
        "range": {
            "resonance_technical": 1.0,
            "resonance_capital": 1.0,
            "resonance_policy": 1.0,
            "elliott_wave": 1.1,
            "sector_rotation": 1.0,
            "stock_tiering": 1.0,
            "market_phase": 1.0,
            "cup_handle": 1.2,            # 杯柄形态更重要
        },
        "transition": {
            "resonance_technical": 1.0,
            "resonance_capital": 1.1,
            "resonance_policy": 1.1,
            "elliott_wave": 0.9,
            "sector_rotation": 1.1,
            "stock_tiering": 1.0,
            "market_phase": 1.2,
            "cup_handle": 0.9,
        },
    }
    
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
    
    def adapt_weights(
        self,
        market_phase: str,
        factor_scores: dict[str, float] | None = None,
    ) -> MarketAdaptiveWeights:
        """Adapt weights based on market phase and factor performance.
        
        Args:
            market_phase: Current market phase (bull/bear/range/transition)
            factor_scores: Optional dict of factor_id -> score for performance-based adjustment
            
        Returns:
            MarketAdaptiveWeights with adjusted weights
        """
        # Start with base weights
        weights = dict(self.BASE_WEIGHTS)
        
        # Apply market phase adjustments
        phase_adjustments = self.PHASE_ADJUSTMENTS.get(market_phase, {})
        for dim, multiplier in phase_adjustments.items():
            if dim in weights:
                weights[dim] *= multiplier
        
        # Apply performance-based adjustments if provided
        if factor_scores:
            weights = self._apply_performance_adjustments(weights, factor_scores)
        
        # Normalize to ensure reasonable totals
        weights = self._normalize_weights(weights)
        
        # Build result
        result = MarketAdaptiveWeights(
            market_phase=market_phase,
            resonance_technical=weights["resonance_technical"],
            resonance_capital=weights["resonance_capital"],
            resonance_policy=weights["resonance_policy"],
            elliott_wave=weights["elliott_wave"],
            sector_rotation=weights["sector_rotation"],
            stock_tiering=weights["stock_tiering"],
            market_phase_weight=weights["market_phase"],
            cup_handle=weights["cup_handle"],
            adjusted_at=date.today(),
            adjustment_reason=f"Market phase: {market_phase}",
        )
        
        if factor_scores:
            result.adjustment_reason += " + Performance-based adjustment"
        
        return result
    
    def _apply_performance_adjustments(
        self,
        weights: dict[str, float],
        factor_scores: dict[str, float],
    ) -> dict[str, float]:
        """Adjust weights based on factor performance scores."""
        adjusted = dict(weights)
        
        # Map factor IDs to weight keys
        factor_to_weight = {
            "resonance_technical": "resonance_technical",
            "resonance_capital": "resonance_capital",
            "resonance_policy": "resonance_policy",
            "elliott_wave_position": "elliott_wave",
            "sector_rps": "sector_rotation",
            "stock_tier": "stock_tiering",
        }
        
        # Calculate average score
        avg_score = sum(factor_scores.values()) / len(factor_scores) if factor_scores else 50.0
        
        # Adjust weights: boost high performers, reduce low performers
        for factor_id, score in factor_scores.items():
            weight_key = factor_to_weight.get(factor_id)
            if weight_key and weight_key in adjusted:
                # Calculate adjustment: +10% for every 10 points above average
                adjustment = 1.0 + (score - avg_score) / 100.0
                adjusted[weight_key] *= adjustment
        
        return adjusted
    
    def _normalize_weights(self, weights: dict[str, float]) -> dict[str, float]:
        """Normalize weights to reasonable ranges."""
        normalized = {}
        
        # Cap individual weights
        for k, v in weights.items():
            normalized[k] = min(0.50, max(0.02, v))  # Min 2%, Max 50%
        
        return normalized
    
    def get_weight_recommendations(
        self,
        current_weights: MarketAdaptiveWeights,
        suggested_weights: MarketAdaptiveWeights,
    ) -> list[dict[str, Any]]:
        """Generate human-readable weight adjustment recommendations."""
        recommendations = []
        
        current = current_weights.to_dict()["weights"]
        suggested = suggested_weights.to_dict()["weights"]
        
        for dim, new_val in suggested.items():
            old_val = current.get(dim, 0)
            change = new_val - old_val
            change_pct = (change / old_val * 100) if old_val > 0 else 0
            
            if abs(change) > 0.02:  # Only significant changes
                recommendations.append({
                    "dimension": dim,
                    "current": round(old_val, 3),
                    "suggested": round(new_val, 3),
                    "change": round(change, 3),
                    "change_pct": round(change_pct, 1),
                    "action": "increase" if change > 0 else "decrease",
                })
        
        # Sort by absolute change
        recommendations.sort(key=lambda x: abs(x["change"]), reverse=True)
        
        return recommendations
