"""Snapshot helpers for lowfreq attribution report consumers."""

from __future__ import annotations

from typing import Any

from neotrade3.decision_engine import project_lowfreq_formal_front


def build_attribution_signal_snapshot(raw: Any) -> dict[str, Any]:
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

    def _tracking_pool_candidate(item: dict[str, Any]) -> dict[str, Any]:
        out = {
            "code": str(item.get("code") or "").strip(),
            "name": str(item.get("name") or "").strip(),
            "sector": str(item.get("sector") or "").strip(),
            "candidate_tier": str(item.get("candidate_tier") or "").strip(),
            "entry_ready": bool(item.get("entry_ready")),
            "buy_score": float(item.get("buy_score") or 0.0),
            "certainty_score": (
                float(item.get("certainty_score"))
                if isinstance(item.get("certainty_score"), (int, float))
                else None
            ),
            "certainty_horizon_days_max": (
                int(item.get("certainty_horizon_days_max"))
                if isinstance(item.get("certainty_horizon_days_max"), (int, float))
                else None
            ),
            "certainty_target_return_pct": (
                float(item.get("certainty_target_return_pct"))
                if isinstance(item.get("certainty_target_return_pct"), (int, float))
                else None
            ),
            "certainty_prob": (
                float(item.get("certainty_prob"))
                if isinstance(item.get("certainty_prob"), (int, float))
                else None
            ),
            "certainty_samples": (
                int(item.get("certainty_samples"))
                if isinstance(item.get("certainty_samples"), (int, float))
                else 0
            ),
            "certainty_bucket_key": str(item.get("certainty_bucket_key") or "").strip(),
            "role": str(item.get("role") or "").strip(),
            "wave_phase": str(item.get("wave_phase") or "").strip(),
            "wave_phase_confidence": float(item.get("wave_phase_confidence") or 0.0),
            "pattern_evidence": list(item.get("pattern_evidence") or []),
            "evidence_bundle": list(item.get("evidence_bundle") or []),
            "reasons": list(item.get("reasons") or []),
            "signal_source": str(item.get("signal_source") or "").strip(),
            "soft_flags": list(item.get("soft_flags") or []),
        }
        formal_front = item.get("formal_front") if isinstance(item.get("formal_front"), dict) else None
        if isinstance(formal_front, dict):
            out["formal_front"] = dict(formal_front)
        else:
            out["formal_front"] = None
        return out

    def _signal_with_formal_priority(signal_payload: dict[str, Any]) -> dict[str, Any]:
        item = dict(signal_payload)
        formal_front = project_lowfreq_formal_front(item)
        if isinstance(formal_front, dict):
            item["formal_front"] = dict(formal_front)
        if not isinstance(formal_front, dict) or str(formal_front.get("status") or "") != "ok":
            return item

        entry_state = formal_front.get("entry_state") if isinstance(formal_front.get("entry_state"), dict) else {}
        tracking_state = formal_front.get("tracking_state") if isinstance(formal_front.get("tracking_state"), dict) else {}
        identify_state = formal_front.get("identify_state") if isinstance(formal_front.get("identify_state"), dict) else {}
        entry_ready = bool(entry_state.get("actionable")) or str(entry_state.get("status") or "") == "ready"
        candidate_tier = str(item.get("candidate_tier") or "").strip()
        if entry_ready:
            candidate_tier = "entry_ready"
        elif str(tracking_state.get("status") or "") == "tracking" or str(identify_state.get("status") or "") == "identified":
            candidate_tier = "soft_retained"
        item["entry_ready"] = entry_ready
        if candidate_tier:
            item["candidate_tier"] = candidate_tier
        return item

    candidate_signals: dict[str, dict[str, Any]] = {}
    entry_signals: dict[str, dict[str, Any]] = {}
    signal_summary: dict[str, Any] = {}
    tracking_pool_candidates_by_code: dict[str, dict[str, Any]] = {}
    tracking_pool_candidate_order: list[str] = []

    if isinstance(raw, dict):
        summary = raw.get("signal_summary")
        if isinstance(summary, dict):
            signal_summary = dict(summary)

        raw_entry = raw.get("entry_signals")
        if not isinstance(raw_entry, list):
            raw_entry = []

        raw_order = raw.get("tracking_pool_candidate_order")
        if isinstance(raw_order, list):
            tracking_pool_candidate_order = [
                str(code).strip() for code in raw_order if str(code).strip()
            ]

        raw_candidate = raw.get("tracking_pool_candidates")
        if isinstance(raw_candidate, dict):
            raw_candidate_items = [item for item in raw_candidate.values() if isinstance(item, dict)]
        elif isinstance(raw_candidate, list):
            raw_candidate_items = [item for item in raw_candidate if isinstance(item, dict)]
        else:
            raw_candidate_items = []

        if not raw_candidate_items:
            legacy_candidate = raw.get("candidate_signals")
            if isinstance(legacy_candidate, list):
                raw_candidate_items = [item for item in legacy_candidate if isinstance(item, dict)]
            if not raw_candidate_items:
                raw_candidate_items = [item for item in raw_entry if isinstance(item, dict)]

        for item in raw_candidate_items:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip()
            if code:
                enriched = _signal_with_formal_priority(item)
                candidate_signals[code] = enriched
                tracking_pool_candidates_by_code[code] = _tracking_pool_candidate(enriched)

        for item in raw_entry:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip()
            if code:
                entry_signals[code] = _signal_with_formal_priority(item)

    signal_summary.setdefault("candidate_count", len(candidate_signals))
    signal_summary.setdefault("entry_count", len(entry_signals))
    signal_summary.setdefault(
        "soft_retained_count",
        sum(1 for item in candidate_signals.values() if str(item.get("candidate_tier") or "") == "soft_retained"),
    )
    if tracking_pool_candidate_order:
        tracking_pool_candidate_order = [
            code for code in tracking_pool_candidate_order if code in tracking_pool_candidates_by_code
        ]
    else:
        tracking_pool_candidate_order = list(tracking_pool_candidates_by_code.keys())
    return {
        "candidate_signals": candidate_signals,
        "entry_signals": entry_signals,
        "tracking_pool_candidates": tracking_pool_candidates_by_code,
        "tracking_pool_candidate_order": list(tracking_pool_candidate_order),
        "tracking_pool_candidate_fields": dict(tracking_pool_candidate_fields),
        "signal_summary": signal_summary,
    }
