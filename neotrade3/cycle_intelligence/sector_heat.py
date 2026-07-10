from __future__ import annotations

from datetime import date
from typing import Any, Callable


def build_hot_sectors(
    cursor: Any,
    *,
    target_date: date,
    top_n: int,
    market_cap_min: float,
    market_cap_max: float,
    sector_accel_bonus_enabled: bool,
    sector_accel_lookback_trading_days: int,
    sector_accel_bonus_high: float,
    sector_accel_bonus_low: float,
    recent_trading_dates_loader: Callable[..., list[date]],
    sector_cooldown_loader: Callable[..., dict[str, Any]],
    sector_heat_factory: Callable[..., Any],
    skip_logger: Callable[[str, dict[str, Any]], None] | None = None,
) -> list[Any]:
    sector_name_by_code = load_sector_display_names(cursor)
    recent_avg_by_sector = load_recent_avg_by_sector(
        cursor,
        target_date=target_date,
        market_cap_min=market_cap_min,
        market_cap_max=market_cap_max,
        enabled=bool(sector_accel_bonus_enabled),
        lookback_trading_days=int(sector_accel_lookback_trading_days),
        recent_trading_dates_loader=recent_trading_dates_loader,
    )
    rows = load_sector_daily_aggregates(
        cursor,
        target_date=target_date,
        market_cap_min=market_cap_min,
        market_cap_max=market_cap_max,
        top_n=top_n,
    )

    sectors: list[Any] = []
    for sector, count, avg_change, _avg_vol, _total_amt in rows:
        sector_code = str(sector or "").strip()
        sector_display = sector_name_by_code.get(sector_code) or sector_code or str(sector)
        cooldown_info = dict(sector_cooldown_loader(sector, target_date, cursor=cursor) or {})

        if bool(cooldown_info.get("cooldown_detected")) and float(
            cooldown_info.get("follower_weakness") or 0.0
        ) > 0.7:
            if skip_logger is not None:
                skip_logger(str(sector), cooldown_info)
            continue

        heat_score = score_sector_heat(
            avg_change=float(avg_change or 0.0),
            avg_change_recent=float(recent_avg_by_sector.get(str(sector)) or 0.0),
            trend_state=str(cooldown_info.get("trend_state") or "unknown"),
            sector_accel_bonus_enabled=bool(sector_accel_bonus_enabled),
            sector_accel_bonus_high=float(sector_accel_bonus_high),
            sector_accel_bonus_low=float(sector_accel_bonus_low),
        )
        sectors.append(
            sector_heat_factory(
                sector=sector,
                name=sector_display,
                heat_score=heat_score,
                momentum_5d=avg_change or 0,
                stock_count=count,
                trend_state=str(cooldown_info.get("trend_state") or "unknown"),
                leader_strength=float(cooldown_info.get("leader_strength") or 0.0),
                follower_weakness=float(cooldown_info.get("follower_weakness") or 0.0),
            )
        )

    sectors.sort(key=_heat_score_of, reverse=True)
    return sectors[:top_n]


def load_sector_display_names(cursor: Any) -> dict[str, str]:
    cursor.execute(
        """
        SELECT sector_lv1, MAX(sector_lv2) AS sector_name
        FROM stocks
        WHERE sector_lv1 IS NOT NULL AND sector_lv2 IS NOT NULL
        GROUP BY sector_lv1
        """
    )
    sector_name_by_code: dict[str, str] = {}
    for sec_code, sec_name in cursor.fetchall():
        code = str(sec_code or "").strip()
        name = str(sec_name or "").strip()
        if code and name:
            sector_name_by_code[code] = name
    return sector_name_by_code


def load_recent_avg_by_sector(
    cursor: Any,
    *,
    target_date: date,
    market_cap_min: float,
    market_cap_max: float,
    enabled: bool,
    lookback_trading_days: int,
    recent_trading_dates_loader: Callable[..., list[date]],
) -> dict[str, float]:
    if not bool(enabled):
        return {}

    recent_dates = list(
        recent_trading_dates_loader(
            target_date,
            limit=max(1, int(lookback_trading_days)),
        )
        or []
    )
    if not recent_dates:
        return {}

    placeholders = ",".join(["?"] * len(recent_dates))
    args: list[object] = [trading_date.isoformat() for trading_date in recent_dates]
    args.extend([float(market_cap_min), float(market_cap_max)])
    cursor.execute(
        f"""
        SELECT s.sector_lv1, AVG(dp.pct_change) as avg_change_recent
        FROM stocks s
        JOIN daily_prices dp ON s.code = dp.code
        WHERE dp.trade_date IN ({placeholders})
          AND s.total_market_cap >= ? AND s.total_market_cap <= ?
          AND (s.is_delisted IS NULL OR s.is_delisted = 0)
        GROUP BY s.sector_lv1
        """,
        tuple(args),
    )

    recent_avg_by_sector: dict[str, float] = {}
    for sec, avg_recent in cursor.fetchall():
        if sec:
            recent_avg_by_sector[str(sec)] = float(avg_recent or 0.0)
    return recent_avg_by_sector


def load_sector_daily_aggregates(
    cursor: Any,
    *,
    target_date: date,
    market_cap_min: float,
    market_cap_max: float,
    top_n: int,
) -> list[tuple[Any, Any, Any, Any, Any]]:
    cursor.execute(
        """
        SELECT s.sector_lv1, COUNT(*) as stock_count,
               AVG(dp.pct_change) as avg_change,
               AVG(dp.volume) as avg_volume,
               SUM(dp.amount) as total_amount
        FROM stocks s
        JOIN daily_prices dp ON s.code = dp.code
        WHERE dp.trade_date = ?
          AND s.total_market_cap >= ? AND s.total_market_cap <= ?
          AND (s.is_delisted IS NULL OR s.is_delisted = 0)
        GROUP BY s.sector_lv1
        HAVING COUNT(*) >= 3
        ORDER BY avg_change DESC
        LIMIT ?
        """,
        (target_date.isoformat(), market_cap_min, market_cap_max, top_n * 2),
    )
    return list(cursor.fetchall() or [])


def score_sector_heat(
    *,
    avg_change: float,
    avg_change_recent: float,
    trend_state: str,
    sector_accel_bonus_enabled: bool,
    sector_accel_bonus_high: float,
    sector_accel_bonus_low: float,
) -> float:
    heat_score = 50.0
    if float(avg_change) > 2:
        heat_score += 30.0
    elif float(avg_change) > 1:
        heat_score += 20.0
    elif float(avg_change) > 0:
        heat_score += 10.0

    if bool(sector_accel_bonus_enabled):
        accel = float(avg_change) - float(avg_change_recent)
        if accel >= 0.8:
            heat_score += float(sector_accel_bonus_high)
        elif accel >= 0.3:
            heat_score += float(sector_accel_bonus_low)

    if str(trend_state or "") == "rising":
        heat_score += 15.0
    return heat_score


def _heat_score_of(item: Any) -> float:
    if isinstance(item, dict):
        return float(item.get("heat_score") or 0.0)
    return float(getattr(item, "heat_score", 0.0))
