from __future__ import annotations

from neotrade3.analysis.attribution_reasoning import resolve_execution_fallback_reason


def test_resolve_execution_fallback_reason_prioritizes_all_limit_up() -> None:
    assert (
        resolve_execution_fallback_reason(
            all_limit_up=True,
            positions_full=True,
            chase_blocked=True,
        )
        == "信号存在但连续涨停，无法成交"
    )


def test_resolve_execution_fallback_reason_reuses_positions_full_text() -> None:
    assert (
        resolve_execution_fallback_reason(
            all_limit_up=False,
            positions_full=True,
            chase_blocked=True,
        )
        == "信号存在但同期仓位已满"
    )


def test_resolve_execution_fallback_reason_reuses_chase_blocked_text() -> None:
    assert (
        resolve_execution_fallback_reason(
            all_limit_up=False,
            positions_full=False,
            chase_blocked=True,
        )
        == "信号存在但因追高型买点被硬禁"
    )


def test_resolve_execution_fallback_reason_keeps_generic_default() -> None:
    assert (
        resolve_execution_fallback_reason(
            all_limit_up=False,
            positions_full=False,
            chase_blocked=False,
        )
        == "信号存在但未形成实际成交，需复核执行窗口"
    )
