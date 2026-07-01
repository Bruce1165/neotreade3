"""Screener runtime functions for NeoTrade3 bootstrap."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, cast


def run_placeholder(
    *, screener_id: str, target_date: date, parameters: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "screener_id": screener_id,
        "target_date": target_date.isoformat(),
        "status": "pending_implementation",
        "parameters": parameters or {},
        "picks": [],
        "decision_trace": [],
    }


def run_daily_hot_cold(
    *, screener_id: str, target_date: date, parameters: dict[str, Any] | None = None
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]
    db_path = Path(
        os.environ.get("NEOTRADE3_STOCK_DB_PATH")
        or project_root / "var/db/stock_data.db"
    ).expanduser()
    params = parameters or {}
    raw_trace_code = params.get("trace_code")
    trace_code = str(raw_trace_code or "").strip().split(".", 1)[0]
    universe_filters = params.get("universe_filters")
    min_market_cap = None
    max_market_cap = None
    if isinstance(universe_filters, dict):
        raw_min_market_cap = universe_filters.get("min_market_cap")
        if raw_min_market_cap is not None:
            try:
                min_market_cap = float(raw_min_market_cap)
            except (TypeError, ValueError):
                min_market_cap = None
        raw_max_market_cap = universe_filters.get("max_market_cap")
        if raw_max_market_cap is not None:
            try:
                max_market_cap = float(raw_max_market_cap)
            except (TypeError, ValueError):
                max_market_cap = None

    use_market_cap_filter = (min_market_cap is not None) or (max_market_cap is not None)

    raw_top_n = params.get("top_n", 50)
    try:
        top_n = int(raw_top_n)
    except (TypeError, ValueError):
        top_n = 50
    if top_n <= 0:
        top_n = 50

    def _get_float(key: str, default: float) -> float:
        raw = params.get(key, default)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    min_amount_yi = _get_float("min_amount_yi", 0.0)
    if min_amount_yi < 0:
        min_amount_yi = 0.0
    min_amount_yuan = min_amount_yi * 100_000_000.0
    hot_pct_threshold = _get_float("hot_pct_threshold", 5.0)
    cold_pct_threshold = _get_float("cold_pct_threshold", -5.0)

    decision_trace: list[dict[str, Any]] = []
    trace_target: list[dict[str, Any]] = []
    if not db_path.exists() or not db_path.is_file():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "stock db not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "open_db",
                    "status": "failed",
                    "reason": "db_path missing",
                }
            ],
        }

    try:
        conn = sqlite3.connect(str(db_path))
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "failed to open sqlite db",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "open_db", "status": "failed", "reason": str(exc)}
            ],
        }

    try:
        cursor = conn.cursor()
        query_attempts: list[tuple[str, bool, bool]] = [
            (
                "SELECT dp.code, COALESCE(s.name,''), dp.pct_change, dp.amount, s.circulating_market_cap "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date = ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0 "
                "AND dp.amount IS NOT NULL "
                "ORDER BY dp.amount DESC "
                "LIMIT 3000",
                True,
                True,
            ),
            (
                "SELECT dp.code, COALESCE(s.name,''), dp.pct_change, dp.amount, NULL "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date = ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0 "
                "AND dp.amount IS NOT NULL "
                "ORDER BY dp.amount DESC "
                "LIMIT 3000",
                False,
                True,
            ),
            (
                "SELECT dp.code, COALESCE(s.name,''), NULL, dp.amount, s.circulating_market_cap "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date = ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0 "
                "AND dp.amount IS NOT NULL "
                "ORDER BY dp.amount DESC "
                "LIMIT 3000",
                True,
                False,
            ),
        ]
        rows: list[tuple[object, object, object, object, object]] = []
        has_market_cap = False
        has_pct_change = False
        last_exc: Exception | None = None
        for sql, attempt_has_market_cap, attempt_has_pct_change in query_attempts:
            try:
                cursor.execute(sql, (target_date.isoformat(),))
                rows = cursor.fetchall()
                has_market_cap = attempt_has_market_cap
                has_pct_change = attempt_has_pct_change
                break
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None and not rows:
            raise last_exc
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "query failed",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "query", "status": "failed", "reason": str(exc)}
            ],
        }
    finally:
        conn.close()

    decision_trace.append(
        {
            "step": "query",
            "status": "ok",
            "row_count": len(rows),
            "has_market_cap": has_market_cap,
            "has_pct_change": has_pct_change,
        }
    )
    if use_market_cap_filter and not has_market_cap:
        decision_trace.append(
            {
                "step": "validate_schema",
                "status": "failed",
                "reason": "market_cap column unavailable; cannot apply market_cap filters",
                "min_market_cap_yuan": min_market_cap,
                "max_market_cap_yuan": max_market_cap,
            }
        )
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "market cap unavailable; cannot apply market_cap filters",
            "parameters": params,
            "picks": [],
            "decision_trace": decision_trace,
        }

    excluded_prefixes = ("399", "43", "83", "87", "88")
    rejected_examples: list[dict[str, Any]] = []
    passed: list[dict[str, Any]] = []
    reject_count = 0
    for code, name, pct_change, amount, market_cap in rows:
        code_str = str(code)
        name_str = str(name or "")
        if code_str.startswith(excluded_prefixes) or any(
            token in name_str for token in ("*ST", "ST", "PT")
        ):
            reject_count += 1
            if trace_code and code_str == trace_code:
                trace_target.append(
                    {"step": "base_exclusion", "ok": False, "code": code_str, "name": name_str}
                )
            if len(rejected_examples) < 5:
                rejected_examples.append(
                    {"code": code_str, "reason": "base_exclusion", "name": name_str}
                )
            continue

        try:
            pct_f = (
                float(cast(Any, pct_change))
                if has_pct_change and pct_change is not None
                else None
            )
        except (TypeError, ValueError):
            pct_f = None

        try:
            amount_f = float(cast(Any, amount))
        except (TypeError, ValueError):
            reject_count += 1
            if trace_code and code_str == trace_code:
                trace_target.append(
                    {"step": "amount", "ok": False, "code": code_str, "value": amount, "reason": "invalid_amount"}
                )
            if len(rejected_examples) < 5:
                rejected_examples.append(
                    {"code": code_str, "reason": "invalid_amount", "value": amount}
                )
            continue

        cap_f: float | None = None
        if use_market_cap_filter:
            if market_cap is None:
                reject_count += 1
                if trace_code and code_str == trace_code:
                    trace_target.append(
                        {
                            "step": "market_cap",
                            "ok": False,
                            "code": code_str,
                            "reason": "missing_market_cap",
                            "min_market_cap_yuan": min_market_cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                if len(rejected_examples) < 5:
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "missing_market_cap",
                            "min_market_cap_yuan": min_market_cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue
            try:
                cap_f = float(cast(Any, market_cap))
            except (TypeError, ValueError):
                reject_count += 1
                if trace_code and code_str == trace_code:
                    trace_target.append(
                        {
                            "step": "market_cap",
                            "ok": False,
                            "code": code_str,
                            "reason": "invalid_market_cap",
                            "value": market_cap,
                        }
                    )
                if len(rejected_examples) < 5:
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "invalid_market_cap",
                            "value": market_cap,
                        }
                    )
                continue
            if min_market_cap is not None and cap_f < min_market_cap:
                reject_count += 1
                if trace_code and code_str == trace_code:
                    trace_target.append(
                        {
                            "step": "market_cap",
                            "ok": False,
                            "code": code_str,
                            "reason": "market_cap_below_threshold",
                            "market_cap_yuan": cap_f,
                            "min_market_cap_yuan": min_market_cap,
                        }
                    )
                if len(rejected_examples) < 5:
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_below_threshold",
                            "market_cap_yuan": cap_f,
                            "min_market_cap_yuan": min_market_cap,
                        }
                    )
                continue
            if max_market_cap is not None and cap_f > max_market_cap:
                reject_count += 1
                if trace_code and code_str == trace_code:
                    trace_target.append(
                        {
                            "step": "market_cap",
                            "ok": False,
                            "code": code_str,
                            "reason": "market_cap_above_threshold",
                            "market_cap_yuan": cap_f,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                if len(rejected_examples) < 5:
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_above_threshold",
                            "market_cap_yuan": cap_f,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue

        passed.append(
            {
                "code": code_str,
                "name": name_str,
                "pct_change": pct_f,
                "amount_yuan": amount_f,
                "market_cap_yuan": cap_f if use_market_cap_filter else None,
            }
        )
        if trace_code and code_str == trace_code:
            trace_target.append(
                {
                    "step": "base_filters",
                    "ok": True,
                    "code": code_str,
                    "pct_change": pct_f,
                    "amount_yuan": amount_f,
                    "market_cap_yuan": cap_f if use_market_cap_filter else None,
                }
            )

    decision_trace.append(
        {
            "step": "filter",
            "status": "ok",
            "passed_count": len(passed),
            "rejected_count": reject_count,
            "min_market_cap_yuan": min_market_cap,
            "max_market_cap_yuan": max_market_cap,
            "min_amount_yi": min_amount_yi,
            "min_amount_yuan": min_amount_yuan,
            "hot_pct_threshold": hot_pct_threshold,
            "cold_pct_threshold": cold_pct_threshold,
            "rejected_examples": rejected_examples,
        }
    )

    ranked_candidates: list[dict[str, Any]] = []
    hot_candidates: list[dict[str, Any]] = []
    cold_candidates: list[dict[str, Any]] = []
    rejected_by_threshold = 0
    threshold_rejected_examples: list[dict[str, Any]] = []
    for item in passed:
        amount_yuan = float(cast(Any, item.get("amount_yuan") or 0.0))
        if amount_yuan < min_amount_yuan:
            rejected_by_threshold += 1
            if trace_code and str(item.get("code") or "") == trace_code:
                trace_target.append(
                    {
                        "step": "min_amount",
                        "ok": False,
                        "code": trace_code,
                        "amount_yuan": amount_yuan,
                        "min_amount_yuan": min_amount_yuan,
                    }
                )
            if len(threshold_rejected_examples) < 5:
                threshold_rejected_examples.append(
                    {
                        "code": str(item.get("code") or ""),
                        "reason": "amount_below_min_amount",
                        "amount_yuan": amount_yuan,
                        "min_amount_yuan": min_amount_yuan,
                    }
                )
            continue

        ranked_candidates.append(item)
        pct = (
            float(cast(Any, item.get("pct_change")))
            if has_pct_change and item.get("pct_change") is not None
            else None
        )
        if has_pct_change:
            if pct is not None and pct >= hot_pct_threshold:
                hot_candidates.append(item)
            if pct is not None and pct <= cold_pct_threshold:
                cold_candidates.append(item)
        if trace_code and str(item.get("code") or "") == trace_code:
            trace_target.append(
                {
                    "step": "hot_cold_thresholds",
                    "ok": bool(has_pct_change),
                    "code": trace_code,
                    "pct_change": pct,
                    "hot_pct_threshold": hot_pct_threshold,
                    "cold_pct_threshold": cold_pct_threshold,
                    "is_hot": bool(has_pct_change and pct is not None and pct >= hot_pct_threshold),
                    "is_cold": bool(has_pct_change and pct is not None and pct <= cold_pct_threshold),
                    "has_pct_change": bool(has_pct_change),
                }
            )

    hot_candidates.sort(
        key=lambda item: float(cast(Any, item.get("amount_yuan") or 0.0)),
        reverse=True,
    )
    cold_candidates.sort(
        key=lambda item: float(cast(Any, item.get("amount_yuan") or 0.0)),
        reverse=True,
    )

    ranked_candidates.sort(
        key=lambda item: float(cast(Any, item.get("amount_yuan") or 0.0)),
        reverse=True,
    )
    picks = [item["code"] for item in ranked_candidates[:top_n]]
    hot_picks = [item["code"] for item in hot_candidates[:top_n]]
    cold_picks = [item["code"] for item in cold_candidates[:top_n]]

    if trace_code:
        amount_rank = None
        for idx, item in enumerate(ranked_candidates, start=1):
            if str(item.get("code") or "") == trace_code:
                amount_rank = idx
                break
        trace_target.append(
            {
                "step": "top_n",
                "ok": bool(trace_code in picks),
                "code": trace_code,
                "top_n": int(top_n),
                "amount_rank": amount_rank,
            }
        )

    decision_trace.append(
        {
            "step": "classify_hot_cold",
            "status": "ok" if has_pct_change else "warn",
            "top_n": top_n,
            "min_amount_yi": min_amount_yi,
            "hot_pct_threshold": hot_pct_threshold,
            "cold_pct_threshold": cold_pct_threshold,
            "hot_candidate_count": len(hot_candidates),
            "cold_candidate_count": len(cold_candidates),
            "hot_picked_count": len(hot_picks),
            "cold_picked_count": len(cold_picks),
            "hot_examples": hot_candidates[: min(5, len(hot_candidates))],
            "cold_examples": cold_candidates[: min(5, len(cold_candidates))],
            "threshold_rejected_count": rejected_by_threshold,
            "threshold_rejected_examples": threshold_rejected_examples,
            "classification_skipped": bool(not has_pct_change),
        }
    )

    message = (
        "daily_hot_cold: hot(pct_change >= hot_pct_threshold) + cold(pct_change <= cold_pct_threshold), both require amount_yuan >= min_amount_yi*1e8, after base filters."
        if has_pct_change
        else "daily_hot_cold: pct_change unavailable in DB schema; hot/cold classification skipped; picks ranked by amount_yuan after base filters."
    )
    payload = {
        "screener_id": screener_id,
        "target_date": target_date.isoformat(),
        "status": "ok",
        "message": message,
        "parameters": params,
        "picks": picks,
        "hot_picks": hot_picks,
        "cold_picks": cold_picks,
        "decision_trace": decision_trace,
    }
    if trace_code:
        payload["trace_code"] = trace_code
        payload["trace_target"] = trace_target
    return payload


def run_er_ban_hui_tiao(
    *, screener_id: str, target_date: date, parameters: dict[str, Any] | None = None
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]
    db_path = Path(
        os.environ.get("NEOTRADE3_STOCK_DB_PATH")
        or project_root / "var/db/stock_data.db"
    ).expanduser()
    params = parameters or {}
    raw_trace_code = params.get("trace_code")
    trace_code = str(raw_trace_code or "").strip().split(".", 1)[0]
    universe_filters = params.get("universe_filters")
    min_market_cap = None
    max_market_cap = None
    if isinstance(universe_filters, dict):
        raw_min_market_cap = universe_filters.get("min_market_cap")
        if raw_min_market_cap is not None:
            try:
                min_market_cap = float(raw_min_market_cap)
            except (TypeError, ValueError):
                min_market_cap = None
        raw_max_market_cap = universe_filters.get("max_market_cap")
        if raw_max_market_cap is not None:
            try:
                max_market_cap = float(raw_max_market_cap)
            except (TypeError, ValueError):
                max_market_cap = None

    use_market_cap_filter = (min_market_cap is not None) or (max_market_cap is not None)

    raw_limit_days = params.get("limit_days", 14)
    try:
        limit_days = int(raw_limit_days)
    except (TypeError, ValueError):
        limit_days = 14
    if limit_days <= 0:
        limit_days = 14

    raw_limit_up_threshold = params.get("limit_up_threshold", 9.9)
    try:
        limit_up_threshold = float(raw_limit_up_threshold)
    except (TypeError, ValueError):
        limit_up_threshold = 9.9

    raw_first_board_volume_ratio = params.get("first_board_volume_ratio", 2.0)
    try:
        first_board_volume_ratio = float(raw_first_board_volume_ratio)
    except (TypeError, ValueError):
        first_board_volume_ratio = 2.0

    raw_top_n = params.get("top_n", 50)
    try:
        top_n = int(raw_top_n)
    except (TypeError, ValueError):
        top_n = 50
    if top_n <= 0:
        top_n = 50

    decision_trace: list[dict[str, Any]] = []
    if not db_path.exists() or not db_path.is_file():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "stock db not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "open_db",
                    "status": "failed",
                    "reason": f"db_path missing: {db_path}",
                }
            ],
        }

    calendar_path = project_root / "var/ledgers/trading_calendar/trading_calendar.json"
    if not calendar_path.exists():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "trading calendar not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"calendar missing: {calendar_path}",
                }
            ],
        }

    try:
        calendar_payload = json.loads(calendar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "failed to read trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": str(exc),
                }
            ],
        }

    if not isinstance(calendar_payload, dict):
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "invalid trading calendar payload",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": "calendar payload is not a JSON object",
                }
            ],
        }
    trading_days = calendar_payload.get("trading_days")
    if not isinstance(trading_days, list) or not all(
        isinstance(item, str) for item in trading_days
    ):
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "invalid trading calendar payload",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": "trading_days missing or invalid",
                }
            ],
        }

    day_key = target_date.isoformat()
    try:
        idx = trading_days.index(day_key)
    except ValueError:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "target_date not in trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"target_date not found: {day_key}",
                }
            ],
        }

    window_start = max(0, idx - (limit_days - 1))
    needed_start = max(0, window_start - 1)
    dates_needed = trading_days[needed_start : idx + 1]
    if len(dates_needed) < 4:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "insufficient history for er_ban_hui_tiao",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "select_trade_days",
                    "status": "failed",
                    "reason": "need at least 4 trading days including target_date",
                }
            ],
        }
    window_dates = trading_days[window_start : idx + 1]
    decision_trace.append(
        {
            "step": "select_trade_days",
            "status": "ok",
            "target_date": day_key,
            "limit_days": limit_days,
            "window_start": window_dates[0] if window_dates else None,
            "window_end": day_key,
            "days_loaded": len(dates_needed),
        }
    )

    try:
        conn = sqlite3.connect(str(db_path))
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "failed to open sqlite db",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "open_db", "status": "failed", "reason": str(exc)}
            ],
        }

    try:
        cursor = conn.cursor()
        start_date = dates_needed[0]
        end_date = dates_needed[-1]
        query_attempts: list[tuple[str, bool]] = [
            (
                "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
                "dp.open, dp.high, dp.low, dp.close, dp.pct_change, dp.amount, "
                "s.circulating_market_cap "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0",
                True,
            ),
            (
                "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
                "dp.open, dp.high, dp.low, dp.close, dp.pct_change, dp.amount, "
                "NULL "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0",
                False,
            ),
        ]
        rows: list[
            tuple[
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
            ]
        ] = []
        has_market_cap = False
        last_exc: Exception | None = None
        for sql, attempt_has_market_cap in query_attempts:
            try:
                cursor.execute(sql, (start_date, end_date))
                rows = cursor.fetchall()
                has_market_cap = attempt_has_market_cap
                break
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None and not rows:
            raise last_exc
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "query failed",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "query", "status": "failed", "reason": str(exc)}
            ],
        }
    finally:
        conn.close()

    decision_trace.append(
        {
            "step": "query",
            "status": "ok",
            "row_count": len(rows),
            "has_market_cap": has_market_cap,
        }
    )
    if use_market_cap_filter and not has_market_cap:
        decision_trace.append(
            {
                "step": "validate_schema",
                "status": "failed",
                "reason": "market_cap column unavailable; cannot apply market_cap filters",
                "min_market_cap_yuan": min_market_cap,
                "max_market_cap_yuan": max_market_cap,
            }
        )
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "market cap unavailable; cannot apply market_cap filters",
            "parameters": params,
            "picks": [],
            "decision_trace": decision_trace,
        }

    excluded_prefixes = ("399", "43", "83", "87", "88")
    by_code: dict[str, dict[str, dict[str, float | str | None]]] = {}
    invalid_rows = 0
    for (
        trade_date_raw,
        code,
        name,
        open_price,
        high_price,
        low_price,
        close_price,
        pct_change,
        amount,
        market_cap,
    ) in rows:
        code_str = str(code)
        trade_date_str = str(trade_date_raw)
        name_str = str(name or "")
        try:
            open_f = float(cast(Any, open_price))
            high_f = float(cast(Any, high_price))
            low_f = float(cast(Any, low_price))
            close_f = float(cast(Any, close_price))
            pct_f = float(cast(Any, pct_change))
            amount_f = float(cast(Any, amount))
        except (TypeError, ValueError):
            invalid_rows += 1
            continue

        cap_f: float | None
        if market_cap is None:
            cap_f = None
        else:
            try:
                cap_f = float(cast(Any, market_cap))
            except (TypeError, ValueError):
                cap_f = None

        by_code.setdefault(code_str, {})[trade_date_str] = {
            "code": code_str,
            "name": name_str,
            "open": open_f,
            "high": high_f,
            "low": low_f,
            "close": close_f,
            "pct_change": pct_f,
            "amount": amount_f,
            "market_cap": cap_f,
        }

    if invalid_rows:
        decision_trace.append(
            {"step": "parse_rows", "status": "warn", "invalid_row_count": invalid_rows}
        )

    def is_limit_up(pct: float) -> bool:
        return pct >= limit_up_threshold

    picks_with_meta: list[dict[str, Any]] = []
    rejected_examples: list[dict[str, Any]] = []
    reject_count = 0
    for code_str, series in by_code.items():
        sample = next(iter(series.values()), None)
        name_str = str(sample.get("name") if isinstance(sample, dict) else "")
        if code_str.startswith(excluded_prefixes) or any(
            token in name_str for token in ("*ST", "ST", "PT")
        ):
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "base_exclusion", "name": name_str}
                )
            continue

        if use_market_cap_filter:
            cap = (
                series.get(day_key, {}).get("market_cap") if day_key in series else None
            )
            if cap is None:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "missing_market_cap",
                            "min_market_cap_yuan": min_market_cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue
            if not isinstance(cap, float):
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "invalid_market_cap",
                            "value": cap,
                        }
                    )
                continue
            if min_market_cap is not None and cap < min_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_below_threshold",
                            "market_cap_yuan": cap,
                            "min_market_cap_yuan": min_market_cap,
                        }
                    )
                continue
            if max_market_cap is not None and cap > max_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_above_threshold",
                            "market_cap_yuan": cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue

        missing_dates = [d for d in dates_needed if d not in series]
        if missing_dates:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {
                        "code": code_str,
                        "reason": "missing_required_days",
                        "missing_count": len(missing_dates),
                        "missing_examples": missing_dates[: min(3, len(missing_dates))],
                    }
                )
            continue

        t_idx: int | None = None
        for j in range(len(dates_needed) - 3, 0, -1):
            d_prev = dates_needed[j - 1]
            d_t = dates_needed[j]
            d_t1 = dates_needed[j + 1]
            d_t2 = dates_needed[j + 2]
            prev = series[d_prev]
            t = series[d_t]
            t1 = series[d_t1]
            t2 = series[d_t2]
            if not (
                is_limit_up(float(cast(Any, t["pct_change"])))
                and is_limit_up(float(cast(Any, t1["pct_change"])))
            ):
                continue
            if is_limit_up(float(cast(Any, t2["pct_change"]))):
                continue
            prev_amount = float(cast(Any, prev["amount"]))
            t_amount = float(cast(Any, t["amount"]))
            t1_amount = float(cast(Any, t1["amount"]))
            if prev_amount <= 0 or t_amount < prev_amount * first_board_volume_ratio:
                continue
            if t1_amount >= t_amount:
                continue
            t_idx = j
            break

        if t_idx is None:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "signal1_not_found"}
                )
            continue

        d_t = dates_needed[t_idx]
        d_t1 = dates_needed[t_idx + 1]
        t_open = float(cast(Any, series[d_t]["open"]))
        if any(
            float(cast(Any, series[d]["low"])) < t_open
            for d in dates_needed[t_idx + 2 :]
        ):
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append({"code": code_str, "reason": "signal2_failed"})
            continue

        launch_idx: int | None = None
        for i in range(t_idx + 2, len(dates_needed)):
            d_i = dates_needed[i]
            d_prev = dates_needed[i - 1]
            row = series[d_i]
            prev_row = series[d_prev]
            close_i = float(cast(Any, row["close"]))
            open_i = float(cast(Any, row["open"]))
            close_prev = float(cast(Any, prev_row["close"]))
            if close_i <= close_prev:
                continue
            if close_i <= open_i:
                continue
            max_amount = max(
                float(cast(Any, series[d]["amount"]))
                for d in dates_needed[t_idx : i + 1]
            )
            max_high = max(
                float(cast(Any, series[d]["high"])) for d in dates_needed[t_idx : i + 1]
            )
            if float(cast(Any, row["amount"])) < max_amount:
                continue
            if float(cast(Any, row["high"])) < max_high:
                continue
            launch_idx = i
            break

        if launch_idx is None:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "signal3_not_found"}
                )
            continue

        d_x = dates_needed[launch_idx]
        x_amount = float(cast(Any, series[d_x]["amount"]))
        picks_with_meta.append(
            {
                "code": code_str,
                "name": name_str,
                "t_date": d_t,
                "t_open": t_open,
                "t_amount": float(cast(Any, series[d_t]["amount"])),
                "s2_date": d_t1,
                "s2_amount": float(cast(Any, series[d_t1]["amount"])),
                "x_date": d_x,
                "x_amount": x_amount,
            }
        )

    decision_trace.append(
        {
            "step": "evaluate",
            "status": "ok",
            "limit_days": limit_days,
            "limit_up_threshold": limit_up_threshold,
            "first_board_volume_ratio": first_board_volume_ratio,
            "passed_count": len(picks_with_meta),
            "rejected_count": reject_count,
            "rejected_examples": rejected_examples,
        }
    )

    picks_with_meta.sort(
        key=lambda item: float(cast(Any, item.get("x_amount") or 0.0)), reverse=True
    )
    picks = [item["code"] for item in picks_with_meta[:top_n]]
    trace_candidate = None
    if trace_code:
        found = next((it for it in picks_with_meta if str(it.get("code") or "") == trace_code), None)
        if isinstance(found, dict):
            rank = None
            for idx, it in enumerate(picks_with_meta, start=1):
                if str(it.get("code") or "") == trace_code:
                    rank = idx
                    break
            cutoff = None
            if len(picks_with_meta) >= int(top_n) and int(top_n) > 0:
                cutoff = float(cast(Any, picks_with_meta[int(top_n) - 1].get("x_amount") or 0.0))
            trace_candidate = {
                "code": trace_code,
                "picked": bool(trace_code in picks),
                "rank_by_x_amount": rank,
                "x_amount": float(cast(Any, found.get("x_amount") or 0.0)),
                "cutoff_x_amount": cutoff,
                "top_n": int(top_n),
            }
    decision_trace.append(
        {
            "step": "rank_and_select",
            "status": "ok",
            "top_n": top_n,
            "picked_count": len(picks),
            "picked_examples": picks_with_meta[: min(5, len(picks_with_meta))],
            "trace_candidate": trace_candidate,
        }
    )

    return {
        "screener_id": screener_id,
        "target_date": day_key,
        "status": "ok",
        "message": "er_ban_hui_tiao: Signal1(two consecutive limit-up with amount constraints, skip 3+), Signal2(price protection vs T open), Signal3(launch day X: up close, yang line, max amount+high since T).",
        "parameters": params,
        "picks": picks,
        "decision_trace": decision_trace,
    }


def run_zhang_ting_bei_liang_yin(
    *, screener_id: str, target_date: date, parameters: dict[str, Any] | None = None
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]
    db_path = Path(
        os.environ.get("NEOTRADE3_STOCK_DB_PATH")
        or project_root / "var/db/stock_data.db"
    ).expanduser()
    params = parameters or {}
    raw_trace_code = params.get("trace_code")
    trace_code = str(raw_trace_code or "").strip().split(".", 1)[0]

    universe_filters = params.get("universe_filters")
    min_market_cap = None
    max_market_cap = None
    if isinstance(universe_filters, dict):
        raw_min_market_cap = universe_filters.get("min_market_cap")
        if raw_min_market_cap is not None:
            try:
                min_market_cap = float(raw_min_market_cap)
            except (TypeError, ValueError):
                min_market_cap = None
        raw_max_market_cap = universe_filters.get("max_market_cap")
        if raw_max_market_cap is not None:
            try:
                max_market_cap = float(raw_max_market_cap)
            except (TypeError, ValueError):
                max_market_cap = None

    use_market_cap_filter = (min_market_cap is not None) or (max_market_cap is not None)

    raw_limit_days = params.get("limit_days", 14)
    try:
        limit_days = int(raw_limit_days)
    except (TypeError, ValueError):
        limit_days = 14
    if limit_days <= 0:
        limit_days = 14

    raw_limit_up_threshold = params.get("limit_up_threshold", 9.9)
    try:
        limit_up_threshold = float(raw_limit_up_threshold)
    except (TypeError, ValueError):
        limit_up_threshold = 9.9

    raw_signal_one_body_ratio = params.get("signal_one_body_ratio", 3.0)
    try:
        signal_one_body_ratio = float(raw_signal_one_body_ratio)
    except (TypeError, ValueError):
        signal_one_body_ratio = 3.0

    raw_signal_two_body_ratio = params.get("signal_two_body_ratio", 2.0)
    try:
        signal_two_body_ratio = float(raw_signal_two_body_ratio)
    except (TypeError, ValueError):
        signal_two_body_ratio = 2.0

    raw_signal_three_volume_ratio = params.get("signal_three_volume_ratio", 2.0)
    try:
        signal_three_volume_ratio = float(raw_signal_three_volume_ratio)
    except (TypeError, ValueError):
        signal_three_volume_ratio = 2.0

    raw_signal_four_volume_ratio = params.get("signal_four_volume_ratio", 0.5)
    try:
        signal_four_volume_ratio = float(raw_signal_four_volume_ratio)
    except (TypeError, ValueError):
        signal_four_volume_ratio = 0.5

    raw_signal_five_volume_ratio = params.get("signal_five_volume_ratio", 2.0)
    try:
        signal_five_volume_ratio = float(raw_signal_five_volume_ratio)
    except (TypeError, ValueError):
        signal_five_volume_ratio = 2.0

    raw_top_n = params.get("top_n", 50)
    try:
        top_n = int(raw_top_n)
    except (TypeError, ValueError):
        top_n = 50
    if top_n <= 0:
        top_n = 50

    decision_trace: list[dict[str, Any]] = []
    if not db_path.exists() or not db_path.is_file():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "stock db not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "open_db",
                    "status": "failed",
                    "reason": f"db_path missing: {db_path}",
                }
            ],
        }

    calendar_path = project_root / "var/ledgers/trading_calendar/trading_calendar.json"
    if not calendar_path.exists():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "trading calendar not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"calendar missing: {calendar_path}",
                }
            ],
        }

    try:
        calendar_payload = json.loads(calendar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "failed to read trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": str(exc),
                }
            ],
        }

    if not isinstance(calendar_payload, dict):
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "invalid trading calendar payload",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": "calendar payload is not a JSON object",
                }
            ],
        }
    trading_days = calendar_payload.get("trading_days")
    if not isinstance(trading_days, list) or not all(
        isinstance(item, str) for item in trading_days
    ):
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "invalid trading calendar payload",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": "trading_days missing or invalid",
                }
            ],
        }

    day_key = target_date.isoformat()
    try:
        idx = trading_days.index(day_key)
    except ValueError:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "target_date not in trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"target_date not found: {day_key}",
                }
            ],
        }

    window_start = max(0, idx - (limit_days - 1))
    dates_needed = trading_days[window_start : idx + 1]
    if len(dates_needed) < 4:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "insufficient history for zhang_ting_bei_liang_yin",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "select_trade_days",
                    "status": "failed",
                    "reason": "need at least 4 trading days including target_date",
                }
            ],
        }

    decision_trace.append(
        {
            "step": "select_trade_days",
            "status": "ok",
            "target_date": day_key,
            "limit_days": limit_days,
            "window_start": dates_needed[0],
            "window_end": day_key,
            "days_loaded": len(dates_needed),
        }
    )

    try:
        conn = sqlite3.connect(str(db_path))
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "failed to open sqlite db",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "open_db", "status": "failed", "reason": str(exc)}
            ],
        }

    try:
        cursor = conn.cursor()
        start_date = dates_needed[0]
        end_date = dates_needed[-1]
        query_attempts: list[tuple[str, bool]] = [
            (
                "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
                "dp.open, dp.high, dp.low, dp.close, dp.pct_change, dp.amount, "
                "s.circulating_market_cap "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0",
                True,
            ),
            (
                "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
                "dp.open, dp.high, dp.low, dp.close, dp.pct_change, dp.amount, "
                "NULL "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0",
                False,
            ),
        ]
        rows: list[
            tuple[
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
            ]
        ] = []
        has_market_cap = False
        last_exc: Exception | None = None
        for sql, attempt_has_market_cap in query_attempts:
            try:
                cursor.execute(sql, (start_date, end_date))
                rows = cursor.fetchall()
                has_market_cap = attempt_has_market_cap
                break
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None and not rows:
            raise last_exc
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "query failed",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "query", "status": "failed", "reason": str(exc)}
            ],
        }
    finally:
        conn.close()

    decision_trace.append(
        {
            "step": "query",
            "status": "ok",
            "row_count": len(rows),
            "has_market_cap": has_market_cap,
        }
    )
    if use_market_cap_filter and not has_market_cap:
        decision_trace.append(
            {
                "step": "validate_schema",
                "status": "failed",
                "reason": "market_cap column unavailable; cannot apply market_cap filters",
                "min_market_cap_yuan": min_market_cap,
                "max_market_cap_yuan": max_market_cap,
            }
        )
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "market cap unavailable; cannot apply market_cap filters",
            "parameters": params,
            "picks": [],
            "decision_trace": decision_trace,
        }

    excluded_prefixes = ("399", "43", "83", "87", "88")
    by_code: dict[str, dict[str, dict[str, float | str | None]]] = {}
    invalid_rows = 0
    for (
        trade_date_raw,
        code,
        name,
        open_price,
        high_price,
        low_price,
        close_price,
        pct_change,
        amount,
        market_cap,
    ) in rows:
        code_str = str(code)
        trade_date_str = str(trade_date_raw)
        name_str = str(name or "")
        try:
            open_f = float(cast(Any, open_price))
            high_f = float(cast(Any, high_price))
            low_f = float(cast(Any, low_price))
            close_f = float(cast(Any, close_price))
            pct_f = float(cast(Any, pct_change))
            amount_f = float(cast(Any, amount))
        except (TypeError, ValueError):
            invalid_rows += 1
            continue

        cap_f: float | None
        if market_cap is None:
            cap_f = None
        else:
            try:
                cap_f = float(cast(Any, market_cap))
            except (TypeError, ValueError):
                cap_f = None

        by_code.setdefault(code_str, {})[trade_date_str] = {
            "code": code_str,
            "name": name_str,
            "open": open_f,
            "high": high_f,
            "low": low_f,
            "close": close_f,
            "pct_change": pct_f,
            "amount": amount_f,
            "market_cap": cap_f,
        }

    if invalid_rows:
        decision_trace.append(
            {"step": "parse_rows", "status": "warn", "invalid_row_count": invalid_rows}
        )

    def is_limit_up(pct: float) -> bool:
        return pct >= limit_up_threshold

    picks_with_meta: list[dict[str, Any]] = []
    rejected_examples: list[dict[str, Any]] = []
    reject_count = 0
    for code_str, series in by_code.items():
        sample = next(iter(series.values()), None)
        name_str = str(sample.get("name") if isinstance(sample, dict) else "")
        if code_str.startswith(excluded_prefixes) or any(
            token in name_str for token in ("*ST", "ST", "PT")
        ):
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "base_exclusion", "name": name_str}
                )
            continue

        if use_market_cap_filter:
            cap = (
                series.get(day_key, {}).get("market_cap") if day_key in series else None
            )
            if cap is None:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "missing_market_cap",
                            "min_market_cap_yuan": min_market_cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue
            if not isinstance(cap, float):
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "invalid_market_cap",
                            "value": cap,
                        }
                    )
                continue
            if min_market_cap is not None and cap < min_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_below_threshold",
                            "market_cap_yuan": cap,
                            "min_market_cap_yuan": min_market_cap,
                        }
                    )
                continue
            if max_market_cap is not None and cap > max_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_above_threshold",
                            "market_cap_yuan": cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue

        missing_dates = [d for d in dates_needed if d not in series]
        if missing_dates:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {
                        "code": code_str,
                        "reason": "missing_required_days",
                        "missing_count": len(missing_dates),
                        "missing_examples": missing_dates[: min(3, len(missing_dates))],
                    }
                )
            continue

        records = [series[d] for d in dates_needed]

        signal_one_idx: int | None = None
        signal_four_idx: int | None = None
        signal_five_idx: int | None = None
        for i in range(len(records) - 1, -1, -1):
            row = records[i]
            pct = float(cast(Any, row["pct_change"]))
            open_i = float(cast(Any, row["open"]))
            close_i = float(cast(Any, row["close"]))
            low_i = float(cast(Any, row["low"]))
            if not is_limit_up(pct):
                continue
            if close_i <= open_i:
                continue
            lower_shadow = open_i - low_i
            if lower_shadow <= 0:
                continue
            body = close_i - open_i
            if body < lower_shadow * signal_one_body_ratio:
                continue
            if i + 1 >= len(records):
                continue

            next_row = records[i + 1]
            open_n = float(cast(Any, next_row["open"]))
            close_n = float(cast(Any, next_row["close"]))
            high_n = float(cast(Any, next_row["high"]))
            low_n = float(cast(Any, next_row["low"]))
            prev_close = close_i
            if open_n <= prev_close:
                continue
            if close_n >= open_n:
                continue
            body_n = open_n - close_n
            upper_shadow = high_n - open_n
            lower_shadow_n = close_n - low_n
            total_shadow = upper_shadow + lower_shadow_n
            if total_shadow <= 0:
                continue
            if body_n < total_shadow * signal_two_body_ratio:
                continue

            amount_t = float(cast(Any, row["amount"]))
            amount_s2 = float(cast(Any, next_row["amount"]))
            if amount_s2 <= amount_t * signal_three_volume_ratio:
                continue

            threshold_x = amount_s2 * signal_four_volume_ratio
            found_x = None
            for j in range(i + 2, len(records)):
                if float(cast(Any, records[j]["amount"])) < threshold_x:
                    found_x = j
                    break
            if found_x is None:
                continue

            found_launch = None
            for k in range(found_x + 1, len(records)):
                k_row = records[k]
                if float(cast(Any, k_row["pct_change"])) <= 0:
                    continue
                if float(cast(Any, k_row["close"])) <= float(cast(Any, k_row["open"])):
                    continue
                prev_amount = float(cast(Any, records[k - 1]["amount"]))
                if (
                    float(cast(Any, k_row["amount"]))
                    <= prev_amount * signal_five_volume_ratio
                ):
                    continue
                found_launch = k
                break
            if found_launch is None:
                continue

            t_open = open_i
            if any(
                float(cast(Any, records[m]["low"])) < t_open
                for m in range(i + 1, len(records))
            ):
                continue

            signal_one_idx = i
            signal_four_idx = found_x
            signal_five_idx = found_launch
            break

        if signal_one_idx is None or signal_four_idx is None or signal_five_idx is None:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append({"code": code_str, "reason": "no_match"})
            continue

        t = records[signal_one_idx]
        s2 = records[signal_one_idx + 1]
        s4 = records[signal_four_idx]
        s5 = records[signal_five_idx]
        picks_with_meta.append(
            {
                "code": code_str,
                "name": name_str,
                "s1_date": dates_needed[signal_one_idx],
                "s2_date": dates_needed[signal_one_idx + 1],
                "s4_date": dates_needed[signal_four_idx],
                "s5_date": dates_needed[signal_five_idx],
                "s1_open": float(cast(Any, t["open"])),
                "s1_low": float(cast(Any, t["low"])),
                "s1_close": float(cast(Any, t["close"])),
                "s1_amount": float(cast(Any, t["amount"])),
                "s2_amount": float(cast(Any, s2["amount"])),
                "s4_amount": float(cast(Any, s4["amount"])),
                "s5_amount": float(cast(Any, s5["amount"])),
            }
        )

    decision_trace.append(
        {
            "step": "evaluate",
            "status": "ok",
            "limit_days": limit_days,
            "limit_up_threshold": limit_up_threshold,
            "passed_count": len(picks_with_meta),
            "rejected_count": reject_count,
            "rejected_examples": rejected_examples,
        }
    )

    picks_with_meta.sort(
        key=lambda item: float(cast(Any, item.get("s5_amount") or 0.0)), reverse=True
    )
    picks = [item["code"] for item in picks_with_meta[:top_n]]
    decision_trace.append(
        {
            "step": "rank_and_select",
            "status": "ok",
            "top_n": top_n,
            "picked_count": len(picks),
            "picked_examples": picks_with_meta[: min(5, len(picks_with_meta))],
        }
    )

    return {
        "screener_id": screener_id,
        "target_date": day_key,
        "status": "ok",
        "message": "zhang_ting_bei_liang_yin: Signal1(limit-up yang with body>=ratio*lower_shadow), Signal2(gap-up open then strong yin body), Signal2.5(price protection), Signal3(amount jump), Signal4(low volume day), Signal5(launch day with yang+amount 2x).",
        "parameters": params,
        "picks": picks,
        "decision_trace": decision_trace,
    }


def run_jin_feng_huang(
    *, screener_id: str, target_date: date, parameters: dict[str, Any] | None = None
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]
    db_path = Path(
        os.environ.get("NEOTRADE3_STOCK_DB_PATH")
        or project_root / "var/db/stock_data.db"
    ).expanduser()
    params = parameters or {}
    raw_trace_code = params.get("trace_code")
    trace_code = str(raw_trace_code or "").strip().split(".", 1)[0]

    universe_filters = params.get("universe_filters")
    min_market_cap = None
    max_market_cap = None
    if isinstance(universe_filters, dict):
        raw_min_market_cap = universe_filters.get("min_market_cap")
        if raw_min_market_cap is not None:
            try:
                min_market_cap = float(raw_min_market_cap)
            except (TypeError, ValueError):
                min_market_cap = None
        raw_max_market_cap = universe_filters.get("max_market_cap")
        if raw_max_market_cap is not None:
            try:
                max_market_cap = float(raw_max_market_cap)
            except (TypeError, ValueError):
                max_market_cap = None

    use_market_cap_filter = (min_market_cap is not None) or (max_market_cap is not None)

    raw_limit_days = params.get("limit_days", 14)
    try:
        limit_days = int(raw_limit_days)
    except (TypeError, ValueError):
        limit_days = 14
    if limit_days <= 0:
        limit_days = 14

    raw_limit_up_threshold = params.get("limit_up_threshold", 9.9)
    try:
        limit_up_threshold = float(raw_limit_up_threshold)
    except (TypeError, ValueError):
        limit_up_threshold = 9.9

    raw_signal_one_volume_ratio = params.get("signal_one_volume_ratio", 2.0)
    try:
        signal_one_volume_ratio = float(raw_signal_one_volume_ratio)
    except (TypeError, ValueError):
        signal_one_volume_ratio = 2.0

    raw_signal_two_volume_ratio = params.get("signal_two_volume_ratio", 2.0)
    try:
        signal_two_volume_ratio = float(raw_signal_two_volume_ratio)
    except (TypeError, ValueError):
        signal_two_volume_ratio = 2.0

    raw_signal_four_volume_ratio = params.get("signal_four_volume_ratio", 0.5)
    try:
        signal_four_volume_ratio = float(raw_signal_four_volume_ratio)
    except (TypeError, ValueError):
        signal_four_volume_ratio = 0.5

    raw_signal_five_volume_ratio = params.get("signal_five_volume_ratio", 2.0)
    try:
        signal_five_volume_ratio = float(raw_signal_five_volume_ratio)
    except (TypeError, ValueError):
        signal_five_volume_ratio = 2.0

    raw_top_n = params.get("top_n", 50)
    try:
        top_n = int(raw_top_n)
    except (TypeError, ValueError):
        top_n = 50
    if top_n <= 0:
        top_n = 50

    decision_trace: list[dict[str, Any]] = []
    if not db_path.exists() or not db_path.is_file():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "stock db not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "open_db",
                    "status": "failed",
                    "reason": f"db_path missing: {db_path}",
                }
            ],
        }

    calendar_path = project_root / "var/ledgers/trading_calendar/trading_calendar.json"
    if not calendar_path.exists():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "trading calendar not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"calendar missing: {calendar_path}",
                }
            ],
        }

    try:
        calendar_payload = json.loads(calendar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "failed to read trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": str(exc),
                }
            ],
        }

    if not isinstance(calendar_payload, dict):
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "invalid trading calendar payload",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": "calendar payload is not a JSON object",
                }
            ],
        }
    trading_days = calendar_payload.get("trading_days")
    if not isinstance(trading_days, list) or not all(
        isinstance(item, str) for item in trading_days
    ):
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "invalid trading calendar payload",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": "trading_days missing or invalid",
                }
            ],
        }

    day_key = target_date.isoformat()
    try:
        idx = trading_days.index(day_key)
    except ValueError:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "target_date not in trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"target_date not found: {day_key}",
                }
            ],
        }

    window_start = max(0, idx - (limit_days - 1))
    dates_needed = trading_days[window_start : idx + 1]
    if len(dates_needed) < 4:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "insufficient history for jin_feng_huang",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "select_trade_days",
                    "status": "failed",
                    "reason": "need at least 4 trading days including target_date",
                }
            ],
        }

    decision_trace.append(
        {
            "step": "select_trade_days",
            "status": "ok",
            "target_date": day_key,
            "limit_days": limit_days,
            "window_start": dates_needed[0],
            "window_end": day_key,
            "days_loaded": len(dates_needed),
        }
    )

    try:
        conn = sqlite3.connect(str(db_path))
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "failed to open sqlite db",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "open_db", "status": "failed", "reason": str(exc)}
            ],
        }

    try:
        cursor = conn.cursor()
        start_date = dates_needed[0]
        end_date = dates_needed[-1]
        query_attempts: list[tuple[str, bool]] = [
            (
                "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
                "dp.open, dp.high, dp.low, dp.close, dp.pct_change, dp.amount, "
                "s.circulating_market_cap "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0",
                True,
            ),
            (
                "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
                "dp.open, dp.high, dp.low, dp.close, dp.pct_change, dp.amount, "
                "NULL "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0",
                False,
            ),
        ]
        rows: list[
            tuple[
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
            ]
        ] = []
        has_market_cap = False
        last_exc: Exception | None = None
        for sql, attempt_has_market_cap in query_attempts:
            try:
                cursor.execute(sql, (start_date, end_date))
                rows = cursor.fetchall()
                has_market_cap = attempt_has_market_cap
                break
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None and not rows:
            raise last_exc
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "query failed",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "query", "status": "failed", "reason": str(exc)}
            ],
        }
    finally:
        conn.close()

    decision_trace.append(
        {
            "step": "query",
            "status": "ok",
            "row_count": len(rows),
            "has_market_cap": has_market_cap,
        }
    )
    if use_market_cap_filter and not has_market_cap:
        decision_trace.append(
            {
                "step": "validate_schema",
                "status": "failed",
                "reason": "market_cap column unavailable; cannot apply market_cap filters",
                "min_market_cap_yuan": min_market_cap,
                "max_market_cap_yuan": max_market_cap,
            }
        )
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "market cap unavailable; cannot apply market_cap filters",
            "parameters": params,
            "picks": [],
            "decision_trace": decision_trace,
        }

    excluded_prefixes = ("399", "43", "83", "87", "88")
    by_code: dict[str, dict[str, dict[str, float | str | None]]] = {}
    invalid_rows = 0
    for (
        trade_date_raw,
        code,
        name,
        open_price,
        high_price,
        low_price,
        close_price,
        pct_change,
        amount,
        market_cap,
    ) in rows:
        code_str = str(code)
        trade_date_str = str(trade_date_raw)
        name_str = str(name or "")
        try:
            open_f = float(cast(Any, open_price))
            high_f = float(cast(Any, high_price))
            low_f = float(cast(Any, low_price))
            close_f = float(cast(Any, close_price))
            pct_f = float(cast(Any, pct_change))
            amount_f = float(cast(Any, amount))
        except (TypeError, ValueError):
            invalid_rows += 1
            continue

        cap_f: float | None
        if market_cap is None:
            cap_f = None
        else:
            try:
                cap_f = float(cast(Any, market_cap))
            except (TypeError, ValueError):
                cap_f = None

        by_code.setdefault(code_str, {})[trade_date_str] = {
            "code": code_str,
            "name": name_str,
            "open": open_f,
            "high": high_f,
            "low": low_f,
            "close": close_f,
            "pct_change": pct_f,
            "amount": amount_f,
            "market_cap": cap_f,
        }

    if invalid_rows:
        decision_trace.append(
            {"step": "parse_rows", "status": "warn", "invalid_row_count": invalid_rows}
        )

    def is_limit_up(pct: float) -> bool:
        return pct >= limit_up_threshold

    def is_yi_zi(open_p: float, close_p: float, high_p: float, low_p: float) -> bool:
        return open_p == close_p == high_p == low_p

    picks_with_meta: list[dict[str, Any]] = []
    rejected_examples: list[dict[str, Any]] = []
    reject_count = 0
    for code_str, series in by_code.items():
        sample = next(iter(series.values()), None)
        name_str = str(sample.get("name") if isinstance(sample, dict) else "")
        if code_str.startswith(excluded_prefixes) or any(
            token in name_str for token in ("*ST", "ST", "PT")
        ):
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "base_exclusion", "name": name_str}
                )
            continue

        if use_market_cap_filter:
            cap = (
                series.get(day_key, {}).get("market_cap") if day_key in series else None
            )
            if cap is None:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "missing_market_cap",
                            "min_market_cap_yuan": min_market_cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue
            if not isinstance(cap, float):
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "invalid_market_cap",
                            "value": cap,
                        }
                    )
                continue
            if min_market_cap is not None and cap < min_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_below_threshold",
                            "market_cap_yuan": cap,
                            "min_market_cap_yuan": min_market_cap,
                        }
                    )
                continue
            if max_market_cap is not None and cap > max_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_above_threshold",
                            "market_cap_yuan": cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue

        missing_dates = [d for d in dates_needed if d not in series]
        if missing_dates:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {
                        "code": code_str,
                        "reason": "missing_required_days",
                        "missing_count": len(missing_dates),
                        "missing_examples": missing_dates[: min(3, len(missing_dates))],
                    }
                )
            continue

        records = [series[d] for d in dates_needed]
        matched = False
        for i in range(len(records) - 2, 0, -1):
            row = records[i]
            prev = records[i - 1]
            next_row = records[i + 1]

            pct = float(cast(Any, row["pct_change"]))
            open_i = float(cast(Any, row["open"]))
            close_i = float(cast(Any, row["close"]))
            high_i = float(cast(Any, row["high"]))
            low_i = float(cast(Any, row["low"]))
            amount_i = float(cast(Any, row["amount"]))
            prev_amount = float(cast(Any, prev["amount"]))

            if not is_limit_up(pct):
                continue
            if is_yi_zi(open_i, close_i, high_i, low_i):
                continue
            if prev_amount <= 0 or amount_i < prev_amount * signal_one_volume_ratio:
                continue

            open_n = float(cast(Any, next_row["open"]))
            close_n = float(cast(Any, next_row["close"]))
            low_n = float(cast(Any, next_row["low"]))
            amount_n = float(cast(Any, next_row["amount"]))
            if close_n <= open_n:
                continue
            if low_n <= high_i:
                continue
            if amount_n < amount_i * signal_two_volume_ratio:
                continue

            signal_two_idx = i + 1
            signal_four_idx: int | None = None
            for j in range(signal_two_idx + 1, len(records)):
                current_amount = float(cast(Any, records[j]["amount"]))
                prev_j_amount = float(cast(Any, records[j - 1]["amount"]))
                if (
                    prev_j_amount > 0
                    and current_amount < prev_j_amount * signal_four_volume_ratio
                ):
                    signal_four_idx = j
                    break
            if signal_four_idx is None:
                continue

            signal_five_idx: int | None = None
            for k in range(signal_four_idx + 1, len(records)):
                k_row = records[k]
                if float(cast(Any, k_row["pct_change"])) <= 0:
                    continue
                prev_k_amount = float(cast(Any, records[k - 1]["amount"]))
                if prev_k_amount <= 0:
                    continue
                if (
                    float(cast(Any, k_row["amount"]))
                    < prev_k_amount * signal_five_volume_ratio
                ):
                    continue
                period_highs = [
                    float(cast(Any, records[t]["high"])) for t in range(i, k + 1)
                ]
                max_high = (
                    max(period_highs)
                    if period_highs
                    else float(cast(Any, k_row["high"]))
                )
                if float(cast(Any, k_row["high"])) < max_high:
                    continue
                signal_five_idx = k
                break
            if signal_five_idx is None:
                continue

            if any(
                float(cast(Any, records[t]["low"])) <= high_i
                for t in range(i + 1, signal_five_idx)
            ):
                continue

            picks_with_meta.append(
                {
                    "code": code_str,
                    "name": name_str,
                    "signal_one_date": dates_needed[i],
                    "signal_two_date": dates_needed[signal_two_idx],
                    "signal_four_date": dates_needed[signal_four_idx],
                    "signal_five_date": dates_needed[signal_five_idx],
                    "s1_amount": amount_i,
                    "s2_amount": amount_n,
                    "s5_amount": float(cast(Any, records[signal_five_idx]["amount"])),
                }
            )
            matched = True
            break

        if not matched:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append({"code": code_str, "reason": "no_match"})

    decision_trace.append(
        {
            "step": "evaluate",
            "status": "ok",
            "limit_days": limit_days,
            "limit_up_threshold": limit_up_threshold,
            "passed_count": len(picks_with_meta),
            "rejected_count": reject_count,
            "rejected_examples": rejected_examples,
        }
    )

    picks_with_meta.sort(
        key=lambda item: float(cast(Any, item.get("s5_amount") or 0.0)), reverse=True
    )
    picks = [item["code"] for item in picks_with_meta[:top_n]]
    decision_trace.append(
        {
            "step": "rank_and_select",
            "status": "ok",
            "top_n": top_n,
            "picked_count": len(picks),
            "picked_examples": picks_with_meta[: min(5, len(picks_with_meta))],
        }
    )

    return {
        "screener_id": screener_id,
        "target_date": day_key,
        "status": "ok",
        "message": "jin_feng_huang: Signal1(non-yi-zi limit-up with amount ratio), Signal2(next day yang with low>signal1 high and amount ratio), Signal3(all lows > signal1 high until launch), Signal4(low-volume day), Signal5(launch day: up + amount ratio + new high since signal1).",
        "parameters": params,
        "picks": picks,
        "decision_trace": decision_trace,
    }


def run_yin_feng_huang(
    *, screener_id: str, target_date: date, parameters: dict[str, Any] | None = None
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]
    db_path = Path(
        os.environ.get("NEOTRADE3_STOCK_DB_PATH")
        or project_root / "var/db/stock_data.db"
    ).expanduser()
    params = parameters or {}
    raw_trace_code = params.get("trace_code")
    trace_code = str(raw_trace_code or "").strip().split(".", 1)[0]

    universe_filters = params.get("universe_filters")
    min_market_cap = None
    max_market_cap = None
    if isinstance(universe_filters, dict):
        raw_min_market_cap = universe_filters.get("min_market_cap")
        if raw_min_market_cap is not None:
            try:
                min_market_cap = float(raw_min_market_cap)
            except (TypeError, ValueError):
                min_market_cap = None
        raw_max_market_cap = universe_filters.get("max_market_cap")
        if raw_max_market_cap is not None:
            try:
                max_market_cap = float(raw_max_market_cap)
            except (TypeError, ValueError):
                max_market_cap = None

    use_market_cap_filter = (min_market_cap is not None) or (max_market_cap is not None)

    raw_limit_days = params.get("limit_days", 14)
    try:
        limit_days = int(raw_limit_days)
    except (TypeError, ValueError):
        limit_days = 14
    if limit_days <= 0:
        limit_days = 14

    raw_limit_up_threshold = params.get("limit_up_threshold", 9.9)
    try:
        limit_up_threshold = float(raw_limit_up_threshold)
    except (TypeError, ValueError):
        limit_up_threshold = 9.9

    raw_signal_one_volume_ratio = params.get("signal_one_volume_ratio", 2.0)
    try:
        signal_one_volume_ratio = float(raw_signal_one_volume_ratio)
    except (TypeError, ValueError):
        signal_one_volume_ratio = 2.0

    raw_signal_three_shrink_ratio = params.get("signal_three_shrink_ratio", 1.0)
    try:
        signal_three_shrink_ratio = float(raw_signal_three_shrink_ratio)
    except (TypeError, ValueError):
        signal_three_shrink_ratio = 1.0

    raw_signal_four_volume_ratio = params.get("signal_four_volume_ratio", 2.0)
    try:
        signal_four_volume_ratio = float(raw_signal_four_volume_ratio)
    except (TypeError, ValueError):
        signal_four_volume_ratio = 2.0

    raw_top_n = params.get("top_n", 50)
    try:
        top_n = int(raw_top_n)
    except (TypeError, ValueError):
        top_n = 50
    if top_n <= 0:
        top_n = 50

    decision_trace: list[dict[str, Any]] = []
    if not db_path.exists() or not db_path.is_file():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "stock db not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "open_db",
                    "status": "failed",
                    "reason": f"db_path missing: {db_path}",
                }
            ],
        }

    calendar_path = project_root / "var/ledgers/trading_calendar/trading_calendar.json"
    if not calendar_path.exists():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "trading calendar not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"calendar missing: {calendar_path}",
                }
            ],
        }

    try:
        calendar_payload = json.loads(calendar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "failed to read trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": str(exc),
                }
            ],
        }

    if not isinstance(calendar_payload, dict):
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "invalid trading calendar payload",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": "calendar payload is not a JSON object",
                }
            ],
        }
    trading_days = calendar_payload.get("trading_days")
    if not isinstance(trading_days, list) or not all(
        isinstance(item, str) for item in trading_days
    ):
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "invalid trading calendar payload",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": "trading_days missing or invalid",
                }
            ],
        }

    day_key = target_date.isoformat()
    try:
        idx = trading_days.index(day_key)
    except ValueError:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "target_date not in trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"target_date not found: {day_key}",
                }
            ],
        }

    window_start = max(0, idx - (limit_days - 1))
    needed_start = max(0, window_start - 1)
    dates_needed = trading_days[needed_start : idx + 1]
    if len(dates_needed) < 3:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "insufficient history for yin_feng_huang",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "select_trade_days",
                    "status": "failed",
                    "reason": "need at least 3 trading days including prev day",
                }
            ],
        }

    decision_trace.append(
        {
            "step": "select_trade_days",
            "status": "ok",
            "target_date": day_key,
            "limit_days": limit_days,
            "window_start": trading_days[window_start],
            "window_end": day_key,
            "days_loaded": len(dates_needed),
        }
    )

    try:
        conn = sqlite3.connect(str(db_path))
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "failed to open sqlite db",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "open_db", "status": "failed", "reason": str(exc)}
            ],
        }

    try:
        cursor = conn.cursor()
        start_date = dates_needed[0]
        end_date = dates_needed[-1]
        query_attempts: list[tuple[str, bool]] = [
            (
                "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
                "dp.open, dp.high, dp.low, dp.close, dp.pct_change, dp.amount, "
                "s.circulating_market_cap "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0",
                True,
            ),
            (
                "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
                "dp.open, dp.high, dp.low, dp.close, dp.pct_change, dp.amount, "
                "NULL "
                "FROM daily_prices dp "
                "JOIN stocks s ON s.code = dp.code "
                "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
                "AND COALESCE(s.asset_type, 'stock') = 'stock' "
                "AND COALESCE(s.is_delisted, 0) = 0",
                False,
            ),
        ]
        rows: list[
            tuple[
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
            ]
        ] = []
        has_market_cap = False
        last_exc: Exception | None = None
        for sql, attempt_has_market_cap in query_attempts:
            try:
                cursor.execute(sql, (start_date, end_date))
                rows = cursor.fetchall()
                has_market_cap = attempt_has_market_cap
                break
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None and not rows:
            raise last_exc
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "query failed",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "query", "status": "failed", "reason": str(exc)}
            ],
        }
    finally:
        conn.close()

    decision_trace.append(
        {
            "step": "query",
            "status": "ok",
            "row_count": len(rows),
            "has_market_cap": has_market_cap,
        }
    )
    if use_market_cap_filter and not has_market_cap:
        decision_trace.append(
            {
                "step": "validate_schema",
                "status": "failed",
                "reason": "market_cap column unavailable; cannot apply market_cap filters",
                "min_market_cap_yuan": min_market_cap,
                "max_market_cap_yuan": max_market_cap,
            }
        )
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "market cap unavailable; cannot apply market_cap filters",
            "parameters": params,
            "picks": [],
            "decision_trace": decision_trace,
        }

    excluded_prefixes = ("399", "43", "83", "87", "88")
    by_code: dict[str, dict[str, dict[str, float | str | None]]] = {}
    invalid_rows = 0
    for (
        trade_date_raw,
        code,
        name,
        open_price,
        high_price,
        low_price,
        close_price,
        pct_change,
        amount,
        market_cap,
    ) in rows:
        code_str = str(code)
        trade_date_str = str(trade_date_raw)
        name_str = str(name or "")
        try:
            open_f = float(cast(Any, open_price))
            high_f = float(cast(Any, high_price))
            low_f = float(cast(Any, low_price))
            close_f = float(cast(Any, close_price))
            pct_f = float(cast(Any, pct_change))
            amount_f = float(cast(Any, amount))
        except (TypeError, ValueError):
            invalid_rows += 1
            continue

        cap_f: float | None
        if market_cap is None:
            cap_f = None
        else:
            try:
                cap_f = float(cast(Any, market_cap))
            except (TypeError, ValueError):
                cap_f = None

        by_code.setdefault(code_str, {})[trade_date_str] = {
            "code": code_str,
            "name": name_str,
            "open": open_f,
            "high": high_f,
            "low": low_f,
            "close": close_f,
            "pct_change": pct_f,
            "amount": amount_f,
            "market_cap": cap_f,
        }

    if invalid_rows:
        decision_trace.append(
            {"step": "parse_rows", "status": "warn", "invalid_row_count": invalid_rows}
        )

    def is_limit_up(pct: float) -> bool:
        return pct >= limit_up_threshold

    def is_yi_zi(open_p: float, close_p: float, high_p: float, low_p: float) -> bool:
        return open_p == close_p == high_p == low_p

    offset = window_start - needed_start
    picks_with_meta: list[dict[str, Any]] = []
    rejected_examples: list[dict[str, Any]] = []
    reject_count = 0
    for code_str, series in by_code.items():
        sample = next(iter(series.values()), None)
        name_str = str(sample.get("name") if isinstance(sample, dict) else "")
        if code_str.startswith(excluded_prefixes) or any(
            token in name_str for token in ("*ST", "ST", "PT")
        ):
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "base_exclusion", "name": name_str}
                )
            continue

        if use_market_cap_filter:
            cap = (
                series.get(day_key, {}).get("market_cap") if day_key in series else None
            )
            if cap is None:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "missing_market_cap",
                            "min_market_cap_yuan": min_market_cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue
            if not isinstance(cap, float):
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {"code": code_str, "reason": "invalid_market_cap", "value": cap}
                    )
                continue
            if min_market_cap is not None and cap < min_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_below_threshold",
                            "market_cap_yuan": cap,
                            "min_market_cap_yuan": min_market_cap,
                        }
                    )
                continue
            if max_market_cap is not None and cap > max_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_above_threshold",
                            "market_cap_yuan": cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue

        missing_dates = [d for d in dates_needed if d not in series]
        if missing_dates:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {
                        "code": code_str,
                        "reason": "missing_required_days",
                        "missing_count": len(missing_dates),
                    }
                )
            continue

        records = [series[d] for d in dates_needed]
        window_records = records[offset:]

        signal_one_idx: int | None = None
        signal_three_idx: int | None = None
        signal_four_idx: int | None = None

        for i in range(len(window_records) - 1, 0, -1):
            row = window_records[i]
            prev = window_records[i - 1]
            pct = float(cast(Any, row["pct_change"]))
            open_i = float(cast(Any, row["open"]))
            close_i = float(cast(Any, row["close"]))
            high_i = float(cast(Any, row["high"]))
            low_i = float(cast(Any, row["low"]))
            amount_i = float(cast(Any, row["amount"]))
            prev_amount = float(cast(Any, prev["amount"]))

            if not is_limit_up(pct):
                continue
            if is_yi_zi(open_i, close_i, high_i, low_i):
                continue
            if prev_amount <= 0 or amount_i < prev_amount * signal_one_volume_ratio:
                continue

            s1_open = open_i
            s1_abs_idx = offset + i

            found_three = None
            for j in range(s1_abs_idx + 1, len(records)):
                current = records[j]
                prev_j = records[j - 1]
                if float(cast(Any, current["pct_change"])) >= 0:
                    continue
                prev_amt = float(cast(Any, prev_j["amount"]))
                if prev_amt <= 0:
                    continue
                if (
                    float(cast(Any, current["amount"]))
                    >= prev_amt * signal_three_shrink_ratio
                ):
                    continue
                found_three = j
                break
            if found_three is None:
                continue

            found_four = None
            for k in range(found_three + 1, len(records)):
                k_row = records[k]
                if float(cast(Any, k_row["pct_change"])) <= 0:
                    continue
                prev_amt = float(cast(Any, records[k - 1]["amount"]))
                if prev_amt <= 0:
                    continue
                if (
                    float(cast(Any, k_row["amount"]))
                    < prev_amt * signal_four_volume_ratio
                ):
                    continue
                found_four = k
                break
            if found_four is None:
                continue

            if any(
                float(cast(Any, records[t]["low"])) <= s1_open
                for t in range(s1_abs_idx + 1, found_four)
            ):
                continue

            signal_one_idx = s1_abs_idx
            signal_three_idx = found_three
            signal_four_idx = found_four
            break

        if (
            signal_one_idx is None
            or signal_three_idx is None
            or signal_four_idx is None
        ):
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append({"code": code_str, "reason": "no_match"})
            continue

        s1 = records[signal_one_idx]
        s3 = records[signal_three_idx]
        s4 = records[signal_four_idx]
        picks_with_meta.append(
            {
                "code": code_str,
                "name": name_str,
                "signal_one_date": dates_needed[signal_one_idx],
                "signal_three_date": dates_needed[signal_three_idx],
                "signal_four_date": dates_needed[signal_four_idx],
                "s1_amount": float(cast(Any, s1["amount"])),
                "s3_amount": float(cast(Any, s3["amount"])),
                "s4_amount": float(cast(Any, s4["amount"])),
            }
        )

    decision_trace.append(
        {
            "step": "evaluate",
            "status": "ok",
            "limit_days": limit_days,
            "limit_up_threshold": limit_up_threshold,
            "passed_count": len(picks_with_meta),
            "rejected_count": reject_count,
            "rejected_examples": rejected_examples,
        }
    )

    picks_with_meta.sort(
        key=lambda item: float(cast(Any, item.get("s4_amount") or 0.0)), reverse=True
    )
    picks = [item["code"] for item in picks_with_meta[:top_n]]
    decision_trace.append(
        {
            "step": "rank_and_select",
            "status": "ok",
            "top_n": top_n,
            "picked_count": len(picks),
            "picked_examples": picks_with_meta[: min(5, len(picks_with_meta))],
        }
    )

    return {
        "screener_id": screener_id,
        "target_date": day_key,
        "status": "ok",
        "message": "yin_feng_huang: Signal1(non-yi-zi limit-up with amount ratio), Signal2(lows between signal1 and launch > signal1 open), Signal3(negative day with shrink amount), Signal4(launch day: up + amount ratio).",
        "parameters": params,
        "picks": picks,
        "decision_trace": decision_trace,
    }


def run_shi_pan_xian(
    *, screener_id: str, target_date: date, parameters: dict[str, Any] | None = None
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]
    db_path = Path(
        os.environ.get("NEOTRADE3_STOCK_DB_PATH")
        or project_root / "var/db/stock_data.db"
    ).expanduser()
    params = parameters or {}
    raw_trace_code = params.get("trace_code")
    trace_code = str(raw_trace_code or "").strip().split(".", 1)[0]

    universe_filters = params.get("universe_filters")
    min_market_cap = None
    max_market_cap = None
    if isinstance(universe_filters, dict):
        raw_min_market_cap = universe_filters.get("min_market_cap")
        if raw_min_market_cap is not None:
            try:
                min_market_cap = float(raw_min_market_cap)
            except (TypeError, ValueError):
                min_market_cap = None
        raw_max_market_cap = universe_filters.get("max_market_cap")
        if raw_max_market_cap is not None:
            try:
                max_market_cap = float(raw_max_market_cap)
            except (TypeError, ValueError):
                max_market_cap = None

    use_market_cap_filter = (min_market_cap is not None) or (max_market_cap is not None)

    def _get_int(key: str, default: int) -> int:
        raw = params.get(key, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default
        return value if value > 0 else default

    def _get_float(key: str, default: float) -> float:
        raw = params.get(key, default)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    lookback_days = _get_int("lookback_days", 150)
    min_history_days = _get_int("min_history_days", 50)
    consolidation_days = _get_int("consolidation_days", 20)
    high_volume_lookback = _get_int("high_volume_lookback", 30)
    callback_max_days = _get_int("callback_max_days", 10)
    limit_up_search_days = _get_int("limit_up_search_days", 5)
    min_days_after_high_volume = _get_int("min_days_after_high_volume", 3)
    breakout_volume_ratio = _get_float("breakout_volume_ratio", 1.5)
    max_consolidation_gain = _get_float("max_consolidation_gain", 0.10)
    volume_shrink_threshold = _get_float("volume_shrink_threshold", 0.25)
    high_volume_peak_tolerance = _get_float("high_volume_peak_tolerance", 0.95)

    main_board_limit_up_pct = _get_float("main_board_limit_up_pct", 9.5)
    gem_star_limit_up_pct = _get_float("gem_star_limit_up_pct", 19.5)
    bse_limit_up_pct = _get_float("bse_limit_up_pct", 29.5)
    st_limit_up_pct = _get_float("st_limit_up_pct", 4.5)

    raw_top_n = params.get("top_n", 50)
    try:
        top_n = int(raw_top_n)
    except (TypeError, ValueError):
        top_n = 50
    if top_n <= 0:
        top_n = 50

    decision_trace: list[dict[str, Any]] = []
    if not db_path.exists() or not db_path.is_file():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "stock db not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "open_db",
                    "status": "failed",
                    "reason": f"db_path missing: {db_path}",
                }
            ],
        }

    calendar_path = project_root / "var/ledgers/trading_calendar/trading_calendar.json"
    if not calendar_path.exists():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "trading calendar not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"calendar missing: {calendar_path}",
                }
            ],
        }

    try:
        calendar_payload = json.loads(calendar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "failed to read trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": str(exc),
                }
            ],
        }

    if not isinstance(calendar_payload, dict):
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "invalid trading calendar payload",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": "calendar payload is not a JSON object",
                }
            ],
        }
    trading_days = calendar_payload.get("trading_days")
    if not isinstance(trading_days, list) or not all(
        isinstance(item, str) for item in trading_days
    ):
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "invalid trading calendar payload",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": "trading_days missing or invalid",
                }
            ],
        }

    day_key = target_date.isoformat()
    try:
        idx = trading_days.index(day_key)
    except ValueError:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "target_date not in trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"target_date not found: {day_key}",
                }
            ],
        }

    window_start = max(0, idx - (lookback_days - 1))
    dates_needed = trading_days[window_start : idx + 1]
    if len(dates_needed) < min_history_days:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "insufficient history for shi_pan_xian",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "select_trade_days",
                    "status": "failed",
                    "reason": f"need at least {min_history_days} trading days",
                    "days_loaded": len(dates_needed),
                }
            ],
        }

    decision_trace.append(
        {
            "step": "select_trade_days",
            "status": "ok",
            "target_date": day_key,
            "lookback_days": lookback_days,
            "window_start": dates_needed[0],
            "window_end": day_key,
            "days_loaded": len(dates_needed),
        }
    )

    try:
        conn = sqlite3.connect(str(db_path))
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "failed to open sqlite db",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "open_db", "status": "failed", "reason": str(exc)}
            ],
        }

    try:
        cursor = conn.cursor()
        start_date = dates_needed[0]
        end_date = dates_needed[-1]
        sql_with_cap = (
            "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
            "dp.open, dp.high, dp.low, dp.close, dp.volume, dp.pct_change, "
            "s.circulating_market_cap "
            "FROM daily_prices dp "
            "JOIN stocks s ON s.code = dp.code "
            "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
            "AND COALESCE(s.asset_type, 'stock') = 'stock' "
            "AND COALESCE(s.is_delisted, 0) = 0"
        )
        sql_no_cap = (
            "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
            "dp.open, dp.high, dp.low, dp.close, dp.volume, dp.pct_change, "
            "NULL "
            "FROM daily_prices dp "
            "JOIN stocks s ON s.code = dp.code "
            "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
            "AND COALESCE(s.asset_type, 'stock') = 'stock' "
            "AND COALESCE(s.is_delisted, 0) = 0"
        )
        rows: list[
            tuple[
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
            ]
        ] = []
        has_market_cap = False
        last_exc: Exception | None = None
        for sql, cap_flag in ((sql_with_cap, True), (sql_no_cap, False)):
            try:
                cursor.execute(sql, (start_date, end_date))
                rows = cursor.fetchall()
                has_market_cap = cap_flag
                break
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None and not rows:
            raise last_exc
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "query failed",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "query", "status": "failed", "reason": str(exc)}
            ],
        }
    finally:
        conn.close()

    decision_trace.append(
        {
            "step": "query",
            "status": "ok",
            "row_count": len(rows),
            "has_market_cap": has_market_cap,
        }
    )
    if use_market_cap_filter and not has_market_cap:
        decision_trace.append(
            {
                "step": "validate_schema",
                "status": "failed",
                "reason": "market_cap column unavailable; cannot apply market_cap filters",
                "min_market_cap_yuan": min_market_cap,
                "max_market_cap_yuan": max_market_cap,
            }
        )
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "market cap unavailable; cannot apply market_cap filters",
            "parameters": params,
            "picks": [],
            "decision_trace": decision_trace,
        }

    excluded_prefixes = ("399", "43", "83", "87", "88")
    by_code: dict[str, dict[str, dict[str, float | str | None]]] = {}
    invalid_rows = 0
    for (
        trade_date_raw,
        code,
        name,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        pct_change,
        market_cap,
    ) in rows:
        code_str = str(code)
        trade_date_str = str(trade_date_raw)
        name_str = str(name or "")
        try:
            open_f = float(cast(Any, open_price))
            high_f = float(cast(Any, high_price))
            low_f = float(cast(Any, low_price))
            close_f = float(cast(Any, close_price))
            volume_f = float(cast(Any, volume))
            pct_f = float(cast(Any, pct_change))
        except (TypeError, ValueError):
            invalid_rows += 1
            continue

        cap_f: float | None
        if market_cap is None:
            cap_f = None
        else:
            try:
                cap_f = float(cast(Any, market_cap))
            except (TypeError, ValueError):
                cap_f = None

        by_code.setdefault(code_str, {})[trade_date_str] = {
            "code": code_str,
            "name": name_str,
            "open": open_f,
            "high": high_f,
            "low": low_f,
            "close": close_f,
            "volume": volume_f,
            "pct_change": pct_f,
            "market_cap": cap_f,
        }

    if invalid_rows:
        decision_trace.append(
            {"step": "parse_rows", "status": "warn", "invalid_row_count": invalid_rows}
        )

    def is_limit_up(row: dict[str, float | str | None], prev_close: float) -> bool:
        if prev_close <= 0:
            return False
        pct = float(cast(Any, row["pct_change"]))
        code_val = str(row.get("code") or "")
        name_val = str(row.get("name") or "")
        if code_val.startswith(("300", "301", "688", "689")):
            return pct >= gem_star_limit_up_pct
        if code_val.startswith(("43", "83", "87", "88")):
            return pct >= bse_limit_up_pct
        if "ST" in name_val or "*ST" in name_val:
            return pct >= st_limit_up_pct
        return pct >= main_board_limit_up_pct

    def is_low_consolidation(
        records: list[dict[str, Any]], high_volume_idx: int
    ) -> bool:
        if high_volume_idx < consolidation_days:
            return False
        start = high_volume_idx - consolidation_days
        end = high_volume_idx
        period = records[start:end]
        if len(period) < consolidation_days:
            return False
        first_close = float(cast(Any, period[0]["close"]))
        last_close = float(cast(Any, period[-1]["close"]))
        if first_close <= 0:
            return False
        gain = (last_close - first_close) / first_close
        return abs(gain) <= max_consolidation_gain

    def find_high_volume_yang_line(records: list[dict[str, Any]]) -> int | None:
        if len(records) < high_volume_lookback + callback_max_days:
            return None
        for i in range(
            len(records) - min_days_after_high_volume, consolidation_days, -1
        ):
            row = records[i]
            if float(cast(Any, row["close"])) <= float(cast(Any, row["open"])):
                continue
            lookback = records[max(0, i - high_volume_lookback) : i]
            if not lookback:
                continue
            max_vol = max(float(cast(Any, item["volume"])) for item in lookback)
            if float(cast(Any, row["volume"])) < max_vol * high_volume_peak_tolerance:
                continue
            if not is_low_consolidation(records, i):
                continue
            return i
        return None

    def check_limit_up_and_callback(
        records: list[dict[str, Any]], high_volume_idx: int
    ) -> dict[str, Any] | None:
        if high_volume_idx >= len(records) - min_days_after_high_volume:
            return None
        hv_row = records[high_volume_idx]
        high_volume = float(cast(Any, hv_row["volume"]))
        limit_up_idx: int | None = None
        for i in range(
            high_volume_idx + 1,
            min(high_volume_idx + 1 + limit_up_search_days, len(records)),
        ):
            row = records[i]
            prev_close = float(cast(Any, records[i - 1]["close"]))
            if (
                is_limit_up(row, prev_close)
                and float(cast(Any, row["volume"])) < high_volume
            ):
                limit_up_idx = i
                break
        if limit_up_idx is None:
            return None

        lu_row = records[limit_up_idx]
        lu_high = float(cast(Any, lu_row["high"]))
        lu_low = float(cast(Any, lu_row["low"]))
        shrink_found = False
        shrink_idx: int | None = None
        min_vol = float("inf")
        breakout_row: dict[str, Any] | None = None

        for i in range(
            limit_up_idx + 1, min(limit_up_idx + 1 + callback_max_days, len(records))
        ):
            day_row = records[i]
            day_low = float(cast(Any, day_row["low"]))
            day_high = float(cast(Any, day_row["high"]))
            if day_low < lu_low or day_high > lu_high:
                break
            day_vol = float(cast(Any, day_row["volume"]))
            if day_vol < min_vol:
                min_vol = day_vol
            if day_vol < high_volume * volume_shrink_threshold:
                shrink_found = True
                shrink_idx = i
            if shrink_found and shrink_idx is not None and i > shrink_idx:
                shrink_period = records[shrink_idx:i]
                if shrink_period:
                    avg_shrink_vol = sum(
                        float(cast(Any, item["volume"])) for item in shrink_period
                    ) / float(len(shrink_period))
                    if day_vol > avg_shrink_vol * breakout_volume_ratio:
                        breakout_row = day_row
                        break

        if not shrink_found or shrink_idx is None or min_vol == float("inf"):
            return None

        result = {
            "high_volume_date": str(hv_row["trade_date"]),
            "high_volume_price": float(cast(Any, hv_row["close"])),
            "high_volume": high_volume,
            "limit_up_date": str(lu_row["trade_date"]),
            "limit_up_price": float(cast(Any, lu_row["close"])),
            "limit_up_high": lu_high,
            "limit_up_low": lu_low,
            "limit_up_volume": float(cast(Any, lu_row["volume"])),
            "callback_days": (
                (breakout_row is None and (len(records) - limit_up_idx - 1))
                if breakout_row is None
                else (int(cast(Any, breakout_row["index"])) - limit_up_idx)
            ),
            "shrink_volume_found": True,
            "shrink_volume_idx": shrink_idx,
            "min_volume_during_callback": min_vol,
            "volume_shrink_ratio": (min_vol / high_volume) if high_volume else 0.0,
            "breakout_date": (
                str(breakout_row["trade_date"]) if breakout_row is not None else None
            ),
            "breakout_price": (
                float(cast(Any, breakout_row["close"]))
                if breakout_row is not None
                else None
            ),
            "breakout_volume": (
                float(cast(Any, breakout_row["volume"]))
                if breakout_row is not None
                else None
            ),
        }
        return result

    picks_with_meta: list[dict[str, Any]] = []
    rejected_examples: list[dict[str, Any]] = []
    reject_count = 0
    for code_str, series in by_code.items():
        sample = next(iter(series.values()), None)
        name_str = str(sample.get("name") if isinstance(sample, dict) else "")

        if code_str.startswith(excluded_prefixes) or any(
            token in name_str for token in ("*ST", "ST", "PT")
        ):
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "base_exclusion", "name": name_str}
                )
            continue

        if use_market_cap_filter:
            cap = (
                series.get(day_key, {}).get("market_cap") if day_key in series else None
            )
            if cap is None:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "missing_market_cap",
                            "min_market_cap_yuan": min_market_cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue
            if not isinstance(cap, float):
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {"code": code_str, "reason": "invalid_market_cap", "value": cap}
                    )
                continue
            if min_market_cap is not None and cap < min_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_below_threshold",
                            "market_cap_yuan": cap,
                            "min_market_cap_yuan": min_market_cap,
                        }
                    )
                continue
            if max_market_cap is not None and cap > max_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_above_threshold",
                            "market_cap_yuan": cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue

        missing_dates = [d for d in dates_needed if d not in series]
        if missing_dates:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {
                        "code": code_str,
                        "reason": "missing_required_days",
                        "missing_count": len(missing_dates),
                    }
                )
            continue

        records: list[dict[str, Any]] = []
        for d in dates_needed:
            row = dict(series[d])
            row["trade_date"] = d
            records.append(row)
        for i, row in enumerate(records):
            row["index"] = i

        hv_idx = find_high_volume_yang_line(records)
        if hv_idx is None:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "high_volume_yang_line_not_found"}
                )
            continue
        pattern = check_limit_up_and_callback(records, hv_idx)
        if pattern is None:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {
                        "code": code_str,
                        "reason": "limit_up_callback_pattern_not_found",
                        "high_volume_date": str(records[hv_idx]["trade_date"]),
                    }
                )
            continue

        latest = records[-1]
        picks_with_meta.append(
            {
                "code": code_str,
                "name": name_str,
                "current_price": float(cast(Any, latest["close"])),
                "current_change": float(cast(Any, latest["pct_change"])),
                "high_volume_date": pattern["high_volume_date"],
                "limit_up_date": pattern["limit_up_date"],
                "volume_shrink_ratio": float(cast(Any, pattern["volume_shrink_ratio"])),
                "breakout_date": pattern.get("breakout_date"),
            }
        )

    decision_trace.append(
        {
            "step": "evaluate",
            "status": "ok",
            "lookback_days": lookback_days,
            "min_history_days": min_history_days,
            "consolidation_days": consolidation_days,
            "high_volume_lookback": high_volume_lookback,
            "callback_max_days": callback_max_days,
            "limit_up_search_days": limit_up_search_days,
            "min_days_after_high_volume": min_days_after_high_volume,
            "breakout_volume_ratio": breakout_volume_ratio,
            "max_consolidation_gain": max_consolidation_gain,
            "volume_shrink_threshold": volume_shrink_threshold,
            "high_volume_peak_tolerance": high_volume_peak_tolerance,
            "main_board_limit_up_pct": main_board_limit_up_pct,
            "gem_star_limit_up_pct": gem_star_limit_up_pct,
            "bse_limit_up_pct": bse_limit_up_pct,
            "st_limit_up_pct": st_limit_up_pct,
            "passed_count": len(picks_with_meta),
            "rejected_count": reject_count,
            "rejected_examples": rejected_examples,
        }
    )

    def _rank_key(item: dict[str, Any]) -> tuple[int, float]:
        has_breakout = 1 if item.get("breakout_date") else 0
        shrink_ratio = float(item.get("volume_shrink_ratio") or 0.0)
        return (has_breakout, -shrink_ratio)

    picks_with_meta.sort(key=_rank_key, reverse=True)
    picks = [item["code"] for item in picks_with_meta[:top_n]]
    decision_trace.append(
        {
            "step": "rank_and_select",
            "status": "ok",
            "top_n": top_n,
            "picked_count": len(picks),
            "picked_examples": picks_with_meta[: min(5, len(picks_with_meta))],
        }
    )

    return {
        "screener_id": screener_id,
        "target_date": day_key,
        "status": "ok",
        "message": "shi_pan_xian: low consolidation -> high-volume yang -> limit-up (lower volume) -> shrink callback within limit-up range -> breakout volume.",
        "parameters": params,
        "picks": picks,
        "decision_trace": decision_trace,
    }


def run_cup_handle_v4(
    *, screener_id: str, target_date: date, parameters: dict[str, Any] | None = None
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]
    db_path = Path(
        os.environ.get("NEOTRADE3_STOCK_DB_PATH")
        or project_root / "var/db/stock_data.db"
    ).expanduser()
    params = parameters or {}
    raw_trace_code = params.get("trace_code")
    trace_code = str(raw_trace_code or "").strip().split(".", 1)[0]

    universe_filters = params.get("universe_filters")
    min_market_cap = None
    max_market_cap = None
    if isinstance(universe_filters, dict):
        raw_min_market_cap = universe_filters.get("min_market_cap")
        if raw_min_market_cap is not None:
            try:
                min_market_cap = float(raw_min_market_cap)
            except (TypeError, ValueError):
                min_market_cap = None
        raw_max_market_cap = universe_filters.get("max_market_cap")
        if raw_max_market_cap is not None:
            try:
                max_market_cap = float(raw_max_market_cap)
            except (TypeError, ValueError):
                max_market_cap = None

    use_market_cap_filter = (min_market_cap is not None) or (max_market_cap is not None)

    def _get_int(key: str, default: int) -> int:
        raw = params.get(key, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default
        return value if value >= 0 else default

    def _get_pos_int(key: str, default: int) -> int:
        value = _get_int(key, default)
        return value if value > 0 else default

    def _get_float(key: str, default: float) -> float:
        raw = params.get(key, default)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    rim_interval_min = _get_pos_int("rim_interval_min", 45)
    rim_interval_max = _get_pos_int("rim_interval_max", 250)
    rim_price_match_pct = _get_float("rim_price_match_pct", 0.05)
    right_rim_search_days = _get_pos_int("right_rim_search_days", 13)
    history_buffer_days = _get_int("history_buffer_days", 50)

    cup_depth_min = _get_float("cup_depth_min", 0.05)
    cup_depth_max = _get_float("cup_depth_max", 0.70)

    rapid_decline_days = _get_pos_int("rapid_decline_days", 12)
    rapid_ascent_days = _get_pos_int("rapid_ascent_days", 12)

    handle_period_min = _get_int("handle_period_min", 1)
    handle_period_max = _get_pos_int("handle_period_max", 13)

    ma5_trend_days = _get_pos_int("ma5_trend_days", 14)
    ma_trend_window = _get_pos_int("ma_trend_window", 5)
    ma_trend_min_valid_points = _get_pos_int("ma_trend_min_valid_points", 10)

    decline_amount_max_ratio = _get_float("decline_amount_max_ratio", 0.5)
    safety_level_depth_ratio = _get_float("safety_level_depth_ratio", 0.5)
    recent_low_lookback_days = _get_pos_int("recent_low_lookback_days", 18)

    handle_period_min = max(0, int(handle_period_min))
    handle_period_max = max(handle_period_min, int(handle_period_max))
    right_rim_search_days = max(1, int(right_rim_search_days))
    history_buffer_days = max(0, int(history_buffer_days))
    ma_trend_window = max(1, int(ma_trend_window))
    ma_trend_min_valid_points = max(1, int(ma_trend_min_valid_points))
    decline_amount_max_ratio = max(0.0, float(decline_amount_max_ratio))
    safety_level_depth_ratio = max(0.0, float(safety_level_depth_ratio))
    rim_price_match_pct = max(0.0, float(rim_price_match_pct))

    raw_top_n = params.get("top_n", 50)
    try:
        top_n = int(raw_top_n)
    except (TypeError, ValueError):
        top_n = 50
    if top_n <= 0:
        top_n = 50

    decision_trace: list[dict[str, Any]] = []
    if not db_path.exists() or not db_path.is_file():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "stock db not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "open_db",
                    "status": "failed",
                    "reason": f"db_path missing: {db_path}",
                }
            ],
        }

    calendar_path = project_root / "var/ledgers/trading_calendar/trading_calendar.json"
    if not calendar_path.exists():
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "trading calendar not found",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"calendar missing: {calendar_path}",
                }
            ],
        }

    try:
        calendar_payload = json.loads(calendar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "failed to read trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": str(exc),
                }
            ],
        }

    trading_days = (
        calendar_payload.get("trading_days")
        if isinstance(calendar_payload, dict)
        else None
    )
    if not isinstance(trading_days, list) or not all(
        isinstance(item, str) for item in trading_days
    ):
        return {
            "screener_id": screener_id,
            "target_date": target_date.isoformat(),
            "status": "failed",
            "message": "invalid trading calendar payload",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": "trading_days missing or invalid",
                }
            ],
        }

    day_key = target_date.isoformat()
    try:
        idx = trading_days.index(day_key)
    except ValueError:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "target_date not in trading calendar",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "load_trading_calendar",
                    "status": "failed",
                    "reason": f"target_date not found: {day_key}",
                }
            ],
        }

    lookback_days = (
        rim_interval_max
        + rapid_decline_days
        + rapid_ascent_days
        + right_rim_search_days
        + history_buffer_days
    )
    window_start = max(0, idx - (lookback_days - 1))
    dates_needed = trading_days[window_start : idx + 1]
    if len(dates_needed) < lookback_days:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "insufficient history for cup_handle_v4",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {
                    "step": "select_trade_days",
                    "status": "failed",
                    "lookback_days": lookback_days,
                    "days_loaded": len(dates_needed),
                }
            ],
        }

    decision_trace.append(
        {
            "step": "select_trade_days",
            "status": "ok",
            "target_date": day_key,
            "lookback_days": lookback_days,
            "window_start": dates_needed[0],
            "window_end": day_key,
            "days_loaded": len(dates_needed),
        }
    )

    try:
        conn = sqlite3.connect(str(db_path))
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "failed to open sqlite db",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "open_db", "status": "failed", "reason": str(exc)}
            ],
        }

    try:
        cursor = conn.cursor()
        start_date = dates_needed[0]
        end_date = dates_needed[-1]
        sql_with_cap = (
            "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
            "dp.open, dp.high, dp.low, dp.close, dp.pct_change, dp.amount, "
            "s.circulating_market_cap "
            "FROM daily_prices dp "
            "JOIN stocks s ON s.code = dp.code "
            "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
            "AND COALESCE(s.asset_type, 'stock') = 'stock' "
            "AND COALESCE(s.is_delisted, 0) = 0"
        )
        sql_no_cap = (
            "SELECT dp.trade_date, dp.code, COALESCE(s.name,''), "
            "dp.open, dp.high, dp.low, dp.close, dp.pct_change, dp.amount, "
            "NULL "
            "FROM daily_prices dp "
            "JOIN stocks s ON s.code = dp.code "
            "WHERE dp.trade_date >= ? AND dp.trade_date <= ? "
            "AND COALESCE(s.asset_type, 'stock') = 'stock' "
            "AND COALESCE(s.is_delisted, 0) = 0"
        )
        rows: list[
            tuple[
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
                object,
            ]
        ] = []
        has_market_cap = False
        last_exc: Exception | None = None
        for sql, cap_flag in ((sql_with_cap, True), (sql_no_cap, False)):
            try:
                cursor.execute(sql, (start_date, end_date))
                rows = cursor.fetchall()
                has_market_cap = cap_flag
                break
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None and not rows:
            raise last_exc
    except Exception as exc:
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "query failed",
            "parameters": params,
            "picks": [],
            "decision_trace": [
                {"step": "query", "status": "failed", "reason": str(exc)}
            ],
        }
    finally:
        conn.close()

    decision_trace.append(
        {
            "step": "query",
            "status": "ok",
            "row_count": len(rows),
            "has_market_cap": has_market_cap,
        }
    )
    if use_market_cap_filter and not has_market_cap:
        decision_trace.append(
            {
                "step": "validate_schema",
                "status": "failed",
                "reason": "market_cap column unavailable; cannot apply market_cap filters",
                "min_market_cap_yuan": min_market_cap,
                "max_market_cap_yuan": max_market_cap,
            }
        )
        return {
            "screener_id": screener_id,
            "target_date": day_key,
            "status": "failed",
            "message": "market cap unavailable; cannot apply market_cap filters",
            "parameters": params,
            "picks": [],
            "decision_trace": decision_trace,
        }

    excluded_prefixes = ("399", "43", "83", "87", "88")
    by_code: dict[str, dict[str, dict[str, float | str | None]]] = {}
    invalid_rows = 0
    for (
        trade_date_raw,
        code,
        name,
        open_price,
        high_price,
        low_price,
        close_price,
        pct_change,
        amount,
        market_cap,
    ) in rows:
        code_str = str(code)
        trade_date_str = str(trade_date_raw)
        name_str = str(name or "")
        try:
            open_f = float(cast(Any, open_price))
            high_f = float(cast(Any, high_price))
            low_f = float(cast(Any, low_price))
            close_f = float(cast(Any, close_price))
            pct_f = float(cast(Any, pct_change))
            amount_f = float(cast(Any, amount))
        except (TypeError, ValueError):
            invalid_rows += 1
            continue

        cap_f: float | None
        if market_cap is None:
            cap_f = None
        else:
            try:
                cap_f = float(cast(Any, market_cap))
            except (TypeError, ValueError):
                cap_f = None

        by_code.setdefault(code_str, {})[trade_date_str] = {
            "code": code_str,
            "name": name_str,
            "open": open_f,
            "high": high_f,
            "low": low_f,
            "close": close_f,
            "pct_change": pct_f,
            "amount": amount_f,
            "market_cap": cap_f,
        }

    if invalid_rows:
        decision_trace.append(
            {"step": "parse_rows", "status": "warn", "invalid_row_count": invalid_rows}
        )

    def check_ma5_trend(
        records: list[dict[str, Any]], left_rim_idx: int
    ) -> tuple[bool, str]:
        trend_days = max(int(ma_trend_window), int(ma5_trend_days))
        trend_start = max(0, left_rim_idx - trend_days)
        trend_period = records[trend_start:left_rim_idx]
        if len(trend_period) < trend_days:
            return False, f"数据不足{trend_days}天"
        closes = [float(cast(Any, item["close"])) for item in trend_period]
        if ma_trend_window > len(closes):
            return False, "MA5数据不足"
        ma5_values: list[float] = []
        window_sum = sum(closes[:ma_trend_window])
        ma5_values.append(window_sum / float(ma_trend_window))
        for i in range(ma_trend_window, len(closes)):
            window_sum += closes[i] - closes[i - ma_trend_window]
            ma5_values.append(window_sum / float(ma_trend_window))
        if len(ma5_values) < ma_trend_min_valid_points:
            return False, "MA5数据不足"
        half = len(ma5_values) // 2
        if half <= 0:
            return False, "MA5数据不足"
        first_half_mean = sum(ma5_values[:half]) / float(half)
        second_half_mean = sum(ma5_values[half:]) / float(len(ma5_values) - half)
        if second_half_mean > first_half_mean:
            improvement = (
                ((second_half_mean - first_half_mean) / first_half_mean) * 100.0
                if first_half_mean
                else 0.0
            )
            return (
                True,
                f"MA5上升趋势（后半段均值{second_half_mean:.2f} > 前半段{first_half_mean:.2f}，提升{improvement:.2f}%）",
            )
        decline = (
            ((first_half_mean - second_half_mean) / first_half_mean) * 100.0
            if first_half_mean
            else 0.0
        )
        return (
            False,
            f"MA5无上升趋势（后半段均值{second_half_mean:.2f} <= 前半段{first_half_mean:.2f}，下降{decline:.2f}%）",
        )

    def round1_find_right_rim(
        records: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, str | None]:
        latest_idx = len(records) - 1
        search_start = max(0, latest_idx - right_rim_search_days)
        right_rim_idx = None
        right_rim_price = None
        for i in range(search_start, latest_idx + 1):
            high_val = float(cast(Any, records[i]["high"]))
            if right_rim_price is None or high_val > right_rim_price:
                right_rim_price = high_val
                right_rim_idx = i
        if right_rim_idx is None or right_rim_price is None:
            return None, "第1轮失败：未找到右侧杯沿"
        handle_length = latest_idx - right_rim_idx
        if handle_length > handle_period_max:
            return None, f"第1轮：杯柄过长（{handle_length}天 > {handle_period_max}天）"
        if handle_length > 0 and handle_length < handle_period_min:
            return None, f"第1轮：杯柄过短（{handle_length}天 < {handle_period_min}天）"
        return (
            {
                "right_rim_idx": right_rim_idx,
                "right_rim_price": float(right_rim_price),
                "handle_length": handle_length,
                "latest_idx": latest_idx,
            },
            None,
        )

    def round2_find_left_rim(
        records: list[dict[str, Any]], r1: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        right_rim_idx = int(cast(Any, r1["right_rim_idx"]))
        right_rim_price = float(cast(Any, r1["right_rim_price"]))

        check_start_idx = max(0, right_rim_idx - rim_interval_min)
        for i in range(check_start_idx, right_rim_idx):
            if float(cast(Any, records[i]["high"])) >= right_rim_price:
                return (
                    None,
                    f"第2轮：右杯沿前{rim_interval_min}天内出现更高/相等高点，右沿不成立",
                )

        search_start = max(0, right_rim_idx - rim_interval_min)
        search_end = max(0, right_rim_idx - rim_interval_max)
        if search_start <= search_end:
            return (
                None,
                f"第2轮：左杯沿搜索区间无效（start={search_start}, end={search_end}）",
            )

        price_match_failed = 0
        local_peak_failed = 0
        rim_interval_failed = 0
        ma5_failed = 0
        last_ma5_reason: str | None = None

        for left_rim_idx in range(search_start, search_end - 1, -1):
            left_rim_price = float(cast(Any, records[left_rim_idx]["high"]))
            if right_rim_price <= 0:
                return None, "第2轮：右杯沿价格无效"
            price_diff_pct = abs(right_rim_price - left_rim_price) / right_rim_price
            if price_diff_pct > rim_price_match_pct:
                price_match_failed += 1
                continue

            local_window_start = max(0, left_rim_idx - 5)
            local_window_end = min(len(records) - 1, left_rim_idx + 5)
            local_high = max(
                float(cast(Any, records[j]["high"]))
                for j in range(local_window_start, local_window_end + 1)
            )
            if left_rim_price < local_high - 0.001:
                local_peak_failed += 1
                continue

            rim_interval = right_rim_idx - left_rim_idx
            if rim_interval < rim_interval_min or rim_interval > rim_interval_max:
                rim_interval_failed += 1
                continue

            ma5_passed, ma5_reason = check_ma5_trend(records, left_rim_idx)
            if not ma5_passed:
                ma5_failed += 1
                last_ma5_reason = ma5_reason
                continue

            result = dict(r1)
            result.update(
                {
                    "left_rim_idx": left_rim_idx,
                    "left_rim_price": float(left_rim_price),
                    "rim_interval": rim_interval,
                    "ma5_passed": True,
                    "ma5_reason": ma5_reason,
                }
            )
            return result, None

        if ma5_failed > 0 and last_ma5_reason:
            return None, f"第2轮：MA5趋势不满足（{last_ma5_reason}）"
        if rim_interval_failed > 0:
            return (
                None,
                f"第2轮：杯沿间隔不满足范围[{rim_interval_min}, {rim_interval_max}]",
            )
        if local_peak_failed > 0:
            return None, "第2轮：候选左杯沿不是局部高点"
        if price_match_failed > 0:
            return None, f"第2轮：左/右杯沿价格偏差超过{rim_price_match_pct * 100:.1f}%"
        return None, "第2轮：未找到满足条件的左杯沿"

    def round3_validate_cup_depth(
        records: list[dict[str, Any]], r2: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        left_rim_idx = int(cast(Any, r2["left_rim_idx"]))
        left_rim_price = float(cast(Any, r2["left_rim_price"]))
        right_rim_idx = int(cast(Any, r2["right_rim_idx"]))
        if left_rim_price <= 0:
            return None, "第3轮：左杯沿价格无效"
        cup_bottom_price = min(
            float(cast(Any, records[i]["low"]))
            for i in range(left_rim_idx, right_rim_idx + 1)
        )
        cup_depth = (left_rim_price - cup_bottom_price) / left_rim_price
        if cup_depth < cup_depth_min:
            return (
                None,
                f"第3轮：杯深过浅（{cup_depth * 100:.1f}% < {cup_depth_min * 100:.1f}%）",
            )
        if cup_depth > cup_depth_max:
            return (
                None,
                f"第3轮：杯深过深（{cup_depth * 100:.1f}% > {cup_depth_max * 100:.1f}%）",
            )
        result = dict(r2)
        result.update(
            {"cup_bottom_price": float(cup_bottom_price), "cup_depth": float(cup_depth)}
        )
        return result, None

    def round4_validate_pattern(
        records: list[dict[str, Any]], r3: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        left_rim_idx = int(cast(Any, r3["left_rim_idx"]))
        right_rim_idx = int(cast(Any, r3["right_rim_idx"]))
        right_rim_price = float(cast(Any, r3["right_rim_price"]))
        latest_idx = int(cast(Any, r3["latest_idx"]))
        handle_length = int(cast(Any, r3["handle_length"]))

        decline_end_idx = left_rim_idx + rapid_decline_days - 1
        ascent_start_idx = right_rim_idx - rapid_ascent_days + 1

        if decline_end_idx >= right_rim_idx:
            return (
                None,
                f"第4轮：阶段索引无效（下跌结束{decline_end_idx} >= 右沿{right_rim_idx}）",
            )
        if ascent_start_idx <= decline_end_idx:
            return (
                None,
                f"第4轮：阶段重叠（上涨开始{ascent_start_idx} <= 下跌结束{decline_end_idx}）",
            )
        if ascent_start_idx < left_rim_idx:
            return (
                None,
                f"第4轮：上涨起点越界（{ascent_start_idx} < 左沿{left_rim_idx}）",
            )

        if handle_length > 0:
            handle_closes = [
                float(cast(Any, records[i]["close"]))
                for i in range(right_rim_idx + 1, latest_idx + 1)
            ]
            handle_low = min(handle_closes) if handle_closes else float(right_rim_price)
            if right_rim_price <= 0:
                return None, "第4轮：右杯沿价格无效，无法计算杯柄回撤"
            handle_drop = max(0.0, (right_rim_price - handle_low) / right_rim_price)
        else:
            handle_low = float(right_rim_price)
            handle_drop = 0.0

        decline_amounts = [
            float(cast(Any, records[i]["amount"]))
            for i in range(left_rim_idx, decline_end_idx + 1)
        ]
        ascent_amounts = [
            float(cast(Any, records[i]["amount"]))
            for i in range(ascent_start_idx, right_rim_idx + 1)
        ]
        if not decline_amounts:
            return None, "第4轮：快速下跌期数据为空"
        if not ascent_amounts:
            return None, "第4轮：快速上涨期数据为空"
        decline_total_amt = sum(decline_amounts)
        ascent_total_amt = sum(ascent_amounts)
        if decline_total_amt <= 0:
            return None, f"第4轮：快速下跌阶段成交额无效（{decline_total_amt:.2f}）"
        decline_amount_limit = ascent_total_amt * decline_amount_max_ratio
        if decline_total_amt >= decline_amount_limit:
            return (
                None,
                f"第4轮：快速下跌总成交额不满足（{decline_total_amt:.2f} >= {decline_amount_limit:.2f}）",
            )
        amount_ratio = ascent_total_amt / decline_total_amt
        result = dict(r3)
        result.update(
            {
                "handle_low": float(handle_low),
                "handle_drop": float(handle_drop),
                "amount_ratio": float(amount_ratio),
            }
        )
        return result, None

    def round5_validate_current_price(
        records: list[dict[str, Any]], r4: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        latest_idx = int(cast(Any, r4["latest_idx"]))
        right_rim_idx = int(cast(Any, r4["right_rim_idx"]))
        left_rim_price = float(cast(Any, r4["left_rim_price"]))
        cup_bottom_price = float(cast(Any, r4["cup_bottom_price"]))
        handle_length = int(cast(Any, r4["handle_length"]))

        latest_price = float(cast(Any, records[latest_idx]["close"]))
        if handle_length == 0:
            result = dict(r4)
            result["latest_price"] = float(latest_price)
            return result, None

        safety_level = (
            cup_bottom_price
            + (left_rim_price - cup_bottom_price) * safety_level_depth_ratio
        )
        middle_closes = [
            float(cast(Any, records[i]["close"]))
            for i in range(right_rim_idx + 1, latest_idx)
        ]
        if middle_closes:
            middle_min_close = min(middle_closes)
            if middle_min_close < safety_level:
                return (
                    None,
                    f"第5轮：中间区间收盘价跌破安全水位（{middle_min_close:.2f} < {safety_level:.2f}）",
                )

        recent_start_idx = max(0, latest_idx - (recent_low_lookback_days - 1))
        recent_closes = [
            float(cast(Any, records[i]["close"]))
            for i in range(recent_start_idx, latest_idx + 1)
        ]
        recent_low = min(recent_closes) if recent_closes else latest_price
        if latest_price <= recent_low and latest_price < safety_level:
            return None, (
                f"第5轮：当前日创{recent_low_lookback_days}天新低且跌破安全水位（{latest_price:.2f} <= {recent_low:.2f} 且 < {safety_level:.2f}）"
            )
        result = dict(r4)
        result["latest_price"] = float(latest_price)
        return result, None

    picks_with_meta: list[dict[str, Any]] = []
    rejected_examples: list[dict[str, Any]] = []
    reject_count = 0

    for code_str, series in by_code.items():
        sample = next(iter(series.values()), None)
        name_str = str(sample.get("name") if isinstance(sample, dict) else "")

        if code_str.startswith(excluded_prefixes) or any(
            token in name_str for token in ("*ST", "ST", "PT")
        ):
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "base_exclusion", "name": name_str}
                )
            continue

        if use_market_cap_filter:
            cap = (
                series.get(day_key, {}).get("market_cap") if day_key in series else None
            )
            if cap is None:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "missing_market_cap",
                            "min_market_cap_yuan": min_market_cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue
            if not isinstance(cap, float):
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {"code": code_str, "reason": "invalid_market_cap", "value": cap}
                    )
                continue
            if min_market_cap is not None and cap < min_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_below_threshold",
                            "market_cap_yuan": cap,
                            "min_market_cap_yuan": min_market_cap,
                        }
                    )
                continue
            if max_market_cap is not None and cap > max_market_cap:
                reject_count += 1
                if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                    rejected_examples.append(
                        {
                            "code": code_str,
                            "reason": "market_cap_above_threshold",
                            "market_cap_yuan": cap,
                            "max_market_cap_yuan": max_market_cap,
                        }
                    )
                continue

        missing_dates = [d for d in dates_needed if d not in series]
        if missing_dates:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {
                        "code": code_str,
                        "reason": "missing_required_days",
                        "missing_count": len(missing_dates),
                    }
                )
            continue

        records: list[dict[str, Any]] = []
        for d in dates_needed:
            row = dict(series[d])
            row["trade_date"] = d
            records.append(row)

        r1, reason = round1_find_right_rim(records)
        if r1 is None:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "round1_failed", "detail": reason}
                )
            continue

        r2, reason = round2_find_left_rim(records, r1)
        if r2 is None:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "round2_failed", "detail": reason}
                )
            continue

        r3, reason = round3_validate_cup_depth(records, r2)
        if r3 is None:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "round3_failed", "detail": reason}
                )
            continue

        r4, reason = round4_validate_pattern(records, r3)
        if r4 is None:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "round4_failed", "detail": reason}
                )
            continue

        r5, reason = round5_validate_current_price(records, r4)
        if r5 is None:
            reject_count += 1
            if len(rejected_examples) < 5 or (trace_code and code_str == trace_code):
                rejected_examples.append(
                    {"code": code_str, "reason": "round5_failed", "detail": reason}
                )
            continue

        picks_with_meta.append(
            {
                "code": code_str,
                "name": name_str,
                "left_rim_idx": int(cast(Any, r5["left_rim_idx"])),
                "left_rim_price": float(cast(Any, r5["left_rim_price"])),
                "right_rim_idx": int(cast(Any, r5["right_rim_idx"])),
                "right_rim_price": float(cast(Any, r5["right_rim_price"])),
                "rim_interval": int(cast(Any, r5["rim_interval"])),
                "cup_bottom_price": float(cast(Any, r5["cup_bottom_price"])),
                "cup_depth": float(cast(Any, r5["cup_depth"])),
                "handle_length": int(cast(Any, r5["handle_length"])),
                "handle_low": float(cast(Any, r5.get("handle_low") or 0.0)),
                "handle_drop": float(cast(Any, r5.get("handle_drop") or 0.0)),
                "amount_ratio": float(cast(Any, r5.get("amount_ratio") or 0.0)),
                "latest_price": float(cast(Any, r5.get("latest_price") or 0.0)),
                "ma5_reason": str(r5.get("ma5_reason") or ""),
            }
        )

    decision_trace.append(
        {
            "step": "evaluate",
            "status": "ok",
            "lookback_days": lookback_days,
            "rim_interval_min": rim_interval_min,
            "rim_interval_max": rim_interval_max,
            "rim_price_match_pct": rim_price_match_pct,
            "right_rim_search_days": right_rim_search_days,
            "history_buffer_days": history_buffer_days,
            "cup_depth_min": cup_depth_min,
            "cup_depth_max": cup_depth_max,
            "rapid_decline_days": rapid_decline_days,
            "rapid_ascent_days": rapid_ascent_days,
            "handle_period_min": handle_period_min,
            "handle_period_max": handle_period_max,
            "ma5_trend_days": ma5_trend_days,
            "ma_trend_window": ma_trend_window,
            "ma_trend_min_valid_points": ma_trend_min_valid_points,
            "decline_amount_max_ratio": decline_amount_max_ratio,
            "safety_level_depth_ratio": safety_level_depth_ratio,
            "recent_low_lookback_days": recent_low_lookback_days,
            "passed_count": len(picks_with_meta),
            "rejected_count": reject_count,
            "rejected_examples": rejected_examples,
        }
    )

    picks_with_meta.sort(
        key=lambda item: float(cast(Any, item.get("amount_ratio") or 0.0)), reverse=True
    )
    picks = [item["code"] for item in picks_with_meta[:top_n]]
    decision_trace.append(
        {
            "step": "rank_and_select",
            "status": "ok",
            "top_n": top_n,
            "picked_count": len(picks),
            "picked_examples": picks_with_meta[: min(5, len(picks_with_meta))],
        }
    )

    return {
        "screener_id": screener_id,
        "target_date": day_key,
        "status": "ok",
        "message": "cup_handle_v4: 5-round pattern (right rim, left rim + MA5, cup depth, amount structure, price safety checks).",
        "parameters": params,
        "picks": picks,
        "decision_trace": decision_trace,
    }
