from __future__ import annotations

import json
import logging
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from apps.api.main import BootstrapApiService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPS_ALERT_SENTINEL = {"status": "skipped", "reason": "alert_webhook_not_configured"}


def _seed_db(tmp_path: Path, *, calendar_dates=(), price_dates=()) -> Path:
    db_path = Path(tmp_path) / "stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE daily_prices (trade_date TEXT)")
        conn.execute("CREATE TABLE trading_calendar_cache (trade_date TEXT)")
        conn.executemany(
            "INSERT INTO trading_calendar_cache (trade_date) VALUES (?)",
            [(str(d),) for d in calendar_dates],
        )
        conn.executemany(
            "INSERT INTO daily_prices (trade_date) VALUES (?)",
            [(str(d),) for d in price_dates],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _capture_ops_alerts(monkeypatch, svc) -> list[dict]:
    calls: list[dict] = []

    def fake_send_ops_alert(*, title, payload, severity="error", timeout_seconds=8):
        calls.append({"title": title, "payload": payload, "severity": severity})
        return dict(OPS_ALERT_SENTINEL)

    monkeypatch.setattr(svc, "_send_ops_alert", fake_send_ops_alert)
    return calls


# ---------------------------------------------------------------------------
# D2-1 ledger forensics
# ---------------------------------------------------------------------------


def test_write_daily_run_ledger_writes_latest_and_archive_copy(tmp_path) -> None:
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    svc._daily_runs_dir = Path(tmp_path) / "daily_runs"
    payload = {
        "version": 1,
        "target_date": "2026-07-24",
        "started_at": "2026-07-24T02:51:00Z",
        "steps": [],
    }

    path = svc._write_daily_run_ledger(target_date="2026-07-24", payload=payload)

    latest = Path(tmp_path) / "daily_runs" / "2026-07-24.json"
    archive = Path(tmp_path) / "daily_runs" / "archive" / "2026-07-24_20260724T025100Z.json"
    assert path == str(latest)
    assert latest.is_file()
    assert archive.is_file()
    assert archive.read_text(encoding="utf-8") == latest.read_text(encoding="utf-8")
    assert json.loads(archive.read_text(encoding="utf-8"))["started_at"] == "2026-07-24T02:51:00Z"


def test_write_daily_run_ledger_archive_failure_does_not_break_main_write(tmp_path, caplog) -> None:
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    svc._daily_runs_dir = Path(tmp_path) / "daily_runs"
    # Pre-create "archive" as a regular file so archive mkdir must fail.
    svc._daily_runs_dir.mkdir(parents=True, exist_ok=True)
    (svc._daily_runs_dir / "archive").write_text("block", encoding="utf-8")
    payload = {"version": 1, "target_date": "2026-07-24", "started_at": "2026-07-24T02:51:00Z"}

    with caplog.at_level(logging.WARNING, logger="apps.api.main"):
        path = svc._write_daily_run_ledger(target_date="2026-07-24", payload=payload)

    assert Path(path).is_file()
    assert "daily_run_ledger_archive_write_failed" in caplog.text


# ---------------------------------------------------------------------------
# D1-3 alert channel visibility
# ---------------------------------------------------------------------------


def test_send_ops_alert_logs_warning_when_webhook_missing(monkeypatch, caplog) -> None:
    # 服务构造时会把 env.secrets 载入 os.environ；必须在构造之后再删键，
    # 否则本机 secrets 里真实配置的 webhook 会让用例误发真实告警。
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    monkeypatch.delenv("NEOTRADE3_ALERT_WEBHOOK_URL", raising=False)

    with caplog.at_level(logging.WARNING, logger="apps.api.main"):
        out = svc._send_ops_alert(title="daily_pipeline_test_alert", payload={"k": "v"})

    assert out == OPS_ALERT_SENTINEL
    assert "ops_alert_skipped_no_webhook: daily_pipeline_test_alert" in caplog.text


def test_send_ops_alert_logs_exception_when_delivery_fails(monkeypatch, caplog) -> None:
    monkeypatch.setenv("NEOTRADE3_ALERT_WEBHOOK_URL", "http://127.0.0.1:9/webhook")

    def _boom(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))

    with caplog.at_level(logging.ERROR, logger="apps.api.main"):
        out = svc._send_ops_alert(title="t", payload={})

    assert out["status"] == "failed"
    assert out["error_type"] == "OSError"
    assert "ops_alert_delivery_failed" in caplog.text


