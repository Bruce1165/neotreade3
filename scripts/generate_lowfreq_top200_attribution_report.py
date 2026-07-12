#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.main import BootstrapApiService
from neotrade3.analysis.attribution_aggregate_summary import build_attribution_aggregate_summary
from neotrade3.analysis.attribution_artifact_payload import build_attribution_artifact_payload
from neotrade3.analysis.attribution_audit_index import build_buy_signal_audit_index
from neotrade3.analysis.attribution_daily_audit_payload import (
    build_candidate_signal_selected_audit,
    build_entry_signal_selected_audit,
    build_simple_stage_audit,
)
from neotrade3.analysis.attribution_execution_limit_window import is_execution_limit_up_window
from neotrade3.analysis.attribution_markdown_report import build_attribution_markdown_report
from neotrade3.analysis.attribution_positions_timeline import build_positions_timeline
from neotrade3.analysis.attribution_ranking_payload import build_attribution_ranking_row
from neotrade3.analysis.attribution_report_row import (
    build_attribution_report_row,
    build_attribution_segment_failed_row,
)
from neotrade3.analysis.attribution_signal_pick_summary import build_attribution_signal_pick_summary
from neotrade3.analysis.attribution_trade_window import build_attribution_trade_window
from neotrade3.analysis.attribution_wave_segment import (
    build_insufficient_history_wave_segment,
    build_missing_wave_segment,
    build_ok_wave_segment,
)
from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16, StockCandidate, TradeRecord
from neotrade3.analysis.attribution_reasoning import (
    resolve_candidate_only_primary_reason,
    resolve_execution_audit_primary_reason,
    resolve_execution_fallback_reason,
    resolve_not_picked_primary_reason,
    resolve_primary_reason_decision,
    resolve_sell_reason_bucket,
)
from neotrade3.analysis.attribution_signal_snapshot import build_attribution_signal_snapshot
from neotrade3.decision_engine.cross_sector_wave_policy import (
    is_cross_sector_wave_mismatch,
)
from neotrade3.orchestration.report_runner_status import (
    build_analysis_ready_report_status,
    build_backtest_ready_report_status,
    build_done_report_status,
    build_initializing_report_status,
    build_ranking_ready_report_status,
)
from neotrade3.orchestration.report_runner_artifact_paths import (
    build_lowfreq_report_artifact_paths,
)
from neotrade3.orchestration.report_runner_cli_summary import (
    build_lowfreq_report_success_summary,
)
from neotrade3.orchestration.report_runner_run_context import (
    build_lowfreq_report_run_context,
)
from neotrade3.orchestration.report_runner_analysis_engine import (
    prepare_lowfreq_report_analysis_engine,
)
from neotrade3.orchestration.report_runner_backtest_source import (
    load_lowfreq_report_backtest_payload,
)


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
            build_attribution_ranking_row(
                rank=idx,
                code=row[0],
                name=row[1],
                sector=row[2],
                first_trade_date=row[3],
                last_trade_date=row[4],
                first_close=row[5],
                last_close=row[6],
                annual_return_pct=row[7],
            )
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
        return build_missing_wave_segment(code=str(code))

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
        return build_insufficient_history_wave_segment(
            code=str(code),
            top_date=top_date,
            top_close=top_close,
        )

    start_row = min(window[:-1], key=lambda x: float(x["close"]))
    start_close = float(start_row["close"])
    segment_return = (top_close - start_close) / max(start_close, 1e-9) * 100.0
    return build_ok_wave_segment(
        code=str(code),
        lookback_trading_days=int(lookback_trading_days),
        start_date=str(start_row["trade_date"]),
        start_close=start_close,
        top_date=top_date,
        top_close=top_close,
        segment_return_pct=segment_return,
    )


def _signal_layer_snapshot(raw: Any) -> dict[str, Any]:
    return build_attribution_signal_snapshot(raw)


