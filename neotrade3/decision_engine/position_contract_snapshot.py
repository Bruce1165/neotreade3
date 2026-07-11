from __future__ import annotations

from typing import Any, Callable


def build_position_contract_snapshot(
    *,
    market_state: str,
    sector_state: str,
    market_reason: str,
    sector_reason: str,
    grace_used: bool,
    grace_reason: str,
    market_snapshot: dict[str, Any] | None,
    sector_snapshot: dict[str, Any] | None,
    trend_snapshot: dict[str, Any] | None,
    sell_payload: dict[str, Any] | None,
    current_date_key: str,
    market_last_hit_date: str,
    sector_last_hit_date: str,
    grace_date: str,
    layer_contract_builder: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    evidence: list[str] = []
    flags: list[str] = []

    normalized_market_state = str(market_state or "").strip()
    normalized_sector_state = str(sector_state or "").strip()
    normalized_market_reason = str(market_reason or "").strip()
    normalized_sector_reason = str(sector_reason or "").strip()
    normalized_grace_reason = str(grace_reason or "").strip()

    if normalized_market_state:
        flags.append(f"market_exit_state:{normalized_market_state}")
    if normalized_sector_state:
        flags.append(f"sector_exit_state:{normalized_sector_state}")
    if bool(grace_used):
        flags.append("system_exit_grace_used")
    if normalized_market_reason:
        evidence.append(normalized_market_reason)
    if normalized_sector_reason:
        evidence.append(normalized_sector_reason)
    if normalized_grace_reason:
        evidence.append(normalized_grace_reason)

    if isinstance(market_snapshot, dict):
        market_details = str(market_snapshot.get("details") or "").strip()
        if market_details and market_details not in evidence:
            evidence.append(market_details)
        if bool(market_snapshot.get("price_trend_weak")):
            flags.append("market_price_trend_weak")
        if bool(market_snapshot.get("breadth_weak")):
            flags.append("market_breadth_weak")
        if bool(market_snapshot.get("drawdown_weak")):
            flags.append("market_drawdown_weak")

    if isinstance(sector_snapshot, dict):
        sector_details = str(sector_snapshot.get("details") or "").strip()
        if sector_details and sector_details not in evidence:
            evidence.append(sector_details)
        if bool(sector_snapshot.get("cooldown_detected")):
            flags.append("sector_cooldown_detected")
        if bool(sector_snapshot.get("trend_deteriorating")):
            flags.append("sector_trend_deteriorating")
        if bool(sector_snapshot.get("leader_rollover")):
            flags.append("sector_leader_rollover")
        if bool(sector_snapshot.get("follower_weak")):
            flags.append("sector_follower_weak")

    if isinstance(trend_snapshot, dict):
        trend_details = str(trend_snapshot.get("details") or "").strip()
        if trend_details and trend_details not in evidence:
            evidence.append(trend_details)
        if bool(trend_snapshot.get("armed")):
            flags.append("trend_exhaustion_armed")
        if bool(trend_snapshot.get("drawdown_from_peak_triggered")):
            flags.append("trend_exhaustion_triggered")

    last_transition = ""
    for value in (
        str(market_last_hit_date or "").strip(),
        str(sector_last_hit_date or "").strip(),
        str(grace_date or "").strip(),
    ):
        if value and (not last_transition or value > last_transition):
            last_transition = value

    if isinstance(sell_payload, dict):
        exit_scope = str(sell_payload.get("exit_scope") or "position_only")
        source_layer = str(sell_payload.get("source_layer") or "exit")
        exit_reason_type = str(sell_payload.get("reason") or "")
        exit_detail = str(sell_payload.get("details") or sell_payload.get("reason") or "")
        exit_contract = layer_contract_builder(
            current_stage="exit_ready",
            decision="exit",
            score=float(sell_payload.get("confidence") or 0.0),
            reasons=[exit_detail],
            evidence=evidence + [exit_detail],
            flags=flags,
            source_layer=source_layer,
            next_action="exit",
            last_transition=last_transition or str(current_date_key or ""),
        )
        return {
            "hold_state": "exit_ready",
            "noise_evidence": [],
            "not_exit_reasons": [],
            "warning_flags": list(flags),
            "hold_attribution_bucket": "",
            "exit_attribution_bucket": (
                "invalidation_exit"
                if exit_reason_type == "thesis_invalidated"
                else (
                    "trend_exhaustion_exit"
                    if exit_reason_type == "trend_exhausted"
                    else (
                        "market_timing_exit"
                        if exit_reason_type == "market_top_confirmed"
                        else (
                            "sector_timing_exit"
                            if exit_reason_type == "sector_top_confirmed"
                            else "exit_other"
                        )
                    )
                )
            ),
            "exit_ready": True,
            "exit_scope": exit_scope,
            "exit_reason_type": exit_reason_type,
            "exit_evidence_bundle": evidence + [exit_detail],
            **exit_contract,
        }

    hold_state = "holding"
    if normalized_market_state == "review" or normalized_sector_state == "review":
        hold_state = "review_watch"
    elif normalized_market_state or normalized_sector_state:
        hold_state = "observe_watch"
    elif bool(
        (isinstance(market_snapshot, dict) and int(market_snapshot.get("evidence_count") or 0) > 0)
        or (isinstance(sector_snapshot, dict) and int(sector_snapshot.get("evidence_count") or 0) > 0)
    ):
        hold_state = "noise_watch"
    elif bool(grace_used):
        hold_state = "grace_hold"

    not_exit_reasons: list[str] = []
    if normalized_market_state or normalized_sector_state:
        not_exit_reasons.append("系统退出证据尚未达到正式确认门槛")
    elif hold_state == "noise_watch":
        not_exit_reasons.append("存在弱化证据，但仍属于观察态，未达到正式退出确认")
    else:
        not_exit_reasons.append("未触发正式退出条件")
    if isinstance(trend_snapshot, dict) and bool(trend_snapshot.get("armed")) and not bool(
        trend_snapshot.get("condition_pass")
    ):
        not_exit_reasons.append("盈利仓存在回撤，但仍未达到 trend_exhausted 正式退出条件")
    if bool(grace_used):
        not_exit_reasons.append("系统退出宽限仍有效，继续持有观察")

    hold_contract = layer_contract_builder(
        current_stage="hold_confirmed",
        decision="hold",
        reasons=not_exit_reasons,
        evidence=evidence,
        flags=flags,
        source_layer="hold",
        next_action="hold",
        last_transition=last_transition,
    )
    return {
        "hold_state": str(hold_state),
        "noise_evidence": list(evidence),
        "not_exit_reasons": list(not_exit_reasons),
        "warning_flags": list(flags),
        "hold_attribution_bucket": (
            "hold_grace"
            if hold_state == "grace_hold"
            else (
                "hold_noise_watch"
                if hold_state in {"review_watch", "observe_watch", "noise_watch"}
                else "hold_confirmed"
            )
        ),
        "exit_attribution_bucket": "",
        "exit_ready": False,
        "exit_scope": "",
        "exit_reason_type": "",
        "exit_evidence_bundle": list(evidence),
        **hold_contract,
    }
