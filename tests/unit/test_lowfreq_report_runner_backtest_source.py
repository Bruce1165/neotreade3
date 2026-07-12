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
    ) -> object:
        self.calls.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
                "include_trades": include_trades,
            }
        )
        return self.metrics


class FakeService:
    def __init__(self, engine: FakeEngine) -> None:
        self.engine = engine
        self.calls = 0

    def _lowfreq_engine_v16(self) -> FakeEngine:
        self.calls += 1
        return self.engine


def test_load_lowfreq_report_backtest_payload_returns_file_json_unchanged(tmp_path: Path) -> None:
    payload = {"summary": {"total_return_pct": 12.3}, "trades": [{"code": "600000"}]}
    backtest_json = tmp_path / "backtest.json"
    backtest_json.write_text(json.dumps(payload), encoding="utf-8")
    service = FakeService(FakeEngine(metrics={"ignored": True}))

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
    service = FakeService(engine)

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
    assert engine.calls == [
        {
            "start_date": date(2024, 12, 18),
            "end_date": date(2026, 6, 18),
            "initial_capital": 1000000.0,
            "include_trades": True,
        }
    ]
    assert out["_meta"] == {
        "status": "ok",
        "requested_by": "script",
        "model": "lowfreq_engine_v16_advanced",
        "generated_at": "2026-07-12T11:00:00Z",
    }
    assert out["summary"] == {
        "total_return_pct": 11.1,
        "config_snapshot": {"execution_mode": "bounded"},
    }
    assert out["trades"] == [{"code": "600000", "action": "buy"}]
    assert "trades" not in out["summary"]


def test_load_lowfreq_report_backtest_payload_normalizes_non_dict_metrics() -> None:
    service = FakeService(FakeEngine(metrics=None))

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

    assert out["_meta"]["generated_at"] == "2026-07-12T12:00:00Z"
    assert out["summary"] == {}
    assert out["trades"] == []
