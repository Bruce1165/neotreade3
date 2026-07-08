#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16, TradeRecord


DB_PATH = PROJECT_ROOT / "var/db/stock_data.db"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_process_research_inputs(
    *,
    base_backtest_json: Optional[Path],
    variant_backtest_json: Optional[Path],
    base_attribution_json: Optional[Path],
    variant_attribution_json: Optional[Path],
) -> dict[str, Path]:
    provided = {
        "base_backtest_json": base_backtest_json,
        "variant_backtest_json": variant_backtest_json,
        "base_attribution_json": base_attribution_json,
        "variant_attribution_json": variant_attribution_json,
    }
    missing = [
        f"--{name.replace('_', '-')}"
        for name, value in provided.items()
        if value is None
    ]
    if missing:
        raise ValueError(
            "explicit input artifacts are required for process research; "
            f"missing {', '.join(missing)}"
        )
    resolved: dict[str, Path] = {}
    for name, value in provided.items():
        path = Path(value)
        if not path.exists():
            raise FileNotFoundError(
                f"{name.replace('_', '-')} not found: {path}"
            )
        resolved[name] = path
    return resolved


def _date_from_text(value: str) -> date:
    return date.fromisoformat(str(value))


def _load_series(
    conn: sqlite3.Connection,
    *,
    code: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT trade_date, close
        FROM daily_prices
        WHERE code = ? AND trade_date BETWEEN ? AND ? AND close IS NOT NULL
        ORDER BY trade_date ASC
        """,
        (str(code), str(start_date), str(end_date)),
    ).fetchall()
    return [
        {"date": str(row[0]), "close": float(row[1])}
        for row in rows
        if row and row[0] and row[1] is not None
    ]


def _series_to_map(series: list[dict[str, Any]]) -> dict[str, float]:
    return {str(item["date"]): float(item["close"]) for item in series}


def _progress_pct(*, price: Optional[float], start_close: float, top_close: float) -> Optional[float]:
    if price is None or top_close <= start_close:
        return None
    return round((float(price) - float(start_close)) / max(float(top_close) - float(start_close), 1e-9) * 100.0, 2)


def _progress_label(progress_pct: Optional[float]) -> str:
    if progress_pct is None:
        return "unknown"
    if progress_pct < 0.0:
        return "前置布局"
    if progress_pct <= 33.0:
        return "早窗"
    if progress_pct <= 66.0:
        return "中窗"
    return "晚窗"


def _time_progress_pct(*, start_date: str, end_date: str, target_date: str) -> Optional[float]:
    try:
        start = _date_from_text(start_date)
        end = _date_from_text(end_date)
        target = _date_from_text(target_date)
    except Exception:
        return None
    total_days = (end - start).days
    if total_days <= 0:
        return None
    return round((target - start).days / max(total_days, 1) * 100.0, 2)


def _discrete_shock_count(series: list[dict[str, Any]], *, threshold_pct: float = 8.0) -> int:
    if not series:
        return 0
    peak = float(series[0]["close"])
    in_shock = False
    shocks = 0
    for item in series[1:]:
        close = float(item["close"])
        if close >= peak:
            peak = close
            in_shock = False
            continue
        drawdown_pct = (close - peak) / max(peak, 1e-9) * 100.0
        if drawdown_pct <= -abs(float(threshold_pct)) and not in_shock:
            shocks += 1
            in_shock = True
    return shocks


def _max_drawdown_pct(series: list[dict[str, Any]]) -> float:
    if not series:
        return 0.0
    peak = float(series[0]["close"])
    worst = 0.0
    for item in series:
        close = float(item["close"])
        if close > peak:
            peak = close
        dd = (close - peak) / max(peak, 1e-9) * 100.0
        if dd < worst:
            worst = dd
    return round(float(worst), 2)


def _local_extrema(
    series: list[dict[str, Any]],
    *,
    lookaround: int = 3,
    min_move_pct: float = 8.0,
) -> list[dict[str, Any]]:
    if len(series) < lookaround * 2 + 1:
        return []
    raw: list[dict[str, Any]] = []
    closes = [float(item["close"]) for item in series]
    for idx in range(lookaround, len(series) - lookaround):
        window = closes[idx - lookaround : idx + lookaround + 1]
        close = closes[idx]
        if close >= max(window):
            raw.append({"date": str(series[idx]["date"]), "close": close, "type": "peak"})
        elif close <= min(window):
            raw.append({"date": str(series[idx]["date"]), "close": close, "type": "trough"})

    compressed: list[dict[str, Any]] = []
    for item in raw:
        if not compressed:
            compressed.append(item)
            continue
        last = compressed[-1]
        if str(last["type"]) == str(item["type"]):
            if str(item["type"]) == "peak" and float(item["close"]) >= float(last["close"]):
                compressed[-1] = item
            elif str(item["type"]) == "trough" and float(item["close"]) <= float(last["close"]):
                compressed[-1] = item
            continue
        move_pct = abs((float(item["close"]) - float(last["close"])) / max(float(last["close"]), 1e-9) * 100.0)
        if move_pct >= float(min_move_pct):
            compressed.append(item)
    return compressed


def _find_first_after(
    pivots: list[dict[str, Any]],
    *,
    target_date: str,
    kind: str,
) -> Optional[dict[str, Any]]:
    for item in pivots:
        if str(item["date"]) > str(target_date) and str(item["type"]) == str(kind):
            return dict(item)
    return None


def _find_first_after_item(
    pivots: list[dict[str, Any]],
    *,
    target_item: Optional[dict[str, Any]],
    kind: str,
) -> Optional[dict[str, Any]]:
    if not isinstance(target_item, dict):
        return None
    return _find_first_after(pivots, target_date=str(target_item["date"]), kind=kind)


def _compute_process_metrics(
    *,
    series: list[dict[str, Any]],
    segment_start_date: str,
    segment_top_date: str,
) -> dict[str, Any]:
    if not series:
        return {
            "status": "missing_series",
            "shape_tags": ["数据不足"],
        }
    price_map = _series_to_map(series)
    start_close = price_map.get(str(segment_start_date))
    top_close = price_map.get(str(segment_top_date))
    if start_close is None or top_close is None:
        return {
            "status": "missing_segment_prices",
            "shape_tags": ["数据不足"],
        }

    pretop = [item for item in series if str(item["date"]) <= str(segment_top_date)]
    posttop = [item for item in series if str(item["date"]) >= str(segment_top_date)]
    pivots = _local_extrema(series, lookaround=3, min_move_pct=8.0)
    a_low = _find_first_after(pivots, target_date=str(segment_top_date), kind="trough")
    b_high = _find_first_after_item(pivots, target_item=a_low, kind="peak")
    c_low = _find_first_after_item(pivots, target_item=b_high, kind="trough")

    last20 = pretop[-20:] if len(pretop) >= 20 else pretop
    pretop_last20_return = 0.0
    if len(last20) >= 2:
        first_close = float(last20[0]["close"])
        last_close = float(last20[-1]["close"])
        pretop_last20_return = round((last_close - first_close) / max(first_close, 1e-9) * 100.0, 2)

    top_to_a_drawdown = None
    a_offset_days = None
    if isinstance(a_low, dict):
        top_to_a_drawdown = round((float(a_low["close"]) - float(top_close)) / max(float(top_close), 1e-9) * 100.0, 2)
        a_offset_days = (_date_from_text(str(a_low["date"])) - _date_from_text(str(segment_top_date))).days

    shape_tags: list[str] = []
    shock_count = _discrete_shock_count(pretop, threshold_pct=8.0)
    pretop_dd = _max_drawdown_pct(pretop)
    if shock_count <= 2 and pretop_dd >= -15.0:
        shape_tags.append("强趋势单边型")
    if shock_count >= 4 or pretop_dd <= -25.0:
        shape_tags.append("高波动换手型")
    if pretop_last20_return >= 25.0:
        shape_tags.append("后期加速见顶型")
    if top_to_a_drawdown is not None and top_to_a_drawdown <= -20.0 and (a_offset_days or 999) <= 15:
        shape_tags.append("A浪快速杀跌型")
    if not shape_tags:
        shape_tags.append("普通主升型")

    return {
        "status": "ok",
        "segment_start_close": round(float(start_close), 4),
        "segment_top_close": round(float(top_close), 4),
        "pretop_shock_count_8pct": int(shock_count),
        "pretop_max_drawdown_pct": round(float(pretop_dd), 2),
        "pretop_last20_return_pct": round(float(pretop_last20_return), 2),
        "pivots_8pct": pivots,
        "post_top_a_low": a_low,
        "post_top_b_high": b_high,
        "post_top_c_low": c_low,
        "top_to_a_drawdown_pct": top_to_a_drawdown,
        "a_days_from_top": a_offset_days,
        "shape_tags": shape_tags,
    }


def _shadow_stop_observation(
    *,
    series: list[dict[str, Any]],
    buy_price: float,
    threshold_pct: float,
) -> dict[str, Any]:
    if buy_price <= 0 or not series:
        return {
            "triggered": False,
            "first_date": "",
            "first_close": None,
            "max_return_after_hit_from_buy_pct": None,
            "rebound_from_hit_pct": None,
            "end_return_from_buy_pct": None,
        }
    threshold_price = float(buy_price) * (1.0 + float(threshold_pct) / 100.0)
    hit_idx = None
    for idx, item in enumerate(series):
        if float(item["close"]) <= float(threshold_price):
            hit_idx = idx
            break
    if hit_idx is None:
        return {
            "triggered": False,
            "first_date": "",
            "first_close": None,
            "max_return_after_hit_from_buy_pct": None,
            "rebound_from_hit_pct": None,
            "end_return_from_buy_pct": None,
        }
    hit = series[hit_idx]
    tail = series[hit_idx:]
    max_close = max(float(item["close"]) for item in tail)
    end_close = float(tail[-1]["close"])
    hit_close = float(hit["close"])
    return {
        "triggered": True,
        "first_date": str(hit["date"]),
        "first_close": round(float(hit_close), 4),
        "max_return_after_hit_from_buy_pct": round((max_close - float(buy_price)) / max(float(buy_price), 1e-9) * 100.0, 2),
        "rebound_from_hit_pct": round((max_close - hit_close) / max(hit_close, 1e-9) * 100.0, 2),
        "end_return_from_buy_pct": round((end_close - float(buy_price)) / max(float(buy_price), 1e-9) * 100.0, 2),
    }


def _warning_counts_for_trade(
    *,
    trade: dict[str, Any],
    sell_audit: list[dict[str, Any]],
) -> dict[str, Any]:
    code = str(trade.get("code") or "")
    start_date = str(trade.get("buy_date") or "")
    end_date = str(trade.get("sell_date") or "")
    window = [
        item
        for item in sell_audit
        if str(item.get("code") or "") == code
        and start_date <= str(item.get("date") or "") <= end_date
    ]
    event_counts = Counter(str(item.get("event") or "") for item in window)
    return {
        "event_counts": dict(event_counts),
        "market_warning_events": int(sum(count for name, count in event_counts.items() if str(name).startswith("market_exit_"))),
        "sector_warning_events": int(sum(count for name, count in event_counts.items() if str(name).startswith("sector_exit_"))),
    }


def _make_proxy_trade(
    *,
    code: str,
    name: str,
    sector: str,
    segment_start_date: str,
    start_close: float,
) -> TradeRecord:
    return TradeRecord(
        code=str(code),
        name=str(name),
        sector=str(sector),
        buy_date=str(segment_start_date),
        buy_price=float(start_close),
        buy_price_ref=float(start_close),
        shares=100,
        status="open",
    )


def _load_window_dates(
    conn: sqlite3.Connection,
    *,
    center_date: str,
    before_days: int = 10,
    after_days: int = 10,
) -> list[str]:
    center = _date_from_text(center_date)
    start = (center - timedelta(days=max(30, before_days * 4))).isoformat()
    end = (center + timedelta(days=max(30, after_days * 4))).isoformat()
    dates = [
        str(row[0])
        for row in conn.execute(
            """
            SELECT DISTINCT trade_date
            FROM daily_prices
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date ASC
            """,
            (start, end),
        ).fetchall()
        if row and row[0]
    ]
    if center_date not in dates:
        return dates
    idx = dates.index(center_date)
    left = max(0, idx - before_days)
    right = min(len(dates), idx + after_days + 1)
    return dates[left:right]


def _top_context(
    *,
    conn: sqlite3.Connection,
    engine: LowFreqTradingEngineV16,
    code: str,
    name: str,
    sector: str,
    segment_start_date: str,
    start_close: float,
    top_date: str,
) -> dict[str, Any]:
    trade = _make_proxy_trade(
        code=str(code),
        name=str(name),
        sector=str(sector),
        segment_start_date=str(segment_start_date),
        start_close=float(start_close),
    )
    dates = _load_window_dates(conn, center_date=str(top_date), before_days=10, after_days=10)
    top_market = engine._market_exit_snapshot(trade, _date_from_text(top_date))
    top_sector = engine._sector_exit_snapshot(trade, _date_from_text(top_date))
    first_market_candidate_date = ""
    first_market_pass_date = ""
    first_sector_candidate_date = ""
    first_sector_pass_date = ""
    for d_key in dates:
        current = _date_from_text(d_key)
        market_snapshot = engine._market_exit_snapshot(trade, current)
        sector_snapshot = engine._sector_exit_snapshot(trade, current)
        if not first_market_candidate_date and isinstance(market_snapshot, dict):
            first_market_candidate_date = d_key
        if not first_market_pass_date and isinstance(market_snapshot, dict) and bool(market_snapshot.get("condition_pass")):
            first_market_pass_date = d_key
        if not first_sector_candidate_date and isinstance(sector_snapshot, dict):
            first_sector_candidate_date = d_key
        if not first_sector_pass_date and isinstance(sector_snapshot, dict) and bool(sector_snapshot.get("condition_pass")):
            first_sector_pass_date = d_key
    def _offset(value: str) -> Optional[int]:
        if not value:
            return None
        return (_date_from_text(value) - _date_from_text(top_date)).days

    return {
        "top_day_market_snapshot": top_market,
        "top_day_sector_snapshot": top_sector,
        "first_market_candidate_date": first_market_candidate_date,
        "first_market_candidate_offset_days": _offset(first_market_candidate_date),
        "first_market_pass_date": first_market_pass_date,
        "first_market_pass_offset_days": _offset(first_market_pass_date),
        "first_sector_candidate_date": first_sector_candidate_date,
        "first_sector_candidate_offset_days": _offset(first_sector_candidate_date),
        "first_sector_pass_date": first_sector_pass_date,
        "first_sector_pass_offset_days": _offset(first_sector_pass_date),
    }


def _enrich_shape_tags(base_tags: list[str], *, context: dict[str, Any]) -> list[str]:
    tags = list(base_tags)
    sector_offset = context.get("first_sector_pass_offset_days")
    market_offset = context.get("first_market_pass_offset_days")
    if isinstance(sector_offset, int) and abs(sector_offset) <= 5:
        tags.append("板块共振型")
    if isinstance(sector_offset, int) and sector_offset < -5 and (market_offset is None or market_offset > sector_offset + 5):
        tags.append("龙头脱队型")
    deduped: list[str] = []
    seen = set()
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        deduped.append(tag)
    return deduped


def _select_deep_dive_codes(
    *,
    base_items: list[dict[str, Any]],
    variant_items: list[dict[str, Any]],
) -> list[str]:
    base_map = {str(item["code"]): item for item in base_items}
    variant_map = {str(item["code"]): item for item in variant_items}
    codes: list[str] = []
    for code in sorted(set(base_map) | set(variant_map)):
        base_item = base_map.get(code)
        variant_item = variant_map.get(code)
        base_bought = bool(base_item and base_item.get("bought"))
        variant_bought = bool(variant_item and variant_item.get("bought"))
        changed = (
            bool(base_item and variant_item)
            and (
                bool(base_item.get("bought")) != bool(variant_item.get("bought"))
                or str(base_item.get("reason_bucket") or "") != str(variant_item.get("reason_bucket") or "")
            )
        )
        if base_bought or variant_bought or changed:
            codes.append(code)
    return codes


def _variant_trade_entries(
    *,
    row: dict[str, Any],
    payload_summary: dict[str, Any],
    full_series: list[dict[str, Any]],
    year_end: str,
    top_date: str,
) -> list[dict[str, Any]]:
    trades = list(row.get("relevant_trades") or [])
    sell_audit = list(payload_summary.get("sell_signal_audit") or [])
    price_map = _series_to_map(full_series)
    out: list[dict[str, Any]] = []
    for trade in trades:
        buy_price = float(trade.get("buy_price_ref") or trade.get("buy_price") or 0.0)
        trade_series = [
            item
            for item in full_series
            if str(item["date"]) >= str(trade.get("buy_date") or "") and str(item["date"]) <= str(year_end)
        ]
        post_exit_series = [
            item
            for item in full_series
            if str(item["date"]) >= str(trade.get("sell_date") or "") and str(item["date"]) <= str(top_date)
        ]
        stop5 = _shadow_stop_observation(series=trade_series, buy_price=buy_price, threshold_pct=-5.0)
        stop6 = _shadow_stop_observation(series=trade_series, buy_price=buy_price, threshold_pct=-6.0)
        warning_summary = _warning_counts_for_trade(trade=trade, sell_audit=sell_audit)
        buy_date = str(trade.get("buy_date") or "")
        buy_close = price_map.get(buy_date)
        sell_date = str(trade.get("sell_date") or "")
        sell_close = price_map.get(sell_date) if sell_date else None
        post_exit_peak = None
        post_exit_peak_date = ""
        remaining_upside = None
        if post_exit_series and sell_close is not None and float(sell_close) > 0:
            best = max(post_exit_series, key=lambda x: float(x["close"]))
            post_exit_peak = float(best["close"])
            post_exit_peak_date = str(best["date"])
            remaining_upside = round((float(post_exit_peak) - float(sell_close)) / max(float(sell_close), 1e-9) * 100.0, 2)
        out.append(
            {
                "buy_date": buy_date,
                "sell_date": sell_date,
                "return_pct": float(trade.get("return_pct") or 0.0),
                "hold_days": int(trade.get("hold_days") or 0),
                "sell_reason": str(trade.get("sell_reason") or ""),
                "buy_price_ref": round(float(buy_price), 4) if buy_price > 0 else None,
                "buy_price_progress_pct": None,
                "buy_price_progress_label": "",
                "warning_summary": warning_summary,
                "shadow_stop_5": stop5,
                "shadow_stop_6": stop6,
                "buy_close": round(float(buy_close), 4) if buy_close is not None else None,
                "sell_close": round(float(sell_close), 4) if sell_close is not None else None,
                "post_exit_peak_close": round(float(post_exit_peak), 4) if post_exit_peak is not None else None,
                "post_exit_peak_date": post_exit_peak_date,
                "post_exit_remaining_upside_pct": remaining_upside,
            }
        )
    return out


def _attach_trade_progress(
    *,
    trade_entries: list[dict[str, Any]],
    segment_start_close: float,
    segment_top_close: float,
) -> None:
    for item in trade_entries:
        progress = _progress_pct(
            price=item.get("buy_price_ref"),
            start_close=float(segment_start_close),
            top_close=float(segment_top_close),
        )
        item["buy_price_progress_pct"] = progress
        item["buy_price_progress_label"] = _progress_label(progress)


def _full_light_row(
    *,
    code: str,
    base_row: dict[str, Any],
    variant_row: dict[str, Any],
    process_metrics: dict[str, Any],
    series_map: dict[str, float],
) -> dict[str, Any]:
    segment_start_close = float(process_metrics.get("segment_start_close") or 0.0)
    segment_top_close = float(process_metrics.get("segment_top_close") or 0.0)

    def _signal_buy_view(row: dict[str, Any]) -> dict[str, Any]:
        signal_date = str(row.get("first_signal_date") or "")
        buy_date = str(row.get("first_buy_date") or "")
        signal_price = series_map.get(signal_date) if signal_date else None
        first_trade = list(row.get("relevant_trades") or [])[:1]
        first_trade_item = first_trade[0] if first_trade else {}
        buy_price = None
        if buy_date:
            buy_price = first_trade_item.get("buy_price_ref")
            if buy_price is None:
                buy_price = first_trade_item.get("buy_price")
            if buy_price is None:
                buy_price = series_map.get(buy_date)
        signal_progress = _progress_pct(price=signal_price, start_close=segment_start_close, top_close=segment_top_close)
        buy_progress = _progress_pct(price=buy_price, start_close=segment_start_close, top_close=segment_top_close)
        signal_time_progress = _time_progress_pct(
            start_date=str(row.get("segment_start_date") or ""),
            end_date=str(row.get("segment_top_date") or ""),
            target_date=signal_date,
        ) if signal_date else None
        buy_time_progress = _time_progress_pct(
            start_date=str(row.get("segment_start_date") or ""),
            end_date=str(row.get("segment_top_date") or ""),
            target_date=buy_date,
        ) if buy_date else None
        return {
            "picked": bool(row.get("picked")),
            "bought": bool(row.get("bought")),
            "held_to_top": bool(row.get("held_to_top")),
            "first_signal_date": signal_date,
            "first_buy_date": buy_date,
            "first_sell_date": str(row.get("first_sell_date") or ""),
            "signal_progress_pct": signal_progress,
            "signal_progress_label": _progress_label(signal_progress),
            "signal_time_progress_pct": signal_time_progress,
            "buy_progress_pct": buy_progress,
            "buy_progress_label": _progress_label(buy_progress),
            "buy_time_progress_pct": buy_time_progress,
            "reason_bucket": str(row.get("reason_bucket") or ""),
            "primary_reason": str(row.get("primary_reason") or ""),
        }

    return {
        "code": str(code),
        "name": str(base_row.get("name") or variant_row.get("name") or ""),
        "sector": str(base_row.get("sector") or variant_row.get("sector") or ""),
        "rank": int(base_row.get("rank") or variant_row.get("rank") or 0),
        "annual_return_pct": float(base_row.get("annual_return_pct") or variant_row.get("annual_return_pct") or 0.0),
        "segment_start_date": str(base_row.get("segment_start_date") or variant_row.get("segment_start_date") or ""),
        "segment_top_date": str(base_row.get("segment_top_date") or variant_row.get("segment_top_date") or ""),
        "segment_return_pct": float(base_row.get("segment_return_pct") or variant_row.get("segment_return_pct") or 0.0),
        "process_metrics": process_metrics,
        "base": _signal_buy_view(base_row),
        "variant": _signal_buy_view(variant_row),
        "reason_bucket_changed": str(base_row.get("reason_bucket") or "") != str(variant_row.get("reason_bucket") or ""),
        "buy_status_changed": bool(base_row.get("bought")) != bool(variant_row.get("bought")),
    }


def _write_markdown(
    *,
    output_path: Path,
    summary: dict[str, Any],
    deep_dive: list[dict[str, Any]],
) -> None:
    lines: list[str] = []
    lines.append("# Top200 全过程研究报告")
    lines.append("")
    lines.append("## 核心结论")
    lines.append("")
    for bullet in list(summary.get("key_findings") or []):
        lines.append(f"- {bullet}")
    lines.append("")
    lines.append("## 统计摘要")
    lines.append("")
    lines.append(f"- Top200 总数：{summary.get('top200_count', 0)}")
    lines.append(f"- 基线实际买入：{summary.get('base_bought_count', 0)}")
    lines.append(f"- 新版实际买入：{summary.get('variant_bought_count', 0)}")
    lines.append(f"- 已买样本深挖数量：{summary.get('deep_dive_count', 0)}")
    lines.append(f"- 基线晚窗买入占比：{summary.get('base_late_buy_ratio_pct', 0)}%")
    lines.append(f"- 新版晚窗买入占比：{summary.get('variant_late_buy_ratio_pct', 0)}%")
    lines.append(f"- 基线 `-6%` 影子触发占比：{summary.get('base_shadow_stop6_ratio_pct', 0)}%")
    lines.append(f"- 新版 `-6%` 影子触发占比：{summary.get('variant_shadow_stop6_ratio_pct', 0)}%")
    lines.append("")
    lines.append("## 信号与买点位置")
    lines.append("")
    for label, count in list(summary.get("base_signal_progress_label_counts") or []):
        lines.append(f"- 首次信号位置 {label}: {count}")
    for label, count in list(summary.get("base_buy_progress_label_counts") or []):
        lines.append(f"- 基线实际买点位置 {label}: {count}")
    for label, count in list(summary.get("variant_buy_progress_label_counts") or []):
        lines.append(f"- 新版实际买点位置 {label}: {count}")
    lines.append("")
    lines.append("## 形态统计")
    lines.append("")
    for tag, count in list(summary.get("shape_tag_counts") or []):
        lines.append(f"- {tag}: {count}")
    lines.append("")
    if list(summary.get("candidate_rules") or []):
        lines.append("## 规则候选")
        lines.append("")
        for item in list(summary.get("candidate_rules") or []):
            lines.append(f"- {item['title']}：{item['proposal']} | 证据：{item['evidence']}")
        lines.append("")
    if list(summary.get("changed_samples") or []):
        lines.append("## 版本差异样本")
        lines.append("")
        for item in list(summary.get("changed_samples") or []):
            lines.append(
                f"- {item['code']} {item['name']} | 基线：{item['base_reason_bucket']} | 新版：{item['variant_reason_bucket']} | "
                f"原因变化：{item['base_primary_reason']} -> {item['variant_primary_reason']}"
            )
        lines.append("")
    lines.append("## 重点样本")
    lines.append("")
    for item in deep_dive:
        lines.append(
            f"- {item['code']} {item['name']} | 排名 {item['rank']} | 形态 {','.join(item.get('shape_tags') or [])} | "
            f"基线买入={item['base']['bought']} | 新版买入={item['variant']['bought']} | "
            f"顶点 {item['segment_top_date']}"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Top200 全过程研究报告")
    parser.add_argument(
        "--base-backtest-json",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--variant-backtest-json",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--base-attribution-json",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--variant-attribution-json",
        type=Path,
        default=None,
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--report-id", type=str, default="")
    args = parser.parse_args()
    try:
        resolved_inputs = _resolve_process_research_inputs(
            base_backtest_json=args.base_backtest_json,
            variant_backtest_json=args.variant_backtest_json,
            base_attribution_json=args.base_attribution_json,
            variant_attribution_json=args.variant_attribution_json,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    report_id = str(args.report_id or f"top200_process_research_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    output_dir = PROJECT_ROOT / "var/artifacts/lowfreq_top200_process_research" / report_id
    output_dir.mkdir(parents=True, exist_ok=True)

    base_payload = _load_json(resolved_inputs["base_backtest_json"])
    variant_payload = _load_json(resolved_inputs["variant_backtest_json"])
    base_attr = _load_json(resolved_inputs["base_attribution_json"])
    variant_attr = _load_json(resolved_inputs["variant_attribution_json"])
    base_items = list(base_attr.get("items") or [])
    variant_items = list(variant_attr.get("items") or [])
    base_map = {str(item["code"]): dict(item) for item in base_items}
    variant_map = {str(item["code"]): dict(item) for item in variant_items}
    year_end = f"{int(args.year)}-12-31"

    full_light_rows: list[dict[str, Any]] = []
    deep_dive_rows: list[dict[str, Any]] = []
    deep_codes = _select_deep_dive_codes(base_items=base_items, variant_items=variant_items)

    conn = sqlite3.connect(str(DB_PATH))
    engine = LowFreqTradingEngineV16()
    try:
        for code in sorted(set(base_map) | set(variant_map)):
            base_row = base_map.get(code)
            variant_row = variant_map.get(code)
            if not isinstance(base_row, dict) or not isinstance(variant_row, dict):
                continue
            start_date = str(base_row.get("segment_start_date") or variant_row.get("segment_start_date") or "")
            top_date = str(base_row.get("segment_top_date") or variant_row.get("segment_top_date") or "")
            if not start_date or not top_date:
                continue
            series = _load_series(conn, code=str(code), start_date=start_date, end_date=year_end)
            process_metrics = _compute_process_metrics(series=series, segment_start_date=start_date, segment_top_date=top_date)
            row = _full_light_row(
                code=str(code),
                base_row=base_row,
                variant_row=variant_row,
                process_metrics=process_metrics,
                series_map=_series_to_map(series),
            )
            full_light_rows.append(row)

            if str(code) not in set(deep_codes):
                continue
            context = _top_context(
                conn=conn,
                engine=engine,
                code=str(code),
                name=str(row["name"]),
                sector=str(row["sector"]),
                segment_start_date=str(start_date),
                start_close=float(process_metrics.get("segment_start_close") or 0.0),
                top_date=str(top_date),
            )
            shape_tags = _enrich_shape_tags(list(process_metrics.get("shape_tags") or []), context=context)
            base_trade_entries = _variant_trade_entries(
                row=base_row,
                payload_summary=base_payload.get("summary") or {},
                full_series=series,
                year_end=year_end,
                top_date=str(top_date),
            )
            variant_trade_entries = _variant_trade_entries(
                row=variant_row,
                payload_summary=variant_payload.get("summary") or {},
                full_series=series,
                year_end=year_end,
                top_date=str(top_date),
            )
            _attach_trade_progress(
                trade_entries=base_trade_entries,
                segment_start_close=float(process_metrics.get("segment_start_close") or 0.0),
                segment_top_close=float(process_metrics.get("segment_top_close") or 0.0),
            )
            _attach_trade_progress(
                trade_entries=variant_trade_entries,
                segment_start_close=float(process_metrics.get("segment_start_close") or 0.0),
                segment_top_close=float(process_metrics.get("segment_top_close") or 0.0),
            )
            deep_dive_rows.append(
                {
                    "code": str(code),
                    "name": str(row["name"]),
                    "sector": str(row["sector"]),
                    "rank": int(row["rank"]),
                    "annual_return_pct": float(row["annual_return_pct"]),
                    "segment_start_date": str(start_date),
                    "segment_top_date": str(top_date),
                    "shape_tags": shape_tags,
                    "process_metrics": process_metrics,
                    "top_context": context,
                    "base": {
                        "picked": bool(base_row.get("picked")),
                        "bought": bool(base_row.get("bought")),
                        "held_to_top": bool(base_row.get("held_to_top")),
                        "first_signal_date": str(base_row.get("first_signal_date") or ""),
                        "first_buy_date": str(base_row.get("first_buy_date") or ""),
                        "first_sell_date": str(base_row.get("first_sell_date") or ""),
                        "reason_bucket": str(base_row.get("reason_bucket") or ""),
                        "primary_reason": str(base_row.get("primary_reason") or ""),
                        "trades": base_trade_entries,
                    },
                    "variant": {
                        "picked": bool(variant_row.get("picked")),
                        "bought": bool(variant_row.get("bought")),
                        "held_to_top": bool(variant_row.get("held_to_top")),
                        "first_signal_date": str(variant_row.get("first_signal_date") or ""),
                        "first_buy_date": str(variant_row.get("first_buy_date") or ""),
                        "first_sell_date": str(variant_row.get("first_sell_date") or ""),
                        "reason_bucket": str(variant_row.get("reason_bucket") or ""),
                        "primary_reason": str(variant_row.get("primary_reason") or ""),
                        "trades": variant_trade_entries,
                    },
                }
            )
    finally:
        conn.close()

    def _late_buy_ratio(rows: list[dict[str, Any]], *, version: str) -> float:
        bought = [item for item in rows if bool(item[version]["bought"])]
        if not bought:
            return 0.0
        late = [item for item in bought if str(item[version].get("buy_progress_label") or "") == "晚窗"]
        return round(len(late) / max(len(bought), 1) * 100.0, 2)

    def _shadow_stop_ratio(deep_rows: list[dict[str, Any]], *, version: str) -> float:
        trades = [trade for item in deep_rows for trade in list(item[version].get("trades") or [])]
        if not trades:
            return 0.0
        hit = [trade for trade in trades if bool((trade.get("shadow_stop_6") or {}).get("triggered"))]
        return round(len(hit) / max(len(trades), 1) * 100.0, 2)

    def _shape_counts(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
        counter = Counter()
        for item in rows:
            for tag in list(item.get("shape_tags") or []):
                counter[str(tag)] += 1
        return counter.most_common()

    def _label_counts(rows: list[dict[str, Any]], *, version: str, key: str, only_truthy: bool = False) -> list[tuple[str, int]]:
        counter = Counter()
        for item in rows:
            if only_truthy and not bool(item[version].get("picked")) and "signal" in key:
                continue
            if only_truthy and not bool(item[version].get("bought")) and "buy_" in key:
                continue
            value = str(item[version].get(key) or "")
            if value:
                counter[value] += 1
        return counter.most_common()

    def _changed_samples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in rows:
            if not item.get("reason_bucket_changed") and not item.get("buy_status_changed"):
                continue
            out.append(
                {
                    "code": str(item["code"]),
                    "name": str(item["name"]),
                    "rank": int(item["rank"]),
                    "base_reason_bucket": str(item["base"]["reason_bucket"]),
                    "variant_reason_bucket": str(item["variant"]["reason_bucket"]),
                    "base_primary_reason": str(item["base"]["primary_reason"]),
                    "variant_primary_reason": str(item["variant"]["primary_reason"]),
                }
            )
        return out

    def _candidate_rules(deep_rows: list[dict[str, Any]], changed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        early_system_exit_cases: list[str] = []
        profitable_reentry_cases: list[str] = []
        for item in deep_rows:
            for version in ["base", "variant"]:
                for trade in list(item[version].get("trades") or []):
                    sell_reason = str(trade.get("sell_reason") or "")
                    buy_label = str(trade.get("buy_price_progress_label") or "")
                    remaining = trade.get("post_exit_remaining_upside_pct")
                    ret = float(trade.get("return_pct") or 0.0)
                    if buy_label in {"早窗", "前置布局"} and remaining is not None and float(remaining) >= 100.0 and "见顶确认" in sell_reason:
                        early_system_exit_cases.append(
                            f"{item['code']} {item['name']} {sell_reason} 后仍有 {float(remaining):.2f}% 空间"
                        )
                    if ret >= 100.0 and remaining is not None and float(remaining) >= 20.0:
                        profitable_reentry_cases.append(
                            f"{item['code']} {item['name']} 首段收益 {ret:.2f}% 后仍有 {float(remaining):.2f}% 空间"
                        )
        early_system_exit_cases = list(dict.fromkeys(early_system_exit_cases))
        profitable_reentry_cases = list(dict.fromkeys(profitable_reentry_cases))
        if early_system_exit_cases:
            rules.append(
                {
                    "title": "早窗龙头系统性退出降级",
                    "proposal": "对早窗/前置布局的龙头股，不因单一市场或板块确认直接清仓，优先降级为观察或减仓，需叠加个股失真证据再退出",
                    "evidence": "；".join(early_system_exit_cases[:3]),
                }
            )
        if profitable_reentry_cases:
            rules.append(
                {
                    "title": "主升段再介入机制",
                    "proposal": "对已取得大额利润但系统性退出后仍保持主升结构的龙头，允许趋势修复后二次上车，而不是视为一次性交易结束",
                    "evidence": "；".join(profitable_reentry_cases[:3]),
                }
            )
        if changed_rows:
            rules.append(
                {
                    "title": "高置信早窗容量保护",
                    "proposal": "对极早窗且高置信的龙头信号引入容量优先级保护，避免被同期普通占仓样本挤掉",
                    "evidence": "；".join(
                        f"{item['code']} {item['name']} 从 {item['base_reason_bucket']} 变为 {item['variant_reason_bucket']}"
                        for item in changed_rows[:3]
                    ),
                }
            )
        return rules

    def _key_findings() -> list[str]:
        findings: list[str] = []
        findings.append(
            f"两版 Top200 轻底稿已覆盖 {len(full_light_rows)} 只样本，深挖样本 {len(deep_dive_rows)} 只。"
        )
        findings.append(
            f"Top200 实际买入从基线 {int(base_attr.get('aggregate', {}).get('bought_count', 0))} 只变为新版 {int(variant_attr.get('aggregate', {}).get('bought_count', 0))} 只。"
        )
        base_late = _late_buy_ratio(full_light_rows, version="base")
        variant_late = _late_buy_ratio(full_light_rows, version="variant")
        findings.append(f"按主升段价格进度代理，基线晚窗买入占比 {base_late}%，新版晚窗买入占比 {variant_late}%。")
        signal_counts = dict(_label_counts(full_light_rows, version="base", key="signal_progress_label", only_truthy=True))
        findings.append(
            f"Top200 首次正式信号主要出现在早窗：早窗 {int(signal_counts.get('早窗', 0))}、中窗 {int(signal_counts.get('中窗', 0))}、晚窗 {int(signal_counts.get('晚窗', 0))}。"
        )
        findings.append(
            f"深挖样本中，基线 `-6%` 影子触发占比 {_shadow_stop_ratio(deep_dive_rows, version='base')}%，新版为 {_shadow_stop_ratio(deep_dive_rows, version='variant')}%。"
        )
        changed = _changed_samples(full_light_rows)
        if changed:
            findings.append(
                "版本差异样本很少，本轮仅发现 "
                + "、".join(f"{item['code']} {item['name']}" for item in changed[:3])
                + " 出现 Top200 归因变化。"
            )
        shape_pairs = _shape_counts(deep_dive_rows)[:3]
        if shape_pairs:
            findings.append(
                "深挖样本最常见形态为：" + "、".join(f"{name}({count})" for name, count in shape_pairs) + "。"
            )
        return findings

    summary = {
        "top200_count": len(full_light_rows),
        "base_bought_count": int(base_attr.get("aggregate", {}).get("bought_count", 0)),
        "variant_bought_count": int(variant_attr.get("aggregate", {}).get("bought_count", 0)),
        "deep_dive_count": len(deep_dive_rows),
        "base_late_buy_ratio_pct": _late_buy_ratio(full_light_rows, version="base"),
        "variant_late_buy_ratio_pct": _late_buy_ratio(full_light_rows, version="variant"),
        "base_shadow_stop6_ratio_pct": _shadow_stop_ratio(deep_dive_rows, version="base"),
        "variant_shadow_stop6_ratio_pct": _shadow_stop_ratio(deep_dive_rows, version="variant"),
        "base_signal_progress_label_counts": _label_counts(full_light_rows, version="base", key="signal_progress_label", only_truthy=True),
        "base_buy_progress_label_counts": _label_counts(full_light_rows, version="base", key="buy_progress_label", only_truthy=True),
        "variant_buy_progress_label_counts": _label_counts(full_light_rows, version="variant", key="buy_progress_label", only_truthy=True),
        "shape_tag_counts": _shape_counts(deep_dive_rows),
        "changed_samples": _changed_samples(full_light_rows),
        "candidate_rules": _candidate_rules(deep_dive_rows, _changed_samples(full_light_rows)),
        "key_findings": _key_findings(),
    }

    summary_path = output_dir / "summary.json"
    light_path = output_dir / "full_top200_lightview.json"
    deep_path = output_dir / "deep_dive_dossiers.json"
    report_path = output_dir / "report.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    light_path.write_text(json.dumps(full_light_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    deep_path.write_text(json.dumps(deep_dive_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_markdown(output_path=report_path, summary=summary, deep_dive=deep_dive_rows)

    print(
        json.dumps(
            {
                "status": "ok",
                "report_id": report_id,
                "output_dir": str(output_dir),
                "summary_path": str(summary_path),
                "light_path": str(light_path),
                "deep_path": str(deep_path),
                "report_path": str(report_path),
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
