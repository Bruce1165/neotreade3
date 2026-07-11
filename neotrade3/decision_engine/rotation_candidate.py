from __future__ import annotations

from typing import Any


def build_rotation_candidate_snapshot(
    *,
    rotation_enabled: bool,
    incoming_score: float,
    held_score: float,
    min_score_margin: float,
    base_snapshot: dict[str, Any] | None,
    max_current_return_pct: float,
    min_evidence: int,
    profit_keep_ratio: float,
    trade_code: str,
) -> dict[str, Any] | None:
    if not bool(rotation_enabled):
        return None

    normalized_incoming_score = float(incoming_score or 0.0)
    normalized_held_score = float(held_score or 0.0)
    normalized_score_gap = normalized_incoming_score - normalized_held_score
    normalized_min_score_margin = float(min_score_margin or 0.0)
    if normalized_score_gap < normalized_min_score_margin:
        return None

    if not isinstance(base_snapshot, dict):
        return None

    current_price = float(base_snapshot.get("current_price") or 0.0)
    if current_price <= 0.0:
        return None

    current_return_pct = float(base_snapshot.get("current_return_pct") or 0.0)
    normalized_max_current_return_pct = float(max_current_return_pct or 0.0)
    if current_return_pct > normalized_max_current_return_pct:
        return None

    market_evidence = int(base_snapshot.get("market_evidence") or 0)
    sector_evidence = int(base_snapshot.get("sector_evidence") or 0)
    normalized_min_evidence = int(min_evidence or 0)
    watch_active = bool(base_snapshot.get("watch_active"))
    weakening = bool(base_snapshot.get("weakening"))
    peak_return_pct = float(base_snapshot.get("peak_return_pct") or 0.0)
    max_evidence = max(market_evidence, sector_evidence)
    if not weakening and max_evidence < normalized_min_evidence:
        return None

    normalized_profit_keep_ratio = float(profit_keep_ratio or 0.0)
    priority = (
        normalized_score_gap
        + float(max_evidence) * 10.0
        + (5.0 if watch_active else 0.0)
        + (3.0 if weakening else 0.0)
        - max(current_return_pct, 0.0) * 0.1
    )
    details = (
        f"弱化持仓换仓候选 | score_gap={normalized_score_gap:.1f} | "
        f"market_evidence={market_evidence} | sector_evidence={sector_evidence} | "
        f"current_return={current_return_pct:.1f}% | keep_ratio={normalized_profit_keep_ratio:.2f}"
    )
    return {
        "code": str(trade_code),
        "current_price": current_price,
        "current_return_pct": current_return_pct,
        "peak_return_pct": peak_return_pct,
        "profit_keep_ratio": normalized_profit_keep_ratio,
        "market_evidence": market_evidence,
        "sector_evidence": sector_evidence,
        "watch_active": watch_active,
        "weakening": weakening,
        "score_gap": normalized_score_gap,
        "priority": float(priority),
        "details": details,
    }


def select_rotation_candidate(
    *,
    candidate_snapshots: list[tuple[str, dict[str, Any]]],
) -> tuple[str, dict[str, Any]] | None:
    best_code: str | None = None
    best_snapshot: dict[str, Any] | None = None
    for code, snapshot in list(candidate_snapshots or []):
        if not isinstance(snapshot, dict):
            continue
        if best_snapshot is None:
            best_code = str(code)
            best_snapshot = snapshot
            continue
        candidate_key = (
            float(snapshot.get("priority") or 0.0),
            float(snapshot.get("score_gap") or 0.0),
            -float(snapshot.get("current_return_pct") or 0.0),
        )
        best_key = (
            float(best_snapshot.get("priority") or 0.0),
            float(best_snapshot.get("score_gap") or 0.0),
            -float(best_snapshot.get("current_return_pct") or 0.0),
        )
        if candidate_key > best_key:
            best_code = str(code)
            best_snapshot = snapshot
    if best_code is None or best_snapshot is None:
        return None
    return best_code, best_snapshot
