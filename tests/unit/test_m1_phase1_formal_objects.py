from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from apps.api.main import BootstrapApiService
from apps.api.router import BootstrapApiRouter
from apps.worker.main import BootstrapWorkerApp
from neotrade3.data_control.pipeline import DataControlPipeline
from neotrade3.data_control.projections import project_pf1_trading_profile
from neotrade3.issue_center import IssueCenterCollector
from neotrade3.orchestration.preflight import PreflightRunner
from tests._support.screeners_config import prepare_screeners_config_root


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _prepare_preflight_project_root(*, project_root: Path) -> None:
    (project_root / "config/data_control").mkdir(parents=True, exist_ok=True)
    (project_root / "config/labs").mkdir(parents=True, exist_ok=True)
    (project_root / "config/orchestrator").mkdir(parents=True, exist_ok=True)
    (project_root / "var/db").mkdir(parents=True, exist_ok=True)
    (project_root / "var/ledgers/trading_calendar").mkdir(parents=True, exist_ok=True)
    (project_root / "config/data_control/source_registry.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (project_root / "config/labs/labs_registry.json").write_text("{}", encoding="utf-8")
    (project_root / "config/orchestrator/daily_master_orchestrator.json").write_text(
        "{}",
        encoding="utf-8",
    )
    _, isolated_registry_path = prepare_screeners_config_root(
        tmp_path=project_root,
        screener_ids=[],
    )
    isolated_registry_path.write_text("{}", encoding="utf-8")
    (project_root / "var/db/stock_data.db").write_text("", encoding="utf-8")
    (project_root / "var/ledgers/trading_calendar/trading_calendar.json").write_text(
        json.dumps({"trading_days": ["2026-07-07"]}),
        encoding="utf-8",
    )


def _seed_m1_phase1_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT,
                asset_type TEXT,
                is_delisted INTEGER,
                sector_lv1 TEXT,
                sector_lv2 TEXT,
                last_trade_date TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE daily_prices (
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
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
        conn.execute("CREATE TABLE trading_calendar_cache (trade_date TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE trading_calendar_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            """
            INSERT INTO stocks(code, name, asset_type, is_delisted, sector_lv1, sector_lv2, last_trade_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("000001", "平安银行", "stock", 0, "金融", "银行", "2026-07-07"),
        )
        conn.execute(
            """
            INSERT INTO stocks(code, name, asset_type, is_delisted, sector_lv1, sector_lv2, last_trade_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("000002", "万科A", "stock", 0, "地产", "开发", "2026-07-07"),
        )

        target = date(2026, 7, 7)
        calendar_start = (target - timedelta(days=19)).isoformat()
        calendar_end = target.isoformat()
        conn.execute(
            "INSERT INTO trading_calendar_meta(key, value) VALUES (?, ?)",
            ("calendar_source", "trading_calendar_cache"),
        )
        conn.execute(
            "INSERT INTO trading_calendar_meta(key, value) VALUES (?, ?)",
            ("calendar_covered_from", calendar_start),
        )
        conn.execute(
            "INSERT INTO trading_calendar_meta(key, value) VALUES (?, ?)",
            ("calendar_covered_until", calendar_end),
        )
        for i in range(20):
            trade_date = (target - timedelta(days=i)).isoformat()
            conn.execute(
                "INSERT INTO trading_calendar_cache(trade_date) VALUES (?)",
                (trade_date,),
            )
            conn.execute(
                """
                INSERT INTO daily_prices(
                    code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "000001",
                    trade_date,
                    10.0 + i,
                    10.5 + i,
                    9.8 + i,
                    10.2 + i,
                    1000000.0 + i,
                    20000000.0 + i * 1000.0,
                    3.0 + i * 0.1,
                    10.0 + i,
                    0.5,
                    "2026-07-07T15:00:00Z",
                ),
            )
            if i < 4:
                conn.execute(
                    """
                    INSERT INTO daily_prices(
                        code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "000002",
                        trade_date,
                        20.0 + i,
                        20.5 + i,
                        19.8 + i,
                        20.2 + i,
                        500000.0 + i,
                        10000000.0 + i * 500.0,
                        1.5 + i * 0.1,
                        20.0 + i,
                        -0.2,
                        "2026-07-07T15:00:00Z",
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def test_project_pf1_trading_profile_requires_full_windows() -> None:
    rows = [
        {
            "trade_date": "2026-07-07",
            "close": 10.0,
            "amount": 100.0 + i,
            "turnover": 1.0 + i,
            "pct_change": 0.1,
        }
        for i in range(4)
    ]

    profile = project_pf1_trading_profile(stock_code="000001", price_rows=rows)

    assert profile is not None
    assert profile.latest_amount == 100.0
    assert profile.avg_amount_5d is None
    assert profile.avg_amount_20d is None
    assert profile.return_20d is None
    assert profile.positive_days_5d is None


def test_m1_phase1_router_exposes_formal_object_endpoints(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    _seed_m1_phase1_db(db_path)
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))

    service = BootstrapApiService(project_root=PROJECT_ROOT)
    router = BootstrapApiRouter(service)

    d1_status, d1_payload = router.dispatch(
        "/api/data-control/m1/d1/daily-price-facts?date=2026-07-07&codes=000001"
    )
    d7_status, d7_payload = router.dispatch(
        "/api/data-control/m1/d7/security-master?codes=000001"
    )
    td_status, td_payload = router.dispatch(
        "/api/data-control/m1/d7/trading-day-status?date=2026-07-07"
    )
    d8_status, d8_payload = router.dispatch(
        "/api/data-control/m1/d8/trading-profiles?date=2026-07-07&codes=000001,000002"
    )

    assert d1_status == 200
    assert d1_payload["count"] == 1
    assert d1_payload["items"][0]["stock_code"] == "000001"
    assert "close_price" in d1_payload["items"][0]
    assert "amount_cny" in d1_payload["items"][0]

    assert d7_status == 200
    assert d7_payload["count"] == 1
    assert d7_payload["items"][0]["stock_name"] == "平安银行"
    assert d7_payload["items"][0]["asset_type"] == "stock"

    assert td_status == 200
    assert td_payload["item"]["target_date"] == "2026-07-07"
    assert td_payload["item"]["is_trading_day"] is True
    assert td_payload["freshness_proof"]["verdict"] == "ready"

    assert d8_status == 200
    assert d8_payload["count"] == 2
    items_by_code = {item["stock_code"]: item for item in d8_payload["items"]}
    assert items_by_code["000001"]["avg_amount_20d"] is not None
    assert items_by_code["000001"]["return_20d"] is not None
    assert items_by_code["000002"]["avg_amount_5d"] is None
    assert items_by_code["000002"]["avg_amount_20d"] is None
    assert d8_payload["quality_status"]["coverage_status"] == "partial"
    assert d8_payload["freshness_proof"]["verdict"] == "partial"
    assert d8_payload["_meta"]["compatibility_mode"] == "formal_only"


def test_data_control_view_exposes_formal_contract_boundaries(monkeypatch) -> None:
    service = BootstrapApiService(project_root=PROJECT_ROOT)

    def _fake_snapshot(*, target_date: date, publish_succeeded: bool, write_outputs: bool) -> dict[str, object]:
        assert write_outputs is False
        return {
            "target_date": target_date.isoformat(),
            "_meta": {"status": "ok"},
            "data_control": {"status": "stubbed"},
        }

    monkeypatch.setattr(service, "build_snapshot", _fake_snapshot)

    payload = service.data_control_view(target_date=date(2026, 7, 7))

    assert "m1_formal_contracts" in payload
    assert (
        payload["m1_formal_contracts"]["formal_entrypoints"]["pf1_trading_profile"]
        == "/api/data-control/m1/d8/trading-profiles"
    )
    assert "/api/signals" in payload["m1_formal_contracts"]["compatibility_only_paths"]
    assert payload["compatibility_boundaries"]["required_formal_entrypoints"][0].startswith(
        "/api/data-control/m1/"
    )


def test_data_control_pipeline_writes_m1_formal_artifacts(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    _seed_m1_phase1_db(db_path)
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    monkeypatch.setattr(
        DataControlPipeline, "_project_root", staticmethod(lambda: tmp_path)
    )

    pipeline = DataControlPipeline()
    target = date(2026, 7, 7)
    pipeline.capture(target_date=target, dry_run=False)
    pipeline.compose(target_date=target, dry_run=False)
    pipeline.publish(target_date=target, dry_run=False)

    capture_ledger = tmp_path / "var/ledgers/data_control/2026-07-07/data_control_capture_ledger.json"
    compose_ledger = tmp_path / "var/ledgers/data_control/2026-07-07/data_control_compose_ledger.json"
    publish_ledger = tmp_path / "var/ledgers/data_control/2026-07-07/data_control_publish_ledger.json"

    capture_payload = json.loads(capture_ledger.read_text(encoding="utf-8"))
    compose_payload = json.loads(compose_ledger.read_text(encoding="utf-8"))
    publish_payload = json.loads(publish_ledger.read_text(encoding="utf-8"))

    assert capture_payload["m1_formal_artifacts"]["status"] == "ok"
    assert compose_payload["m1_formal_artifacts"]["summary"]["d1_daily_price_fact"]["freshness_verdict"] == "ready"
    assert publish_payload["m1_formal_artifacts"]["summary"]["pf1_trading_profile"]["freshness_verdict"] in {
        "ready",
        "partial",
    }


def test_worker_stage_summary_surfaces_formal_artifacts(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "stock_data.db"
    _seed_m1_phase1_db(db_path)
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    monkeypatch.setattr(
        DataControlPipeline, "_project_root", staticmethod(lambda: tmp_path)
    )

    pipeline = DataControlPipeline()
    target = date(2026, 7, 7)
    pipeline.capture(target_date=target, dry_run=False)
    pipeline.compose(target_date=target, dry_run=False)

    worker = BootstrapWorkerApp(project_root=tmp_path)
    summary = worker._load_data_control_stage_summary(target)

    compose_stage = summary["stages"]["compose"]
    assert compose_stage["m1_formal_artifacts"]["d1_daily_price_fact"]["freshness_verdict"] == "ready"
    assert "pf1_trading_profile" in compose_stage["m1_formal_artifacts"]


def test_issue_center_collects_m1_formal_artifact_degradation() -> None:
    collector = IssueCenterCollector(project_root=PROJECT_ROOT)
    snapshot = collector.collect(
        date(2026, 7, 7),
        task_results=[],
        task_entries=[],
        data_control_stage_summary={
            "target_date": "2026-07-07",
            "stages": {
                "compose": {
                    "m1_formal_artifacts": {
                        "pf1_trading_profile": {
                            "freshness_verdict": "partial",
                            "attention_count": 1,
                        }
                    }
                }
            },
        },
    )

    assert snapshot.events
    assert any(event.source == "data_control.m1_formal_artifacts" for event in snapshot.events)
    assert any(case.task_id == "data_control.compose.m1_formal.pf1_trading_profile" for case in snapshot.cases)


def test_preflight_skips_formal_contract_gating_without_same_day_artifacts(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path
    _prepare_preflight_project_root(project_root=project_root)
    monkeypatch.setattr(PreflightRunner, "_project_root", staticmethod(lambda: project_root))

    report = PreflightRunner().build_report(date(2026, 7, 7))
    by_id = {check.check_id: check for check in report.checks}

    assert by_id["m1_formal_contract_check"].status.value == "passed"
    assert "skip M1 formal readiness gating" in by_id["m1_formal_contract_check"].details


def test_preflight_fails_when_existing_formal_artifacts_are_not_ready(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path
    (project_root / "var/ledgers/data_control/2026-07-07").mkdir(parents=True, exist_ok=True)
    _prepare_preflight_project_root(project_root=project_root)
    (project_root / "var/ledgers/data_control/2026-07-07/data_control_publish_ledger.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "message": "ok",
                "m1_formal_artifacts": {
                    "summary": {
                        "pf1_trading_profile": {
                            "freshness_verdict": "not_ready",
                            "attention_count": 1,
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(PreflightRunner, "_project_root", staticmethod(lambda: project_root))

    report = PreflightRunner().build_report(date(2026, 7, 7))
    by_id = {check.check_id: check for check in report.checks}

    assert by_id["m1_formal_contract_check"].status.value == "failed"
    assert "pf1_trading_profile=not_ready" in by_id["m1_formal_contract_check"].details
