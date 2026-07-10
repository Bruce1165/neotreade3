from __future__ import annotations

import json
import sqlite3
from datetime import date

from neotrade3.cycle_intelligence.market_focus_snapshot import (
    build_market_focus_snapshot,
    load_penetration_keywords,
    load_stock_concepts_cache,
)


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE fund_portfolios (
            symbol TEXT,
            ann_date TEXT,
            ts_code TEXT,
            mkv REAL,
            stk_mkv_ratio REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE etf_basic_info (
            ts_code TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE index_weights (
            con_code TEXT,
            trade_date TEXT,
            index_code TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE research_reports (
            ts_code TEXT,
            trade_date TEXT,
            inst_csname TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE report_consensus (
            ts_code TEXT,
            report_date TEXT,
            org_name TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE institutional_surveys (
            ts_code TEXT,
            surv_date TEXT,
            rece_org TEXT
        )
        """
    )
    return conn


def _seed_snapshot_tables(conn: sqlite3.Connection, target: date) -> None:
    rows = [
        ("000001", target.isoformat(), "FUND1", 1_000_000.0, 3.5),
        ("000001", target.isoformat(), "FUND2", 800_000.0, 3.6),
        ("000001.SZ", target.isoformat(), "ETF1", 900_000.0, 3.7),
    ]
    conn.executemany(
        "INSERT INTO fund_portfolios(symbol, ann_date, ts_code, mkv, stk_mkv_ratio) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.execute("INSERT INTO etf_basic_info(ts_code) VALUES ('ETF1')")
    conn.execute(
        "INSERT INTO index_weights(con_code, trade_date, index_code) VALUES (?, ?, ?)",
        ("000001.SZ", target.isoformat(), "INDEX-A"),
    )
    conn.execute(
        "INSERT INTO research_reports(ts_code, trade_date, inst_csname) VALUES (?, ?, ?)",
        ("000001.SZ", target.isoformat(), "Broker-A"),
    )
    conn.execute(
        "INSERT INTO report_consensus(ts_code, report_date, org_name) VALUES (?, ?, ?)",
        ("000001.SZ", target.isoformat(), "Consensus-A"),
    )
    conn.execute(
        "INSERT INTO institutional_surveys(ts_code, surv_date, rece_org) VALUES (?, ?, ?)",
        ("000001.SZ", target.isoformat(), "Survey-A"),
    )
    conn.commit()


def test_build_market_focus_snapshot_aggregates_evidence_and_reuses_cache(tmp_path) -> None:
    target = date(2026, 6, 18)
    themes_dir = tmp_path / "themes"
    config_dir = tmp_path / "config"
    themes_dir.mkdir()
    config_dir.mkdir()

    (themes_dir / "_tushare_concepts_cache.json").write_text(
        json.dumps(
            {
                "items": [
                    {"code": "C1", "name": "人工智能"},
                    {"code": "C2", "name": "高股息"},
                    {"code": "C3", "name": "东数西算"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (themes_dir / "_tushare_concept_members_cache.json").write_text(
        json.dumps(
            {
                "concepts": {
                    "C1": {"name": "人工智能", "stocks": [{"code": "000001"}]},
                    "C2": {"name": "高股息", "stocks": [{"code": "000001"}]},
                    "C3": {"name": "东数西算", "stocks": [{"code": "000001"}]},
                }
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "penetration_stages.json").write_text(
        json.dumps(
            {
                "items": [
                    {"match_type": "keyword", "match_value": "东数西算"},
                    {"match_type": "keyword", "match_value": "算力底座"},
                ]
            }
        ),
        encoding="utf-8",
    )

    conn = _make_conn()
    _seed_snapshot_tables(conn, target)
    cursor = conn.cursor()

    stock_concepts_cache = load_stock_concepts_cache(
        themes_snapshot_dir=themes_dir,
        stock_concepts_cache=None,
    )
    penetration_keywords = load_penetration_keywords(
        market_intelligence_config_dir=config_dir,
        penetration_keywords_cache=None,
    )

    market_focus_cache: dict[tuple[str, str], dict[str, object]] = {}
    nonempty_table_cache: dict[str, bool] = {}
    snapshot = build_market_focus_snapshot(
        cursor,
        code="000001",
        stock_name="测试龙头",
        target_date=target,
        market_focus_cache=market_focus_cache,
        nonempty_table_cache=nonempty_table_cache,
        stock_concepts_cache=stock_concepts_cache,
        penetration_keywords=penetration_keywords,
    )

    assert snapshot["focus_pass"] is True
    assert snapshot["focus_bonus"] == 12.0
    assert snapshot["config_score"] == 5
    assert snapshot["attention_score"] == 4
    assert snapshot["holder_etf_count"] == 1
    assert snapshot["holder_fund_count"] == 3
    assert snapshot["index_count"] == 1
    assert "人工智能" in snapshot["ai_hits"]
    assert "人工智能" in snapshot["hardtech_hits"]
    assert "高股息" in snapshot["down_hits"]
    assert "东数西算" in snapshot["penetration_hits"]

    conn.execute("DELETE FROM fund_portfolios")
    conn.execute("DELETE FROM research_reports")
    conn.execute("DELETE FROM report_consensus")
    conn.execute("DELETE FROM institutional_surveys")
    conn.commit()

    cached_snapshot = build_market_focus_snapshot(
        cursor,
        code="000001",
        stock_name="测试龙头",
        target_date=target,
        market_focus_cache=market_focus_cache,
        nonempty_table_cache=nonempty_table_cache,
        stock_concepts_cache=stock_concepts_cache,
        penetration_keywords=penetration_keywords,
    )

    assert cached_snapshot == snapshot
