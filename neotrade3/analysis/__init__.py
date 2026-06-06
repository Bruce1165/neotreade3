"""Analysis module for NeoTrade3 - market analysis, stock tiering, and scoring."""

from neotrade3.analysis.market_phase import (
    MarketPhase,
    MarketPhaseResult,
    detect_market_phase,
)
from neotrade3.analysis.pools import (
    PoolManager,
    PoolMember,
    PoolSnapshot,
    PoolStatus,
)
from neotrade3.analysis.resonance_scorer import (
    ResonanceResult,
    ResonanceScorer,
    ResonanceWeights,
    SubScores,
)
from neotrade3.analysis.sector_rotation import (
    POLICY_MAINLINE_SECTORS,
    SectorRotationAnalyzer,
    SectorRotationResult,
    SectorRPS,
    StockRPS,
)
from neotrade3.analysis.elliott_wave import (
    ElliottWaveAnalyzer,
    ElliottWaveResult,
    Wave,
    WaveDirection,
    WavePosition,
    WaveSequence,
    WaveTradingSignal,
    WaveType,
)
from neotrade3.analysis.signal_generator import (
    DimensionScore,
    ExpectedReturn,
    SignalDirection,
    SignalGrade,
    SignalGenerationResult,
    SignalGenerator,
    SignalSource,
    TradingSignal,
)
from neotrade3.analysis.backtest import (
    BacktestResult,
    BacktestStatistics,
    BacktestTrade,
    ExitReason,
    GradeComparison,
    SignalBacktester,
)
from neotrade3.analysis.stock_tiering import (
    SectorTieringResult,
    StockTier,
    StockTieringAnalyzer,
    StockTieringResult,
    StockTierMetrics,
    TieredStock,
)
from neotrade3.analysis.factor_matrix import FactorMatrixBuilder

__all__ = [
    # Market phase
    "MarketPhase",
    "MarketPhaseResult",
    "detect_market_phase",
    # Pools
    "PoolManager",
    "PoolMember",
    "PoolSnapshot",
    "PoolStatus",
    # Resonance scorer
    "ResonanceResult",
    "ResonanceScorer",
    "ResonanceWeights",
    "SubScores",
    # Sector rotation
    "POLICY_MAINLINE_SECTORS",
    "SectorRotationAnalyzer",
    "SectorRotationResult",
    "SectorRPS",
    "StockRPS",
    # Stock tiering
    "SectorTieringResult",
    "StockTier",
    "StockTieringAnalyzer",
    "StockTieringResult",
    "StockTierMetrics",
    "TieredStock",
    # Elliott Wave
    "ElliottWaveAnalyzer",
    "ElliottWaveResult",
    "Wave",
    "WaveDirection",
    "WavePosition",
    "WaveSequence",
    "WaveTradingSignal",
    "WaveType",
    # Signal Generator
    "DimensionScore",
    "ExpectedReturn",
    "SignalDirection",
    "SignalGrade",
    "SignalGenerationResult",
    "SignalGenerator",
    "SignalSource",
    "TradingSignal",
    # Backtest
    "BacktestResult",
    "BacktestStatistics",
    "BacktestTrade",
    "ExitReason",
    "GradeComparison",
    "SignalBacktester",
    # Factor Matrix
    "FactorMatrixBuilder",
]
