"""Reasoning helpers for lowfreq attribution report consumers."""

from __future__ import annotations

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
