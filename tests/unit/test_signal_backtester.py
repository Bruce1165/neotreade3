from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import pytest

from neotrade3.analysis.backtest import SignalBacktester


@dataclass
class _ExpectedReturn:
    base_pct: float = 10.0

    def to_dict(self) -> dict[str, float]:
        return {"base_pct": self.base_pct}


def test_signal_backtester_recycles_cash_after_exit(monkeypatch) -> None:
    import neotrade3.analysis.signal_generator as signal_generator

    day1 = date(2026, 6, 1)
    day2 = date(2026, 6, 2)
    day3 = date(2026, 6, 3)

    signal_map = {
        day1: [
            SimpleNamespace(
                code="AAA",
                name="First",
                entry_price=1.0,
                expected_return=_ExpectedReturn(base_pct=10.0),
                grade="A",
            )
        ],
        day2: [
            SimpleNamespace(
                code="BBB",
                name="Second",
                entry_price=1.0,
                expected_return=_ExpectedReturn(base_pct=10.0),
                grade="A",
            )
        ],
        day3: [],
    }

    class _FakeSignalGenerator:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path

        def generate(self, *, codes, target_date, min_grade):
            return SimpleNamespace(signals=list(signal_map.get(target_date, [])))

    monkeypatch.setattr(signal_generator, "SignalGenerator", _FakeSignalGenerator)

    price_map = {
        ("AAA", day1): 1.0,
        ("AAA", day2): 1.2,
        ("BBB", day2): 1.0,
        ("BBB", day3): 1.0,
    }

    engine = SignalBacktester(
        db_path="unused.db",
        initial_capital=1000.0,
        max_positions=1,
        position_size_pct=50.0,
    )
    monkeypatch.setattr(
        engine,
        "_get_price",
        lambda code, target_date: price_map.get((code, target_date)),
    )

    result = engine.run(start_date=day1, end_date=day3)

    assert [trade.code for trade in result.trades] == ["AAA", "BBB"]
    assert result.trades[0].exit_date == day2
    assert round(result.trades[0].realized_pnl, 6) == 100.0
    assert result.trades[1].quantity == 500
    assert result.trades[1].exit_date == day3


def test_signal_backtester_refreshes_final_equity_point_after_forced_close(
    monkeypatch,
) -> None:
    import neotrade3.analysis.signal_generator as signal_generator

    friday = date(2026, 6, 5)
    saturday = date(2026, 6, 6)

    class _FakeSignalGenerator:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path

        def generate(self, *, codes, target_date, min_grade):
            if target_date != friday:
                return SimpleNamespace(signals=[])
            return SimpleNamespace(
                signals=[
                    SimpleNamespace(
                        code="AAA",
                        name="Only",
                        entry_price=1.0,
                        expected_return=_ExpectedReturn(base_pct=50.0),
                        grade="A",
                    )
                ]
            )

    monkeypatch.setattr(signal_generator, "SignalGenerator", _FakeSignalGenerator)

    price_map = {
        ("AAA", friday): 1.0,
        ("AAA", saturday): 1.2,
    }
    engine = SignalBacktester(
        db_path="unused.db",
        initial_capital=1000.0,
        max_positions=1,
        position_size_pct=50.0,
    )
    monkeypatch.setattr(
        engine,
        "_get_price",
        lambda code, target_date: price_map.get((code, target_date)),
    )

    result = engine.run(start_date=friday, end_date=saturday)

    assert result.equity_curve[-1] == {
        "date": saturday.isoformat(),
        "equity": 1100.0,
    }
    assert result.trades[-1].exit_reason.value == "end_of_test"


def test_signal_backtester_logs_signal_generation_failures(
    monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    import neotrade3.analysis.signal_generator as signal_generator

    target_date = date(2026, 6, 1)

    class _FailingSignalGenerator:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path

        def generate(self, *, codes, target_date, min_grade):
            raise RuntimeError("boom")

    monkeypatch.setattr(signal_generator, "SignalGenerator", _FailingSignalGenerator)

    engine = SignalBacktester(db_path="unused.db")
    monkeypatch.setattr(engine, "_get_price", lambda code, run_date: None)

    with caplog.at_level(logging.WARNING, logger="neotrade3.analysis.backtest"):
        result = engine.run(start_date=target_date, end_date=target_date, codes=["AAA"])

    assert result.trades == []
    assert "SignalBacktester signal generation failed" in caplog.text
    assert target_date.isoformat() in caplog.text
    assert "AAA" in caplog.text


def test_signal_backtester_keeps_unpriced_tail_position_in_final_equity(
    monkeypatch,
) -> None:
    import neotrade3.analysis.signal_generator as signal_generator

    friday = date(2026, 6, 5)
    saturday = date(2026, 6, 6)

    class _FakeSignalGenerator:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path

        def generate(self, *, codes, target_date, min_grade):
            if target_date != friday:
                return SimpleNamespace(signals=[])
            return SimpleNamespace(
                signals=[
                    SimpleNamespace(
                        code="AAA",
                        name="Only",
                        entry_price=1.0,
                        expected_return=_ExpectedReturn(base_pct=50.0),
                        grade="A",
                    )
                ]
            )

    monkeypatch.setattr(signal_generator, "SignalGenerator", _FakeSignalGenerator)

    price_map = {
        ("AAA", friday): 1.0,
    }
    engine = SignalBacktester(
        db_path="unused.db",
        initial_capital=1000.0,
        max_positions=1,
        position_size_pct=50.0,
    )
    monkeypatch.setattr(
        engine,
        "_get_price",
        lambda code, target_date: price_map.get((code, target_date)),
    )

    result = engine.run(start_date=friday, end_date=saturday)

    assert result.trades == []
    assert result.equity_curve[-1] == {
        "date": saturday.isoformat(),
        "equity": 1000.0,
    }
