from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any


def _fallback_payload(*, table_exists: bool) -> dict[str, Any]:
    return {
        "pe_ttm": 0,
        "profit_growth": 0,
        "revenue_growth": 0,
        "roe": 0,
        "table_exists": table_exists,
    }


def _resolve_financial_reports_flag(cursor: sqlite3.Cursor, has_financial_reports: bool | None) -> bool | None:
    if has_financial_reports is None:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='financial_reports'")
        return bool(cursor.fetchone())
    return has_financial_reports


def _normalize_codes(codes: list[str]) -> list[str]:
    normalized: list[str] = []
    for code in codes:
        text = str(code).strip()
        if text:
            normalized.append(text)
    return normalized


def load_fundamentals_batch(
    cursor: sqlite3.Cursor,
    codes: list[str],
    *,
    target_date: date,
    has_financial_reports: bool | None,
) -> tuple[dict[str, dict[str, Any]], bool | None]:
    normalized_codes = _normalize_codes(codes)
    if not normalized_codes:
        return {}, has_financial_reports

    refreshed_flag = _resolve_financial_reports_flag(cursor, has_financial_reports)
    if not bool(refreshed_flag):
        return {code: _fallback_payload(table_exists=False) for code in normalized_codes}, refreshed_flag

    placeholders = ",".join(["?"] * len(normalized_codes))
    cursor.execute(
        f"""
        SELECT
            code,
            report_date,
            ann_date,
            pe_ttm,
            profit_growth_yoy,
            revenue_growth_yoy,
            roe
        FROM financial_reports
        WHERE code IN ({placeholders})
          AND COALESCE(ann_date, report_date) <= ?
        ORDER BY code, COALESCE(ann_date, report_date) DESC, report_date DESC
        """,
        (*normalized_codes, target_date.isoformat()),
    )
    rows = cursor.fetchall()

    latest_by_code: dict[str, dict[str, Any]] = {}
    for code, _report_date, _ann_date, pe_ttm, profit_growth_yoy, revenue_growth_yoy, roe in rows:
        code_s = str(code or "").strip()
        if not code_s or code_s in latest_by_code:
            continue
        latest_by_code[code_s] = {
            "pe_ttm": pe_ttm or 0,
            "profit_growth": profit_growth_yoy or 0,
            "revenue_growth": revenue_growth_yoy or 0,
            "roe": roe or 0,
            "table_exists": True,
        }

    out: dict[str, dict[str, Any]] = {}
    for code in normalized_codes:
        out[code] = latest_by_code.get(code) or _fallback_payload(table_exists=False)
    return out, refreshed_flag


def load_fundamentals(
    conn: sqlite3.Connection,
    code: str,
    *,
    target_date: date,
    has_financial_reports: bool | None,
) -> tuple[dict[str, Any], bool | None]:
    normalized_code = str(code).strip()
    if not normalized_code:
        return _fallback_payload(table_exists=False), has_financial_reports

    cursor = conn.cursor()
    refreshed_flag = _resolve_financial_reports_flag(cursor, has_financial_reports)
    if not bool(refreshed_flag):
        return _fallback_payload(table_exists=False), refreshed_flag

    try:
        cursor.execute(
            """
            SELECT pe_ttm, profit_growth_yoy, revenue_growth_yoy, roe
            FROM financial_reports
            WHERE code = ? AND COALESCE(ann_date, report_date) <= ?
            ORDER BY COALESCE(ann_date, report_date) DESC, report_date DESC
            LIMIT 1
            """,
            (normalized_code, target_date.isoformat()),
        )
        row = cursor.fetchone()
        if row:
            pe, profit_growth, revenue_growth, roe = row
            return {
                "pe_ttm": pe or 0,
                "profit_growth": profit_growth or 0,
                "revenue_growth": revenue_growth or 0,
                "roe": roe or 0,
                "table_exists": True,
            }, refreshed_flag
    except Exception:
        pass

    return _fallback_payload(table_exists=False), refreshed_flag
