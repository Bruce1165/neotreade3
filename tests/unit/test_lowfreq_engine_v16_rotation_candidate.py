from __future__ import annotations

from neotrade3.decision_engine.rotation_candidate import (
    build_rotation_candidate_snapshot,
    select_rotation_candidate,
)


def _base_snapshot(**overrides: object) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "current_price": 12.3,
        "current_return_pct": 8.0,
        "peak_return_pct": 15.0,
        "market_evidence": 1,
        "sector_evidence": 2,
        "watch_active": False,
        "weakening": True,
    }
    snapshot.update(overrides)
    return snapshot


def test_build_rotation_candidate_snapshot_returns_none_when_rotation_disabled() -> None:
    snapshot = build_rotation_candidate_snapshot(
        rotation_enabled=False,
        incoming_score=92.0,
        held_score=70.0,
        min_score_margin=12.0,
        base_snapshot=_base_snapshot(),
        max_current_return_pct=25.0,
        min_evidence=2,
        profit_keep_ratio=0.6,
        trade_code="000001",
    )

    assert snapshot is None


def test_build_rotation_candidate_snapshot_returns_none_for_insufficient_score_gap() -> None:
    snapshot = build_rotation_candidate_snapshot(
        rotation_enabled=True,
        incoming_score=80.0,
        held_score=70.0,
        min_score_margin=12.0,
        base_snapshot=_base_snapshot(),
        max_current_return_pct=25.0,
        min_evidence=2,
        profit_keep_ratio=0.6,
        trade_code="000001",
    )

    assert snapshot is None


def test_build_rotation_candidate_snapshot_returns_none_above_current_return_ceiling() -> None:
    snapshot = build_rotation_candidate_snapshot(
        rotation_enabled=True,
        incoming_score=92.0,
        held_score=70.0,
        min_score_margin=12.0,
        base_snapshot=_base_snapshot(current_return_pct=25.1),
        max_current_return_pct=25.0,
        min_evidence=2,
        profit_keep_ratio=0.6,
        trade_code="000001",
    )

    assert snapshot is None


def test_build_rotation_candidate_snapshot_returns_none_without_weakening_or_evidence() -> None:
    snapshot = build_rotation_candidate_snapshot(
        rotation_enabled=True,
        incoming_score=92.0,
        held_score=70.0,
        min_score_margin=12.0,
        base_snapshot=_base_snapshot(
            market_evidence=1,
            sector_evidence=1,
            weakening=False,
        ),
        max_current_return_pct=25.0,
        min_evidence=2,
        profit_keep_ratio=0.6,
        trade_code="000001",
    )

    assert snapshot is None


def test_build_rotation_candidate_snapshot_returns_expected_contract_for_valid_candidate() -> None:
    snapshot = build_rotation_candidate_snapshot(
        rotation_enabled=True,
        incoming_score=92.0,
        held_score=70.0,
        min_score_margin=12.0,
        base_snapshot=_base_snapshot(),
        max_current_return_pct=25.0,
        min_evidence=2,
        profit_keep_ratio=0.6,
        trade_code="000001",
    )

    assert snapshot == {
        "code": "000001",
        "current_price": 12.3,
        "current_return_pct": 8.0,
        "peak_return_pct": 15.0,
        "profit_keep_ratio": 0.6,
        "market_evidence": 1,
        "sector_evidence": 2,
        "watch_active": False,
        "weakening": True,
        "score_gap": 22.0,
        "priority": 44.2,
        "details": (
            "弱化持仓换仓候选 | score_gap=22.0 | "
            "market_evidence=1 | sector_evidence=2 | "
            "current_return=8.0% | keep_ratio=0.60"
        ),
    }


def test_build_rotation_candidate_snapshot_applies_watch_active_priority_bonus() -> None:
    base_snapshot = _base_snapshot(weakening=False, market_evidence=2, sector_evidence=1)
    without_watch = build_rotation_candidate_snapshot(
        rotation_enabled=True,
        incoming_score=92.0,
        held_score=70.0,
        min_score_margin=12.0,
        base_snapshot=base_snapshot,
        max_current_return_pct=25.0,
        min_evidence=2,
        profit_keep_ratio=0.6,
        trade_code="000001",
    )
    with_watch = build_rotation_candidate_snapshot(
        rotation_enabled=True,
        incoming_score=92.0,
        held_score=70.0,
        min_score_margin=12.0,
        base_snapshot=_base_snapshot(
            watch_active=True,
            weakening=False,
            market_evidence=2,
            sector_evidence=1,
        ),
        max_current_return_pct=25.0,
        min_evidence=2,
        profit_keep_ratio=0.6,
        trade_code="000001",
    )

    assert without_watch is not None
    assert with_watch is not None
    assert with_watch["priority"] == without_watch["priority"] + 5.0


def test_select_rotation_candidate_returns_none_for_empty_input() -> None:
    assert select_rotation_candidate(candidate_snapshots=[]) is None


def test_select_rotation_candidate_prefers_higher_priority() -> None:
    selected = select_rotation_candidate(
        candidate_snapshots=[
            (
                "000001",
                {
                    "priority": 30.0,
                    "score_gap": 20.0,
                    "current_return_pct": 5.0,
                },
            ),
            (
                "000002",
                {
                    "priority": 31.0,
                    "score_gap": 15.0,
                    "current_return_pct": 10.0,
                },
            ),
        ]
    )

    assert selected is not None
    assert selected[0] == "000002"


def test_select_rotation_candidate_uses_score_gap_as_second_tie_break() -> None:
    selected = select_rotation_candidate(
        candidate_snapshots=[
            (
                "000001",
                {
                    "priority": 30.0,
                    "score_gap": 20.0,
                    "current_return_pct": 5.0,
                },
            ),
            (
                "000002",
                {
                    "priority": 30.0,
                    "score_gap": 21.0,
                    "current_return_pct": 10.0,
                },
            ),
        ]
    )

    assert selected is not None
    assert selected[0] == "000002"


def test_select_rotation_candidate_uses_lower_current_return_as_third_tie_break() -> None:
    selected = select_rotation_candidate(
        candidate_snapshots=[
            (
                "000001",
                {
                    "priority": 30.0,
                    "score_gap": 20.0,
                    "current_return_pct": 6.0,
                },
            ),
            (
                "000002",
                {
                    "priority": 30.0,
                    "score_gap": 20.0,
                    "current_return_pct": 5.0,
                },
            ),
        ]
    )

    assert selected is not None
    assert selected[0] == "000002"
