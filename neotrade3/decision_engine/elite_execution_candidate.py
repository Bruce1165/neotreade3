from __future__ import annotations

from typing import Any


def build_elite_execution_candidate_snapshot(
    *,
    gate_blocked: bool,
    gate_details: str,
    gate_min_score_required: float | None,
    role: str,
    wave_phase: str,
    buy_score: float,
    soft_flags: list[str],
    elite_min_score: float,
    elite_unknown_leader_min_score: float,
    wave1_value: str,
    wave3_value: str,
) -> dict[str, Any]:
    if bool(gate_blocked):
        return {
            "eligible": False,
            "blocked_reason": "elite_execution_candidate_rejected",
            "details": str(gate_details or ""),
            "min_score_required": gate_min_score_required,
        }

    normalized_role = str(role or "").strip()
    normalized_wave_phase = str(wave_phase or "").strip()
    normalized_buy_score = float(buy_score or 0.0)
    normalized_soft_flags = [
        str(flag or "").strip() for flag in list(soft_flags or []) if str(flag or "").strip()
    ]
    normalized_elite_min_score = float(elite_min_score)
    normalized_elite_unknown_leader_min_score = float(elite_unknown_leader_min_score)
    normalized_wave1_value = str(wave1_value or "").strip()
    normalized_wave3_value = str(wave3_value or "").strip()

    reasons: list[str] = []
    if normalized_role != "龙头":
        reasons.append("非龙头不进入 elite execution 资格")
    if normalized_soft_flags:
        reasons.append("存在 soft-retained 标记，不进入 elite execution 资格")

    min_score_required = normalized_elite_min_score
    if normalized_wave_phase in {normalized_wave1_value, normalized_wave3_value}:
        if normalized_buy_score < normalized_elite_min_score:
            reasons.append(f"1浪/3浪龙头正式保留至少需要 {normalized_elite_min_score:.1f} 分")
    else:
        min_score_required = normalized_elite_unknown_leader_min_score
        if normalized_buy_score < normalized_elite_unknown_leader_min_score:
            reasons.append(
                f"未知波段龙头正式保留至少需要 {normalized_elite_unknown_leader_min_score:.1f} 分"
            )

    return {
        "eligible": not bool(reasons),
        "blocked_reason": "elite_execution_candidate_rejected",
        "details": "；".join(reasons),
        "soft_flags": normalized_soft_flags,
        "min_score_required": float(min_score_required),
    }
