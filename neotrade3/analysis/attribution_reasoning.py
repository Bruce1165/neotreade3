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
