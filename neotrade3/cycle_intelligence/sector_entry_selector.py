from __future__ import annotations

from datetime import date
from typing import Any, Callable

import numpy as np

from neotrade3.cycle_intelligence.legacy_recognition import (
    apply_strong_leader_soft_release,
    passes_core_focus_gate,
)
from neotrade3.cycle_intelligence.weekly_returns import weekly_returns_from_series


def build_sector_candidates(
    cursor: Any,
    *,
    sector: str,
    target_date: date,
    top_n: int,
    market_cap_min: float,
    market_cap_max: float,
    cup_handle_enabled: bool,
    cup_handle_bonus: float,
    relative_strength_bonus_cap: float,
    release_enabled: bool,
    release_min_score: float,
    structure_confirm_mode: str,
    weekly_duck_head_enabled: bool,
    weekly_duck_head_min_weeks: int,
    weekly_duck_head_ma_short: int,
    weekly_duck_head_ma_mid: int,
    weekly_duck_head_ma_long: int,
    weekly_duck_head_pullback_weeks: int,
    weekly_duck_head_breakout_lookback_weeks: int,
    weekly_duck_head_overextend_pct: float,
    fundamentals_loader: Callable[[Any, list[str], date], dict[str, dict[str, Any]]],
    check_fundamentals: Callable[[dict[str, Any]], tuple[bool, float, list[str]]],
    weekly_series_loader: Callable[[str, date], dict[str, Any]],
    cup_handle_loader: Callable[[date], set[str]],
    ensure_no_lookahead_guard: Callable[[list[tuple[Any, ...]], date, int, str], None],
    market_focus_snapshot_loader: Callable[[str, date], dict[str, Any]],
    stock_candidate_factory: Callable[..., Any],
) -> list[Any]:
    top_rows = load_sector_top_rows(
        cursor,
        sector=sector,
        target_date=target_date,
        market_cap_min=market_cap_min,
        market_cap_max=market_cap_max,
    )
    if not top_rows:
        return []

    top_codes = [
        str(code or "").strip()
        for code, _name, _mkt_cap, _close, _pct_chg, _amount, _volume in top_rows
        if str(code or "").strip()
    ]
    fundamentals_by_code = fundamentals_loader(cursor, top_codes, target_date)
    history_by_code, wave_phase_by_code = load_history_views_for_codes(
        cursor,
        codes=top_codes,
        target_date=target_date,
        ensure_no_lookahead_guard=ensure_no_lookahead_guard,
    )

    cup_picks = cup_handle_loader(target_date) if bool(cup_handle_enabled) else set()
    weekly_view_cache: dict[str, dict[str, Any]] = {}

    def _weekly_view(code: str) -> dict[str, Any]:
        code_s = str(code or "").strip()
        cached = weekly_view_cache.get(code_s)
        if cached is not None:
            return cached
        view = dict(weekly_series_loader(code_s, target_date) or {})
        weekly_view_cache[code_s] = view
        return view

    staged: list[dict[str, Any]] = []
    for code, name, mkt_cap, close, pct_chg, _amount, _volume in top_rows:
        reasons: list[str] = []
        base_score = 0.0
        code_s = str(code or "").strip()
        stock_name = str(name or "")
        cup_ok = code_s in cup_picks
        soft_flags: list[str] = []
        mkt_cap_value = float(mkt_cap or 0.0)
        mkt_cap_min = float(market_cap_min)
        mkt_cap_max = float(market_cap_max)
        if mkt_cap_value <= 0:
            soft_flags.append("market_cap_missing")
            base_score -= 8.0
            reasons.append("capture-first: 市值缺失，降权保留")
        elif mkt_cap_value < mkt_cap_min:
            soft_flags.append("market_cap_low")
            base_score -= 8.0
            reasons.append(f"capture-first: 市值低于{mkt_cap_min/1e8:.0f}亿，降权保留")
        elif mkt_cap_value > mkt_cap_max:
            soft_flags.append("market_cap_high")
            base_score -= 8.0
            reasons.append(f"capture-first: 市值高于{mkt_cap_max/1e8:.0f}亿，降权保留")

        fundamentals = fundamentals_by_code.get(code_s) or {
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
            reasons.extend([f"soft:{r}" for r in fund_reasons])
        else:
            base_score += float(fund_score) * 0.3
            reasons.extend(fund_reasons)

        structure = confirm_structure(
            code=code_s,
            target_date=target_date,
            structure_confirm_mode=structure_confirm_mode,
            cup_handle_enabled=cup_handle_enabled,
            weekly_duck_head_checker=lambda checked_code, checked_date: check_weekly_duck_head(
                checked_code,
                checked_date,
                weekly_duck_head_enabled=weekly_duck_head_enabled,
                weekly_duck_head_min_weeks=weekly_duck_head_min_weeks,
                weekly_duck_head_ma_short=weekly_duck_head_ma_short,
                weekly_duck_head_ma_mid=weekly_duck_head_ma_mid,
                weekly_duck_head_ma_long=weekly_duck_head_ma_long,
                weekly_duck_head_pullback_weeks=weekly_duck_head_pullback_weeks,
                weekly_duck_head_breakout_lookback_weeks=weekly_duck_head_breakout_lookback_weeks,
                weekly_duck_head_overextend_pct=weekly_duck_head_overextend_pct,
                weekly_series_loader=lambda loader_code, _loader_date: _weekly_view(loader_code),
            ),
            cup_handle_loader=lambda _loader_date: cup_picks,
        )
        if not structure.get("passed"):
            soft_flags.append("structure_soft_fail")
            base_score -= 10.0
            reasons.append("capture-first: 结构未确认，降权保留")
            reasons.extend([f"soft:{r}" for r in list(structure.get("reasons") or [])])
        else:
            reasons.extend(list(structure.get("reasons") or []))
        pattern_evidence = list(structure.get("reasons") or [])

        if cup_ok:
            base_score += float(cup_handle_bonus)
            if "杯柄确认（cup_handle_v4）" not in reasons:
                reasons.append("杯柄确认（cup_handle_v4）")
            if "杯柄确认（cup_handle_v4）" not in pattern_evidence:
                pattern_evidence.append("杯柄确认（cup_handle_v4）")

        history = history_by_code.get(code_s) or []
        ensure_no_lookahead_guard(
            history,
            target_date,
            0,
            f"build_sector_candidates.history({code_s})",
        )

        closes = [row[1] for row in history if row[1] is not None]
        vols = [row[2] for row in history if row[2] is not None]
        if len(history) < 20 or len(closes) < 20:
            soft_flags.append("history_short")
            reasons.append("capture-first: 历史样本不足，保留但不做完整结构打分")
            base_score -= 6.0

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

        wave_phase, wave_confidence = wave_phase_by_code.get(code_s) or ("未知", 0.0)
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

        mkt_cap_yi = float(mkt_cap or 0.0) / 1e8
        if 200 <= mkt_cap_yi <= 300:
            base_score += 10
        elif 300 < mkt_cap_yi <= 350:
            base_score += 7

        weekly_ret = weekly_returns_from_series(_weekly_view(code_s))
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
                "code": code_s,
                "name": stock_name,
                "mkt_cap": mkt_cap_value,
                "close": float(close or 0.0),
                "pct_chg": float(pct_chg or 0.0),
                "fundamentals": fundamentals,
                "base_score": float(base_score),
                "reasons": reasons,
                "wave_phase": wave_phase,
                "wave_confidence": float(wave_confidence or 0.0),
                "ret_5d": float(ret_5d),
                "vol_ratio": float(vol_ratio),
                "price_position": float(price_position),
                "resonance": float(resonance),
                "strength_score": float(strength_score),
                "cup_ok": bool(cup_ok),
                "soft_flags": soft_flags,
                "pattern_evidence": pattern_evidence,
            }
        )

    if not staged:
        return []

    role_by_code, sector_avg_strength = assign_sector_roles(staged)
    candidates: list[Any] = []
    for item in staged:
        code_s = str(item["code"])
        stock_name = str(item.get("name") or "")
        role = role_by_code.get(code_s) or "跟随"
        score = float(item.get("base_score") or 0.0)
        reasons = list(item.get("reasons") or [])
        soft_flags = list(item.get("soft_flags") or [])
        rel_delta = float(item.get("strength_score") or 0.0) - float(sector_avg_strength)
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

        passed_focus, focus_reasons, focus_snapshot = passes_core_focus_gate(
            cursor,
            code=code_s,
            stock_name=stock_name,
            role=role,
            target_date=target_date,
            market_focus_snapshot_loader=market_focus_snapshot_loader,
        )
        if not passed_focus:
            soft_flags.append("focus_soft_fail")
            score -= 8.0
            reasons.append("capture-first: focus gate 未过，降权保留")
            reasons.extend([f"soft:{r}" for r in focus_reasons])
        else:
            score += float(focus_snapshot.get("focus_bonus") or 0.0)
            reasons.extend(focus_reasons)

        if role == "跟随":
            soft_flags.append("follower_soft")
            score -= 4.0
            reasons.append("capture-first: 跟随股降权保留")

        score, soft_flags, reasons = apply_strong_leader_soft_release(
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
                code=code_s,
                name=stock_name,
                sector=sector,
                market_cap_yi=round(mkt_cap_yi, 1),
                role=role,
                buy_score=float(score),
                buy_reasons=reasons,
                wave_phase=str(item.get("wave_phase") or ""),
                wave_phase_confidence=round(float(item.get("wave_confidence") or 0.0), 4),
                evidence_bundle=reasons,
                pattern_evidence=list(item.get("pattern_evidence") or []),
                ret_5d=round(float(item.get("ret_5d") or 0.0), 2),
                vol_ratio=round(float(item.get("vol_ratio") or 0.0), 2),
                price_position=round(float(item.get("price_position") or 0.0), 1),
                pe_ttm=fundamentals.get("pe_ttm", 0),
                profit_growth=fundamentals.get("profit_growth", 0),
                revenue_growth=fundamentals.get("revenue_growth", 0),
                roe=fundamentals.get("roe", 0),
                sector_resonance=round(float(item.get("resonance") or 0.0), 2),
                cup_handle_ok=bool(item.get("cup_ok") or False),
                signal_source="hot_sector",
                soft_flags=soft_flags,
            )
        )

    candidates.sort(key=_buy_score_of, reverse=True)
    return candidates[: int(top_n)]


