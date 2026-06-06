"""Data models for paper trading simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class TradeSide(str, Enum):
    """Trade direction."""
    BUY = "buy"
    SELL = "sell"


class TradeStatus(str, Enum):
    """Trade execution status."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionStatus(str, Enum):
    """Position status."""
    OPEN = "open"
    CLOSED = "closed"
    PARTIAL = "partial"  # Partially closed


@dataclass
class TradeRecord:
    """A simulated trade record."""
    trade_id: str
    strategy_id: str
    code: str
    name: str
    side: TradeSide
    quantity: int
    price: float
    amount: float  # Total trade amount
    trade_date: date
    status: TradeStatus
    
    # Optional fields
    signal_source: str = ""  # e.g., "cup_handle_lab", "quant_trading_lab"
    signal_reason: str = ""  # Why this trade was triggered
    related_position_id: str = ""
    
    # Execution details
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: datetime | None = None
    
    # Fees (simulated)
    commission: float = 0.0
    stamp_duty: float = 0.0  # 印花税（卖出时）
    
    @property
    def total_cost(self) -> float:
        """Total cost including fees."""
        return self.amount + self.commission + self.stamp_duty


@dataclass
class Position:
    """A simulated position."""
    position_id: str
    strategy_id: str
    code: str
    name: str
    
    # Entry info
    entry_date: date
    entry_price: float
    entry_quantity: int
    
    # Current state
    current_quantity: int
    current_price: float
    
    # Exit info (if closed)
    exit_date: date | None = None
    exit_price: float | None = None
    
    # P&L tracking
    realized_pnl: float = 0.0  # 已实现盈亏
    unrealized_pnl: float = 0.0  # 未实现盈亏
    
    # Status
    status: PositionStatus = PositionStatus.OPEN
    
    # Source
    entry_signal_source: str = ""
    entry_signal_reason: str = ""
    
    # Related trades
    trade_ids: list[str] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def cost_basis(self) -> float:
        """Total cost basis."""
        return self.entry_price * self.entry_quantity
    
    @property
    def market_value(self) -> float:
        """Current market value."""
        return self.current_price * self.current_quantity
    
    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl
    
    @property
    def total_pnl_pct(self) -> float:
        """Total P&L percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.total_pnl / self.cost_basis) * 100
    
    @property
    def holding_days(self) -> int:
        """Number of days held."""
        end_date = self.exit_date or date.today()
        return (end_date - self.entry_date).days
    
    def update_price(self, new_price: float) -> None:
        """Update current price and recalculate unrealized P&L."""
        self.current_price = new_price
        if self.status != PositionStatus.CLOSED:
            self.unrealized_pnl = (new_price - self.entry_price) * self.current_quantity
        self.updated_at = datetime.now()


@dataclass
class StrategyConfig:
    """Configuration for a paper trading strategy."""
    strategy_id: str
    strategy_name: str
    
    # Capital settings
    initial_capital: float = 1_000_000.0  # 初始资金 100万
    max_positions: int = 10  # 最大持仓数
    max_position_pct: float = 20.0  # 单票最大仓位 (%)
    
    # Risk settings
    stop_loss_pct: float = 8.0  # 止损线 (%)
    take_profit_pct: float = 20.0  # 止盈线 (%)
    
    # Entry rules
    min_resonance_score: float = 60.0  # 最低共振分
    preferred_tiers: list[str] = field(default_factory=lambda: ["leader", "core"])
    
    # Exit rules
    max_holding_days: int = 50  # 最大持仓天数
    
    # Signal sources
    signal_sources: list[str] = field(default_factory=lambda: ["cup_handle_lab", "quant_trading_lab"])
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "initial_capital": self.initial_capital,
            "max_positions": self.max_positions,
            "max_position_pct": self.max_position_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "min_resonance_score": self.min_resonance_score,
            "preferred_tiers": self.preferred_tiers,
            "max_holding_days": self.max_holding_days,
            "signal_sources": self.signal_sources,
        }


@dataclass
class PortfolioSnapshot:
    """Portfolio state at a point in time."""
    snapshot_date: date
    strategy_id: str
    
    # Capital
    cash: float
    total_value: float
    
    # Positions
    position_count: int
    open_positions: list[Position]
    
    # P&L
    daily_pnl: float
    total_pnl: float
    total_return_pct: float
    
    # Metrics
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "snapshot_date": self.snapshot_date.isoformat(),
            "strategy_id": self.strategy_id,
            "cash": self.cash,
            "total_value": self.total_value,
            "position_count": self.position_count,
            "open_positions": [
                {
                    "code": p.code,
                    "name": p.name,
                    "quantity": p.current_quantity,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.unrealized_pnl,
                    "unrealized_pnl_pct": (p.current_price - p.entry_price) / p.entry_price * 100 if p.entry_price else 0,
                    "holding_days": p.holding_days,
                }
                for p in self.open_positions
            ],
            "daily_pnl": self.daily_pnl,
            "total_pnl": self.total_pnl,
            "total_return_pct": self.total_return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
        }
