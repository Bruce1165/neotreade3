from __future__ import annotations

from neotrade3.analysis.attribution_reasoning import resolve_primary_reason_decision


def test_resolve_primary_reason_decision_prefers_held_to_top_branch() -> None:
    out = resolve_primary_reason_decision(
        bought=True,
        held_to_top=True,
        entry_picked=True,
        candidate_picked=True,
        latest_exit_reason="回测结束平仓",
        sell_reason_bucket="回测结束平仓",
        execution_primary_reason="信号存在但未形成实际成交，需复核执行窗口",
        candidate_only_primary_reason="进入候选池但未进入正式建仓池",
        not_picked_primary_reason="主升段内从未进入候选池",
    )

    assert out == {
        "primary_reason": "实际持仓延续到市场事实见顶",
        "reason_bucket": "held_to_top",
    }


def test_resolve_primary_reason_decision_keeps_bought_branch_fallback_and_bucket() -> None:
    out = resolve_primary_reason_decision(
        bought=True,
        held_to_top=False,
        entry_picked=True,
        candidate_picked=True,
        latest_exit_reason="",
        sell_reason_bucket="other",
        execution_primary_reason="unused",
        candidate_only_primary_reason="unused",
        not_picked_primary_reason="unused",
    )

    assert out == {
        "primary_reason": "已买入但未持有到见顶",
        "reason_bucket": "other",
    }


def test_resolve_primary_reason_decision_prefers_entry_branch_over_candidate() -> None:
    out = resolve_primary_reason_decision(
        bought=False,
        held_to_top=False,
        entry_picked=True,
        candidate_picked=True,
        latest_exit_reason="",
        sell_reason_bucket="other",
        execution_primary_reason="信号存在但未形成实际成交，需复核执行窗口",
        candidate_only_primary_reason="进入候选池但未进入正式建仓池",
        not_picked_primary_reason="主升段内从未进入候选池",
    )

    assert out == {
        "primary_reason": "信号存在但未形成实际成交，需复核执行窗口",
        "reason_bucket": "picked_not_bought",
    }


def test_resolve_primary_reason_decision_prefers_candidate_branch_over_not_picked() -> None:
    out = resolve_primary_reason_decision(
        bought=False,
        held_to_top=False,
        entry_picked=False,
        candidate_picked=True,
        latest_exit_reason="",
        sell_reason_bucket="other",
        execution_primary_reason="",
        candidate_only_primary_reason="进入候选池但被软保留，未进入正式建仓池",
        not_picked_primary_reason="主升段内从未进入候选池",
    )

    assert out == {
        "primary_reason": "进入候选池但被软保留，未进入正式建仓池",
        "reason_bucket": "candidate_not_entry",
    }
