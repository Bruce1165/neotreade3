from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional


@dataclass(frozen=True)
class ChaosOnlineConfigV0:
    lookback_days: int = 90
    regime_confirm_days: int = 4
    within_regime_window_days: int = 20


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


def _mean(values: list[float]) -> float:
    items = [float(x) for x in values if isinstance(x, (int, float))]
    if not items:
        return 0.0
    return float(sum(items)) / float(len(items))


def _std(values: list[float]) -> float:
    items = [float(x) for x in values if isinstance(x, (int, float))]
    if len(items) <= 1:
        return 0.0
    m = _mean(items)
    var = _mean([(x - m) ** 2 for x in items])
    return float(var) ** 0.5


def _percentile_rank(values: list[float], current: float) -> float | None:
    items = [float(x) for x in values if isinstance(x, (int, float))]
    if not items:
        return None
    cur = float(current)
    le = sum(1 for x in items if x <= cur)
    return float(le) / float(len(items))


def _zscore(values: list[float], current: float) -> float | None:
    items = [float(x) for x in values if isinstance(x, (int, float))]
    if len(items) <= 1:
        return None
    m = _mean(items)
    s = _std(items)
    if s <= 0:
        return None
    return (float(current) - float(m)) / float(s)


def _flip_count(signs: list[int]) -> int:
    if len(signs) <= 1:
        return 0
    c = 0
    prev = int(signs[0])
    for s in signs[1:]:
        si = int(s)
        if si != prev:
            c += 1
        prev = si
    return int(c)


def _sign(v: float) -> int:
    x = float(v)
    return 1 if x > 0 else (-1 if x < 0 else 0)


def _proxy_net_energy(*, pct_change: float, volume: float, avg_volume: float) -> float:
    vr = float(volume) / float(avg_volume) if float(avg_volume) > 0 else 1.0
    vr = _clamp(vr, 0.5, 2.0)
    return float(pct_change) * float(vr)


def _find_regime_anchor_date(
    *,
    dates: list[str],
    net_energy_series: list[float],
    confirm_days: int,
) -> str:
    n = len(net_energy_series)
    if n <= int(confirm_days) + 1:
        return ""
    for i in range(n - int(confirm_days) - 1, -1, -1):
        if _sign(net_energy_series[i]) >= 0:
            continue
        if _sign(net_energy_series[i + 1]) <= 0:
            continue
        ok = True
        for j in range(1, int(confirm_days) + 1):
            if _sign(net_energy_series[i + j]) <= 0:
                ok = False
                break
        if ok:
            return str(dates[i + 1])
    return ""


