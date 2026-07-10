from __future__ import annotations

from datetime import date
from typing import Any, Callable

import numpy as np


def build_global_candidates(
    cursor: Any,
    *,
    target_date: date,
    top_n: int,
    market_cap_min: float,
    market_cap_max: float,
    cross_sector_scan_limit: int,
    exclude_sectors: set[str] | None,
    exclude_codes: set[str] | None,
    cup_handle_enabled: bool,
    cup_handle_bonus: float,
    relative_strength_bonus_cap: float,
    release_enabled: bool,
    release_min_score: float,
    cup_handle_loader: Callable[[date], set[str]],
    structure_confirm_loader: Callable[..., dict[str, Any]],
    fundamentals_loader: Callable[[Any, list[str], date], dict[str, dict[str, Any]]],
    check_fundamentals: Callable[[dict[str, Any]], tuple[bool, float, list[str]]],
    history_batch_loader: Callable[..., dict[str, list[dict[str, Any]]]],
    weekly_returns_loader: Callable[[str, date], dict[str, Any]],
    wave_phase_detector: Callable[..., tuple[str, float]],
    focus_gate_checker: Callable[..., tuple[bool, list[str], dict[str, Any]]],
    strong_leader_release: Callable[..., tuple[float, list[str], list[str]]],
    market_focus_snapshot_loader: Callable[..., dict[str, Any]],
    stock_candidate_factory: Callable[..., Any],
) -> list[Any]:
    seed_rows = load_global_seed_rows(
        cursor,
        target_date=target_date,
        market_cap_min=market_cap_min,
        market_cap_max=market_cap_max,
        cross_sector_scan_limit=cross_sector_scan_limit,
    )
    filtered_rows, dedup_codes = filter_seed_rows(
        seed_rows,
        exclude_sectors=exclude_sectors,
        exclude_codes=exclude_codes,
    )
    if not filtered_rows:
        return []

    cup_picks = cup_handle_loader(target_date) if bool(cup_handle_enabled) else set()
    fundamentals_by_code = fundamentals_loader(cursor, dedup_codes, target_date)
    history_by_code = load_global_history_views(
        cursor,
        codes=dedup_codes,
        target_date=target_date,
        history_batch_loader=history_batch_loader,
    )

    staged: list[dict[str, Any]] = []
    for seed in filtered_rows:
        code = str(seed["code"])
        name = str(seed["name"])
        sector = str(seed["sector"])
        mkt_cap = float(seed["mkt_cap"])
        close = float(seed["close"])
        pct_chg = float(seed["pct_chg"])
        reasons: list[str] = []
        base_score = 0.0
        cup_ok = code in cup_picks
        soft_flags: list[str] = []

        fundamentals = fundamentals_by_code.get(code) or {
            "pe_ttm": 0,
            "profit_growth": 0,
            "revenue_growth": 0,
            "roe": 0,
            "table_exists": False,
        }
        fund_passed, fund_score, fund_reasons = check_fundamentals(fundamentals)
        if not fund_passed:
            soft_flags.append("fundamentals_soft_fail")
            base_score -= 12.0
            reasons.append("capture-first: 基本面未过，降权保留")
            reasons.extend([f"soft:{reason}" for reason in fund_reasons])
        else:
            base_score += float(fund_score) * 0.3
            reasons.extend(fund_reasons)

        structure = dict(structure_confirm_loader(code=code, target_date=target_date) or {})
        if not structure.get("passed"):
            soft_flags.append("structure_soft_fail")
            base_score -= 10.0
            reasons.append("capture-first: 结构未确认，降权保留")
            reasons.extend([f"soft:{reason}" for reason in list(structure.get("reasons") or [])])
        else:
            reasons.extend(list(structure.get("reasons") or []))

        if cup_ok:
            base_score += float(cup_handle_bonus)
            if "杯柄确认（cup_handle_v4）" not in reasons:
                reasons.append("杯柄确认（cup_handle_v4）")

        history = history_by_code.get(code) or []
        closes = [row["close"] for row in history[:30] if row.get("close") is not None]
        vols = [row["volume"] for row in history[:30] if row.get("volume") is not None]
        if len(history) < 20 or len(closes) < 20:
            soft_flags.append("history_short")
            base_score -= 6.0
            reasons.append("capture-first: 历史样本不足，保留但不做完整结构打分")

        price_position = 50.0
        if len(closes) >= 20:
            high_20 = max(closes[:20])
            low_20 = min(closes[:20])
            if high_20 > low_20:
                price_position = (float(close) - low_20) / (high_20 - low_20) * 100.0
            if 60 <= price_position <= 90:
                base_score += 20
                reasons.append(f"价格位置{price_position:.0f}%（突破区间）")
            elif 40 <= price_position < 60:
                base_score += 12

        wave_closes = [row["close"] for row in history if row.get("close") is not None]
        wave_highs = [row["high"] for row in history if row.get("high") is not None]
        wave_lows = [row["low"] for row in history if row.get("low") is not None]
        wave_phase, _wave_confidence = wave_phase_detector(
            closes=wave_closes,
            highs=wave_highs,
            lows=wave_lows,
        )
        if wave_phase == "3浪":
            base_score += 20
            reasons.append("3浪主升浪")
        elif wave_phase == "1浪":
            base_score += 15
            reasons.append("1浪启动")
        elif len(closes) >= 20:
            soft_flags.append("wave_uncertain")

        resonance = resonance_from_closes(closes)
        if resonance >= 0.7:
            base_score += 15
            reasons.append(f"同频共振{resonance:.0%}")
        elif resonance >= 0.5:
            base_score += 8
            reasons.append(f"共振{resonance:.0%}")
        else:
            soft_flags.append("low_resonance")
            base_score -= 3.0
            reasons.append(f"capture-first: 共振偏弱{resonance:.0%}，降权保留")

        avg_vol_5d = np.mean(vols[1:6]) if len(vols) >= 6 else (np.mean(vols[1:]) if len(vols) > 1 else 0.0)
        vol_ratio = float(vols[0]) / float(avg_vol_5d) if len(vols) > 0 and float(avg_vol_5d) > 0 else 1.0
        if 1.0 < vol_ratio <= 2.0:
            base_score += 15
            reasons.append(f"温和放量{vol_ratio:.1f}倍")

        ret_5d = (
            (float(closes[0]) - float(closes[4])) / float(closes[4]) * 100.0
            if len(closes) >= 5 and float(closes[4]) > 0
            else 0.0
        )
        if 2 <= ret_5d <= 10:
            base_score += 10
            reasons.append(f"5日涨{ret_5d:.1f}%（适中）")

        if len(closes) >= 20:
            ma5 = np.mean(closes[:5])
            ma10 = np.mean(closes[:10])
            ma20 = np.mean(closes[:20])
            if float(close) > ma5 > ma10 > ma20:
                base_score += 10
                reasons.append("均线多头排列")
            elif ma5 > ma10 and float(close) > ma5:
                base_score += 6

        mkt_cap_yi = float(mkt_cap) / 1e8
        if 200 <= mkt_cap_yi <= 300:
            base_score += 10
        elif 300 < mkt_cap_yi <= 350:
            base_score += 7

        weekly_ret = weekly_returns_loader(code, target_date)
        if weekly_ret.get("status") == "ok":
            strength_score = (
                float(weekly_ret.get("ret_1w") or 0.0) * 0.45
                + float(weekly_ret.get("ret_4w") or 0.0) * 0.35
                + float(weekly_ret.get("ret_12w") or 0.0) * 0.2
            )
        else:
            ret_20d = (
                (float(closes[0]) - float(closes[19])) / float(closes[19]) * 100.0
                if len(closes) >= 20 and float(closes[19]) > 0
                else 0.0
            )
            strength_score = (
                float(pct_chg or 0.0) * 0.45
                + float(ret_5d or 0.0) * 0.35
                + float(ret_20d or 0.0) * 0.2
            )

        staged.append(
            {
                "code": code,
                "name": name,
                "sector": sector,
                "mkt_cap": mkt_cap,
                "fundamentals": fundamentals,
                "base_score": float(base_score),
                "reasons": reasons,
                "wave_phase": wave_phase,
                "ret_5d": float(ret_5d),
                "vol_ratio": float(vol_ratio),
                "price_position": float(price_position),
                "resonance": float(resonance),
                "strength_score": float(strength_score),
                "cup_ok": bool(cup_ok),
                "soft_flags": soft_flags,
            }
        )

    if not staged:
        return []

    role_by_code, sector_avg_strength = assign_global_roles_by_sector(staged)
    candidates: list[Any] = []
    for item in staged:
        code = str(item["code"])
        stock_name = str(item.get("name") or "")
        sector = str(item.get("sector") or "")
        role = role_by_code.get(code) or "跟随"
        score = float(item.get("base_score") or 0.0)
        reasons = list(item.get("reasons") or [])
        soft_flags = list(item.get("soft_flags") or [])
        rel_delta = float(item.get("strength_score") or 0.0) - float(sector_avg_strength.get(sector) or 0.0)
        bonus_cap = float(relative_strength_bonus_cap)
        if bonus_cap > 0 and rel_delta > 0:
            score += min(bonus_cap, float(rel_delta))
            reasons.append(f"相对板块强度+{rel_delta:.1f}")
        if role == "龙头":
            score += 15
            reasons.append("板块龙头（多因子）")
        elif role == "中军":
            score += 8
            reasons.append("板块中军（多因子）")

        passed_focus, focus_reasons, focus_snapshot = focus_gate_checker(
            cursor,
            code=code,
            stock_name=stock_name,
            role=role,
            target_date=target_date,
            market_focus_snapshot_loader=market_focus_snapshot_loader,
        )
        if not passed_focus:
            soft_flags.append("focus_soft_fail")
            score -= 8.0
            reasons.append("capture-first: focus gate 未过，降权保留")
            reasons.extend([f"soft:{reason}" for reason in focus_reasons])
        else:
            score += float(focus_snapshot.get("focus_bonus") or 0.0)
            reasons.extend(focus_reasons)

        if role == "跟随":
            soft_flags.append("follower_soft")
            score -= 4.0
            reasons.append("capture-first: 跟随股降权保留")

        score, soft_flags, reasons = strong_leader_release(
            score=float(score),
            role=role,
            wave_phase=str(item.get("wave_phase") or ""),
            soft_flags=soft_flags,
            reasons=reasons,
            release_enabled=bool(release_enabled),
            release_min_score=float(release_min_score),
        )
        mkt_cap_yi = float(item.get("mkt_cap") or 0.0) / 1e8
        fundamentals = item.get("fundamentals") or {}
        candidates.append(
            stock_candidate_factory(
                code=code,
                name=stock_name,
                sector=sector,
                market_cap_yi=round(mkt_cap_yi, 1),
                role=role,
                buy_score=float(score),
                buy_reasons=reasons,
                wave_phase=str(item.get("wave_phase") or ""),
                ret_5d=round(float(item.get("ret_5d") or 0.0), 2),
                vol_ratio=round(float(item.get("vol_ratio") or 0.0), 2),
                price_position=round(float(item.get("price_position") or 0.0), 1),
                pe_ttm=fundamentals.get("pe_ttm", 0),
                profit_growth=fundamentals.get("profit_growth", 0),
                revenue_growth=fundamentals.get("revenue_growth", 0),
                roe=fundamentals.get("roe", 0),
                sector_resonance=round(float(item.get("resonance") or 0.0), 2),
                cup_handle_ok=bool(item.get("cup_ok") or False),
                signal_source="cross_sector",
                soft_flags=soft_flags,
            )
        )

    candidates.sort(key=_buy_score_of, reverse=True)
    return candidates[: int(top_n)]


