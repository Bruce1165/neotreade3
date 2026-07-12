"""Signal-pick summary helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any


def build_attribution_signal_pick_summary(daily_audits: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_dates: list[str] = []
    entry_dates: list[str] = []
    for audit in daily_audits:
        stage = str(audit.get("stage") or "")
        audit_date = str(audit.get("date") or "")
        if stage in {"candidate_signal_selected", "entry_signal_selected"}:
            candidate_dates.append(audit_date)
        if stage == "entry_signal_selected":
            entry_dates.append(audit_date)
    return {
        "candidate_dates": candidate_dates,
        "entry_dates": entry_dates,
        "candidate_picked": bool(candidate_dates),
        "entry_picked": bool(entry_dates),
        "picked": bool(entry_dates),
        "first_candidate_date": candidate_dates[0] if candidate_dates else "",
        "candidate_signal_count_in_segment": len(candidate_dates),
        "first_entry_date": entry_dates[0] if entry_dates else "",
        "first_signal_date": entry_dates[0] if entry_dates else "",
        "entry_signal_count_in_segment": len(entry_dates),
        "signal_count_in_segment": len(entry_dates),
    }