def confirm_structure(
    code: str,
    target_date: date,
    *,
    structure_confirm_mode: str,
    cup_handle_enabled: bool,
    weekly_duck_head_checker: Callable[[str, date], dict[str, Any]],
    cup_handle_loader: Callable[[date], set[str]],
) -> dict[str, Any]:
    mode = str(structure_confirm_mode or "duck_only")
    weekly = dict(weekly_duck_head_checker(str(code), target_date) or {})
    duck_ok = bool(weekly.get("passed"))

    cup_ok = False
    if mode != "duck_only" and bool(cup_handle_enabled):
        cup_ok = str(code) in set(cup_handle_loader(target_date) or set())

    if mode == "duck_only":
        passed = duck_ok
    elif mode == "cup_only":
        passed = cup_ok
    elif mode == "duck_or_cup":
        passed = duck_ok or cup_ok
    elif mode == "duck_and_cup":
        passed = duck_ok and cup_ok
    else:
        passed = duck_ok

    reasons: list[str] = []
    if duck_ok:
        reasons.append("周线老鸭头确认（MA5/MA10/MA15）")
    if cup_ok:
        reasons.append("杯柄确认（cup_handle_v4）")

    return {
        "passed": bool(passed),
        "mode": mode,
        "duck_ok": bool(duck_ok),
        "cup_ok": bool(cup_ok),
        "weekly_reason": weekly.get("reason"),
        "reasons": reasons,
    }


