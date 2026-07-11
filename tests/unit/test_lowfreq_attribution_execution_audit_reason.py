from __future__ import annotations

from neotrade3.analysis.attribution_reasoning import resolve_execution_audit_primary_reason


def test_resolve_execution_audit_primary_reason_prefers_latest_block_and_appends_late_trade_suffix() -> None:
    assert (
        resolve_execution_audit_primary_reason(
            buy_signal_audits=[
                {
                    "date": "2025-08-29",
                    "action_type": "block",
                    "blocked_reason": "execution_signal_gate_blocked",
                },
                {
                    "date": "2025-09-01",
                    "action_type": "block",
                    "blocked_reason": "chase_entry_blocked",
                },
            ],
            code_trades=[{"buy_date": "2025-09-03", "sell_date": "2025-09-05"}],
            segment_top_date="2025-09-02",
        )
        == "信号存在但因追高型买点被硬禁，见顶后才成交"
    )


def test_resolve_execution_audit_primary_reason_keeps_plain_late_trade_fallback_without_mapped_audit_reason() -> None:
    assert (
        resolve_execution_audit_primary_reason(
            buy_signal_audits=[
                {
                    "date": "2025-09-01",
                    "action_type": "block",
                    "blocked_reason": "custom_reason",
                }
            ],
            code_trades=[{"buy_date": "2025-09-03"}],
            segment_top_date="2025-09-02",
        )
        == "信号存在但见顶后才成交"
    )


def test_resolve_execution_audit_primary_reason_returns_empty_without_usable_audit_or_late_trade() -> None:
    assert (
        resolve_execution_audit_primary_reason(
            buy_signal_audits=[
                {
                    "date": "2025-09-03",
                    "action_type": "block",
                    "blocked_reason": "chase_entry_blocked",
                }
            ],
            code_trades=[],
            segment_top_date="2025-09-02",
        )
        == ""
    )
