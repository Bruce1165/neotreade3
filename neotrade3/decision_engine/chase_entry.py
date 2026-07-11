from __future__ import annotations

from typing import Any


def build_chase_entry_snapshot(
    *,
    enabled: bool,
    closes: list[float],
    ref_price: float,
    near_high_ratio: float,
    pre3_threshold: float,
    pre5_threshold: float,
) -> dict[str, Any] | None:
    if not bool(enabled):
        return None

    normalized_ref_price = float(ref_price or 0.0)
    if normalized_ref_price <= 0.0:
        return None

    normalized_closes = [float(close) for close in list(closes or [])]
    if len(normalized_closes) < 5:
        return None

    normalized_near_high_ratio = float(near_high_ratio)
    normalized_pre3_threshold = float(pre3_threshold)
    normalized_pre5_threshold = float(pre5_threshold)

    trailing5 = normalized_closes[-5:]
    trailing10 = normalized_closes[-10:] if len(normalized_closes) >= 10 else normalized_closes
    near_5d_high = bool(trailing5) and normalized_ref_price >= max(trailing5) * normalized_near_high_ratio
    near_10d_high = bool(trailing10) and normalized_ref_price >= max(trailing10) * normalized_near_high_ratio

    pre3_close = normalized_closes[-3] if len(normalized_closes) >= 3 else None
    pre5_close = normalized_closes[-5] if len(normalized_closes) >= 5 else None
    pre3_return_pct = (
        (normalized_ref_price - float(pre3_close)) / max(float(pre3_close), 1e-9) * 100.0
        if pre3_close is not None
        else None
    )
    pre5_return_pct = (
        (normalized_ref_price - float(pre5_close)) / max(float(pre5_close), 1e-9) * 100.0
        if pre5_close is not None
        else None
    )

    near_high_flag = bool(near_5d_high or near_10d_high)
    recent_runup_flag = bool(
        (pre3_return_pct is not None and float(pre3_return_pct) >= normalized_pre3_threshold)
        or (pre5_return_pct is not None and float(pre5_return_pct) >= normalized_pre5_threshold)
    )
    blocked = bool(near_high_flag and recent_runup_flag)
    details = (
        f"追高型买点硬禁：近5日高位={'是' if near_5d_high else '否'} | "
        f"近10日高位={'是' if near_10d_high else '否'} | "
        f"前3日涨幅{float(pre3_return_pct):.1f}% | 前5日涨幅{float(pre5_return_pct):.1f}%"
        if pre3_return_pct is not None and pre5_return_pct is not None
        else "追高型买点硬禁：历史窗口不足"
    )
    return {
        "blocked": bool(blocked),
        "near_high_flag": bool(near_high_flag),
        "recent_runup_flag": bool(recent_runup_flag),
        "near_5d_high": bool(near_5d_high),
        "near_10d_high": bool(near_10d_high),
        "pre3_return_pct": round(float(pre3_return_pct), 2) if pre3_return_pct is not None else None,
        "pre5_return_pct": round(float(pre5_return_pct), 2) if pre5_return_pct is not None else None,
        "details": details,
    }
