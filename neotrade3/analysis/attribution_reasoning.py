"""Reasoning helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from collections import Counter
from typing import Any


def resolve_audit_block_reason_text(entry: dict[str, Any]) -> str:
    blocked_reason = str(entry.get("blocked_reason") or "").strip()
    execution_block_reason = str(entry.get("execution_block_reason") or "").strip()
    if blocked_reason == "chase_entry_blocked":
        return "信号存在但因追高型买点被硬禁"
    if blocked_reason == "execution_signal_gate_blocked":
        return "信号存在但因执行信号闸门被阻断"
    if execution_block_reason == "entry_window_missed":
        return "信号存在但执行窗口失效"
    if execution_block_reason == "positions_full":
        return "信号存在但同期仓位已满"
    if execution_block_reason == "cash_insufficient":
        return "信号存在但资金不足"
    return ""


def resolve_execution_audit_primary_reason(
    *,
    buy_signal_audits: list[dict[str, Any]],
    code_trades: list[dict[str, Any]],
    segment_top_date: str,
) -> str:
    top_key = str(segment_top_date or "").strip()
    top_audits = [x for x in buy_signal_audits if str(x.get("date") or "") <= top_key] if top_key else list(buy_signal_audits)
    blocking_audits = [x for x in top_audits if str(x.get("action_type") or "") == "block"]
    late_trades = [x for x in code_trades if top_key and str(x.get("buy_date") or "") > top_key]
    if blocking_audits:
        latest_block = max(blocking_audits, key=lambda x: str(x.get("date") or ""))
        reason = resolve_audit_block_reason_text(latest_block)
        if reason:
            if late_trades:
                return f"{reason}，见顶后才成交"
            return reason
    if late_trades:
        return "信号存在但见顶后才成交"
    return ""


def resolve_execution_fallback_reason(
    *,
    all_limit_up: bool,
    positions_full: bool,
    chase_blocked: bool,
) -> str:
    if all_limit_up:
        return "信号存在但连续涨停，无法成交"
    if positions_full:
        return resolve_audit_block_reason_text({"execution_block_reason": "positions_full"})
    if chase_blocked:
        return resolve_audit_block_reason_text({"blocked_reason": "chase_entry_blocked"})
    return "信号存在但未形成实际成交，需复核执行窗口"


def resolve_sell_reason_bucket(sell_reason: str) -> str:
    reason = str(sell_reason or "").strip()
    if reason.startswith("回测结束平仓"):
        return "回测结束平仓"
    if "板块见顶确认" in reason:
        return "sector_top_confirmed"
    if "见顶确认" in reason or "见顶：" in reason:
        return "market_top_confirmed"
    if "跌破买入价止损" in reason or "硬证伪退出" in reason:
        return "thesis_invalidated"
    return "other"


def resolve_not_picked_primary_reason(daily_audits: list[dict[str, Any]]) -> str:
    stage_priority = {
        "market_filtered": 1,
        "market_candidate_filtered": 2,
        "sector_filtered": 2,
        "sector_candidate_filtered": 3,
        "global_candidate_filtered": 3,
        "score_below_threshold": 4,
        "follower_filtered": 4,
        "resonance_filtered": 4,
        "global_follower_filtered": 4,
        "global_resonance_filtered": 4,
        "global_wave_filtered": 4,
        "global_score_filtered": 4,
        "global_cap_filtered": 5,
        "sector_candidate_not_selected": 5,
        "candidate_signal_selected": 6,
        "entry_signal_selected": 7,
    }
    if not daily_audits:
        return "主升段内从未进入候选池"
    max_priority = max(int(stage_priority.get(str(x.get("stage") or ""), 0)) for x in daily_audits)
    preferred = [x for x in daily_audits if int(stage_priority.get(str(x.get("stage") or ""), 0)) == max_priority]
    if not preferred:
        preferred = daily_audits
    reason_counter = Counter(str(x.get("reason") or "") for x in preferred if x.get("reason"))
    if not reason_counter:
        return "主升段内从未进入候选池"
    return str(reason_counter.most_common(1)[0][0])


def resolve_candidate_only_primary_reason(daily_audits: list[dict[str, Any]]) -> str:
    candidate_hits = [x for x in daily_audits if str(x.get("stage") or "") == "candidate_signal_selected"]
    if not candidate_hits:
        return "进入候选池但未进入正式建仓池"
    first_hit = candidate_hits[0]
    signal = first_hit.get("signal") if isinstance(first_hit.get("signal"), dict) else {}
    if str(signal.get("candidate_tier") or "") == "soft_retained":
        return "进入候选池但被软保留，未进入正式建仓池"
    return "进入候选池但未进入正式建仓池"


def resolve_primary_reason_decision(
    *,
    bought: bool,
    held_to_top: bool,
    entry_picked: bool,
    candidate_picked: bool,
    latest_exit_reason: str,
    sell_reason_bucket: str,
    execution_primary_reason: str,
    candidate_only_primary_reason: str,
    not_picked_primary_reason: str,
) -> dict[str, str]:
    if bought and held_to_top:
        return {
            "primary_reason": "实际持仓延续到市场事实见顶",
            "reason_bucket": "held_to_top",
        }
    if bought:
        return {
            "primary_reason": str(latest_exit_reason or "") or "已买入但未持有到见顶",
            "reason_bucket": str(sell_reason_bucket or ""),
        }
    if entry_picked:
        return {
            "primary_reason": str(execution_primary_reason or ""),
            "reason_bucket": "picked_not_bought",
        }
    if candidate_picked:
        return {
            "primary_reason": str(candidate_only_primary_reason or ""),
            "reason_bucket": "candidate_not_entry",
        }
    return {
        "primary_reason": str(not_picked_primary_reason or ""),
        "reason_bucket": "not_picked",
    }
