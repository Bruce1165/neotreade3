from __future__ import annotations

from datetime import datetime
import os
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo

from apps.api.main import BootstrapApiService


def _parts(value: str) -> list[str]:
    return [p.strip() for p in str(value or "").split(",") if p.strip()]


def test_ensure_no_proxy_includes_localhost_and_targets(monkeypatch) -> None:
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    BootstrapApiService._ensure_no_proxy(hosts=["api.waditu.com", "api.tushare.pro"])

    no_proxy = os.environ.get("NO_PROXY") or ""
    parts = _parts(no_proxy)
    assert "127.0.0.1" in parts
    assert "localhost" in parts
    assert "api.waditu.com" in parts
    assert "api.tushare.pro" in parts
    assert os.environ.get("no_proxy") == no_proxy


def test_ensure_no_proxy_is_idempotent(monkeypatch) -> None:
    monkeypatch.setenv("NO_PROXY", "api.waditu.com,localhost")
    monkeypatch.delenv("no_proxy", raising=False)

    BootstrapApiService._ensure_no_proxy(hosts=["api.waditu.com", "api.tushare.pro"])
    BootstrapApiService._ensure_no_proxy(hosts=["api.waditu.com", "api.tushare.pro"])

    parts = _parts(os.environ.get("NO_PROXY") or "")
    assert parts.count("api.waditu.com") == 1
    assert parts.count("api.tushare.pro") == 1
    assert parts.count("localhost") == 1
    assert parts.count("127.0.0.1") == 1


def test_daily_pipeline_falls_back_to_tushare_when_target_date_missing(monkeypatch, tmp_path) -> None:
    db_path = Path(tmp_path) / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE daily_prices (trade_date TEXT)")
        conn.execute("CREATE TABLE trading_calendar_cache (trade_date TEXT)")
        conn.execute("INSERT INTO trading_calendar_cache (trade_date) VALUES (?)", ("2026-06-08",))
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))

    svc = BootstrapApiService(project_root=str(Path(__file__).resolve().parents[2]))

    def fake_authoritative(*, target_date: str, requested_by: str, dry_run: bool, **kwargs):
        return {
            "_meta": {"status": "ok"},
            "status": "ok",
            "fallback_used": False,
            "authoritative_update": {
                "tushare_update": {
                    "trade_date": "2026-06-07",
                    "calendar_is_trading_day": True,
                    "quality_gate": {"passed": True},
                    "format_gate": {"passed": True},
                    "db_upserted": 0,
                }
            },
        }

    def fake_backfill(*, start_date: str, end_date: str, requested_by: str, dry_run: bool = False, **kwargs):
        assert start_date == "2026-06-08"
        assert end_date == "2026-06-08"
        return {
            "_meta": {"status": "ok"},
            "status": "ok",
            "ok_days": 1,
            "failed_days": 0,
            "skipped_days": 0,
            "rows_upserted_total": 4819,
            "results_sample": [{"trade_date": "2026-06-08", "status": "ok", "gate_reasons": []}],
        }

    monkeypatch.setattr(svc, "update_daily_prices_authoritative_view", fake_authoritative)
    monkeypatch.setattr(svc, "backfill_daily_prices_tushare_range_view", fake_backfill)
    monkeypatch.setattr(BootstrapApiService, "_is_market_closed_cn", classmethod(lambda cls, *, target_trade_date: True))
    monkeypatch.setattr(svc, "tushare_concept_health_view", lambda *, requested_by: {"ok": True, "elapsed_ms": 0.0, "checks": {}, "errors": []})
    monkeypatch.setattr(svc, "refresh_team_theme_snapshot_view", lambda *, target_date, requested_by="api": {"snapshot_path": "x"})
    monkeypatch.setattr(svc, "ths_concept_mainline_compute_view", lambda *, trade_date, requested_by, top_n=10: {"status": "ok", "trade_date": trade_date, "concept_count": 0, "top_mainline": [], "reason": None})
    monkeypatch.setattr(svc, "screeners_bulk_run_view", lambda **kwargs: {"_meta": {"status": "ok"}})
    monkeypatch.setattr(svc, "lowfreq_confidence_daily_run_view", lambda **kwargs: {"date": "2026-06-08", "market_regime": "unknown", "observations_written": 0, "labels_updated": 0, "buckets_written": 0})
    monkeypatch.setattr(svc, "lowfreq_backtest_run_view", lambda **kwargs: {"pdf_url": None, "summary": {}})
    monkeypatch.setattr(svc, "lowfreq_daily_auto_optimize_view", lambda **kwargs: {"run_id": "x", "selected_overrides": {}, "effective_from": "2026-06-08"})
    monkeypatch.setattr(svc, "_write_daily_run_ledger", lambda *, target_date, payload: str(Path(tmp_path) / f"{target_date}.json"))
    monkeypatch.setattr("apps.api.main.time.sleep", lambda *_args, **_kwargs: None)

    out = svc.daily_pipeline_run_view(target_date="2026-06-08", requested_by="test")
    ledger = out.get("ledger") or {}
    steps = ledger.get("steps") or []
    step_ids = [s.get("step_id") for s in steps if isinstance(s, dict)]
    assert "authoritative_update" in step_ids
    assert "tushare_backfill" in step_ids


