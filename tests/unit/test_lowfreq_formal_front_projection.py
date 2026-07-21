from __future__ import annotations

from neotrade3.decision_engine import project_lowfreq_formal_front


def test_lowfreq_formal_front_projection_returns_compact_ok_payload() -> None:
    projected = project_lowfreq_formal_front(
        {
            "formal": {
                "status": "ok",
                "small_cycle": {
                    "cycle_state": "S2 Advancing",
                    "state_stability_level": "stable",
                },
                "identify_state": {
                    "status": "identified",
                    "reason": "small_cycle_enters_formal_watch_scope",
                },
                "tracking_state": {
                    "status": "tracking",
                    "maturity": "ready_for_entry",
                    "transition_reason": "small_cycle_supports_formal_action",
                },
                "entry_state": {
                    "status": "ready",
                    "decision": "enter",
                    "actionable": True,
                    "blocking_reasons": [],
                },
                "m1_constraints_ref": {
                    "blocked": False,
                    "blocking_reasons": [],
                    "profile_window_ready": True,
                },
            }
        }
    )

    assert projected == {
        "status": "ok",
        "small_cycle": {
            "cycle_state": "S2 Advancing",
            "state_stability_level": "stable",
        },
        "identify_state": {
            "status": "identified",
            "reason": "small_cycle_enters_formal_watch_scope",
        },
        "tracking_state": {
            "status": "tracking",
            "maturity": "ready_for_entry",
            "transition_reason": "small_cycle_supports_formal_action",
        },
        "entry_state": {
            "status": "ready",
            "decision": "enter",
            "actionable": True,
            "blocking_reasons": [],
        },
        "entry_window": {
            "status": "ready",
            "decision": "enter",
            "actionable": True,
            "blocking_reasons": [],
        },
        "m1_constraints": {
            "blocked": False,
            "blocking_reasons": [],
            "profile_window_ready": True,
        },
    }


def test_lowfreq_formal_front_projection_preserves_error_status() -> None:
    projected = project_lowfreq_formal_front(
        {
            "formal": {
                "status": "error",
                "error_type": "formal_projection_failed",
                "message": "d1_fact_missing",
            }
        }
    )

    assert projected == {
        "status": "error",
        "error_type": "formal_projection_failed",
        "message": "d1_fact_missing",
    }
