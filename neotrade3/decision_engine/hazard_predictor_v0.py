from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional


@dataclass(frozen=True)
class HazardT2OnlineConfig:
    accel_window_days: int = 15
    accel_return_threshold: float = 0.30
    break_pct_threshold: float = -7.0
    confirm_window_days: int = 10
    prebreak_lookback_days: int = 5


def _clamp_int(value: float, *, lo: int = 0, hi: int = 100) -> int:
    return max(int(lo), min(int(hi), int(round(float(value)))))


def _accel_return(closes: list[float], idx: int, *, window: int) -> Optional[float]:
    if idx < int(window):
        return None
    base = float(closes[idx - int(window)])
    now = float(closes[idx])
    if base <= 0 or now <= 0:
        return None
    return now / base - 1.0


def _hazard_score(
    *,
    state: str,
    accel_ret: Optional[float],
    days_since_break: int,
    recovered: bool,
    horizon_days: int,
) -> int:
    h = int(horizon_days)
    if state == "neutral":
        return 5
    if state == "accel_only":
        r = float(accel_ret or 0.0)
        base = 40.0
        if r > 0.30:
            base += min(50.0, (r - 0.30) / 0.40 * 50.0)
        if h >= 20:
            base += 5.0
        return _clamp_int(base, lo=0, hi=100)
    if state in {"break_armed", "stale_break", "recovering"}:
        return 0
    return 0


def compute_hazard_snapshots_v0_t2_for_series(
    *,
    dates: list[str],
    closes: list[float],
    highs: list[float],
    pct_changes: list[float],
    cfg: Optional[HazardT2OnlineConfig] = None,
    include_evidence: bool = True,
) -> list[dict[str, Any]]:
    cfg_v = cfg if isinstance(cfg, HazardT2OnlineConfig) else HazardT2OnlineConfig()
    n = len(dates)
    if n <= 0:
        return []
    lookback = min(n - 1, max(int(cfg_v.confirm_window_days) * 6, 60))
    out: list[dict[str, Any]] = []
    latest_break_idx: Optional[int] = None
    latest_pre_high = 0.0
    latest_accel_at_break: Optional[float] = None
    recovered = False
    recovered_date = ""

    for i in range(n):
        if latest_break_idx is not None and int(i - latest_break_idx) > int(lookback):
            latest_break_idx = None
            latest_pre_high = 0.0
            latest_accel_at_break = None
            recovered = False
            recovered_date = ""

        accel_ret = _accel_return(closes, i, window=int(cfg_v.accel_window_days))
        accel_ok = accel_ret is not None and float(accel_ret) >= float(cfg_v.accel_return_threshold)
        break_candidate = (
            accel_ok
            and i >= int(cfg_v.prebreak_lookback_days)
            and float(pct_changes[i]) <= float(cfg_v.break_pct_threshold)
        )
        if break_candidate:
            latest_break_idx = int(i)
            pre_start = max(0, int(i) - int(cfg_v.prebreak_lookback_days))
            pre_end = int(i)
            latest_pre_high = (
                max(float(x) for x in highs[pre_start:pre_end]) if pre_end > pre_start else 0.0
            )
            latest_accel_at_break = accel_ret
            recovered = False
            recovered_date = ""
        elif latest_break_idx is not None and not recovered and latest_pre_high > 0:
            if float(highs[i]) > float(latest_pre_high):
                recovered = True
                recovered_date = str(dates[i])

        if i < int(cfg_v.accel_window_days):
            out.append(
                {
                    "risk_status": "pending",
                    "hazard_state": "not_ready",
                    "stock_top_risk_5d": 0,
                    "stock_top_risk_20d": 0,
                    "first_event_date": "",
                    "evidence": ["history_insufficient_for_accel"] if bool(include_evidence) else [],
                }
            )
            continue

        evidence: list[str] = []
        if bool(include_evidence):
            evidence.append(
                f"t2_online:k{int(cfg_v.accel_window_days)}_r{float(cfg_v.accel_return_threshold):.2f}"
                f"_b{float(cfg_v.break_pct_threshold):.1f}_m{int(cfg_v.confirm_window_days)}"
                f"_pre{int(cfg_v.prebreak_lookback_days)}"
            )

        if latest_break_idx is None:
            state = "accel_only" if accel_ok else "neutral"
            if bool(include_evidence) and state == "accel_only" and accel_ret is not None:
                evidence.append(f"accel_15d_ret={float(accel_ret):.4f}")
            score5 = _hazard_score(
                state=state,
                accel_ret=accel_ret,
                days_since_break=0,
                recovered=False,
                horizon_days=5,
            )
            score20 = _hazard_score(
                state=state,
                accel_ret=accel_ret,
                days_since_break=0,
                recovered=False,
                horizon_days=20,
            )
            out.append(
                {
                    "risk_status": "ready",
                    "hazard_state": str(state),
                    "stock_top_risk_5d": int(score5),
                    "stock_top_risk_20d": int(score20),
                    "first_event_date": "",
                    "evidence": list(evidence),
                }
            )
            continue

        first_event_date = str(dates[int(latest_break_idx)])
        days_since_break = int(i - int(latest_break_idx))
        if bool(include_evidence):
            evidence.append(f"break_date={first_event_date}")
            evidence.append(f"break_pct={float(pct_changes[int(latest_break_idx)]):.2f}")

        if recovered:
            state = "recovering"
            if bool(include_evidence):
                evidence.append("recovered_by_prebreak_5d_high")
                evidence.append(f"recovered_date={recovered_date}")
        else:
            state = "stale_break" if days_since_break >= int(cfg_v.confirm_window_days) else "break_armed"
            if bool(include_evidence):
                evidence.append(f"days_since_break={int(days_since_break)}")

        if bool(include_evidence) and latest_accel_at_break is not None:
            evidence.append(f"accel_at_break_ret={float(latest_accel_at_break):.4f}")

        score5 = _hazard_score(
            state=state,
            accel_ret=latest_accel_at_break,
            days_since_break=days_since_break,
            recovered=recovered,
            horizon_days=5,
        )
        score20 = _hazard_score(
            state=state,
            accel_ret=latest_accel_at_break,
            days_since_break=days_since_break,
            recovered=recovered,
            horizon_days=20,
        )
        out.append(
            {
                "risk_status": "ready",
                "hazard_state": str(state),
                "stock_top_risk_5d": int(score5),
                "stock_top_risk_20d": int(score20),
                "first_event_date": str(first_event_date),
                "evidence": list(evidence),
            }
        )

    return out