class AuditContext:
    def __init__(self, *, engine: LowFreqTradingEngineV16, conn: sqlite3.Connection) -> None:
        self.engine = engine
        self.conn = conn
        self.hot_sectors_cache: dict[str, list[str]] = {}
        self.signal_layers_cache: dict[str, dict[str, Any]] = {}
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

    def signal_snapshot(self, target_date: date) -> dict[str, Any]:
        key = target_date.isoformat()
        cached = self.signal_layers_cache.get(key)
        if cached is not None:
            return {
                "candidate_signals": {k: dict(v) for k, v in cached.get("candidate_signals", {}).items()},
                "entry_signals": {k: dict(v) for k, v in cached.get("entry_signals", {}).items()},
                "signal_summary": dict(cached.get("signal_summary", {})),
            }
        raw = self.engine.generate_buy_signals(target_date)
        snapshot = _signal_layer_snapshot(raw)
        self.signal_layers_cache[key] = {
            "candidate_signals": {k: dict(v) for k, v in snapshot["candidate_signals"].items()},
            "entry_signals": {k: dict(v) for k, v in snapshot["entry_signals"].items()},
            "signal_summary": dict(snapshot["signal_summary"]),
        }
        return snapshot

    def signals(self, target_date: date) -> dict[str, dict[str, Any]]:
        return self.entry_signals(target_date)

    def candidate_signals(self, target_date: date) -> dict[str, dict[str, Any]]:
        snapshot = self.signal_snapshot(target_date)
        return {k: dict(v) for k, v in snapshot.get("candidate_signals", {}).items()}

    def entry_signals(self, target_date: date) -> dict[str, dict[str, Any]]:
        snapshot = self.signal_snapshot(target_date)
        return {k: dict(v) for k, v in snapshot.get("entry_signals", {}).items()}

    def signal_summary(self, target_date: date) -> dict[str, Any]:
        snapshot = self.signal_snapshot(target_date)
        return dict(snapshot.get("signal_summary", {}))

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
        return build_simple_stage_audit(
            audit_date=target_date.isoformat(),
            stage="market_filtered",
            reason=f"市场情绪过滤（{market_state['sentiment']} {market_state['score']:.0f}分）",
        )

    entry_signals = ctx.entry_signals(target_date)
    if str(code) in entry_signals:
        sig = entry_signals[str(code)]
        return build_entry_signal_selected_audit(audit_date=target_date.isoformat(), signal=sig)

    candidate_signals = ctx.candidate_signals(target_date)
    if str(code) in candidate_signals:
        sig = candidate_signals[str(code)]
        return build_candidate_signal_selected_audit(audit_date=target_date.isoformat(), signal=sig)

    hot_sectors = set(ctx.hot_sectors(target_date))
    sector_str = str(sector or "").strip()
    if sector_str in hot_sectors:
        seed_codes = ctx.sector_seed_codes(sector_str, target_date)
        if str(code) not in seed_codes:
            return build_simple_stage_audit(
                audit_date=target_date.isoformat(),
                stage="sector_seed_miss",
                reason="所属热点板块内未进入当日涨幅前20种子",
            )
        candidates = ctx.sector_candidates(sector_str, target_date)
        cand = candidates.get(str(code))
        if cand is None:
            return build_simple_stage_audit(
                audit_date=target_date.isoformat(),
                stage="sector_candidate_filtered",
                reason="进入板块种子但在候选阶段被硬过滤（基本面/结构/focus/历史）",
            )
        required = float(engine.BUY_THRESHOLD)
        nonconfirm_bonus = float(engine.CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS or 0.0)
        if nonconfirm_bonus > 0 and not bool(getattr(cand, "cup_handle_ok", False)):
            required += nonconfirm_bonus
        if float(cand.buy_score) < required:
            return build_simple_stage_audit(
                audit_date=target_date.isoformat(),
                stage="score_below_threshold",
                reason=f"评分未达门槛（{cand.buy_score:.1f} < {required:.1f}）",
            )
        if str(cand.role) == "跟随":
            return build_simple_stage_audit(
                audit_date=target_date.isoformat(),
                stage="follower_filtered",
                reason="跟随股过滤",
            )
        if float(cand.sector_resonance) < float(engine.MIN_RESONANCE):
            return build_simple_stage_audit(
                audit_date=target_date.isoformat(),
                stage="resonance_filtered",
                reason=f"共振不足（{cand.sector_resonance:.0%} < {engine.MIN_RESONANCE:.0%}）",
            )
        return build_simple_stage_audit(
            audit_date=target_date.isoformat(),
            stage="sector_candidate_not_selected",
            reason="通过板块候选但未进入最终信号，需复核当日去重/并列排序",
        )

    seed_codes = ctx.global_seed_codes(target_date)
    if str(code) not in seed_codes:
        return build_simple_stage_audit(
            audit_date=target_date.isoformat(),
            stage="global_seed_miss",
            reason="所属板块未进热点，且个股未进入跨板块扫描种子",
        )
    candidates = ctx.global_candidates(target_date)
    cand = candidates.get(str(code))
    if cand is None:
        return build_simple_stage_audit(
            audit_date=target_date.isoformat(),
            stage="global_candidate_filtered",
            reason="进入跨板块种子但在候选阶段被硬过滤（基本面/结构/focus/历史）",
        )
    if str(cand.role) == "跟随":
        return build_simple_stage_audit(
            audit_date=target_date.isoformat(),
            stage="global_follower_filtered",
            reason="跨板块分支中过滤跟随股",
        )
    if float(cand.sector_resonance) < float(engine.MIN_RESONANCE):
        return build_simple_stage_audit(
            audit_date=target_date.isoformat(),
            stage="global_resonance_filtered",
            reason=f"跨板块分支共振不足（{cand.sector_resonance:.0%} < {engine.MIN_RESONANCE:.0%}）",
        )
    if is_cross_sector_wave_mismatch(
        cand.wave_phase,
        wave3_only=bool(engine.CROSS_SECTOR_WAVE3_ONLY),
        allow_wave1=bool(getattr(engine, "CROSS_SECTOR_ALLOW_WAVE1", True)),
    ):
        return build_simple_stage_audit(
            audit_date=target_date.isoformat(),
            stage="global_wave_filtered",
            reason=f"跨板块分支波段不符（{cand.wave_phase}）",
        )
    required = float(engine.BUY_THRESHOLD) + float(engine.CROSS_SECTOR_SCORE_MARGIN)
    nonconfirm_bonus = float(engine.CUP_HANDLE_NONCONFIRM_THRESHOLD_BONUS or 0.0)
    if nonconfirm_bonus > 0 and not bool(getattr(cand, "cup_handle_ok", False)):
        required += nonconfirm_bonus
    if float(cand.buy_score) < required:
        return build_simple_stage_audit(
            audit_date=target_date.isoformat(),
            stage="global_score_filtered",
            reason=f"跨板块评分未达门槛（{cand.buy_score:.1f} < {required:.1f}）",
        )
    return build_simple_stage_audit(
        audit_date=target_date.isoformat(),
        stage="global_cap_filtered",
        reason="跨板块候选满足条件，但名额已被更高优先级股票占满",
    )


