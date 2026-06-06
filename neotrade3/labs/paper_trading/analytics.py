"""Performance analytics for paper trading simulation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from neotrade3.labs.paper_trading.models import Position, PositionStatus, TradeRecord


@dataclass
class TradeStatistics:
    """Statistics for a single trade."""
    trade_id: str
    code: str
    entry_date: date
    exit_date: date | None
    entry_price: float
    exit_price: float | None
    quantity: int
    realized_pnl: float
    return_pct: float
    holding_days: int
    exit_reason: str


@dataclass
class PerformanceAnalytics:
    """Performance analytics for a strategy."""
    strategy_id: str
    analysis_date: date

    # Overall performance
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # P&L
    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    # Returns
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0

    # Risk metrics
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate_pct: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return_pct: float = 0.0

    # Trade statistics
    avg_holding_days: float = 0.0
    avg_winner_return_pct: float = 0.0
    avg_loser_return_pct: float = 0.0
    largest_winner_pct: float = 0.0
    largest_loser_pct: float = 0.0

    # Current positions
    open_positions: list[Position] = field(default_factory=list)
    open_positions_count: int = 0

    # Recent trades
    recent_trades: list[TradeStatistics] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strategy_id": self.strategy_id,
            "analysis_date": self.analysis_date.isoformat(),
            "summary": {
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "win_rate_pct": round(self.win_rate_pct, 2),
                "total_return_pct": round(self.total_return_pct, 2),
                "annualized_return_pct": round(self.annualized_return_pct, 2),
                "max_drawdown_pct": round(self.max_drawdown_pct, 2),
                "sharpe_ratio": round(self.sharpe_ratio, 2),
                "profit_factor": round(self.profit_factor, 2),
            },
            "pnl": {
                "total_realized_pnl": round(self.total_realized_pnl, 2),
                "total_unrealized_pnl": round(self.total_unrealized_pnl, 2),
                "gross_profit": round(self.gross_profit, 2),
                "gross_loss": round(self.gross_loss, 2),
            },
            "trade_stats": {
                "avg_trade_return_pct": round(self.avg_trade_return_pct, 2),
                "avg_holding_days": round(self.avg_holding_days, 1),
                "avg_winner_return_pct": round(self.avg_winner_return_pct, 2),
                "avg_loser_return_pct": round(self.avg_loser_return_pct, 2),
                "largest_winner_pct": round(self.largest_winner_pct, 2),
                "largest_loser_pct": round(self.largest_loser_pct, 2),
            },
            "open_positions": {
                "count": self.open_positions_count,
                "positions": [
                    {
                        "code": p.code,
                        "name": p.name,
                        "entry_date": p.entry_date.isoformat(),
                        "entry_price": p.entry_price,
                        "current_price": p.current_price,
                        "unrealized_pnl": round(p.unrealized_pnl, 2),
                        "unrealized_pnl_pct": round((p.current_price - p.entry_price) / p.entry_price * 100, 2) if p.entry_price else 0,
                        "holding_days": p.holding_days,
                    }
                    for p in self.open_positions
                ],
            },
            "recent_trades": [
                {
                    "code": t.code,
                    "entry_date": t.entry_date.isoformat(),
                    "exit_date": t.exit_date.isoformat() if t.exit_date else None,
                    "realized_pnl": round(t.realized_pnl, 2),
                    "return_pct": round(t.return_pct, 2),
                    "holding_days": t.holding_days,
                    "exit_reason": t.exit_reason,
                }
                for t in self.recent_trades[:10]  # Last 10 trades
            ],
        }


class AnalyticsCalculator:
    """Calculator for performance analytics."""

    def __init__(self, db_path: str | Path, strategy_id: str) -> None:
        self.db_path = Path(db_path)
        self.strategy_id = strategy_id

    def calculate(
        self,
        analysis_date: date | None = None,
        lookback_days: int = 365,
    ) -> PerformanceAnalytics:
        """Calculate performance analytics."""
        if analysis_date is None:
            analysis_date = date.today()

        start_date = analysis_date - timedelta(days=lookback_days)

        analytics = PerformanceAnalytics(
            strategy_id=self.strategy_id,
            analysis_date=analysis_date,
        )

        # Get closed positions (completed trades)
        closed_positions = self._get_closed_positions(start_date, analysis_date)

        # Calculate trade statistics
        if closed_positions:
            analytics.total_trades = len(closed_positions)

            returns = []
            holding_days = []

            for pos in closed_positions:
                trade_return = pos.total_pnl_pct
                returns.append(trade_return)
                holding_days.append(pos.holding_days)

                if trade_return > 0:
                    analytics.winning_trades += 1
                    analytics.gross_profit += pos.realized_pnl
                    if trade_return > analytics.largest_winner_pct:
                        analytics.largest_winner_pct = trade_return
                else:
                    analytics.losing_trades += 1
                    analytics.gross_loss += abs(pos.realized_pnl)
                    if trade_return < analytics.largest_loser_pct:
                        analytics.largest_loser_pct = trade_return

                analytics.total_realized_pnl += pos.realized_pnl

            # Calculate averages
            if analytics.total_trades > 0:
                analytics.win_rate_pct = (analytics.winning_trades / analytics.total_trades) * 100
                analytics.avg_trade_return_pct = sum(returns) / len(returns)
                analytics.avg_holding_days = sum(holding_days) / len(holding_days)

            if analytics.winning_trades > 0:
                winner_returns = [r for r in returns if r > 0]
                analytics.avg_winner_return_pct = sum(winner_returns) / len(winner_returns)

            if analytics.losing_trades > 0:
                loser_returns = [r for r in returns if r <= 0]
                analytics.avg_loser_return_pct = sum(loser_returns) / len(loser_returns)

            if analytics.gross_loss > 0:
                analytics.profit_factor = analytics.gross_profit / analytics.gross_loss

        # Get open positions
        analytics.open_positions = self._get_open_positions()
        analytics.open_positions_count = len(analytics.open_positions)
        analytics.total_unrealized_pnl = sum(p.unrealized_pnl for p in analytics.open_positions)

        # Get recent trades
        analytics.recent_trades = self._get_recent_trades(20)

        # Calculate total return
        total_pnl = analytics.total_realized_pnl + analytics.total_unrealized_pnl
        initial_capital = self._get_initial_capital()
        if initial_capital > 0:
            analytics.total_return_pct = (total_pnl / initial_capital) * 100
            analytics.annualized_return_pct = self._calculate_annualized_return(
                analytics.total_return_pct, lookback_days
            )

        # Calculate max drawdown from snapshots
        analytics.max_drawdown_pct = self._calculate_max_drawdown(start_date, analysis_date)

        # Calculate Sharpe ratio (simplified)
        analytics.sharpe_ratio = self._calculate_sharpe_ratio(start_date, analysis_date)

        return analytics

    def _get_closed_positions(
        self,
        start_date: date,
        end_date: date,
    ) -> list[Position]:
        """Get closed positions within date range."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM positions
                WHERE strategy_id = ? AND status = 'closed'
                AND entry_date >= ? AND entry_date <= ?
                ORDER BY entry_date DESC
                """,
                (self.strategy_id, start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
            return [self._row_to_position(row) for row in rows]

    def _get_open_positions(self) -> list[Position]:
        """Get current open positions."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM positions
                WHERE strategy_id = ? AND status IN ('open', 'partial')
                ORDER BY entry_date DESC
                """,
                (self.strategy_id,),
            ).fetchall()
            return [self._row_to_position(row) for row in rows]

    def _get_recent_trades(self, limit: int = 10) -> list[TradeStatistics]:
        """Get recent trade statistics."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT t.*, p.entry_date as pos_entry_date, p.entry_price as pos_entry_price
                FROM trades t
                LEFT JOIN positions p ON t.related_position_id = p.position_id
                WHERE t.strategy_id = ? AND t.side = 'sell' AND t.status = 'filled'
                ORDER BY t.trade_date DESC
                LIMIT ?
                """,
                (self.strategy_id, limit),
            ).fetchall()

            trades = []
            for row in rows:
                entry_date = (
                    date.fromisoformat(row["pos_entry_date"])
                    if row["pos_entry_date"]
                    else date.fromisoformat(row["trade_date"])
                )
                exit_date = date.fromisoformat(row["trade_date"])
                entry_price = row["pos_entry_price"] or row["price"]
                exit_price = row["price"]
                quantity = row["quantity"]

                realized_pnl = (exit_price - entry_price) * quantity if entry_price else 0
                return_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price else 0
                holding_days = (exit_date - entry_date).days

                trades.append(
                    TradeStatistics(
                        trade_id=row["trade_id"],
                        code=row["code"],
                        entry_date=entry_date,
                        exit_date=exit_date,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        quantity=quantity,
                        realized_pnl=realized_pnl,
                        return_pct=return_pct,
                        holding_days=holding_days,
                        exit_reason=row["signal_reason"] or "",
                    )
                )
            return trades

    def _get_initial_capital(self) -> float:
        """Get initial capital from strategy config."""
        # This would typically come from config stored in DB
        # For now, return default
        return 1_000_000.0

    def _calculate_annualized_return(
        self,
        total_return_pct: float,
        days: int,
    ) -> float:
        """Calculate annualized return."""
        if days <= 0:
            return 0.0
        # (1 + r)^(365/days) - 1
        total_return = total_return_pct / 100
        annualized = ((1 + total_return) ** (365 / days)) - 1
        return annualized * 100

    def _calculate_max_drawdown(
        self,
        start_date: date,
        end_date: date,
    ) -> float:
        """Calculate maximum drawdown from portfolio snapshots."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT total_value FROM portfolio_snapshots
                WHERE strategy_id = ? AND snapshot_date >= ? AND snapshot_date <= ?
                ORDER BY snapshot_date ASC
                """,
                (self.strategy_id, start_date.isoformat(), end_date.isoformat()),
            ).fetchall()

            if not rows:
                return 0.0

            values = [row[0] for row in rows]
            peak = values[0]
            max_dd = 0.0

            for value in values:
                if value > peak:
                    peak = value
                dd = (peak - value) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd

            return max_dd * 100

    def _calculate_sharpe_ratio(
        self,
        start_date: date,
        end_date: date,
    ) -> float:
        """Calculate simplified Sharpe ratio from daily returns."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT total_value FROM portfolio_snapshots
                WHERE strategy_id = ? AND snapshot_date >= ? AND snapshot_date <= ?
                ORDER BY snapshot_date ASC
                """,
                (self.strategy_id, start_date.isoformat(), end_date.isoformat()),
            ).fetchall()

            if len(rows) < 2:
                return 0.0

            values = [row[0] for row in rows]
            returns = []
            for i in range(1, len(values)):
                if values[i - 1] > 0:
                    daily_return = (values[i] - values[i - 1]) / values[i - 1]
                    returns.append(daily_return)

            if not returns:
                return 0.0

            avg_return = sum(returns) / len(returns)
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            std_dev = variance ** 0.5

            if std_dev == 0:
                return 0.0

            # Annualized Sharpe (assuming 252 trading days)
            # Using risk-free rate of 0 for simplicity
            sharpe = (avg_return / std_dev) * (252 ** 0.5)
            return sharpe

    def _row_to_position(self, row: sqlite3.Row) -> Position:
        """Convert database row to Position object."""
        return Position(
            position_id=row["position_id"],
            strategy_id=row["strategy_id"],
            code=row["code"],
            name=row["name"] or "",
            entry_date=date.fromisoformat(row["entry_date"]),
            entry_price=row["entry_price"],
            entry_quantity=row["entry_quantity"],
            current_quantity=row["current_quantity"],
            current_price=row["current_price"],
            exit_date=date.fromisoformat(row["exit_date"]) if row["exit_date"] else None,
            exit_price=row["exit_price"],
            realized_pnl=row["realized_pnl"] or 0,
            unrealized_pnl=row["unrealized_pnl"] or 0,
            status=PositionStatus(row["status"]),
            entry_signal_source=row["entry_signal_source"] or "",
            entry_signal_reason=row["entry_signal_reason"] or "",
            trade_ids=[],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
