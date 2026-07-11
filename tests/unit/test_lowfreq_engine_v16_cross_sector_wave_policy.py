from __future__ import annotations

from neotrade3.decision_engine.cross_sector_wave_policy import (
    build_cross_sector_allowed_waves,
    is_cross_sector_wave_mismatch,
)


def test_build_cross_sector_allowed_waves_keeps_wave3_baseline() -> None:
    assert build_cross_sector_allowed_waves(allow_wave1=False) == {"3浪"}


def test_build_cross_sector_allowed_waves_optionally_adds_wave1() -> None:
    assert build_cross_sector_allowed_waves(allow_wave1=True) == {"3浪", "1浪"}


def test_is_cross_sector_wave_mismatch_is_disabled_when_wave3_only_is_false() -> None:
    assert is_cross_sector_wave_mismatch("未知", wave3_only=False, allow_wave1=False) is False


def test_is_cross_sector_wave_mismatch_rejects_unsupported_wave_under_wave3_only() -> None:
    assert is_cross_sector_wave_mismatch("未知", wave3_only=True, allow_wave1=True) is True