def check_weekly_duck_head(
    code: str,
    target_date: date,
    *,
    weekly_duck_head_enabled: bool,
    weekly_duck_head_min_weeks: int,
    weekly_duck_head_ma_short: int,
    weekly_duck_head_ma_mid: int,
    weekly_duck_head_ma_long: int,
    weekly_duck_head_pullback_weeks: int,
    weekly_duck_head_breakout_lookback_weeks: int,
    weekly_duck_head_overextend_pct: float,
    weekly_series_loader: Callable[[str, date], dict[str, Any]],
) -> dict[str, Any]:
    if not bool(weekly_duck_head_enabled):
        return {"passed": True, "reason": "disabled"}

    view = dict(weekly_series_loader(str(code), target_date) or {})
    series = view.get("series") or []
    closes = [float(x["close"]) for x in series if isinstance(x, dict) and x.get("close") is not None]
    if len(closes) < int(weekly_duck_head_min_weeks):
        return {"passed": False, "reason": "weekly_insufficient", "weeks": len(closes)}

    t = len(closes) - 1
    ma_s = _sma_at(closes, int(weekly_duck_head_ma_short), t)
    ma_m = _sma_at(closes, int(weekly_duck_head_ma_mid), t)
    ma_l = _sma_at(closes, int(weekly_duck_head_ma_long), t)
    ma_s_prev = _sma_at(closes, int(weekly_duck_head_ma_short), t - 1)
    ma_m_prev = _sma_at(closes, int(weekly_duck_head_ma_mid), t - 1)
    if ma_s is None or ma_m is None or ma_l is None or ma_s_prev is None or ma_m_prev is None:
        return {"passed": False, "reason": "weekly_ma_unavailable"}

    close_now = float(closes[t])
    if not (ma_s > ma_m > ma_l):
        return {"passed": False, "reason": "weekly_ma_not_bull", "ma5": ma_s, "ma10": ma_m, "ma15": ma_l}

    if not (ma_s > ma_s_prev and ma_m >= ma_m_prev):
        return {
            "passed": False,
            "reason": "weekly_turn_not_confirmed",
            "ma5_slope": ma_s - ma_s_prev,
            "ma10_slope": ma_m - ma_m_prev,
        }

    pullback_weeks = int(weekly_duck_head_pullback_weeks)
    start_idx = max(0, t - pullback_weeks + 1)
    touched = False
    for idx in range(start_idx, t + 1):
        ma10_i = _sma_at(closes, int(weekly_duck_head_ma_mid), idx)
        if ma10_i is None:
            continue
        min_close = float(series[idx]["min_close"]) if idx < len(series) else float(closes[idx])
        if min_close <= float(ma10_i):
            touched = True
            break
    if not touched:
        return {"passed": False, "reason": "weekly_pullback_missing"}
    if close_now <= float(ma_m):
        return {"passed": False, "reason": "weekly_close_below_ma10", "close": close_now, "ma10": ma_m}

    lookback = int(weekly_duck_head_breakout_lookback_weeks)
    if lookback >= 1 and t - lookback >= 0:
        recent = closes[max(0, t - lookback) : t]
        if recent and close_now < float(max(recent)):
            return {"passed": False, "reason": "weekly_breakout_not_confirmed"}

    if float(ma_l) > 0:
        over = (close_now / float(ma_l) - 1.0) * 100.0
        if over > float(weekly_duck_head_overextend_pct):
            return {"passed": False, "reason": "weekly_overextended", "over_ma15_pct": over}

    return {
        "passed": True,
        "reason": "weekly_duck_head_confirmed",
        "ma5": ma_s,
        "ma10": ma_m,
        "ma15": ma_l,
    }


