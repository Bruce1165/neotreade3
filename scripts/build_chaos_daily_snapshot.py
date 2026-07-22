#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neotrade3.analysis.resonance_scorer import MarketPhase as ResonanceMarketPhase
from neotrade3.analysis.resonance_scorer import ResonanceScorer
from neotrade3.analysis.sector_rotation import SectorRotationAnalyzer
from neotrade3.analysis.stock_tiering import StockTieringAnalyzer
from neotrade3.chaos.registry import load_chaos_factor_registry, registry_to_payload
from neotrade3.chaos.store import (
    ensure_chaos_schema,
    resolve_chaos_db_path,
    upsert_daily_snapshot,
    upsert_factor_values,
    upsert_registry,
)
from neotrade3.cycle_intelligence.market_focus_snapshot import (
    build_market_focus_snapshot,
    load_penetration_keywords,
    load_stock_concepts_cache,
)
from neotrade3.chaos.projection_v1 import (
    ChaosProjectionContext,
    project_chaos_yin_yang_v1,
)
from neotrade3.chaos.regime_reference_v1 import compute_self_history_reference_v1
from neotrade3.chaos.weights import load_chaos_weights
from neotrade3.decision_engine.hazard_predictor_v0 import build_hazard_snapshot_v0_t2
from neotrade3.decision_engine.chaos_model_v0 import build_chaos_snapshot_v0


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


def _load_trade_dates(conn: sqlite3.Connection, *, start_date: str, end_date: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE trade_date BETWEEN ? AND ?
        ORDER BY trade_date ASC
        """,
        (str(start_date), str(end_date)),
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _load_codes_code_asc(conn: sqlite3.Connection, *, limit: int) -> list[str]:
    rows = conn.execute(
        f"""
        SELECT s.code
        FROM stocks s
        WHERE {_a_share_universe_sql()}
        ORDER BY s.code ASC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]

