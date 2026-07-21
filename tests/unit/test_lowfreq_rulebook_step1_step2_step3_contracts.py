from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import lowfreq_engine_v16_advanced as lowfreq_engine_module
from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16, StockCandidate, WavePhase


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *_args, **_kwargs):
        return self

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return None


class _Conn:
    def __init__(self, rows):
        self._cursor = _Cursor(rows)

    def cursor(self):
        return self._cursor

    def close(self):
        return None


def _make_engine(*, calibration_rows) -> LowFreqTradingEngineV16:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine.MARKET_FILTER_ENABLED = False
    engine.HOT_SECTOR_COUNT = 1
    engine.HOT_SECTOR_CANDIDATE_LIMIT = 4
    engine.BUY_THRESHOLD = 85.0
    engine.MIN_RESONANCE = 0.7
    engine.CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS = 0.0
    engine.CROSS_SECTOR_SCAN_ENABLED = True
    engine.CROSS_SECTOR_MAX_SIGNALS = 2
    engine.CROSS_SECTOR_CANDIDATE_TOP_N = 40
    engine.CROSS_SECTOR_WAVE3_ONLY = True
    engine.CROSS_SECTOR_ALLOW_WAVE1 = True
    engine.WAVE1_TRACKING_ONLY_ENABLED = True
    engine.STRONG_LEADER_SOFT_RELEASE_ENABLED = False
    engine.CROSS_SECTOR_SCORE_MARGIN = 8.0
    engine._conn = lambda: _Conn(calibration_rows)
    engine._build_formal_front_payload = lambda **_kwargs: {"status": "error", "error_type": "stub"}
    return engine


def test_step1_step2_step3_contract_fields_exist_and_match_rulebook_constants() -> None:
    target_date = date(2026, 6, 18)
    raw_score = 95.0
    role = "龙头"
    engine = _make_engine(calibration_rows=[])
    bucket_key = engine._confidence_bucket_key(
        raw_score=raw_score,
        role=role,
        risk_level="ok",
        market_regime="unknown",
    )
    engine = _make_engine(
        calibration_rows=[
            (bucket_key, 100, 25, 0.25),
        ]
    )

    engine.get_hot_sectors = lambda *_args, **_kwargs: []
    engine.get_sector_candidates = lambda *_args, **_kwargs: []
    engine.get_global_candidates = lambda *_args, **_kwargs: [
        StockCandidate(
            code="600460",
            name="士兰微",
            sector="C39",
            market_cap_yi=320.0,
            role=role,
            buy_score=raw_score,
            buy_reasons=["跨板块样本"],
            wave_phase=WavePhase.WAVE_3.value,
            wave_phase_confidence=0.88,
            evidence_bundle=["wave_detector:ok"],
            pattern_evidence=["cup_handle_confirmed"],
            sector_resonance=0.9,
        )
    ]

    out = engine.generate_buy_signals(SimpleNamespace(isoformat=lambda: target_date.isoformat()))
    tracking_pool = out.get("tracking_pool_candidates")
    assert isinstance(tracking_pool, dict)
    candidate = tracking_pool.get("600460")
    assert isinstance(candidate, dict)

    assert candidate.get("role") in {"龙头", "中军", "跟随"}
    assert str(candidate.get("wave_phase") or "").strip()
    conf = float(candidate.get("wave_phase_confidence") or 0.0)
    assert 0.0 <= conf <= 1.0
    ev = candidate.get("evidence_bundle")
    assert isinstance(ev, list)
    assert "wave_detector:ok" in ev

    pe = candidate.get("pattern_evidence")
    assert isinstance(pe, list)
    assert "cup_handle_confirmed" in pe

    assert candidate.get("certainty_horizon_days_max") == 100
    assert candidate.get("certainty_target_return_pct") == 50
    assert candidate.get("certainty_bucket_key") == bucket_key
    assert candidate.get("certainty_prob") == 0.25
    assert candidate.get("certainty_score") == 25.0