def build_chaos_snapshot_v0(
    cursor: sqlite3.Cursor,
    *,
    code: str,
    target_date: date,
    market_snapshot: dict[str, Any] | None = None,
    sector_snapshot: dict[str, Any] | None = None,
    trend_snapshot: dict[str, Any] | None = None,
    hazard_snapshot: dict[str, Any] | None = None,
    cfg: Optional[ChaosOnlineConfigV0] = None,
) -> dict[str, Any]:
    cfg_v = cfg if isinstance(cfg, ChaosOnlineConfigV0) else ChaosOnlineConfigV0()
    code_s = str(code or "").strip()
    target_key = target_date.isoformat()
    limit = max(int(cfg_v.lookback_days), 20)
    rows = cursor.execute(
        """
        SELECT trade_date, pct_change, volume
        FROM daily_prices
        WHERE code = ?
          AND trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (code_s, target_key, int(limit)),
    ).fetchall()
    if not rows or len(rows) < 10:
        return {
            "chaos_status": "pending",
            "yin_value": 0.0,
            "yang_value": 0.0,
            "yin_yang_ratio": "0:0",
            "net_energy": 0.0,
            "reference_mode": "price_volume_proxy_v0",
            "raw_factors": {},
            "self_history_reference": {
                "regime_anchor_date": "",
                "regime_day_index": -1,
                "within_regime_window_days": 0,
                "net_energy_percentile_in_window": None,
                "net_energy_zscore_in_window": None,
                "flip_count_in_window": 0,
                "flip_rate_in_window": 0.0,
                "yang_speed_mean_in_window": 0.0,
                "regime_shift_flag": False,
            },
            "factor_registry_version": "chaos_registry_v0",
            "weights_version": "chaos_weights_v0",
            "evidence": ["history_insufficient"],
        }

    dates_desc = [str(r[0]) for r in rows]
    pct_desc = [float(r[1] or 0.0) for r in rows]
    vol_desc = [float(r[2] or 0.0) for r in rows]
    dates = list(reversed(dates_desc))
    pct = list(reversed(pct_desc))
    vol = list(reversed(vol_desc))

    avg20_by_idx: list[float] = []
    for i in range(len(vol)):
        start = max(0, i - 19)
        avg20_by_idx.append(_mean(vol[start : i + 1]))

    net_series = [
        _proxy_net_energy(pct_change=float(pct[i]), volume=float(vol[i]), avg_volume=float(avg20_by_idx[i]))
        for i in range(len(vol))
    ]

    base_net = float(net_series[-1])
    evidence: list[str] = []
    raw_factors: dict[str, float] = {
        "pct_change": float(pct[-1]),
        "volume": float(vol[-1]),
        "avg_volume_20d": float(avg20_by_idx[-1]),
    }
    if float(vol[-1]) > 0 and float(avg20_by_idx[-1]) > 0:
        vr = float(vol[-1]) / float(avg20_by_idx[-1])
        evidence.append(f"volume_ratio_20d:{vr:.2f}")
        raw_factors["volume_ratio_20d"] = float(vr)
    evidence.append(f"pct_change:{float(pct[-1]):.2f}")
    raw_factors["net_energy_base"] = float(base_net)

    net_adj = float(base_net)
    if isinstance(market_snapshot, dict):
        if bool(market_snapshot.get("breadth_weak")):
            net_adj -= 0.8
            evidence.append("market_breadth_weak")
        if bool(market_snapshot.get("price_trend_weak")):
            net_adj -= 0.8
            evidence.append("market_price_trend_weak")
        if bool(market_snapshot.get("drawdown_weak")):
            net_adj -= 0.6
            evidence.append("market_drawdown_weak")
    if isinstance(sector_snapshot, dict):
        if bool(sector_snapshot.get("cooldown_detected")):
            net_adj -= 0.9
            evidence.append("sector_cooldown_detected")
        if bool(sector_snapshot.get("trend_deteriorating")):
            net_adj -= 0.7
            evidence.append("sector_trend_deteriorating")
        if bool(sector_snapshot.get("leader_rollover")):
            net_adj -= 0.8
            evidence.append("sector_leader_rollover")
    if isinstance(trend_snapshot, dict):
        if bool(trend_snapshot.get("drawdown_from_peak_triggered")):
            net_adj -= 1.2
            evidence.append("trend_exhaustion_triggered")
        elif bool(trend_snapshot.get("armed")):
            net_adj -= 0.4
            evidence.append("trend_exhaustion_armed")
    if isinstance(hazard_snapshot, dict):
        if str(hazard_snapshot.get("risk_status") or "").strip() == "ready":
            score_5d = int(hazard_snapshot.get("stock_top_risk_5d") or 0)
            if score_5d >= 70:
                net_adj -= 0.6
                evidence.append(f"hazard_score_5d:{score_5d}")

    yin = max(0.0, -float(net_adj))
    yang = max(0.0, float(net_adj))
    yin_i = int(round(float(yin)))
    yang_i = int(round(float(yang)))
    ratio = f"{yin_i}:{yang_i}"

    anchor_date = _find_regime_anchor_date(
        dates=dates,
        net_energy_series=net_series,
        confirm_days=int(cfg_v.regime_confirm_days),
    )
    anchor_idx = dates.index(anchor_date) if anchor_date and anchor_date in dates else -1
    if anchor_idx < 0:
        window_start = max(0, len(net_series) - int(cfg_v.within_regime_window_days))
    else:
        window_start = anchor_idx
    window_end = len(net_series)
    window = net_series[window_start:window_end]
    signs = [_sign(x) for x in window]
    flip_count = _flip_count(signs)
    flip_rate = float(flip_count) / float(max(1, len(signs) - 1))
    diffs = [float(window[i] - window[i - 1]) for i in range(1, len(window))] if len(window) >= 2 else []
    speed_mean = _mean(diffs)

    pct_rank = _percentile_rank(window, float(net_adj))
    z = _zscore(window, float(net_adj))
    regime_shift = bool(pct_rank is not None and (pct_rank <= 0.1 or pct_rank >= 0.9))
    raw_factors["net_energy_adjusted"] = float(net_adj)

    return {
        "chaos_status": "ready",
        "yin_value": float(yin),
        "yang_value": float(yang),
        "yin_yang_ratio": ratio,
        "net_energy": float(net_adj),
        "reference_mode": "price_volume_proxy_v0",
        "raw_factors": dict(raw_factors),
        "self_history_reference": {
            "regime_anchor_date": str(anchor_date),
            "regime_day_index": int(window_end - 1 - window_start),
            "within_regime_window_days": int(len(window)),
            "net_energy_percentile_in_window": pct_rank,
            "net_energy_zscore_in_window": z,
            "flip_count_in_window": int(flip_count),
            "flip_rate_in_window": float(flip_rate),
            "yang_speed_mean_in_window": float(speed_mean),
            "regime_shift_flag": bool(regime_shift),
        },
        "factor_registry_version": "chaos_registry_v0",
        "weights_version": "chaos_weights_v0",
        "evidence": list(dict.fromkeys([str(x) for x in evidence if str(x).strip()])),
    }