def load_global_seed_rows(
    cursor: Any,
    *,
    target_date: date,
    market_cap_min: float,
    market_cap_max: float,
    cross_sector_scan_limit: int,
) -> list[tuple[Any, ...]]:
    cursor.execute(
        """
        SELECT s.code, s.name, s.sector_lv1, s.total_market_cap,
               dp.close, dp.pct_change, dp.amount, dp.volume
        FROM stocks s
        JOIN daily_prices dp ON s.code = dp.code
        WHERE dp.trade_date = ?
          AND s.total_market_cap >= ? AND s.total_market_cap <= ?
          AND (s.is_delisted IS NULL OR s.is_delisted = 0)
          AND dp.close > 0
        ORDER BY dp.pct_change DESC
        LIMIT ?
        """,
        (
            target_date.isoformat(),
            market_cap_min,
            market_cap_max,
            int(cross_sector_scan_limit),
        ),
    )
    return list(cursor.fetchall() or [])


def filter_seed_rows(
    rows: list[tuple[Any, ...]],
    *,
    exclude_sectors: set[str] | None,
    exclude_codes: set[str] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    excluded_sectors = {str(item or "").strip() for item in (exclude_sectors or set()) if str(item or "").strip()}
    excluded_codes = {str(item or "").strip() for item in (exclude_codes or set()) if str(item or "").strip()}
    filtered_rows: list[dict[str, Any]] = []
    candidate_codes: list[str] = []
    for code, name, sector, mkt_cap, close, pct_chg, amount, volume in rows:
        code_s = str(code or "").strip()
        sector_s = str(sector or "").strip()
        if not code_s or not sector_s:
            continue
        if code_s in excluded_codes or sector_s in excluded_sectors:
            continue
        filtered_rows.append(
            {
                "code": code_s,
                "name": str(name or ""),
                "sector": sector_s,
                "mkt_cap": float(mkt_cap or 0.0),
                "close": float(close or 0.0),
                "pct_chg": float(pct_chg or 0.0),
                "amount": float(amount or 0.0),
                "volume": float(volume or 0.0),
            }
        )
        candidate_codes.append(code_s)
    return filtered_rows, list(dict.fromkeys(candidate_codes))


def load_global_history_views(
    cursor: Any,
    *,
    codes: list[str],
    target_date: date,
    history_batch_loader: Callable[..., dict[str, list[dict[str, Any]]]],
) -> dict[str, list[dict[str, Any]]]:
    if not codes:
        return {}
    return dict(
        history_batch_loader(
            cursor,
            codes,
            target_date=target_date,
            limit=60,
        )
        or {}
    )


def assign_global_roles_by_sector(staged: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, float]]:
    by_sector: dict[str, list[dict[str, Any]]] = {}
    for item in staged:
        by_sector.setdefault(str(item.get("sector") or ""), []).append(item)

    sector_avg_strength: dict[str, float] = {}
    role_by_code: dict[str, str] = {}
    for sector, items in by_sector.items():
        ranked = sorted(items, key=lambda item: float(item.get("strength_score") or 0.0), reverse=True)
        sector_avg_strength[sector] = float(
            np.mean([float(item.get("strength_score") or 0.0) for item in ranked]) if ranked else 0.0
        )
        for idx, item in enumerate(ranked):
            code = str(item["code"])
            if idx <= 1:
                role_by_code[code] = "龙头"
            elif idx <= 3:
                role_by_code[code] = "中军"
            else:
                role_by_code[code] = "跟随"
    return role_by_code, sector_avg_strength


def resonance_from_closes(closes: list[Any]) -> float:
    resonance = 0.5
    if len(closes) >= 10 and closes[4] and closes[9] and closes[4] > 0 and closes[9] > 0:
        stock_ret_5d = (closes[0] - closes[4]) / closes[4] * 100
        stock_ret_10d = (closes[0] - closes[9]) / closes[9] * 100
        if 2 <= stock_ret_5d <= 15:
            resonance += 0.3
        if 2 <= stock_ret_10d <= 20:
            resonance += 0.2
    return min(1.0, float(resonance))


def _buy_score_of(item: Any) -> float:
    if isinstance(item, dict):
        return float(item.get("buy_score") or 0.0)
    return float(getattr(item, "buy_score", 0.0))
