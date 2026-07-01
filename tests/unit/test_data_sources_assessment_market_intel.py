from __future__ import annotations

import sqlite3
from pathlib import Path

from apps.api.main import BootstrapApiService


def test_data_sources_assessment_includes_market_intel_tables(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE stocks (
            code TEXT PRIMARY KEY,
            asset_type TEXT,
            is_delisted INTEGER,
            total_market_cap REAL,
            pe_ratio REAL,
            pb_ratio REAL,
            profit_growth REAL,
            revenue_growth REAL,
            roe REAL,
            last_trade_date TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE daily_prices (
            code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            close REAL,
            amount REAL,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO stocks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("000001", "stock", 0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, "2026-06-13"),
    )
    conn.execute(
        "INSERT INTO daily_prices VALUES (?, ?, ?, ?, ?)",
        ("000001", "2026-06-13", 10.0, 100.0, "2026-06-13T12:00:00"),
    )
    conn.commit()

    service = BootstrapApiService(project_root="/Users/mac/NeoTrade3")
    service._ensure_tushare_market_tables(conn=conn)
    conn.execute(
        """
        INSERT INTO policy_documents (pubtime, title, pcode, puborg, ptype, url, content_html, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-06-13T10:00:00",
            "政策测试",
            "文号A",
            "国务院",
            "科技",
            "https://example.com/policy",
            "<p>ok</p>",
            "tushare.npr",
            "2026-06-13T12:00:00",
        ),
    )
    conn.execute(
        """
        INSERT INTO fund_portfolios (
            ts_code, ann_date, end_date, symbol, mkv, amount, stk_mkv_ratio, stk_float_ratio, source, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "510330.SH",
            "2026-04-20",
            "2026-03-31",
            "300308",
            1000.0,
            100.0,
            8.2,
            0.1,
            "tushare.fund_portfolio",
            "2026-06-13T12:00:00",
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    payload = service.data_sources_assessment_view(
        target_date="2026-06-13",
        lookback_days=30,
    )

    assert payload["sources"]["policy_documents"]["exists"] is True
    assert payload["sources"]["policy_documents"]["range"]["rows"] == 1
    assert payload["sources"]["fund_portfolios"]["exists"] is True
    assert payload["sources"]["fund_portfolios"]["range"]["distinct_codes"] == 1
