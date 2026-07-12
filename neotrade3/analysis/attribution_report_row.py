"""Report row projection helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any


def build_attribution_segment_failed_row(
    *,
    rank: Any,
    code: str,
    name: str,
    annual_return_pct: Any,
    segment_status: str,
) -> dict[str, Any]:
    return {
        "rank": int(rank),
        "code": str(code),
        "name": str(name),
        "annual_return_pct": float(annual_return_pct),
        "segment_status": str(segment_status or "unknown"),
        "candidate_picked": False,
        "entry_picked": False,
        "picked": False,
        "bought": False,
        "held_to_top": False,
        "primary_reason": "主升段识别失败",
    }


def build_attribution_report_row(
    *,
    rank: Any,
    code: str,
    name: str,
    sector: str,
    annual_return_pct: Any,
    segment_start_date: str,
    segment_top_date: str,
    segment_return_pct: Any,
    candidate_picked: bool,
    entry_picked: bool,
    picked: bool,
    first_candidate_date: str,
    candidate_signal_count_in_segment: Any,
    first_entry_date: str,
    first_signal_date: str,
    entry_signal_count_in_segment: Any,
    signal_count_in_segment: Any,
    bought: bool,
    first_buy_date: str,
    first_sell_date: str,
    held_to_top: bool,
    primary_reason: str,
    reason_bucket: str,
    daily_audits: list[dict[str, Any]],
    relevant_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "rank": int(rank),
        "code": str(code),
        "name": str(name),
        "sector": str(sector),
        "annual_return_pct": float(annual_return_pct),
        "segment_start_date": str(segment_start_date),
        "segment_top_date": str(segment_top_date),
        "segment_return_pct": float(segment_return_pct),
        "candidate_picked": bool(candidate_picked),
        "entry_picked": bool(entry_picked),
        "picked": bool(picked),
        "first_candidate_date": str(first_candidate_date or ""),
        "candidate_signal_count_in_segment": int(candidate_signal_count_in_segment),
        "first_entry_date": str(first_entry_date or ""),
        "first_signal_date": str(first_signal_date or ""),
        "entry_signal_count_in_segment": int(entry_signal_count_in_segment),
        "signal_count_in_segment": int(signal_count_in_segment),
        "bought": bool(bought),
        "first_buy_date": str(first_buy_date or ""),
        "first_sell_date": str(first_sell_date or ""),
        "held_to_top": bool(held_to_top),
        "primary_reason": str(primary_reason or ""),
        "reason_bucket": str(reason_bucket or ""),
        "daily_audits": daily_audits,
        "relevant_trades": relevant_trades,
    }
