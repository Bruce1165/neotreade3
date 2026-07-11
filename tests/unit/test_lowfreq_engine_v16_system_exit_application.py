from __future__ import annotations

from neotrade3.decision_engine.system_exit_application import plan_system_exit_application


def _transition(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "expire_existing_watch": False,
        "snapshot_pass": True,
        "start_watch": False,
        "increment_hit": False,
        "enter_review": False,
        "confirm_signal": False,
        "use_grace": False,
        "emit_grace_then_confirmed_event": False,
        "next_hits": 0,
        "snapshot_details": "创业板见顶确认候选：趋势转弱=是 | 广度转弱=是",
        "confirmed_details": "创业板见顶确认：趋势转弱=是 | 广度转弱=是",
        "exit_scope": "portfolio",
    }
    payload.update(overrides)
    return payload


def test_plan_system_exit_application_returns_expire_only_for_non_passing_snapshot() -> None:
    plan = plan_system_exit_application(
        scope="market",
        current_key="2026-06-24",
        expire_date="",
        transition=_transition(expire_existing_watch=True, snapshot_pass=False),
        signal_reason="market_top_confirmed",
        signal_confidence=0.95,
    )

    assert plan["expire_existing_watch"] is True
    assert plan["snapshot_pass"] is False
    assert plan["start_watch"] is False
    assert plan["sell_signal"] is None


def test_plan_system_exit_application_returns_start_watch_values() -> None:
    plan = plan_system_exit_application(
        scope="market",
        current_key="2026-06-18",
        expire_date="2026-06-24",
        transition=_transition(start_watch=True),
        signal_reason="market_top_confirmed",
        signal_confidence=0.95,
    )

    assert plan["start_watch"] is True
    assert plan["start_values"] == {
        "state": "observe",
        "start": "2026-06-18",
        "expire": "2026-06-24",
        "hits": 1,
        "last_reason": "创业板见顶确认候选：趋势转弱=是 | 广度转弱=是",
        "last_hit": "2026-06-18",
    }


def test_plan_system_exit_application_returns_review_update_plan() -> None:
    plan = plan_system_exit_application(
        scope="market",
        current_key="2026-06-19",
        expire_date="",
        transition=_transition(increment_hit=True, enter_review=True, next_hits=2),
        signal_reason="market_top_confirmed",
        signal_confidence=0.95,
    )

    assert plan["increment_hit"] is True
    assert plan["update_values"] == {
        "last_reason": "创业板见顶确认候选：趋势转弱=是 | 广度转弱=是",
        "hits": 2,
        "last_hit": "2026-06-19",
    }
    assert plan["enter_review"] is True
    assert plan["review_state"] == "review"


def test_plan_system_exit_application_returns_grace_reset_all_plan() -> None:
    plan = plan_system_exit_application(
        scope="sector",
        current_key="2026-06-20",
        expire_date="",
        transition=_transition(confirm_signal=True, use_grace=True),
        signal_reason="sector_top_confirmed",
        signal_confidence=0.93,
    )

    assert plan["use_grace"] is True
    assert plan["reset_all_scopes"] is True
    assert plan["grace_values"] == {
        "used": True,
        "date": "2026-06-20",
        "scope": "sector",
        "reason": "创业板见顶确认候选：趋势转弱=是 | 广度转弱=是",
    }
    assert plan["sell_signal"] is None


def test_plan_system_exit_application_returns_followup_confirm_plan_after_grace() -> None:
    plan = plan_system_exit_application(
        scope="market",
        current_key="2026-06-23",
        expire_date="",
        transition=_transition(confirm_signal=True, emit_grace_then_confirmed_event=True),
        signal_reason="market_top_confirmed",
        signal_confidence=0.95,
    )

    assert plan["emit_grace_then_confirmed_event"] is True
    assert plan["emit_confirm_event"] is True
    assert plan["reset_scope_on_confirm"] is True
    assert plan["sell_signal"] == {
        "reason": "market_top_confirmed",
        "confidence": 0.95,
        "details": "创业板见顶确认：趋势转弱=是 | 广度转弱=是",
        "source_layer": "exit",
        "exit_scope": "portfolio",
    }


def test_plan_system_exit_application_returns_plain_confirm_plan() -> None:
    plan = plan_system_exit_application(
        scope="sector",
        current_key="2026-06-20",
        expire_date="",
        transition=_transition(
            confirm_signal=True,
            confirmed_details="板块见顶确认：AI | 趋势=diverging",
            exit_scope="sector_only",
        ),
        signal_reason="sector_top_confirmed",
        signal_confidence=0.92,
    )

    assert plan["emit_confirm_event"] is True
    assert plan["reset_scope_on_confirm"] is True
    assert plan["emit_grace_then_confirmed_event"] is False
    assert plan["sell_signal"] == {
        "reason": "sector_top_confirmed",
        "confidence": 0.92,
        "details": "板块见顶确认：AI | 趋势=diverging",
        "source_layer": "exit",
        "exit_scope": "sector_only",
    }
