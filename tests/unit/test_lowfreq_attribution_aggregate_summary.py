from __future__ import annotations

from collections import Counter

from neotrade3.analysis.attribution_aggregate_summary import build_attribution_aggregate_summary


def test_build_attribution_aggregate_summary_computes_visible_counts() -> None:
    out = build_attribution_aggregate_summary(
        [
            {
                "candidate_picked": True,
                "entry_picked": True,
                "picked": True,
                "bought": True,
                "held_to_top": False,
            },
            {
                "candidate_picked": True,
                "entry_picked": False,
                "picked": False,
                "bought": False,
                "held_to_top": False,
            },
            {
                "candidate_picked": False,
                "entry_picked": False,
                "picked": False,
                "bought": True,
                "held_to_top": True,
            },
        ],
        {"candidate_not_entry": 1, "held_to_top": 1},
    )

    assert out["count"] == 3
    assert out["candidate_picked_count"] == 2
    assert out["entry_picked_count"] == 1
    assert out["bought_count"] == 2
    assert out["held_to_top_count"] == 1
    assert out["reason_buckets"] == {"candidate_not_entry": 1, "held_to_top": 1}


def test_build_attribution_aggregate_summary_keeps_picked_count_aligned_with_entry_picked() -> None:
    out = build_attribution_aggregate_summary(
        [
            {
                "candidate_picked": True,
                "entry_picked": False,
                "picked": True,
                "bought": False,
                "held_to_top": False,
            }
        ],
        {},
    )

    assert out["entry_picked_count"] == 0
    assert out["picked_count"] == 0


def test_build_attribution_aggregate_summary_materializes_reason_buckets_as_plain_dict() -> None:
    out = build_attribution_aggregate_summary(
        [],
        Counter({"candidate_not_entry": 2}),
    )

    assert out["reason_buckets"] == {"candidate_not_entry": 2}
    assert type(out["reason_buckets"]) is dict