def _build_positions_timeline(trades: list[dict[str, Any]], trading_dates: list[str]) -> dict[str, set[str]]:
    return build_positions_timeline(trades, trading_dates)


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


def _build_buy_signal_audit_index(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return build_buy_signal_audit_index(entries)


def _extract_execution_reason(
    *,
    code: str,
    signal_dates: list[str],
    positions_timeline: dict[str, set[str]],
    conn: sqlite3.Connection,
    engine: LowFreqTradingEngineV16,
    ctx: AuditContext,
    max_positions: int,
    segment_top_date: str,
    buy_signal_audits: list[dict[str, Any]],
    code_trades: list[dict[str, Any]],
    execution_mode: str = "bounded",
    execution_one_price_limit_only: bool = False,
    limit_up_pct: float = 9.8,
) -> str:
    if not signal_dates:
        return ""
    first_signal = signal_dates[0]
    reason = resolve_execution_audit_primary_reason(
        buy_signal_audits=buy_signal_audits,
        code_trades=code_trades,
        segment_top_date=segment_top_date,
    )
    if reason:
        return reason
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
    all_limit_up = is_execution_limit_up_window(
        bars=[
            {
                "pct_change": float(row[1]) if row and row[1] is not None else None,
                "high": float(row[2]) if row and row[2] is not None else None,
                "low": float(row[3]) if row and row[3] is not None else None,
                "close": float(row[4]) if row and row[4] is not None else None,
            }
            for row in rows
        ],
        limit_up_pct=float(limit_up_pct),
        one_price_only=bool(execution_one_price_limit_only),
    )
    positions_full = (
        str(execution_mode or "").strip().lower() != "unbounded_opportunity"
        and first_signal in positions_timeline
        and len(positions_timeline[first_signal]) >= int(max_positions)
    )
    chase_blocked = False
    if (
        not all_limit_up
        and not positions_full
    ):
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
                chase_blocked = isinstance(snapshot, dict) and bool(snapshot.get("blocked"))
    return resolve_execution_fallback_reason(
        all_limit_up=all_limit_up,
        positions_full=positions_full,
        chase_blocked=chase_blocked,
    )


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
    summary = backtest_payload.get("summary") if isinstance(backtest_payload, dict) else {}
    config_snapshot = backtest_payload.get("config_snapshot") if isinstance(backtest_payload, dict) else {}
    execution_mode = (
        str(config_snapshot.get("execution_mode") or "").strip()
        if isinstance(config_snapshot, dict)
        else ""
    ) or str(getattr(engine, "EXECUTION_MODE", "unbounded_opportunity") or "unbounded_opportunity")
    buy_signal_audit_by_code = _build_buy_signal_audit_index(
        list(summary.get("buy_signal_audit") or []) if isinstance(summary, dict) else []
    )
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
                build_attribution_segment_failed_row(
                    rank=item["rank"],
                    code=code,
                    name=name,
                    annual_return_pct=item["annual_return_pct"],
                    segment_status=str(segment.get("status") or "unknown"),
                )
            )
            summary_counters["segment_failed"] += 1
            continue

        start_key = str(segment["start_date"])
        top_key = str(segment["top_date"])
        start_idx = int(date_to_idx.get(start_key, 0))
        top_idx = int(date_to_idx.get(top_key, start_idx))
        segment_dates = trading_dates[start_idx : top_idx + 1]
        daily_audits: list[dict[str, Any]] = []
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
        signal_pick_summary = build_attribution_signal_pick_summary(daily_audits)
        candidate_dates = list(signal_pick_summary["candidate_dates"])
        entry_dates = list(signal_pick_summary["entry_dates"])

        trade_window = build_attribution_trade_window(
            trades_by_code.get(code, []),
            segment_start_date=start_key,
            segment_top_date=top_key,
        )
        code_trades = list(trade_window["code_trades"])
        relevant_trades = list(trade_window["relevant_trades"])
        bought = bool(trade_window["bought"])
        held_to_top = bool(trade_window["held_to_top"])

        first_candidate_date = str(signal_pick_summary["first_candidate_date"] or "")
        first_entry_date = str(signal_pick_summary["first_entry_date"] or "")
        first_buy_date = str(trade_window["first_buy_date"] or "")
        first_sell_date = str(trade_window["first_sell_date"] or "")
        latest_exit_reason = str(trade_window["latest_exit_reason"] or "")

        sell_reason_bucket = resolve_sell_reason_bucket(latest_exit_reason)
        execution_primary_reason = ""
        if entry_dates:
            execution_primary_reason = _extract_execution_reason(
                code=code,
                signal_dates=entry_dates,
                positions_timeline=positions_timeline,
                conn=conn,
                engine=engine,
                ctx=ctx,
                max_positions=int(engine.MAX_POSITIONS),
                segment_top_date=top_key,
                buy_signal_audits=buy_signal_audit_by_code.get(code, []),
                code_trades=code_trades,
                execution_mode=execution_mode,
                execution_one_price_limit_only=bool(execution_one_price_limit_only),
                limit_up_pct=float(getattr(engine, "EXEC_LIMIT_UP_PCT", 9.8) or 9.8),
            )
        candidate_only_primary_reason = resolve_candidate_only_primary_reason(daily_audits)
        not_picked_primary_reason = resolve_not_picked_primary_reason(daily_audits)
        reason_decision = resolve_primary_reason_decision(
            bought=bought,
            held_to_top=held_to_top,
            entry_picked=bool(entry_dates),
            candidate_picked=bool(candidate_dates),
            latest_exit_reason=latest_exit_reason,
            sell_reason_bucket=sell_reason_bucket,
            execution_primary_reason=execution_primary_reason,
            candidate_only_primary_reason=candidate_only_primary_reason,
            not_picked_primary_reason=not_picked_primary_reason,
        )
        primary_reason = str(reason_decision["primary_reason"] or "")
        reason_bucket = str(reason_decision["reason_bucket"] or "")

        summary_counters[reason_bucket] += 1
        report_rows.append(
            build_attribution_report_row(
                rank=item["rank"],
                code=code,
                name=name,
                sector=sector,
                annual_return_pct=item["annual_return_pct"],
                segment_start_date=start_key,
                segment_top_date=top_key,
                segment_return_pct=segment["segment_return_pct"],
                candidate_picked=bool(signal_pick_summary["candidate_picked"]),
                entry_picked=bool(signal_pick_summary["entry_picked"]),
                picked=bool(signal_pick_summary["picked"]),
                first_candidate_date=first_candidate_date,
                candidate_signal_count_in_segment=signal_pick_summary["candidate_signal_count_in_segment"],
                first_entry_date=first_entry_date,
                first_signal_date=str(signal_pick_summary["first_signal_date"] or ""),
                entry_signal_count_in_segment=signal_pick_summary["entry_signal_count_in_segment"],
                signal_count_in_segment=signal_pick_summary["signal_count_in_segment"],
                bought=bought,
                first_buy_date=first_buy_date,
                first_sell_date=first_sell_date,
                held_to_top=held_to_top,
                primary_reason=primary_reason,
                reason_bucket=reason_bucket,
                daily_audits=daily_audits,
                relevant_trades=relevant_trades,
            )
        )

    aggregate = build_attribution_aggregate_summary(report_rows, dict(summary_counters))
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
    output_path.write_text(
        build_attribution_markdown_report(
            year=int(year),
            limit=int(limit),
            ranking=ranking,
            aggregate=aggregate,
            attribution_rows=attribution_rows,
            backtest_payload=backtest_payload,
        ),
        encoding="utf-8",
    )


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
    run_context = build_lowfreq_report_run_context(
        project_root=PROJECT_ROOT,
        year=int(args.year),
        limit=int(args.limit),
        report_id=args.report_id,
        timestamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    )
    report_id = str(run_context["report_id"])
    output_dir = Path(run_context["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_status(
        output_dir,
        **build_initializing_report_status(
            year=int(args.year),
            limit=int(args.limit),
            report_id=report_id,
        ),
    )

    conn = sqlite3.connect(str(DB_PATH))
    try:
        ranking = _load_top_ranking(conn, year=int(args.year), limit=int(args.limit))
        _write_status(
            output_dir,
            **build_ranking_ready_report_status(ranking_count=len(ranking)),
        )
        backtest_payload = load_lowfreq_report_backtest_payload(
            service=service,
            backtest_json=args.backtest_json,
            start_date=date.fromisoformat(str(args.backtest_start)),
            end_date=date.fromisoformat(str(args.backtest_end)),
            initial_capital=float(args.initial_capital),
            max_positions_override=args.max_positions_override,
            execution_one_price_limit_only=bool(args.execution_one_price_limit_only),
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        summary = backtest_payload.get("summary") if isinstance(backtest_payload, dict) else {}
        _write_status(
            output_dir,
            **build_backtest_ready_report_status(
                ranking_count=len(ranking),
                total_return_pct=(summary.get("total_return_pct") if isinstance(summary, dict) else None),
                total_trades=(summary.get("total_trades") if isinstance(summary, dict) else None),
            ),
        )
        engine = prepare_lowfreq_report_analysis_engine(
            service=service,
            max_positions_override=args.max_positions_override,
        )
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
            **build_analysis_ready_report_status(
                ranking_count=len(ranking),
                aggregate=aggregate,
            ),
        )
    finally:
        conn.close()

    artifact_paths = build_lowfreq_report_artifact_paths(
        output_dir=output_dir,
        year=int(args.year),
        limit=int(args.limit),
    )
    ranking_path = Path(artifact_paths["ranking_path"])
    segments_path = Path(artifact_paths["segments_path"])
    attribution_path = Path(artifact_paths["attribution_path"])
    report_path = Path(artifact_paths["report_path"])
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ranking_path.write_text(json.dumps(ranking, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    segments_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    attribution_payload = build_attribution_artifact_payload(
        report_id=report_id,
        generated_at=generated_at,
        year=int(args.year),
        limit=int(args.limit),
        aggregate=aggregate,
        items=attribution_rows,
    )
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
        **build_done_report_status(
            report_id=report_id,
            ranking_path=ranking_path,
            segments_path=segments_path,
            attribution_path=attribution_path,
            report_path=report_path,
        ),
    )

    print(
        json.dumps(
            build_lowfreq_report_success_summary(
                report_id=report_id,
                output_dir=output_dir,
                ranking_path=ranking_path,
                segments_path=segments_path,
                attribution_path=attribution_path,
                report_path=report_path,
                aggregate=aggregate,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
