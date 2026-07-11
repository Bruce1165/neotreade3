"""Snapshot helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any

from neotrade3.decision_engine import project_lowfreq_formal_front


def build_attribution_signal_snapshot(raw: Any) -> dict[str, Any]:
    def _signal_with_formal_priority(signal_payload: dict[str, Any]) -> dict[str, Any]:
        item = dict(signal_payload)
        formal_front = project_lowfreq_formal_front(item)
        if isinstance(formal_front, dict):
            item["formal_front"] = dict(formal_front)
        if not isinstance(formal_front, dict) or str(formal_front.get("status") or "") != "ok":
            return item

        entry_state = formal_front.get("entry_state") if isinstance(formal_front.get("entry_state"), dict) else {}
        tracking_state = formal_front.get("tracking_state") if isinstance(formal_front.get("tracking_state"), dict) else {}
        identify_state = formal_front.get("identify_state") if isinstance(formal_front.get("identify_state"), dict) else {}
        entry_ready = bool(entry_state.get("actionable")) or str(entry_state.get("status") or "") == "ready"
        candidate_tier = str(item.get("candidate_tier") or "").strip()
        if entry_ready:
            candidate_tier = "entry_ready"
        elif str(tracking_state.get("status") or "") == "tracking" or str(identify_state.get("status") or "") == "identified":
            candidate_tier = "soft_retained"
        item["entry_ready"] = entry_ready
        if candidate_tier:
            item["candidate_tier"] = candidate_tier
        return item

    candidate_signals: dict[str, dict[str, Any]] = {}
    entry_signals: dict[str, dict[str, Any]] = {}
    signal_summary: dict[str, Any] = {}

    if isinstance(raw, dict):
        summary = raw.get("signal_summary")
        if isinstance(summary, dict):
            signal_summary = dict(summary)

        raw_entry = raw.get("entry_signals")
        if not isinstance(raw_entry, list):
            raw_entry = []

        raw_candidate = raw.get("candidate_signals")
        if not isinstance(raw_candidate, list):
            raw_candidate = raw_entry

        for item in raw_candidate:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip()
            if code:
                candidate_signals[code] = _signal_with_formal_priority(item)

        for item in raw_entry:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip()
            if code:
                entry_signals[code] = _signal_with_formal_priority(item)

    signal_summary.setdefault("candidate_count", len(candidate_signals))
    signal_summary.setdefault("entry_count", len(entry_signals))
    signal_summary.setdefault(
        "soft_retained_count",
        sum(1 for item in candidate_signals.values() if str(item.get("candidate_tier") or "") == "soft_retained"),
    )
    return {
        "candidate_signals": candidate_signals,
        "entry_signals": entry_signals,
        "signal_summary": signal_summary,
    }
