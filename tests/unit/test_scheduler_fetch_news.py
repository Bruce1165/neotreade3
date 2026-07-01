from __future__ import annotations

from neotrade3.scheduler import task_scheduler


def test_run_fetch_news_runs_on_trading_day(monkeypatch) -> None:
    calls: dict[str, object] = {"fetch_called": False, "log_info": []}

    class _FakeService:
        def __init__(self, project_root):
            self.project_root = project_root

        def trading_day_view(self, *, target_date: str):
            return {"is_trading_day": True, "nearest_trading_day": target_date}

    class _FakeAdapter:
        def fetch_telegraph(self, *, limit: int):
            calls["fetch_called"] = True
            calls["fetch_limit"] = limit
            return [{"title": "n1"}, {"title": "n2"}]

    monkeypatch.setitem(__import__("sys").modules, "apps.api.main", type("m", (), {"BootstrapApiService": _FakeService}))
    monkeypatch.setitem(
        __import__("sys").modules,
        "neotrade3.data_sources.cls_adapter",
        type("m", (), {"ClsNewsAdapter": _FakeAdapter}),
    )
    monkeypatch.setattr(task_scheduler.logger, "info", lambda msg, *args: calls["log_info"].append(msg % args if args else msg))
    monkeypatch.setattr(task_scheduler.logger, "error", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not log error")))

    task_scheduler._run_fetch_news()

    assert calls["fetch_called"] is True
    assert calls["fetch_limit"] == 20
    assert any("财联社快讯抓取完成" in line for line in calls["log_info"])


def test_run_fetch_news_skips_on_non_trading_day(monkeypatch) -> None:
    calls: dict[str, object] = {"fetch_called": False, "log_info": []}

    class _FakeService:
        def __init__(self, project_root):
            self.project_root = project_root

        def trading_day_view(self, *, target_date: str):
            return {"is_trading_day": False, "nearest_trading_day": "2026-06-12"}

    class _FakeAdapter:
        def fetch_telegraph(self, *, limit: int):
            calls["fetch_called"] = True
            return []

    monkeypatch.setitem(__import__("sys").modules, "apps.api.main", type("m", (), {"BootstrapApiService": _FakeService}))
    monkeypatch.setitem(
        __import__("sys").modules,
        "neotrade3.data_sources.cls_adapter",
        type("m", (), {"ClsNewsAdapter": _FakeAdapter}),
    )
    monkeypatch.setattr(task_scheduler.logger, "info", lambda msg, *args: calls["log_info"].append(msg % args if args else msg))
    monkeypatch.setattr(task_scheduler.logger, "error", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not log error")))

    task_scheduler._run_fetch_news()

    assert calls["fetch_called"] is False
    assert any("fetch_news skipped: non-trading day" in line for line in calls["log_info"])


def test_run_fetch_news_logs_error_when_trading_day_check_fails(monkeypatch) -> None:
    calls: dict[str, object] = {"errors": []}

    class _FakeService:
        def __init__(self, project_root):
            self.project_root = project_root

        def trading_day_view(self, *, target_date: str):
            raise RuntimeError("calendar unavailable")

    class _FakeAdapter:
        def fetch_telegraph(self, *, limit: int):
            return []

    monkeypatch.setitem(__import__("sys").modules, "apps.api.main", type("m", (), {"BootstrapApiService": _FakeService}))
    monkeypatch.setitem(
        __import__("sys").modules,
        "neotrade3.data_sources.cls_adapter",
        type("m", (), {"ClsNewsAdapter": _FakeAdapter}),
    )
    monkeypatch.setattr(task_scheduler.logger, "info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(task_scheduler.logger, "error", lambda msg, *args: calls["errors"].append(msg % args if args else msg))

    task_scheduler._run_fetch_news()

    assert any("抓取财联社快讯失败" in line for line in calls["errors"])
