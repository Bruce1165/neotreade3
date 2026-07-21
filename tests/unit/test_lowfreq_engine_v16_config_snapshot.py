from __future__ import annotations

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16, LowFreqV16Config


def test_config_snapshot_includes_cross_sector_scan_knobs() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.config = LowFreqV16Config()
    snapshot = engine.get_config_snapshot()

    assert snapshot["CROSS_SECTOR_SCAN_ENABLED"] is True
    assert snapshot["CROSS_SECTOR_SCAN_LIMIT"] == 500
    assert snapshot["CROSS_SECTOR_CANDIDATE_TOP_N"] == 120
    assert snapshot["CROSS_SECTOR_WAVE3_ONLY"] is True