def test_update_daily_prices_authoritative_prefers_tushare(monkeypatch, tmp_path) -> None:
    db_path = Path(tmp_path) / "stock_data.db"
    sqlite3.connect(str(db_path)).close()
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    svc = BootstrapApiService(project_root=str(Path(__file__).resolve().parents[2]))

    calls = {"tencent": 0}

    def fake_tushare(**kwargs):
        return {
            "_meta": {"status": "ok"},
            "tushare_update": {
                "quality_gate": {"passed": True, "gate_reasons": []},
                "format_gate": {"passed": True, "gate_reasons": []},
            },
            "backfill": {"status": "ok", "format_gate": {"passed": True, "gate_reasons": []}},
        }

    def fake_tencent(**kwargs):
        calls["tencent"] += 1
        return {"tencent_update": {"quality_gate": {"passed": True}}}

    monkeypatch.setattr(svc, "update_daily_prices_tushare_view", fake_tushare)
    monkeypatch.setattr(svc, "update_daily_prices_tencent_view", fake_tencent)

    out = svc.update_daily_prices_authoritative_view(
        target_date="2026-06-16",
        requested_by="unit.test",
        dry_run=False,
    )

    assert out["fallback_used"] is False
    assert out["retry_window_used"] is False
    assert out["retry_attempts"] == 0
    assert calls["tencent"] == 0


def test_update_daily_prices_tushare_rebuilds_trading_calendar_ledger(monkeypatch, tmp_path) -> None:
    db_path = Path(tmp_path) / "stock_data.db"
    sqlite3.connect(str(db_path)).close()
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    svc = BootstrapApiService(project_root=str(Path(__file__).resolve().parents[2]))

    rebuild_calls: list[dict[str, str]] = []

    monkeypatch.setattr(svc, "_ensure_daily_price_capture_tables", lambda conn: None)
    monkeypatch.setattr(svc, "_ensure_daily_price_publish_batch_table", lambda conn: None)
    monkeypatch.setattr(
        BootstrapApiService,
        "_is_market_closed_cn",
        classmethod(lambda cls, *, target_trade_date: True),
    )
    monkeypatch.setattr(
        svc,
        "_calendar_membership",
        lambda conn, target_date: ("trading_calendar_cache", True),
    )
    monkeypatch.setattr(
        svc,
        "_backfill_daily_prices_from_tushare_daily",
        lambda **kwargs: {
            "status": "ok",
            "coverage": {"close": 1.0, "open": 1.0, "amount": 1.0, "turnover": 0.5},
            "format_gate": {"passed": True, "gate_reasons": []},
            "db_upserted": 4819,
            "before_rows": 0,
            "after_rows": 4819,
            "volume_normalized_rows": 0,
        },
    )

    def fake_rebuild(**kwargs):
        rebuild_calls.append(kwargs)
        return {
            "_meta": {"status": "ok"},
            "trading_calendar": {
                "generated_by": kwargs["requested_by"],
                "trading_day_count": 123,
            },
        }

    monkeypatch.setattr(svc, "rebuild_trading_calendar_view", fake_rebuild)

    out = svc.update_daily_prices_tushare_view(
        target_date="2026-06-16",
        requested_by="unit.test",
        dry_run=False,
    )

    assert len(rebuild_calls) == 1
    assert rebuild_calls[0]["sqlite_db_path"] == str(db_path)
    assert rebuild_calls[0]["table"] == "daily_prices"
    assert rebuild_calls[0]["date_column"] == "trade_date"
    assert out["tushare_update"]["trading_calendar"]["trading_day_count"] == 123


