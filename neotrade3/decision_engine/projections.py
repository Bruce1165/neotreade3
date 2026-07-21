"""Projection helpers for low-frequency formal front payloads."""

from __future__ import annotations

from typing import Any


def project_lowfreq_formal_front(signal_payload: object) -> dict[str, Any] | None:
    """Project a raw signal payload into a compact formal-front snapshot."""

    if not isinstance(signal_payload, dict):
        return None
    formal = signal_payload.get("formal")
    if not isinstance(formal, dict):
        return None

    output: dict[str, Any] = {"status": str(formal.get("status") or "").strip() or "unknown"}
    if output["status"] != "ok":
        error_type = str(formal.get("error_type") or "").strip()
        message = str(formal.get("message") or "").strip()
        if error_type:
            output["error_type"] = error_type
        if message:
            output["message"] = message
        return output

    small_cycle = formal.get("small_cycle") if isinstance(formal.get("small_cycle"), dict) else {}
    identify_state = formal.get("identify_state") if isinstance(formal.get("identify_state"), dict) else {}
    tracking_state = formal.get("tracking_state") if isinstance(formal.get("tracking_state"), dict) else {}
    entry_state = formal.get("entry_state") if isinstance(formal.get("entry_state"), dict) else {}
    constraints = (
        formal.get("m1_constraints_ref")
        if isinstance(formal.get("m1_constraints_ref"), dict)
        else {}
    )
    entry_status = str(entry_state.get("status") or "").strip()
    entry_decision = str(entry_state.get("decision") or "").strip()
    entry_actionable = bool(entry_state.get("actionable"))
    entry_blocking = list(entry_state.get("blocking_reasons") or [])
    constraints_blocked = bool(constraints.get("blocked"))
    constraints_blocking = list(constraints.get("blocking_reasons") or [])
    combined_blocking: list[str] = []
    for reason in constraints_blocking + entry_blocking:
        reason_s = str(reason or "").strip()
        if not reason_s or reason_s in combined_blocking:
            continue
        combined_blocking.append(reason_s)
    window_actionable = bool(entry_actionable and not constraints_blocked)
    if window_actionable:
        window_status = "ready"
    elif constraints_blocked:
        window_status = "blocked"
    else:
        window_status = "not_ready"

    output["small_cycle"] = {
        "cycle_state": str(small_cycle.get("cycle_state") or "").strip(),
        "state_stability_level": str(small_cycle.get("state_stability_level") or "").strip(),
    }
    output["identify_state"] = {
        "status": str(identify_state.get("status") or "").strip(),
        "reason": str(identify_state.get("reason") or "").strip(),
    }
    output["tracking_state"] = {
        "status": str(tracking_state.get("status") or "").strip(),
        "maturity": str(tracking_state.get("maturity") or "").strip(),
        "transition_reason": str(tracking_state.get("transition_reason") or "").strip(),
    }
    output["entry_state"] = {
        "status": entry_status,
        "decision": entry_decision,
        "actionable": bool(entry_actionable),
        "blocking_reasons": entry_blocking,
    }
    output["entry_window"] = {
        "status": window_status,
        "decision": entry_decision,
        "actionable": bool(window_actionable),
        "blocking_reasons": combined_blocking,
    }
    output["m1_constraints"] = {
        "blocked": bool(constraints.get("blocked")),
        "blocking_reasons": list(constraints.get("blocking_reasons") or []),
        "profile_window_ready": bool(constraints.get("profile_window_ready")),
    }
    return output
