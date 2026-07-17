from __future__ import annotations

import pytest

from neotrade3.decision_engine.contracts import (
    DecisionLifecycleEvent,
    DecisionLifecycleLog,
)


def test_decision_lifecycle_event_roundtrip_allows_empty_exit_scope_and_details() -> None:
    obj = DecisionLifecycleEvent(
        stock_code="300001",
        trade_date="2026-06-18",
        run_id="run-001",
        source_run_id="source-001",
        event="market_exit_watch_started",
        source_layer="sell",
        stage="hold_confirmed",
        decision="hold",
        exit_scope="",
        details="",
        position_contract_snapshot={},
        evidence_ref={"scope": "market"},
    )
    assert DecisionLifecycleEvent.from_dict(obj.to_payload()) == obj


def test_decision_lifecycle_event_fail_closed_on_unknown_fields() -> None:
    payload = {
        "object_type": "decision_lifecycle_event",
        "object_version": 2,
        "stock_code": "300001",
        "trade_date": "2026-06-18",
        "run_id": "run-001",
        "source_run_id": "source-001",
        "event": "market_exit_watch_started",
        "source_layer": "sell",
        "stage": "hold_confirmed",
        "decision": "hold",
        "exit_scope": "",
        "details": "",
        "position_contract_snapshot": {},
        "evidence_ref": {},
        "extra": 1,
    }
    with pytest.raises(ValueError):
        DecisionLifecycleEvent.from_dict(payload)


def test_decision_lifecycle_log_roundtrip_parses_events_as_objects() -> None:
    event = DecisionLifecycleEvent(
        stock_code="300001",
        trade_date="2026-06-18",
        run_id="run-001",
        source_run_id="source-001",
        event="market_exit_watch_started",
        source_layer="sell",
        stage="hold_confirmed",
        decision="hold",
        exit_scope="",
        details="",
        position_contract_snapshot={},
        evidence_ref={},
    )
    log = DecisionLifecycleLog(
        stock_code="300001",
        run_id="run-001",
        source_run_id="source-001",
        events=[event],
    )

    reconstructed = DecisionLifecycleLog.from_dict(log.to_payload())
    assert reconstructed.stock_code == "300001"
    assert len(reconstructed.events) == 1
    assert reconstructed.events[0] == event


def test_decision_lifecycle_log_fail_closed_on_invalid_events() -> None:
    payload = {
        "object_type": "decision_lifecycle_log",
        "object_version": 2,
        "stock_code": "300001",
        "run_id": "run-001",
        "source_run_id": "source-001",
        "events": [{"object_type": "decision_lifecycle_event", "object_version": 1}],
    }
    with pytest.raises(ValueError):
        DecisionLifecycleLog.from_dict(payload)


def test_decision_lifecycle_event_rejects_v1_payload() -> None:
    payload = {
        "object_type": "decision_lifecycle_event",
        "object_version": 1,
        "stock_code": "300001",
        "trade_date": "2026-06-18",
        "run_id": "run-001",
        "source_run_id": "source-001",
        "event": "market_exit_watch_started",
        "source_layer": "sell",
        "stage": "hold_confirmed",
        "decision": "hold",
        "exit_scope": "",
        "details": "",
        "position_contract_snapshot": {},
        "evidence_ref": {},
    }
    with pytest.raises(ValueError):
        DecisionLifecycleEvent.from_dict(payload)
