from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from apps.api.main import BootstrapApiService


def _seed_daily_prices(conn: sqlite3.Connection, *, stock_code: str) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_prices (
            code TEXT,
            trade_date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            turnover REAL,
            preclose REAL,
            pct_change REAL,
            updated_at TEXT
        )
        """
    )
    rows = [
        ("2026-06-13", 9.80, 10.10, 9.70, 10.00, 1000000.0, 300000000.0, 4.0, 9.70, 3.10),
        ("2026-06-12", 9.60, 9.90, 9.55, 9.70, 900000.0, 200000000.0, 3.0, 9.50, 2.10),
        ("2026-06-11", 9.45, 9.60, 9.35, 9.50, 850000.0, 150000000.0, 2.5, 9.40, 1.06),
        ("2026-06-10", 9.30, 9.45, 9.20, 9.40, 780000.0, 100000000.0, 2.0, 9.50, -1.05),
        ("2026-06-09", 9.10, 9.30, 9.05, 9.20, 700000.0, 80000000.0, 1.5, 9.10, 1.10),
    ]
    conn.executemany(
        """
        INSERT INTO daily_prices (
            code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                stock_code,
                trade_date,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                amount,
                turnover,
                preclose,
                pct_change,
                "2026-06-13T10:00:00+00:00",
            )
            for (
                trade_date,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                amount,
                turnover,
                preclose,
                pct_change,
            ) in rows
        ],
    )


