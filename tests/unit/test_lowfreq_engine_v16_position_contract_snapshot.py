from __future__ import annotations

from typing import Any

from neotrade3.decision_engine.position_contract_snapshot import (
    build_position_contract_snapshot,
)


def _layer_contract_builder(
    *,
    current_stage: str,
    decision: str,
    score: float | None = None,
    reasons: list[str] | None = None,
    evidence: list[str] | None = None,
    flags: list[str] | None = None,
    source_layer: str,
    next_action: str,
    last_transition: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "current_stage": current_stage,
        "decision": decision,
        "reasons": list(reasons or []),
        "evidence": list(evidence or []),
        "flags": list(flags or []),
        "source_layer": source_layer,
        "next_action": next_action,
        "last_transition": last_transition,
    }
    if score is not None:
        payload["score"] = float(score)
    return payload


def test_build_position_contract_snapshot_keeps_partial_weakness_in_hold_layer() -> None:
    snapshot = build_position_contract_snapshot(
        market_state="",
        sector_state="",
        market_reason="",
        sector_reason="",
        grace_used=False,
        grace_reason="",
        market_snapshot={
            "evidence_count": 1,
            "breadth_weak": True,
            "details": "创业板见顶确认候选：趋势转弱=否 | 广度转弱=是",
        },
        sector_snapshot=None,
        trend_snapshot=None,
        sell_payload=None,
        current_date_key="2026-06-18",
        market_last_hit_date="",
        sector_last_hit_date="",
        grace_date="",
        layer_contract_builder=_layer_contract_builder,
    )

    assert snapshot["hold_state"] == "noise_watch"
    assert snapshot["hold_attribution_bucket"] == "hold_noise_watch"
    assert snapshot["exit_attribution_bucket"] == ""
    assert snapshot["exit_ready"] is False
    assert snapshot["decision"] == "hold"
    assert "存在弱化证据，但仍属于观察态" in snapshot["not_exit_reasons"][0]
    assert "market_breadth_weak" in snapshot["warning_flags"]


def test_build_position_contract_snapshot_maps_grace_hold_bucket_and_note() -> None:
    snapshot = build_position_contract_snapshot(
        market_state="",
        sector_state="",
        market_reason="",
        sector_reason="",
        grace_used=True,
        grace_reason="系统退出宽限仍有效",
        market_snapshot=None,
        sector_snapshot=None,
        trend_snapshot=None,
        sell_payload=None,
        current_date_key="2026-06-18",
        market_last_hit_date="",
        sector_last_hit_date="",
        grace_date="2026-06-17",
        layer_contract_builder=_layer_contract_builder,
    )

    assert snapshot["hold_state"] == "grace_hold"
    assert snapshot["hold_attribution_bucket"] == "hold_grace"
    assert "system_exit_grace_used" in snapshot["warning_flags"]
    assert "系统退出宽限仍有效，继续持有观察" in snapshot["not_exit_reasons"]
    assert snapshot["last_transition"] == "2026-06-17"


def test_build_position_contract_snapshot_maps_trend_exhausted_exit_bucket() -> None:
    snapshot = build_position_contract_snapshot(
        market_state="",
        sector_state="",
        market_reason="",
        sector_reason="",
        grace_used=False,
        grace_reason="",
        market_snapshot=None,
        sector_snapshot=None,
        trend_snapshot=None,
        sell_payload={
            "reason": "trend_exhausted",
            "confidence": 0.88,
            "details": "趋势衰竭退出",
            "source_layer": "exit",
            "exit_scope": "position_only",
        },
        current_date_key="2026-06-18",
        market_last_hit_date="",
        sector_last_hit_date="",
        grace_date="",
        layer_contract_builder=_layer_contract_builder,
    )

    assert snapshot["hold_state"] == "exit_ready"
    assert snapshot["exit_ready"] is True
    assert snapshot["exit_reason_type"] == "trend_exhausted"
    assert snapshot["exit_attribution_bucket"] == "trend_exhaustion_exit"
    assert snapshot["exit_scope"] == "position_only"


def test_build_position_contract_snapshot_falls_back_to_exit_other_for_unknown_exit_reason() -> None:
    snapshot = build_position_contract_snapshot(
        market_state="",
        sector_state="",
        market_reason="",
        sector_reason="",
        grace_used=False,
        grace_reason="",
        market_snapshot=None,
        sector_snapshot=None,
        trend_snapshot=None,
        sell_payload={
            "reason": "other_reason",
            "confidence": 0.5,
            "details": "其它退出",
            "source_layer": "exit",
            "exit_scope": "position_only",
        },
        current_date_key="2026-06-18",
        market_last_hit_date="",
        sector_last_hit_date="",
        grace_date="",
        layer_contract_builder=_layer_contract_builder,
    )

    assert snapshot["exit_attribution_bucket"] == "exit_other"
    assert snapshot["exit_reason_type"] == "other_reason"


def test_build_position_contract_snapshot_uses_latest_transition_date() -> None:
    snapshot = build_position_contract_snapshot(
        market_state="review",
        sector_state="",
        market_reason="市场观察",
        sector_reason="",
        grace_used=True,
        grace_reason="宽限有效",
        market_snapshot=None,
        sector_snapshot=None,
        trend_snapshot=None,
        sell_payload=None,
        current_date_key="2026-06-18",
        market_last_hit_date="2026-06-15",
        sector_last_hit_date="2026-06-17",
        grace_date="2026-06-16",
        layer_contract_builder=_layer_contract_builder,
    )

    assert snapshot["hold_state"] == "review_watch"
    assert snapshot["last_transition"] == "2026-06-17"
