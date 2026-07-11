from __future__ import annotations

from neotrade3.analysis.attribution_signal_snapshot import build_attribution_signal_snapshot


def test_build_attribution_signal_snapshot_preserves_candidate_entry_split_and_summary() -> None:
    snapshot = build_attribution_signal_snapshot(
        {
            "candidate_signals": [
                {"code": "300308", "candidate_tier": "soft_retained", "buy_score": 91.0},
                {"code": "600460", "candidate_tier": "entry_ready", "buy_score": 95.0},
            ],
            "entry_signals": [
                {"code": "600460", "candidate_tier": "entry_ready", "buy_score": 95.0},
            ],
        }
    )

    assert sorted(snapshot["candidate_signals"].keys()) == ["300308", "600460"]
    assert sorted(snapshot["entry_signals"].keys()) == ["600460"]
    assert snapshot["signal_summary"]["candidate_count"] == 2
    assert snapshot["signal_summary"]["entry_count"] == 1
    assert snapshot["signal_summary"]["soft_retained_count"] == 1


def test_build_attribution_signal_snapshot_prefers_formal_front_entry_ready_override() -> None:
    snapshot = build_attribution_signal_snapshot(
        {
            "candidate_signals": [
                {
                    "code": "300308",
                    "candidate_tier": "soft_retained",
                    "entry_ready": False,
                    "buy_score": 91.0,
                    "formal": {
                        "status": "ok",
                        "identify_state": {"status": "identified", "reason": "watch_scope"},
                        "tracking_state": {
                            "status": "tracking",
                            "maturity": "ready_for_entry",
                            "transition_reason": "supports_action",
                        },
                        "entry_state": {
                            "status": "ready",
                            "decision": "enter",
                            "actionable": True,
                            "blocking_reasons": [],
                        },
                        "small_cycle": {
                            "cycle_state": "S2 Advancing",
                            "state_stability_level": "stable",
                        },
                        "m1_constraints_ref": {
                            "blocked": False,
                            "blocking_reasons": [],
                            "profile_window_ready": True,
                        },
                    },
                }
            ]
        }
    )

    candidate = snapshot["candidate_signals"]["300308"]
    assert candidate["entry_ready"] is True
    assert candidate["candidate_tier"] == "entry_ready"
    assert candidate["formal_front"]["entry_state"]["status"] == "ready"


def test_build_attribution_signal_snapshot_ignores_legacy_buy_signals_without_entry_signals() -> None:
    snapshot = build_attribution_signal_snapshot(
        {
            "buy_signals": [{"code": "600460", "candidate_tier": "entry_ready", "buy_score": 95.0}],
        }
    )

    assert snapshot["candidate_signals"] == {}
    assert snapshot["entry_signals"] == {}
    assert snapshot["signal_summary"]["candidate_count"] == 0
    assert snapshot["signal_summary"]["entry_count"] == 0
