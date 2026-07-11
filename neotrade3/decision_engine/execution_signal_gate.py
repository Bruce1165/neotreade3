from __future__ import annotations

from typing import Any


def build_execution_signal_gate_snapshot(
    *,
    enabled: bool,
    role: str,
    wave_phase: str,
    buy_score: float,
    follower_min_score: float,
    unknown_wave_min_score: float,
    wave1_value: str,
    wave3_value: str,
) -> dict[str, Any]:
    if not bool(enabled):
        return {"blocked": False}

    normalized_role = str(role or "").strip()
    normalized_wave_phase = str(wave_phase or "").strip()
    normalized_buy_score = float(buy_score or 0.0)
    normalized_follower_min_score = float(follower_min_score)
    normalized_unknown_wave_min_score = float(unknown_wave_min_score)

    soft_role_blocked = False
    soft_wave_blocked = False
    min_score_required = 0.0
    reasons: list[str] = []

    if normalized_role == "跟随" and normalized_buy_score < normalized_follower_min_score:
        soft_role_blocked = True
        min_score_required = max(min_score_required, normalized_follower_min_score)
        reasons.append(f"跟随股正式执行至少需要 {normalized_follower_min_score:.1f} 分")

    if (
        normalized_wave_phase not in {str(wave1_value or "").strip(), str(wave3_value or "").strip()}
        and normalized_buy_score < normalized_unknown_wave_min_score
    ):
        soft_wave_blocked = True
        min_score_required = max(min_score_required, normalized_unknown_wave_min_score)
        reasons.append(f"未知波段正式执行至少需要 {normalized_unknown_wave_min_score:.1f} 分")

    return {
        "blocked": bool(reasons),
        "blocked_reason": "execution_signal_gate_blocked",
        "soft_role_blocked": bool(soft_role_blocked),
        "soft_wave_blocked": bool(soft_wave_blocked),
        "min_score_required": float(min_score_required),
        "details": "；".join(reasons),
    }