def test_send_ops_alert_serverchan_branch_uses_form_encoding(monkeypatch) -> None:
    monkeypatch.setenv(
        "NEOTRADE3_ALERT_WEBHOOK_URL",
        "https://sctapi.ftqq.com/SCTTESTKEY.send",
    )
    captured: dict = {}

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"code":0}'

    def _fake_urlopen(req, timeout=0):
        captured["content_type"] = req.headers.get("Content-type")
        captured["body"] = req.data.decode("utf-8")
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    out = svc._send_ops_alert(title="链路测试", payload={"k": "v"}, severity="warning")

    assert out["status"] == "ok"
    assert captured["content_type"] == "application/x-www-form-urlencoded"
    from urllib.parse import parse_qs

    form = parse_qs(captured["body"])
    assert form["title"] == ["链路测试"]
    assert "severity: `warning`" in form["desp"][0]
    assert '"k": "v"' in form["desp"][0]


def test_daily_pipeline_records_ops_alert_when_trading_day_check_fails(monkeypatch, tmp_path) -> None:
    db_path = _seed_db(tmp_path)
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    alert_calls = _capture_ops_alerts(monkeypatch, svc)

    def _raise_td(*, target_date):
        raise RuntimeError("calendar_broken")

    monkeypatch.setattr(svc, "trading_day_view", _raise_td)
    written: dict = {}

    def _capture_ledger(*, target_date, payload):
        written["payload"] = payload
        return str(tmp_path / "x.json")

    monkeypatch.setattr(svc, "_write_daily_run_ledger", _capture_ledger)

    out = svc.daily_pipeline_run_view(target_date="2026-06-08", requested_by="test")

    assert out["_meta"]["status"] == "failed"
    assert [c["title"] for c in alert_calls] == ["daily_pipeline_trading_day_check_failed"]
    step = next(s for s in out["ledger"]["steps"] if s["step_id"] == "trading_day_check")
    assert step["status"] == "failed"
    assert step["outputs"]["ops_alert"] == OPS_ALERT_SENTINEL
    # The alert result must already be inside the payload handed to the ledger writer.
    written_step = next(s for s in written["payload"]["steps"] if s["step_id"] == "trading_day_check")
    assert written_step["outputs"]["ops_alert"] == OPS_ALERT_SENTINEL


# ---------------------------------------------------------------------------
# D1-4 meta status honesty (+ D1-3c recording at acquisition failure)
# ---------------------------------------------------------------------------


