"""Trading engine for paper trading simulation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from neotrade3.labs.paper_trading.models import (
    Position,
    PositionStatus,
    StrategyConfig,
    TradeRecord,
    TradeSide,
    TradeStatus,
)
from neotrade3.labs.paper_trading.portfolio import PortfolioManager


class SignalType(str, Enum):
    """Trading signal type."""
    BUY = "buy"
    SELL = "sell"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TIME_EXIT = "time_exit"


@dataclass
class TradeAction:
    """A trade action to be executed."""
    code: str
    name: str
    side: TradeSide
    quantity: int
    price: float
    signal_type: SignalType
    signal_source: str
    signal_reason: str


class PaperTradingEngine:
    """Trading engine that converts signals to trades."""

    def __init__(
        self,
        portfolio_manager: PortfolioManager,
        market_data_source: Path | None = None,
    ) -> None:
        self.portfolio = portfolio_manager
        self.config = portfolio_manager.config
        self.market_data_source = market_data_source

    def process_signals(
        self,
        signals: list[dict[str, Any]],
        trade_date: date,
    ) -> list[TradeRecord]:
        """Process trading signals and execute trades.

        Args:
            signals: List of signal dicts with keys: code, name, signal_type,
                     source, reason, score, tier, etc.
            trade_date: Date to execute trades

        Returns:
            List of executed trade records
        """
        executed_trades: list[TradeRecord] = []

        for signal in signals:
            action = self._signal_to_action(signal, trade_date)
            if action:
                trade = self._execute_action(action, trade_date)
                if trade:
                    executed_trades.append(trade)

        return executed_trades

    def _signal_to_action(
        self,
        signal: dict[str, Any],
        trade_date: date,
    ) -> TradeAction | None:
        """Convert a signal to a trade action."""
        code = signal.get("code", "")
        name = signal.get("name", "")
        signal_type = signal.get("signal_type", "")
        source = signal.get("source", "")
        reason = signal.get("reason", "")
        score = signal.get("score", 0)
        tier = signal.get("tier", "")

        if not code:
            return None

        # Get current price
        price = self._get_current_price(code, trade_date)
        if not price or price <= 0:
            return None

        # Check entry rules for buy signals
        if signal_type in ["buy", "entry"]:
            # Check if already have position
            existing = self.portfolio.get_position(code)
            if existing:
                return None  # Already holding

            # Check tier preference
            if tier and tier not in self.config.preferred_tiers:
                return None

            # Check resonance score
            if score < self.config.min_resonance_score:
                return None

            # Check position limit
            open_positions = self.portfolio.get_open_positions()
            if len(open_positions) >= self.config.max_positions:
                return None

            # Calculate position size
            portfolio_value = self.portfolio.get_portfolio_value()
            max_position_value = portfolio_value * (self.config.max_position_pct / 100)
            position_value = min(max_position_value, portfolio_value * 0.1)  # Max 10% per trade

            # Check cash available
            cash = self.portfolio.get_cash()
            if cash < position_value * 0.95:  # Need some buffer
                return None

            quantity = int(position_value / price / 100) * 100  # Round to 100 shares
            if quantity < 100:
                return None

            return TradeAction(
                code=code,
                name=name,
                side=TradeSide.BUY,
                quantity=quantity,
                price=price,
                signal_type=SignalType.BUY,
                signal_source=source,
                signal_reason=reason or f"Resonance score: {score}",
            )

        # Check exit rules for sell signals
        elif signal_type in ["sell", "exit"]:
            existing = self.portfolio.get_position(code)
            if not existing:
                return None

            return TradeAction(
                code=code,
                name=name or existing.name,
                side=TradeSide.SELL,
                quantity=existing.current_quantity,
                price=price,
                signal_type=SignalType.SELL,
                signal_source=source,
                signal_reason=reason or "Signal exit",
            )

        return None

    def check_exit_conditions(self, trade_date: date) -> list[TradeRecord]:
        """Check all positions for exit conditions (stop loss, take profit, time exit).

        Args:
            trade_date: Current trading date

        Returns:
            List of executed exit trades
        """
        executed_trades: list[TradeRecord] = []
        open_positions = self.portfolio.get_open_positions()

        for position in open_positions:
            action = self._check_position_exit(position, trade_date)
            if action:
                trade = self._execute_action(action, trade_date)
                if trade:
                    executed_trades.append(trade)

        return executed_trades

    def _check_position_exit(
        self,
        position: Position,
        trade_date: date,
    ) -> TradeAction | None:
        """Check if a position should be exited."""
        # Update price
        price = self._get_current_price(position.code, trade_date)
        if not price:
            return None

        self.portfolio.update_position_price(position.code, price)

        # Calculate return
        entry_value = position.entry_price * position.current_quantity
        current_value = price * position.current_quantity
        return_pct = ((current_value - entry_value) / entry_value * 100) if entry_value > 0 else 0

        # Check stop loss
        if return_pct <= -self.config.stop_loss_pct:
            return TradeAction(
                code=position.code,
                name=position.name,
                side=TradeSide.SELL,
                quantity=position.current_quantity,
                price=price,
                signal_type=SignalType.STOP_LOSS,
                signal_source="system",
                signal_reason=f"Stop loss triggered: {return_pct:.2f}%",
            )

        # Check take profit
        if return_pct >= self.config.take_profit_pct:
            return TradeAction(
                code=position.code,
                name=position.name,
                side=TradeSide.SELL,
                quantity=position.current_quantity,
                price=price,
                signal_type=SignalType.TAKE_PROFIT,
                signal_source="system",
                signal_reason=f"Take profit triggered: {return_pct:.2f}%",
            )

        # Check time exit
        if position.holding_days >= self.config.max_holding_days:
            return TradeAction(
                code=position.code,
                name=position.name,
                side=TradeSide.SELL,
                quantity=position.current_quantity,
                price=price,
                signal_type=SignalType.TIME_EXIT,
                signal_source="system",
                signal_reason=f"Max holding days reached: {position.holding_days}",
            )

        return None

    def _execute_action(
        self,
        action: TradeAction,
        trade_date: date,
    ) -> TradeRecord | None:
        """Execute a trade action."""
        amount = action.price * action.quantity

        # Calculate fees
        commission = max(5.0, amount * 0.0003)  # 0.03%, min 5 yuan
        stamp_duty = amount * 0.001 if action.side == TradeSide.SELL else 0  # 0.1% on sell

        # Create trade record
        trade = TradeRecord(
            trade_id=str(uuid.uuid4()),
            strategy_id=self.config.strategy_id,
            code=action.code,
            name=action.name,
            side=action.side,
            quantity=action.quantity,
            price=action.price,
            amount=amount,
            trade_date=trade_date,
            status=TradeStatus.FILLED,
            signal_source=action.signal_source,
            signal_reason=action.signal_reason,
            commission=commission,
            stamp_duty=stamp_duty,
            filled_at=datetime.now(),
        )

        # Record trade
        self.portfolio.record_trade(trade)

        # Update position
        if action.side == TradeSide.BUY:
            position = self.portfolio.create_position(
                code=action.code,
                name=action.name,
                entry_date=trade_date,
                entry_price=action.price,
                quantity=action.quantity,
                signal_source=action.signal_source,
                signal_reason=action.signal_reason,
            )
            trade.related_position_id = position.position_id
        else:
            position = self.portfolio.close_position(
                code=action.code,
                exit_date=trade_date,
                exit_price=action.price,
                quantity=action.quantity,
            )
            if position:
                trade.related_position_id = position.position_id

        return trade

    def _get_current_price(self, code: str, trade_date: date) -> float | None:
        """Get current price for a stock."""
        # Try to get from market data source
        if self.market_data_source and self.market_data_source.exists():
            try:
                import sqlite3
                with sqlite3.connect(str(self.market_data_source)) as conn:
                    row = conn.execute(
                        "SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?",
                        (code, trade_date.isoformat()),
                    ).fetchone()
                    if row:
                        return float(row[0])
            except Exception:
                pass

        # Try to get from position's current price
        position = self.portfolio.get_position(code)
        if position:
            return position.current_price

        return None

    def generate_signals_from_candidates(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate buy signals from lab candidates.

        Args:
            candidates: List of candidate stocks from labs

        Returns:
            List of buy signals
        """
        signals: list[dict[str, Any]] = []

        for candidate in candidates:
            code = candidate.get("stock_code") or candidate.get("code", "")
            name = candidate.get("stock_name") or candidate.get("name", "")
            score = candidate.get("resonance_score", 0)
            tier = candidate.get("tier", "")
            source = candidate.get("source", "")

            if not code:
                continue

            signals.append({
                "code": code,
                "name": name,
                "signal_type": "buy",
                "source": source or "lab_candidate",
                "reason": f"Lab selection: {candidate.get('reason', 'N/A')}",
                "score": score,
                "tier": tier,
                "entry_price": candidate.get("entry_price"),
            })

        return signals
