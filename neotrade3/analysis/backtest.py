"""Backtesting framework for NeoTrade3 signals.

信号回测框架 - 历史信号验证，客观评估策略有效性
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any


class ExitReason(str, Enum):
    """Reason for position exit."""
    STOP_LOSS = "stop_loss"           # 止损
    TAKE_PROFIT = "take_profit"       # 止盈
    TIME_EXIT = "time_exit"           # 时间退出
    SIGNAL_EXIT = "signal_exit"       # 反向信号
    END_OF_TEST = "end_of_test"       # 回测结束


@dataclass
class BacktestTrade:
    """A simulated trade in backtest."""
    code: str
    name: str
    entry_date: date
    entry_price: float
    exit_date: date | None = None
    exit_price: float | None = None
    quantity: int = 0
    
    # P&L
    realized_pnl: float = 0.0
    realized_pnl_pct: float = 0.0
    
    # Exit info
    exit_reason: ExitReason | None = None
    expected_return: dict[str, Any] = field(default_factory=dict)
    actual_holding_days: int = 0
    grade: str = "C"  # Signal grade at entry time (A/B/C)
    
    def close(self, exit_date: date, exit_price: float, reason: ExitReason) -> None:
        """Close the position."""
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.exit_reason = reason
        self.actual_holding_days = (exit_date - self.entry_date).days
        
        if self.entry_price > 0:
            self.realized_pnl = (exit_price - self.entry_price) * self.quantity
            self.realized_pnl_pct = ((exit_price - self.entry_price) / self.entry_price) * 100


@dataclass
class BacktestStatistics:
    """Statistics for a backtest run."""
    # Trade counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    
    # Win rate
    win_rate_pct: float = 0.0
    
    # Returns
    total_return_pct: float = 0.0
    avg_trade_return_pct: float = 0.0
    
    # Risk metrics
    max_drawdown_pct: float = 0.0
    max_consecutive_losses: int = 0
    
    # Advanced risk-adjusted metrics (NEW)
    sharpe_ratio: float = 0.0           # 夏普比率
    sortino_ratio: float = 0.0          # 索提诺比率
    calmar_ratio: float = 0.0           # 卡玛比率
    volatility_annual: float = 0.0      # 年化波动率 (%)
    
    # Benchmark comparison (NEW)
    benchmark_return_pct: float = 0.0   # 基准收益率 (%)
    alpha: float = 0.0                  # Alpha (超额收益)
    beta: float = 0.0                   # Beta (系统性风险)
    information_ratio: float = 0.0      # 信息比率
    
    # Profit metrics
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    profit_factor: float = 0.0
    
    # Trade characteristics
    avg_holding_days: float = 0.0
    avg_winner_return_pct: float = 0.0
    avg_loser_return_pct: float = 0.0
    largest_winner_pct: float = 0.0
    largest_loser_pct: float = 0.0
    
    # Expectation vs Reality
    expected_hit_rate: float = 0.0      # 预期达成率
    avg_expected_return: float = 0.0    # 平均预期收益
    avg_actual_return: float = 0.0      # 平均实际收益
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "trades": {
                "total": self.total_trades,
                "winning": self.winning_trades,
                "losing": self.losing_trades,
                "breakeven": self.breakeven_trades,
                "win_rate_pct": round(self.win_rate_pct, 2),
            },
            "returns": {
                "total_return_pct": round(self.total_return_pct, 2),
                "avg_trade_return_pct": round(self.avg_trade_return_pct, 2),
            },
            "risk": {
                "max_drawdown_pct": round(self.max_drawdown_pct, 2),
                "max_consecutive_losses": self.max_consecutive_losses,
                "sharpe_ratio": round(self.sharpe_ratio, 2),
                "sortino_ratio": round(self.sortino_ratio, 2),
                "calmar_ratio": round(self.calmar_ratio, 2),
                "volatility_annual_pct": round(self.volatility_annual, 2),
            },
            "benchmark": {
                "benchmark_return_pct": round(self.benchmark_return_pct, 2),
                "alpha": round(self.alpha, 2),
                "beta": round(self.beta, 2),
                "information_ratio": round(self.information_ratio, 2),
            },
            "profit": {
                "gross_profit": round(self.gross_profit, 2),
                "gross_loss": round(self.gross_loss, 2),
                "net_profit": round(self.net_profit, 2),
                "profit_factor": round(self.profit_factor, 2),
            },
            "trade_characteristics": {
                "avg_holding_days": round(self.avg_holding_days, 1),
                "avg_winner_return_pct": round(self.avg_winner_return_pct, 2),
                "avg_loser_return_pct": round(self.avg_loser_return_pct, 2),
                "largest_winner_pct": round(self.largest_winner_pct, 2),
                "largest_loser_pct": round(self.largest_loser_pct, 2),
            },
            "expectation_vs_reality": {
                "expected_hit_rate": round(self.expected_hit_rate, 2),
                "avg_expected_return": round(self.avg_expected_return, 2),
                "avg_actual_return": round(self.avg_actual_return, 2),
            },
        }


@dataclass
class GradeComparison:
    """Comparison between different signal grades."""
    grade: str
    statistics: BacktestStatistics
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "grade": self.grade,
            "statistics": self.statistics.to_dict(),
        }


@dataclass
class BacktestResult:
    """Complete backtest result."""
    start_date: date
    end_date: date
    initial_capital: float
    
    # Overall statistics
    overall_stats: BacktestStatistics
    
    # By grade comparison
    grade_comparisons: list[GradeComparison] = field(default_factory=list)
    
    # All trades
    trades: list[BacktestTrade] = field(default_factory=list)
    
    # Equity curve (for charting)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "period": {
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
                "trading_days": (self.end_date - self.start_date).days,
            },
            "initial_capital": self.initial_capital,
            "overall_statistics": self.overall_stats.to_dict(),
            "grade_comparison": [g.to_dict() for g in self.grade_comparisons],
            "trade_summary": [
                {
                    "code": t.code,
                    "name": t.name,
                    "entry_date": t.entry_date.isoformat(),
                    "exit_date": t.exit_date.isoformat() if t.exit_date else None,
                    "entry_price": round(t.entry_price, 2),
                    "exit_price": round(t.exit_price, 2) if t.exit_price else None,
                    "realized_pnl_pct": round(t.realized_pnl_pct, 2),
                    "exit_reason": t.exit_reason.value if t.exit_reason else None,
                    "holding_days": t.actual_holding_days,
                }
                for t in self.trades[:50]  # First 50 trades
            ],
            "total_trades": len(self.trades),
            "equity_curve_sample": self.equity_curve[:30] if self.equity_curve else [],
        }


class SignalBacktester:
    """Backtester for trading signals."""
    
    def __init__(
        self,
        db_path: str,
        initial_capital: float = 1_000_000.0,
        max_positions: int = 10,
        position_size_pct: float = 10.0,  # 每只票仓位 %
    ) -> None:
        self.db_path = db_path
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.position_size_pct = position_size_pct
    
    def run(
        self,
        start_date: date,
        end_date: date,
        min_grade: str = "C",
        codes: list[str] | None = None,
    ) -> BacktestResult:
        """Run backtest for a date range.
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            min_grade: Minimum signal grade (A/B/C)
            codes: Specific codes to test, or None for all candidates
            
        Returns:
            BacktestResult with complete statistics
        """
        from neotrade3.analysis.signal_generator import SignalGenerator, SignalGrade
        
        result = BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            overall_stats=BacktestStatistics(),
        )
        
        grade_map = {"A": SignalGrade.A, "B": SignalGrade.B, "C": SignalGrade.C}
        min_grade_enum = grade_map.get(min_grade.upper(), SignalGrade.C)
        
        # Generate signals for each trading day
        current_date = start_date
        open_positions: dict[str, BacktestTrade] = {}
        all_trades: list[BacktestTrade] = []
        equity_curve: list[dict[str, Any]] = []
        
        capital = self.initial_capital
        
        while current_date <= end_date:
            # Skip weekends (simplified)
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            # Check exit conditions for open positions
            capital += self._check_exits(
                current_date=current_date,
                open_positions=open_positions,
                all_trades=all_trades,
                capital=capital,
            )
            
            # Generate new signals for this date
            try:
                generator = SignalGenerator(db_path=self.db_path)
                signal_result = generator.generate(
                    codes=codes,
                    target_date=current_date,
                    min_grade=min_grade_enum,
                )
                
                # Process buy signals
                for signal in signal_result.signals:
                    if len(open_positions) >= self.max_positions:
                        break
                    
                    if signal.code in open_positions:
                        continue  # Already holding
                    
                    # Calculate position size
                    position_value = capital * (self.position_size_pct / 100)
                    quantity = int(position_value / signal.entry_price / 100) * 100
                    
                    if quantity < 100:
                        continue
                    
                    # Create trade
                    trade = BacktestTrade(
                        code=signal.code,
                        name=signal.name,
                        entry_date=current_date,
                        entry_price=signal.entry_price,
                        quantity=quantity,
                        expected_return=signal.expected_return.to_dict(),
                        grade=signal.grade.value if hasattr(signal.grade, 'value') else str(signal.grade),
                    )
                    
                    open_positions[signal.code] = trade
                    capital -= position_value  # Deduct capital
                    
            except Exception:
                pass  # Continue on error
            
            # Record equity
            current_equity = self._calculate_equity(
                capital=capital,
                open_positions=open_positions,
                current_date=current_date,
            )
            equity_curve.append({
                "date": current_date.isoformat(),
                "equity": round(current_equity, 2),
            })
            
            current_date += timedelta(days=1)
        
        # Close all remaining positions at end
        for code, trade in list(open_positions.items()):
            exit_price = self._get_price(code, end_date)
            if exit_price:
                trade.close(end_date, exit_price, ExitReason.END_OF_TEST)
                all_trades.append(trade)
                capital += trade.exit_price * trade.quantity if trade.exit_price else 0
        
        open_positions.clear()
        
        # Calculate statistics
        result.trades = all_trades
        result.equity_curve = equity_curve
        result.overall_stats = self._calculate_statistics(all_trades)
        
        # Compare by grade
        result.grade_comparisons = self._compare_by_grade(all_trades)
        
        return result
    
    def _check_exits(
        self,
        current_date: date,
        open_positions: dict[str, BacktestTrade],
        all_trades: list[BacktestTrade],
        capital: float,
    ) -> float:
        """Check and execute exits for open positions, returning released cash."""
        released_capital = 0.0
        for code, trade in list(open_positions.items()):
            current_price = self._get_price(code, current_date)
            if not current_price:
                continue
            
            # Get signal info (we stored expected return in trade)
            expected = trade.expected_return
            tp1 = expected.get("base_pct", 10) if expected else 10
            
            # Calculate current return
            current_return = ((current_price - trade.entry_price) / trade.entry_price) * 100
            
            # Check stop loss (-8%)
            if current_return <= -8:
                trade.close(current_date, current_price, ExitReason.STOP_LOSS)
                all_trades.append(trade)
                released_capital += current_price * trade.quantity
                del open_positions[code]
                continue
            
            # Check take profit (base target)
            if current_return >= tp1:
                trade.close(current_date, current_price, ExitReason.TAKE_PROFIT)
                all_trades.append(trade)
                released_capital += current_price * trade.quantity
                del open_positions[code]
                continue
            
            # Check time exit (max 50 days)
            holding_days = (current_date - trade.entry_date).days
            if holding_days >= 50:
                trade.close(current_date, current_price, ExitReason.TIME_EXIT)
                all_trades.append(trade)
                released_capital += current_price * trade.quantity
                del open_positions[code]
                continue
        return released_capital
    
    def _get_price(self, code: str, target_date: date) -> float | None:
        """Get closing price for a stock on a date."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?",
                (code, target_date.isoformat()),
            ).fetchone()
            return row[0] if row else None
    
    def _calculate_equity(
        self,
        capital: float,
        open_positions: dict[str, BacktestTrade],
        current_date: date,
    ) -> float:
        """Calculate current equity (cash + positions)."""
        equity = capital
        for code, trade in open_positions.items():
            price = self._get_price(code, current_date)
            if price:
                equity += price * trade.quantity
            else:
                equity += trade.entry_price * trade.quantity
        return equity
    
    def _calculate_statistics(self, trades: list[BacktestTrade]) -> BacktestStatistics:
        """Calculate statistics from trades."""
        stats = BacktestStatistics()
        
        if not trades:
            return stats
        
        stats.total_trades = len(trades)
        
        returns = []
        holding_days = []
        consecutive_losses = 0
        max_consecutive = 0
        
        for trade in trades:
            ret = trade.realized_pnl_pct
            returns.append(ret)
            holding_days.append(trade.actual_holding_days)
            
            if ret > 0.5:
                stats.winning_trades += 1
                stats.gross_profit += trade.realized_pnl
                consecutive_losses = 0
                if ret > stats.largest_winner_pct:
                    stats.largest_winner_pct = ret
            elif ret < -0.5:
                stats.losing_trades += 1
                stats.gross_loss += abs(trade.realized_pnl)
                consecutive_losses += 1
                if consecutive_losses > max_consecutive:
                    max_consecutive = consecutive_losses
                if ret < stats.largest_loser_pct:
                    stats.largest_loser_pct = ret
            else:
                stats.breakeven_trades += 1
                consecutive_losses = 0
        
        stats.max_consecutive_losses = max_consecutive
        
        # Win rate
        if stats.total_trades > 0:
            stats.win_rate_pct = (stats.winning_trades / stats.total_trades) * 100
        
        # Returns
        if returns:
            stats.avg_trade_return_pct = sum(returns) / len(returns)
            stats.total_return_pct = sum(returns)
        
        # Profit factor
        if stats.gross_loss > 0:
            stats.profit_factor = stats.gross_profit / stats.gross_loss
        elif stats.gross_profit > 0:
            stats.profit_factor = float('inf')
        
        # Holding days
        if holding_days:
            stats.avg_holding_days = sum(holding_days) / len(holding_days)
        
        # Winner/Loser averages
        winner_returns = [r for r in returns if r > 0.5]
        loser_returns = [r for r in returns if r < -0.5]
        
        if winner_returns:
            stats.avg_winner_return_pct = sum(winner_returns) / len(winner_returns)
        if loser_returns:
            stats.avg_loser_return_pct = sum(loser_returns) / len(loser_returns)
        
        # Calculate max drawdown from equity curve
        stats.max_drawdown_pct = self._calculate_max_drawdown_from_trades(trades)
        
        # Expected vs Actual
        expected_returns = []
        for trade in trades:
            if trade.expected_return:
                exp = trade.expected_return.get("base_pct", 0)
                expected_returns.append(exp)
                if trade.realized_pnl_pct >= exp * 0.8:  # Within 80% of target
                    stats.expected_hit_rate += 1
        
        if expected_returns:
            stats.avg_expected_return = sum(expected_returns) / len(expected_returns)
            stats.expected_hit_rate = (stats.expected_hit_rate / len(trades)) * 100
        
        if returns:
            stats.avg_actual_return = sum(returns) / len(returns)
        
        stats.net_profit = stats.gross_profit - stats.gross_loss
        
        # Calculate advanced risk metrics (NEW)
        if returns:
            stats.sharpe_ratio = self._calculate_sharpe_ratio(returns)
            stats.sortino_ratio = self._calculate_sortino_ratio(returns)
            stats.volatility_annual = self._calculate_annual_volatility(returns)
        
        if stats.max_drawdown_pct > 0:
            stats.calmar_ratio = abs(stats.total_return_pct) / stats.max_drawdown_pct
        
        return stats
    
    def _calculate_sharpe_ratio(self, returns: list[float], risk_free_rate: float = 0.03) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance ** 0.5
        if std_dev == 0:
            return 0.0
        # Assume ~20 trading days per month for annualization
        return ((avg_return - risk_free_rate / 20) / std_dev) * (20 ** 0.5)
    
    def _calculate_sortino_ratio(self, returns: list[float], risk_free_rate: float = 0.03) -> float:
        """Calculate annualized Sortino ratio (downside deviation only)."""
        if len(returns) < 2:
            return 0.0
        avg_return = sum(returns) / len(returns)
        downside_returns = [r for r in returns if r < 0]
        if not downside_returns:
            return float('inf') if avg_return > 0 else 0.0
        downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
        downside_std = downside_variance ** 0.5
        if downside_std == 0:
            return 0.0
        return ((avg_return - risk_free_rate / 20) / downside_std) * (20 ** 0.5)
    
    def _calculate_annual_volatility(self, returns: list[float]) -> float:
        """Calculate annualized volatility (%)."""
        if len(returns) < 2:
            return 0.0
        variance = sum((r - sum(returns) / len(returns)) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance ** 0.5
        # Annualize assuming ~20 trades per month, 12 months
        return std_dev * (240 ** 0.5)
    
    def _calculate_max_drawdown_from_trades(self, trades: list[BacktestTrade]) -> float:
        """Calculate max drawdown from trade sequence."""
        if not trades:
            return 0.0
        
        # Simplified: calculate from cumulative returns
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        
        for trade in trades:
            cumulative += trade.realized_pnl_pct
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def _compare_by_grade(self, trades: list[BacktestTrade]) -> list[GradeComparison]:
        """Compare statistics by signal grade."""
        from collections import defaultdict

        grade_groups: dict[str, list[BacktestTrade]] = defaultdict(list)
        for trade in trades:
            grade_groups[trade.grade].append(trade)

        comparisons: list[GradeComparison] = []
        for grade in ("A", "B", "C"):
            group = grade_groups.get(grade, [])
            if not group:
                continue
            stats = self._calculate_statistics(group)
            comparisons.append(GradeComparison(grade=grade, statistics=stats))

        return comparisons
