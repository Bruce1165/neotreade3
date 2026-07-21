from __future__ import annotations

from typing import Any


def build_trade_discipline_metrics(
    *,
    asof_date: str,
    window_days: int,
    open_positions: int,
    planned_entries_today: int,
    planned_exits_today: int,
    executed_trades_window: int,
) -> dict[str, Any]:
    normalized_window_days = max(int(window_days or 0), 1)
    normalized_open_positions = max(int(open_positions or 0), 0)
    normalized_entries_today = max(int(planned_entries_today or 0), 0)
    normalized_exits_today = max(int(planned_exits_today or 0), 0)
    normalized_executed_window = max(int(executed_trades_window or 0), 0)

    return {
        "asof_date": str(asof_date or "").strip(),
        "window_days": normalized_window_days,
        "open_positions": normalized_open_positions,
        "planned_entries_today": normalized_entries_today,
        "planned_exits_today": normalized_exits_today,
        "executed_trades_window": normalized_executed_window,
        "entry_churn_ratio_window": round(float(normalized_executed_window) / float(normalized_window_days), 6),
        "metrics_status": "ready",
        "pending_reason": None,
    }


def build_discipline_guard_verdict(
    *,
    enabled: bool,
    asof_date: str,
    policy_id: str,
    metrics: dict[str, Any] | None,
    max_trades_window: int,
) -> dict[str, Any]:
    normalized_policy_id = str(policy_id or "").strip() or "trade_discipline_v0"
    snap = metrics if isinstance(metrics, dict) else {}
    metrics_status = str(snap.get("metrics_status") or "").strip() or "pending"

    if not bool(enabled):
        return {
            "status": "pass",
            "policy_id": normalized_policy_id,
            "block_reason_code": None,
            "block_reason": None,
            "evidence_keys": [],
            "asof_date": str(asof_date or "").strip(),
        }

    if metrics_status != "ready":
        return {
            "status": "block",
            "policy_id": normalized_policy_id,
            "block_reason_code": "metrics_pending",
            "block_reason": str(snap.get("pending_reason") or "discipline metrics pending"),
            "evidence_keys": ["metrics_status", "pending_reason"],
            "asof_date": str(asof_date or "").strip(),
        }

    normalized_max_trades_window = max(int(max_trades_window or 0), 0)
    if normalized_max_trades_window <= 0:
        return {
            "status": "pass",
            "policy_id": normalized_policy_id,
            "block_reason_code": None,
            "block_reason": None,
            "evidence_keys": [],
            "asof_date": str(asof_date or "").strip(),
        }

    executed_trades_window = int(snap.get("executed_trades_window") or 0)
    if executed_trades_window >= normalized_max_trades_window:
        return {
            "status": "block",
            "policy_id": normalized_policy_id,
            "block_reason_code": "max_trades_window_exceeded",
            "block_reason": (
                f"executed_trades_window={executed_trades_window} "
                f">= max_trades_window={normalized_max_trades_window}"
            ),
            "evidence_keys": ["executed_trades_window", "window_days", "max_trades_window"],
            "asof_date": str(asof_date or "").strip(),
        }

    return {
        "status": "pass",
        "policy_id": normalized_policy_id,
        "block_reason_code": None,
        "block_reason": None,
        "evidence_keys": [],
        "asof_date": str(asof_date or "").strip(),
    }


def build_discipline_audit_event(
    *,
    asof_date: str,
    policy_id: str,
    guard_verdict: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "event_type": "trade_discipline_guard",
        "asof_date": str(asof_date or "").strip(),
        "policy_id": str(policy_id or "").strip() or "trade_discipline_v0",
        "guard_verdict": dict(guard_verdict) if isinstance(guard_verdict, dict) else {},
        "metrics": dict(metrics) if isinstance(metrics, dict) else {},
    }

