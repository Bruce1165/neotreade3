from __future__ import annotations

from neotrade3.analysis.attribution_reasoning import resolve_candidate_only_primary_reason


def test_resolve_candidate_only_primary_reason_keeps_default_fallback_without_candidate_hit() -> None:
    assert resolve_candidate_only_primary_reason([]) == "进入候选池但未进入正式建仓池"


def test_resolve_candidate_only_primary_reason_maps_soft_retained() -> None:
    assert (
        resolve_candidate_only_primary_reason(
            [
                {
                    "stage": "candidate_signal_selected",
                    "signal": {"candidate_tier": "soft_retained"},
                }
            ]
        )
        == "进入候选池但被软保留，未进入正式建仓池"
    )


def test_resolve_candidate_only_primary_reason_keeps_default_for_non_dict_signal() -> None:
    assert (
        resolve_candidate_only_primary_reason(
            [
                {
                    "stage": "candidate_signal_selected",
                    "signal": "not-a-dict",
                }
            ]
        )
        == "进入候选池但未进入正式建仓池"
    )
