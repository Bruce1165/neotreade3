"""Analysis-engine helpers for lowfreq report-runner consumers."""

from __future__ import annotations

from typing import Optional

from apps.api.main import BootstrapApiService
from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16


def prepare_lowfreq_report_analysis_engine(
    *,
    service: BootstrapApiService,
    max_positions_override: Optional[int],
) -> LowFreqTradingEngineV16:
    engine = service._lowfreq_engine_v16()
    if max_positions_override is not None:
        engine.MAX_POSITIONS = int(max_positions_override)
    return engine