def test_daily_pipeline_early_exit_marks_meta_failed_and_records_ops_alert(monkeypatch, tmp_path) -> None:
    db_path = _seed_db(tmp_path, calendar_dates=["2026-06-08"])
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    alert_calls = _capture_ops_alerts(monkeypatch, svc)

    def _always_fail_authoritative(**kwargs):
        raise RuntimeError("tushare_down")

    monkeypatch.setattr(svc, "update_daily_prices_authoritative_view", _always_fail_authoritative)
    monkeypatch.setattr(
        BootstrapApiService,
        "_is_market_closed_cn",
        classmethod(lambda cls, *, target_trade_date: True),
    )
    monkeypatch.setattr(
        svc,
        "backfill_daily_prices_tushare_range_view",
        lambda **kwargs: {
            "_meta": {"status": "ok"},
            "status": "ok",
            "ok_days": 0,
            "failed_days": 1,
            "skipped_days": 0,
            "rows_upserted_total": 0,
            "results_sample": [{"trade_date": "2026-06-08", "status": "failed", "reason": "tushare_down"}],
        },
    )
    monkeypatch.setattr(
        svc,
        "_write_daily_run_ledger",
        lambda *, target_date, payload: str(tmp_path / f"{target_date}.json"),
    )
    monkeypatch.setattr("apps.api.main.time.sleep", lambda *_args, **_kwargs: None)

    out = svc.daily_pipeline_run_view(target_date="2026-06-08", requested_by="test")

    assert out["_meta"]["status"] == "failed"
    titles = [c["title"] for c in alert_calls]
    assert "authoritative_daily_prices_update_failed" in titles
    assert "daily_pipeline_acquisition_failed" in titles
    steps = {s["step_id"]: s for s in out["ledger"]["steps"]}
    assert steps["authoritative_update"]["status"] == "failed"
    assert steps["authoritative_update"]["outputs"]["ops_alert"] == OPS_ALERT_SENTINEL
    assert steps["tushare_backfill"]["status"] == "failed"
    assert steps["tushare_backfill"]["outputs"]["ops_alert"] == OPS_ALERT_SENTINEL


def test_daily_pipeline_early_exit_keeps_meta_ok_without_acquisition_failure(monkeypatch, tmp_path) -> None:
    db_path = _seed_db(tmp_path, calendar_dates=["2026-06-08"])
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    alert_calls = _capture_ops_alerts(monkeypatch, svc)

    # Non-trading-day style outcome: acquisition step ok but publish gate not met
    # and no backfill applicable (market still open) -> early exit stays ok.
    monkeypatch.setattr(
        svc,
        "update_daily_prices_authoritative_view",
        lambda **kwargs: {
            "_meta": {"status": "ok"},
            "status": "ok",
            "fallback_used": False,
            "authoritative_update": {
                "tushare_update": {
                    "trade_date": "2026-06-05",
                    "calendar_is_trading_day": False,
                    "quality_gate": {"passed": True},
                    "format_gate": {"passed": True},
                    "db_upserted": 0,
                }
            },
        },
    )
    monkeypatch.setattr(
        BootstrapApiService,
        "_is_market_closed_cn",
        classmethod(lambda cls, *, target_trade_date: False),
    )
    monkeypatch.setattr(
        svc,
        "_write_daily_run_ledger",
        lambda *, target_date, payload: str(tmp_path / f"{target_date}.json"),
    )
    monkeypatch.setattr("apps.api.main.time.sleep", lambda *_args, **_kwargs: None)

    out = svc.daily_pipeline_run_view(target_date="2026-06-08", requested_by="test")

    assert out["_meta"]["status"] == "ok"
    assert alert_calls == []


# ---------------------------------------------------------------------------
# D1-6 fallback degradation warning
# ---------------------------------------------------------------------------


def test_update_daily_prices_authoritative_logs_warning_on_fallback(monkeypatch, tmp_path, caplog) -> None:
    db_path = _seed_db(tmp_path)
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))

    monkeypatch.setattr(
        svc,
        "update_daily_prices_tushare_view",
        lambda **kwargs: {
            "_meta": {"status": "ok"},
            "tushare_update": {
                "quality_gate": {"passed": False, "gate_reasons": ["tushare_daily_failed"]},
                "format_gate": {"passed": False, "gate_reasons": ["tushare_daily_format_invalid"]},
            },
            "backfill": {"status": "skipped", "reason": "tushare_daily_failed"},
        },
    )
    monkeypatch.setattr(
        svc,
        "update_daily_prices_tencent_view",
        lambda **kwargs: {"tencent_update": {"quality_gate": {"passed": True}}},
    )
    monkeypatch.setattr("apps.api.main.time.sleep", lambda *_args, **_kwargs: None)

    with caplog.at_level(logging.WARNING, logger="apps.api.main"):
        out = svc.update_daily_prices_authoritative_view(
            target_date="2026-06-16",
            requested_by="unit.test",
            dry_run=False,
        )

    assert out["fallback_used"] is True
    assert "daily_prices fallback_used=true primary_final_reason=" in caplog.text
    assert "target=2026-06-16" in caplog.text


