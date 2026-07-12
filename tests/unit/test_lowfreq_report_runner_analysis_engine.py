from __future__ import annotations

from neotrade3.orchestration.report_runner_analysis_engine import (
    prepare_lowfreq_report_analysis_engine,
)


class FakeEngine:
    def __init__(self) -> None:
        self.MAX_POSITIONS = 5


class FakeService:
    def __init__(self, engine: FakeEngine) -> None:
        self.engine = engine
        self.calls = 0

    def _lowfreq_engine_v16(self) -> FakeEngine:
        self.calls += 1
        return self.engine


def test_prepare_lowfreq_report_analysis_engine_returns_service_engine_without_override() -> None:
    engine = FakeEngine()
    service = FakeService(engine)

    out = prepare_lowfreq_report_analysis_engine(
        service=service,
        max_positions_override=None,
    )

    assert out is engine
    assert out.MAX_POSITIONS == 5
    assert service.calls == 1


def test_prepare_lowfreq_report_analysis_engine_applies_max_positions_override() -> None:
    engine = FakeEngine()
    service = FakeService(engine)

    out = prepare_lowfreq_report_analysis_engine(
        service=service,
        max_positions_override="9",
    )

    assert out is engine
    assert out.MAX_POSITIONS == 9
    assert service.calls == 1
