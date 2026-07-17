from __future__ import annotations

from neotrade3.decision_engine import (
    DECISION_LIFECYCLE_EVENT_OBJECT_TYPE,
    DECISION_LIFECYCLE_LOG_OBJECT_TYPE,
    build_decision_lifecycle_event_from_sell_audit_entry,
    build_decision_lifecycle_logs,
)


def test_build_decision_lifecycle_event_prefers_snapshot_truth() -> None:
    payload = build_decision_lifecycle_event_from_sell_audit_entry(
        {
            "code": "300001",
            "date": "2026-06-18",
            "event": "market_exit_watch_started",
            "source_layer": "sell",
            "details": "进入市场退出观察态",
            "scope": "market",
            "state": "observe",
            "watch_day": 1,
            "position_contract_snapshot": {
                "source_layer": "hold",
                "current_stage": "hold_confirmed",
                "decision": "hold",
                "exit_scope": "",
                "hold_state": "observe_watch",
            },
        },
        run_id="run-001",
        source_run_id="source-001",
    )

    assert payload["object_type"] == DECISION_LIFECYCLE_EVENT_OBJECT_TYPE
    assert payload["stock_code"] == "300001"
    assert payload["trade_date"] == "2026-06-18"
    assert payload["event"] == "market_exit_watch_started"
    assert payload["source_layer"] == "sell"
    assert payload["stage"] == "hold_confirmed"
    assert payload["decision"] == "hold"
    assert payload["exit_scope"] == ""
    assert payload["position_contract_snapshot"]["hold_state"] == "observe_watch"
    assert payload["evidence_ref"]["scope"] == "market"
    assert payload["evidence_ref"]["state"] == "observe"
    assert payload["evidence_ref"]["watch_day"] == 1


def test_build_decision_lifecycle_event_uses_conservative_confirm_fallbacks() -> None:
    payload = build_decision_lifecycle_event_from_sell_audit_entry(
        {
            "code": "300001",
            "date": "2026-06-20",
            "event": "market_exit_confirmed",
            "details": "市场退出确认",
            "scope": "market",
        },
        run_id="run-001",
        source_run_id="source-001",
    )

    assert payload["object_type"] == DECISION_LIFECYCLE_EVENT_OBJECT_TYPE
    assert payload["stage"] == "exit_ready"
    assert payload["decision"] == "exit"
    assert payload["exit_scope"] == "portfolio"
    assert payload["position_contract_snapshot"] == {}


def test_build_decision_lifecycle_event_preserves_grace_evidence_fields() -> None:
    payload = build_decision_lifecycle_event_from_sell_audit_entry(
        {
            "code": "300001",
            "date": "2026-06-20",
            "event": "system_exit_downgraded",
            "details": "首次系统退出确认被 grace 降级",
            "scope": "market",
            "state": "confirmed",
            "grace_scope": "market",
            "grace_date": "2026-06-20",
            "grace_reason": "leader_grace",
            "position_contract_snapshot": {
                "source_layer": "hold",
                "current_stage": "hold_confirmed",
                "decision": "hold",
                "exit_scope": "",
                "hold_state": "review_watch",
            },
        },
        run_id="run-001",
        source_run_id="source-001",
    )

    assert payload["event"] == "system_exit_downgraded"
    assert payload["stage"] == "hold_confirmed"
    assert payload["decision"] == "hold"
    assert payload["evidence_ref"]["grace_scope"] == "market"
    assert payload["evidence_ref"]["grace_date"] == "2026-06-20"
    assert payload["evidence_ref"]["grace_reason"] == "leader_grace"


def test_build_decision_lifecycle_logs_groups_rows_by_stock_code() -> None:
    logs = build_decision_lifecycle_logs(
        [
            {
                "code": "300001",
                "date": "2026-06-18",
                "event": "market_exit_watch_started",
                "details": "A 观察",
            },
            {
                "code": "600000",
                "date": "2026-06-18",
                "event": "trend_exhausted",
                "details": "B 趋势衰竭",
            },
            {
                "code": "300001",
                "date": "2026-06-19",
                "event": "market_exit_review_started",
                "details": "A 复核",
            },
            {
                "code": "300001",
                "date": "2026-06-19",
                "event": "market_exit_confirmed",
                "details": "A 确认",
            },
        ],
        run_id="run-001",
        source_run_id="source-001",
    )

    assert len(logs) == 2
    assert logs[0]["object_type"] == DECISION_LIFECYCLE_LOG_OBJECT_TYPE
    assert logs[0]["stock_code"] == "300001"
    assert [event["event"] for event in logs[0]["events"]] == [
        "market_exit_watch_started",
        "market_exit_review_started",
        "market_exit_confirmed",
    ]
    assert logs[1]["stock_code"] == "600000"
    assert [event["event"] for event in logs[1]["events"]] == ["trend_exhausted"]