# ---------------------------------------------------------------------------
# D1-7 health probe honesty
# ---------------------------------------------------------------------------


class _FakeConcept:
    def __init__(self, code: str, name: str) -> None:
        self.code = code
        self.name = name


class _FakeTushareConceptAdapter:
    configured = True
    errors: list = []

    def fetch_all_concepts(self):
        return [_FakeConcept("TS1", "概念一")]

    def fetch_concept_stocks(self, *, concept_code, limit=5):
        return [_FakeConcept("000001.SZ", "平安银行")]


def _patch_health_adapter(monkeypatch) -> None:
    monkeypatch.setattr(
        "neotrade3.data_sources.tushare_concept_adapter.TushareConceptAdapter",
        _FakeTushareConceptAdapter,
    )


def test_tushare_concept_health_includes_importable_check_when_package_present(monkeypatch) -> None:
    pytest.importorskip("tushare")
    _patch_health_adapter(monkeypatch)
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))

    out = svc.tushare_concept_health_view(requested_by="unit.test")

    assert out["checks"]["tushare_package_importable"] is True
    assert out["ok"] is True


def test_tushare_concept_health_fails_when_package_not_importable(monkeypatch) -> None:
    _patch_health_adapter(monkeypatch)
    monkeypatch.setitem(sys.modules, "tushare", None)
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))

    out = svc.tushare_concept_health_view(requested_by="unit.test")

    assert out["checks"]["tushare_package_importable"] is False
    assert out["ok"] is False


# ---------------------------------------------------------------------------
# D2-3 skipped-days visibility
# ---------------------------------------------------------------------------


def test_backfill_range_logs_warning_with_skip_reasons(monkeypatch, tmp_path, caplog) -> None:
    db_path = _seed_db(tmp_path, calendar_dates=["2026-06-08"])
    monkeypatch.setenv("NEOTRADE3_STOCK_DB_PATH", str(db_path))
    monkeypatch.setenv("TUSHARE_TOKEN", "unit-test-token")
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    monkeypatch.setattr(svc, "_ensure_daily_price_capture_tables", lambda conn: None)
    monkeypatch.setattr(svc, "_ensure_daily_price_publish_batch_table", lambda conn: None)
    monkeypatch.setattr(
        svc,
        "_backfill_daily_prices_from_tushare_daily",
        lambda **kwargs: {
            "status": "skipped",
            "reason": "tushare_has_no_rows_for_target_date",
            "db_upserted": 0,
            "coverage": None,
        },
    )

    with caplog.at_level(logging.WARNING, logger="apps.api.main"):
        out = svc.backfill_daily_prices_tushare_range_view(
            start_date="2026-06-08",
            end_date="2026-06-08",
            requested_by="unit.test",
            dry_run=False,
        )

    assert out["skipped_days"] == 1
    assert "backfill_daily_prices_tushare_range skipped_days=1" in caplog.text
    assert "tushare_has_no_rows_for_target_date" in caplog.text


# ---------------------------------------------------------------------------
# D3-extra-1 deprecated prediction signals endpoint
# ---------------------------------------------------------------------------


def test_prediction_signals_view_returns_stable_deprecation_payload() -> None:
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))

    out = svc.prediction_signals_view({"date": ["2026-07-23"]})

    assert out["status"] == "deprecated"
    assert out["reason"] == "ml_prediction_line_sunset"
    assert "joblib" in out["detail"]
    assert "scikit-learn" in out["detail"]
    # The deprecated path must not touch the model/trainer or the stock db.
    assert not hasattr(svc, "_ml_trainer")
    assert svc.prediction_signals_view({}) == out


