"""Bridge existing position snapshot semantics into formal M3 hold/exit payloads."""

from __future__ import annotations

from typing import Any, Mapping

from .assembler import build_exit_state, build_hold_state


M3_HOLD_EXIT_BRIDGE_VERSION = 1
M3_HOLD_EXIT_BRIDGE_SOURCE = "position_contract_snapshot.v1"

_WATCH_HOLD_STATES = {"review_watch", "observe_watch", "noise_watch", "grace_hold"}


def _copy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    return {str(key): item for key, item in value.items()}


def _copy_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _position_status_from_snapshot(snapshot: Mapping[str, Any]) -> str:
    if bool(snapshot.get("exit_ready")):
        return "exit_ready"
    hold_state = str(snapshot.get("hold_state") or "").strip()
    if hold_state in _WATCH_HOLD_STATES:
        return "watch"
    return "holding"


def _hold_quality_signal_from_snapshot(snapshot: Mapping[str, Any]) -> str:
    if bool(snapshot.get("exit_ready")):
        return "high_risk_exit"
    hold_state = str(snapshot.get("hold_state") or "").strip()
    if hold_state in _WATCH_HOLD_STATES:
        return "watch_hold"
    return "stable_hold"


def build_m3_hold_exit_bridge(
    *,
    stock_code: str,
    trade_date: str,
    position_snapshot: Mapping[str, Any],
    m2_cycle_ref: Mapping[str, Any] | None = None,
    m1_constraints_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable M3 bridge payload from the existing position snapshot contract."""

    snapshot = _copy_mapping(position_snapshot)
    position_status = _position_status_from_snapshot(snapshot)
    hold_quality_signal = _hold_quality_signal_from_snapshot(snapshot)
    warning_flags = _copy_text_list(snapshot.get("warning_flags"))
    exit_evidence_bundle = _copy_text_list(snapshot.get("exit_evidence_bundle"))

    hold_state_payload: dict[str, Any] = {}
    exit_state_payload: dict[str, Any] = {}

    if bool(snapshot.get("exit_ready")):
        exit_state = build_exit_state(
            stock_code=stock_code,
            trade_date=trade_date,
            status="exit_ready",
            exit_ready=True,
            exit_scope=str(snapshot.get("exit_scope") or "position_only").strip(),
            exit_reason_type=str(snapshot.get("exit_reason_type") or "exit_other").strip(),
            exit_attribution_bucket=str(
                snapshot.get("exit_attribution_bucket") or "exit_other"
            ).strip(),
            local_exit_semantics=str(
                snapshot.get("local_exit_semantics") or "local_end_only"
            ).strip(),
            global_thesis_end_semantics=str(
                snapshot.get("global_thesis_end_semantics")
                or "needs_global_confirmation"
            ).strip(),
            evidence_ref={
                "warning_flags": warning_flags,
                "exit_evidence_bundle": exit_evidence_bundle,
                "current_stage": str(snapshot.get("current_stage") or "").strip(),
                "decision": str(snapshot.get("decision") or "").strip(),
                "next_action": str(snapshot.get("next_action") or "").strip(),
                "last_transition": str(snapshot.get("last_transition") or "").strip(),
                "source_layer": str(snapshot.get("source_layer") or "").strip(),
            },
            m2_cycle_ref=m2_cycle_ref,
            m1_constraints_ref=m1_constraints_ref,
        )
        exit_state_payload = exit_state.to_payload()
    else:
        hold_state_value = str(snapshot.get("hold_state") or "holding").strip()
        hold_state = build_hold_state(
            stock_code=stock_code,
            trade_date=trade_date,
            status="watch" if hold_state_value in _WATCH_HOLD_STATES else "holding",
            hold_state=hold_state_value,
            warning_flags=warning_flags,
            not_exit_reasons=_copy_text_list(snapshot.get("not_exit_reasons")),
            evidence_ref={
                "noise_evidence": _copy_text_list(snapshot.get("noise_evidence")),
                "exit_evidence_bundle": exit_evidence_bundle,
                "hold_attribution_bucket": str(
                    snapshot.get("hold_attribution_bucket") or ""
                ).strip(),
                "current_stage": str(snapshot.get("current_stage") or "").strip(),
                "decision": str(snapshot.get("decision") or "").strip(),
                "next_action": str(snapshot.get("next_action") or "").strip(),
                "last_transition": str(snapshot.get("last_transition") or "").strip(),
                "source_layer": str(snapshot.get("source_layer") or "").strip(),
            },
            m2_cycle_ref=m2_cycle_ref,
            m1_constraints_ref=m1_constraints_ref,
        )
        hold_state_payload = hold_state.to_payload()

    return {
        "bridge_version": M3_HOLD_EXIT_BRIDGE_VERSION,
        "source_contract": M3_HOLD_EXIT_BRIDGE_SOURCE,
        "position_status": position_status,
        "hold_quality_signal": hold_quality_signal,
        "hold_state": hold_state_payload,
        "exit_state": exit_state_payload,
    }
