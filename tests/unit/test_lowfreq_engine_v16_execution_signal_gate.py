from __future__ import annotations

from neotrade3.decision_engine.execution_signal_gate import build_execution_signal_gate_snapshot


def test_build_execution_signal_gate_snapshot_returns_non_blocked_when_disabled() -> None:
    snapshot = build_execution_signal_gate_snapshot(
        enabled=False,
        role="跟随",
        wave_phase="未知浪",
        buy_score=60.0,
        follower_min_score=75.0,
        unknown_wave_min_score=80.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot == {"blocked": False}


def test_build_execution_signal_gate_snapshot_blocks_follower_below_threshold() -> None:
    snapshot = build_execution_signal_gate_snapshot(
        enabled=True,
        role="跟随",
        wave_phase="1浪",
        buy_score=74.9,
        follower_min_score=75.0,
        unknown_wave_min_score=80.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot["blocked"] is True
    assert snapshot["soft_role_blocked"] is True
    assert snapshot["soft_wave_blocked"] is False
    assert snapshot["min_score_required"] == 75.0
    assert snapshot["details"] == "跟随股正式执行至少需要 75.0 分"


def test_build_execution_signal_gate_snapshot_blocks_unknown_wave_candidate_below_threshold() -> None:
    snapshot = build_execution_signal_gate_snapshot(
        enabled=True,
        role="龙头",
        wave_phase="未知浪",
        buy_score=79.9,
        follower_min_score=75.0,
        unknown_wave_min_score=80.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot["blocked"] is True
    assert snapshot["soft_role_blocked"] is False
    assert snapshot["soft_wave_blocked"] is True
    assert snapshot["min_score_required"] == 80.0
    assert snapshot["details"] == "未知波段正式执行至少需要 80.0 分"


def test_build_execution_signal_gate_snapshot_keeps_both_reasons_and_max_threshold() -> None:
    snapshot = build_execution_signal_gate_snapshot(
        enabled=True,
        role="跟随",
        wave_phase="未知浪",
        buy_score=70.0,
        follower_min_score=75.0,
        unknown_wave_min_score=80.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot["blocked"] is True
    assert snapshot["soft_role_blocked"] is True
    assert snapshot["soft_wave_blocked"] is True
    assert snapshot["min_score_required"] == 80.0
    assert snapshot["details"] == "跟随股正式执行至少需要 75.0 分；未知波段正式执行至少需要 80.0 分"


def test_build_execution_signal_gate_snapshot_allows_strong_unknown_wave_leader() -> None:
    snapshot = build_execution_signal_gate_snapshot(
        enabled=True,
        role="龙头",
        wave_phase="未知浪",
        buy_score=82.0,
        follower_min_score=75.0,
        unknown_wave_min_score=80.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert snapshot["blocked"] is False
    assert snapshot["details"] == ""
    assert snapshot["min_score_required"] == 0.0


def test_build_execution_signal_gate_snapshot_skips_unknown_wave_rule_for_wave1_and_wave3() -> None:
    wave1_snapshot = build_execution_signal_gate_snapshot(
        enabled=True,
        role="龙头",
        wave_phase="1浪",
        buy_score=70.0,
        follower_min_score=75.0,
        unknown_wave_min_score=80.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )
    wave3_snapshot = build_execution_signal_gate_snapshot(
        enabled=True,
        role="龙头",
        wave_phase="3浪",
        buy_score=70.0,
        follower_min_score=75.0,
        unknown_wave_min_score=80.0,
        wave1_value="1浪",
        wave3_value="3浪",
    )

    assert wave1_snapshot["blocked"] is False
    assert wave3_snapshot["blocked"] is False