# ---------------------------------------------------------------------------
# Chaos chain daily steps (snapshot -> focus board), fail-closed
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _collect_steps() -> tuple[list[dict], Any]:
    calls: list[dict] = []

    def fake_add_step(step_id, status, *, outputs=None, error=None, elapsed_ms=0.0):
        calls.append(
            {
                "step_id": step_id,
                "status": status,
                "outputs": outputs,
                "error": error,
            }
        )

    return calls, fake_add_step


def test_chaos_chain_steps_both_ok(monkeypatch) -> None:
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    calls, add_step = _collect_steps()
    run_cmds: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        run_cmds.append(list(cmd))
        if "build_chaos_daily_snapshot.py" in cmd[1]:
            return _FakeProc(0, json.dumps({"rows_written": 5015}))
        return _FakeProc(
            0,
            json.dumps({"summary": {"selected_count_after_cap": {"focus_list": 50}}}),
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    svc._run_chaos_chain_steps(end_date="2026-07-24", add_step=add_step)

    assert [c["step_id"] for c in calls] == ["chaos_daily_snapshot", "chaos_focus_board"]
    assert [c["status"] for c in calls] == ["ok", "ok"]
    assert calls[0]["outputs"]["rows_written"] == 5015
    assert calls[0]["outputs"]["universe"] == "code_asc_all_a"
    assert calls[1]["outputs"]["selected_count_after_cap"] == {"focus_list": 50}

    build_cmd = run_cmds[0]
    assert build_cmd[0] == sys.executable
    assert "code_asc" in build_cmd
    assert "chaos_weights_v1_2" in build_cmd
    assert "chaos_registry_v1" not in build_cmd  # registry goes through --registry-id v1
    assert "v1" in build_cmd
    assert "chaos_thresholds_v0" in build_cmd

    board_cmd = run_cmds[1]
    assert board_cmd[0] == sys.executable
    assert "run_chaos_focus_board.py" in board_cmd[1]
    assert "all_a_share" in board_cmd
    assert "2026-07-24" in board_cmd


def test_chaos_chain_steps_snapshot_failure_skips_board(monkeypatch) -> None:
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    calls, add_step = _collect_steps()
    run_cmds: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        run_cmds.append(list(cmd))
        return _FakeProc(1, "", "boom-build")

    monkeypatch.setattr(subprocess, "run", fake_run)

    svc._run_chaos_chain_steps(end_date="2026-07-24", add_step=add_step)

    assert [c["step_id"] for c in calls] == ["chaos_daily_snapshot", "chaos_focus_board"]
    assert calls[0]["status"] == "failed"
    assert "boom-build" in calls[0]["error"]
    assert calls[1]["status"] == "failed"
    assert "skipped" in calls[1]["error"]
    # focus board command must never run when the snapshot step failed
    assert len(run_cmds) == 1


def test_chaos_chain_steps_board_failure_after_snapshot_ok(monkeypatch) -> None:
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    calls, add_step = _collect_steps()

    def fake_run(cmd, **kwargs):
        if "build_chaos_daily_snapshot.py" in cmd[1]:
            return _FakeProc(0, json.dumps({"rows_written": 5015}))
        return _FakeProc(2, "", "boom-board")

    monkeypatch.setattr(subprocess, "run", fake_run)

    svc._run_chaos_chain_steps(end_date="2026-07-24", add_step=add_step)

    assert calls[0]["status"] == "ok"
    assert calls[1]["step_id"] == "chaos_focus_board"
    assert calls[1]["status"] == "failed"
    assert "boom-board" in calls[1]["error"]


def test_chaos_chain_steps_exception_is_recorded_not_raised(monkeypatch) -> None:
    svc = BootstrapApiService(project_root=str(PROJECT_ROOT))
    calls, add_step = _collect_steps()

    def fake_run(cmd, **kwargs):
        raise RuntimeError("spawn failed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    svc._run_chaos_chain_steps(end_date="2026-07-24", add_step=add_step)

    assert calls[0]["status"] == "failed"
    assert "spawn failed" in calls[0]["error"]
    assert calls[1]["status"] == "failed"
    assert "skipped" in calls[1]["error"]
