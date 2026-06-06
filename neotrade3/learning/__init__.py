"""Learning and self-evolution module for NeoTrade3.

自进化系统 - 因子发现、淘汰、权重自适应、参数优化
"""

from neotrade3.learning.factor_evolution import (
    Factor,
    FactorDiscovery,
    FactorPerformance,
    FactorStatus,
)
from neotrade3.learning.weight_adaptation import (
    MarketAdaptiveWeights,
    WeightAdaptationEngine,
)
from neotrade3.learning.evolution_report import (
    EvolutionReport,
    EvolutionReportGenerator,
)
from neotrade3.learning.pipeline import LearningLoopPipeline
from neotrade3.learning.models import EvaluationDecision

__all__ = [
    # Factor Evolution
    "Factor",
    "FactorDiscovery",
    "FactorPerformance",
    "FactorStatus",
    # Weight Adaptation
    "MarketAdaptiveWeights",
    "WeightAdaptationEngine",
    # Evolution Report
    "EvolutionReport",
    "EvolutionReportGenerator",
    # Learning Loop Pipeline (original)
    "EvaluationDecision",
    "LearningLoopPipeline",
]