def build_hazard_snapshot_v0_t2(
    cursor: sqlite3.Cursor,
    *,
    code: str,
    target_date: date,
    cfg: Optional[HazardT2OnlineConfig] = None,
) -> dict[str, Any]:
    cfg_v = cfg if isinstance(cfg, HazardT2OnlineConfig) else HazardT2OnlineConfig()
    code_s = str(code or "").strip()
    if not code_s:
        return {
            "risk_status": "pending",
            "hazard_state": "not_ready",
            "stock_top_risk_5d": 0,
            "stock_top_risk_20d": 0,
            "first_event_date": "",
            "evidence": ["code_missing"],
        }

    rows = cursor.execute(
        """
        SELECT trade_date, close, high, pct_change
        FROM daily_prices
        WHERE code = ?
          AND trade_date <= ?
          AND trade_date IS NOT NULL
          AND TRIM(trade_date) != ''
        ORDER BY trade_date ASC
        """,
        (code_s, target_date.isoformat()),
    ).fetchall()
    if not rows:
        return {
            "risk_status": "pending",
            "hazard_state": "not_ready",
            "stock_top_risk_5d": 0,
            "stock_top_risk_20d": 0,
            "first_event_date": "",
            "evidence": ["price_series_missing"],
        }

    dates: list[str] = []
    closes: list[float] = []
    highs: list[float] = []
    pct_changes: list[float] = []
    for trade_date, close, high, pct_change in rows:
        d = str(trade_date or "").strip()
        if not d:
            continue
        dates.append(d)
        closes.append(float(close or 0.0))
        highs.append(float(high or 0.0))
        pct_changes.append(float(pct_change or 0.0))

    if not dates:
        return {
            "risk_status": "pending",
            "hazard_state": "not_ready",
            "stock_top_risk_5d": 0,
            "stock_top_risk_20d": 0,
            "first_event_date": "",
            "evidence": ["price_series_empty"],
        }

    if str(dates[-1]) != target_date.isoformat():
        return {
            "risk_status": "pending",
            "hazard_state": "not_ready",
            "stock_top_risk_5d": 0,
            "stock_top_risk_20d": 0,
            "first_event_date": "",
            "evidence": ["target_date_bar_missing"],
        }

    snapshots = compute_hazard_snapshots_v0_t2_for_series(
        dates=dates,
        closes=closes,
        highs=highs,
        pct_changes=pct_changes,
        cfg=cfg_v,
        include_evidence=True,
    )
    if not snapshots:
        return {
            "risk_status": "pending",
            "hazard_state": "not_ready",
            "stock_top_risk_5d": 0,
            "stock_top_risk_20d": 0,
            "first_event_date": "",
            "evidence": ["price_series_empty"],
        }
    return dict(snapshots[-1])
