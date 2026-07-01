from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from apps.api.main import BootstrapApiService
from apps.api.shared import ApiError


class _StubAdapter:
    def __init__(self, *, rows: list[dict], configured: bool = True) -> None:
        self._rows = rows
        self.configured = configured
        self.last_code = 0 if configured else "request_error"
        self.last_api_name = None
        self.last_msg = None
        self.token_fingerprint = "stub-token"

    def fetch_company_announcements(self, **kwargs):
        return list(self._rows)

    def fetch_policy_documents(self, **kwargs):
        return list(self._rows)

    def fetch_research_reports(self, **kwargs):
        return list(self._rows)

    def fetch_report_consensus(self, **kwargs):
        return list(self._rows)

    def fetch_institutional_surveys(self, **kwargs):
        return list(self._rows)

    def fetch_etf_basic(self, **kwargs):
        return list(self._rows)

    def fetch_fund_daily(self, **kwargs):
        return list(self._rows)

    def fetch_etf_share_size(self, **kwargs):
        return list(self._rows)

    def fetch_etf_index(self, **kwargs):
        return list(self._rows)

    def fetch_fund_basic(self, **kwargs):
        return list(self._rows)

    def fetch_fund_portfolio(self, **kwargs):
        return list(self._rows)

    def fetch_index_announcements(self, **kwargs):
        return list(self._rows)

    def fetch_index_weight(self, **kwargs):
        return list(self._rows)


def _make_service(tmp_path: Path) -> BootstrapApiService:
    project_root = tmp_path / "project"
    db_dir = project_root / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(str(db_dir / "stock_data.db")).close()
    return BootstrapApiService(project_root=project_root)


def test_sync_tushare_market_data_view_dry_run_returns_sample(tmp_path, monkeypatch) -> None:
    service = _make_service(tmp_path)
    monkeypatch.setattr(
        service,
        "_tushare_market_adapter",
        lambda timeout_seconds=20: _StubAdapter(
            rows=[
                {
                    "ann_date": "20260613",
                    "ts_code": "000001.SZ",
                    "name": "平安银行",
                    "title": "测试公告",
                    "url": "https://example.com/a.pdf",
                    "rec_time": "2026-06-13 19:00:00",
                }
            ]
        ),
    )

    result = service.sync_tushare_market_data_view(
        resource="company_announcements",
        requested_by="unit.test",
        filters={"ann_date": "20260613"},
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["rows_prepared"] == 1
    assert result["sample"][0]["title"] == "测试公告"


def test_sync_tushare_market_data_view_persists_announcements(tmp_path, monkeypatch) -> None:
    service = _make_service(tmp_path)
    monkeypatch.setattr(
        service,
        "_tushare_market_adapter",
        lambda timeout_seconds=20: _StubAdapter(
            rows=[
                {
                    "ann_date": "20260613",
                    "ts_code": "000001.SZ",
                    "name": "平安银行",
                    "title": "年度报告",
                    "url": "https://example.com/annual.pdf",
                    "rec_time": "2026-06-13 19:00:00",
                }
            ]
        ),
    )

    result = service.sync_tushare_market_data_view(
        resource="company_announcements",
        requested_by="unit.test",
        filters={"ann_date": "20260613"},
        dry_run=False,
    )

    assert result["status"] == "ok"
    assert result["rows_upserted"] == 1

    db_path = tmp_path / "project" / "var" / "db" / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT code, ts_code, stock_name, title, publish_date, source FROM announcements"
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        "000001",
        "000001.SZ",
        "平安银行",
        "年度报告",
        "2026-06-13",
        "tushare.anns_d",
    )


def test_sync_tushare_market_data_view_hard_fails_when_unique_tushare_source_empty(
    tmp_path, monkeypatch
) -> None:
    service = _make_service(tmp_path)
    monkeypatch.setattr(
        service,
        "_tushare_market_adapter",
        lambda timeout_seconds=20: _StubAdapter(rows=[]),
    )

    with pytest.raises(ApiError) as exc_info:
        service.sync_tushare_market_data_view(
            resource="company_announcements",
            requested_by="unit.test",
            filters={"ann_date": "20260613"},
            dry_run=False,
        )

    assert exc_info.value.code == "authoritative_source_unavailable"
    assert exc_info.value.details["resource"] == "company_announcements"
