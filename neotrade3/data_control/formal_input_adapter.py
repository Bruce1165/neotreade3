"""Read-side adapter for lowfreq formal M1 inputs."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from .contracts import D7TradingDayStatus
from .projections import (
    project_d1_daily_price_fact,
    project_d7_security_master_minimal,
    project_d7_trading_day_status,
)


def _normalize_codes(codes: list[str]) -> list[str]:
    return [str(code or "").strip() for code in (codes or []) if str(code or "").strip()]


def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    row = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _load_recent_price_history_batch(
    cursor: sqlite3.Cursor,
    codes: list[str],
    *,
    target_date: date,
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    normalized_codes = _normalize_codes(codes)
    if not normalized_codes or int(limit) <= 0:
        return {}

    placeholders = ",".join(["?"] * len(normalized_codes))
    cursor.execute(
        f"""
        SELECT code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change
        FROM (
            SELECT
                code,
                trade_date,
                open,
                high,
                low,
                close,
                volume,
                amount,
                turnover,
                preclose,
                pct_change,
                row_number() OVER (PARTITION BY code ORDER BY trade_date DESC) AS rn
            FROM daily_prices
            WHERE code IN ({placeholders})
              AND trade_date <= ?
        )
        WHERE rn <= ?
        ORDER BY code ASC, trade_date DESC
        """,
        (*normalized_codes, target_date.isoformat(), int(limit)),
    )
    rows = cursor.fetchall()

    out: dict[str, list[dict[str, Any]]] = {}
    for code, trade_date, open_, high, low, close, volume, amount, turnover, preclose, pct_change in rows:
        code_s = str(code or "").strip()
        if not code_s:
            continue
        out.setdefault(code_s, []).append(
            {
                "trade_date": str(trade_date or ""),
                "open": float(open_) if open_ is not None else None,
                "high": float(high) if high is not None else None,
                "low": float(low) if low is not None else None,
                "close": float(close) if close is not None else None,
                "volume": float(volume) if volume is not None else None,
                "amount": float(amount) if amount is not None else None,
                "turnover": float(turnover) if turnover is not None else None,
                "preclose": float(preclose) if preclose is not None else None,
                "pct_change": float(pct_change) if pct_change is not None else None,
            }
        )
    return out


def _load_d1_facts_batch(
    cursor: sqlite3.Cursor,
    codes: list[str],
    *,
    target_date: date,
) -> dict[str, Any]:
    normalized_codes = _normalize_codes(codes)
    if not normalized_codes:
        return {}

    placeholders = ",".join(["?"] * len(normalized_codes))
    cursor.execute(
        f"""
        SELECT code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change, updated_at
        FROM daily_prices
        WHERE code IN ({placeholders})
          AND trade_date = ?
        """,
        (*normalized_codes, target_date.isoformat()),
    )
    rows = cursor.fetchall()

    out: dict[str, Any] = {}
    for row in rows:
        payload = {
            "code": row[0],
            "trade_date": row[1],
            "open": row[2],
            "high": row[3],
            "low": row[4],
            "close": row[5],
            "volume": row[6],
            "amount": row[7],
            "turnover": row[8],
            "preclose": row[9],
            "pct_change": row[10],
            "updated_at": row[11],
        }
        item = project_d1_daily_price_fact(payload)
        out[item.stock_code] = item
    return out


def _load_security_master_batch(
    cursor: sqlite3.Cursor,
    codes: list[str],
) -> dict[str, Any]:
    normalized_codes = _normalize_codes(codes)
    if not normalized_codes:
        return {}

    placeholders = ",".join(["?"] * len(normalized_codes))
    cursor.execute(
        f"""
        SELECT code, name, asset_type, is_delisted, sector_lv1, sector_lv2, last_trade_date
        FROM stocks
        WHERE code IN ({placeholders})
        """,
        (*normalized_codes,),
    )
    rows = cursor.fetchall()

    out: dict[str, Any] = {}
    for row in rows:
        payload = {
            "code": row[0],
            "name": row[1],
            "asset_type": row[2],
            "is_delisted": row[3],
            "sector_lv1": row[4],
            "sector_lv2": row[5],
            "last_trade_date": row[6],
        }
        item = project_d7_security_master_minimal(payload)
        out[item.stock_code] = item
    return out


def _build_trading_day_status(
    cursor: sqlite3.Cursor,
    *,
    target_date: date,
) -> D7TradingDayStatus:
    target_key = target_date.isoformat()
    if _table_exists(cursor, "trading_calendar_cache"):
        cursor.execute(
            "SELECT 1 FROM trading_calendar_cache WHERE trade_date = ? LIMIT 1",
            (target_key,),
        )
        is_trading_day = bool(cursor.fetchone())
        cursor.execute(
            "SELECT MIN(trade_date), MAX(trade_date) FROM trading_calendar_cache"
        )
        row = cursor.fetchone() or (None, None)
        min_trading_day = str(row[0] or "").strip() or None
        max_trading_day = str(row[1] or "").strip() or None
        covered_until = max_trading_day
        calendar_source = "trading_calendar_cache"
        if _table_exists(cursor, "trading_calendar_meta"):
            cursor.execute(
                "SELECT key, value FROM trading_calendar_meta WHERE key IN (?, ?)",
                ("calendar_source", "calendar_covered_until"),
            )
            for key, value in cursor.fetchall():
                if str(key or "") == "calendar_source" and str(value or "").strip():
                    calendar_source = str(value).strip()
                if str(key or "") == "calendar_covered_until" and str(value or "").strip():
                    covered_until = str(value).strip()
        return project_d7_trading_day_status(
            {
                "target_date": target_key,
                "is_trading_day": is_trading_day,
                "nearest_trading_day": target_key if is_trading_day else None,
                "min_trading_day": min_trading_day,
                "max_trading_day": max_trading_day,
                "calendar_covered_until": covered_until,
                "_meta": {"calendar_source": calendar_source},
            }
        )

    cursor.execute(
        "SELECT MIN(trade_date), MAX(trade_date) FROM daily_prices"
    )
    row = cursor.fetchone() or (None, None)
    min_trading_day = str(row[0] or "").strip() or None
    max_trading_day = str(row[1] or "").strip() or None
    cursor.execute(
        "SELECT 1 FROM daily_prices WHERE trade_date = ? LIMIT 1",
        (target_key,),
    )
    is_trading_day = bool(cursor.fetchone())
    return project_d7_trading_day_status(
        {
            "target_date": target_key,
            "is_trading_day": is_trading_day,
            "nearest_trading_day": target_key if is_trading_day else None,
            "min_trading_day": min_trading_day,
            "max_trading_day": max_trading_day,
            "calendar_covered_until": max_trading_day,
            "_meta": {"calendar_source": "daily_prices_fallback"},
        }
    )


def load_formal_m1_inputs(
    cursor: sqlite3.Cursor,
    codes: list[str],
    *,
    target_date: date,
    history_limit: int = 20,
) -> dict[str, Any]:
    normalized_codes = _normalize_codes(codes)
    return {
        "d1_by_code": _load_d1_facts_batch(cursor, normalized_codes, target_date=target_date),
        "security_by_code": _load_security_master_batch(cursor, normalized_codes),
        "trading_day_status": _build_trading_day_status(cursor, target_date=target_date),
        "history_by_code": _load_recent_price_history_batch(
            cursor,
            normalized_codes,
            target_date=target_date,
            limit=history_limit,
        ),
    }