def test_daily_pipeline_records_failed_screeners_bulk_run_status(monkeypatch, tmp_path) -> None:
    db_path = Path(tmp_path) / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE daily_prices (trade_date TEXT)")
        conn.execute("CREATE TABLE trading_calendar_cache (trade_date TEXT)")
        conn.execute("INSERT INTO trading_calendar_cache (trade_date) VALUES (?)", ("2026-06-08",))
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    svc = BootstrapApiService(project_root=str(Path(__file__).resolve().parents[2]))

    monkeypatch.setattr(
        svc,
        "update_daily_prices_authoritative_view",
        lambda **kwargs: {
            "_meta": {"status": "ok"},
            "status": "ok",
            "fallback_used": False,
            "authoritative_update": {
                "tushare_update": {
                    "trade_date": "2026-06-08",
                    "calendar_is_trading_day": True,
                    "quality_gate": {"passed": True},
                    "format_gate": {"passed": True},
                    "db_upserted": 4819,
                }
            },
        },
    )
    monkeypatch.setattr(
        BootstrapApiService,
        "_is_market_closed_cn",
        classmethod(lambda cls, *, target_trade_date: True),
    )
    monkeypatch.setattr(
        svc,
        "tushare_concept_health_view",
        lambda *, requested_by: {"ok": True, "elapsed_ms": 0.0, "checks": {}, "errors": []},
    )
    monkeypatch.setattr(
        svc,
        "refresh_team_theme_snapshot_view",
        lambda *, target_date, requested_by="api": {"snapshot_path": "x"},
    )
    monkeypatch.setattr(
        svc,
        "ths_concept_mainline_compute_view",
        lambda *, trade_date, requested_by, top_n=10: {
            "status": "ok",
            "trade_date": trade_date,
            "concept_count": 0,
            "top_mainline": [],
            "reason": None,
        },
    )
    monkeypatch.setattr(
        svc,
        "screeners_bulk_run_view",
        lambda **kwargs: {
            "_meta": {"status": "failed"},
            "status": "failed",
            "bulk_run": {"status": "failed", "run_count": 6},
        },
    )
    monkeypatch.setattr(
        svc,
        "lowfreq_confidence_daily_run_view",
        lambda **kwargs: {
            "date": "2026-06-08",
            "market_regime": "unknown",
            "observations_written": 0,
            "labels_updated": 0,
            "buckets_written": 0,
        },
    )
    monkeypatch.setattr(svc, "lowfreq_backtest_run_view", lambda **kwargs: {"pdf_url": None, "summary": {}})
    monkeypatch.setattr(
        svc,
        "lowfreq_daily_auto_optimize_view",
        lambda **kwargs: {"run_id": "x", "selected_overrides": {}, "effective_from": "2026-06-08"},
    )
    monkeypatch.setattr(
        svc,
        "_write_daily_run_ledger",
        lambda *, target_date, payload: str(Path(tmp_path) / f"{target_date}.json"),
    )

    out = svc.daily_pipeline_run_view(target_date="2026-06-08", requested_by="test")
    steps = out["ledger"]["steps"]
    bulk_step = next(step for step in steps if step["step_id"] == "screeners_bulk_run")
    assert bulk_step["status"] == "failed"
    assert bulk_step["outputs"]["status"] == "failed"
    assert bulk_step["outputs"]["run_count"] == 6


def test_lowfreq_hot_sectors_view_caches_lightweight_ths_concept_payload(monkeypatch) -> None:
    svc = BootstrapApiService(project_root=str(Path(__file__).resolve().parents[2]))
    calls = {"count": 0}

    monkeypatch.setattr(svc, "_lowfreq_engine_v16", lambda: object())

    def fake_build(**kwargs):
        calls["count"] += 1
        return {"_meta": {"status": "ok"}, "sectors": [{"name": "机器人"}]}

    monkeypatch.setattr(svc, "_build_ths_concepts_hot_snapshot", fake_build)

    first = svc.lowfreq_hot_sectors_view(
        target_date="2026-06-18",
        mode="ths_concept",
        include_portfolio=False,
        include_sell_signal=False,
    )
    second = svc.lowfreq_hot_sectors_view(
        target_date="2026-06-18",
        mode="ths_concept",
        include_portfolio=False,
        include_sell_signal=False,
    )

    assert calls["count"] == 1
    assert first["sectors"][0]["name"] == "机器人"
    assert second["sectors"][0]["name"] == "机器人"


