"""SQLite-backed storage for the low-frequency score system."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional


class LowfreqScoreStore:
    """Minimal authoritative store for the operation layer fact model."""

    def __init__(self, *, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _ensure_column(
        cursor: sqlite3.Cursor,
        *,
        table_name: str,
        column_name: str,
        definition_sql: str,
    ) -> None:
        existing_columns = {
            str(row[1])
            for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {definition_sql}")

    def ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lowfreq_score_pool_current (
                  code TEXT PRIMARY KEY,
                  name TEXT NOT NULL DEFAULT '',
                  sector TEXT NOT NULL DEFAULT '',
                  sector_name TEXT NOT NULL DEFAULT '',
                  state TEXT NOT NULL,
                  state_since TEXT NOT NULL DEFAULT '',
                  tracking_since TEXT NOT NULL DEFAULT '',
                  buy_date TEXT,
                  buy_price REAL,
                  sell_date TEXT,
                  sell_price REAL,
                  last_trade_date TEXT,
                  last_price REAL,
                  current_return_pct REAL,
                  realized_return_pct REAL,
                  top_signal_date TEXT,
                  engine_snapshot_ref TEXT NOT NULL DEFAULT '',
                  updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_lowfreq_score_pool_current_state ON lowfreq_score_pool_current (state, state_since)"
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lowfreq_score_pool_events (
                  event_id TEXT PRIMARY KEY,
                  code TEXT NOT NULL,
                  sector_name TEXT NOT NULL DEFAULT '',
                  event_type TEXT NOT NULL,
                  event_date TEXT NOT NULL,
                  from_state TEXT NOT NULL DEFAULT '',
                  to_state TEXT NOT NULL DEFAULT '',
                  trigger_source TEXT NOT NULL DEFAULT '',
                  engine_evidence_ref TEXT NOT NULL DEFAULT '',
                  price REAL,
                  note TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(
                cursor,
                table_name="lowfreq_score_pool_current",
                column_name="sector_name",
                definition_sql="sector_name TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                cursor,
                table_name="lowfreq_score_pool_events",
                column_name="sector_name",
                definition_sql="sector_name TEXT NOT NULL DEFAULT ''",
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_lowfreq_score_pool_events_code_date ON lowfreq_score_pool_events (code, event_date DESC)"
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lowfreq_score_daily_price_snapshots (
                  trade_date TEXT NOT NULL,
                  code TEXT NOT NULL,
                  state TEXT NOT NULL,
                  close_price REAL,
                  buy_price REAL,
                  sell_price REAL,
                  unrealized_return_pct REAL,
                  realized_return_pct REAL,
                  snapshot_refreshed_at TEXT NOT NULL,
                  PRIMARY KEY (trade_date, code)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_lowfreq_score_daily_snapshots_code_date ON lowfreq_score_daily_price_snapshots (code, trade_date DESC)"
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lowfreq_score_period_summaries (
                  period_type TEXT NOT NULL,
                  period_start TEXT NOT NULL,
                  period_end TEXT NOT NULL,
                  tracked_count INTEGER NOT NULL DEFAULT 0,
                  holding_count INTEGER NOT NULL DEFAULT 0,
                  closed_count INTEGER NOT NULL DEFAULT 0,
                  entered_count INTEGER NOT NULL DEFAULT 0,
                  holding_return_pct REAL,
                  realized_return_pct REAL,
                  pool_return_pct REAL,
                  capture_quality REAL,
                  top_exit_quality REAL,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY (period_type, period_start, period_end)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_lowfreq_score_period_summaries_type_end ON lowfreq_score_period_summaries (period_type, period_end DESC)"
            )
            conn.commit()

    def list_pool_current(
        self,
        *,
        state: Optional[str] = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        self.ensure_schema()
        sql = """
            SELECT
              code, name, sector, sector_name, state, state_since, tracking_since,
              buy_date, buy_price, sell_date, sell_price,
              last_trade_date, last_price, current_return_pct, realized_return_pct,
              top_signal_date, engine_snapshot_ref, updated_at
            FROM lowfreq_score_pool_current
        """
        params: list[Any] = []
        if state:
            sql += " WHERE state = ?"
            params.append(str(state))
        sql += " ORDER BY CASE state WHEN '持有中' THEN 0 WHEN '跟踪' THEN 1 ELSE 2 END, updated_at DESC, code ASC LIMIT ?"
        params.append(max(1, int(limit)))
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_pool_current(self, *, code: str) -> Optional[dict[str, Any]]:
        self.ensure_schema()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                  code, name, sector, sector_name, state, state_since, tracking_since,
                  buy_date, buy_price, sell_date, sell_price,
                  last_trade_date, last_price, current_return_pct, realized_return_pct,
                  top_signal_date, engine_snapshot_ref, updated_at
                FROM lowfreq_score_pool_current
                WHERE code = ?
                """,
                (str(code),),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_events(self, *, code: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        self.ensure_schema()
        sql = """
            SELECT
              event_id, code, sector_name, event_type, event_date, from_state, to_state,
              trigger_source, engine_evidence_ref, price, note, created_at
            FROM lowfreq_score_pool_events
        """
        params: list[Any] = []
        if code:
            sql += " WHERE code = ?"
            params.append(str(code))
        sql += " ORDER BY event_date DESC, created_at DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def list_daily_snapshots(
        self,
        *,
        code: Optional[str] = None,
        limit: int = 120,
    ) -> list[dict[str, Any]]:
        self.ensure_schema()
        sql = """
            SELECT
              trade_date, code, state, close_price, buy_price, sell_price,
              unrealized_return_pct, realized_return_pct, snapshot_refreshed_at
            FROM lowfreq_score_daily_price_snapshots
        """
        params: list[Any] = []
        if code:
            sql += " WHERE code = ?"
            params.append(str(code))
        sql += " ORDER BY trade_date DESC, code ASC LIMIT ?"
        params.append(max(1, int(limit)))
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def list_period_summaries(
        self,
        *,
        period_type: Optional[str] = None,
        limit: int = 120,
    ) -> list[dict[str, Any]]:
        self.ensure_schema()
        sql = """
            SELECT
              period_type, period_start, period_end,
              tracked_count, holding_count, closed_count, entered_count,
              holding_return_pct, realized_return_pct, pool_return_pct,
              capture_quality, top_exit_quality, updated_at
            FROM lowfreq_score_period_summaries
        """
        params: list[Any] = []
        if period_type:
            sql += " WHERE period_type = ?"
            params.append(str(period_type))
        sql += " ORDER BY period_end DESC, updated_at DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def upsert_pool_current(self, payload: dict[str, Any]) -> None:
        self.ensure_schema()
        fields = {
            "code": str(payload.get("code") or "").strip(),
            "name": str(payload.get("name") or ""),
            "sector": str(payload.get("sector") or ""),
            "sector_name": str(payload.get("sector_name") or ""),
            "state": str(payload.get("state") or "跟踪"),
            "state_since": str(payload.get("state_since") or ""),
            "tracking_since": str(payload.get("tracking_since") or ""),
            "buy_date": payload.get("buy_date"),
            "buy_price": payload.get("buy_price"),
            "sell_date": payload.get("sell_date"),
            "sell_price": payload.get("sell_price"),
            "last_trade_date": payload.get("last_trade_date"),
            "last_price": payload.get("last_price"),
            "current_return_pct": payload.get("current_return_pct"),
            "realized_return_pct": payload.get("realized_return_pct"),
            "top_signal_date": payload.get("top_signal_date"),
            "engine_snapshot_ref": str(payload.get("engine_snapshot_ref") or ""),
            "updated_at": str(payload.get("updated_at") or ""),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO lowfreq_score_pool_current (
                  code, name, sector, sector_name, state, state_since, tracking_since,
                  buy_date, buy_price, sell_date, sell_price,
                  last_trade_date, last_price, current_return_pct, realized_return_pct,
                  top_signal_date, engine_snapshot_ref, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                  name=excluded.name,
                  sector=excluded.sector,
                  sector_name=excluded.sector_name,
                  state=excluded.state,
                  state_since=excluded.state_since,
                  tracking_since=excluded.tracking_since,
                  buy_date=excluded.buy_date,
                  buy_price=excluded.buy_price,
                  sell_date=excluded.sell_date,
                  sell_price=excluded.sell_price,
                  last_trade_date=excluded.last_trade_date,
                  last_price=excluded.last_price,
                  current_return_pct=excluded.current_return_pct,
                  realized_return_pct=excluded.realized_return_pct,
                  top_signal_date=excluded.top_signal_date,
                  engine_snapshot_ref=excluded.engine_snapshot_ref,
                  updated_at=excluded.updated_at
                """,
                tuple(fields.values()),
            )
            conn.commit()

    def append_event(self, payload: dict[str, Any]) -> None:
        self.ensure_schema()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO lowfreq_score_pool_events (
                  event_id, code, sector_name, event_type, event_date, from_state, to_state,
                  trigger_source, engine_evidence_ref, price, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(payload.get("event_id") or ""),
                    str(payload.get("code") or ""),
                    str(payload.get("sector_name") or ""),
                    str(payload.get("event_type") or ""),
                    str(payload.get("event_date") or ""),
                    str(payload.get("from_state") or ""),
                    str(payload.get("to_state") or ""),
                    str(payload.get("trigger_source") or ""),
                    str(payload.get("engine_evidence_ref") or ""),
                    payload.get("price"),
                    str(payload.get("note") or ""),
                    str(payload.get("created_at") or ""),
                ),
            )
            conn.commit()

    def upsert_daily_snapshot(self, payload: dict[str, Any]) -> None:
        self.ensure_schema()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO lowfreq_score_daily_price_snapshots (
                  trade_date, code, state, close_price, buy_price, sell_price,
                  unrealized_return_pct, realized_return_pct, snapshot_refreshed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date, code) DO UPDATE SET
                  state=excluded.state,
                  close_price=excluded.close_price,
                  buy_price=excluded.buy_price,
                  sell_price=excluded.sell_price,
                  unrealized_return_pct=excluded.unrealized_return_pct,
                  realized_return_pct=excluded.realized_return_pct,
                  snapshot_refreshed_at=excluded.snapshot_refreshed_at
                """,
                (
                    str(payload.get("trade_date") or ""),
                    str(payload.get("code") or ""),
                    str(payload.get("state") or ""),
                    payload.get("close_price"),
                    payload.get("buy_price"),
                    payload.get("sell_price"),
                    payload.get("unrealized_return_pct"),
                    payload.get("realized_return_pct"),
                    str(payload.get("snapshot_refreshed_at") or ""),
                ),
            )
            conn.commit()

    def upsert_period_summary(self, payload: dict[str, Any]) -> None:
        self.ensure_schema()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO lowfreq_score_period_summaries (
                  period_type, period_start, period_end,
                  tracked_count, holding_count, closed_count, entered_count,
                  holding_return_pct, realized_return_pct, pool_return_pct,
                  capture_quality, top_exit_quality, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(period_type, period_start, period_end) DO UPDATE SET
                  tracked_count=excluded.tracked_count,
                  holding_count=excluded.holding_count,
                  closed_count=excluded.closed_count,
                  entered_count=excluded.entered_count,
                  holding_return_pct=excluded.holding_return_pct,
                  realized_return_pct=excluded.realized_return_pct,
                  pool_return_pct=excluded.pool_return_pct,
                  capture_quality=excluded.capture_quality,
                  top_exit_quality=excluded.top_exit_quality,
                  updated_at=excluded.updated_at
                """,
                (
                    str(payload.get("period_type") or ""),
                    str(payload.get("period_start") or ""),
                    str(payload.get("period_end") or ""),
                    int(payload.get("tracked_count") or 0),
                    int(payload.get("holding_count") or 0),
                    int(payload.get("closed_count") or 0),
                    int(payload.get("entered_count") or 0),
                    payload.get("holding_return_pct"),
                    payload.get("realized_return_pct"),
                    payload.get("pool_return_pct"),
                    payload.get("capture_quality"),
                    payload.get("top_exit_quality"),
                    str(payload.get("updated_at") or ""),
                ),
            )
            conn.commit()

    def prune_pool_current(self, *, active_codes: set[str]) -> None:
        self.ensure_schema()
        normalized = sorted({str(code).strip() for code in set(active_codes or set()) if str(code).strip()})
        with self.connect() as conn:
            if not normalized:
                conn.execute("DELETE FROM lowfreq_score_pool_current")
            else:
                placeholders = ",".join("?" for _ in normalized)
                conn.execute(
                    f"DELETE FROM lowfreq_score_pool_current WHERE code NOT IN ({placeholders})",
                    tuple(normalized),
                )
            conn.commit()
