from __future__ import annotations

from neotrade3.decision_engine import (
    EXIT_STATE_OBJECT_TYPE,
    HOLD_STATE_OBJECT_TYPE,
    build_m3_hold_exit_bridge,
)


def test_build_m3_hold_exit_bridge_maps_watch_hold_snapshot() -> None:
    bridge = build_m3_hold_exit_bridge(
        stock_code="600000",
        trade_date="2026-07-07",
        position_snapshot={
            "hold_state": "review_watch",
            "warning_flags": ["market_exit_state:review", "trend_exhaustion_armed"],
            "not_exit_reasons": ["系统退出证据尚未达到正式确认门槛"],
            "noise_evidence": ["market breadth weakening"],
            "hold_attribution_bucket": "hold_noise_watch",
            "exit_evidence_bundle": ["market breadth weakening"],
            "current_stage": "hold_confirmed",
            "decision": "hold",
            "next_action": "hold",
            "last_transition": "2026-07-06",
            "source_layer": "hold",
            "exit_ready": False,
        },
        m2_cycle_ref={"object_type": "small_cycle", "cycle_state": "S2 Advancing"},
    )

    assert bridge["bridge_version"] == 1
    assert bridge["source_contract"] == "position_contract_snapshot.v1"
    assert bridge["position_status"] == "watch"
    assert bridge["hold_quality_signal"] == "watch_hold"
    assert bridge["exit_state"] == {}
    assert bridge["hold_state"]["object_type"] == HOLD_STATE_OBJECT_TYPE
    assert bridge["hold_state"]["status"] == "watch"
    assert bridge["hold_state"]["hold_state"] == "review_watch"
    assert bridge["hold_state"]["warning_flags"] == [
        "market_exit_state:review",
        "trend_exhaustion_armed",
    ]


def test_build_m3_hold_exit_bridge_maps_exit_ready_snapshot() -> None:
    bridge = build_m3_hold_exit_bridge(
        stock_code="600000",
        trade_date="2026-07-07",
        position_snapshot={
            "hold_state": "exit_ready",
            "warning_flags": ["market_exit_state:confirmed"],
            "exit_evidence_bundle": ["trend exhausted", "market breadth failed"],
            "current_stage": "exit_ready",
            "decision": "exit",
            "next_action": "exit",
            "last_transition": "2026-07-07",
            "source_layer": "exit",
            "exit_ready": True,
            "exit_scope": "portfolio",
            "exit_reason_type": "trend_exhausted",
            "exit_attribution_bucket": "trend_exhaustion_exit",
        },
    )

    assert bridge["position_status"] == "exit_ready"
    assert bridge["hold_quality_signal"] == "high_risk_exit"
    assert bridge["hold_state"] == {}
    assert bridge["exit_state"]["object_type"] == EXIT_STATE_OBJECT_TYPE
    assert bridge["exit_state"]["status"] == "exit_ready"
    assert bridge["exit_state"]["exit_ready"] is True
    assert bridge["exit_state"]["exit_scope"] == "portfolio"
    assert bridge["exit_state"]["exit_reason_type"] == "trend_exhausted"
