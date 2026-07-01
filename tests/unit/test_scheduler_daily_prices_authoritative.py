from __future__ import annotations

import pytest

from neotrade3.scheduler import task_scheduler


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
