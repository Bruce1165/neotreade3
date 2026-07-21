from __future__ import annotations

from typing import Any, Optional


def build_step8_report_id(*, source_run_id: str, asof_date: str) -> str:
    normalized_run = str(source_run_id or "").strip()
    normalized_date = str(asof_date or "").strip().replace("-", "")
    if not normalized_run:
        raise ValueError("source_run_id must be non-empty")
    if not normalized_date:
        raise ValueError("asof_date must be non-empty")
    return f"{normalized_run}-{normalized_date}-step8"


def _count_events(*, buy_signal_audit: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in buy_signal_audit:
        if not isinstance(row, dict):
            continue
        event = str(row.get("event") or "").strip()
        if not event:
            continue
        counts[event] = counts.get(event, 0) + 1
    return counts


def _count_discipline_block_days(
    *,
    trade_discipline_audit: list[dict[str, Any]],
) -> int:
    out = 0
    for row in trade_discipline_audit:
        if not isinstance(row, dict):
            continue
        verdict = row.get("guard_verdict")
        if not isinstance(verdict, dict):
            continue
        if str(verdict.get("status") or "").strip() == "block":
            out += 1
    return int(out)


def build_tracking_pool_quality_report_v0(
    *,
    asof_date: str,
    source_run_id: str,
    backtest_result: dict[str, Any] | None,
    report_id: Optional[str] = None,
) -> dict[str, Any]:
    normalized_asof_date = str(asof_date or "").strip()
    normalized_source_run_id = str(source_run_id or "").strip()
    normalized_report_id = str(report_id or "").strip() or build_step8_report_id(
        source_run_id=normalized_source_run_id,
        asof_date=normalized_asof_date,
    )

    result = backtest_result if isinstance(backtest_result, dict) else {}
    buy_signal_audit = result.get("buy_signal_audit")
    trade_discipline_audit = result.get("trade_discipline_audit")
    if not isinstance(buy_signal_audit, list):
        buy_signal_audit = None
    if not isinstance(trade_discipline_audit, list):
        trade_discipline_audit = None

    inputs_ready = bool(normalized_asof_date and normalized_source_run_id)
    outputs_ready = bool(inputs_ready and buy_signal_audit is not None and trade_discipline_audit is not None)
    pending_reason = ""
    if not normalized_asof_date:
        pending_reason = "missing_asof_date"
    elif not normalized_source_run_id:
        pending_reason = "missing_source_run_id"
    elif buy_signal_audit is None:
        pending_reason = "missing_buy_signal_audit"
    elif trade_discipline_audit is None:
        pending_reason = "missing_trade_discipline_audit"

    summary_metrics: dict[str, int] = {}
    discipline_block_days = 0
    discipline_guard_blocked = 0
    if outputs_ready and isinstance(buy_signal_audit, list) and isinstance(trade_discipline_audit, list):
        event_counts = _count_events(buy_signal_audit=buy_signal_audit)
        summary_metrics = {
            "tracking_started_n": int(event_counts.get("tracking_started", 0)),
            "tracking_promoted_to_entry_n": int(event_counts.get("tracking_promoted_to_entry", 0)),
            "tracking_dropped_n": int(event_counts.get("tracking_dropped", 0)),
            "buy_executed_n": int(event_counts.get("buy_executed", 0)),
            "reservation_created_n": int(event_counts.get("reservation_created", 0)),
            "reservation_expired_n": int(event_counts.get("reservation_expired", 0)),
            "execution_signal_gate_blocked_n": int(event_counts.get("execution_signal_gate_blocked", 0)),
            "chase_entry_blocked_n": int(event_counts.get("chase_entry_blocked", 0)),
            "trade_discipline_guard_blocked_n": int(event_counts.get("trade_discipline_guard_blocked", 0)),
        }
        discipline_block_days = _count_discipline_block_days(
            trade_discipline_audit=trade_discipline_audit,
        )
        summary_metrics["discipline_block_days_n"] = int(discipline_block_days)
        discipline_guard_blocked = int(summary_metrics.get("trade_discipline_guard_blocked_n") or 0)

    quality_fail_reason_codes: list[str] = []
    if not outputs_ready:
        quality_fail_reason_codes.append("outputs_pending")
    if int(discipline_block_days) > 0:
        quality_fail_reason_codes.append("discipline_block_days")
    if int(discipline_guard_blocked) > 0:
        quality_fail_reason_codes.append("discipline_guard_blocked")
    quality_verdict = "fail" if quality_fail_reason_codes else "pass"

    return {
        "report_id": normalized_report_id,
        "asof_date": normalized_asof_date,
        "source_run_id": normalized_source_run_id or None,
        "quality_verdict": quality_verdict,
        "quality_fail_reason_codes": list(quality_fail_reason_codes),
        "summary_metrics": dict(summary_metrics),
        "evidence_paths": [],
        "inputs_ready": "ready" if inputs_ready else "pending",
        "outputs_ready": "ready" if outputs_ready else "pending",
        "pending_reason": pending_reason or None,
    }


def build_evaluation_trigger_inputs_v0(
    *,
    asof_date: str,
    source_run_id: str,
    inputs_ready: str,
    pending_reason: str | None,
    evidence_paths: list[str],
    trigger_type: str = "backtest_result_dict",
) -> dict[str, Any]:
    normalized_asof_date = str(asof_date or "").strip()
    normalized_source_run_id = str(source_run_id or "").strip()
    normalized_inputs_ready = str(inputs_ready or "").strip() or "pending"
    normalized_pending_reason = str(pending_reason or "").strip() or None
    normalized_evidence_paths = [str(p).strip() for p in list(evidence_paths or []) if str(p).strip()]
    return {
        "trigger_id": f"{normalized_source_run_id}:{normalized_asof_date}:step8_eval",
        "trigger_type": str(trigger_type or "").strip() or "backtest_result_dict",
        "asof_date": normalized_asof_date,
        "source_run_id": normalized_source_run_id or None,
        "inputs_ready": normalized_inputs_ready,
        "pending_reason": normalized_pending_reason,
        "evidence_paths": normalized_evidence_paths,
    }


def build_evaluation_outputs_v0(
    *,
    report_id: str,
    asof_date: str,
    source_run_id: str,
    outputs_ready: str,
    pending_reason: str | None,
    report_paths: list[str],
) -> dict[str, Any]:
    normalized_outputs_ready = str(outputs_ready or "").strip() or "pending"
    normalized_report_paths = (
        [str(p).strip() for p in list(report_paths or []) if str(p).strip()]
        if normalized_outputs_ready == "ready"
        else []
    )
    normalized_pending_reason = str(pending_reason or "").strip() or None
    return {
        "report_id": str(report_id or "").strip(),
        "asof_date": str(asof_date or "").strip(),
        "source_run_id": str(source_run_id or "").strip() or None,
        "outputs_ready": normalized_outputs_ready,
        "pending_reason": normalized_pending_reason,
        "report_paths": normalized_report_paths,
    }
