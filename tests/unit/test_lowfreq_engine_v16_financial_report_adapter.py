from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from apps.api.main import BootstrapApiService
from neotrade3.data_control.financial_report_adapter import (
    load_fundamentals,
    load_fundamentals_batch,
)


def _build_reports_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        BootstrapApiService._ensure_financial_reports_tables(conn=conn)
        conn.executemany(
            """
            INSERT INTO financial_reports (
                code, report_date, ann_date, pe_ttm, profit_growth_yoy, revenue_growth_yoy, roe, source, metadata_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "000001",
                    "2024-12-31",
                    "2025-01-20",
                    8.0,
                    11.0,
                    12.0,
                    13.0,
                    "unit.test",
                    "{}",
                    "2026-06-19T00:00:00",
                ),
                (
                    "000001",
                    "2025-03-31",
                    "2025-04-20",
                    10.0,
                    21.0,
                    22.0,
                    23.0,
                    "unit.test",
                    "{}",
                    "2026-06-19T00:00:00",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_load_fundamentals_returns_missing_table_fallback(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        out, refreshed_flag = load_fundamentals(
            conn,
            "000001",
            target_date=date(2025, 4, 19),
            has_financial_reports=None,
        )
    finally:
        conn.close()

    assert refreshed_flag is False
    assert out == {
        "pe_ttm": 0,
        "profit_growth": 0,
        "revenue_growth": 0,
        "roe": 0,
        "table_exists": False,
    }


def test_load_fundamentals_batch_returns_missing_table_fallback(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        out, refreshed_flag = load_fundamentals_batch(
            conn.cursor(),
            ["000001"],
            target_date=date(2025, 4, 19),
            has_financial_reports=None,
        )
    finally:
        conn.close()

    assert refreshed_flag is False
    assert out == {
        "000001": {
            "pe_ttm": 0,
            "profit_growth": 0,
            "revenue_growth": 0,
            "roe": 0,
            "table_exists": False,
        }
    }


def test_load_fundamentals_uses_ann_date_visibility(tmp_path: Path) -> None:
    db_path = _build_reports_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    try:
        before, before_flag = load_fundamentals(
            conn,
            "000001",
            target_date=date(2025, 4, 19),
            has_financial_reports=None,
        )
        after, after_flag = load_fundamentals(
            conn,
            "000001",
            target_date=date(2025, 4, 20),
            has_financial_reports=before_flag,
        )
    finally:
        conn.close()

    assert before_flag is True
    assert after_flag is True
    assert before["pe_ttm"] == 8.0
    assert before["profit_growth"] == 11.0
    assert after["pe_ttm"] == 10.0
    assert after["profit_growth"] == 21.0


def test_load_fundamentals_batch_uses_ann_date_visibility(tmp_path: Path) -> None:
    db_path = _build_reports_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    try:
        before, before_flag = load_fundamentals_batch(
            conn.cursor(),
            ["000001"],
            target_date=date(2025, 4, 19),
            has_financial_reports=None,
        )
        after, after_flag = load_fundamentals_batch(
            conn.cursor(),
            ["000001"],
            target_date=date(2025, 4, 20),
            has_financial_reports=before_flag,
        )
    finally:
        conn.close()

    assert before_flag is True
    assert after_flag is True
    assert before["000001"]["pe_ttm"] == 8.0
    assert before["000001"]["profit_growth"] == 11.0
    assert after["000001"]["pe_ttm"] == 10.0
    assert after["000001"]["profit_growth"] == 21.0


def test_load_fundamentals_preserves_none_cache_for_blank_input(tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        single_out, single_flag = load_fundamentals(
            conn,
            "",
            target_date=date(2025, 4, 19),
            has_financial_reports=None,
        )
        batch_out, batch_flag = load_fundamentals_batch(
            conn.cursor(),
            ["", "   "],
            target_date=date(2025, 4, 19),
            has_financial_reports=None,
        )
    finally:
        conn.close()

    assert single_flag is None
    assert batch_flag is None
    assert single_out == {
        "pe_ttm": 0,
        "profit_growth": 0,
        "revenue_growth": 0,
        "roe": 0,
        "table_exists": False,
    }
    assert batch_out == {}
