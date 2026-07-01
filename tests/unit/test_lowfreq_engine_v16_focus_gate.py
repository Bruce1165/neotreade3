from __future__ import annotations

from datetime import date

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16


def test_focus_gate_allows_zero_attention_when_other_hard_conditions_hold() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine._market_focus_snapshot = lambda cursor, code, stock_name, target_date: {
        "focus_pass": True,
        "ai_hits": ["算力"],
        "hardtech_hits": ["算力"],
        "penetration_hits": ["东数西算(算力)"],
        "etf_index_data_ready": False,
        "holder_fund_count": 3,
        "config_score": 2,
        "attention_score": 0,
    }

    passed, reasons, snapshot = engine._passes_core_focus_gate(
        None,
        code="000001",
        stock_name="测试龙头",
        role="龙头",
        target_date=date(2026, 6, 18),
    )

    assert passed is True
    assert snapshot["attention_score"] == 0
    assert any("参考项" in reason for reason in reasons)


def test_focus_gate_still_blocks_non_leaders() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)
    engine._market_focus_snapshot = lambda cursor, code, stock_name, target_date: {
        "focus_pass": True,
        "attention_score": 2,
    }

    passed, reasons, _snapshot = engine._passes_core_focus_gate(
        None,
        code="000001",
        stock_name="测试跟随",
        role="跟随",
        target_date=date(2026, 6, 18),
    )

    assert passed is False
    assert reasons == ["仅允许细分赛道龙头进入正式买入主链"]


def test_focus_gate_skips_snapshot_for_non_leaders() -> None:
    engine = LowFreqTradingEngineV16.__new__(LowFreqTradingEngineV16)

    def _unexpected_snapshot(*_args, **_kwargs):
        raise AssertionError("non-leader should not evaluate expensive focus snapshot")

    engine._market_focus_snapshot = _unexpected_snapshot

    passed, reasons, snapshot = engine._passes_core_focus_gate(
        None,
        code="000001",
        stock_name="测试跟随",
        role="跟随",
        target_date=date(2026, 6, 18),
    )

    assert passed is False
    assert reasons == ["仅允许细分赛道龙头进入正式买入主链"]
    assert snapshot["focus_pass"] is False
    assert snapshot["focus_bonus"] == 0.0
