"""Paper trading simulation module for NeoTrade3.

模拟交易实验室 - 虚拟持仓管理、交易信号执行、绩效分析
"""

from neotrade3.labs.paper_trading.analytics import AnalyticsCalculator, PerformanceAnalytics, TradeStatistics
from neotrade3.labs.paper_trading.engine import PaperTradingEngine, SignalType, TradeAction
from neotrade3.labs.paper_trading.models import (
    Position,
    PositionStatus,
    StrategyConfig,
    TradeRecord,
    TradeSide,
    TradeStatus,
)
from neotrade3.labs.paper_trading.portfolio import PortfolioManager

__all__ = [
    # Models
    "Position",
    "PositionStatus",
    "TradeRecord",
    "TradeSide",
    "TradeStatus",
    "StrategyConfig",
    # Portfolio
    "PortfolioManager",
    # Engine
    "PaperTradingEngine",
    "SignalType",
    "TradeAction",
    # Analytics
    "AnalyticsCalculator",
    "PerformanceAnalytics",
    "TradeStatistics",
]
