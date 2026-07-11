from __future__ import annotations

from typing import Any


def plan_system_exit_application(
    *,
    scope: str,
    current_key: str,
    expire_date: str,
    transition: dict[str, Any],
    signal_reason: str,
    signal_confidence: float,
) -> dict[str, Any]:
    snapshot_pass = bool(transition.get("snapshot_pass"))
    snapshot_details = str(transition.get("snapshot_details") or "")

    plan: dict[str, Any] = {
        "expire_existing_watch": bool(transition.get("expire_existing_watch")),
        "snapshot_pass": snapshot_pass,
        "start_watch": False,
        "start_values": {},
        "increment_hit": False,
        "update_values": {},
        "enter_review": False,
        "review_state": "",
        "use_grace": False,
        "grace_values": {},
        "reset_scope_on_confirm": False,
        "reset_all_scopes": False,
        "emit_confirm_event": False,
        "emit_grace_then_confirmed_event": bool(
            transition.get("emit_grace_then_confirmed_event")
        ),
        "sell_signal": None,
    }
    if not snapshot_pass:
        return plan

    if bool(transition.get("start_watch")):
        plan["start_watch"] = True
        plan["start_values"] = {
            "state": "observe",
            "start": str(current_key or ""),
            "expire": str(expire_date or ""),
            "hits": 1,
            "last_reason": snapshot_details,
            "last_hit": str(current_key or ""),
        }
        return plan

    update_values: dict[str, Any] = {"last_reason": snapshot_details}
    if bool(transition.get("increment_hit")):
        plan["increment_hit"] = True
        update_values["hits"] = int(transition.get("next_hits") or 0)
        update_values["last_hit"] = str(current_key or "")
    plan["update_values"] = update_values

    if bool(transition.get("enter_review")):
        plan["enter_review"] = True
        plan["review_state"] = "review"

    if not bool(transition.get("confirm_signal")):
        return plan

    if bool(transition.get("use_grace")):
        plan["use_grace"] = True
        plan["reset_all_scopes"] = True
        plan["grace_values"] = {
            "used": True,
            "date": str(current_key or ""),
            "scope": str(scope or ""),
            "reason": snapshot_details,
        }
        return plan

    plan["emit_confirm_event"] = True
    plan["reset_scope_on_confirm"] = True
    plan["sell_signal"] = {
        "reason": str(signal_reason),
        "confidence": float(signal_confidence),
        "details": str(transition.get("confirmed_details") or ""),
        "source_layer": "exit",
        "exit_scope": str(transition.get("exit_scope") or ""),
    }
    return plan
