from __future__ import annotations

from neotrade3.decision_engine.system_exit_state_machine import evaluate_system_exit_transition


def _snapshot(details: str = "创业板见顶确认候选：趋势转弱=是 | 广度转弱=是 | 代理回撤-10.5%") -> dict:
    return {
        "condition_pass": True,
        "details": details,
    }


def test_system_exit_state_machine_returns_noop_for_non_passing_snapshot() -> None:
    transition = evaluate_system_exit_transition(
        scope="market",
        window=5,
        confirm_hits=3,
        current_key="2026-06-18",
        start_value="",
        state_value="",
        hit_count=0,
        last_hit_date="",
        snapshot=None,
        elapsed_watch_days=None,
        grace_eligible=False,
        grace_used=False,
    )

    assert transition["snapshot_pass"] is False
    assert transition["start_watch"] is False
    assert transition["confirm_signal"] is False


def test_system_exit_state_machine_expires_existing_watch_before_processing() -> None:
    transition = evaluate_system_exit_transition(
        scope="market",
        window=5,
        confirm_hits=3,
        current_key="2026-06-24",
        start_value="2026-06-18",
        state_value="review",
        hit_count=2,
        last_hit_date="2026-06-19",
        snapshot=None,
        elapsed_watch_days=6,
        grace_eligible=False,
        grace_used=False,
    )

    assert transition["expire_existing_watch"] is True
    assert transition["next_hits"] == 0
    assert transition["next_state"] == ""


def test_system_exit_state_machine_starts_watch_on_first_valid_hit() -> None:
    transition = evaluate_system_exit_transition(
        scope="market",
        window=5,
        confirm_hits=3,
        current_key="2026-06-18",
        start_value="",
        state_value="",
        hit_count=0,
        last_hit_date="",
        snapshot=_snapshot(),
        elapsed_watch_days=None,
        grace_eligible=False,
        grace_used=False,
    )

    assert transition["start_watch"] is True
    assert transition["next_state"] == "observe"
    assert transition["next_hits"] == 1
    assert transition["confirm_signal"] is False


def test_system_exit_state_machine_enters_review_on_second_distinct_day_hit() -> None:
    transition = evaluate_system_exit_transition(
        scope="market",
        window=5,
        confirm_hits=3,
        current_key="2026-06-19",
        start_value="2026-06-18",
        state_value="observe",
        hit_count=1,
        last_hit_date="2026-06-18",
        snapshot=_snapshot(),
        elapsed_watch_days=2,
        grace_eligible=False,
        grace_used=False,
    )

    assert transition["increment_hit"] is True
    assert transition["enter_review"] is True
    assert transition["next_state"] == "review"
    assert transition["next_hits"] == 2


def test_system_exit_state_machine_does_not_increment_hits_twice_on_same_day() -> None:
    transition = evaluate_system_exit_transition(
        scope="market",
        window=5,
        confirm_hits=3,
        current_key="2026-06-19",
        start_value="2026-06-18",
        state_value="observe",
        hit_count=1,
        last_hit_date="2026-06-19",
        snapshot=_snapshot(),
        elapsed_watch_days=2,
        grace_eligible=False,
        grace_used=False,
    )

    assert transition["increment_hit"] is False
    assert transition["next_hits"] == 1
    assert transition["enter_review"] is False


def test_system_exit_state_machine_confirms_sell_when_hits_reach_threshold() -> None:
    transition = evaluate_system_exit_transition(
        scope="market",
        window=5,
        confirm_hits=3,
        current_key="2026-06-20",
        start_value="2026-06-18",
        state_value="review",
        hit_count=2,
        last_hit_date="2026-06-19",
        snapshot=_snapshot(),
        elapsed_watch_days=3,
        grace_eligible=False,
        grace_used=False,
    )

    assert transition["confirm_signal"] is True
    assert transition["use_grace"] is False
    assert transition["confirmed_details"] == "创业板见顶确认：趋势转弱=是 | 广度转弱=是 | 代理回撤-10.5%"
    assert transition["exit_scope"] == "portfolio"


def test_system_exit_state_machine_returns_grace_downgrade_when_eligible() -> None:
    transition = evaluate_system_exit_transition(
        scope="sector",
        window=4,
        confirm_hits=3,
        current_key="2026-06-20",
        start_value="2026-06-18",
        state_value="review",
        hit_count=2,
        last_hit_date="2026-06-19",
        snapshot={"condition_pass": True, "details": "板块见顶确认候选：AI | 趋势=diverging | 跟随股弱势70% | 龙头强度48%"},
        elapsed_watch_days=3,
        grace_eligible=True,
        grace_used=False,
    )

    assert transition["confirm_signal"] is True
    assert transition["use_grace"] is True
    assert transition["exit_scope"] == "sector_only"


def test_system_exit_state_machine_marks_followup_confirmation_after_prior_grace() -> None:
    transition = evaluate_system_exit_transition(
        scope="market",
        window=5,
        confirm_hits=3,
        current_key="2026-06-23",
        start_value="2026-06-21",
        state_value="review",
        hit_count=2,
        last_hit_date="2026-06-22",
        snapshot=_snapshot(),
        elapsed_watch_days=3,
        grace_eligible=False,
        grace_used=True,
    )

    assert transition["confirm_signal"] is True
    assert transition["emit_grace_then_confirmed_event"] is True
