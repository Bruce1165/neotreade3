from __future__ import annotations

from typing import Any


def build_market_exit_snapshot(
    *,
    top_snapshot: dict[str, Any] | None,
    drawdown_snapshot: dict[str, Any] | None,
    fallback_market_label: str,
    fallback_market_key: str,
    min_drawdown_pct: float,
) -> dict[str, Any] | None:
    market_label = ""
    proxy_key = str(fallback_market_key or "")
    if isinstance(top_snapshot, dict):
        market_label = str(top_snapshot.get("market_label") or "")
        proxy_key = str(top_snapshot.get("market_key") or proxy_key)
    elif isinstance(drawdown_snapshot, dict):
        market_label = str(drawdown_snapshot.get("market_label") or "")
    if not market_label:
        market_label = str(fallback_market_label or "市场")
    breadth_ratio = top_snapshot.get("breadth_ratio") if isinstance(top_snapshot, dict) else None
    break_ma20 = bool(top_snapshot.get("break_ma20")) if isinstance(top_snapshot, dict) else False
    ma20_weak = bool(top_snapshot.get("ma20_weak")) if isinstance(top_snapshot, dict) else False
    price_trend_weak = bool(break_ma20 or ma20_weak)
    breadth_weak = breadth_ratio is not None and float(breadth_ratio) < 0.40
    drawdown_pct = drawdown_snapshot.get("drawdown_pct") if isinstance(drawdown_snapshot, dict) else None
    drawdown_weak = drawdown_pct is not None and float(drawdown_pct) <= float(min_drawdown_pct)
    evidence_count = int(bool(price_trend_weak)) + int(bool(breadth_weak)) + int(bool(drawdown_weak))
    condition_pass = bool(price_trend_weak and breadth_weak and int(evidence_count) >= 2)
    if not condition_pass and not any((price_trend_weak, breadth_weak, drawdown_weak)):
        return None
    details = (
        f"{market_label}见顶确认候选：趋势转弱={'是' if price_trend_weak else '否'} | "
        f"广度转弱={'是' if breadth_weak else '否'} | "
        f"代理回撤{float(drawdown_pct):.1f}%"
        if drawdown_pct is not None
        else f"{market_label}见顶确认候选：趋势转弱={'是' if price_trend_weak else '否'} | "
        f"广度转弱={'是' if breadth_weak else '否'} | 代理回撤未知"
    )
    return {
        "scope": "market",
        "market_key": proxy_key,
        "market_label": market_label,
        "break_ma20": bool(break_ma20),
        "ma20_weak": bool(ma20_weak),
        "breadth_ratio": float(breadth_ratio) if breadth_ratio is not None else None,
        "drawdown_pct": float(drawdown_pct) if drawdown_pct is not None else None,
        "price_trend_weak": bool(price_trend_weak),
        "breadth_weak": bool(breadth_weak),
        "drawdown_weak": bool(drawdown_weak),
        "drawdown_is_observation_only": True,
        "evidence_count": int(evidence_count),
        "condition_pass": bool(condition_pass),
        "details": details,
    }


def build_sector_exit_snapshot(
    *,
    sector: str,
    cooldown_info: dict[str, Any] | None,
) -> dict[str, Any] | None:
    normalized_sector = str(sector or "").strip()
    if not normalized_sector:
        return None
    if not isinstance(cooldown_info, dict):
        return None
    follower_weakness = float(cooldown_info.get("follower_weakness") or 0.0)
    leader_strength = float(cooldown_info.get("leader_strength") or 0.0)
    leader_avg = float(cooldown_info.get("leader_avg") or 0.0)
    trend_state = str(cooldown_info.get("trend_state") or "unknown")
    cooldown_detected = bool(cooldown_info.get("cooldown_detected"))
    follower_weak = follower_weakness > 0.6
    trend_deteriorating = trend_state in {"diverging", "falling"}
    leader_rollover = leader_strength < 0.55 or leader_avg < 8.0
    evidence_count = (
        int(bool(trend_deteriorating))
        + int(bool(follower_weak))
        + int(bool(cooldown_detected))
        + int(bool(leader_rollover))
    )
    condition_pass = bool(trend_deteriorating and follower_weak)
    if not condition_pass and not any((cooldown_detected, trend_deteriorating, leader_rollover)):
        return None
    details = (
        f"板块见顶确认候选：{normalized_sector} | 趋势={trend_state} | "
        f"跟随股弱势{follower_weakness:.0%} | 龙头强度{leader_strength:.0%}"
    )
    return {
        "scope": "sector",
        "sector": normalized_sector,
        "cooldown_detected": bool(cooldown_detected),
        "follower_weakness": float(follower_weakness),
        "leader_strength": float(leader_strength),
        "leader_avg": float(leader_avg),
        "trend_state": trend_state,
        "follower_weak": bool(follower_weak),
        "trend_deteriorating": bool(trend_deteriorating),
        "leader_rollover": bool(leader_rollover),
        "cooldown_is_observation_only": True,
        "leader_rollover_is_observation_only": True,
        "evidence_count": int(evidence_count),
        "condition_pass": bool(condition_pass),
        "details": details,
    }
