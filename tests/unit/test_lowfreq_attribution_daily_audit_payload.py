from __future__ import annotations

from neotrade3.analysis.attribution_daily_audit_payload import (
    build_candidate_signal_selected_audit,
    build_entry_signal_selected_audit,
)


def test_build_entry_signal_selected_audit_projects_current_payload() -> None:
    out = build_entry_signal_selected_audit(
        audit_date="2025-06-18",
        signal={
            "buy_score": "95.0",
            "role": "龙头",
            "wave_phase": "3浪",
            "candidate_tier": "entry_ready",
            "reasons": ("正式建仓",),
        },
    )

    assert out == {
        "date": "2025-06-18",
        "stage": "entry_signal_selected",
        "reason": "进入正式建仓池",
        "signal": {
            "buy_score": 95.0,
            "role": "龙头",
            "wave_phase": "3浪",
            "candidate_tier": "entry_ready",
            "reasons": ["正式建仓"],
        },
    }


def test_build_candidate_signal_selected_audit_projects_current_payload() -> None:
    out = build_candidate_signal_selected_audit(
        audit_date="2025-06-18",
        signal={
            "buy_score": "90.0",
            "role": "龙头",
            "wave_phase": "1浪",
            "candidate_tier": "soft_retained",
            "entry_ready": 0,
            "reasons": ("soft retained",),
        },
    )

    assert out == {
        "date": "2025-06-18",
        "stage": "candidate_signal_selected",
        "reason": "进入候选池，但未进入正式建仓池",
        "signal": {
            "buy_score": 90.0,
            "role": "龙头",
            "wave_phase": "1浪",
            "candidate_tier": "soft_retained",
            "entry_ready": False,
            "reasons": ["soft retained"],
        },
    }


def test_build_candidate_signal_selected_audit_keeps_entry_ready_independent() -> None:
    out = build_candidate_signal_selected_audit(
        audit_date="2025-06-18",
        signal={
            "buy_score": 88.0,
            "role": "龙头",
            "wave_phase": "1浪",
            "candidate_tier": "soft_retained",
            "entry_ready": True,
            "reasons": [],
        },
    )

    assert out["signal"]["candidate_tier"] == "soft_retained"
    assert out["signal"]["entry_ready"] is True
