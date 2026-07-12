"""Daily audit payload helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any


def build_simple_stage_audit(*, audit_date: str, stage: str, reason: str) -> dict[str, Any]:
    return {
        "date": str(audit_date or ""),
        "stage": str(stage or ""),
        "reason": str(reason or ""),
    }


def build_entry_signal_selected_audit(*, audit_date: str, signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": str(audit_date or ""),
        "stage": "entry_signal_selected",
        "reason": "进入正式建仓池",
        "signal": {
            "buy_score": float(signal.get("buy_score") or 0.0),
            "role": str(signal.get("role") or ""),
            "wave_phase": str(signal.get("wave_phase") or ""),
            "candidate_tier": str(signal.get("candidate_tier") or ""),
            "reasons": list(signal.get("reasons") or []),
        },
    }


def build_candidate_signal_selected_audit(*, audit_date: str, signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": str(audit_date or ""),
        "stage": "candidate_signal_selected",
        "reason": "进入候选池，但未进入正式建仓池",
        "signal": {
            "buy_score": float(signal.get("buy_score") or 0.0),
            "role": str(signal.get("role") or ""),
            "wave_phase": str(signal.get("wave_phase") or ""),
            "candidate_tier": str(signal.get("candidate_tier") or ""),
            "entry_ready": bool(signal.get("entry_ready")),
            "reasons": list(signal.get("reasons") or []),
        },
    }
