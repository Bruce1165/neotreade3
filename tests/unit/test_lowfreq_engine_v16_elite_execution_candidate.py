from __future__ import annotations

from neotrade3.decision_engine.elite_execution_candidate import (
    build_elite_execution_candidate_snapshot,
)


def test_build_elite_execution_candidate_snapshot_rejects_gate_blocked_candidate() -> None:
    snapshot = build_elite_execution_candidate_snapshot(
        gate_blocked=True,
        gate_details="跟随股正式执行至少需要 75.0 分",
        gate_min_score_required=75.0,
        role="龙头",
        wave_phase="1浪",
        buy_score=95.0,
        soft_flags=[],
        elite_min_score=80.0,
        elite_unknown_leader_min_score=90.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot["eligible"] is False
    assert snapshot["blocked_reason"] == "elite_execution_candidate_rejected"
    assert snapshot["details"] == "跟随股正式执行至少需要 75.0 分"
    assert snapshot["min_score_required"] == 75.0


def test_build_elite_execution_candidate_snapshot_rejects_non_leader_candidate() -> None:
    snapshot = build_elite_execution_candidate_snapshot(
        gate_blocked=False,
        gate_details="",
        gate_min_score_required=None,
        role="跟随",
        wave_phase="1浪",
        buy_score=85.0,
        soft_flags=[],
        elite_min_score=80.0,
        elite_unknown_leader_min_score=90.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot["eligible"] is False
    assert snapshot["details"] == "非龙头不进入 elite execution 资格"
    assert snapshot["soft_flags"] == []
    assert snapshot["min_score_required"] == 80.0


def test_build_elite_execution_candidate_snapshot_rejects_soft_retained_candidate() -> None:
    snapshot = build_elite_execution_candidate_snapshot(
        gate_blocked=False,
        gate_details="",
        gate_min_score_required=None,
        role="龙头",
        wave_phase="3浪",
        buy_score=88.0,
        soft_flags=["soft-retained"],
        elite_min_score=80.0,
        elite_unknown_leader_min_score=90.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot["eligible"] is False
    assert snapshot["details"] == "存在 soft-retained 标记，不进入 elite execution 资格"
    assert snapshot["soft_flags"] == ["soft-retained"]
    assert snapshot["min_score_required"] == 80.0


def test_build_elite_execution_candidate_snapshot_rejects_wave1_leader_below_elite_threshold() -> None:
    snapshot = build_elite_execution_candidate_snapshot(
        gate_blocked=False,
        gate_details="",
        gate_min_score_required=None,
        role="龙头",
        wave_phase="1浪",
        buy_score=79.9,
        soft_flags=[],
        elite_min_score=80.0,
        elite_unknown_leader_min_score=90.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot["eligible"] is False
    assert snapshot["details"] == "1浪/3浪龙头正式保留至少需要 80.0 分"
    assert snapshot["min_score_required"] == 80.0


def test_build_elite_execution_candidate_snapshot_rejects_unknown_wave_leader_below_threshold() -> None:
    snapshot = build_elite_execution_candidate_snapshot(
        gate_blocked=False,
        gate_details="",
        gate_min_score_required=None,
        role="龙头",
        wave_phase="未知浪",
        buy_score=89.9,
        soft_flags=[],
        elite_min_score=80.0,
        elite_unknown_leader_min_score=90.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot["eligible"] is False
    assert snapshot["details"] == "未知波段龙头正式保留至少需要 90.0 分"
    assert snapshot["min_score_required"] == 90.0


def test_build_elite_execution_candidate_snapshot_accepts_eligible_leader() -> None:
    snapshot = build_elite_execution_candidate_snapshot(
        gate_blocked=False,
        gate_details="",
        gate_min_score_required=None,
        role="龙头",
        wave_phase="3浪",
        buy_score=90.0,
        soft_flags=[],
        elite_min_score=80.0,
        elite_unknown_leader_min_score=90.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot["eligible"] is True
    assert snapshot["details"] == ""
    assert snapshot["soft_flags"] == []
    assert snapshot["min_score_required"] == 80.0


def test_build_elite_execution_candidate_snapshot_keeps_reason_order_for_combined_rejection() -> None:
    snapshot = build_elite_execution_candidate_snapshot(
        gate_blocked=False,
        gate_details="",
        gate_min_score_required=None,
        role="跟随",
        wave_phase="未知浪",
        buy_score=70.0,
        soft_flags=["soft-retained"],
        elite_min_score=80.0,
        elite_unknown_leader_min_score=90.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot["eligible"] is False
    assert snapshot["details"] == (
        "非龙头不进入 elite execution 资格；"
        "存在 soft-retained 标记，不进入 elite execution 资格；"
        "未知波段龙头正式保留至少需要 90.0 分"
    )
    assert snapshot["soft_flags"] == ["soft-retained"]
    assert snapshot["min_score_required"] == 90.0