def test_build_ths_concepts_hot_snapshot_does_not_force_recompute(monkeypatch) -> None:
    svc = BootstrapApiService(project_root=str(Path(__file__).resolve().parents[2]))

    monkeypatch.setattr(
        svc,
        "ths_concept_mainline_compute_view",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("should not force compute before mainline view")
        ),
    )
    monkeypatch.setattr(
        svc,
        "ths_concept_mainline_view",
        lambda **kwargs: {"concepts": [], "trade_date": "2026-06-18"},
    )
    monkeypatch.setattr(svc, "_load_ths_concept_caches", lambda: ({}, {}))
    monkeypatch.setattr(svc, "_load_stock_metrics_for_codes", lambda **kwargs: {})
    monkeypatch.setattr(svc, "_load_lowfreq_sim_state", lambda: {})

    engine = type(
        "DummyEngine",
        (),
        {
            "MARKET_CAP_MIN": 20_000_000_000.0,
            "MARKET_CAP_MAX": 50_000_000_000.0,
            "get_global_candidates": lambda self, **kwargs: [],
        },
    )()
    payload = svc._build_ths_concepts_hot_snapshot(
        engine=engine,
        target_date=datetime(2026, 6, 18).date(),
        include_portfolio=False,
        include_sell_signal=False,
        perf={},
    )

    assert payload["sectors"] == []


def test_update_daily_prices_authoritative_uses_tencent_as_safety_net(monkeypatch, tmp_path) -> None:
    db_path = Path(tmp_path) / "stock_data.db"
    sqlite3.connect(str(db_path)).close()
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    svc = BootstrapApiService(project_root=str(Path(__file__).resolve().parents[2]))

    calls = {"tencent": 0, "tushare": 0}

    def fake_tushare(**kwargs):
        calls["tushare"] += 1
        return {
            "_meta": {"status": "ok"},
            "tushare_update": {
                "quality_gate": {"passed": False, "gate_reasons": ["tushare_daily_failed"]},
                "format_gate": {"passed": False, "gate_reasons": ["tushare_daily_format_invalid"]},
            },
            "backfill": {"status": "skipped", "reason": "tushare_daily_failed"},
        }

    def fake_tencent(**kwargs):
        calls["tencent"] += 1
        return {"tencent_update": {"quality_gate": {"passed": True}}}

    monkeypatch.setattr(svc, "update_daily_prices_tushare_view", fake_tushare)
    monkeypatch.setattr(svc, "update_daily_prices_tencent_view", fake_tencent)
    monkeypatch.setattr("apps.api.main.time.sleep", lambda *_args, **_kwargs: None)

    out = svc.update_daily_prices_authoritative_view(
        target_date="2026-06-16",
        requested_by="unit.test",
        dry_run=False,
    )

    assert out["fallback_used"] is True
    assert out["fallback_provider"] == "tencent"
    assert out["retry_window_used"] is False
    assert out["retry_attempts"] == 0
    assert calls["tushare"] == 1
    assert calls["tencent"] == 1


