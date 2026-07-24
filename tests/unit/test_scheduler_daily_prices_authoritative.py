from __future__ import annotations

import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

from neotrade3.scheduler import task_scheduler


_CUTOFF = "2026-07-23"


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 7, 23, 16, 0, tzinfo=tz)


def _seed_stock_db(tmp_path: Path, *, calendar_dates, price_dates) -> Path:
    db_dir = tmp_path / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "stock_data.db"
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


def _prepare_scheduler(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(task_scheduler, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(task_scheduler, "_require_scheduler_python", lambda: None)
    monkeypatch.setattr(task_scheduler, "datetime", _FixedDateTime)


def _ok_pipeline_payload(target_date: str) -> dict:
    return {
        "_meta": {"status": "ok"},
        "ledger_path": f"/tmp/{target_date}.json",
        "ledger": {
            "target_date": target_date,
            "trade_date": target_date,
            "steps": [
                {"step_id": "trading_day_check", "status": "ok", "outputs": {}, "error": None},
                {"step_id": "authoritative_update", "status": "ok", "outputs": {}, "error": None},
            ],
        },
    }


def _install_fake_service(monkeypatch, handler) -> None:
    class _FakeService:
        def __init__(self, *, project_root):
            self.project_root = Path(project_root)

        def _ensure_no_proxy(self, *, hosts):
            return None

        def _dbg_emit(self, **kwargs):
            return None

        def daily_pipeline_run_view(self, *, target_date, requested_by):
            return handler(target_date=target_date, project_root=self.project_root)

    monkeypatch.setattr("apps.api.main.BootstrapApiService", _FakeService)


def test_main_rejects_removed_tencent_job_id(monkeypatch) -> None:
    monkeypatch.setattr(task_scheduler, "_require_scheduler_python", lambda: None)
    monkeypatch.setattr(
        task_scheduler.argparse.ArgumentParser,
        "parse_args",
        lambda self: type(
            "Args",
            (),
            {
                "run_once": "update_daily_prices_tencent",
                "list_jobs": False,
                "run_now": None,
                "run_forever": False,
            },
        )(),
    )

    with pytest.raises(SystemExit, match="unknown job_id: update_daily_prices_tencent"):
        task_scheduler.main()


def test_main_returns_nonzero_when_run_once_job_fails(monkeypatch) -> None:
    monkeypatch.setattr(task_scheduler, "_require_scheduler_python", lambda: None)
    monkeypatch.setattr(task_scheduler, "_run_fetch_news", lambda: False)
    monkeypatch.setattr(
        task_scheduler.argparse.ArgumentParser,
        "parse_args",
        lambda self: type(
            "Args",
            (),
            {
                "run_once": "fetch_news",
                "list_jobs": False,
                "run_now": None,
                "run_forever": False,
            },
        )(),
    )

    assert task_scheduler.main() == 1


def test_main_returns_nonzero_when_run_now_job_is_missing(monkeypatch) -> None:
    class _FakeScheduler:
        def start(self) -> None:
            return None

        def run_now(self, job_id: str) -> bool:
            assert job_id == "missing_job"
            return False

    monkeypatch.setattr(task_scheduler, "_require_scheduler_python", lambda: None)
    monkeypatch.setattr(task_scheduler, "log_python_runtime", lambda *args, **kwargs: None)
    monkeypatch.setattr(task_scheduler, "NeoTradeScheduler", lambda: _FakeScheduler())
    monkeypatch.setattr(
        task_scheduler.argparse.ArgumentParser,
        "parse_args",
        lambda self: type(
            "Args",
            (),
            {
                "run_once": None,
                "list_jobs": False,
                "run_now": "missing_job",
                "run_forever": False,
            },
        )(),
    )

    assert task_scheduler.main() == 1


def test_run_once_returns_false_when_pipeline_step_fails(monkeypatch, tmp_path, caplog) -> None:
    _prepare_scheduler(monkeypatch, tmp_path)
    _seed_stock_db(tmp_path, calendar_dates=[_CUTOFF], price_dates=[])

    def handler(*, target_date, project_root):
        payload = _ok_pipeline_payload(target_date)
        payload["ledger"]["steps"][1]["status"] = "failed"
        return payload

    _install_fake_service(monkeypatch, handler)

    with caplog.at_level(logging.ERROR, logger="neotrade3.scheduler.task_scheduler"):
        assert task_scheduler._run_update_daily_prices_authoritative() is False
    assert "pipeline run(s) failed" in caplog.text
    assert "authoritative_update" in caplog.text


def test_run_once_returns_false_when_pipeline_meta_not_ok(monkeypatch, tmp_path) -> None:
    _prepare_scheduler(monkeypatch, tmp_path)
    _seed_stock_db(tmp_path, calendar_dates=[_CUTOFF], price_dates=[])

    def handler(*, target_date, project_root):
        payload = _ok_pipeline_payload(target_date)
        payload["_meta"]["status"] = "failed"
        return payload

    _install_fake_service(monkeypatch, handler)

    assert task_scheduler._run_update_daily_prices_authoritative() is False


def test_run_once_returns_true_when_db_fresh_after_run(monkeypatch, tmp_path) -> None:
    _prepare_scheduler(monkeypatch, tmp_path)
    _seed_stock_db(tmp_path, calendar_dates=[_CUTOFF], price_dates=[])

    def handler(*, target_date, project_root):
        db_path = Path(project_root) / "var" / "db" / "stock_data.db"
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("INSERT INTO daily_prices (trade_date) VALUES (?)", (str(target_date),))
            conn.commit()
        finally:
            conn.close()
        return _ok_pipeline_payload(target_date)

    _install_fake_service(monkeypatch, handler)

    assert task_scheduler._run_update_daily_prices_authoritative() is True


def test_run_once_returns_false_when_db_still_missing_expected_dates(monkeypatch, tmp_path, caplog) -> None:
    _prepare_scheduler(monkeypatch, tmp_path)
    _seed_stock_db(tmp_path, calendar_dates=[_CUTOFF], price_dates=[])

    # Pipeline reports ok but never writes rows -> freshness re-check must fail.
    _install_fake_service(monkeypatch, lambda *, target_date, project_root: _ok_pipeline_payload(target_date))

    with caplog.at_level(logging.ERROR, logger="neotrade3.scheduler.task_scheduler"):
        assert task_scheduler._run_update_daily_prices_authoritative() is False
    assert "still missing expected" in caplog.text
    assert _CUTOFF in caplog.text


def test_run_once_up_to_date_early_return_preserved(monkeypatch, tmp_path) -> None:
    _prepare_scheduler(monkeypatch, tmp_path)
    _seed_stock_db(tmp_path, calendar_dates=[_CUTOFF], price_dates=[_CUTOFF])

    def handler(*, target_date, project_root):
        raise AssertionError("pipeline must not run when db is up-to-date")

    _install_fake_service(monkeypatch, handler)

    assert task_scheduler._run_update_daily_prices_authoritative() is True


def test_run_once_returns_false_when_tushare_not_importable(monkeypatch, tmp_path, caplog) -> None:
    _prepare_scheduler(monkeypatch, tmp_path)

    class _ExplodingService:
        def __init__(self, *, project_root):
            raise AssertionError("service must not be constructed when tushare is missing")

    monkeypatch.setattr("apps.api.main.BootstrapApiService", _ExplodingService)
    monkeypatch.setitem(sys.modules, "tushare", None)

    with caplog.at_level(logging.ERROR, logger="neotrade3.scheduler.task_scheduler"):
        assert task_scheduler._run_update_daily_prices_authoritative() is False
    assert "tushare is not importable" in caplog.text


def test_run_once_returns_false_when_freshness_check_cannot_run(monkeypatch, tmp_path, caplog) -> None:
    _prepare_scheduler(monkeypatch, tmp_path)
    # db_path is a directory -> every sqlite read raises; pre-loop degrades to
    # "run today", post-loop freshness re-check must fail loudly.
    db_dir = tmp_path / "var" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / "stock_data.db").mkdir()

    _install_fake_service(monkeypatch, lambda *, target_date, project_root: _ok_pipeline_payload(target_date))

    with caplog.at_level(logging.ERROR, logger="neotrade3.scheduler.task_scheduler"):
        assert task_scheduler._run_update_daily_prices_authoritative() is False
    assert "freshness re-check failed" in caplog.text
