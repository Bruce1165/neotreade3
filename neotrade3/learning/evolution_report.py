"""Evolution report generator for NeoTrade3 self-evolution.

进化报告生成器 - 生成可解释的自进化报告
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from neotrade3.learning.factor_evolution import FactorDiscovery
from neotrade3.learning.weight_adaptation import WeightAdaptationEngine


@dataclass
class EvolutionAction:
    """A single evolution action taken."""
    action_type: str  # "factor_promoted", "factor_deprecated", "weight_adjusted", "new_factor"
    target: str
    reason: str
    before_value: Any | None = None
    after_value: Any | None = None
    confidence: float = 0.0


@dataclass
class EvolutionReport:
    """Complete evolution report."""
    report_id: str
    generation_date: date
    evaluation_period_start: date
    evaluation_period_end: date
    
    # Summary
    total_factors_evaluated: int = 0
    factors_promoted: int = 0
    factors_deprecated: int = 0
    new_factors_discovered: int = 0
    weight_adjustments_made: int = 0
    
    # Details
    actions: list[EvolutionAction] = field(default_factory=list)
    factor_summary: dict[str, Any] = field(default_factory=dict)
    weight_recommendations: list[dict[str, Any]] = field(default_factory=list)
    
    # Next steps
    recommended_actions: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generation_date": self.generation_date.isoformat(),
            "evaluation_period": {
                "start": self.evaluation_period_start.isoformat(),
                "end": self.evaluation_period_end.isoformat(),
            },
            "summary": {
                "total_factors_evaluated": self.total_factors_evaluated,
                "factors_promoted": self.factors_promoted,
                "factors_deprecated": self.factors_deprecated,
                "new_factors_discovered": self.new_factors_discovered,
                "weight_adjustments_made": self.weight_adjustments_made,
            },
            "actions": [
                {
                    "type": a.action_type,
                    "target": a.target,
                    "reason": a.reason,
                    "before": a.before_value,
                    "after": a.after_value,
                    "confidence": round(a.confidence, 1),
                }
                for a in self.actions
            ],
            "factor_summary": self.factor_summary,
            "weight_recommendations": self.weight_recommendations,
            "recommended_next_steps": self.recommended_actions,
        }


class EvolutionReportGenerator:
    """Generator for evolution reports."""
    
    def __init__(
        self,
        db_path: str,
        factors_storage_path: str | None = None,
    ) -> None:
        self.db_path = db_path
        self.factors_storage_path = factors_storage_path
    
    def generate(
        self,
        start_date: date,
        end_date: date,
        market_phase: str,
    ) -> EvolutionReport:
        """Generate a complete evolution report.
        
        Args:
            start_date: Evaluation period start
            end_date: Evaluation period end
            market_phase: Current market phase
            
        Returns:
            EvolutionReport with all findings and recommendations
        """
        report = EvolutionReport(
            report_id=f"evolution_{end_date.isoformat()}",
            generation_date=date.today(),
            evaluation_period_start=start_date,
            evaluation_period_end=end_date,
        )
        
        # Step 1: Evaluate all factors
        factor_discovery = FactorDiscovery(
            db_path=self.db_path,
            factors_storage_path=self.factors_storage_path,
        )
        
        evaluation_results = factor_discovery.evaluate_all_factors(start_date, end_date)
        report.total_factors_evaluated = len(evaluation_results)
        
        # Track factor status changes
        for factor_id, performance in evaluation_results.items():
            factor = factor_discovery.factors.get(factor_id)
            if not factor:
                continue
            
            # Check for promotion
            if factor.status.value == "active" and factor.evaluation_count == 1:
                report.factors_promoted += 1
                report.actions.append(EvolutionAction(
                    action_type="factor_promoted",
                    target=factor.name,
                    reason=f"Score improved to {factor.current_score:.1f}, exceeding active threshold",
                    after_value=factor.current_score,
                    confidence=performance.hit_rate,
                ))
            
            # Check for deprecation
            if factor.status.value == "deprecated":
                report.factors_deprecated += 1
                report.actions.append(EvolutionAction(
                    action_type="factor_deprecated",
                    target=factor.name,
                    reason=f"Score dropped to {factor.current_score:.1f}, below deprecation threshold",
                    before_value=factor.current_score + 15,  # Approximate
                    after_value=factor.current_score,
                    confidence=100 - performance.consistency_score,
                ))
        
        # Step 2: Discover new factors
        new_factors = factor_discovery.discover_new_factors(start_date, end_date)
        report.new_factors_discovered = len(new_factors)
        
        for new_factor in new_factors:
            report.actions.append(EvolutionAction(
                action_type="new_factor",
                target=new_factor.name,
                reason=f"New {new_factor.category} factor discovered from data analysis",
                after_value=new_factor.parameters,
                confidence=50.0,  # New factors start with medium confidence
            ))
        
        # Step 3: Adapt weights
        weight_engine = WeightAdaptationEngine(db_path=self.db_path)
        
        # Get factor scores for performance-based adjustment
        factor_scores = {
            fid: factor.current_score
            for fid, factor in factor_discovery.factors.items()
            if factor.status.value in ("active", "candidate")
        }
        
        suggested_weights = weight_engine.adapt_weights(
            market_phase=market_phase,
            factor_scores=factor_scores,
        )
        
        # Compare with current weights (simplified - would load from config)
        from neotrade3.learning.weight_adaptation import MarketAdaptiveWeights
        current_weights = MarketAdaptiveWeights(market_phase=market_phase)
        
        weight_recommendations = weight_engine.get_weight_recommendations(
            current_weights=current_weights,
            suggested_weights=suggested_weights,
        )
        
        report.weight_recommendations = weight_recommendations
        report.weight_adjustments_made = len(weight_recommendations)
        
        for rec in weight_recommendations:
            report.actions.append(EvolutionAction(
                action_type="weight_adjusted",
                target=rec["dimension"],
                reason=f"{rec['action'].capitalize()} weight based on {market_phase} market conditions",
                before_value=rec["current"],
                after_value=rec["suggested"],
                confidence=abs(rec["change_pct"]),
            ))
        
        # Step 4: Generate factor summary
        report.factor_summary = factor_discovery.get_evolution_summary()
        
        # Step 5: Generate recommendations
        report.recommended_actions = self._generate_recommendations(
            report=report,
            market_phase=market_phase,
        )
        
        return report
    
    def _generate_recommendations(
        self,
        report: EvolutionReport,
        market_phase: str,
    ) -> list[str]:
        """Generate recommended next actions."""
        recommendations = []
        
        # Factor-related recommendations
        if report.factors_deprecated > 0:
            recommendations.append(
                f"Review {report.factors_deprecated} deprecated factor(s) for potential revival or permanent removal"
            )
        
        if report.new_factors_discovered > 0:
            recommendations.append(
                f"Monitor {report.new_factors_discovered} new factor(s) during candidate observation period (30 days)"
            )
        
        under_review = report.factor_summary.get("factors_for_review", [])
        if under_review:
            recommendations.append(
                f"Pay attention to {len(under_review)} factor(s) under review - may need manual intervention"
            )
        
        # Weight-related recommendations
        if report.weight_adjustments_made > 0:
            significant_changes = [
                r for r in report.weight_recommendations
                if abs(r["change"]) > 0.05
            ]
            if significant_changes:
                recommendations.append(
                    f"Consider applying {len(significant_changes)} significant weight adjustment(s) to signal generator"
                )
        
        # Market phase specific
        if market_phase == "bear":
            recommendations.append(
                "Bear market detected: Consider increasing cash position and being more selective with signals"
            )
        elif market_phase == "bull":
            recommendations.append(
                "Bull market detected: Good opportunity to increase position sizes and capture trend"
            )
        
        # General recommendations
        avg_score = report.factor_summary.get("average_score", 50)
        if avg_score < 55:
            recommendations.append(
                f"Overall factor health is low ({avg_score:.1f}) - consider reviewing evaluation methodology"
            )
        
        recommendations.append(
            f"Schedule next evolution evaluation after {self._get_next_evaluation_date()}"
        )
        
        return recommendations
    
    def _get_next_evaluation_date(self) -> str:
        """Calculate next recommended evaluation date."""
        # Monthly evaluation recommended
        from datetime import timedelta
        next_date = date.today() + timedelta(days=30)
        return next_date.isoformat()
