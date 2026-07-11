from __future__ import annotations

from neotrade3.analysis.attribution_reasoning import resolve_not_picked_primary_reason


def test_resolve_not_picked_primary_reason_keeps_empty_fallback() -> None:
    assert resolve_not_picked_primary_reason([]) == "主升段内从未进入候选池"


def test_resolve_not_picked_primary_reason_prefers_highest_stage_priority() -> None:
    assert (
        resolve_not_picked_primary_reason(
            [
                {"stage": "market_filtered", "reason": "低优先级原因"},
                {"stage": "candidate_signal_selected", "reason": "高优先级原因"},
            ]
        )
        == "高优先级原因"
    )


def test_resolve_not_picked_primary_reason_uses_most_common_reason_within_priority() -> None:
    assert (
        resolve_not_picked_primary_reason(
            [
                {"stage": "global_cap_filtered", "reason": "容量约束"},
                {"stage": "global_cap_filtered", "reason": "容量约束"},
                {"stage": "global_cap_filtered", "reason": "分数不足"},
                {"stage": "market_filtered", "reason": "低优先级原因"},
            ]
        )
        == "容量约束"
    )


def test_resolve_not_picked_primary_reason_keeps_no_reason_fallback() -> None:
    assert (
        resolve_not_picked_primary_reason(
            [
                {"stage": "candidate_signal_selected", "reason": ""},
                {"stage": "entry_signal_selected"},
            ]
        )
        == "主升段内从未进入候选池"
    )