def load_sector_top_rows(
    cursor: Any,
    *,
    sector: str,
    target_date: date,
    market_cap_min: float,
    market_cap_max: float,
) -> list[tuple[Any, Any, Any, Any, Any, Any, Any]]:
    cursor.execute(
        """
        SELECT s.code, s.name, s.total_market_cap, dp.close, dp.pct_change, dp.amount, dp.volume
        FROM stocks s
        JOIN daily_prices dp ON s.code = dp.code
        WHERE s.sector_lv1 = ? AND dp.trade_date = ?
          AND (s.is_delisted IS NULL OR s.is_delisted = 0)
          AND dp.close > 0
        ORDER BY dp.pct_change DESC
        LIMIT 80
        """,
        (sector, target_date.isoformat()),
    )
    return list(cursor.fetchall() or [])


def load_history_views_for_codes(
    cursor: Any,
    *,
    codes: list[str],
    target_date: date,
    ensure_no_lookahead_guard: Callable[[list[tuple[Any, ...]], date, int, str], None],
) -> tuple[dict[str, list[tuple[Any, Any, Any, Any]]], dict[str, tuple[str, float]]]:
    history_by_code: dict[str, list[tuple[Any, Any, Any, Any]]] = {}
    wave_phase_by_code: dict[str, tuple[str, float]] = {}
    rows_by_code: dict[str, list[tuple[Any, Any, Any, Any]]] = {}
    if not codes:
        return history_by_code, wave_phase_by_code

    placeholders = ",".join(["?"] * len(codes))
    cursor.execute(
        f"""
        SELECT code, trade_date, close, volume, amount, high, low, rn FROM (
            SELECT code, trade_date, close, volume, amount, high, low,
                   row_number() OVER (PARTITION BY code ORDER BY trade_date DESC) as rn
            FROM daily_prices
            WHERE trade_date <= ?
              AND code IN ({placeholders})
        )
        WHERE rn <= 60
        ORDER BY code, rn
        """,
        (target_date.isoformat(), *codes),
    )
    for code, trade_date, close, volume, amount, high, low, rn in cursor.fetchall():
        code_s = str(code or "").strip()
        if not code_s:
            continue
        rows60 = rows_by_code.get(code_s)
        if rows60 is None:
            rows60 = []
            rows_by_code[code_s] = rows60
        if len(rows60) < 60:
            rows60.append((close, volume, high, low))

        if int(rn or 0) <= 30:
            history = history_by_code.get(code_s)
            if history is None:
                history = []
                history_by_code[code_s] = history
            if len(history) < 30:
                history.append((trade_date, close, volume, amount))

    for code_s, history in history_by_code.items():
        ensure_no_lookahead_guard(
            history,
            target_date,
            0,
            f"build_sector_candidates.history_batch({code_s})",
        )

    for code_s, rows60 in rows_by_code.items():
        wave_phase_by_code[code_s] = detect_sector_wave_phase(rows60)
    return history_by_code, wave_phase_by_code


