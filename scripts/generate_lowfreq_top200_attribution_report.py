#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.main import BootstrapApiService
from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16, StockCandidate, TradeRecord


LOGGER = logging.getLogger("lowfreq_topk_attribution")
DB_PATH = PROJECT_ROOT / "var/db/stock_data.db"


def _write_status(output_dir: Path, *, stage: str, **extra: Any) -> None:
    payload = {
        "stage": str(stage),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if extra:
        payload.update(extra)
    (output_dir / "status.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(message)s")
    logging.getLogger("lowfreq_engine_v16_advanced").setLevel(logging.WARNING)
    logging.getLogger("apps.api.main").setLevel(logging.WARNING)


def _load_backtest_payload(
    *,
    service: BootstrapApiService,
    backtest_json: Optional[Path],
    start_date: date,
    end_date: date,
    initial_capital: float,
    max_positions_override: Optional[int],
    execution_one_price_limit_only: bool,
) -> dict[str, Any]:
    if backtest_json and backtest_json.exists():
        return json.loads(backtest_json.read_text(encoding="utf-8"))

    engine = service._lowfreq_engine_v16()
    if max_positions_override is not None:
        engine.MAX_POSITIONS = int(max_positions_override)
    if execution_one_price_limit_only:
        engine.EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT = True
    metrics = engine.run_backtest(
        start_date=start_date,
        end_date=end_date,
        initial_capital=float(initial_capital),
        include_trades=True,
    )
    trades = metrics.get("trades", []) if isinstance(metrics, dict) else []
    summary = dict(metrics) if isinstance(metrics, dict) else {}
    summary.pop("trades", None)
    return {
        "_meta": {
            "status": "ok",
            "requested_by": "script",
            "model": "lowfreq_engine_v16_advanced",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "summary": summary,
        "trade_blocks": summary.get("trade_blocks", {}) if isinstance(summary, dict) else {},
        "config_snapshot": summary.get("config_snapshot", {}) if isinstance(summary, dict) else {},
        "coverage_gaps": summary.get("coverage_gaps", {}) if isinstance(summary, dict) else {},
        "trades": trades if isinstance(trades, list) else [],
    }


def _a_share_universe_sql() -> str:
    return """
        length(s.code) = 6
        AND (s.is_delisted IS NULL OR s.is_delisted = 0)
        AND (
            s.code GLOB '60[0-9][0-9][0-9][0-9]'
            OR s.code GLOB '688[0-9][0-9][0-9]'
            OR s.code GLOB '300[0-9][0-9][0-9]'
            OR s.code GLOB '301[0-9][0-9][0-9]'
            OR s.code GLOB '00[0-9][0-9][0-9][0-9]'
        )
    """


def _load_top_ranking(conn: sqlite3.Connection, *, year: int, limit: int) -> list[dict[str, Any]]:
    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"
    sql = f"""
    WITH universe AS (
        SELECT s.code, s.name, s.sector_lv1
        FROM stocks s
        WHERE {_a_share_universe_sql()}
    ),
    bounds AS (
        SELECT
            u.code,
            u.name,
            u.sector_lv1,
            MIN(CASE WHEN d.trade_date BETWEEN ? AND ? THEN d.trade_date END) AS first_dt,
            MAX(CASE WHEN d.trade_date BETWEEN ? AND ? THEN d.trade_date END) AS last_dt
        FROM universe u
        JOIN daily_prices d ON d.code = u.code
        GROUP BY u.code, u.name, u.sector_lv1
    )
    SELECT
        b.code,
        b.name,
        b.sector_lv1,
        b.first_dt,
        b.last_dt,
        p1.close AS first_close,
        p2.close AS last_close,
        ((p2.close - p1.close) / p1.close) * 100.0 AS annual_return_pct
    FROM bounds b
    JOIN daily_prices p1 ON p1.code = b.code AND p1.trade_date = b.first_dt
    JOIN daily_prices p2 ON p2.code = b.code AND p2.trade_date = b.last_dt
    WHERE b.first_dt IS NOT NULL
      AND b.last_dt IS NOT NULL
      AND p1.close IS NOT NULL
      AND p2.close IS NOT NULL
      AND p1.close > 0
    ORDER BY annual_return_pct DESC, b.code ASC
    LIMIT ?
    """
    rows = conn.execute(
        sql,
        (year_start, year_end, year_start, year_end, int(limit)),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        out.append(
            {
                "rank": idx,
                "code": str(row[0]),
                "name": str(row[1] or ""),
                "sector": str(row[2] or ""),
                "first_trade_date": str(row[3]),
                "last_trade_date": str(row[4]),
                "first_close": round(float(row[5]), 4),
                "last_close": round(float(row[6]), 4),
                "annual_return_pct": round(float(row[7]), 2),
                "price_basis": "未复权收盘价",
            }
        )
    return out


def _load_price_series(
    conn: sqlite3.Connection,
    *,
    code: str,
    end_date: date,
    lookback_trading_days: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT trade_date, close
        FROM (
            SELECT trade_date, close,
                   row_number() OVER (ORDER BY trade_date DESC) AS rn
            FROM daily_prices
            WHERE code = ? AND trade_date <= ? AND close IS NOT NULL
        )
        WHERE rn <= ?
        ORDER BY trade_date ASC
        """,
        (str(code), end_date.isoformat(), int(lookback_trading_days)),
    ).fetchall()
    return [{"trade_date": str(r[0]), "close": float(r[1])} for r in rows if r and r[0] and r[1] is not None]


def _compute_wave_segment(
    conn: sqlite3.Connection,
    *,
    code: str,
    year: int,
    lookback_trading_days: int = 180,
) -> dict[str, Any]:
    rows_2025 = conn.execute(
        """
        SELECT trade_date, close
        FROM daily_prices
        WHERE code = ? AND trade_date BETWEEN ? AND ? AND close IS NOT NULL
        ORDER BY trade_date ASC
        """,
        (str(code), f"{year}-01-01", f"{year}-12-31"),
    ).fetchall()
    if not rows_2025:
        return {
            "status": "missing_2025_prices",
            "code": str(code),
        }

    top_row = max(rows_2025, key=lambda x: float(x[1] or 0.0))
    top_date = date.fromisoformat(str(top_row[0]))
    top_close = float(top_row[1])
    window = _load_price_series(
        conn,
        code=str(code),
        end_date=top_date,
        lookback_trading_days=int(lookback_trading_days),
    )
    if len(window) < 2:
        return {
            "status": "insufficient_history",
            "code": str(code),
            "top_date": top_date.isoformat(),
            "top_close": round(top_close, 4),
        }

    start_row = min(window[:-1], key=lambda x: float(x["close"]))
    start_close = float(start_row["close"])
    segment_return = (top_close - start_close) / max(start_close, 1e-9) * 100.0
    return {
        "status": "ok",
        "code": str(code),
        "segment_window_trading_days": int(lookback_trading_days),
        "start_date": str(start_row["trade_date"]),
        "start_close": round(start_close, 4),
        "top_date": top_date.isoformat(),
        "top_close": round(top_close, 4),
        "segment_return_pct": round(float(segment_return), 2),
        "segment_basis": "见顶日前180交易日窗口内最低收盘价 -> 2025年最高收盘价",
    }


class AuditContext:
    def __init__(self, *, engine: LowFreqTradingEngineV16, conn: sqlite3.Connection) -> None:
        self.engine = engine
        self.conn = conn
        self.hot_sectors_cache: dict[str, list[str]] = {}
        self.signals_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self.global_seed_cache: dict[str, set[str]] = {}
        self.global_candidate_cache: dict[str, dict[str, StockCandidate]] = {}
        self.sector_seed_cache: dict[tuple[str, str], set[str]] = {}
        self.sector_candidate_cache: dict[tuple[str, str], dict[str, StockCandidate]] = {}
        self.market_filter_cache: dict[str, dict[str, Any]] = {}

    def market_filter_state(self, target_date: date) -> dict[str, Any]:
        key = target_date.isoformat()
        cached = self.market_filter_cache.get(key)
        if cached is not None:
            return dict(cached)
        sentiment, score = self.engine.get_market_sentiment(target_date)
        state = {
            "filtered": bool(self.engine.MARKET_FILTER_ENABLED and float(score) < float(self.engine.MIN_MARKET_SCORE)),
            "sentiment": getattr(sentiment, "value", str(sentiment)),
            "score": float(score),
        }
        self.market_filter_cache[key] = dict(state)
        return state

    def hot_sectors(self, target_date: date) -> list[str]:
        key = target_date.isoformat()
        cached = self.hot_sectors_cache.get(key)
        if cached is not None:
            return list(cached)
        sectors = self.engine.get_hot_sectors(target_date, self.engine.HOT_SECTOR_COUNT)
        out = [str(x.sector) for x in sectors]
        self.hot_sectors_cache[key] = list(out)
        return out

    def signals(self, target_date: date) -> dict[str, dict[str, Any]]:
        key = target_date.isoformat()
        cached = self.signals_cache.get(key)
        if cached is not None:
            return {k: dict(v) for k, v in cached.items()}
        out: dict[str, dict[str, Any]] = {}
        raw = self.engine.generate_buy_signals(target_date)
        for item in raw.get("buy_signals", []) if isinstance(raw, dict) else []:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip()
            if code:
                out[code] = dict(item)
        self.signals_cache[key] = {k: dict(v) for k, v in out.items()}
        return out

    def sector_seed_codes(self, sector: str, target_date: date) -> set[str]:
        key = (str(sector), target_date.isoformat())
        cached = self.sector_seed_cache.get(key)
        if cached is not None:
            return set(cached)
        rows = self.conn.execute(
            """
            SELECT s.code
            FROM stocks s
            JOIN daily_prices dp ON s.code = dp.code
            WHERE s.sector_lv1 = ?
              AND dp.trade_date = ?
              AND s.total_market_cap >= ? AND s.total_market_cap <= ?
              AND (s.is_delisted IS NULL OR s.is_delisted = 0)
              AND dp.close > 0
            ORDER BY dp.pct_change DESC
            LIMIT 20
            """,
            (
                str(sector),
                target_date.isoformat(),
                self.engine.MARKET_CAP_MIN,
                self.engine.MARKET_CAP_MAX,
            ),
        ).fetchall()
        codes = {str(r[0]) for r in rows if r and r[0]}
        self.sector_seed_cache[key] = set(codes)
        return codes

    def sector_candidates(self, sector: str, target_date: date) -> dict[str, StockCandidate]:
        key = (str(sector), target_date.isoformat())
        cached = self.sector_candidate_cache.get(key)
        if cached is not None:
            return dict(cached)
        conn = self.engine._conn()
        try:
            cursor = conn.cursor()
            items = self.engine.get_sector_candidates(
                str(sector),
                target_date,
                top_n=20,
                cursor=cursor,
            )
        finally:
            conn.close()
        out = {str(c.code): c for c in items}
        self.sector_candidate_cache[key] = dict(out)
        return out

    def global_seed_codes(self, target_date: date) -> set[str]:
        key = target_date.isoformat()
        cached = self.global_seed_cache.get(key)
        if cached is not None:
            return set(cached)
        hot_sector_set = set(self.hot_sectors(target_date))
        rows = self.conn.execute(
            """
            SELECT s.code, s.sector_lv1
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
                self.engine.MARKET_CAP_MIN,
                self.engine.MARKET_CAP_MAX,
                int(self.engine.CROSS_SECTOR_SCAN_LIMIT),
            ),
        ).fetchall()
        codes = {
            str(r[0])
            for r in rows
            if r and r[0] and str(r[1] or "").strip() not in hot_sector_set
        }
        self.global_seed_cache[key] = set(codes)
        return codes

    def global_candidates(self, target_date: date) -> dict[str, StockCandidate]:
        key = target_date.isoformat()
        cached = self.global_candidate_cache.get(key)
        if cached is not None:
            return dict(cached)
        hot_sector_set = set(self.hot_sectors(target_date))
        items = self.engine.get_global_candidates(
            target_date,
            top_n=int(self.engine.CROSS_SECTOR_SCAN_LIMIT),
            exclude_sectors=hot_sector_set,
            exclude_codes=set(),
        )
        out = {str(c.code): c for c in items}
        self.global_candidate_cache[key] = dict(out)
        return out


def _audit_daily_reason(
    *,
    engine: LowFreqTradingEngineV16,
    ctx: AuditContext,
    code: str,
    name: str,
    sector: str,
    target_date: date,
) -> dict[str, Any]:
    market_state = ctx.market_filter_state(target_date)
    if market_state["filtered"]:
        return {
            "date": target_date.isoformat(),
            "stage": "market_filtered",
            "reason": f"市场情绪过滤（{market_state['sentiment']} {market_state['score']:.0f}分）",
        }

    signals = ctx.signals(target_date)
    if str(code) in signals:
        sig = signals[str(code)]
        return {
            "date": target_date.isoformat(),
            "stage": "signal_selected",
            "reason": "进入正式买入信号",
            "signal": {
                "buy_score": float(sig.get("buy_score") or 0.0),
                "role": str(sig.get("role") or ""),
                "wave_phase": str(sig.get("wave_phase") or ""),
                "reasons": list(sig.get("reasons") or []),
            },
        }

    hot_sectors = set(ctx.hot_sectors(target_date))
    sector_str = str(sector or "").strip()
    if sector_str in hot_sectors:
        seed_codes = ctx.sector_seed_codes(sector_str, target_date)
        if str(code) not in seed_codes:
            return {
                "date": target_date.isoformat(),
                "stage": "sector_seed_miss",
                "reason": "所属热点板块内未进入当日涨幅前20种子",
            }
        candidates = ctx.sector_candidates(sector_str, target_date)
        cand = candidates.get(str(code))
        if cand is None:
            return {
                "date": target_date.isoformat(),
                "stage": "sector_candidate_filtered",
                "reason": "进入板块种子但在候选阶段被硬过滤（基本面/结构/focus/历史）",
            }
        required = float(engine.BUY_THRESHOLD)
        nonconfirm_bonus = float(engine.CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS or 0.0)
        if nonconfirm_bonus > 0 and not bool(getattr(cand, "cup_handle_ok", False)):
            required += nonconfirm_bonus
        if float(cand.buy_score) < required:
            return {
                "date": target_date.isoformat(),
                "stage": "score_below_threshold",
                "reason": f"评分未达门槛（{cand.buy_score:.1f} < {required:.1f}）",
            }
        if str(cand.role) == "跟随":
            return {
                "date": target_date.isoformat(),
                "stage": "follower_filtered",
                "reason": "跟随股过滤",
            }
        if float(cand.sector_resonance) < float(engine.MIN_RESONANCE):
            return {
                "date": target_date.isoformat(),
                "stage": "resonance_filtered",
                "reason": f"共振不足（{cand.sector_resonance:.0%} < {engine.MIN_RESONANCE:.0%}）",
            }
        return {
            "date": target_date.isoformat(),
            "stage": "sector_candidate_not_selected",
            "reason": "通过板块候选但未进入最终信号，需复核当日去重/并列排序",
        }

    seed_codes = ctx.global_seed_codes(target_date)
    if str(code) not in seed_codes:
        return {
            "date": target_date.isoformat(),
            "stage": "global_seed_miss",
            "reason": "所属板块未进热点，且个股未进入跨板块扫描种子",
        }
    candidates = ctx.global_candidates(target_date)
    cand = candidates.get(str(code))
    if cand is None:
        return {
            "date": target_date.isoformat(),
            "stage": "global_candidate_filtered",
            "reason": "进入跨板块种子但在候选阶段被硬过滤（基本面/结构/focus/历史）",
        }
    if str(cand.role) == "跟随":
        return {
            "date": target_date.isoformat(),
            "stage": "global_follower_filtered",
            "reason": "跨板块分支中过滤跟随股",
        }
    if float(cand.sector_resonance) < float(engine.MIN_RESONANCE):
        return {
            "date": target_date.isoformat(),
            "stage": "global_resonance_filtered",
            "reason": f"跨板块分支共振不足（{cand.sector_resonance:.0%} < {engine.MIN_RESONANCE:.0%}）",
        }
    allowed_waves = {"3浪"}
    if bool(getattr(engine, "CROSS_SECTOR_ALLOW_WAVE1", True)):
        allowed_waves.add("1浪")
    if bool(engine.CROSS_SECTOR_WAVE3_ONLY) and str(cand.wave_phase) not in allowed_waves:
        return {
            "date": target_date.isoformat(),
            "stage": "global_wave_filtered",
            "reason": f"跨板块分支波段不符（{cand.wave_phase}）",
        }
    required = float(engine.BUY_THRESHOLD) + float(engine.CROSS_SECTOR_SCORE_MARGIN)
    nonconfirm_bonus = float(engine.CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS or 0.0)
    if nonconfirm_bonus > 0 and not bool(getattr(cand, "cup_handle_ok", False)):
        required += nonconfirm_bonus
    if float(cand.buy_score) < required:
        return {
            "date": target_date.isoformat(),
            "stage": "global_score_filtered",
            "reason": f"跨板块评分未达门槛（{cand.buy_score:.1f} < {required:.1f}）",
        }
    return {
        "date": target_date.isoformat(),
        "stage": "global_cap_filtered",
        "reason": "跨板块候选满足条件，但名额已被更高优先级股票占满",
    }


def _build_positions_timeline(trades: list[dict[str, Any]], trading_dates: list[str]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {d: set() for d in trading_dates}
    for t in trades:
        code = str(t.get("code") or "").strip()
        buy_date = str(t.get("buy_date") or "").strip()
        sell_date = str(t.get("sell_date") or "").strip()
        if not code or not buy_date or buy_date not in out:
            continue
        for d in trading_dates:
            if d < buy_date:
                continue
            if sell_date and d >= sell_date:
                break
            out[d].add(code)
    return out


def _load_trading_dates(conn: sqlite3.Connection, *, start_date: date, end_date: date) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE trade_date BETWEEN ? AND ?
        ORDER BY trade_date ASC
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _extract_execution_reason(
    *,
    code: str,
    signal_dates: list[str],
    positions_timeline: dict[str, set[str]],
    conn: sqlite3.Connection,
    engine: LowFreqTradingEngineV16,
    ctx: AuditContext,
    max_positions: int,
    execution_one_price_limit_only: bool = False,
    limit_up_pct: float = 9.8,
) -> str:
    if not signal_dates:
        return ""
    first_signal = signal_dates[0]
    rows = conn.execute(
        """
        SELECT trade_date, pct_change, high, low, close
        FROM daily_prices
        WHERE code = ? AND trade_date >= ?
        ORDER BY trade_date ASC
        LIMIT 3
        """,
        (str(code), str(first_signal)),
    ).fetchall()
    if rows:
        all_limit_up = True
        for row in rows:
            pct = float(row[1]) if row and row[1] is not None else None
            high = float(row[2]) if row and row[2] is not None else None
            low = float(row[3]) if row and row[3] is not None else None
            close = float(row[4]) if row and row[4] is not None else None
            is_one_price_board = (
                high is not None
                and low is not None
                and close is not None
                and abs(float(high) - float(low)) <= 1e-9
                and abs(float(high) - float(close)) <= 1e-9
            )
            if pct is None or pct < float(limit_up_pct):
                all_limit_up = False
                break
            if execution_one_price_limit_only and not is_one_price_board:
                all_limit_up = False
                break
        if all_limit_up:
            return "信号存在但连续涨停，无法成交"
    if first_signal in positions_timeline and len(positions_timeline[first_signal]) >= int(max_positions):
        return "信号存在但同期仓位已满"
    signal_map = ctx.signals(date.fromisoformat(str(first_signal)))
    sig = signal_map.get(str(code))
    if isinstance(sig, dict):
        row = conn.execute(
            """
            SELECT close
            FROM daily_prices
            WHERE code = ? AND trade_date = ?
            LIMIT 1
            """,
            (str(code), str(first_signal)),
        ).fetchone()
        ref_price = float(row[0]) if row and row[0] is not None else None
        if ref_price is not None and ref_price > 0:
            snapshot = engine._chase_entry_snapshot(
                conn.cursor(),
                code=str(code),
                target_date=date.fromisoformat(str(first_signal)),
                ref_price=float(ref_price),
            )
            if isinstance(snapshot, dict) and bool(snapshot.get("blocked")):
                return "信号存在但因追高型买点被硬禁"
    return "信号存在但未形成实际成交，需复核执行窗口"


def _sell_reason_bucket(sell_reason: str) -> str:
    reason = str(sell_reason or "").strip()
    if reason.startswith("回测结束平仓"):
        return "回测结束平仓"
    if "板块见顶确认" in reason:
        return "sector_top"
    if "见顶确认" in reason or "见顶：" in reason:
        return "market_top"
    if "代理回撤" in reason:
        return "market_drawdown"
    if "个股回调" in reason:
        return "stock_drawdown"
    if "跌破买入价止损" in reason:
        return "entry_stop_loss"
    return "other"


def _not_picked_primary_reason(daily_audits: list[dict[str, Any]]) -> str:
    stage_priority = {
        "market_filtered": 1,
        "sector_seed_miss": 2,
        "global_seed_miss": 2,
        "sector_candidate_filtered": 3,
        "global_candidate_filtered": 3,
        "score_below_threshold": 4,
        "follower_filtered": 4,
        "resonance_filtered": 4,
        "global_follower_filtered": 4,
        "global_resonance_filtered": 4,
        "global_wave_filtered": 4,
        "global_score_filtered": 4,
        "global_cap_filtered": 5,
        "sector_candidate_not_selected": 5,
    }
    if not daily_audits:
        return "主升段内从未形成正式信号"
    max_priority = max(int(stage_priority.get(str(x.get("stage") or ""), 0)) for x in daily_audits)
    preferred = [x for x in daily_audits if int(stage_priority.get(str(x.get("stage") or ""), 0)) == max_priority]
    if not preferred:
        preferred = daily_audits
    reason_counter = Counter(str(x.get("reason") or "") for x in preferred if x.get("reason"))
    if not reason_counter:
        return "主升段内从未形成正式信号"
    return str(reason_counter.most_common(1)[0][0])


def _analyze_topk(
    *,
    engine: LowFreqTradingEngineV16,
    conn: sqlite3.Connection,
    ranking: list[dict[str, Any]],
    backtest_payload: dict[str, Any],
    year: int,
    execution_one_price_limit_only: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    min_start = date(year, 1, 1)
    max_top = date(year, 12, 31)
    for item in ranking:
        segment = _compute_wave_segment(conn, code=str(item["code"]), year=year)
        if segment.get("status") == "ok":
            min_start = min(min_start, date.fromisoformat(str(segment["start_date"])))
            max_top = max(max_top, date.fromisoformat(str(segment["top_date"])))
        segments.append(segment)

    trading_dates = _load_trading_dates(conn, start_date=min_start, end_date=max_top)
    date_to_idx = {d: i for i, d in enumerate(trading_dates)}
    positions_timeline = _build_positions_timeline(list(backtest_payload.get("trades") or []), trading_dates)
    ctx = AuditContext(engine=engine, conn=conn)
    trades_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in list(backtest_payload.get("trades") or []):
        code = str(trade.get("code") or "").strip()
        if code:
            trades_by_code[code].append(dict(trade))

    summary_counters = Counter()
    for item, segment in zip(ranking, segments):
        code = str(item["code"])
        name = str(item["name"])
        sector = str(item.get("sector") or "")
        if segment.get("status") != "ok":
            report_rows.append(
                {
                    "rank": item["rank"],
                    "code": code,
                    "name": name,
                    "annual_return_pct": item["annual_return_pct"],
                    "segment_status": str(segment.get("status") or "unknown"),
                    "picked": False,
                    "bought": False,
                    "held_to_top": False,
                    "primary_reason": "主升段识别失败",
                }
            )
            summary_counters["segment_failed"] += 1
            continue

        start_key = str(segment["start_date"])
        top_key = str(segment["top_date"])
        start_idx = int(date_to_idx.get(start_key, 0))
        top_idx = int(date_to_idx.get(top_key, start_idx))
        segment_dates = trading_dates[start_idx : top_idx + 1]
        daily_audits: list[dict[str, Any]] = []
        signal_dates: list[str] = []
        for d_key in segment_dates:
            audit = _audit_daily_reason(
                engine=engine,
                ctx=ctx,
                code=code,
                name=name,
                sector=sector,
                target_date=date.fromisoformat(d_key),
            )
            daily_audits.append(audit)
            if audit.get("stage") == "signal_selected":
                signal_dates.append(d_key)

        code_trades = sorted(
            trades_by_code.get(code, []),
            key=lambda x: (str(x.get("buy_date") or ""), str(x.get("sell_date") or "")),
        )
        relevant_trades = [
            t
            for t in code_trades
            if str(t.get("buy_date") or "") <= top_key and str(t.get("sell_date") or "9999-12-31") >= start_key
        ]
        bought = bool(relevant_trades)
        held_to_top = any(
            str(t.get("buy_date") or "") <= top_key <= str(t.get("sell_date") or "9999-12-31")
            for t in relevant_trades
        )

        first_signal_date = signal_dates[0] if signal_dates else ""
        first_buy_date = str(relevant_trades[0].get("buy_date") or "") if relevant_trades else ""
        first_sell_date = str(relevant_trades[0].get("sell_date") or "") if relevant_trades else ""
        latest_exit_reason = ""
        if relevant_trades:
            latest_trade = max(relevant_trades, key=lambda x: str(x.get("sell_date") or ""))
            latest_exit_reason = str(latest_trade.get("sell_reason") or "")

        if signal_dates and not bought:
            primary_reason = _extract_execution_reason(
                code=code,
                signal_dates=signal_dates,
                positions_timeline=positions_timeline,
                conn=conn,
                engine=engine,
                ctx=ctx,
                max_positions=int(engine.MAX_POSITIONS),
                execution_one_price_limit_only=bool(execution_one_price_limit_only),
                limit_up_pct=float(getattr(engine, "EXEC_LIMIT_UP_PCT", 9.8) or 9.8),
            )
            reason_bucket = "picked_not_bought"
        elif not signal_dates:
            primary_reason = _not_picked_primary_reason(daily_audits)
            reason_bucket = "not_picked"
        elif bought and held_to_top:
            primary_reason = "实际持仓延续到市场事实见顶"
            reason_bucket = "held_to_top"
        else:
            primary_reason = latest_exit_reason or "已买入但未持有到见顶"
            reason_bucket = _sell_reason_bucket(latest_exit_reason)

        summary_counters[reason_bucket] += 1
        report_rows.append(
            {
                "rank": int(item["rank"]),
                "code": code,
                "name": name,
                "sector": sector,
                "annual_return_pct": float(item["annual_return_pct"]),
                "segment_start_date": start_key,
                "segment_top_date": top_key,
                "segment_return_pct": float(segment["segment_return_pct"]),
                "picked": bool(signal_dates),
                "first_signal_date": first_signal_date,
                "signal_count_in_segment": len(signal_dates),
                "bought": bought,
                "first_buy_date": first_buy_date,
                "first_sell_date": first_sell_date,
                "held_to_top": held_to_top,
                "primary_reason": primary_reason,
                "reason_bucket": reason_bucket,
                "daily_audits": daily_audits,
                "relevant_trades": relevant_trades,
            }
        )

    aggregate = {
        "count": len(report_rows),
        "picked_count": int(sum(1 for x in report_rows if x.get("picked"))),
        "bought_count": int(sum(1 for x in report_rows if x.get("bought"))),
        "held_to_top_count": int(sum(1 for x in report_rows if x.get("held_to_top"))),
        "reason_buckets": dict(summary_counters),
    }
    return segments, report_rows, aggregate


def _write_markdown_report(
    *,
    output_path: Path,
    year: int,
    limit: int,
    ranking: list[dict[str, Any]],
    aggregate: dict[str, Any],
    attribution_rows: list[dict[str, Any]],
    backtest_payload: dict[str, Any],
) -> None:
    top_reasons = Counter(str(x.get("reason_bucket") or "") for x in attribution_rows)
    early_exits = [x for x in attribution_rows if x.get("bought") and not x.get("held_to_top")]
    lines: list[str] = []
    lines.append(f"# Lowfreq Model {year} Top{int(limit)} Scorecard Report")
    lines.append("")
    lines.append("## 口径说明")
    lines.append("")
    lines.append("- 年度涨幅口径：未复权收盘价，使用年内首个有效交易日与最后一个有效交易日。")
    lines.append("- 主升段起点：见顶日前 180 个交易日窗口内最低收盘价。")
    lines.append("- 见顶日期：2025 年内最高收盘价所在交易日。")
    lines.append("- 模型行为口径：当前收紧 `market_top` 且补正 `301* -> 创业板` 后的引擎逻辑。")
    lines.append("")
    lines.append("## 总体摘要")
    lines.append("")
    lines.append(f"- Top{int(limit)} count: {len(ranking)}")
    lines.append(f"- 模型曾挑中：{aggregate.get('picked_count', 0)}")
    lines.append(f"- 实际买入：{aggregate.get('bought_count', 0)}")
    lines.append(f"- 持有到市场事实见顶：{aggregate.get('held_to_top_count', 0)}")
    summary = backtest_payload.get("summary") if isinstance(backtest_payload, dict) else {}
    if isinstance(summary, dict) and summary:
        lines.append(
            f"- 当前18个月回测摘要：总收益 {summary.get('total_return_pct', 0)}%，最大回撤 {summary.get('max_drawdown_pct', 0)}%，交易数 {summary.get('total_trades', 0)}"
        )
    lines.append("")
    lines.append("## 原因分布")
    lines.append("")
    for reason, count in top_reasons.most_common():
        lines.append(f"- {reason}: {count}")
    lines.append("")
    lines.append("## 典型未挑中样本")
    lines.append("")
    for row in [x for x in attribution_rows if not x.get("picked")][:20]:
        lines.append(
            f"- {row['code']} {row['name']} | 年涨幅 {row['annual_return_pct']:.2f}% | 起涨 {row['segment_start_date']} | 见顶 {row['segment_top_date']} | 原因：{row['primary_reason']}"
        )
    lines.append("")
    lines.append("## 典型提前离场样本")
    lines.append("")
    for row in early_exits[:20]:
        lines.append(
            f"- {row['code']} {row['name']} | 买入 {row['first_buy_date']} | 卖出 {row['first_sell_date']} | 见顶 {row['segment_top_date']} | 原因：{row['primary_reason']}"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate lowfreq model TopK scorecard, wave segments, and attribution report.")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--backtest-json", type=Path, default=None)
    parser.add_argument("--backtest-start", type=str, default="2024-12-18")
    parser.add_argument("--backtest-end", type=str, default="2026-06-18")
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--max-positions-override", type=int, default=None)
    parser.add_argument("--execution-one-price-limit-only", action="store_true")
    parser.add_argument("--report-id", type=str, default="")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    _setup_logging(bool(args.verbose))
    service = BootstrapApiService(project_root=PROJECT_ROOT)
    top_label = f"top{int(args.limit)}"
    report_id = str(args.report_id or f"{top_label}_{args.year}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    output_dir = PROJECT_ROOT / "var/artifacts" / f"lowfreq_{top_label}_attribution" / report_id
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_status(output_dir, stage="initializing", year=int(args.year), limit=int(args.limit), report_id=report_id)

    conn = sqlite3.connect(str(DB_PATH))
    try:
        ranking = _load_top_ranking(conn, year=int(args.year), limit=int(args.limit))
        _write_status(output_dir, stage="ranking_ready", ranking_count=len(ranking))
        backtest_payload = _load_backtest_payload(
            service=service,
            backtest_json=args.backtest_json,
            start_date=date.fromisoformat(str(args.backtest_start)),
            end_date=date.fromisoformat(str(args.backtest_end)),
            initial_capital=float(args.initial_capital),
            max_positions_override=args.max_positions_override,
            execution_one_price_limit_only=bool(args.execution_one_price_limit_only),
        )
        summary = backtest_payload.get("summary") if isinstance(backtest_payload, dict) else {}
        _write_status(
            output_dir,
            stage="backtest_ready",
            ranking_count=len(ranking),
            total_return_pct=(summary.get("total_return_pct") if isinstance(summary, dict) else None),
            total_trades=(summary.get("total_trades") if isinstance(summary, dict) else None),
        )
        engine = service._lowfreq_engine_v16()
        if args.max_positions_override is not None:
            engine.MAX_POSITIONS = int(args.max_positions_override)
        segments, attribution_rows, aggregate = _analyze_topk(
            engine=engine,
            conn=conn,
            ranking=ranking,
            backtest_payload=backtest_payload,
            year=int(args.year),
            execution_one_price_limit_only=bool(args.execution_one_price_limit_only),
        )
        _write_status(
            output_dir,
            stage="analysis_ready",
            ranking_count=len(ranking),
            aggregate=aggregate,
        )
    finally:
        conn.close()

    ranking_path = output_dir / f"top{int(args.limit)}_{args.year}_ranking.json"
    segments_path = output_dir / f"top{int(args.limit)}_{args.year}_wave_segments.json"
    attribution_path = output_dir / f"top{int(args.limit)}_{args.year}_model_attribution.json"
    report_path = output_dir / "report.md"

    ranking_path.write_text(json.dumps(ranking, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    segments_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    attribution_payload = {
        "_meta": {
            "status": "ok",
            "report_id": report_id,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "year": int(args.year),
            "limit": int(args.limit),
        },
        "aggregate": aggregate,
        "items": attribution_rows,
    }
    attribution_path.write_text(json.dumps(attribution_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_markdown_report(
        output_path=report_path,
        year=int(args.year),
        limit=int(args.limit),
        ranking=ranking,
        aggregate=aggregate,
        attribution_rows=attribution_rows,
        backtest_payload=backtest_payload,
    )
    _write_status(
        output_dir,
        stage="done",
        report_id=report_id,
        ranking_path=str(ranking_path),
        segments_path=str(segments_path),
        attribution_path=str(attribution_path),
        report_path=str(report_path),
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "report_id": report_id,
                "output_dir": str(output_dir),
                "ranking_path": str(ranking_path),
                "segments_path": str(segments_path),
                "attribution_path": str(attribution_path),
                "report_path": str(report_path),
                "aggregate": aggregate,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
