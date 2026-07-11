from __future__ import annotations

from neotrade3.analysis.attribution_reasoning import resolve_audit_block_reason_text


def test_resolve_audit_block_reason_text_maps_blocked_reason_priority() -> None:
    assert (
        resolve_audit_block_reason_text(
            {
                "blocked_reason": "chase_entry_blocked",
                "execution_block_reason": "execution_rule_blocked",
            }
        )
        == "信号存在但因追高型买点被硬禁"
    )
    assert (
        resolve_audit_block_reason_text(
            {
                "blocked_reason": "execution_signal_gate_blocked",
                "execution_block_reason": "entry_window_missed",
            }
        )
        == "信号存在但因执行信号闸门被阻断"
    )


def test_resolve_audit_block_reason_text_maps_execution_block_reason_buckets() -> None:
    assert (
        resolve_audit_block_reason_text({"execution_block_reason": "entry_window_missed"})
        == "信号存在但执行窗口失效"
    )
    assert (
        resolve_audit_block_reason_text({"execution_block_reason": "positions_full"})
        == "信号存在但同期仓位已满"
    )
    assert (
        resolve_audit_block_reason_text({"execution_block_reason": "cash_insufficient"})
        == "信号存在但资金不足"
    )


def test_resolve_audit_block_reason_text_returns_empty_for_unknown_reason() -> None:
    assert resolve_audit_block_reason_text({"execution_block_reason": "custom_reason"}) == ""