def _load_codes_top_by_amount(
    conn: sqlite3.Connection,
    *,
    start_date: str,
    end_date: str,
    limit: int,
) -> list[str]:
    rows = conn.execute(
        f"""
        WITH universe AS (
          SELECT s.code
          FROM stocks s
          WHERE {_a_share_universe_sql()}
        ),
        agg AS (
          SELECT d.code, SUM(COALESCE(d.amount, 0.0)) AS amount_sum
          FROM daily_prices d
          JOIN universe u ON u.code = d.code
          WHERE d.trade_date BETWEEN ? AND ?
          GROUP BY d.code
        )
        SELECT a.code
        FROM agg a
        WHERE a.amount_sum > 0
        ORDER BY a.amount_sum DESC, a.code ASC
        LIMIT ?
        """,
        (str(start_date), str(end_date), int(limit)),
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _load_codes_from_file(path: str) -> list[str]:
    p = Path(str(path))
    if not p.is_file():
        raise SystemExit(f"codes file not found: {p}")
    txt = p.read_text(encoding="utf-8").strip()
    if not txt:
        return []
    try:
        data = json.loads(txt)
    except Exception:
        data = None
    if isinstance(data, list):
        return [str(x).strip() for x in data if str(x).strip()]
    return [line.strip() for line in txt.splitlines() if line.strip()]


def _load_stock_base_map(conn: sqlite3.Connection, *, codes: list[str]) -> dict[str, dict[str, str]]:
    codes_norm = [str(c).strip() for c in list(codes or []) if str(c).strip()]
    if not codes_norm:
        return {}
    placeholders = ",".join(["?"] * len(codes_norm))
    rows = conn.execute(
        f"""
        SELECT code, name, sector_lv1
        FROM stocks
        WHERE code IN ({placeholders})
        """,
        tuple(codes_norm),
    ).fetchall()
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        if not row or row[0] is None:
            continue
        out[str(row[0])] = {
            "name": str(row[1] or ""),
            "sector_lv1": str(row[2] or ""),
        }
    return out


def _load_stock_fundamental_map(conn: sqlite3.Connection, *, codes: list[str]) -> dict[str, dict[str, float]]:
    codes_norm = [str(c).strip() for c in list(codes or []) if str(c).strip()]
    if not codes_norm:
        return {}
    placeholders = ",".join(["?"] * len(codes_norm))
    rows = conn.execute(
        f"""
        SELECT code, pe_ratio, pb_ratio, roe, total_market_cap
        FROM stocks
        WHERE code IN ({placeholders})
        """,
        tuple(codes_norm),
    ).fetchall()
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        if not row or row[0] is None:
            continue
        out[str(row[0])] = {
            "pe_ratio": float(row[1]) if isinstance(row[1], (int, float)) else 0.0,
            "pb_ratio": float(row[2]) if isinstance(row[2], (int, float)) else 0.0,
            "roe": float(row[3]) if isinstance(row[3], (int, float)) else 0.0,
            "market_cap": float(row[4]) if isinstance(row[4], (int, float)) else 0.0,
        }
    return out


def _load_daily_market_map(conn: sqlite3.Connection, *, trade_date: str, codes: list[str]) -> dict[str, dict[str, float]]:
    codes_norm = [str(c).strip() for c in list(codes or []) if str(c).strip()]
    if not codes_norm:
        return {}
    placeholders = ",".join(["?"] * len(codes_norm))
    rows = conn.execute(
        f"""
        SELECT code, amount, turnover
        FROM daily_prices
        WHERE trade_date = ?
          AND code IN ({placeholders})
        """,
        (str(trade_date), *codes_norm),
    ).fetchall()
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        if not row or row[0] is None:
            continue
        out[str(row[0])] = {
            "amount": float(row[1]) if isinstance(row[1], (int, float)) else 0.0,
            "turnover": float(row[2]) if isinstance(row[2], (int, float)) else 0.0,
        }
    return out


def _load_amount_rank_map(conn: sqlite3.Connection, *, trade_date: str) -> dict[str, int]:
    rows = conn.execute(
        f"""
        SELECT dp.code, dp.amount
        FROM daily_prices dp
        JOIN stocks s ON s.code = dp.code
        WHERE dp.trade_date = ?
          AND {_a_share_universe_sql()}
          AND dp.amount IS NOT NULL
          AND dp.amount > 0
        """,
        (str(trade_date),),
    ).fetchall()
    items = [(str(r[0]), float(r[1])) for r in rows if r and r[0] and isinstance(r[1], (int, float))]
    items.sort(key=lambda x: (-x[1], x[0]))
    out: dict[str, int] = {}
    for idx, (code, _amount) in enumerate(items, start=1):
        out[code] = int(idx)
    return out


def _load_sector_amount_rank_map(
    conn: sqlite3.Connection, *, trade_date: str
) -> dict[str, int]:
    rows = conn.execute(
        f"""
        SELECT s.sector_lv1, SUM(COALESCE(dp.amount, 0.0)) AS total_amount
        FROM daily_prices dp
        JOIN stocks s ON s.code = dp.code
        WHERE dp.trade_date = ?
          AND {_a_share_universe_sql()}
        GROUP BY s.sector_lv1
        HAVING total_amount > 0
        """,
        (str(trade_date),),
    ).fetchall()
    items = [(str(r[0] or ""), float(r[1] or 0.0)) for r in rows if r and r[0]]
    items.sort(key=lambda x: (-x[1], x[0]))
    out: dict[str, int] = {}
    for idx, (sector, _amount) in enumerate(items, start=1):
        out[sector] = int(idx)
    return out


def _load_sector_daily_stats(
    conn: sqlite3.Connection, *, trade_dates: list[str]
) -> dict[str, dict[str, dict[str, float]]]:
    dates_norm = [str(d).strip() for d in list(trade_dates or []) if str(d).strip()]
    if not dates_norm:
        return {}
    placeholders = ",".join(["?"] * len(dates_norm))
    rows = conn.execute(
        f"""
        SELECT dp.trade_date, s.sector_lv1, SUM(COALESCE(dp.amount, 0.0)) AS total_amount, AVG(COALESCE(dp.pct_change, 0.0)) AS avg_pct
        FROM daily_prices dp
        JOIN stocks s ON s.code = dp.code
        WHERE dp.trade_date IN ({placeholders})
          AND {_a_share_universe_sql()}
        GROUP BY dp.trade_date, s.sector_lv1
        """,
        tuple(dates_norm),
    ).fetchall()
    out: dict[str, dict[str, dict[str, float]]] = {}
    for row in rows:
        if not row or row[0] is None:
            continue
        d = str(row[0])
        sector = str(row[1] or "")
        out.setdefault(d, {})[sector] = {
            "sector_total_amount_today": float(row[2] or 0.0),
            "sector_avg_pct_today": float(row[3] or 0.0),
        }
    return out


def _compute_sector_roll_20(
    *,
    trade_dates: list[str],
    sector_daily: dict[str, dict[str, dict[str, float]]],
) -> dict[str, dict[str, dict[str, float]]]:
    out: dict[str, dict[str, dict[str, float]]] = {}
    for i, d in enumerate(list(trade_dates or [])):
        window = trade_dates[max(0, i - 19) : i + 1]
        sectors: set[str] = set()
        for wd in window:
            sectors.update((sector_daily.get(wd) or {}).keys())
        out_d: dict[str, dict[str, float]] = {}
        for sector in sectors:
            amounts: list[float] = []
            pcts: list[float] = []
            for wd in window:
                item = (sector_daily.get(wd) or {}).get(sector) or {}
                amounts.append(float(item.get("sector_total_amount_today") or 0.0))
                pcts.append(float(item.get("sector_avg_pct_today") or 0.0))
            avg_amount_20 = float(sum(amounts)) / float(len(amounts)) if amounts else 0.0
            avg_pct_20 = float(sum(pcts)) / float(len(pcts)) if pcts else 0.0
            today_item = (sector_daily.get(d) or {}).get(sector) or {}
            today_amount = float(today_item.get("sector_total_amount_today") or 0.0)
            ratio = float(today_amount) / float(avg_amount_20) if float(avg_amount_20) > 0 else 0.0
            out_d[sector] = {
                "sector_amount_ratio_today_over_avg20": float(ratio),
                "sector_avg_pct_20d": float(avg_pct_20),
            }
        out[d] = out_d
    return out


def _load_market_daily_stats(
    conn: sqlite3.Connection, *, trade_dates: list[str]
) -> dict[str, dict[str, float]]:
    dates_norm = [str(d).strip() for d in list(trade_dates or []) if str(d).strip()]
    if not dates_norm:
        return {}
    placeholders = ",".join(["?"] * len(dates_norm))
    rows = conn.execute(
        f"""
        SELECT
          dp.trade_date,
          COUNT(*) AS n,
          SUM(CASE WHEN COALESCE(dp.pct_change, 0.0) < 0 THEN 1 ELSE 0 END) AS down_n,
          AVG(COALESCE(dp.pct_change, 0.0)) AS avg_pct
        FROM daily_prices dp
        JOIN stocks s ON s.code = dp.code
        WHERE dp.trade_date IN ({placeholders})
          AND {_a_share_universe_sql()}
        GROUP BY dp.trade_date
        """,
        tuple(dates_norm),
    ).fetchall()
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        if not row or row[0] is None:
            continue
        d = str(row[0])
        n = float(row[1] or 0.0)
        down_n = float(row[2] or 0.0)
        avg_pct = float(row[3] or 0.0)
        down_ratio = float(down_n) / float(n) if float(n) > 0 else 0.0
        out[d] = {
            "market_down_ratio": float(down_ratio),
            "market_avg_pct_today": float(avg_pct),
        }
    return out


def _compute_market_roll_20(
    *,
    trade_dates: list[str],
    market_daily: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for i, d in enumerate(list(trade_dates or [])):
        window = trade_dates[max(0, i - 19) : i + 1]
        pcts: list[float] = []
        downs: list[float] = []
        for wd in window:
            item = market_daily.get(wd) or {}
            pcts.append(float(item.get("market_avg_pct_today") or 0.0))
            downs.append(float(item.get("market_down_ratio") or 0.0))
        avg_pct_20 = float(sum(pcts)) / float(len(pcts)) if pcts else 0.0
        avg_down_ratio_20 = float(sum(downs)) / float(len(downs)) if downs else 0.0
        out[d] = {
            "market_avg_pct_20d": float(avg_pct_20),
            "market_down_ratio_20d": float(avg_down_ratio_20),
        }
    return out


def _extract_stock_codes_from_screener(data: Any) -> list[str]:
    if isinstance(data, list):
        return [str(c) for c in data if str(c).strip()]
    if not isinstance(data, dict):
        return []
    for key in ("picked", "picked_examples", "hits", "pool", "stocks"):
        v = data.get(key)
        if not isinstance(v, list):
            continue
        out: list[str] = []
        for item in v:
            if isinstance(item, dict):
                code = item.get("code") or item.get("stock_code")
                if code:
                    out.append(str(code))
            elif isinstance(item, (str, int)):
                out.append(str(item))
        if out:
            return [c for c in out if str(c).strip()]
    return []


def _extract_stock_codes_from_lab(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    artifacts = data.get("artifacts", data)
    if isinstance(artifacts, dict):
        for _key, value in artifacts.items():
            if isinstance(value, dict):
                for sub_key in ("pool", "hits", "stocks", "candidates", "positions"):
                    codes = value.get(sub_key)
                    if isinstance(codes, list):
                        return [str(c) if isinstance(c, (str, int)) else str(c.get("code", "")) for c in codes if c]
                trades = value.get("trades")
                if isinstance(trades, dict):
                    for trade_key in ("entry_trades", "exit_trades"):
                        codes = trades.get(trade_key)
                        if isinstance(codes, list):
                            return [str(c) if isinstance(c, (str, int)) else str(c.get("code", "")) for c in codes if c]
    for key in ("pool", "hits", "stocks", "candidates", "positions"):
        codes = data.get(key)
        if isinstance(codes, list):
            return [str(c) if isinstance(c, (str, int)) else str(c.get("code", "")) for c in codes if c]
    trades = data.get("trades")
    if isinstance(trades, dict):
        for trade_key in ("entry_trades", "exit_trades"):
            codes = trades.get(trade_key)
            if isinstance(codes, list):
                return [str(c) if isinstance(c, (str, int)) else str(c.get("code", "")) for c in codes if c]
    return []


def _load_screener_hit_count_map(*, project_root: Path, target_date: str) -> dict[str, int]:
    hits: dict[str, int] = {}
    artifacts_dir = project_root / "var" / "artifacts" / "screener_runs" / str(target_date)
    ledgers_dir = project_root / "var" / "ledgers" / "screener_runs" / str(target_date)
    for search_dir in (artifacts_dir, ledgers_dir):
        if not search_dir.is_dir():
            continue
        for fp in sorted(search_dir.glob("*.json")):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            codes = _extract_stock_codes_from_screener(data)
            for c in codes:
                code = str(c or "").strip()
                if not code:
                    continue
                hits[code] = int(hits.get(code, 0)) + 1
    return hits


def _load_lab_hit_count_map(*, project_root: Path, target_date: str) -> dict[str, int]:
    hits: dict[str, int] = {}
    lab_dir = project_root / "var" / "artifacts" / "lab_runs" / str(target_date)
    if not lab_dir.is_dir():
        return hits
    for fp in sorted(lab_dir.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        codes = _extract_stock_codes_from_lab(data)
        for c in codes:
            code = str(c or "").strip()
            if not code:
                continue
            hits[code] = int(hits.get(code, 0)) + 1
    return hits


def _write_ledger_and_artifact(*, project_root: Path, target_date: str, payload: dict) -> None:
    ledger_dir = project_root / "var" / "ledgers" / "chaos" / target_date
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "chaos_run.json"
    ledger_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_dir = project_root / "var" / "artifacts" / "chaos" / target_date
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "chaos_daily.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--code-limit", type=int, default=200)
    parser.add_argument("--universe", choices=["top_by_amount", "code_asc"], default="top_by_amount")
    parser.add_argument("--codes-file", default="")
    parser.add_argument("--chaos-db", default="")
    parser.add_argument("--registry-id", default="v0")
    parser.add_argument("--weights-version", default="")
    parser.add_argument("--thresholds-version", default="chaos_thresholds_v0")
    parser.add_argument("--regime-confirm-days", type=int, default=3)
    parser.add_argument("--regime-deadzone-eps", type=float, default=0.15)
    parser.add_argument("--fixed-window-days", type=int, default=45)
    args = parser.parse_args()

    start_date = str(args.start_date).strip()
    end_date = str(args.end_date).strip()
    if not start_date or not end_date:
        raise SystemExit("missing date range")

    stock_db = PROJECT_ROOT / "var" / "db" / "stock_data.db"
    if not stock_db.is_file():
        raise SystemExit(f"stock db not found: {stock_db}")

    registry = load_chaos_factor_registry(project_root=PROJECT_ROOT, registry_id=str(args.registry_id))
    weights_version = str(args.weights_version).strip()
    if not weights_version:
        if str(args.registry_id) == "v1":
            weights_version = "chaos_weights_v1"
        else:
            weights_version = "chaos_weights_v0"
    weights = load_chaos_weights(project_root=PROJECT_ROOT, weights_version=weights_version) if str(args.registry_id) == "v1" else None
    chaos_db_arg = str(args.chaos_db).strip()
    if chaos_db_arg:
        chaos_db = Path(chaos_db_arg)
        chaos_db.parent.mkdir(parents=True, exist_ok=True)
    else:
        chaos_db = resolve_chaos_db_path(project_root=PROJECT_ROOT)

    t0 = time.time()
    with sqlite3.connect(str(stock_db)) as stock_conn, sqlite3.connect(str(chaos_db)) as chaos_conn:
        chaos_conn.execute("PRAGMA busy_timeout=60000")
        ensure_chaos_schema(chaos_conn)
        upsert_registry(chaos_conn, registry_version=registry.version, payload=registry_to_payload(registry))

        trade_dates = _load_trade_dates(stock_conn, start_date=start_date, end_date=end_date)
        codes_file = str(args.codes_file).strip()
        if codes_file:
            codes = _load_codes_from_file(codes_file)
        elif str(args.universe) == "top_by_amount":
            codes = _load_codes_top_by_amount(
                stock_conn,
                start_date=start_date,
                end_date=end_date,
                limit=int(args.code_limit),
            )
            if not codes:
                codes = _load_codes_code_asc(stock_conn, limit=int(args.code_limit))
        else:
            codes = _load_codes_code_asc(stock_conn, limit=int(args.code_limit))

        regime_confirm_days = int(args.regime_confirm_days)
        deadzone_eps = float(args.regime_deadzone_eps)
        fixed_window_days = int(args.fixed_window_days)
        dates_processed: list[str] = []
        net_series_by_code: dict[str, list[float]] = {str(c): [] for c in list(codes or [])}

        row_count = 0
        weights_versions: set[str] = set()
        stock_base = _load_stock_base_map(stock_conn, codes=codes)
        stock_fund = _load_stock_fundamental_map(stock_conn, codes=codes)
        sector_daily = _load_sector_daily_stats(stock_conn, trade_dates=trade_dates)
        sector_roll_20 = _compute_sector_roll_20(trade_dates=trade_dates, sector_daily=sector_daily)
        market_daily = _load_market_daily_stats(stock_conn, trade_dates=trade_dates)
        market_roll_20 = _compute_market_roll_20(trade_dates=trade_dates, market_daily=market_daily)
        themes_snapshot_dir = PROJECT_ROOT / "var" / "ledgers" / "team_themes"
        stock_concepts_cache = load_stock_concepts_cache(
            themes_snapshot_dir=themes_snapshot_dir,
            stock_concepts_cache=None,
        )
        penetration_keywords = load_penetration_keywords(
            market_intelligence_config_dir=PROJECT_ROOT / "config" / "market_intelligence",
            penetration_keywords_cache=None,
        )
        market_focus_cache: dict[tuple[str, str], dict[str, object]] = {}
        nonempty_table_cache: dict[str, bool] = {}
        resonance_scorer = ResonanceScorer(market_phase=ResonanceMarketPhase.TRANSITION)
        sector_rotation_analyzer = SectorRotationAnalyzer(db_path=str(stock_db))
        stock_tiering_analyzer = StockTieringAnalyzer(db_path=str(stock_db))
        for d in trade_dates:
            dates_processed.append(str(d))
            d_obj = date.fromisoformat(d)
            cur = stock_conn.cursor()
            screener_hit_count_map = _load_screener_hit_count_map(project_root=PROJECT_ROOT, target_date=str(d))
            lab_hit_count_map = _load_lab_hit_count_map(project_root=PROJECT_ROOT, target_date=str(d))
            amount_rank_map = _load_amount_rank_map(stock_conn, trade_date=d)
            amount_universe_size = int(len(amount_rank_map))
            sector_amount_rank_map = _load_sector_amount_rank_map(stock_conn, trade_date=d)
            sector_count = int(len(sector_amount_rank_map))
            daily_market_map = _load_daily_market_map(stock_conn, trade_date=d, codes=codes)
            sector_rps_map: dict[str, float] = {}
            try:
                sr = sector_rotation_analyzer.analyze(target_date=str(d))
                for item in list(sr.top_sectors or []):
                    sector_rps_map[str(getattr(item, "sector_name", "") or "")] = float(getattr(item, "rps_120", 0.0) or 0.0)
                for item in list(sr.weakening_sectors or []):
                    sector_rps_map.setdefault(str(getattr(item, "sector_name", "") or ""), float(getattr(item, "rps_120", 0.0) or 0.0))
                for item in list(sr.mainline_sectors or []):
                    sector_rps_map.setdefault(str(getattr(item, "sector_name", "") or ""), float(getattr(item, "rps_120", 0.0) or 0.0))
                for item in list(sr.emerging_sectors or []):
                    sector_rps_map.setdefault(str(getattr(item, "sector_name", "") or ""), float(getattr(item, "rps_120", 0.0) or 0.0))
            except Exception:
                sector_rps_map = {}
            tier_map: dict[str, float] = {}
            try:
                tier_result = stock_tiering_analyzer.analyze(codes=list(codes), target_date=d_obj)
                for ts in list(tier_result.all_tiered_stocks or []):
                    tier_map[str(ts.code)] = float(ts.metrics.leadership_score or 0.0)
            except Exception:
                tier_map = {}
            for code in codes:
                snap = build_chaos_snapshot_v0(cur, code=str(code), target_date=d_obj)
                snap["factor_registry_version"] = str(registry.version)
                raw = snap.get("raw_factors") if isinstance(snap, dict) else {}
                if isinstance(raw, dict):
                    base_info = stock_base.get(str(code)) or {}
                    sector_lv1 = str(base_info.get("sector_lv1") or "")
                    raw["screener_hit_count"] = float(screener_hit_count_map.get(str(code), 0))
                    raw["lab_hit_count"] = float(lab_hit_count_map.get(str(code), 0))
                    dm = daily_market_map.get(str(code)) or {}
                    amount = float(dm.get("amount") or 0.0)
                    turnover = float(dm.get("turnover") or 0.0)
                    raw["amount"] = float(amount)
                    raw["turnover"] = float(turnover)
                    raw["amount_rank"] = float(amount_rank_map.get(str(code)) or 0)
                    fund = stock_fund.get(str(code)) or {}
                    raw["pe_ratio"] = float(fund.get("pe_ratio") or 0.0)
                    raw["pb_ratio"] = float(fund.get("pb_ratio") or 0.0)
                    raw["roe"] = float(fund.get("roe") or 0.0)
                    raw["market_cap"] = float(fund.get("market_cap") or 0.0)
                    sd = (sector_daily.get(str(d)) or {}).get(sector_lv1) or {}
                    sr20 = (sector_roll_20.get(str(d)) or {}).get(sector_lv1) or {}
                    raw["sector_total_amount_today"] = float(sd.get("sector_total_amount_today") or 0.0)
                    raw["sector_amount_ratio_today_over_avg20"] = float(sr20.get("sector_amount_ratio_today_over_avg20") or 0.0)
                    raw["sector_avg_pct_today"] = float(sd.get("sector_avg_pct_today") or 0.0)
                    raw["sector_avg_pct_20d"] = float(sr20.get("sector_avg_pct_20d") or 0.0)
                    raw["sector_rps_120"] = float(sector_rps_map.get(sector_lv1) or 0.0)
                    raw["tier_leadership_score"] = float(tier_map.get(str(code)) or 0.0)
                    pct_change = float(raw.get("pct_change") or 0.0)
                    price_trend = max(0.0, min(1.0, (pct_change + 10.0) / 20.0))
                    volume_trend = max(0.0, min(1.0, float(turnover) / 20.0)) if float(turnover) > 0 else 0.5
                    ma_alignment = bool(pct_change > 0 and float(amount) > 0)
                    breakout_signal = bool(abs(pct_change) >= 9.5)
                    raw["resonance_score"] = float(
                        resonance_scorer.calculate_technical_score(
                            rps_120=float(raw.get("sector_rps_120") or 50.0),
                            rps_250=50.0,
                            price_trend=float(price_trend),
                            volume_trend=float(volume_trend),
                            ma_alignment=bool(ma_alignment),
                            breakout_signal=bool(breakout_signal),
                        )
                    )
                    name = str(base_info.get("name") or "")
                    mf = build_market_focus_snapshot(
                        stock_conn.cursor(),
                        code=str(code),
                        stock_name=name,
                        target_date=d_obj,
                        market_focus_cache=market_focus_cache,
                        nonempty_table_cache=nonempty_table_cache,
                        stock_concepts_cache=stock_concepts_cache,
                        penetration_keywords=penetration_keywords,
                    )
                    raw["holder_etf_count"] = float(mf.get("holder_etf_count") or 0.0)
                    raw["holder_fund_count"] = float(mf.get("holder_fund_count") or 0.0)
                    raw["index_count"] = float(mf.get("index_count") or 0.0)
                    raw["config_score"] = float(mf.get("config_score") or 0.0)
                    raw["attention_score"] = float(mf.get("attention_score") or 0.0)
                    raw["research_inst"] = float(mf.get("research_inst") or 0.0)
                    raw["consensus_orgs"] = float(mf.get("consensus_orgs") or 0.0)
                    raw["survey_orgs"] = float(mf.get("survey_orgs") or 0.0)
                    raw["survey_count"] = float(mf.get("survey_count") or 0.0)
                    hz = build_hazard_snapshot_v0_t2(cur, code=str(code), target_date=d_obj)
                    hz_ready = str(hz.get("risk_status") or "").strip() == "ready"
                    hz_5d = int(hz.get("stock_top_risk_5d") or 0) if hz_ready else 0
                    raw["hazard_score_5d_high"] = 1.0 if hz_ready and int(hz_5d) >= 70 else 0.0
                    md = market_daily.get(str(d)) or {}
                    mr20 = market_roll_20.get(str(d)) or {}
                    market_down_ratio = float(md.get("market_down_ratio") or 0.0)
                    market_avg_pct_today = float(md.get("market_avg_pct_today") or 0.0)
                    market_avg_pct_20d = float(mr20.get("market_avg_pct_20d") or 0.0)
                    raw["market_breadth_weak"] = 1.0 if float(market_down_ratio) > 0.6 else 0.0
                    raw["market_price_trend_weak"] = 1.0 if float(market_avg_pct_20d) < 0.0 and float(market_avg_pct_today) < 0.0 else 0.0
                    raw["market_drawdown_weak"] = 1.0 if float(market_down_ratio) > 0.75 and float(market_avg_pct_today) < -1.0 else 0.0
                    sector_amount_ratio = float(raw.get("sector_amount_ratio_today_over_avg20") or 0.0)
                    sector_avg_pct_today = float(raw.get("sector_avg_pct_today") or 0.0)
                    sector_avg_pct_20d = float(raw.get("sector_avg_pct_20d") or 0.0)
                    sector_rps_120 = float(raw.get("sector_rps_120") or 0.0)
                    raw["sector_cooldown_detected"] = 1.0 if float(sector_amount_ratio) < 0.8 and float(sector_avg_pct_today) < 0.0 else 0.0
                    raw["sector_trend_deteriorating"] = 1.0 if float(sector_avg_pct_20d) < 0.0 else 0.0
                    raw["sector_leader_rollover"] = 1.0 if float(sector_rps_120) < 40.0 and float(sector_avg_pct_today) < 0.0 else 0.0
                    if str(args.registry_id) == "v1" and str(snap.get("chaos_status") or "") == "ready":
                        ctx = ChaosProjectionContext(
                            amount_rank=int(amount_rank_map.get(str(code)) or 0),
                            amount_universe_size=int(amount_universe_size),
                            sector_amount_rank=int(sector_amount_rank_map.get(sector_lv1) or 0),
                            sector_count=int(sector_count),
                        )
                        proj = project_chaos_yin_yang_v1(
                            raw_factors=raw,
                            registry=registry,
                            ctx=ctx,
                            weights_override=dict(weights.weights) if weights else None,
                        )
                        snap["yin_value"] = float(proj["yin_value"])
                        snap["yang_value"] = float(proj["yang_value"])
                        snap["net_energy"] = float(proj["net_energy"])
                        snap["yin_yang_ratio"] = str(proj["yin_yang_ratio"])
                        snap["weights_version"] = str(weights.version) if weights else weights_version
                        series = net_series_by_code.get(str(code))
                        if series is not None:
                            series.append(float(snap.get("net_energy") or 0.0))
                            ref = compute_self_history_reference_v1(
                                dates=list(dates_processed),
                                net_energy_series=list(series),
                                deadzone_eps=float(deadzone_eps),
                                confirm_days=int(regime_confirm_days),
                                fixed_window_days=int(fixed_window_days),
                            )
                            ref_payload = dict(ref.__dict__)
                            ref_payload["deadzone_eps"] = float(deadzone_eps)
                            ref_payload["confirm_days"] = int(regime_confirm_days)
                            snap["self_history_reference"] = ref_payload
                            snap["reference_mode"] = "projection_v1_regime_any_flip"
                    else:
                        series = net_series_by_code.get(str(code))
                        if series is not None:
                            series.append(float(snap.get("net_energy") or 0.0))
                weights_v = str(snap.get("weights_version") or weights_version).strip() or str(weights_version)
                weights_versions.add(weights_v)
                upsert_daily_snapshot(
                    chaos_conn,
                    code=str(code),
                    trade_date=str(d),
                    registry_version=str(registry.version),
                    weights_version=weights_v,
                    thresholds_version=str(args.thresholds_version),
                    snapshot=snap,
                )
                if isinstance(raw, dict) and raw:
                    upsert_factor_values(
                        chaos_conn,
                        code=str(code),
                        trade_date=str(d),
                        registry_version=str(registry.version),
                        values={str(k): float(v) for k, v in raw.items() if isinstance(v, (int, float))},
                    )
                row_count += 1

    elapsed = round(time.time() - t0, 3)
    payload = {
        "_meta": {
            "status": "ok",
            "requested_by": "build_chaos_daily_snapshot",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "range": {"start_date": start_date, "end_date": end_date},
        "registry_version": registry.version,
        "thresholds_version": str(args.thresholds_version),
        "weights_versions": sorted(list(weights_versions)),
        "code_limit": int(args.code_limit),
        "universe": str(args.universe),
        "days": int(len(trade_dates)),
        "rows_written": int(row_count),
        "chaos_db_path": str(chaos_db),
        "elapsed_seconds": float(elapsed),
    }
    _write_ledger_and_artifact(project_root=PROJECT_ROOT, target_date=end_date, payload=payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
