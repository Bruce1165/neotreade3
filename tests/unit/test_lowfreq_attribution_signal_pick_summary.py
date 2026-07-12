from __future__ import annotations

from neotrade3.analysis.attribution_signal_pick_summary import build_attribution_signal_pick_summary


def test_build_attribution_signal_pick_summary_maps_candidate_only_stage() -> None:
    out = build_attribution_signal_pick_summary(
        [
            {"date": "2025-09-01", "stage": "global_seed_miss"},
            {"date": "2025-09-02", "stage": "candidate_signal_selected"},
        ]
    )

    assert out["candidate_dates"] == ["2025-09-02"]
    assert out["entry_dates"] == []
    assert out["candidate_picked"] is True
    assert out["entry_picked"] is False
    assert out["picked"] is False
    assert out["first_candidate_date"] == "2025-09-02"
    assert out["candidate_signal_count_in_segment"] == 1
    assert out["first_entry_date"] == ""


def test_build_attribution_signal_pick_summary_maps_entry_stage_to_both_streams() -> None:
    out = build_attribution_signal_pick_summary(
        [
            {"date": "2025-09-02", "stage": "candidate_signal_selected"},
            {"date": "2025-09-03", "stage": "entry_signal_selected"},
        ]
    )

    assert out["candidate_dates"] == ["2025-09-02", "2025-09-03"]
    assert out["entry_dates"] == ["2025-09-03"]
    assert out["candidate_picked"] is True
    assert out["entry_picked"] is True
    assert out["picked"] is True
    assert out["first_entry_date"] == "2025-09-03"
    assert out["first_signal_date"] == "2025-09-03"
    assert out["entry_signal_count_in_segment"] == 1
    assert out["signal_count_in_segment"] == 1


def test_build_attribution_signal_pick_summary_keeps_empty_defaults_without_match() -> None:
    out = build_attribution_signal_pick_summary(
        [
            {"date": "2025-09-01", "stage": "global_seed_miss"},
            {"date": "2025-09-02", "stage": "global_cap_filtered"},
        ]
    )

    assert out["candidate_dates"] == []
    assert out["entry_dates"] == []
    assert out["candidate_picked"] is False
    assert out["entry_picked"] is False
    assert out["picked"] is False
    assert out["first_candidate_date"] == ""
    assert out["candidate_signal_count_in_segment"] == 0
    assert out["first_entry_date"] == ""
    assert out["first_signal_date"] == ""
    assert out["entry_signal_count_in_segment"] == 0
    assert out["signal_count_in_segment"] == 0
