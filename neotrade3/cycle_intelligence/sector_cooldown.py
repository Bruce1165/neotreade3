from __future__ import annotations

from datetime import date
from typing import Any, Callable

import numpy as np


def detect_sector_cooldown(
    cursor: Any,
    *,
    sector: str,
    target_date: date,
    market_cap_min: float,
    market_cap_max: float,
    sector_members_cache: dict[str, dict[str, Any]] | None = None,
    sector_cooldown_cache: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cache_key = (str(sector or ""), target_date.isoformat())
    if sector_cooldown_cache is not None:
        cached = sector_cooldown_cache.get(cache_key)
        if isinstance(cached, dict):
            return cached

    sector_key = str(sector or "").strip()
    cached_members = sector_members_cache.get(sector_key) if sector_members_cache and sector_key else None
    if isinstance(cached_members, dict):
        codes = list(cached_members.get("codes") or [])
        name_by_code = dict(cached_members.get("name_by_code") or {})
    else:
        cursor.execute(
            """
            SELECT s.code, s.name
            FROM stocks s
            WHERE s.sector_lv1 = ?
              AND s.total_market_cap >= ? AND s.total_market_cap <= ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
            """,
            (sector, market_cap_min, market_cap_max),
        )
        stock_rows = cursor.fetchall()
        if len(stock_rows) < 10:
            return _remember_result(sector_cooldown_cache, cache_key, _unknown_result())

        codes = []
        name_by_code = {}
        for code, name in stock_rows:
            code_s = str(code or "").strip()
            if not code_s:
                continue
            codes.append(code_s)
            name_by_code[code_s] = str(name or "")

        if sector_members_cache is not None:
            sector_members_cache[sector_key] = {"codes": codes, "name_by_code": name_by_code}

    if len(codes) < 10 or not codes:
        return _remember_result(sector_cooldown_cache, cache_key, _unknown_result())

    placeholders = ",".join(["?"] * len(codes))
    cursor.execute(
        f"""
        SELECT code, close, rn FROM (
            SELECT code, close,
                   row_number() OVER (PARTITION BY code ORDER BY trade_date DESC) as rn
            FROM daily_prices
            WHERE trade_date <= ?
              AND code IN ({placeholders})
        )
        WHERE rn <= 5
        ORDER BY code, rn
        """,
        (target_date.isoformat(), *codes),
    )
    price_rows = cursor.fetchall()

    closes_by_code: dict[str, list[float]] = {}
    for code, close, _rn in price_rows:
        code_s = str(code or "").strip()
        if not code_s or close is None:
            continue
        values = closes_by_code.get(code_s)
        if values is None:
            values = []
            closes_by_code[code_s] = values
        if len(values) < 5:
            values.append(float(close))

    returns: list[tuple[str, str, float]] = []
    for code_s in codes:
        closes = closes_by_code.get(code_s) or []
        if len(closes) < 5:
            continue
        close_0 = float(closes[0])
        close_5 = float(closes[4])
        if close_5 <= 0:
            continue
        ret = (close_0 - close_5) / close_5 * 100
        returns.append((code_s, name_by_code.get(code_s, ""), float(ret)))

    if len(returns) < 10:
        return _remember_result(sector_cooldown_cache, cache_key, _unknown_result())

    returns.sort(key=lambda item: item[2], reverse=True)
    n = len(returns)
    leaders = returns[: max(1, n // 5)]
    middle = returns[max(1, n // 5) : max(1, n // 5) + max(1, n * 3 // 10)]
    followers = returns[max(1, n // 2) :]

    leader_avg = float(np.mean([item[2] for item in leaders])) if leaders else 0.0
    _middle_avg = float(np.mean([item[2] for item in middle])) if middle else 0.0
    follower_avg = float(np.mean([item[2] for item in followers])) if followers else 0.0

    leader_strength = min(1.0, max(0.0, (leader_avg + 10.0) / 30.0))
    follower_weakness = min(1.0, max(0.0, (5.0 - follower_avg) / 15.0))

    if leader_avg > 15 and follower_avg > 5:
        trend_state = "rising"
    elif leader_avg < 5 and follower_avg < -5:
        trend_state = "falling"
    elif follower_avg < -3 and leader_avg > 10:
        trend_state = "diverging"
    else:
        trend_state = "consolidating"

    result = {
        "cooldown_detected": bool(follower_weakness > 0.6 and leader_strength > 0.5),
        "follower_weakness": follower_weakness,
        "leader_strength": leader_strength,
        "trend_state": trend_state,
        "leader_avg": leader_avg,
        "follower_avg": follower_avg,
    }
    return _remember_result(sector_cooldown_cache, cache_key, result)


def confirm_sector_cooldown(
    sector: str,
    current_date: date,
    *,
    window: int,
    required: int,
    trading_dates_loader: Callable[[date, date], list[date]],
    cooldown_loader: Callable[[str, date], dict[str, Any]],
) -> dict[str, Any]:
    start = current_date.fromordinal(current_date.toordinal() - 40)
    dates = list(trading_dates_loader(start, current_date) or [])
    tail = dates[-window:] if window > 0 else dates[-3:]
    hits = 0
    checked = 0
    latest: dict[str, Any] | None = None
    for trading_date in tail:
        info = dict(cooldown_loader(sector, trading_date) or {})
        latest = info
        checked += 1
        if (
            info.get("cooldown_detected")
            and float(info.get("follower_weakness") or 0) > 0.6
            and str(info.get("trend_state") or "") in {"diverging", "falling"}
        ):
            hits += 1

    return {
        "confirmed": bool(checked > 0 and hits >= required),
        "hits": hits,
        "checked": checked,
        "latest": latest or {},
    }


def _unknown_result() -> dict[str, Any]:
    return {
        "cooldown_detected": False,
        "follower_weakness": 0,
        "leader_strength": 0.5,
        "trend_state": "unknown",
    }


def _remember_result(
    cache: dict[tuple[str, str], dict[str, Any]] | None,
    cache_key: tuple[str, str],
    result: dict[str, Any],
) -> dict[str, Any]:
    if cache is not None:
        cache[cache_key] = result
    return result
