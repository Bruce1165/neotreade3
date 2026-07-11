from __future__ import annotations

from typing import Any


def normalize_execution_block_reason(raw_reason: str | None) -> str:
    reason = str(raw_reason or "").strip()
    if reason in {
        "reserved_due_to_full_book",
        "reservation_created",
        "no_slots",
        "buy_reserved_due_to_full_book",
    }:
        return "positions_full"
    if reason in {"no_cash", "buy_insufficient_cash"}:
        return "cash_insufficient"
    if reason in {"reservation_expired", "buy_reserved_expired"}:
        return "entry_window_missed"
    if reason in {"pending_conflict_older_intent_wins"}:
        return "conflict_with_exit"
    if reason in {
        "execution_signal_gate_blocked",
        "chase_entry_blocked",
        "elite_execution_candidate_rejected",
        "limit_up",
        "limit_down",
        "min_amount",
        "participation_rate",
        "missing_price_bar",
    }:
        return "execution_rule_blocked"
    return reason


def resolve_execution_action_fields(
    *,
    event_type: str,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snap = snapshot if isinstance(snapshot, dict) else {}
    event = str(event_type or "").strip()
    if event in {"tracking_started", "tracking_promoted_to_entry", "tracking_dropped"}:
        return {
            "action_type": "",
            "order_action": "",
            "reserve_action": "",
            "execution_status": "tracking",
        }
    if event == "reservation_created":
        return {
            "action_type": "reserve",
            "order_action": "block",
            "reserve_action": "reserve",
            "execution_status": "reserved",
        }
    if event == "reservation_released_into_buy":
        return {
            "action_type": "buy",
            "order_action": "buy",
            "reserve_action": "release",
            "execution_status": "executed",
        }
    if event == "buy_executed":
        reserve_action = "release" if str(snap.get("queue_name") or "") == "reserved" else ""
        return {
            "action_type": "buy",
            "order_action": "buy",
            "reserve_action": reserve_action,
            "execution_status": "executed",
        }
    if event == "reservation_expired":
        return {
            "action_type": "block",
            "order_action": "block",
            "reserve_action": "expire",
            "execution_status": "expired",
        }
    return {
        "action_type": "block",
        "order_action": "block",
        "reserve_action": "",
        "execution_status": "blocked",
    }


def resolve_buy_signal_audit_funnel_stage(event_type: str) -> str:
    event = str(event_type or "").strip()
    if event == "tracking_started":
        return "candidate_detected"
    if event == "tracking_promoted_to_entry":
        return "entry_ready"
    if event == "tracking_dropped":
        return "expired"
    if event == "reservation_created":
        return "reserved"
    if event == "reservation_expired":
        return "expired"
    if event == "reservation_released_into_buy":
        return "released"
    return "blocked"
