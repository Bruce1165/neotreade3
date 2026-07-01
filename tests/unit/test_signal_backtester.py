from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

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
