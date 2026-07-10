from __future__ import annotations

from datetime import date
from typing import Any


def build_signal_structure_payload(
    *,
    deduped_signals: dict[str, dict[str, Any]],
    target_date: date,
    market_filter_note: str | None,
) -> dict[str, Any]:
    candidate_signals = sorted(
        deduped_signals.values(),
        key=lambda item: (float(item.get("buy_score") or 0.0), float(item.get("resonance") or 0.0)),
        reverse=True,
    )
    entry_signals = [dict(sig) for sig in candidate_signals if bool(sig.get("entry_ready"))]
    return {
        "buy_signals": list(entry_signals),
        "candidate_signals": candidate_signals,
        "entry_signals": entry_signals,
        "signal_summary": {
            "candidate_count": len(candidate_signals),
            "entry_count": len(entry_signals),
            "soft_retained_count": sum(
                1 for sig in candidate_signals if str(sig.get("candidate_tier") or "") == "soft_retained"
            ),
        },
        "date": target_date.isoformat(),
        "capture_first_mode": True,
        "market_filter_note": market_filter_note,
    }
