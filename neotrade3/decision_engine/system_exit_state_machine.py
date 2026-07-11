from __future__ import annotations

from typing import Any


def evaluate_system_exit_transition(
    *,
    scope: str,
    window: int,
    confirm_hits: int,
    current_key: str,
    start_value: str,
    state_value: str,
    hit_count: int,
    last_hit_date: str,
    snapshot: dict[str, Any] | None,
    elapsed_watch_days: int | None,
    grace_eligible: bool,
    grace_used: bool,
) -> dict[str, Any]:
    normalized_scope = str(scope or "")
    normalized_start_value = str(start_value or "").strip()
    normalized_state_value = str(state_value or "").strip()
    normalized_last_hit_date = str(last_hit_date or "").strip()
    normalized_hit_count = int(hit_count or 0)
    normalized_window = max(int(window or 0), 1)
    normalized_confirm_hits = max(int(confirm_hits or 0), 1)
    snapshot_details = str(snapshot.get("details") or "") if isinstance(snapshot, dict) else ""
    snapshot_pass = bool(isinstance(snapshot, dict) and snapshot.get("condition_pass"))
    expire_existing_watch = bool(
        normalized_start_value
        and elapsed_watch_days is not None
        and int(elapsed_watch_days) > int(normalized_window)
    )

    effective_start_value = "" if expire_existing_watch else normalized_start_value
    effective_state_value = "" if expire_existing_watch else normalized_state_value
    effective_hit_count = 0 if expire_existing_watch else normalized_hit_count
    effective_last_hit_date = "" if expire_existing_watch else normalized_last_hit_date

    payload: dict[str, Any] = {
        "snapshot_pass": bool(snapshot_pass),
        "expire_existing_watch": bool(expire_existing_watch),
        "start_watch": False,
        "increment_hit": False,
        "enter_review": False,
        "confirm_signal": False,
        "use_grace": False,
        "emit_grace_then_confirmed_event": False,
        "next_state": effective_state_value,
        "next_hits": int(effective_hit_count),
        "next_last_hit": effective_last_hit_date,
        "snapshot_details": snapshot_details,
        "confirmed_details": "",
        "exit_scope": "portfolio" if normalized_scope == "market" else "sector_only",
    }
    if not snapshot_pass:
        return payload
    if not effective_start_value:
        payload["start_watch"] = True
        payload["next_state"] = "observe"
        payload["next_hits"] = 1
        payload["next_last_hit"] = str(current_key or "")
        return payload

    if effective_last_hit_date != str(current_key or ""):
        payload["increment_hit"] = True
        payload["next_hits"] = int(effective_hit_count) + 1
        payload["next_last_hit"] = str(current_key or "")

    if int(payload["next_hits"]) >= 2 and effective_state_value != "review":
        payload["enter_review"] = True
        payload["next_state"] = "review"

    if int(payload["next_hits"]) >= int(normalized_confirm_hits):
        payload["confirm_signal"] = True
        payload["use_grace"] = bool(grace_eligible)
        payload["emit_grace_then_confirmed_event"] = bool(not grace_eligible and grace_used)
        payload["confirmed_details"] = snapshot_details.replace("确认候选", "确认")

    return payload