def test_load_market_intelligence_for_stock_summarizes_new_tables(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        service._ensure_tushare_market_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO announcements (
                code, ts_code, stock_name, title, type, publish_date, url, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "300308",
                "300308.SZ",
                "中际旭创",
                "年度报告",
                "定期报告",
                "2026-06-13",
                "https://example.com/ann.pdf",
                "tushare.anns_d",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO research_reports (
                trade_date, ts_code, name, title, report_type, author, inst_csname, ind_name, url, abstr, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "光模块龙头更新",
                "个股研报",
                "分析师A",
                "中信证券",
                "光模块",
                "https://example.com/report.pdf",
                "摘要",
                "tushare.research_report",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO report_consensus (
                report_date, ts_code, name, report_title, report_type, classify, org_name, author_name, quarter,
                op_rt, np, eps, pe, roe, rating, imp_dg, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "盈利预测更新",
                "一般报告",
                "一般报告",
                "中信证券",
                "分析师A",
                "2026Q4",
                100000.0,
                20000.0,
                1.2,
                22.5,
                15.3,
                "买入",
                "高",
                "tushare.report_rc",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO institutional_surveys (
                surv_date, ts_code, name, fund_visitors, rece_place, rece_mode, rece_org, org_type, comp_rece, content, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-11",
                "300308.SZ",
                "中际旭创",
                "张三",
                "电话会议",
                "特定对象调研",
                "高毅资产",
                "基金",
                "董秘",
                "调研摘要",
                "tushare.stk_surv",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO etf_basic_info (
                ts_code, csname, extname, index_code, index_name, list_date, list_status, exchange, mgr_name, etf_type, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "光伏ETF",
                "光伏ETF",
                "931151.CSI",
                "光伏指数",
                "2021-01-01",
                "L",
                "SH",
                "华夏基金",
                "境内",
                "tushare.etf_basic",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO fund_basic_info (
                ts_code, name, management, fund_type, found_date, list_date, benchmark, status, market, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "光伏ETF",
                "华夏基金",
                "ETF",
                "2021-01-01",
                "2021-01-15",
                "光伏指数",
                "L",
                "E",
                "tushare.fund_basic",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO fund_portfolios (
                ts_code, ann_date, end_date, symbol, mkv, amount, stk_mkv_ratio, stk_float_ratio, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "2026-05-31",
                "2026-03-31",
                "300308",
                500000.0,
                12000.0,
                8.5,
                1.2,
                "tushare.fund_portfolio",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO index_weights (
                index_code, con_code, trade_date, weight, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "000300.SH",
                "300308.SZ",
                "2026-05-30",
                2.35,
                "tushare.index_weight",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        _seed_daily_prices(conn, stock_code="300308")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {
                "885976.TI": "光模块",
                "880001.TI": "高股息",
            },
            {
                "885976.TI": ["300308"],
                "880001.TI": ["300308"],
            },
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_market_penetration_stage_rules",
        lambda: [
            {
                "match_type": "keyword",
                "match_value": "光模块",
                "penetration_stage": "10_30",
                "reason": "光模块按 10-30 阶段处理",
                "scope": "theme",
            },
            {
                "match_type": "keyword",
                "match_value": "高股息",
                "penetration_stage": "1_10",
                "reason": "高股息按 1-10 阶段处理",
                "scope": "theme",
            },
        ],
    )
    summary = service._load_market_intelligence_for_stock(
        db_path=db_path,
        stock_code="300308",
    )

    assert summary["status"] == "ok"
    assert summary["signals"]["announcements"]["recent_30d_count"] == 1
    assert summary["signals"]["research_reports"]["distinct_institutions_90d"] == 1
    assert summary["signals"]["report_consensus"]["distinct_orgs"] == 1
    assert summary["signals"]["institutional_surveys"]["recent_180d_count"] == 1
    assert summary["signals"]["fund_portfolios"]["holder_etf_count"] == 1
    assert summary["signals"]["index_weights"]["index_count"] == 1
    assert summary["derived_tags"]["config_leader_candidate"]["result"] is True
    assert summary["derived_tags"]["config_leader_candidate"]["level"] == "high"
    assert summary["derived_tags"]["institutional_attention_candidate"]["result"] is True
    assert summary["derived_tags"]["institutional_attention_candidate"]["level"] == "high"
    assert summary["derived_tags"]["trading_leader_candidate"]["result"] is True
    assert summary["derived_tags"]["trading_leader_candidate"]["level"] == "high"
    assert summary["thematic_tags"]["ai_related"]["result"] is True
    assert summary["thematic_tags"]["kshape_direction"]["value"] == "down"
    assert summary["thematic_tags"]["kshape_direction"]["risk_discount_applied"] is True
    assert summary["thematic_tags"]["suggestion_bias"] == 1
    assert summary["thematic_tags"]["penetration_stage"]["value"] == "1_10"
    assert summary["thematic_tags"]["penetration_stage"]["values"] == ["1_10", "10_30"]
    assert summary["thematic_tags"]["penetration_stage"]["is_multi"] is True
    assert len(summary["concepts"]) == 2


def test_market_intelligence_candidates_view_returns_candidate_lists(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.execute("INSERT INTO stocks(code, name) VALUES (?, ?)", ("300308", "中际旭创"))
        service._ensure_tushare_market_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO research_reports (
                trade_date, ts_code, name, title, report_type, author, inst_csname, ind_name, url, abstr, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "光模块龙头更新",
                "个股研报",
                "分析师A",
                "中信证券",
                "光模块",
                "https://example.com/report.pdf",
                "摘要",
                "tushare.research_report",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO report_consensus (
                report_date, ts_code, name, report_title, report_type, classify, org_name, author_name, quarter,
                op_rt, np, eps, pe, roe, rating, imp_dg, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "盈利预测更新",
                "一般报告",
                "一般报告",
                "中信证券",
                "分析师A",
                "2026Q4",
                100000.0,
                20000.0,
                1.2,
                22.5,
                15.3,
                "买入",
                "高",
                "tushare.report_rc",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO institutional_surveys (
                surv_date, ts_code, name, fund_visitors, rece_place, rece_mode, rece_org, org_type, comp_rece, content, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-11",
                "300308.SZ",
                "中际旭创",
                "张三",
                "电话会议",
                "特定对象调研",
                "高毅资产",
                "基金",
                "董秘",
                "调研摘要",
                "tushare.stk_surv",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO etf_basic_info (
                ts_code, csname, extname, index_code, index_name, list_date, list_status, exchange, mgr_name, etf_type, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "光伏ETF",
                "光伏ETF",
                "931151.CSI",
                "光伏指数",
                "2021-01-01",
                "L",
                "SH",
                "华夏基金",
                "境内",
                "tushare.etf_basic",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO fund_portfolios (
                ts_code, ann_date, end_date, symbol, mkv, amount, stk_mkv_ratio, stk_float_ratio, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "2026-05-31",
                "2026-03-31",
                "300308",
                500000.0,
                12000.0,
                8.5,
                1.2,
                "tushare.fund_portfolio",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO index_weights (
                index_code, con_code, trade_date, weight, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "000300.SH",
                "300308.SZ",
                "2026-05-30",
                2.35,
                "tushare.index_weight",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        _seed_daily_prices(conn, stock_code="300308")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {
                "885976.TI": "光模块",
                "880001.TI": "高股息",
            },
            {
                "885976.TI": ["300308"],
                "880001.TI": ["300308"],
            },
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_market_penetration_stage_rules",
        lambda: [
            {
                "match_type": "keyword",
                "match_value": "光模块",
                "penetration_stage": "10_30",
                "reason": "光模块按 10-30 阶段处理",
                "scope": "theme",
            },
            {
                "match_type": "keyword",
                "match_value": "高股息",
                "penetration_stage": "1_10",
                "reason": "高股息按 1-10 阶段处理",
                "scope": "theme",
            },
        ],
    )
    payload = service.market_intelligence_candidates_view(top_n=5)

    assert payload["status"] == "ok"
    assert payload["config_leader_candidates"][0]["stock_code"] == "300308"
    assert payload["config_leader_candidates"][0]["stock_name"] == "中际旭创"
    assert payload["config_leader_candidates"][0]["thematic_tags"]["ai_related"]["result"] is True
    assert payload["config_leader_candidates"][0]["thematic_tags"]["kshape_direction"]["value"] == "down"
    assert (
        payload["config_leader_candidates"][0]["thematic_tags"]["penetration_stage"]["values"]
        == ["1_10", "10_30"]
    )
    assert payload["config_leader_candidates"][0]["suggestion_bias"] == 1
    assert payload["institutional_attention_candidates"][0]["stock_code"] == "300308"
    assert payload["institutional_attention_candidates"][0]["stock_name"] == "中际旭创"
    assert (
        payload["institutional_attention_candidates"][0]["thematic_tags"]["kshape_direction"]["value"]
        == "down"
    )
    assert payload["trading_leader_candidates"][0]["stock_code"] == "300308"
    assert payload["trading_leader_candidates"][0]["level"] == "high"


def test_market_intelligence_candidates_from_seed_snapshot_prefetches_stock_summaries(
    tmp_path,
    monkeypatch,
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")
    db_path = tmp_path / "stock_data.db"
    calls: list[tuple[Path, list[str]]] = []

    def fake_batch_load(*, db_path: Path, stock_codes: list[str]) -> dict[str, dict[str, object]]:
        calls.append((db_path, list(stock_codes)))
        return {
            "300308": {
                "status": "ok",
                "stock_code": "300308",
                "ts_code": "300308.SZ",
                "stock_name": "中际旭创",
                "signals": {
                    "fund_portfolios": {
                        "holder_fund_count": 2,
                        "holder_etf_count": 1,
                        "latest_ann_date": "2026-05-31",
                        "total_mkv": 500000.0,
                        "avg_stk_mkv_ratio": 8.5,
                    },
                    "index_weights": {"index_count": 1},
                    "research_reports": {
                        "distinct_institutions_90d": 1,
                        "recent_90d_count": 2,
                    },
                    "report_consensus": {
                        "distinct_orgs": 1,
                        "latest_report_date": "2026-06-12",
                    },
                    "institutional_surveys": {
                        "distinct_orgs_180d": 1,
                        "recent_180d_count": 1,
                        "latest_survey_date": "2026-06-11",
                    },
                    "trading_profile": {
                        "latest_trade_date": "2026-06-13",
                        "latest_amount": 300000000.0,
                        "avg_amount_5d": 200000000.0,
                        "avg_amount_20d": 180000000.0,
                        "latest_turnover": 4.0,
                        "avg_turnover_5d": 3.0,
                        "return_20d": 0.12,
                        "positive_days_5d": 4,
                    },
                    "theme_momentum": {
                        "best_mainline_rank": 1,
                        "best_heat_rank": 2,
                        "leading_concepts": [
                            {
                                "concept_code": "885976.TI",
                                "concept_name": "光模块",
                                "mainline_rank": 1,
                                "heat_rank": 2,
                                "mainline_score": 95.0,
                                "trend_state": "rising",
                                "risk_level": "ok",
                            }
                        ],
                    },
                },
                "derived_tags": {
                    "config_leader_candidate": {
                        "result": True,
                        "score": 4,
                        "level": "high",
                        "reasons": ["配置主线命中"],
                    },
                    "institutional_attention_candidate": {
                        "result": True,
                        "score": 3,
                        "level": "high",
                        "reasons": ["机构关注命中"],
                    },
                    "trading_leader_candidate": {
                        "result": True,
                        "score": 4,
                        "level": "high",
                        "reasons": ["交易主线命中"],
                    },
                },
                "thematic_tags": {
                    "suggestion_bias": 1,
                    "ai_related": {"result": True},
                    "penetration_stage": {"value": "10_30", "values": ["10_30"]},
                },
                "concepts": [
                    {"concept_code": "885976.TI", "concept_name": "光模块"},
                ],
            }
        }

    monkeypatch.setattr(service, "_load_market_intelligence_for_stocks", fake_batch_load)
    monkeypatch.setattr(
        service,
        "_load_market_intelligence_for_stock",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("should use batch prefetch before single-stock fallback")
        ),
    )

    payload = service._market_intelligence_candidates_from_seed_snapshot(
        top_n=10,
        seed_snapshot={
            "db_path": db_path,
            "config_seed_codes": ["300308.SZ"],
            "attention_seed_codes": ["300308.SZ"],
            "trading_seed_codes": ["300308.SZ"],
            "stock_name_map": {"300308.SZ": "中际旭创"},
        },
    )

    assert payload["status"] == "ok"
    assert calls == [(db_path, ["300308.SZ"])]
    assert payload["config_leader_candidates"][0]["stock_code"] == "300308.SZ"
    assert payload["institutional_attention_candidates"][0]["stock_code"] == "300308.SZ"
    assert payload["trading_leader_candidates"][0]["best_concept_name"] == "光模块"


def test_market_intelligence_unified_candidates_view_merges_roles(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.execute("INSERT INTO stocks(code, name) VALUES (?, ?)", ("300308", "中际旭创"))
        service._ensure_tushare_market_tables(conn=conn)
        service._ensure_ths_concept_daily_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO research_reports (
                trade_date, ts_code, name, title, report_type, author, inst_csname, ind_name, url, abstr, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "光模块龙头更新",
                "个股研报",
                "分析师A",
                "中信证券",
                "光模块",
                "https://example.com/report.pdf",
                "摘要",
                "tushare.research_report",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO report_consensus (
                report_date, ts_code, name, report_title, report_type, classify, org_name, author_name, quarter,
                op_rt, np, eps, pe, roe, rating, imp_dg, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "盈利预测更新",
                "一般报告",
                "一般报告",
                "中信证券",
                "分析师A",
                "2026Q4",
                100000.0,
                20000.0,
                1.2,
                22.5,
                15.3,
                "买入",
                "高",
                "tushare.report_rc",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO institutional_surveys (
                surv_date, ts_code, name, fund_visitors, rece_place, rece_mode, rece_org, org_type, comp_rece, content, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-11",
                "300308.SZ",
                "中际旭创",
                "张三",
                "电话会议",
                "特定对象调研",
                "高毅资产",
                "基金",
                "董秘",
                "调研摘要",
                "tushare.stk_surv",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO etf_basic_info (
                ts_code, csname, extname, index_code, index_name, list_date, list_status, exchange, mgr_name, etf_type, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "光伏ETF",
                "光伏ETF",
                "931151.CSI",
                "光伏指数",
                "2021-01-01",
                "L",
                "SH",
                "华夏基金",
                "境内",
                "tushare.etf_basic",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO fund_portfolios (
                ts_code, ann_date, end_date, symbol, mkv, amount, stk_mkv_ratio, stk_float_ratio, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "2026-05-31",
                "2026-03-31",
                "300308",
                500000.0,
                12000.0,
                8.5,
                1.2,
                "tushare.fund_portfolio",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "885976.TI",
                "光模块",
                "ths",
                10,
                8,
                2.1,
                0.6,
                123456789.0,
                3.2,
                0.1,
                "rising",
                "ok",
                91.5,
                2,
                88.1,
                82.4,
                79.0,
                95.0,
                1,
                5,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        _seed_daily_prices(conn, stock_code="300308")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {"885976.TI": "光模块"},
            {"885976.TI": ["300308"]},
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_market_penetration_stage_rules",
        lambda: [
            {
                "match_type": "keyword",
                "match_value": "光模块",
                "penetration_stage": "10_30",
                "reason": "光模块按 10-30 阶段处理",
                "scope": "theme",
            }
        ],
    )

    payload = service.market_intelligence_unified_candidates_view(top_n=10)

    assert payload["status"] == "ok"
    assert payload["candidates"][0]["stock_code"] == "300308"
    assert payload["candidates"][0]["candidate_type_count"] == 3
    assert payload["candidates"][0]["candidate_types"] == [
        "config_leader",
        "institutional_attention",
        "trading_leader",
    ]
    assert payload["candidates"][0]["roles"]["config_leader"] is not None
    assert payload["candidates"][0]["roles"]["institutional_attention"] is not None
    assert payload["candidates"][0]["roles"]["trading_leader"] is not None


def test_market_intelligence_unified_candidates_view_normalizes_stock_code_and_preserves_name(
    tmp_path, monkeypatch
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")
    monkeypatch.setattr(
        service,
        "_market_intelligence_candidates_payload",
        lambda *,
        top_n,
        stock_summary_cache=None,
        candidate_classified_snapshot=None,
        candidate_seed_snapshot=None: {
            "status": "ok",
            "config_leader_candidates": [
                {
                    "stock_code": "000725",
                    "stock_name": "京东方A",
                    "score": 3,
                    "thematic_tags": {"ai_related": {"result": True}},
                    "suggestion_bias": 2,
                }
            ],
            "institutional_attention_candidates": [
                {
                    "stock_code": "000725.SZ",
                    "stock_name": "",
                    "score": 2,
                    "thematic_tags": {"ai_related": {"result": True}},
                    "suggestion_bias": 1,
                }
            ],
            "trading_leader_candidates": [
                {
                    "stock_code": "000725.SZ",
                    "stock_name": None,
                    "score": 1,
                    "best_concept_name": "显示面板",
                    "thematic_tags": {"ai_related": {"result": True}},
                    "suggestion_bias": 1,
                }
            ],
            "coverage": {},
        },
    )

    payload = service.market_intelligence_unified_candidates_view(top_n=10)

    assert payload["status"] == "ok"
    assert payload["coverage"]["unique_candidates"] == 1
    assert len(payload["candidates"]) == 1
    assert payload["candidates"][0]["stock_code"] == "000725"
    assert payload["candidates"][0]["stock_name"] == "京东方A"
    assert payload["candidates"][0]["candidate_type_count"] == 3
    assert payload["candidates"][0]["candidate_types"] == [
        "config_leader",
        "institutional_attention",
        "trading_leader",
    ]


def test_market_intelligence_recommendations_view_returns_recommendation_status(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.execute("INSERT INTO stocks(code, name) VALUES (?, ?)", ("300308", "中际旭创"))
        service._ensure_tushare_market_tables(conn=conn)
        service._ensure_ths_concept_daily_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO research_reports (
                trade_date, ts_code, name, title, report_type, author, inst_csname, ind_name, url, abstr, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "光模块龙头更新",
                "个股研报",
                "分析师A",
                "中信证券",
                "光模块",
                "https://example.com/report.pdf",
                "摘要",
                "tushare.research_report",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO report_consensus (
                report_date, ts_code, name, report_title, report_type, classify, org_name, author_name, quarter,
                op_rt, np, eps, pe, roe, rating, imp_dg, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "盈利预测更新",
                "一般报告",
                "一般报告",
                "中信证券",
                "分析师A",
                "2026Q4",
                100000.0,
                20000.0,
                1.2,
                22.5,
                15.3,
                "买入",
                "高",
                "tushare.report_rc",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO institutional_surveys (
                surv_date, ts_code, name, fund_visitors, rece_place, rece_mode, rece_org, org_type, comp_rece, content, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-11",
                "300308.SZ",
                "中际旭创",
                "张三",
                "电话会议",
                "特定对象调研",
                "高毅资产",
                "基金",
                "董秘",
                "调研摘要",
                "tushare.stk_surv",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO etf_basic_info (
                ts_code, csname, extname, index_code, index_name, list_date, list_status, exchange, mgr_name, etf_type, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "光伏ETF",
                "光伏ETF",
                "931151.CSI",
                "光伏指数",
                "2021-01-01",
                "L",
                "SH",
                "华夏基金",
                "境内",
                "tushare.etf_basic",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO fund_portfolios (
                ts_code, ann_date, end_date, symbol, mkv, amount, stk_mkv_ratio, stk_float_ratio, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "2026-05-31",
                "2026-03-31",
                "300308",
                500000.0,
                12000.0,
                8.5,
                1.2,
                "tushare.fund_portfolio",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "885976.TI",
                "光模块",
                "ths",
                10,
                8,
                2.1,
                0.6,
                123456789.0,
                3.2,
                0.1,
                "rising",
                "ok",
                91.5,
                2,
                88.1,
                82.4,
                79.0,
                95.0,
                1,
                5,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        _seed_daily_prices(conn, stock_code="300308")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {"885976.TI": "光模块"},
            {"885976.TI": ["300308"]},
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_market_penetration_stage_rules",
        lambda: [
            {
                "match_type": "keyword",
                "match_value": "光模块",
                "penetration_stage": "10_30",
                "reason": "光模块按 10-30 阶段处理",
                "scope": "theme",
            }
        ],
    )

    payload = service.market_intelligence_recommendations_view(top_n=10)

    assert payload["status"] == "ok"
    assert payload["items"][0]["stock_code"] == "300308"
    assert payload["items"][0]["recommendation_status"] == "推荐"
    assert payload["items"][0]["leader_summary"]["candidate_type_count"] == 3
    assert "命中 AI 宽口径主线" in payload["items"][0]["recommendation_reasons"]


def test_build_recommendation_payload_demotes_single_trading_ai_candidate_to_watch(
) -> None:
    candidate = {
        "stock_code": "000001",
        "stock_name": "测试股票",
        "candidate_types": ["trading_leader"],
        "candidate_type_count": 1,
        "primary_candidate_type": "trading_leader",
        "suggestion_bias": 2,
        "thematic_tags": {
            "ai_related": {"result": True},
            "kshape_direction": {"value": "up"},
            "penetration_stage": {"value": "10_30", "values": ["10_30"]},
        },
    }

    payload = BootstrapApiService._build_recommendation_payload_from_candidate(
        candidate,
        recommendation_rank=1,
    )

    assert payload["recommendation_status"] == "观察"
    assert "single_role_only" in payload["risk_flags"]
    assert "single_trading_role_only" in payload["risk_flags"]
    assert "仅单一交易型证据，建议层降为观察" in payload["recommendation_reasons"]


def test_build_recommendation_payload_keeps_single_config_ai_candidate_recommended(
) -> None:
    candidate = {
        "stock_code": "000002",
        "stock_name": "配置龙头股",
        "candidate_types": ["config_leader"],
        "candidate_type_count": 1,
        "primary_candidate_type": "config_leader",
        "suggestion_bias": 2,
        "thematic_tags": {
            "ai_related": {"result": True},
            "kshape_direction": {"value": "up"},
            "penetration_stage": {"value": "10_30", "values": ["10_30"]},
        },
    }

    payload = BootstrapApiService._build_recommendation_payload_from_candidate(
        candidate,
        recommendation_rank=1,
    )

    assert payload["recommendation_status"] == "推荐"
    assert "single_trading_role_only" not in payload["risk_flags"]


def test_build_recommendation_payload_demotes_multi_role_candidate_without_confirmed_theme(
) -> None:
    candidate = {
        "stock_code": "000725",
        "stock_name": "京东方A",
        "candidate_types": ["institutional_attention", "trading_leader"],
        "candidate_type_count": 2,
        "primary_candidate_type": "institutional_attention",
        "suggestion_bias": 2,
        "thematic_tags": {
            "ai_related": {"result": True},
            "kshape_direction": {"value": "up"},
            "penetration_stage": {"value": "10_30", "values": ["10_30"]},
        },
        "roles": {
            "institutional_attention": {},
            "trading_leader": {"best_concept_name": "芯片概念"},
        },
    }

    payload = BootstrapApiService._build_recommendation_payload_from_candidate(
        candidate,
        recommendation_rank=1,
    )

    assert payload["recommendation_status"] == "观察"
    assert "confirmed_theme_missing" in payload["risk_flags"]
    assert "缺少可确认主线锚点，建议层降为观察" in payload["recommendation_reasons"]


def test_build_recommendation_payload_demotes_multi_role_candidate_with_unknown_penetration(
) -> None:
    candidate = {
        "stock_code": "002202",
        "stock_name": "金风科技",
        "candidate_types": ["institutional_attention", "trading_leader"],
        "candidate_type_count": 2,
        "primary_candidate_type": "institutional_attention",
        "suggestion_bias": 2,
        "thematic_tags": {
            "ai_related": {"result": True},
            "kshape_direction": {"value": "up"},
            "penetration_stage": {"value": "unknown", "values": ["unknown"]},
        },
        "roles": {
            "institutional_attention": {},
            "trading_leader": {"best_concept_name": "东数西算(算力)"},
        },
    }

    payload = BootstrapApiService._build_recommendation_payload_from_candidate(
        candidate,
        recommendation_rank=1,
    )

    assert payload["recommendation_status"] == "观察"
    assert "penetration_unknown" in payload["risk_flags"]
    assert "渗透率阶段未确认，建议层降为观察" in payload["recommendation_reasons"]


def test_build_recommendation_payload_keeps_multi_role_candidate_recommended_with_confirmed_theme(
) -> None:
    candidate = {
        "stock_code": "002046",
        "stock_name": "国机精工",
        "candidate_types": ["institutional_attention", "trading_leader"],
        "candidate_type_count": 2,
        "primary_candidate_type": "institutional_attention",
        "suggestion_bias": 2,
        "thematic_tags": {
            "ai_related": {"result": True},
            "kshape_direction": {"value": "up"},
            "penetration_stage": {"value": "10_30", "values": ["10_30"]},
        },
        "roles": {
            "institutional_attention": {},
            "trading_leader": {"best_concept_name": "第三代半导体"},
        },
    }

    payload = BootstrapApiService._build_recommendation_payload_from_candidate(
        candidate,
        recommendation_rank=1,
    )

    assert payload["recommendation_status"] == "推荐"
    assert "confirmed_theme_missing" not in payload["risk_flags"]


def test_load_market_boundary_recovered_candidates_reads_config(tmp_path) -> None:
    project_root = tmp_path / "project"
    config_dir = project_root / "config" / "market_intelligence"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "boundary_recovered_candidates.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-06-15",
                "items": [
                    {
                        "stock_code": "000338.SZ",
                        "marker": "boundary_recovered_candidate",
                        "note": "边界样本：需人工重点复核主题集中度。",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = BootstrapApiService(project_root=project_root)

    payload = service._load_market_boundary_recovered_candidates()

    assert payload == {
        "000338": {
            "special_markers": ["boundary_recovered_candidate"],
            "special_marker_notes": ["边界样本：需人工重点复核主题集中度。"],
        }
    }


def test_market_intelligence_recommendations_view_includes_special_marker_from_config(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    config_dir = project_root / "config" / "market_intelligence"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "boundary_recovered_candidates.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-06-15",
                "items": [
                    {
                        "stock_code": "000338",
                        "marker": "boundary_recovered_candidate",
                        "note": "边界样本：因补齐渗透率标注后恢复为推荐，需人工重点复核主题集中度。",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    service = BootstrapApiService(project_root=project_root)
    monkeypatch.setattr(
        service,
        "_market_intelligence_unified_candidates_payload",
        lambda *,
        top_n,
        stock_summary_cache=None,
        candidate_classified_snapshot=None,
        candidate_seed_snapshot=None: {
            "status": "ok",
            "candidates": [
                {
                    "stock_code": "000338",
                    "stock_name": "潍柴动力",
                    "candidate_types": ["institutional_attention", "trading_leader"],
                    "candidate_type_count": 2,
                    "primary_candidate_type": "institutional_attention",
                    "suggestion_bias": 2,
                    "thematic_tags": {
                        "ai_related": {"result": True},
                        "kshape_direction": {"value": "up"},
                        "penetration_stage": {"value": "1_10", "values": ["1_10"]},
                    },
                    "roles": {
                        "institutional_attention": {},
                        "trading_leader": {"best_concept_name": "数据中心"},
                    },
                }
            ],
        },
    )

    payload = service.market_intelligence_recommendations_view(top_n=10)

    assert payload["status"] == "ok"
    assert payload["items"][0]["stock_code"] == "000338"
    assert payload["items"][0]["recommendation_status"] == "推荐"
    assert payload["items"][0]["special_markers"] == [
        "boundary_recovered_candidate"
    ]
    assert payload["items"][0]["special_marker_notes"] == [
        "边界样本：因补齐渗透率标注后恢复为推荐，需人工重点复核主题集中度。"
    ]


def test_market_intelligence_review_board_view_combines_themes_and_recommendations(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.execute("INSERT INTO stocks(code, name) VALUES (?, ?)", ("300308", "中际旭创"))
        service._ensure_tushare_market_tables(conn=conn)
        service._ensure_ths_concept_daily_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO research_reports (
                trade_date, ts_code, name, title, report_type, author, inst_csname, ind_name, url, abstr, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "光模块龙头更新",
                "个股研报",
                "分析师A",
                "中信证券",
                "光模块",
                "https://example.com/report.pdf",
                "摘要",
                "tushare.research_report",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO report_consensus (
                report_date, ts_code, name, report_title, report_type, classify, org_name, author_name, quarter,
                op_rt, np, eps, pe, roe, rating, imp_dg, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "盈利预测更新",
                "一般报告",
                "一般报告",
                "中信证券",
                "分析师A",
                "2026Q4",
                100000.0,
                20000.0,
                1.2,
                22.5,
                15.3,
                "买入",
                "高",
                "tushare.report_rc",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO institutional_surveys (
                surv_date, ts_code, name, fund_visitors, rece_place, rece_mode, rece_org, org_type, comp_rece, content, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-11",
                "300308.SZ",
                "中际旭创",
                "张三",
                "电话会议",
                "特定对象调研",
                "高毅资产",
                "基金",
                "董秘",
                "调研摘要",
                "tushare.stk_surv",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO etf_basic_info (
                ts_code, csname, extname, index_code, index_name, list_date, list_status, exchange, mgr_name, etf_type, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "光伏ETF",
                "光伏ETF",
                "931151.CSI",
                "光伏指数",
                "2021-01-01",
                "L",
                "SH",
                "华夏基金",
                "境内",
                "tushare.etf_basic",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO fund_portfolios (
                ts_code, ann_date, end_date, symbol, mkv, amount, stk_mkv_ratio, stk_float_ratio, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "2026-05-31",
                "2026-03-31",
                "300308",
                500000.0,
                12000.0,
                8.5,
                1.2,
                "tushare.fund_portfolio",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "885976.TI",
                "光模块",
                "ths",
                10,
                8,
                2.1,
                0.6,
                123456789.0,
                3.2,
                0.1,
                "rising",
                "ok",
                91.5,
                2,
                88.1,
                82.4,
                79.0,
                95.0,
                1,
                5,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        _seed_daily_prices(conn, stock_code="300308")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {"885976.TI": "光模块"},
            {"885976.TI": ["300308"]},
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_market_penetration_stage_rules",
        lambda: [
            {
                "match_type": "keyword",
                "match_value": "光模块",
                "penetration_stage": "10_30",
                "reason": "光模块按 10-30 阶段处理",
                "scope": "theme",
            }
        ],
    )
    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: "2026-06-13")

    payload = service.market_intelligence_review_board_view(top_n=10)

    assert payload["status"] == "ok"
    assert payload["theme_summary"]["items"][0]["concept_code"] == "885976.TI"
    assert payload["candidate_summary"]["items"][0]["stock_code"] == "300308"
    assert payload["review_focus"]["theme"]["concept_code"] == "885976.TI"
    assert payload["review_focus"]["candidate"]["stock_code"] == "300308"
    assert payload["links"][0]["matched_themes"][0]["concept_name"] == "光模块"


def test_market_intelligence_review_board_view_suppresses_weak_broad_anchor_links(
    tmp_path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")
    service._lowfreq_latest_trade_date = lambda: "2026-06-13"  # type: ignore[attr-defined]
    service._market_intelligence_candidate_seed_snapshot = lambda **kwargs: {}  # type: ignore[method-assign]
    service._market_intelligence_theme_board_payload = lambda **kwargs: {  # type: ignore[method-assign]
        "status": "ok",
        "trade_date": "2026-06-13",
        "themes": [
            {"concept_code": "885756.TI", "concept_name": "芯片概念", "board_score": 41},
            {"concept_code": "885887.TI", "concept_name": "数据中心", "board_score": 45},
        ],
    }
    service._market_intelligence_recommendations_payload = lambda **kwargs: {  # type: ignore[method-assign]
        "status": "ok",
        "items": [
            {
                "stock_code": "000725",
                "stock_name": "京东方A",
                "recommendation_status": "观察",
                "leader_summary": {"candidate_types": ["institutional_attention", "trading_leader"]},
                "thematic_tags": {"penetration_stage": {"values": ["10_30"]}},
                "candidate": {
                    "roles": {
                        "institutional_attention": {},
                        "trading_leader": {"best_concept_name": "芯片概念"},
                    }
                },
            },
            {
                "stock_code": "000338",
                "stock_name": "潍柴动力",
                "recommendation_status": "推荐",
                "leader_summary": {"candidate_types": ["institutional_attention", "trading_leader"]},
                "thematic_tags": {"penetration_stage": {"values": ["10_30"]}},
                "candidate": {
                    "roles": {
                        "institutional_attention": {},
                        "trading_leader": {"best_concept_name": "数据中心"},
                    }
                },
            },
        ],
        "coverage": {"recommended": 1, "watchlist": 1, "avoid": 0},
    }

    payload = service.market_intelligence_review_board_view(top_n=10)

    assert payload["status"] == "ok"
    assert payload["links"][0]["stock_code"] == "000725"
    assert payload["links"][0]["matched_themes"] == []
    assert payload["links"][1]["stock_code"] == "000338"
    assert payload["links"][1]["matched_themes"][0]["concept_name"] == "数据中心"


def test_market_intelligence_review_board_view_propagates_special_markers(
    tmp_path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")
    service._lowfreq_latest_trade_date = lambda: "2026-06-13"  # type: ignore[attr-defined]
    service._market_intelligence_candidate_seed_snapshot = lambda **kwargs: {}  # type: ignore[method-assign]
    service._market_intelligence_theme_board_payload = lambda **kwargs: {  # type: ignore[method-assign]
        "status": "ok",
        "trade_date": "2026-06-13",
        "themes": [
            {"concept_code": "885887.TI", "concept_name": "数据中心", "board_score": 45},
        ],
    }
    service._market_intelligence_recommendations_payload = lambda **kwargs: {  # type: ignore[method-assign]
        "status": "ok",
        "items": [
            {
                "stock_code": "000338",
                "stock_name": "潍柴动力",
                "recommendation_status": "推荐",
                "leader_summary": {"candidate_types": ["institutional_attention", "trading_leader"]},
                "thematic_tags": {"penetration_stage": {"values": ["1_10"]}},
                "special_markers": ["boundary_recovered_candidate"],
                "special_marker_notes": [
                    "边界样本：因补齐渗透率标注后恢复为推荐，需人工重点复核主题集中度。"
                ],
                "candidate": {
                    "roles": {
                        "institutional_attention": {},
                        "trading_leader": {"best_concept_name": "数据中心"},
                    }
                },
            },
        ],
        "coverage": {"recommended": 1, "watchlist": 0, "avoid": 0},
    }

    payload = service.market_intelligence_review_board_view(top_n=10)

    assert payload["status"] == "ok"
    assert payload["links"][0]["stock_code"] == "000338"
    assert payload["links"][0]["special_markers"] == [
        "boundary_recovered_candidate"
    ]
    assert payload["links"][0]["special_marker_notes"] == [
        "边界样本：因补齐渗透率标注后恢复为推荐，需人工重点复核主题集中度。"
    ]
    assert payload["links"][0]["matched_themes"][0]["concept_name"] == "数据中心"


def test_market_intelligence_review_board_view_focus_candidate_prefers_focus_theme_match(
    tmp_path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")
    service._lowfreq_latest_trade_date = lambda: "2026-06-13"  # type: ignore[attr-defined]
    service._market_intelligence_candidate_seed_snapshot = lambda **kwargs: {}  # type: ignore[method-assign]
    service._market_intelligence_theme_board_payload = lambda **kwargs: {  # type: ignore[method-assign]
        "status": "ok",
        "trade_date": "2026-06-13",
        "themes": [
            {
                "concept_code": "885957.TI",
                "concept_name": "东数西算(算力)",
                "board_score": 99,
                "base_score": 38,
                "resonance_score": 61,
                "total_score": 99,
            },
            {
                "concept_code": "885908.TI",
                "concept_name": "第三代半导体",
                "board_score": 101,
                "base_score": 20,
                "resonance_score": 81,
                "total_score": 101,
            },
        ],
    }
    service._market_intelligence_recommendations_payload = lambda **kwargs: {  # type: ignore[method-assign]
        "status": "ok",
        "items": [
            {
                "stock_code": "002046",
                "stock_name": "国机精工",
                "recommendation_status": "推荐",
                "leader_summary": {"candidate_types": ["institutional_attention", "trading_leader"]},
                "thematic_tags": {"penetration_stage": {"values": ["10_30"]}},
                "candidate": {
                    "roles": {
                        "institutional_attention": {},
                        "trading_leader": {"best_concept_name": "第三代半导体"},
                    }
                },
            },
            {
                "stock_code": "002202",
                "stock_name": "金风科技",
                "recommendation_status": "推荐",
                "leader_summary": {"candidate_types": ["institutional_attention", "trading_leader"]},
                "thematic_tags": {"penetration_stage": {"values": ["1_10"]}},
                "candidate": {
                    "roles": {
                        "institutional_attention": {},
                        "trading_leader": {"best_concept_name": "东数西算(算力)"},
                    }
                },
            },
        ],
        "coverage": {"recommended": 2, "watchlist": 0, "avoid": 0},
    }

    payload = service.market_intelligence_review_board_view(top_n=10)

    assert payload["review_focus"]["theme"]["concept_name"] == "东数西算(算力)"
    assert payload["review_focus"]["candidate"]["stock_code"] == "002202"
    assert payload["candidate_summary"]["focus_candidate"]["stock_code"] == "002202"


def test_market_intelligence_review_board_view_focus_candidate_falls_back_without_theme_match(
    tmp_path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")
    service._lowfreq_latest_trade_date = lambda: "2026-06-13"  # type: ignore[attr-defined]
    service._market_intelligence_candidate_seed_snapshot = lambda **kwargs: {}  # type: ignore[method-assign]
    service._market_intelligence_theme_board_payload = lambda **kwargs: {  # type: ignore[method-assign]
        "status": "ok",
        "trade_date": "2026-06-13",
        "themes": [
            {
                "concept_code": "885957.TI",
                "concept_name": "东数西算(算力)",
                "board_score": 99,
                "base_score": 38,
                "resonance_score": 61,
                "total_score": 99,
            }
        ],
    }
    service._market_intelligence_recommendations_payload = lambda **kwargs: {  # type: ignore[method-assign]
        "status": "ok",
        "items": [
            {
                "stock_code": "002046",
                "stock_name": "国机精工",
                "recommendation_status": "推荐",
                "leader_summary": {"candidate_types": ["institutional_attention", "trading_leader"]},
                "thematic_tags": {"penetration_stage": {"values": ["10_30"]}},
                "candidate": {
                    "roles": {
                        "institutional_attention": {},
                        "trading_leader": {"best_concept_name": "第三代半导体"},
                    }
                },
            }
        ],
        "coverage": {"recommended": 1, "watchlist": 0, "avoid": 0},
    }

    payload = service.market_intelligence_review_board_view(top_n=10)

    assert payload["review_focus"]["theme"]["concept_name"] == "东数西算(算力)"
    assert payload["review_focus"]["candidate"]["stock_code"] == "002046"
    assert payload["candidate_summary"]["focus_candidate"]["stock_code"] == "002046"


def test_market_intelligence_review_board_view_reuses_classified_candidate_snapshot(
    tmp_path, monkeypatch
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")
    snapshot_payload = {
        "status": "ok",
        "top_n": 180,
        "config_leader_candidates": [{"stock_code": "000001"}],
        "institutional_attention_candidates": [{"stock_code": "000001"}],
        "trading_leader_candidates": [{"stock_code": "000001"}],
        "coverage": {"unique_seed_codes": 1},
    }
    calls: list[dict[str, Any]] = []

    def fake_candidates_payload(**kwargs) -> dict[str, Any]:
        calls.append(dict(kwargs))
        if kwargs.get("candidate_classified_snapshot") is not None:
            raise AssertionError("review-board should reuse prebuilt snapshot downstream")
        return snapshot_payload

    monkeypatch.setattr(
        service,
        "_market_intelligence_candidates_payload",
        fake_candidates_payload,
    )
    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: "2026-06-13")

    def fake_theme_board_payload(**kwargs) -> dict[str, Any]:
        assert kwargs.get("candidate_classified_snapshot") is snapshot_payload
        return {
            "status": "ok",
            "trade_date": "2026-06-13",
            "themes": [],
        }

    def fake_recommendations_payload(**kwargs) -> dict[str, Any]:
        assert kwargs.get("candidate_classified_snapshot") is snapshot_payload
        return {
            "status": "ok",
            "items": [],
            "coverage": {"recommended": 0, "watchlist": 0, "avoid": 0},
        }

    monkeypatch.setattr(
        service,
        "_market_intelligence_theme_board_payload",
        fake_theme_board_payload,
    )
    monkeypatch.setattr(
        service,
        "_market_intelligence_recommendations_payload",
        fake_recommendations_payload,
    )

    payload = service.market_intelligence_review_board_view(top_n=10)

    assert payload["status"] == "ok"
    assert len(calls) == 1
    assert calls[0]["top_n"] == 90


def test_market_intelligence_decision_summary_view_returns_structured_conclusions(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.execute("INSERT INTO stocks(code, name) VALUES (?, ?)", ("300308", "中际旭创"))
        service._ensure_tushare_market_tables(conn=conn)
        service._ensure_ths_concept_daily_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO research_reports (
                trade_date, ts_code, name, title, report_type, author, inst_csname, ind_name, url, abstr, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "光模块龙头更新",
                "个股研报",
                "分析师A",
                "中信证券",
                "光模块",
                "https://example.com/report.pdf",
                "摘要",
                "tushare.research_report",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO report_consensus (
                report_date, ts_code, name, report_title, report_type, classify, org_name, author_name, quarter,
                op_rt, np, eps, pe, roe, rating, imp_dg, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "盈利预测更新",
                "一般报告",
                "一般报告",
                "中信证券",
                "分析师A",
                "2026Q4",
                100000.0,
                20000.0,
                1.2,
                22.5,
                15.3,
                "买入",
                "高",
                "tushare.report_rc",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO institutional_surveys (
                surv_date, ts_code, name, fund_visitors, rece_place, rece_mode, rece_org, org_type, comp_rece, content, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-11",
                "300308.SZ",
                "中际旭创",
                "张三",
                "电话会议",
                "特定对象调研",
                "高毅资产",
                "基金",
                "董秘",
                "调研摘要",
                "tushare.stk_surv",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO etf_basic_info (
                ts_code, csname, extname, index_code, index_name, list_date, list_status, exchange, mgr_name, etf_type, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "光伏ETF",
                "光伏ETF",
                "931151.CSI",
                "光伏指数",
                "2021-01-01",
                "L",
                "SH",
                "华夏基金",
                "境内",
                "tushare.etf_basic",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO fund_portfolios (
                ts_code, ann_date, end_date, symbol, mkv, amount, stk_mkv_ratio, stk_float_ratio, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "2026-05-31",
                "2026-03-31",
                "300308",
                500000.0,
                12000.0,
                8.5,
                1.2,
                "tushare.fund_portfolio",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "885976.TI",
                "光模块",
                "ths",
                10,
                8,
                2.1,
                0.6,
                123456789.0,
                3.2,
                0.1,
                "rising",
                "ok",
                91.5,
                2,
                88.1,
                82.4,
                79.0,
                95.0,
                1,
                5,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        _seed_daily_prices(conn, stock_code="300308")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {"885976.TI": "光模块"},
            {"885976.TI": ["300308"]},
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_market_penetration_stage_rules",
        lambda: [
            {
                "match_type": "keyword",
                "match_value": "光模块",
                "penetration_stage": "10_30",
                "reason": "光模块按 10-30 阶段处理",
                "scope": "theme",
            }
        ],
    )
    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: "2026-06-13")

    payload = service.market_intelligence_decision_summary_view(top_n=10)

    assert payload["status"] == "ok"
    assert payload["summary"]["ai_focus"] == "focused"
    assert payload["summary"]["kshape_interference"] == "low"
    assert payload["counts"]["recommended"] >= 1
    assert payload["conclusions"]["recommendations_are_ai_focused"] is True
    assert payload["signals"]["focus_theme"]["concept_code"] == "885976.TI"
    assert payload["signals"]["focus_candidate"]["stock_code"] == "300308"


def test_market_intelligence_decision_summary_view_reuses_cached_review_board(
    tmp_path, monkeypatch
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")
    calls: list[tuple[int, str | None]] = []

    def fake_build_review_board(*, top_n: int, trade_date: str | None = None) -> dict[str, object]:
        calls.append((top_n, trade_date))
        return {
            "_meta": {"status": "ok"},
            "status": "ok",
            "top_n": top_n,
            "trade_date": trade_date or "2026-06-13",
            "theme_summary": {
                "items": [
                    {
                        "concept_code": "885976.TI",
                        "concept_name": "光模块",
                        "board_score": 9,
                        "base_score": 6,
                        "resonance_score": 3,
                        "total_score": 9,
                    }
                ]
            },
            "candidate_summary": {
                "items": [
                    {
                        "stock_code": "300308",
                        "stock_name": "中际旭创",
                        "recommendation_status": "推荐",
                        "thematic_tags": {
                            "ai_related": {"result": True},
                            "kshape_direction": {"value": "up"},
                        },
                    }
                ]
            },
            "review_focus": {
                "theme": {"concept_code": "885976.TI", "concept_name": "光模块"},
                "candidate": {"stock_code": "300308", "stock_name": "中际旭创"},
            },
            "links": [],
        }

    monkeypatch.setattr(
        service,
        "_build_market_intelligence_review_board_payload",
        fake_build_review_board,
    )

    review_payload = service.market_intelligence_review_board_view(
        top_n=10,
        trade_date="2026-06-13",
    )
    summary_payload = service.market_intelligence_decision_summary_view(
        top_n=10,
        trade_date="2026-06-13",
    )

    assert review_payload["status"] == "ok"
    assert summary_payload["status"] == "ok"
    assert summary_payload["signals"]["focus_candidate"]["stock_code"] == "300308"
    assert calls == [(10, "2026-06-13")]


def test_market_intelligence_review_board_inflight_is_shared_across_parallel_requests(
    tmp_path, monkeypatch
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")
    started = threading.Event()
    release = threading.Event()
    calls: list[tuple[int, str | None]] = []
    outputs: dict[str, dict[str, object]] = {}

    def fake_build_review_board(*, top_n: int, trade_date: str | None = None) -> dict[str, object]:
        calls.append((top_n, trade_date))
        started.set()
        assert release.wait(timeout=5)
        return {
            "_meta": {"status": "ok"},
            "status": "ok",
            "top_n": top_n,
            "trade_date": trade_date or "2026-06-13",
            "theme_summary": {
                "items": [
                    {
                        "concept_code": "885976.TI",
                        "concept_name": "光模块",
                        "board_score": 9,
                        "base_score": 6,
                        "resonance_score": 3,
                        "total_score": 9,
                    }
                ]
            },
            "candidate_summary": {
                "items": [
                    {
                        "stock_code": "300308",
                        "stock_name": "中际旭创",
                        "recommendation_status": "推荐",
                        "thematic_tags": {
                            "ai_related": {"result": True},
                            "kshape_direction": {"value": "up"},
                        },
                    }
                ]
            },
            "review_focus": {
                "theme": {"concept_code": "885976.TI", "concept_name": "光模块"},
                "candidate": {"stock_code": "300308", "stock_name": "中际旭创"},
            },
            "links": [],
        }

    monkeypatch.setattr(
        service,
        "_build_market_intelligence_review_board_payload",
        fake_build_review_board,
    )

    def load_review_board() -> None:
        outputs["review_board"] = service.market_intelligence_review_board_view(
            top_n=10,
            trade_date="2026-06-13",
        )

    def load_decision_summary() -> None:
        assert started.wait(timeout=5)
        outputs["decision_summary"] = service.market_intelligence_decision_summary_view(
            top_n=10,
            trade_date="2026-06-13",
        )

    review_thread = threading.Thread(target=load_review_board)
    summary_thread = threading.Thread(target=load_decision_summary)
    review_thread.start()
    summary_thread.start()
    release.set()
    review_thread.join(timeout=5)
    summary_thread.join(timeout=5)

    assert not review_thread.is_alive()
    assert not summary_thread.is_alive()
    assert calls == [(10, "2026-06-13")]
    assert outputs["review_board"]["status"] == "ok"
    assert outputs["decision_summary"]["status"] == "ok"


def test_market_intelligence_theme_board_view_aggregates_candidates_by_concept(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.execute("INSERT INTO stocks(code, name) VALUES (?, ?)", ("300308", "中际旭创"))
        service._ensure_tushare_market_tables(conn=conn)
        service._ensure_ths_concept_daily_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO research_reports (
                trade_date, ts_code, name, title, report_type, author, inst_csname, ind_name, url, abstr, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-12",
                "300308.SZ",
                "中际旭创",
                "光模块龙头更新",
                "个股研报",
                "分析师A",
                "中信证券",
                "光模块",
                "https://example.com/report.pdf",
                "摘要",
                "tushare.research_report",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO fund_portfolios (
                ts_code, ann_date, end_date, symbol, mkv, amount, stk_mkv_ratio, stk_float_ratio, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "2026-05-31",
                "2026-03-31",
                "300308",
                500000.0,
                12000.0,
                8.5,
                1.2,
                "tushare.fund_portfolio",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO etf_basic_info (
                ts_code, csname, extname, index_code, index_name, list_date, list_status, exchange, mgr_name, etf_type, source, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "515790.SH",
                "光伏ETF",
                "光伏ETF",
                "931151.CSI",
                "光模块指数",
                "2021-01-01",
                "L",
                "SH",
                "华夏基金",
                "境内",
                "tushare.etf_basic",
                "{}",
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "885976.TI",
                "光模块",
                "ths",
                10,
                8,
                2.1,
                0.6,
                123456789.0,
                3.2,
                0.1,
                "rising",
                "ok",
                91.5,
                2,
                88.1,
                82.4,
                79.0,
                95.0,
                1,
                5,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        _seed_daily_prices(conn, stock_code="300308")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {"885976.TI": "光模块"},
            {"885976.TI": ["300308"]},
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_market_penetration_stage_rules",
        lambda: [
            {
                "match_type": "keyword",
                "match_value": "光模块",
                "penetration_stage": "10_30",
                "reason": "光模块按 10-30 阶段处理",
                "scope": "theme",
            }
        ],
    )
    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: "2026-06-13")

    payload = service.market_intelligence_theme_board_view(top_n=5)

    assert payload["status"] == "ok"
    assert payload["themes"][0]["concept_code"] == "885976.TI"
    assert payload["themes"][0]["concept_name"] == "光模块"
    assert payload["themes"][0]["config_candidate_count"] == 1
    assert payload["themes"][0]["institutional_candidate_count"] == 1
    assert payload["themes"][0]["ths_mainline"]["mainline_rank"] == 1
    assert payload["themes"][0]["thematic_tags"]["ai_related"]["result"] is True
    assert payload["themes"][0]["thematic_tags"]["kshape_direction"]["value"] == "up"
    assert payload["themes"][0]["thematic_tags"]["penetration_stage"]["value"] == "10_30"
    assert payload["themes"][0]["suggestion_bias"] == 2
    assert payload["themes"][0]["base_score"] > 0
    assert payload["themes"][0]["resonance_score"] > 0
    assert payload["themes"][0]["total_score"] == payload["themes"][0]["board_score"]
    assert payload["themes"][0]["trading_candidate_count"] == 1
    assert payload["themes"][0]["trading_top_stocks"][0]["stock_code"] == "300308"


def test_market_intelligence_theme_board_view_normalizes_candidate_codes_for_concept_matching(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        service._ensure_ths_concept_daily_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "885921.TI",
                "显示面板",
                "ths",
                10,
                8,
                1.8,
                0.6,
                223456789.0,
                2.4,
                0.1,
                "rising",
                "ok",
                88.0,
                4,
                84.0,
                80.0,
                76.0,
                90.0,
                12,
                3,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_market_intelligence_candidates_payload",
        lambda *,
        top_n,
        stock_summary_cache=None,
        candidate_classified_snapshot=None,
        candidate_seed_snapshot=None: {
            "status": "ok",
            "config_leader_candidates": [
                {
                    "stock_code": "000725.SZ",
                    "stock_name": "京东方A",
                    "score": 3,
                    "holder_etf_count": 1,
                    "total_mkv": 100.0,
                    "thematic_tags": {"ai_related": {"result": True}},
                    "suggestion_bias": 2,
                }
            ],
            "institutional_attention_candidates": [
                {
                    "stock_code": "000725",
                    "stock_name": "京东方A",
                    "score": 2,
                    "consensus_orgs": 1,
                    "research_inst_90d": 1,
                    "survey_orgs_180d": 1,
                    "thematic_tags": {"ai_related": {"result": True}},
                    "suggestion_bias": 1,
                }
            ],
            "trading_leader_candidates": [
                {
                    "stock_code": "000725.SZ",
                    "stock_name": "京东方A",
                    "score": 1,
                    "latest_amount": 1000000.0,
                    "avg_turnover_5d": 2.5,
                    "thematic_tags": {"ai_related": {"result": True}},
                    "suggestion_bias": 1,
                }
            ],
            "coverage": {},
        },
    )
    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {"885921.TI": "显示面板"},
            {"885921.TI": ["000725"]},
        ),
    )
    monkeypatch.setattr(service, "_load_market_penetration_stage_rules", lambda: [])

    payload = service.market_intelligence_theme_board_view(
        top_n=10,
        trade_date="2026-06-13",
    )

    assert payload["status"] == "ok"
    assert len(payload["themes"]) == 1
    assert payload["themes"][0]["concept_name"] == "显示面板"
    assert payload["themes"][0]["config_candidate_count"] == 1
    assert payload["themes"][0]["institutional_candidate_count"] == 1
    assert payload["themes"][0]["trading_candidate_count"] == 1


def test_market_intelligence_theme_board_view_filters_generic_packaging_concepts(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.execute("INSERT INTO stocks(code, name) VALUES (?, ?)", ("300308", "中际旭创"))
        service._ensure_tushare_market_tables(conn=conn)
        service._ensure_ths_concept_daily_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "885976.TI",
                "光模块",
                "ths",
                10,
                8,
                2.1,
                0.6,
                123456789.0,
                3.2,
                0.1,
                "rising",
                "ok",
                91.5,
                2,
                88.1,
                82.4,
                79.0,
                95.0,
                3,
                5,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "883300.TI",
                "沪深300样本股",
                "ths",
                300,
                280,
                0.8,
                0.5,
                987654321.0,
                1.2,
                0.2,
                "consolidating",
                "ok",
                98.0,
                1,
                95.0,
                90.0,
                86.0,
                99.0,
                1,
                10,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        _seed_daily_prices(conn, stock_code="300308")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {
                "885976.TI": "光模块",
                "883300.TI": "沪深300样本股",
            },
            {
                "885976.TI": ["300308"],
                "883300.TI": ["300308"],
            },
        ),
    )
    monkeypatch.setattr(service, "_load_market_penetration_stage_rules", lambda: [])
    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: "2026-06-13")

    payload = service.market_intelligence_theme_board_view(top_n=10)

    concept_names = [item["concept_name"] for item in payload["themes"]]
    assert "光模块" in concept_names
    assert "沪深300样本股" not in concept_names


def test_market_intelligence_theme_board_view_filters_index_constituent_suffix_concepts(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.execute("INSERT INTO stocks(code, name) VALUES (?, ?)", ("300308", "中际旭创"))
        service._ensure_tushare_market_tables(conn=conn)
        service._ensure_ths_concept_daily_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "885976.TI",
                "光模块",
                "ths",
                10,
                8,
                2.1,
                0.6,
                123456789.0,
                3.2,
                0.1,
                "rising",
                "ok",
                91.5,
                2,
                88.1,
                82.4,
                79.0,
                95.0,
                3,
                5,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "000009.TI",
                "上证380成份股",
                "ths",
                180,
                160,
                0.9,
                0.5,
                456789123.0,
                1.1,
                0.2,
                "consolidating",
                "ok",
                97.0,
                4,
                93.0,
                89.0,
                85.0,
                98.0,
                5,
                10,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        _seed_daily_prices(conn, stock_code="300308")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {
                "885976.TI": "光模块",
                "000009.TI": "上证380成份股",
            },
            {
                "885976.TI": ["300308"],
                "000009.TI": ["300308"],
            },
        ),
    )
    monkeypatch.setattr(service, "_load_market_penetration_stage_rules", lambda: [])
    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: "2026-06-13")

    payload = service.market_intelligence_theme_board_view(top_n=10)

    concept_names = [item["concept_name"] for item in payload["themes"]]
    assert "光模块" in concept_names
    assert "上证380成份股" not in concept_names


def test_market_intelligence_theme_board_view_penalizes_exit_risk_in_theme_ranking(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO stocks(code, name) VALUES (?, ?)",
            [
                ("300308", "中际旭创"),
                ("300309", "吉艾科技"),
            ],
        )
        service._ensure_tushare_market_tables(conn=conn)
        service._ensure_ths_concept_daily_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "885976.TI",
                "光模块",
                "ths",
                10,
                8,
                2.1,
                0.6,
                123456789.0,
                3.2,
                0.1,
                "rising",
                "exit",
                95.0,
                1,
                90.0,
                85.0,
                80.0,
                98.0,
                1,
                5,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "886044.TI",
                "液冷服务器",
                "ths",
                12,
                9,
                1.8,
                0.55,
                223456789.0,
                2.4,
                0.1,
                "rising",
                "ok",
                88.0,
                5,
                84.0,
                80.0,
                76.0,
                90.0,
                40,
                3,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        _seed_daily_prices(conn, stock_code="300308")
        _seed_daily_prices(conn, stock_code="300309")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {
                "885976.TI": "光模块",
                "886044.TI": "液冷服务器",
            },
            {
                "885976.TI": ["300308"],
                "886044.TI": ["300309"],
            },
        ),
    )
    monkeypatch.setattr(service, "_load_market_penetration_stage_rules", lambda: [])
    monkeypatch.setattr(service, "_lowfreq_latest_trade_date", lambda: "2026-06-13")

    payload = service.market_intelligence_theme_board_view(top_n=10)

    assert payload["themes"][0]["concept_name"] == "液冷服务器"
    assert payload["themes"][0]["ths_mainline"]["risk_level"] == "ok"
    assert payload["themes"][1]["concept_name"] == "光模块"
    assert payload["themes"][1]["ths_mainline"]["risk_level"] == "exit"


def test_market_intelligence_theme_board_view_prioritizes_base_score_over_resonance(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        service._ensure_ths_concept_daily_tables(conn=conn)
        conn.executemany(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-06-13",
                    "100001.TI",
                    "稳定主线",
                    "ths",
                    10,
                    8,
                    2.1,
                    0.6,
                    123456789.0,
                    3.2,
                    0.1,
                    "rising",
                    "ok",
                    91.5,
                    2,
                    88.1,
                    82.4,
                    79.0,
                    95.0,
                    1,
                    5,
                    "2026-06-13T10:00:00+00:00",
                ),
                (
                    "2026-06-13",
                    "100002.TI",
                    "高共振赛道",
                    "ths",
                    12,
                    9,
                    1.4,
                    0.5,
                    223456789.0,
                    2.1,
                    0.2,
                    "consolidating",
                    "ok",
                    84.0,
                    18,
                    80.0,
                    76.0,
                    72.0,
                    88.0,
                    20,
                    3,
                    "2026-06-13T10:00:00+00:00",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {"100001.TI": "稳定主线", "100002.TI": "高共振赛道"},
            {
                "100001.TI": ["000001"],
                "100002.TI": ["000002", "000003", "000004"],
            },
        ),
    )
    monkeypatch.setattr(service, "_load_market_penetration_stage_rules", lambda: [])
    monkeypatch.setattr(
        service,
        "_market_intelligence_candidates_payload",
        lambda *,
        top_n,
        stock_summary_cache=None,
        candidate_classified_snapshot=None,
        candidate_seed_snapshot=None: {
            "status": "ok",
            "config_leader_candidates": [
                {"stock_code": "000001", "score": 1, "suggestion_bias": 2},
                {"stock_code": "000002", "score": 3, "suggestion_bias": 2},
                {"stock_code": "000003", "score": 3, "suggestion_bias": 2},
                {"stock_code": "000004", "score": 3, "suggestion_bias": 2},
            ],
            "institutional_attention_candidates": [
                {"stock_code": "000002", "score": 2, "suggestion_bias": 2},
                {"stock_code": "000003", "score": 2, "suggestion_bias": 2},
                {"stock_code": "000004", "score": 2, "suggestion_bias": 2},
            ],
            "trading_leader_candidates": [
                {"stock_code": "000002", "score": 2, "suggestion_bias": 2},
                {"stock_code": "000003", "score": 2, "suggestion_bias": 2},
                {"stock_code": "000004", "score": 2, "suggestion_bias": 2},
            ],
            "coverage": {},
        },
    )

    payload = service.market_intelligence_theme_board_view(
        top_n=10,
        trade_date="2026-06-13",
    )

    assert payload["status"] == "ok"
    assert payload["themes"][0]["concept_name"] == "稳定主线"
    assert payload["themes"][0]["base_score"] > payload["themes"][1]["base_score"]
    assert (
        payload["themes"][0]["resonance_score"]
        < payload["themes"][1]["resonance_score"]
    )


def test_market_intelligence_review_board_view_focus_theme_prioritizes_base_score(
    tmp_path,
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")
    service._lowfreq_latest_trade_date = lambda: "2026-06-13"  # type: ignore[attr-defined]
    service._market_intelligence_candidate_seed_snapshot = lambda **kwargs: {}  # type: ignore[method-assign]
    service._market_intelligence_theme_board_payload = lambda **kwargs: {  # type: ignore[method-assign]
        "status": "ok",
        "trade_date": "2026-06-13",
        "themes": [
            {
                "concept_code": "100002.TI",
                "concept_name": "高共振赛道",
                "board_score": 80,
                "base_score": 40,
                "resonance_score": 40,
                "total_score": 80,
                "suggestion_bias": 2,
            },
            {
                "concept_code": "100001.TI",
                "concept_name": "稳定主线",
                "board_score": 72,
                "base_score": 60,
                "resonance_score": 12,
                "total_score": 72,
                "suggestion_bias": 2,
            },
        ],
    }
    service._market_intelligence_recommendations_payload = lambda **kwargs: {  # type: ignore[method-assign]
        "status": "ok",
        "items": [],
        "coverage": {"recommended": 0, "watchlist": 0, "avoid": 0},
    }

    payload = service.market_intelligence_review_board_view(top_n=10)

    assert payload["status"] == "ok"
    assert payload["theme_summary"]["items"][0]["concept_name"] == "高共振赛道"
    assert payload["review_focus"]["theme"]["concept_name"] == "稳定主线"
    assert payload["review_focus"]["theme"]["base_score"] == 60


def test_resolve_market_penetration_for_theme_defaults_to_unknown(
    tmp_path, monkeypatch
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")
    monkeypatch.setattr(service, "_load_market_penetration_stage_rules", lambda: [])

    payload = service._resolve_market_penetration_for_theme(
        concept_code="999999.TI",
        concept_name="普通概念",
    )

    assert payload["value"] == "unknown"
    assert payload["values"] == ["unknown"]
    assert payload["is_multi"] is False


def test_market_intelligence_candidates_view_returns_trading_candidates_from_daily_prices(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.execute("INSERT INTO stocks(code, name) VALUES (?, ?)", ("300308", "中际旭创"))
        service._ensure_tushare_market_tables(conn=conn)
        service._ensure_ths_concept_daily_tables(conn=conn)
        conn.execute(
            """
            INSERT INTO ths_concept_daily (
                trade_date, concept_code, concept_name, provider,
                member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                leader_avg_pct, follower_weakness, trend_state, risk_level,
                heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                mainline_score, mainline_rank, mainline_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-13",
                "885976.TI",
                "光模块",
                "ths",
                10,
                8,
                2.1,
                0.6,
                123456789.0,
                3.2,
                0.1,
                "rising",
                "ok",
                91.5,
                2,
                88.1,
                82.4,
                79.0,
                95.0,
                1,
                5,
                "2026-06-13T10:00:00+00:00",
            ),
        )
        _seed_daily_prices(conn, stock_code="300308")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {"885976.TI": "光模块"},
            {"885976.TI": ["300308"]},
        ),
    )
    monkeypatch.setattr(service, "_load_market_penetration_stage_rules", lambda: [])

    payload = service.market_intelligence_candidates_view(top_n=5)

    assert payload["status"] == "ok"
    assert payload["trading_leader_candidates"][0]["stock_code"] == "300308"
    assert payload["coverage"]["trading_seed_codes"] >= 1


def test_select_market_best_leading_concept_prefers_ai_theme_and_skips_packaging(
    tmp_path, monkeypatch
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")

    def fake_theme_tags(*, concept_code: str, concept_name: str) -> dict[str, object]:
        ai_related = concept_name in {"第三代半导体", "光模块", "算力租赁"}
        kshape_value = "up" if ai_related else "unknown"
        return {
            "ai_related": {"result": ai_related},
            "kshape_direction": {"value": kshape_value},
        }

    monkeypatch.setattr(
        service,
        "_derive_market_thematic_tags_for_theme",
        fake_theme_tags,
    )

    best = service._select_market_best_leading_concept(
        leading_concepts=[
            {
                "concept_code": "883300.TI",
                "concept_name": "沪深300样本股",
                "mainline_rank": 1,
                "heat_rank": 1,
                "mainline_score": 99.0,
            },
            {
                "concept_code": "999001.TI",
                "concept_name": "高端装备",
                "mainline_rank": 2,
                "heat_rank": 2,
                "mainline_score": 95.0,
            },
            {
                "concept_code": "885908.TI",
                "concept_name": "第三代半导体",
                "mainline_rank": 3,
                "heat_rank": 3,
                "mainline_score": 90.0,
            },
        ]
    )

    assert best["concept_name"] == "第三代半导体"


def test_market_intelligence_candidates_view_best_concept_name_uses_later_ai_concept(
    tmp_path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"

    service = BootstrapApiService(project_root=project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.execute("INSERT INTO stocks(code, name) VALUES (?, ?)", ("300308", "中际旭创"))
        service._ensure_tushare_market_tables(conn=conn)
        service._ensure_ths_concept_daily_tables(conn=conn)
        concept_rows = [
            ("883300.TI", "沪深300样本股", 1, 1, 99.0, "ok"),
            ("991111.TI", "高端装备", 2, 2, 95.0, "ok"),
            ("992222.TI", "智能医疗", 3, 3, 94.0, "ok"),
            ("885908.TI", "第三代半导体", 4, 4, 90.0, "ok"),
        ]
        for concept_code, concept_name, mainline_rank, heat_rank, mainline_score, risk_level in concept_rows:
            conn.execute(
                """
                INSERT INTO ths_concept_daily (
                    trade_date, concept_code, concept_name, provider,
                    member_count, valid_count, avg_pct_change, adv_ratio, total_amount,
                    leader_avg_pct, follower_weakness, trend_state, risk_level,
                    heat_score, heat_rank, heat_ma20, heat_ma60, heat_ma90,
                    mainline_score, mainline_rank, mainline_streak, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-06-13",
                    concept_code,
                    concept_name,
                    "ths",
                    10,
                    8,
                    2.1,
                    0.6,
                    123456789.0,
                    3.2,
                    0.1,
                    "rising",
                    risk_level,
                    91.5,
                    heat_rank,
                    88.1,
                    82.4,
                    79.0,
                    mainline_score,
                    mainline_rank,
                    5,
                    "2026-06-13T10:00:00+00:00",
                ),
            )
        _seed_daily_prices(conn, stock_code="300308")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        service,
        "_load_ths_concept_caches",
        lambda: (
            {
                "883300.TI": "沪深300样本股",
                "991111.TI": "高端装备",
                "992222.TI": "智能医疗",
                "885908.TI": "第三代半导体",
            },
            {
                "883300.TI": ["300308"],
                "991111.TI": ["300308"],
                "992222.TI": ["300308"],
                "885908.TI": ["300308"],
            },
        ),
    )
    monkeypatch.setattr(service, "_load_market_penetration_stage_rules", lambda: [])

    payload = service.market_intelligence_candidates_view(top_n=5)

    assert payload["status"] == "ok"
    assert payload["trading_leader_candidates"][0]["stock_code"] == "300308"
    assert payload["trading_leader_candidates"][0]["best_concept_name"] == "第三代半导体"


def test_select_market_best_leading_concept_deprioritizes_broad_chip_concept(
    tmp_path, monkeypatch
) -> None:
    service = BootstrapApiService(project_root=tmp_path / "project")

    def fake_theme_tags(*, concept_code: str, concept_name: str) -> dict[str, object]:
        ai_related = concept_name in {"芯片概念", "汽车芯片"}
        return {
            "ai_related": {"result": ai_related},
            "kshape_direction": {"value": "up" if ai_related else "unknown"},
        }

    monkeypatch.setattr(
        service,
        "_derive_market_thematic_tags_for_theme",
        fake_theme_tags,
    )

    best = service._select_market_best_leading_concept(
        leading_concepts=[
            {
                "concept_code": "885756.TI",
                "concept_name": "芯片概念",
                "mainline_rank": 1,
                "heat_rank": 1,
                "mainline_score": 99.0,
            },
            {
                "concept_code": "886041.TI",
                "concept_name": "汽车芯片",
                "mainline_rank": 4,
                "heat_rank": 4,
                "mainline_score": 90.0,
            },
        ]
    )

    assert best["concept_name"] == "汽车芯片"
