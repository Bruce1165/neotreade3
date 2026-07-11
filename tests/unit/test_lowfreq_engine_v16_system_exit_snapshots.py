from __future__ import annotations

from neotrade3.decision_engine.system_exit_snapshots import (
    build_market_exit_snapshot,
    build_sector_exit_snapshot,
)


def test_build_market_exit_snapshot_allows_confirmation_without_large_drawdown() -> None:
    snapshot = build_market_exit_snapshot(
        top_snapshot={
            "market_key": "cyb",
            "market_label": "创业板",
            "break_ma20": True,
            "ma20_weak": True,
            "breadth_ratio": 0.25,
        },
        drawdown_snapshot={
            "market_label": "创业板",
            "drawdown_pct": -2.5,
        },
        fallback_market_label="市场",
        fallback_market_key="cyb",
        min_drawdown_pct=-4.0,
    )

    assert snapshot is not None
    assert snapshot["price_trend_weak"] is True
    assert snapshot["breadth_weak"] is True
    assert snapshot["drawdown_weak"] is False
    assert snapshot["drawdown_is_observation_only"] is True
    assert snapshot["condition_pass"] is True


def test_build_market_exit_snapshot_keeps_large_drawdown_as_observation_evidence() -> None:
    snapshot = build_market_exit_snapshot(
        top_snapshot={
            "market_key": "cyb",
            "market_label": "创业板",
            "break_ma20": True,
            "ma20_weak": True,
            "breadth_ratio": 0.22,
        },
        drawdown_snapshot={
            "market_label": "创业板",
            "drawdown_pct": -4.5,
        },
        fallback_market_label="市场",
        fallback_market_key="cyb",
        min_drawdown_pct=-4.0,
    )

    assert snapshot is not None
    assert snapshot["drawdown_weak"] is True
    assert snapshot["condition_pass"] is True
    assert snapshot["drawdown_is_observation_only"] is True


def test_build_market_exit_snapshot_drawdown_only_does_not_confirm_exit() -> None:
    snapshot = build_market_exit_snapshot(
        top_snapshot={
            "market_key": "cyb",
            "market_label": "创业板",
            "break_ma20": False,
            "ma20_weak": False,
            "breadth_ratio": 0.58,
        },
        drawdown_snapshot={
            "market_label": "创业板",
            "drawdown_pct": -6.5,
        },
        fallback_market_label="市场",
        fallback_market_key="cyb",
        min_drawdown_pct=-4.0,
    )

    assert snapshot is not None
    assert snapshot["price_trend_weak"] is False
    assert snapshot["breadth_weak"] is False
    assert snapshot["drawdown_weak"] is True
    assert snapshot["condition_pass"] is False
    assert snapshot["drawdown_is_observation_only"] is True


def test_build_market_exit_snapshot_returns_none_when_no_evidence_exists() -> None:
    assert (
        build_market_exit_snapshot(
            top_snapshot={
                "market_key": "cyb",
                "market_label": "创业板",
                "break_ma20": False,
                "ma20_weak": False,
                "breadth_ratio": 0.58,
            },
            drawdown_snapshot=None,
            fallback_market_label="市场",
            fallback_market_key="cyb",
            min_drawdown_pct=-4.0,
        )
        is None
    )


def test_build_sector_exit_snapshot_requires_trend_and_follower_weakness_to_confirm() -> None:
    snapshot = build_sector_exit_snapshot(
        sector="AI",
        cooldown_info={
            "cooldown_detected": True,
            "follower_weakness": 0.72,
            "leader_strength": 0.49,
            "leader_avg": 7.5,
            "trend_state": "diverging",
        },
    )

    assert snapshot is not None
    assert snapshot["trend_deteriorating"] is True
    assert snapshot["follower_weak"] is True
    assert snapshot["condition_pass"] is True
    assert snapshot["cooldown_is_observation_only"] is True
    assert snapshot["leader_rollover_is_observation_only"] is True


def test_build_sector_exit_snapshot_cooldown_and_leader_rollover_only_stay_observation() -> None:
    snapshot = build_sector_exit_snapshot(
        sector="AI",
        cooldown_info={
            "cooldown_detected": True,
            "follower_weakness": 0.42,
            "leader_strength": 0.41,
            "leader_avg": 6.8,
            "trend_state": "sideways",
        },
    )

    assert snapshot is not None
    assert snapshot["trend_deteriorating"] is False
    assert snapshot["follower_weak"] is False
    assert snapshot["leader_rollover"] is True
    assert snapshot["condition_pass"] is False
    assert snapshot["cooldown_is_observation_only"] is True
    assert snapshot["leader_rollover_is_observation_only"] is True


def test_build_sector_exit_snapshot_returns_none_when_sector_is_blank() -> None:
    assert build_sector_exit_snapshot(sector="", cooldown_info={"cooldown_detected": True}) is None


def test_build_sector_exit_snapshot_returns_none_when_cooldown_info_is_missing() -> None:
    assert build_sector_exit_snapshot(sector="AI", cooldown_info=None) is None
