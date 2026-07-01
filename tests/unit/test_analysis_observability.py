from __future__ import annotations

import logging
import sys
from datetime import date
from types import SimpleNamespace

import pytest

import neotrade3.analysis.market_phase as market_phase
import neotrade3.analysis.sector_rotation as sector_rotation
import neotrade3.analysis.signal_generator as signal_generator


def test_signal_generator_logs_market_phase_degradation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _raise_market_phase(**kwargs):
        raise RuntimeError("phase boom")

    monkeypatch.setitem(
        sys.modules,
        "neotrade3.analysis.market_phase",
        SimpleNamespace(detect_market_phase=_raise_market_phase),
    )
    monkeypatch.setattr(
        signal_generator.SignalGenerator,
        "_get_candidate_codes",
        lambda self, target_date: [],
    )

    with caplog.at_level(logging.WARNING, logger=signal_generator.__name__):
        result = signal_generator.SignalGenerator("unused.db").generate(
            target_date=date(2026, 6, 9)
        )

    assert result.market_phase == "unknown"
    assert "SignalGenerator market phase detection degraded" in caplog.text


def test_signal_generator_logs_resonance_degradation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        signal_generator.SignalGenerator,
        "_get_stock_info",
        lambda self, code, target_date: ("示例股票", 10.0),
    )
    monkeypatch.setattr(
        signal_generator.SignalGenerator,
        "_get_stock_sector",
        lambda self, code: None,
    )

    class _FakeWaveAnalyzer:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path

        def analyze(self, *, code, target_date):
            return SimpleNamespace(signals=[], get_primary_signal=lambda: None)

    class _FakeSectorAnalyzer:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path

        def analyze(self, *, target_date):
            return SimpleNamespace(top_sectors=[])

    class _FakeTierAnalyzer:
        def __init__(self, db_path: str) -> None:
            self.db_path = db_path

        def analyze(self, *, codes, target_date):
            return SimpleNamespace(all_tiered_stocks=[])

    monkeypatch.setitem(
        sys.modules,
        "neotrade3.analysis.elliott_wave",
        SimpleNamespace(ElliottWaveAnalyzer=_FakeWaveAnalyzer),
    )
    monkeypatch.setitem(
        sys.modules,
        "neotrade3.analysis.sector_rotation",
        SimpleNamespace(SectorRotationAnalyzer=_FakeSectorAnalyzer),
    )
    monkeypatch.setitem(
        sys.modules,
        "neotrade3.analysis.stock_tiering",
        SimpleNamespace(StockTieringAnalyzer=_FakeTierAnalyzer, StockTier=object),
    )

    def _broken_connect(*args, **kwargs):
        raise RuntimeError("resonance boom")

    monkeypatch.setattr(signal_generator.sqlite3, "connect", _broken_connect)

    engine = signal_generator.SignalGenerator("unused.db")
    with caplog.at_level(logging.WARNING, logger=signal_generator.__name__):
        engine._analyze_stock(
            code="600001",
            target_date=date(2026, 6, 9),
            market_bullish=True,
            market_score=80.0,
        )

    assert "SignalGenerator resonance analysis degraded" in caplog.text


def test_market_phase_helpers_log_degradation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _broken_connect(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(market_phase.sqlite3, "connect", _broken_connect)

    with caplog.at_level(logging.WARNING, logger=market_phase.__name__):
        assert market_phase._calc_market_breadth("unused.db", "2026-06-09", 20) == 0.5
        assert market_phase._calc_total_amount("unused.db", "2026-06-09", 20) == (
            0.0,
            "unknown",
        )

    assert "计算市场广度时出错" in caplog.text
    assert "计算成交额时出错" in caplog.text


def test_detect_market_phase_logs_degradation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _broken_connect(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(market_phase.sqlite3, "connect", _broken_connect)

    with caplog.at_level(logging.WARNING, logger=market_phase.__name__):
        result = market_phase.detect_market_phase("unused.db", "2026-06-09")

    assert result.phase is market_phase.MarketPhase.TRANSITION
    assert "检测市场阶段时出错" in caplog.text


def test_sector_rotation_logs_degradation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _broken_connect(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(sector_rotation.sqlite3, "connect", _broken_connect)
    analyzer = sector_rotation.SectorRotationAnalyzer("unused.db")

    with caplog.at_level(logging.WARNING, logger=sector_rotation.__name__):
        assert analyzer._calc_sector_returns("2026-06-09", 120) == {}
        assert analyzer._calc_stock_rps("2026-06-09") == []

    assert "计算板块收益率时出错" in caplog.text
    assert "计算个股RPS时出错" in caplog.text
