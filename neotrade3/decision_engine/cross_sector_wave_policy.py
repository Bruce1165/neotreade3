from __future__ import annotations

from typing import Any


def build_cross_sector_allowed_waves(*, allow_wave1: bool) -> set[str]:
    allowed_waves = {"3浪"}
    if bool(allow_wave1):
        allowed_waves.add("1浪")
    return allowed_waves


def is_cross_sector_wave_mismatch(
    wave_phase: Any,
    *,
    wave3_only: bool,
    allow_wave1: bool,
) -> bool:
    if not bool(wave3_only):
        return False
    allowed_waves = build_cross_sector_allowed_waves(allow_wave1=bool(allow_wave1))
    return str(wave_phase) not in allowed_waves
