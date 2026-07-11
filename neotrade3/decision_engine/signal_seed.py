from __future__ import annotations

from typing import Any


def build_hot_sector_signal_seed(candidate: Any, *, market_filter_note: str | None) -> dict[str, Any]:
    reasons = list(candidate.buy_reasons)
    if market_filter_note:
        reasons.append(market_filter_note)

    return {
        "code": candidate.code,
        "name": candidate.name,
        "sector": candidate.sector,
        "buy_score": float(candidate.buy_score),
        "market_cap_yi": candidate.market_cap_yi,
        "wave_phase": candidate.wave_phase,
        "role": candidate.role,
        "reasons": reasons,
        "pe": candidate.pe_ttm,
        "profit_growth": candidate.profit_growth,
        "resonance": candidate.sector_resonance,
        "cup_handle_ok": bool(getattr(candidate, "cup_handle_ok", False)),
        "signal_source": str(getattr(candidate, "signal_source", "") or "hot_sector"),
        "soft_flags": list(getattr(candidate, "soft_flags", []) or []),
    }


def build_cross_sector_signal_seed(
    candidate: Any,
    *,
    market_filter_note: str | None,
    wave3_only: bool,
    allowed_waves: set[str],
) -> dict[str, Any]:
    reasons = ["跨板块扫描"] + list(candidate.buy_reasons)
    soft_flags = list(getattr(candidate, "soft_flags", []) or [])

    if wave3_only and str(candidate.wave_phase) not in allowed_waves:
        reasons.append("capture-first: 波段不符，降权保留")
        soft_flags.append("wave_uncertain")

    if market_filter_note:
        reasons.append(market_filter_note)

    return {
        "code": candidate.code,
        "name": candidate.name,
        "sector": candidate.sector,
        "buy_score": float(candidate.buy_score),
        "market_cap_yi": candidate.market_cap_yi,
        "wave_phase": candidate.wave_phase,
        "role": candidate.role,
        "reasons": reasons,
        "pe": candidate.pe_ttm,
        "profit_growth": candidate.profit_growth,
        "resonance": candidate.sector_resonance,
        "cross_sector": True,
        "cup_handle_ok": bool(getattr(candidate, "cup_handle_ok", False)),
        "signal_source": str(getattr(candidate, "signal_source", "") or "cross_sector"),
        "soft_flags": soft_flags,
    }
