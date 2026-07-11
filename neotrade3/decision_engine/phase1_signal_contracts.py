from __future__ import annotations

from typing import Any, Callable


def _normalized_text_list(values: list[Any] | None) -> list[str]:
    return [str(x or "").strip() for x in list(values or []) if str(x or "").strip()]


def candidate_tier_from_signal(sig: dict[str, Any]) -> str:
    soft_flags = _normalized_text_list(list(sig.get("soft_flags") or []))
    if soft_flags:
        return "soft_retained"
    return "execution_eligible"


def tracking_snapshot_from_signal(sig: dict[str, Any]) -> dict[str, Any]:
    reasons = _normalized_text_list(list(sig.get("reasons") or []))
    evidence = _normalized_text_list(list(sig.get("entry_reasons") or reasons))
    flags = _normalized_text_list(list(sig.get("soft_flags") or []))
    candidate_tier = str(sig.get("candidate_tier") or candidate_tier_from_signal(sig))
    entry_ready = bool(sig.get("entry_ready")) if "entry_ready" in sig else candidate_tier != "soft_retained"
    tracking_state = str(
        sig.get("tracking_state") or ("tracking_mature" if entry_ready else "tracking_observe")
    ).strip()
    tracking_days = max(int(sig.get("tracking_days") or 1), 1)
    transition_reason = str(
        sig.get("tracking_transition_reason")
        or ("candidate_meets_current_entry_contract" if entry_ready else "candidate_retained_for_tracking")
    ).strip()
    decision = "tracking_ready_for_entry" if entry_ready else "tracking_continue"
    next_action = "promote_to_entry" if entry_ready else "continue_tracking"
    current_stage = "entry_ready" if entry_ready else "candidate_detected"
    details = (
        "tracking 晋升：候选当前满足 entry 条件"
        if entry_ready
        else "tracking 继续：候选保留观察，尚未进入正式 entry"
    )
    return {
        "tracking_ready": bool(entry_ready),
        "tracking_state": tracking_state,
        "tracking_days": int(tracking_days),
        "tracking_transition_reason": transition_reason,
        "tracking_evidence_bundle": list(evidence or reasons),
        "tracking_flags": list(flags),
        "tracking_decision": decision,
        "tracking_next_action": next_action,
        "tracking_current_stage": current_stage,
        "tracking_details": details,
    }


def decorate_signal_with_phase1_contracts(
    sig: dict[str, Any],
    *,
    wave1_tracking_only_enabled: bool,
    wave1_value: str,
    layer_contract_builder: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    out = dict(sig)
    buy_score = float(out.get("buy_score") or 0.0)
    reasons = _normalized_text_list(list(out.get("reasons") or []))
    soft_flags = _normalized_text_list(list(out.get("soft_flags") or []))
    wave_phase = str(out.get("wave_phase") or "").strip()
    if bool(wave1_tracking_only_enabled) and wave_phase == str(wave1_value):
        if "wave1_tracking_only" not in soft_flags:
            soft_flags.append("wave1_tracking_only")
        if "capture-first: 1浪仅保留 tracking，不进入正式建仓" not in reasons:
            reasons.append("capture-first: 1浪仅保留 tracking，不进入正式建仓")
        out["soft_flags"] = list(soft_flags)
        out["reasons"] = list(reasons)
    signal_source = str(out.get("signal_source") or "buy_signal")
    candidate_tier = candidate_tier_from_signal(out)
    entry_ready = candidate_tier != "soft_retained"
    tracking_snapshot = tracking_snapshot_from_signal(
        {
            **out,
            "candidate_tier": candidate_tier,
            "entry_ready": entry_ready,
        }
    )
    candidate_contract = layer_contract_builder(
        current_stage="candidate_detected",
        decision="candidate_detected",
        score=buy_score,
        reasons=reasons,
        evidence=reasons,
        flags=soft_flags,
        source_layer="discovery",
        next_action="evaluate_entry",
    )
    tracking_contract = layer_contract_builder(
        current_stage=str(tracking_snapshot.get("tracking_current_stage") or "candidate_detected"),
        decision=str(tracking_snapshot.get("tracking_decision") or "tracking_continue"),
        score=buy_score,
        reasons=list(tracking_snapshot.get("tracking_evidence_bundle") or reasons),
        evidence=list(tracking_snapshot.get("tracking_evidence_bundle") or reasons),
        flags=list(tracking_snapshot.get("tracking_flags") or soft_flags),
        source_layer="tracking",
        next_action=str(tracking_snapshot.get("tracking_next_action") or "continue_tracking"),
    )
    entry_contract = layer_contract_builder(
        current_stage="entry_ready" if entry_ready else "candidate_detected",
        decision="entry_ready" if entry_ready else "candidate_only",
        score=buy_score,
        reasons=reasons,
        evidence=reasons,
        flags=soft_flags,
        source_layer="entry",
        next_action="queue_for_execution" if entry_ready else "observe_candidate",
    )
    out.update(
        {
            "candidate_detected": True,
            "candidate_score": buy_score,
            "candidate_reasons": list(reasons),
            "candidate_tier": str(candidate_tier),
            "entry_ready": bool(entry_ready),
            "tracking_ready": bool(tracking_snapshot.get("tracking_ready")),
            "tracking_state": str(tracking_snapshot.get("tracking_state") or ""),
            "tracking_days": int(tracking_snapshot.get("tracking_days") or 0),
            "tracking_transition_reason": str(tracking_snapshot.get("tracking_transition_reason") or ""),
            "tracking_evidence_bundle": list(tracking_snapshot.get("tracking_evidence_bundle") or []),
            "entry_signal_type": signal_source,
            "entry_confidence": buy_score,
            "entry_reasons": list(reasons),
            "entry_risk_flags": list(soft_flags),
            "candidate_contract": candidate_contract,
            "tracking_contract": tracking_contract,
            "entry_contract": entry_contract,
        }
    )
    return out
