"""Formalize raw sell-side audit rows into M3 decision-lifecycle logs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .assembler import build_decision_lifecycle_event, build_decision_lifecycle_log

_HOLD_SIDE_EVENTS = {
    "market_exit_watch_started",
    "market_exit_review_started",
    "market_exit_watch_expired",
    "sector_exit_watch_started",
    "sector_exit_review_started",
    "sector_exit_watch_expired",
    "system_exit_downgraded",
}

_EXIT_SIDE_EVENTS = {
    "market_exit_confirmed",
    "sector_exit_confirmed",
    "trend_exhausted",
    "system_exit_downgraded_then_confirmed",
    "system_exit_downgraded_then_stop_loss",
    "system_exit_downgraded_then_end_flat",
}

_CORE_FIELDS = {
    "code",
    "date",
    "event",
    "source_layer",
    "details",
    "position_contract_snapshot",
    "stage",
    "decision",
    "exit_scope",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _copy_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _snapshot_from_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    return _copy_mapping(entry.get("position_contract_snapshot"))


def _resolve_source_layer(
    entry: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> str:
    return (
        _text(entry.get("source_layer"))
        or _text(snapshot.get("source_layer"))
        or "sell"
    )


def _resolve_stage(
    event_type: str,
    entry: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> str:
    explicit_stage = _text(entry.get("stage")) or _text(snapshot.get("current_stage"))
    if explicit_stage:
        return explicit_stage
    if event_type in _EXIT_SIDE_EVENTS:
        return "exit_ready"
    return "hold_confirmed"


def _resolve_decision(
    event_type: str,
    entry: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> str:
    explicit_decision = _text(entry.get("decision")) or _text(snapshot.get("decision"))
    if explicit_decision:
        return explicit_decision
    if event_type in _EXIT_SIDE_EVENTS:
        return "exit"
    return "hold"


def _resolve_exit_scope(
    event_type: str,
    entry: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> str:
    explicit_scope = (
        _text(entry.get("exit_scope"))
        or _text(snapshot.get("exit_scope"))
    )
    if explicit_scope:
        return explicit_scope
    if event_type == "trend_exhausted":
        return "position_only"
    if event_type in {"market_exit_confirmed", "system_exit_downgraded_then_confirmed"}:
        return "portfolio"
    if event_type == "sector_exit_confirmed":
        return "sector"
    if event_type in {
        "system_exit_downgraded_then_stop_loss",
        "system_exit_downgraded_then_end_flat",
    }:
        return "position_only"
    return ""


def _build_evidence_ref(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in entry.items()
        if str(key) not in _CORE_FIELDS
    }


def build_decision_lifecycle_event_from_sell_audit_entry(
    entry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Formalize one raw sell-side audit row into a lifecycle-event payload."""

    raw_entry = entry if isinstance(entry, Mapping) else {}
    snapshot = _snapshot_from_entry(raw_entry)
    event_type = _text(raw_entry.get("event"))
    return build_decision_lifecycle_event(
        stock_code=_text(raw_entry.get("code")),
        trade_date=_text(raw_entry.get("date")),
        event=event_type,
        source_layer=_resolve_source_layer(raw_entry, snapshot),
        stage=_resolve_stage(event_type, raw_entry, snapshot),
        decision=_resolve_decision(event_type, raw_entry, snapshot),
        exit_scope=_resolve_exit_scope(event_type, raw_entry, snapshot),
        details=_text(raw_entry.get("details")),
        position_contract_snapshot=snapshot,
        evidence_ref=_build_evidence_ref(raw_entry),
    ).to_payload()


def build_decision_lifecycle_logs(
    sell_signal_audit: list[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Group current raw sell-side audit rows into per-stock lifecycle logs."""

    grouped: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}
    code_order: list[str] = []
    for index, raw_entry in enumerate(sell_signal_audit or []):
        if not isinstance(raw_entry, Mapping):
            continue
        stock_code = _text(raw_entry.get("code"))
        event_type = _text(raw_entry.get("event"))
        trade_date = _text(raw_entry.get("date"))
        if not stock_code or not event_type or not trade_date:
            continue
        if stock_code not in grouped:
            grouped[stock_code] = []
            code_order.append(stock_code)
        grouped[stock_code].append((index, raw_entry))

    logs: list[dict[str, Any]] = []
    for stock_code in code_order:
        ordered_rows = sorted(
            grouped[stock_code],
            key=lambda item: (_text(item[1].get("date")), item[0]),
        )
        events = [
            build_decision_lifecycle_event_from_sell_audit_entry(raw_entry)
            for _, raw_entry in ordered_rows
        ]
        logs.append(
            build_decision_lifecycle_log(
                stock_code=stock_code,
                events=events,
            ).to_payload()
        )
    return logs
