from __future__ import annotations

from neotrade3.decision_engine.phase1_signal_contracts import (
    candidate_tier_from_signal,
    decorate_signal_with_phase1_contracts,
    tracking_snapshot_from_signal,
)


def _contract_builder(**kwargs):
    return dict(kwargs)


def test_candidate_tier_from_signal_returns_soft_retained_when_soft_flags_present() -> None:
    assert candidate_tier_from_signal({"soft_flags": ["wave_uncertain"]}) == "soft_retained"


def test_candidate_tier_from_signal_returns_execution_eligible_without_soft_flags() -> None:
    assert candidate_tier_from_signal({"soft_flags": []}) == "execution_eligible"


def test_tracking_snapshot_from_signal_emits_mature_defaults_for_ready_signal() -> None:
    out = tracking_snapshot_from_signal(
        {
            "candidate_tier": "execution_eligible",
            "entry_ready": True,
            "reasons": ["成熟候选"],
        }
    )

    assert out["tracking_ready"] is True
    assert out["tracking_state"] == "tracking_mature"
    assert out["tracking_transition_reason"] == "candidate_meets_current_entry_contract"
    assert out["tracking_decision"] == "tracking_ready_for_entry"
    assert out["tracking_next_action"] == "promote_to_entry"


def test_tracking_snapshot_from_signal_emits_observe_defaults_for_soft_retained_signal() -> None:
    out = tracking_snapshot_from_signal(
        {
            "soft_flags": ["wave_uncertain"],
            "reasons": ["继续观察"],
        }
    )

    assert out["tracking_ready"] is False
    assert out["tracking_state"] == "tracking_observe"
    assert out["tracking_transition_reason"] == "candidate_retained_for_tracking"
    assert out["tracking_decision"] == "tracking_continue"
    assert out["tracking_next_action"] == "continue_tracking"


def test_decorate_signal_with_phase1_contracts_appends_wave1_soft_retain_once() -> None:
    out = decorate_signal_with_phase1_contracts(
        {
            "code": "300001",
            "buy_score": 92.0,
            "wave_phase": "1浪",
            "reasons": ["原始原因"],
            "soft_flags": ["wave1_tracking_only"],
        },
        wave1_tracking_only_enabled=True,
        wave1_value="1浪",
        layer_contract_builder=_contract_builder,
    )

    assert out["candidate_tier"] == "soft_retained"
    assert out["entry_ready"] is False
    assert out["soft_flags"] == ["wave1_tracking_only"]
    assert out["reasons"] == ["原始原因", "capture-first: 1浪仅保留 tracking，不进入正式建仓"]


def test_decorate_signal_with_phase1_contracts_preserves_layer_sources() -> None:
    out = decorate_signal_with_phase1_contracts(
        {
            "code": "600001",
            "buy_score": 95.0,
            "wave_phase": "3浪",
            "reasons": ["成熟候选"],
            "soft_flags": [],
        },
        wave1_tracking_only_enabled=True,
        wave1_value="1浪",
        layer_contract_builder=_contract_builder,
    )

    assert out["candidate_contract"]["source_layer"] == "discovery"
    assert out["tracking_contract"]["source_layer"] == "tracking"
    assert out["entry_contract"]["source_layer"] == "entry"
