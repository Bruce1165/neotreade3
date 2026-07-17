from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from neotrade3.orchestration.report_runner_backtest_source import (
    load_lowfreq_report_backtest_payload,
)


class FakeEngine:
    def __init__(self, metrics: object) -> None:
        self.metrics = metrics
        self.MAX_POSITIONS = 5
        self.EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT = False
        self.calls: list[dict[str, object]] = []

    def run_backtest(
        self,
        *,
        start_date: date,
        end_date: date,
        initial_capital: float,
        include_trades: bool,
        project_root: Path,
        run_id: str,
        source_run_id: str,
    ) -> object:
        self.calls.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
                "include_trades": include_trades,
                "project_root": project_root,
                "run_id": run_id,
                "source_run_id": source_run_id,
            }
        )
        return self.metrics


class FakeService:
    def __init__(self, engine: FakeEngine, *, project_root: Path) -> None:
        self.engine = engine
        self.calls = 0
        self.project_root = project_root

    def _lowfreq_engine_v16(self) -> FakeEngine:
        self.calls += 1
        return self.engine


def test_load_lowfreq_report_backtest_payload_returns_file_json_unchanged(tmp_path: Path) -> None:
    payload = {"summary": {"total_return_pct": 12.3}, "trades": [{"code": "600000"}]}
    backtest_json = tmp_path / "backtest.json"
    backtest_json.write_text(json.dumps(payload), encoding="utf-8")
    service = FakeService(FakeEngine(metrics={"ignored": True}), project_root=tmp_path)

    out = load_lowfreq_report_backtest_payload(
        service=service,
        backtest_json=backtest_json,
        start_date=date(2024, 12, 18),
        end_date=date(2026, 6, 18),
        initial_capital=1_000_000.0,
        max_positions_override=10,
        execution_one_price_limit_only=True,
        generated_at="2026-07-12T10:00:00Z",
    )

    assert out == payload
    assert service.calls == 0


def test_load_lowfreq_report_backtest_payload_applies_engine_overrides_and_wraps_metrics() -> None:
    engine = FakeEngine(
        metrics={
            "total_return_pct": 11.1,
            "config_snapshot": {"execution_mode": "bounded"},
            "trades": [{"code": "600000", "action": "buy"}],
        }
    )
    service = FakeService(engine, project_root=Path("/tmp/project_root"))

    out = load_lowfreq_report_backtest_payload(
        service=service,
        backtest_json=None,
        start_date=date(2024, 12, 18),
        end_date=date(2026, 6, 18),
        initial_capital="1000000",
        max_positions_override="9",
        execution_one_price_limit_only=True,
        generated_at="2026-07-12T11:00:00Z",
    )

    assert service.calls == 1
    assert engine.MAX_POSITIONS == 9
    assert engine.EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT is True
    assert len(engine.calls) == 1
    call = engine.calls[0]
    assert call["start_date"] == date(2024, 12, 18)
    assert call["end_date"] == date(2026, 6, 18)
    assert call["initial_capital"] == 1000000.0
    assert call["include_trades"] is True
    assert call["project_root"] == Path("/tmp/project_root")
    assert isinstance(call["run_id"], str)
    assert call["run_id"] == call["source_run_id"]
    assert call["run_id"].startswith("lowfreq_v16_2024-12-18_2026-06-18__")
    assert out["_meta"] == {
        "status": "ok",
        "requested_by": "script",
        "model": "lowfreq_engine_v16_advanced",
        "generated_at": "2026-07-12T11:00:00Z",
        "report_id": call["run_id"],
    }
    assert out["summary"] == {
        "total_return_pct": 11.1,
        "config_snapshot": {"execution_mode": "bounded"},
    }
    assert out["trades"] == [{"code": "600000", "action": "buy"}]
    assert "trades" not in out["summary"]


def test_load_lowfreq_report_backtest_payload_normalizes_non_dict_metrics(tmp_path: Path) -> None:
    engine = FakeEngine(metrics=None)
    service = FakeService(engine, project_root=tmp_path)

    out = load_lowfreq_report_backtest_payload(
        service=service,
        backtest_json=None,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        initial_capital=500000.0,
        max_positions_override=None,
        execution_one_price_limit_only=False,
        generated_at="2026-07-12T12:00:00Z",
    )

    assert len(engine.calls) == 1
    assert out["_meta"]["generated_at"] == "2026-07-12T12:00:00Z"
    assert out["_meta"]["report_id"] == engine.calls[0]["run_id"]
    assert out["_meta"]["report_id"].startswith("lowfreq_v16_2024-01-01_2024-01-31__")
    assert out["summary"] == {}
    assert out["trades"] == []
