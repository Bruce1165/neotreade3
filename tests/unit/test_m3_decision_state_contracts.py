from __future__ import annotations

import pytest

from neotrade3.decision_engine.contracts import (
    EntryState,
    ExitState,
    HoldState,
    IdentifyState,
    TrackingState,
)


def test_identify_state_roundtrip() -> None:
    obj = IdentifyState(
        stock_code="600000",
        trade_date="2026-07-07",
        status="ok",
        reason="test",
        evidence_ref={"kind": "test"},
        m2_cycle_ref={"kind": "m2"},
        m1_constraints_ref={"kind": "m1"},
    )
    assert IdentifyState.from_dict(obj.to_payload()) == obj


def test_tracking_state_roundtrip() -> None:
    obj = TrackingState(
        stock_code="600000",
        trade_date="2026-07-07",
        status="ok",
        maturity="M1",
        transition_reason="test",
        evidence_ref={"kind": "test"},
        m2_cycle_ref={"kind": "m2"},
        m1_constraints_ref={"kind": "m1"},
    )
    assert TrackingState.from_dict(obj.to_payload()) == obj


def test_entry_state_roundtrip() -> None:
    obj = EntryState(
        stock_code="600000",
        trade_date="2026-07-07",
        status="ok",
        decision="buy",
        actionable=True,
        blocking_reasons=["a"],
        evidence_ref={"kind": "test"},
        m2_cycle_ref={"kind": "m2"},
        m1_constraints_ref={"kind": "m1"},
    )
    assert EntryState.from_dict(obj.to_payload()) == obj


def test_hold_state_roundtrip() -> None:
    obj = HoldState(
        stock_code="600000",
        trade_date="2026-07-07",
        status="ok",
        hold_state="hold",
        warning_flags=["w1"],
        not_exit_reasons=["r1"],
        evidence_ref={"kind": "test"},
        m2_cycle_ref={"kind": "m2"},
        m1_constraints_ref={"kind": "m1"},
    )
    assert HoldState.from_dict(obj.to_payload()) == obj


def test_exit_state_roundtrip() -> None:
    obj = ExitState(
        stock_code="600000",
        trade_date="2026-07-07",
        status="ok",
        exit_ready=False,
        exit_scope="local",
        exit_reason_type="risk",
        exit_attribution_bucket="bucket",
        local_exit_semantics="sem",
        global_thesis_end_semantics="end",
        evidence_ref={"kind": "test"},
        m2_cycle_ref={"kind": "m2"},
        m1_constraints_ref={"kind": "m1"},
    )
    assert ExitState.from_dict(obj.to_payload()) == obj


@pytest.mark.parametrize(
    "cls,payload",
    [
        (
            IdentifyState,
            {
                "object_version": 1,
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "status": "ok",
                "reason": "x",
                "evidence_ref": {},
                "m2_cycle_ref": {},
                "m1_constraints_ref": {},
            },
        ),
        (
            TrackingState,
            {
                "object_type": "tracking_state",
                "stock_code": "600000",
                "trade_date": "2026-07-07",
                "status": "ok",
                "maturity": "M1",
                "transition_reason": "x",
                "evidence_ref": {},
                "m2_cycle_ref": {},
                "m1_constraints_ref": {},
            },
        ),
    ],
)
def test_state_from_dict_fail_closed_on_missing_header(
    cls, payload
) -> None:
    with pytest.raises(ValueError):
        cls.from_dict(payload)


def test_entry_state_fail_closed_on_invalid_list() -> None:
    payload = {
        "object_type": "entry_state",
        "object_version": 1,
        "stock_code": "600000",
        "trade_date": "2026-07-07",
        "status": "ok",
        "decision": "buy",
        "actionable": True,
        "blocking_reasons": ["", "a"],
        "evidence_ref": {},
        "m2_cycle_ref": {},
        "m1_constraints_ref": {},
    }
    with pytest.raises(ValueError):
        EntryState.from_dict(payload)


def test_exit_state_fail_closed_on_unknown_fields() -> None:
    payload = {
        "object_type": "exit_state",
        "object_version": 1,
        "stock_code": "600000",
        "trade_date": "2026-07-07",
        "status": "ok",
        "exit_ready": False,
        "exit_scope": "local",
        "exit_reason_type": "risk",
        "exit_attribution_bucket": "bucket",
        "local_exit_semantics": "sem",
        "global_thesis_end_semantics": "end",
        "evidence_ref": {},
        "m2_cycle_ref": {},
        "m1_constraints_ref": {},
        "extra": 1,
    }
    with pytest.raises(ValueError):
        ExitState.from_dict(payload)

