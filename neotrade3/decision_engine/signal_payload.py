from __future__ import annotations

from datetime import date
from typing import Any


def build_signal_structure_payload(
    *,
    deduped_signals: dict[str, dict[str, Any]],
    target_date: date,
    market_filter_note: str | None,
) -> dict[str, Any]:
    candidate_signals_sorted = sorted(
        deduped_signals.values(),
        key=lambda item: (float(item.get("buy_score") or 0.0), float(item.get("resonance") or 0.0)),
        reverse=True,
    )
    tracking_pool_candidate_order: list[str] = []
    tracking_pool_candidates: dict[str, dict[str, Any]] = {}
    for sig in candidate_signals_sorted:
        if not isinstance(sig, dict):
            continue
        code = str(sig.get("code") or "").strip()
        if not code:
            continue
        tracking_pool_candidate_order.append(code)
        tracking_pool_candidates[code] = dict(sig)

    candidate_signals = [tracking_pool_candidates[code] for code in tracking_pool_candidate_order]
    entry_signals = [dict(sig) for sig in candidate_signals if bool(sig.get("entry_ready"))]
    tracking_pool_candidate_fields = {
        "code": "股票代码",
        "name": "股票名称（如有）",
        "sector": "所属板块（如有）",
        "candidate_tier": "候选层级（entry_ready/soft_retained 等）",
        "entry_ready": "是否满足入场窗口（受 formal front 覆盖）",
        "buy_score": "入场评分（用于排序/择优）",
        "certainty_score": "确定性评分（0-100），口径为 100 交易日内>=50%区间最大涨幅概率*100",
        "certainty_horizon_days_max": "确定性口径窗口上限（固定 100）",
        "certainty_target_return_pct": "确定性口径目标涨幅（固定 50）",
        "certainty_prob": "确定性概率（0-1），来自校准桶",
        "certainty_samples": "确定性校准样本量（n）",
        "certainty_bucket_key": "确定性校准桶 key（用于审计/复算）",
        "role": "身份（龙头/中军/跟随）",
        "wave_phase": "小周期阶段（1浪/3浪/5浪/B浪/未知）",
        "wave_phase_confidence": "小周期阶段置信度（0-1）",
        "pattern_evidence": "形态证据摘要（如周线老鸭头/杯柄等）",
        "evidence_bundle": "证据束（用于审计与解释）",
        "reasons": "原因列表（与证据束同源）",
        "signal_source": "信号来源（hot_sector/cross_sector 等）",
        "soft_flags": "软标记（降权/保留原因）",
        "formal_front": "formal front 投影快照（如有）",
    }
    return {
        "buy_signals": list(entry_signals),
        "candidate_signals": candidate_signals,
        "entry_signals": entry_signals,
        "tracking_pool_candidates": tracking_pool_candidates,
        "tracking_pool_candidate_order": list(tracking_pool_candidate_order),
        "tracking_pool_candidate_fields": tracking_pool_candidate_fields,
        "signal_summary": {
            "candidate_count": len(candidate_signals),
            "entry_count": len(entry_signals),
            "soft_retained_count": sum(
                1 for sig in candidate_signals if str(sig.get("candidate_tier") or "") == "soft_retained"
            ),
        },
        "date": target_date.isoformat(),
        "capture_first_mode": True,
        "market_filter_note": market_filter_note,
    }