def test_update_daily_prices_authoritative_retries_no_rows_within_window(monkeypatch, tmp_path) -> None:
    db_path = Path(tmp_path) / "stock_data.db"
    sqlite3.connect(str(db_path)).close()
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    svc = BootstrapApiService(project_root=str(Path(__file__).resolve().parents[2]))

    calls = {"tencent": 0, "tushare": 0}
    sleep_calls: list[float] = []

    responses = [
        {
            "_meta": {"status": "ok"},
            "tushare_update": {
                "quality_gate": {"passed": False, "gate_reasons": ["tushare_has_no_rows_for_target_date"]},
                "format_gate": {"passed": False, "gate_reasons": []},
            },
            "backfill": {"status": "skipped", "reason": "tushare_has_no_rows_for_target_date"},
        },
        {
            "_meta": {"status": "ok"},
            "tushare_update": {
                "quality_gate": {"passed": True, "gate_reasons": []},
                "format_gate": {"passed": True, "gate_reasons": []},
            },
            "backfill": {"status": "ok"},
        },
    ]

    def fake_tushare(**kwargs):
        idx = calls["tushare"]
        calls["tushare"] += 1
        return responses[idx]

    def fake_tencent(**kwargs):
        calls["tencent"] += 1
        return {"tencent_update": {"quality_gate": {"passed": True}}}

    retry_now = datetime(2026, 6, 18, 15, 45, tzinfo=ZoneInfo("Asia/Shanghai"))
    monkeypatch.setattr(BootstrapApiService, "_now_cn", staticmethod(lambda: retry_now))
    monkeypatch.setattr(svc, "update_daily_prices_tushare_view", fake_tushare)
    monkeypatch.setattr(svc, "update_daily_prices_tencent_view", fake_tencent)
    monkeypatch.setattr("apps.api.main.time.sleep", lambda seconds: sleep_calls.append(seconds))

    out = svc.update_daily_prices_authoritative_view(
        target_date="2026-06-18",
        requested_by="unit.test",
        dry_run=False,
    )

    assert out["fallback_used"] is False
    assert out["retry_window_used"] is True
    assert out["retry_attempts"] == 1
    assert out["retry_deadline"].endswith("16:00:00+08:00")
    assert calls["tushare"] == 2
    assert calls["tencent"] == 0
    assert sleep_calls == [180.0]


def test_update_daily_prices_authoritative_falls_back_after_retry_deadline(monkeypatch, tmp_path) -> None:
    db_path = Path(tmp_path) / "stock_data.db"
    sqlite3.connect(str(db_path)).close()
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    svc = BootstrapApiService(project_root=str(Path(__file__).resolve().parents[2]))

    calls = {"tencent": 0, "tushare": 0}
    sleep_calls: list[float] = []
    clock_values = iter(
        [
            datetime(2026, 6, 18, 15, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
            datetime(2026, 6, 18, 15, 45, tzinfo=ZoneInfo("Asia/Shanghai")),
            datetime(2026, 6, 18, 15, 48, tzinfo=ZoneInfo("Asia/Shanghai")),
            datetime(2026, 6, 18, 15, 51, tzinfo=ZoneInfo("Asia/Shanghai")),
            datetime(2026, 6, 18, 15, 54, tzinfo=ZoneInfo("Asia/Shanghai")),
            datetime(2026, 6, 18, 15, 57, tzinfo=ZoneInfo("Asia/Shanghai")),
        ]
    )

    def fake_tushare(**kwargs):
        calls["tushare"] += 1
        return {
            "_meta": {"status": "ok"},
            "tushare_update": {
                "quality_gate": {"passed": False, "gate_reasons": ["tushare_has_no_rows_for_target_date"]},
                "format_gate": {"passed": False, "gate_reasons": []},
            },
            "backfill": {"status": "skipped", "reason": "tushare_has_no_rows_for_target_date"},
        }

    def fake_tencent(**kwargs):
        calls["tencent"] += 1
        return {"tencent_update": {"quality_gate": {"passed": True}}}

    monkeypatch.setattr(BootstrapApiService, "_now_cn", staticmethod(lambda: next(clock_values)))
    monkeypatch.setattr(svc, "update_daily_prices_tushare_view", fake_tushare)
    monkeypatch.setattr(svc, "update_daily_prices_tencent_view", fake_tencent)
    monkeypatch.setattr("apps.api.main.time.sleep", lambda seconds: sleep_calls.append(seconds))

    out = svc.update_daily_prices_authoritative_view(
        target_date="2026-06-18",
        requested_by="unit.test",
        dry_run=False,
    )

    assert out["fallback_used"] is True
    assert out["fallback_provider"] == "tencent"
    assert out["retry_window_used"] is True
    assert out["retry_attempts"] == 5
    assert out["primary_final_reason"] == "tushare_has_no_rows_for_target_date"
    assert calls["tushare"] == 6
    assert calls["tencent"] == 1
    assert sleep_calls == [180.0, 180.0, 180.0, 180.0, 180.0]
