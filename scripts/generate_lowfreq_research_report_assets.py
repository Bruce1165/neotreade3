#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16, TradeRecord


def run_backtest_with_daily_values(
    *,
    engine: LowFreqTradingEngineV16,
    start: date,
    end: date,
    initial_capital: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[TradeRecord]]:
    trading_dates = engine._get_trading_dates(start, end)
    capital = float(initial_capital)
    positions: dict[str, TradeRecord] = {}
    trades: list[TradeRecord] = []
    daily_values: list[dict[str, Any]] = []

    pending_buy_attempts: dict[str, dict[str, Any]] = {}
    pending_sell_signals: dict[str, dict[str, Any]] = {}

    conn = engine._conn()
    try:
        cur = conn.cursor()
        name_cache: dict[str, str] = {}
        limit_cache: dict[str, float] = {}
        pct_cache: dict[tuple[str, str], float] = {}

        def stock_name(code: str) -> str:
            code = str(code or "").strip()
            if code in name_cache:
                return name_cache[code]
            try:
                cur.execute("SELECT name FROM stocks WHERE code = ?", (code,))
                row = cur.fetchone()
                name = str(row[0]) if row and row[0] else ""
            except Exception:
                name = ""
            name_cache[code] = name
            return name

        def limit_pct(code: str) -> float:
            code = str(code or "").strip()
            if code in limit_cache:
                return limit_cache[code]
            name = stock_name(code)
            if "ST" in name.upper():
                limit = 4.8
            elif code.startswith("688") or code.startswith("300"):
                limit = 19.8
            else:
                limit = 9.8
            limit_cache[code] = float(limit)
            return float(limit)

        def pct_change(code: str, d: date):
            key = (str(code or "").strip(), d.isoformat())
            if key in pct_cache:
                return pct_cache[key]
            try:
                cur.execute(
                    "SELECT pct_change FROM daily_prices WHERE code = ? AND trade_date = ?",
                    key,
                )
                row = cur.fetchone()
                if row and row[0] is not None:
                    val = float(row[0])
                    pct_cache[key] = val
                    return val
            except Exception:
                return None
            return None

        def is_limit_up(code: str, d: date) -> bool:
            pct = pct_change(code, d)
            if pct is None:
                return False
            return float(pct) >= float(limit_pct(code))

        def is_limit_down(code: str, d: date) -> bool:
            pct = pct_change(code, d)
            if pct is None:
                return False
            return float(pct) <= -float(limit_pct(code))

        def close_trade(*, code: str, trade: TradeRecord, d: date, sell_reason: str) -> None:
            nonlocal capital
            sell_price = engine._get_price(code, d)
            if not sell_price:
                return
            ret = (float(sell_price) - trade.buy_price) / max(trade.buy_price, 1e-9) * 100.0
            capital += float(sell_price) * trade.shares
            trade.sell_date = d.isoformat()
            trade.sell_price = float(sell_price)
            trade.return_pct = round(ret, 2)
            trade.hold_days = engine._count_trading_days(date.fromisoformat(trade.buy_date), d)
            trade.sell_reason = sell_reason
            trade.status = "closed"
            trades.append(trade)
            positions.pop(code, None)

        for i, current_date in enumerate(trading_dates):
            for code, payload in list(pending_sell_signals.items()):
                if code not in positions:
                    pending_sell_signals.pop(code, None)
                    continue
                if is_limit_down(code, current_date):
                    continue
                trade = positions.get(code)
                if trade is None:
                    pending_sell_signals.pop(code, None)
                    continue
                first_date = str(payload.get("first_date") or "")
                details = str(payload.get("details") or "离场信号")
                reason = (
                    f"{details}（跌停顺延，自{first_date}）"
                    if first_date
                    else f"{details}（跌停顺延）"
                )
                close_trade(code=code, trade=trade, d=current_date, sell_reason=reason)
                pending_sell_signals.pop(code, None)

            for code, trade in list(positions.items()):
                if code in pending_sell_signals:
                    continue
                sell = engine.check_sell_signal_v2(trade, current_date)
                if not sell:
                    continue
                if is_limit_down(code, current_date):
                    pending_sell_signals[code] = {
                        "first_date": current_date.isoformat(),
                        "details": str(getattr(sell, "details", "") or "离场信号"),
                    }
                    continue
                close_trade(
                    code=code,
                    trade=trade,
                    d=current_date,
                    sell_reason=str(getattr(sell, "details", "") or "离场信号"),
                )

            for code, payload in list(pending_buy_attempts.items()):
                if code in positions:
                    pending_buy_attempts.pop(code, None)
                    continue
                slots = int(engine.MAX_POSITIONS) - len(positions)
                if slots <= 0:
                    continue
                remaining = int(payload.get("remaining") or 0)
                if remaining <= 0:
                    pending_buy_attempts.pop(code, None)
                    continue
                if is_limit_up(code, current_date):
                    payload["remaining"] = remaining - 1
                    if int(payload.get("remaining") or 0) <= 0:
                        pending_buy_attempts.pop(code, None)
                    continue
                sig = payload.get("sig") if isinstance(payload.get("sig"), dict) else {}
                price = engine._get_price(code, current_date)
                if not price or float(price) <= 0:
                    payload["remaining"] = remaining - 1
                    if int(payload.get("remaining") or 0) <= 0:
                        pending_buy_attempts.pop(code, None)
                    continue
                per_slot = capital / max(slots, 1)
                shares = int(per_slot / float(price) / 100) * 100
                if shares >= 100 and shares * float(price) <= capital:
                    capital -= shares * float(price)
                    positions[code] = TradeRecord(
                        code=code,
                        name=str(sig.get("name") or ""),
                        sector=str(sig.get("sector") or ""),
                        buy_date=current_date.isoformat(),
                        buy_price=float(price),
                        shares=shares,
                        buy_score=float(sig.get("buy_score") or 0.0),
                        wave_phase=str(sig.get("wave_phase") or ""),
                        peak_price=float(price),
                        role=str(sig.get("role") or ""),
                        status="open",
                    )
                    pending_buy_attempts.pop(code, None)
                else:
                    payload["remaining"] = remaining - 1
                    if int(payload.get("remaining") or 0) <= 0:
                        pending_buy_attempts.pop(code, None)

            if i % int(engine.REBALANCE_DAYS) == 0 and len(positions) < int(engine.MAX_POSITIONS):
                signals = engine.generate_buy_signals(current_date)
                raw = signals.get("buy_signals", []) if isinstance(signals, dict) else []
                for sig in raw:
                    if not isinstance(sig, dict):
                        continue
                    code = str(sig.get("code") or "").strip()
                    if not code or code in positions or code in pending_buy_attempts:
                        continue
                    slots = int(engine.MAX_POSITIONS) - len(positions)
                    if slots <= 0:
                        break
                    if is_limit_up(code, current_date):
                        pending_buy_attempts[code] = {
                            "sig": sig,
                            "first_date": current_date.isoformat(),
                            "remaining": 3,
                        }
                        continue
                    price = engine._get_price(code, current_date)
                    if not price or float(price) <= 0:
                        continue
                    per_slot = capital / max(slots, 1)
                    shares = int(per_slot / float(price) / 100) * 100
                    if shares >= 100 and shares * float(price) <= capital:
                        capital -= shares * float(price)
                        positions[code] = TradeRecord(
                            code=code,
                            name=str(sig.get("name") or ""),
                            sector=str(sig.get("sector") or ""),
                            buy_date=current_date.isoformat(),
                            buy_price=float(price),
                            shares=shares,
                            buy_score=float(sig.get("buy_score") or 0.0),
                            wave_phase=str(sig.get("wave_phase") or ""),
                            peak_price=float(price),
                            role=str(sig.get("role") or ""),
                            status="open",
                        )

            pos_value = sum(
                (engine._get_price(code, current_date) or pos.buy_price) * pos.shares
                for code, pos in positions.items()
            )
            total = capital + float(pos_value)
            daily_values.append(
                {
                    "date": current_date.isoformat(),
                    "total_value": round(total, 2),
                    "positions": len(positions),
                }
            )

        if trading_dates:
            last_day = trading_dates[-1]
            for code, trade in list(positions.items()):
                sell_price = engine._get_price(code, last_day)
                if sell_price:
                    ret = (float(sell_price) - trade.buy_price) / max(trade.buy_price, 1e-9) * 100.0
                    capital += float(sell_price) * trade.shares
                    trade.sell_date = last_day.isoformat()
                    trade.sell_price = float(sell_price)
                    trade.return_pct = round(ret, 2)
                    trade.hold_days = engine._count_trading_days(date.fromisoformat(trade.buy_date), last_day)
                    trade.sell_reason = "回测结束平仓"
                    trade.status = "closed"
                    trades.append(trade)
                    positions.pop(code, None)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    metrics = engine._calc_metrics(daily_values, trades, float(initial_capital))
    return metrics, daily_values, trades


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    db_path = project_root / "var/db/stock_data.db"
    out_dir = project_root / "var/tmp/lowfreq_research_report"
    out_dir.mkdir(parents=True, exist_ok=True)

    start = date.fromisoformat("2024-09-02")
    end = date.fromisoformat("2026-06-05")
    initial_capital = 1_000_000.0

    engine = LowFreqTradingEngineV16(db_path=db_path)
    metrics = engine.run_backtest(
        start,
        end,
        initial_capital=initial_capital,
        include_daily_values=True,
        include_trades=True,
    )
    daily_values = list(metrics.get("daily_values_gross") or [])
    daily_values_net = list(metrics.get("daily_values_net") or [])
    trades = list(metrics.get("trades") or [])
    annual = float(metrics.get("annual_return_pct") or 0.0)
    max_dd = float(metrics.get("max_drawdown_pct") or 0.0)
    calmar = (annual / max_dd) if max_dd > 0 else None

    universe_stats: dict[str, Any] = {}
    benchmarks: dict[str, Any] = {}
    try:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        target_date = end.isoformat()
        cur.execute(
            "SELECT trade_date FROM trading_calendar_cache WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT 20",
            (target_date,),
        )
        last_20_days = [str(r[0]) for r in (cur.fetchall() or []) if r and r[0]]
        last_20_days = list(reversed(last_20_days))

        def compute_bucket(min_cap: float, max_cap: float) -> dict[str, Any]:
            cur.execute(
                """
                SELECT code, name, total_market_cap
                FROM stocks
                WHERE COALESCE(asset_type, 'stock') = 'stock'
                AND COALESCE(is_delisted, 0) = 0
                AND total_market_cap IS NOT NULL
                AND total_market_cap >= ?
                AND total_market_cap <= ?
                """,
                (min_cap, max_cap),
            )
            rows = cur.fetchall() or []
            codes = [str(r[0]) for r in rows if r and r[0]]
            if not codes or not last_20_days:
                return {"count": len(codes), "avg_amount_20d": None}

            date_ph = ",".join("?" for _ in last_20_days)
            code_ph = ",".join("?" for _ in codes)
            cur.execute(
                f"""
                SELECT code, AVG(amount) AS avg_amount
                FROM daily_prices
                WHERE trade_date IN ({date_ph})
                AND code IN ({code_ph})
                GROUP BY code
                """,
                tuple(last_20_days + codes),
            )
            avg_map = {str(c): float(a) for c, a in (cur.fetchall() or []) if c and a is not None}
            avgs = list(avg_map.values())
            avgs.sort()

            def pct(p: float) -> float:
                if not avgs:
                    return 0.0
                idx = int(round((len(avgs) - 1) * p))
                idx = max(0, min(len(avgs) - 1, idx))
                return float(avgs[idx])

            return {
                "count": len(codes),
                "avg_amount_20d": {
                    "n_with_data": len(avgs),
                    "p10": pct(0.10),
                    "p50": pct(0.50),
                    "p90": pct(0.90),
                    "min": float(avgs[0]) if avgs else None,
                    "max": float(avgs[-1]) if avgs else None,
                    "lt_50m_count": sum(1 for x in avgs if x < 50_000_000.0),
                },
            }

        universe_stats = {
            "target_date": target_date,
            "cap_buckets": {
                "20_50b": compute_bucket(20_000_000_000.0, 50_000_000_000.0),
            },
            "notes": {
                "market_cap_source": "stocks.total_market_cap (snapshot; not point-in-time)",
                "liquidity_source": "daily_prices.amount avg over last 20 trading days",
            },
        }

        def calc_portfolio_metrics(series: list[float]) -> dict[str, Any]:
            if not series:
                return {"annual_return_pct": 0.0, "max_drawdown_pct": 0.0, "total_return_pct": 0.0}
            total_return = (series[-1] / series[0] - 1.0) * 100.0 if series[0] else 0.0
            n_days = len(series)
            annual_return = (1.0 + total_return / 100.0) ** (252 / max(n_days, 1)) - 1.0
            peak = series[0]
            max_dd = 0.0
            for v in series:
                if v > peak:
                    peak = v
                dd = (peak - v) / peak * 100.0 if peak else 0.0
                if dd > max_dd:
                    max_dd = dd
            return {
                "trading_days": n_days,
                "total_return_pct": round(total_return, 2),
                "annual_return_pct": round(annual_return * 100.0, 2),
                "max_drawdown_pct": round(max_dd, 2),
                "calmar_ratio": None if max_dd <= 0 else round((annual_return * 100.0) / max_dd, 3),
            }

        def benchmark_equal_weight(min_cap: float, max_cap: float) -> dict[str, Any]:
            eq = 1_000_000.0
            series = []
            dates = []
            for row in daily_values:
                d = str(row["date"])
                cur.execute(
                    """
                    SELECT AVG(dp.pct_change)
                    FROM daily_prices dp
                    JOIN stocks s ON s.code = dp.code
                    WHERE dp.trade_date = ?
                    AND COALESCE(s.asset_type, 'stock') = 'stock'
                    AND COALESCE(s.is_delisted, 0) = 0
                    AND s.total_market_cap IS NOT NULL
                    AND s.total_market_cap >= ?
                    AND s.total_market_cap <= ?
                    """,
                    (d, min_cap, max_cap),
                )
                avg_pct = cur.fetchone()[0]
                r = float(avg_pct or 0.0) / 100.0
                eq = eq * (1.0 + r)
                dates.append(d)
                series.append(eq)
            return {
                "definition": "equal-weight cross-sectional average pct_change (daily, no cost)",
                "cap_range": {"min": min_cap, "max": max_cap},
                "equity_series": {"dates": dates, "values": series},
                "metrics": calc_portfolio_metrics(series),
            }

        benchmarks = {
            "equal_weight_20_50b": benchmark_equal_weight(20_000_000_000.0, 50_000_000_000.0),
        }

        def exit_quality(trades_payload: list[dict[str, Any]], *, lookahead_trading_days: int) -> dict[str, Any]:
            if not trades_payload:
                return {"lookahead_trading_days": int(lookahead_trading_days), "count": 0}
            per_trade = []
            for t in trades_payload:
                if not isinstance(t, dict):
                    continue
                code = str(t.get("code") or "").strip()
                sell_date = str(t.get("sell_date") or "").strip()
                if not code or not sell_date:
                    continue
                sell_ref = t.get("sell_price_ref")
                if not isinstance(sell_ref, (int, float)) or float(sell_ref) <= 0:
                    cur.execute(
                        "SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?",
                        (code, sell_date),
                    )
                    row = cur.fetchone()
                    sell_ref = float(row[0]) if row and row[0] is not None else None
                if not isinstance(sell_ref, (int, float)) or float(sell_ref) <= 0:
                    continue
                cur.execute(
                    """
                    SELECT trade_date FROM trading_calendar_cache
                    WHERE trade_date > ?
                    ORDER BY trade_date ASC
                    LIMIT ?
                    """,
                    (sell_date, int(lookahead_trading_days)),
                )
                next_days = [str(r[0]) for r in (cur.fetchall() or []) if r and r[0]]
                if not next_days:
                    continue
                ph = ",".join("?" for _ in next_days)
                cur.execute(
                    f"SELECT MAX(close) FROM daily_prices WHERE code = ? AND trade_date IN ({ph})",
                    tuple([code] + next_days),
                )
                row = cur.fetchone()
                max_close = float(row[0]) if row and row[0] is not None else None
                if not isinstance(max_close, float) or max_close <= 0:
                    continue
                runup = (max_close / float(sell_ref) - 1.0) * 100.0
                per_trade.append(
                    {
                        "code": code,
                        "sell_date": sell_date,
                        "sell_price_ref": float(sell_ref),
                        "max_close_next_window": float(max_close),
                        "post_exit_runup_pct": round(float(runup), 2),
                        "sell_reason": str(t.get("sell_reason") or ""),
                    }
                )

            runups = [float(x.get("post_exit_runup_pct") or 0.0) for x in per_trade]
            runups.sort()

            def pctl(p: float) -> float:
                if not runups:
                    return 0.0
                idx = int(round((len(runups) - 1) * p))
                idx = max(0, min(len(runups) - 1, idx))
                return float(runups[idx])

            return {
                "lookahead_trading_days": int(lookahead_trading_days),
                "count": len(per_trade),
                "post_exit_runup_pct": {
                    "p50": round(pctl(0.50), 2),
                    "p75": round(pctl(0.75), 2),
                    "p90": round(pctl(0.90), 2),
                    "max": round(float(runups[-1]), 2) if runups else 0.0,
                    "gt_10pct_rate": round(
                        (sum(1 for x in runups if x >= 10.0) / len(runups) * 100.0) if runups else 0.0, 2
                    ),
                },
                "per_trade": per_trade,
            }

        exit_eval = exit_quality(trades, lookahead_trading_days=10)
    except Exception:
        universe_stats = {"error": "universe_stats_failed"}
        benchmarks = {"error": "benchmarks_failed"}
        exit_eval = {"error": "exit_quality_failed"}
    finally:
        try:
            conn.close()
        except Exception:
            pass

    years: dict[str, list[dict[str, Any]]] = {}
    for row in daily_values:
        y = str(row["date"])[:4]
        years.setdefault(y, []).append(row)
    yearly = {}
    for y, arr in years.items():
        arr.sort(key=lambda x: x["date"])
        yearly[y] = (float(arr[-1]["total_value"]) / float(arr[0]["total_value"]) - 1.0) * 100.0

    payload = {
        "meta": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "initial_capital": initial_capital,
            "engine_params": metrics.get("config_snapshot") or {},
        },
        "metrics": metrics,
        "calmar_ratio": None if calmar is None else round(calmar, 3),
        "yearly_return_pct": {k: round(v, 2) for k, v in yearly.items()},
        "universe_stats": universe_stats,
        "benchmarks": benchmarks,
        "daily_values": daily_values,
        "daily_values_net": daily_values_net,
        "exit_quality": exit_eval,
        "trades": trades,
    }
    out_path = out_dir / "lowfreq_v16_backtest_full.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    charts_dir = out_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        vals = [float(x.get("total_value") or 0.0) for x in daily_values]
        plt.figure(figsize=(10, 4))
        plt.plot(vals, linewidth=1.2)
        plt.title("LowFreq v16 Equity Curve (Total Value)")
        plt.xlabel("Trading Days")
        plt.ylabel("Portfolio Value (CNY)")
        plt.tight_layout()
        plt.savefig(charts_dir / "equity_curve.png", dpi=160)
        plt.close()

        try:
            b1 = payload.get("benchmarks", {}).get("equal_weight_20_40b", {})
            b2 = payload.get("benchmarks", {}).get("equal_weight_20_50b", {})
            v1 = (b1.get("equity_series") or {}).get("values") or []
            v2 = (b2.get("equity_series") or {}).get("values") or []
            if v1 and v2 and len(v1) == len(vals) and len(v2) == len(vals):
                plt.figure(figsize=(10, 4))
                plt.plot(vals, linewidth=1.2, label="LowFreq v16")
                plt.plot(v1, linewidth=1.1, label="EW 20-40B (avg pct_change)")
                plt.plot(v2, linewidth=1.1, label="EW 20-50B (avg pct_change)")
                plt.title("Equity Curve vs Baselines")
                plt.xlabel("Trading Days")
                plt.ylabel("Portfolio Value (CNY)")
                plt.legend()
                plt.tight_layout()
                plt.savefig(charts_dir / "equity_curve_vs_bench.png", dpi=160)
                plt.close()
        except Exception:
            pass

        peak = vals[0] if vals else 1.0
        dds = []
        for v in vals:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak else 0.0
            dds.append(dd * 100.0)

        plt.figure(figsize=(10, 3.5))
        plt.plot(dds, linewidth=1.2)
        plt.title("LowFreq v16 Drawdown (%)")
        plt.xlabel("Trading Days")
        plt.ylabel("Drawdown (%)")
        plt.tight_layout()
        plt.savefig(charts_dir / "drawdown.png", dpi=160)
        plt.close()

        rets = [float(t.get("return_pct") or 0.0) for t in payload.get("trades", [])]
        plt.figure(figsize=(10, 3.5))
        plt.hist(rets, bins=40)
        plt.title("Trade Return Distribution (%)")
        plt.xlabel("Return (%)")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(charts_dir / "trade_return_hist.png", dpi=160)
        plt.close()
    except Exception:
        pass
    print(str(out_path))


if __name__ == "__main__":
    main()
