from __future__ import annotations

import pytest

import neotrade3.decision_engine.contracts as m3_contracts
from neotrade3.decision_engine.contracts import (
    DecisionLifecycleEvent,
    DecisionLifecycleLog,
    EntryState,
    IdentifyState,
)


def test_copy_mapping_fail_closed_on_none() -> None:
    with pytest.raises(TypeError):
        m3_contracts._copy_mapping(None)


def test_copy_text_list_fail_closed_on_non_list() -> None:
    with pytest.raises(TypeError):
        m3_contracts._copy_text_list(None)


def test_copy_text_list_fail_closed_on_empty_string() -> None:
    with pytest.raises(ValueError):
        m3_contracts._copy_text_list(["", "a"])


def test_copy_payload_list_fail_closed_on_non_dict_item() -> None:
    with pytest.raises(TypeError):
        m3_contracts._copy_payload_list([{"a": 1}, "x"])


def test_to_payload_fail_closed_when_mapping_fields_are_invalid() -> None:
    obj = IdentifyState(
        stock_code="600000",
        trade_date="2026-07-07",
        status="ok",
        reason="x",
        evidence_ref=None,  # type: ignore[arg-type]
        m2_cycle_ref={},
        m1_constraints_ref={},
    )
    with pytest.raises(TypeError):
        obj.to_payload()


def test_to_payload_fail_closed_when_list_fields_are_invalid() -> None:
    obj = EntryState(
        stock_code="600000",
        trade_date="2026-07-07",
        status="ok",
        decision="buy",
        actionable=True,
        blocking_reasons=[""],  # type: ignore[list-item]
        evidence_ref={},
        m2_cycle_ref={},
        m1_constraints_ref={},
    )
    with pytest.raises(ValueError):
        obj.to_payload()


def test_decision_lifecycle_log_to_payload_emits_event_payloads() -> None:
    event = DecisionLifecycleEvent(
        stock_code="300001",
        trade_date="2026-06-18",
        event="market_exit_watch_started",
        source_layer="sell",
        stage="hold_confirmed",
        decision="hold",
        exit_scope="",
        details="",
        position_contract_snapshot={},
        evidence_ref={},
    )
    log = DecisionLifecycleLog(stock_code="300001", events=[event])
    payload = log.to_payload()
    assert payload["events"][0]["object_type"] == "decision_lifecycle_event"

