"""Portfolio manager for paper trading simulation."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import date, datetime
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


class PortfolioManager:
    """Manages paper trading portfolio state."""

    def __init__(self, db_path: str | Path, strategy_config: StrategyConfig) -> None:
        self.db_path = Path(db_path)
        self.config = strategy_config
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            # Positions table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    position_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT,
                    entry_date TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_quantity INTEGER NOT NULL,
                    current_quantity INTEGER NOT NULL,
                    current_price REAL NOT NULL,
                    exit_date TEXT,
                    exit_price REAL,
                    realized_pnl REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0,
                    status TEXT NOT NULL,
                    entry_signal_source TEXT,
                    entry_signal_reason TEXT,
                    trade_ids TEXT,  -- JSON list
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # Trades table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    amount REAL NOT NULL,
                    trade_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    signal_source TEXT,
                    signal_reason TEXT,
                    related_position_id TEXT,
                    created_at TEXT NOT NULL,
                    filled_at TEXT,
                    commission REAL DEFAULT 0,
                    stamp_duty REAL DEFAULT 0
                )
                """
            )

            # Portfolio snapshots table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    snapshot_date TEXT NOT NULL,
                    cash REAL NOT NULL,
                    total_value REAL NOT NULL,
                    position_count INTEGER NOT NULL,
                    daily_pnl REAL DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    total_return_pct REAL DEFAULT 0,
                    max_drawdown_pct REAL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE(strategy_id, snapshot_date)
                )
                """
            )

            conn.commit()

    def get_open_positions(self) -> list[Position]:
        """Get all open positions."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM positions
                WHERE strategy_id = ? AND status IN ('open', 'partial')
                ORDER BY entry_date DESC
                """,
                (self.config.strategy_id,),
            ).fetchall()
            return [self._row_to_position(row) for row in rows]

    def get_position(self, code: str) -> Position | None:
        """Get position for a specific stock."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM positions
                WHERE strategy_id = ? AND code = ? AND status IN ('open', 'partial')
                LIMIT 1
                """,
                (self.config.strategy_id, code),
            ).fetchone()
            return self._row_to_position(row) if row else None

    def create_position(
        self,
        code: str,
        name: str,
        entry_date: date,
        entry_price: float,
        quantity: int,
        signal_source: str = "",
        signal_reason: str = "",
    ) -> Position:
        """Create a new position."""
        position_id = str(uuid.uuid4())
        now = datetime.now()

        position = Position(
            position_id=position_id,
            strategy_id=self.config.strategy_id,
            code=code,
            name=name,
            entry_date=entry_date,
            entry_price=entry_price,
            entry_quantity=quantity,
            current_quantity=quantity,
            current_price=entry_price,
            entry_signal_source=signal_source,
            entry_signal_reason=signal_reason,
            created_at=now,
            updated_at=now,
        )

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO positions (
                    position_id, strategy_id, code, name, entry_date, entry_price,
                    entry_quantity, current_quantity, current_price, status,
                    entry_signal_source, entry_signal_reason, trade_ids, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    position.position_id,
                    position.strategy_id,
                    position.code,
                    position.name,
                    position.entry_date.isoformat(),
                    position.entry_price,
                    position.entry_quantity,
                    position.current_quantity,
                    position.current_price,
                    position.status.value,
                    position.entry_signal_source,
                    position.entry_signal_reason,
                    "[]",
                    position.created_at.isoformat(),
                    position.updated_at.isoformat(),
                ),
            )
            conn.commit()

        return position

    def update_position_price(self, code: str, new_price: float) -> None:
        """Update current price for a position."""
        with sqlite3.connect(str(self.db_path)) as conn:
            # Get current position
            row = conn.execute(
                "SELECT * FROM positions WHERE strategy_id = ? AND code = ? AND status IN ('open', 'partial')",
                (self.config.strategy_id, code),
            ).fetchone()

            if not row:
                return

            position = self._row_to_position(row)
            position.update_price(new_price)

            conn.execute(
                """
                UPDATE positions
                SET current_price = ?, unrealized_pnl = ?, updated_at = ?
                WHERE position_id = ?
                """,
                (
                    position.current_price,
                    position.unrealized_pnl,
                    datetime.now().isoformat(),
                    position.position_id,
                ),
            )
            conn.commit()

    def close_position(
        self,
        code: str,
        exit_date: date,
        exit_price: float,
        quantity: int | None = None,
    ) -> Position | None:
        """Close or partially close a position."""
        position = self.get_position(code)
        if not position:
            return None

        if quantity is None:
            quantity = position.current_quantity

        # Calculate realized P&L for this close
        realized_pnl = (exit_price - position.entry_price) * quantity

        with sqlite3.connect(str(self.db_path)) as conn:
            if quantity >= position.current_quantity:
                # Full close
                conn.execute(
                    """
                    UPDATE positions
                    SET current_quantity = 0, exit_date = ?, exit_price = ?,
                        realized_pnl = realized_pnl + ?, status = ?, updated_at = ?
                    WHERE position_id = ?
                    """,
                    (
                        exit_date.isoformat(),
                        exit_price,
                        realized_pnl,
                        PositionStatus.CLOSED.value,
                        datetime.now().isoformat(),
                        position.position_id,
                    ),
                )
            else:
                # Partial close
                new_quantity = position.current_quantity - quantity
                conn.execute(
                    """
                    UPDATE positions
                    SET current_quantity = ?, realized_pnl = realized_pnl + ?,
                        status = ?, updated_at = ?
                    WHERE position_id = ?
                    """,
                    (
                        new_quantity,
                        realized_pnl,
                        PositionStatus.PARTIAL.value,
                        datetime.now().isoformat(),
                        position.position_id,
                    ),
                )
            conn.commit()

        return self.get_position(code) if quantity < position.current_quantity else None

    def record_trade(self, trade: TradeRecord) -> None:
        """Record a trade."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO trades (
                    trade_id, strategy_id, code, name, side, quantity, price,
                    amount, trade_date, status, signal_source, signal_reason,
                    related_position_id, created_at, filled_at, commission, stamp_duty
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.trade_id,
                    trade.strategy_id,
                    trade.code,
                    trade.name,
                    trade.side.value,
                    trade.quantity,
                    trade.price,
                    trade.amount,
                    trade.trade_date.isoformat(),
                    trade.status.value,
                    trade.signal_source,
                    trade.signal_reason,
                    trade.related_position_id,
                    trade.created_at.isoformat(),
                    trade.filled_at.isoformat() if trade.filled_at else None,
                    trade.commission,
                    trade.stamp_duty,
                ),
            )

            # Update position's trade_ids if related
            if trade.related_position_id:
                conn.execute(
                    """
                    UPDATE positions
                    SET trade_ids = (
                        SELECT CASE
                            WHEN trade_ids IS NULL OR trade_ids = '[]' THEN ?
                            ELSE json_insert(trade_ids, '$[#]', ?)
                        END
                    ),
                    updated_at = ?
                    WHERE position_id = ?
                    """,
                    (
                        f'["{trade.trade_id}"]',
                        trade.trade_id,
                        datetime.now().isoformat(),
                        trade.related_position_id,
                    ),
                )

            conn.commit()

    def get_cash(self) -> float:
        """Get current cash balance."""
        # Calculate from initial capital and all trades
        with sqlite3.connect(str(self.db_path)) as conn:
            total_buys = conn.execute(
                """
                SELECT COALESCE(SUM(amount + commission), 0)
                FROM trades
                WHERE strategy_id = ? AND side = 'buy' AND status = 'filled'
                """,
                (self.config.strategy_id,),
            ).fetchone()[0] or 0

            total_sells = conn.execute(
                """
                SELECT COALESCE(SUM(amount - commission - stamp_duty), 0)
                FROM trades
                WHERE strategy_id = ? AND side = 'sell' AND status = 'filled'
                """,
                (self.config.strategy_id,),
            ).fetchone()[0] or 0

            return self.config.initial_capital - total_buys + total_sells

    def get_portfolio_value(self) -> float:
        """Get total portfolio value (cash + positions)."""
        cash = self.get_cash()
        positions_value = sum(
            p.market_value for p in self.get_open_positions()
        )
        return cash + positions_value

    def save_snapshot(self, snapshot_date: date) -> dict[str, Any]:
        """Save portfolio snapshot for a date."""
        cash = self.get_cash()
        total_value = self.get_portfolio_value()
        open_positions = self.get_open_positions()

        # Calculate P&L
        total_pnl = total_value - self.config.initial_capital
        total_return_pct = (
            (total_pnl / self.config.initial_capital) * 100
            if self.config.initial_capital > 0
            else 0
        )

        snapshot_id = str(uuid.uuid4())
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO portfolio_snapshots (
                    snapshot_id, strategy_id, snapshot_date, cash, total_value,
                    position_count, total_pnl, total_return_pct, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    self.config.strategy_id,
                    snapshot_date.isoformat(),
                    cash,
                    total_value,
                    len(open_positions),
                    total_pnl,
                    total_return_pct,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

        return {
            "snapshot_id": snapshot_id,
            "snapshot_date": snapshot_date.isoformat(),
            "cash": cash,
            "total_value": total_value,
            "position_count": len(open_positions),
            "total_pnl": total_pnl,
            "total_return_pct": total_return_pct,
        }

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