def assign_sector_roles(staged: list[dict[str, Any]]) -> tuple[dict[str, str], float]:
    ranked = sorted(staged, key=lambda item: float(item.get("strength_score") or 0.0), reverse=True)
    sector_avg_strength = float(np.mean([float(item.get("strength_score") or 0.0) for item in ranked])) if ranked else 0.0
    role_by_code: dict[str, str] = {}
    for idx, item in enumerate(ranked):
        code_s = str(item["code"])
        if idx <= 1:
            role_by_code[code_s] = "龙头"
        elif idx <= 3:
            role_by_code[code_s] = "中军"
        else:
            role_by_code[code_s] = "跟随"
    return role_by_code, sector_avg_strength


def detect_sector_wave_phase(rows60: list[tuple[Any, Any, Any, Any]]) -> tuple[str, float]:
    if len(rows60) < 30:
        return "未知", 0.0
    closes60 = [row[0] for row in rows60 if row[0] is not None]
    highs60 = [row[2] for row in rows60 if row[2] is not None]
    lows60 = [row[3] for row in rows60 if row[3] is not None]
    if len(closes60) < 30 or len(highs60) < 20 or len(lows60) < 20:
        return "未知", 0.0

    recent_high = max(highs60[:20])
    recent_low = min(lows60[:20])
    prev_high = max(highs60[20:40]) if len(highs60) >= 40 else recent_high * 0.9
    current_price = closes60[0]
    base_20 = closes60[19]
    price_change_20d = (current_price - base_20) / base_20 * 100 if base_20 and base_20 > 0 else 0.0
    if current_price > prev_high * 1.02 and price_change_20d > 10:
        return "3浪", 0.8
    if current_price > prev_high * 1.05 and price_change_20d > 20:
        return "5浪", 0.7
    if current_price < recent_low * 1.05 and price_change_20d < -10:
        return "B浪", 0.6
    if price_change_20d > 5:
        return "1浪", 0.5
    return "未知", 0.3


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


def _sma_at(closes: list[float], window: int, idx: int) -> float | None:
    width = int(window)
    if width <= 0:
        return None
    if idx < width - 1:
        return None
    segment = closes[idx - width + 1 : idx + 1]
    if len(segment) != width:
        return None
    return float(np.mean(segment))
