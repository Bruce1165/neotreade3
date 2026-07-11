from __future__ import annotations

from types import SimpleNamespace

from neotrade3.decision_engine.signal_seed import (
    build_cross_sector_signal_seed,
    build_hot_sector_signal_seed,
)


def test_build_hot_sector_signal_seed_maps_fields_and_appends_market_filter() -> None:
    candidate = SimpleNamespace(
        code="600001",
        name="测试龙头",
        sector="AI",
        buy_score=92.5,
        market_cap_yi=320.0,
        wave_phase="3浪",
        role="龙头",
        buy_reasons=["主线强化"],
        pe_ttm=18.0,
        profit_growth=25.0,
        sector_resonance=0.85,
        cup_handle_ok=True,
        signal_source="",
        soft_flags=["focus_pass"],
    )

    out = build_hot_sector_signal_seed(
        candidate,
        market_filter_note="capture-first: 市场偏弱，降权保留",
    )

    assert out["code"] == "600001"
    assert out["signal_source"] == "hot_sector"
    assert out["cup_handle_ok"] is True
    assert out["soft_flags"] == ["focus_pass"]
    assert out["reasons"] == ["主线强化", "capture-first: 市场偏弱，降权保留"]


def test_build_cross_sector_signal_seed_adds_prefix_and_wave_penalty_when_required() -> None:
    candidate = SimpleNamespace(
        code="300001",
        name="跨板块候选",
        sector="C40",
        buy_score=96.0,
        market_cap_yi=280.0,
        wave_phase="未知",
        role="龙头",
        buy_reasons=["跨板块样本"],
        pe_ttm=20.0,
        profit_growth=18.0,
        sector_resonance=0.82,
        cup_handle_ok=False,
        signal_source="",
        soft_flags=["focus_soft_fail"],
    )

    out = build_cross_sector_signal_seed(
        candidate,
        market_filter_note=None,
        wave3_only=True,
        allowed_waves={"3浪", "1浪"},
    )

    assert out["signal_source"] == "cross_sector"
    assert out["cross_sector"] is True
    assert out["reasons"] == ["跨板块扫描", "跨板块样本", "capture-first: 波段不符，降权保留"]
    assert out["soft_flags"] == ["focus_soft_fail", "wave_uncertain"]


def test_build_cross_sector_signal_seed_skips_wave_penalty_when_allowed() -> None:
    candidate = SimpleNamespace(
        code="300002",
        name="允许波段",
        sector="C41",
        buy_score=97.0,
        market_cap_yi=300.0,
        wave_phase="3浪",
        role="龙头",
        buy_reasons=["跨板块样本2"],
        pe_ttm=21.0,
        profit_growth=20.0,
        sector_resonance=0.88,
        cup_handle_ok=False,
        signal_source="custom_cross",
        soft_flags=[],
    )

    out = build_cross_sector_signal_seed(
        candidate,
        market_filter_note="capture-first: 市场偏弱，降权保留",
        wave3_only=True,
        allowed_waves={"3浪"},
    )

    assert out["signal_source"] == "custom_cross"
    assert out["reasons"] == ["跨板块扫描", "跨板块样本2", "capture-first: 市场偏弱，降权保留"]
    assert out["soft_flags"] == []
