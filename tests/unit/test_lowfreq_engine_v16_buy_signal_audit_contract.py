from __future__ import annotations

from neotrade3.decision_engine.buy_signal_audit_contract import (
    normalize_execution_block_reason,
    resolve_buy_signal_audit_funnel_stage,
    resolve_execution_action_fields,
)


def test_normalize_execution_block_reason_maps_aliases() -> None:
    assert normalize_execution_block_reason("reserved_due_to_full_book") == "positions_full"
    assert normalize_execution_block_reason("buy_insufficient_cash") == "cash_insufficient"
    assert normalize_execution_block_reason("reservation_expired") == "entry_window_missed"
    assert normalize_execution_block_reason("pending_conflict_older_intent_wins") == "conflict_with_exit"
    assert normalize_execution_block_reason("elite_execution_candidate_rejected") == "execution_rule_blocked"


def test_normalize_execution_block_reason_keeps_unknown_reason() -> None:
    assert normalize_execution_block_reason("custom_reason") == "custom_reason"


def test_resolve_execution_action_fields_returns_tracking_fields_for_tracking_events() -> None:
    assert resolve_execution_action_fields(event_type="tracking_started") == {
        "action_type": "",
        "order_action": "",
        "reserve_action": "",
        "execution_status": "tracking",
    }


def test_resolve_execution_action_fields_returns_reserved_fields() -> None:
    assert resolve_execution_action_fields(event_type="reservation_created") == {
        "action_type": "reserve",
        "order_action": "block",
        "reserve_action": "reserve",
        "execution_status": "reserved",
    }


def test_resolve_execution_action_fields_releases_reserved_buy_execution() -> None:
    assert resolve_execution_action_fields(
        event_type="buy_executed",
        snapshot={"queue_name": "reserved"},
    ) == {
        "action_type": "buy",
        "order_action": "buy",
        "reserve_action": "release",
        "execution_status": "executed",
    }


def test_resolve_execution_action_fields_keeps_direct_buy_without_release() -> None:
    assert resolve_execution_action_fields(
        event_type="buy_executed",
        snapshot={"queue_name": "hot"},
    ) == {
        "action_type": "buy",
        "order_action": "buy",
        "reserve_action": "",
        "execution_status": "executed",
    }


def test_resolve_execution_action_fields_returns_expired_fields() -> None:
    assert resolve_execution_action_fields(event_type="reservation_expired") == {
        "action_type": "block",
        "order_action": "block",
        "reserve_action": "expire",
        "execution_status": "expired",
    }


def test_resolve_execution_action_fields_falls_back_to_blocked_fields() -> None:
    assert resolve_execution_action_fields(event_type="blocked_other") == {
        "action_type": "block",
        "order_action": "block",
        "reserve_action": "",
        "execution_status": "blocked",
    }


def test_resolve_buy_signal_audit_funnel_stage_maps_current_contract() -> None:
    assert resolve_buy_signal_audit_funnel_stage("tracking_started") == "candidate_detected"
    assert resolve_buy_signal_audit_funnel_stage("tracking_promoted_to_entry") == "entry_ready"
    assert resolve_buy_signal_audit_funnel_stage("tracking_dropped") == "expired"
    assert resolve_buy_signal_audit_funnel_stage("reservation_created") == "reserved"
    assert resolve_buy_signal_audit_funnel_stage("reservation_expired") == "expired"
    assert resolve_buy_signal_audit_funnel_stage("reservation_released_into_buy") == "released"
    assert resolve_buy_signal_audit_funnel_stage("buy_executed") == "blocked"
