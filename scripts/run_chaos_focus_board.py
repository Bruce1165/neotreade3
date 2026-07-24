#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neotrade3.chaos.m4_eval_monitor import _compute_predicted_direction, _parse_json_object
from neotrade3.cycle_intelligence.fundamental_gate import score_fundamentals
from neotrade3.cycle_intelligence.market_focus_snapshot import (
    build_market_focus_snapshot,
    load_penetration_keywords,
    load_stock_concepts_cache,
)


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


def _resolve_output_roots(
    *,
    project_root: Path,
    output_root: str,
) -> tuple[Path, Path, dict[str, Any]]:
    raw_output_root = str(output_root or "").strip()
    if not raw_output_root:
        return (
            project_root / "var" / "ledgers",
            project_root / "var" / "artifacts",
            {
                "output_mode": "var_symlink_default",
                "output_root": "",
                "canonical_output_mode": "var_symlink_default",
                "temporary_output": False,
            },
        )

    base_root = Path(raw_output_root).expanduser()
    if not base_root.is_absolute():
        base_root = (project_root / base_root).resolve()
    else:
        base_root = base_root.resolve()
    runtime_root = (project_root / ".runtime_outputs").resolve()
    try:
        base_root.relative_to(runtime_root)
    except ValueError as exc:
        raise SystemExit(
            f"output_root must stay under dedicated runtime root: {runtime_root}"
        ) from exc
    return (
        base_root / "ledgers",
        base_root / "artifacts",
        {
            "output_mode": "override_local",
            "output_root": str(base_root),
            "canonical_output_mode": "var_symlink_default",
            "temporary_output": True,
        },
    )


def _write_outputs(
    *,
    ledger_root: Path,
    artifact_root: Path,
    target_date: str,
    payload: dict[str, Any],
    suffix: str,
) -> None:
    name = f"chaos_focus_board_{suffix}.json" if suffix else "chaos_focus_board.json"
    ledger_dir = ledger_root / "chaos_focus_board" / target_date
    artifact_dir = artifact_root / "chaos_focus_board" / target_date
    ledger_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (ledger_dir / name).write_text(text, encoding="utf-8")
    (artifact_dir / name).write_text(text, encoding="utf-8")


def _load_codes_all_a_share(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        f"""
        SELECT s.code
        FROM stocks s
        WHERE {_a_share_universe_sql()}
        ORDER BY s.code ASC
        """
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _load_codes_top_by_amount(conn: sqlite3.Connection, *, trade_date: str, limit: int) -> list[str]:
    rows = conn.execute(
        f"""
        SELECT dp.code
        FROM daily_prices dp
        JOIN stocks s ON s.code = dp.code
        WHERE dp.trade_date = ?
          AND {_a_share_universe_sql()}
          AND dp.amount IS NOT NULL
          AND dp.amount > 0
        ORDER BY dp.amount DESC, dp.code ASC
        LIMIT ?
        """,
        (str(trade_date), int(limit)),
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _load_stock_rows(conn: sqlite3.Connection, *, codes: list[str]) -> dict[str, dict[str, Any]]:
    if not codes:
        return {}
    placeholders = ",".join(["?"] * len(codes))
    rows = conn.execute(
        f"""
        SELECT code, name, sector_lv1, pe_ratio, pb_ratio, roe
        FROM stocks
        WHERE code IN ({placeholders})
        """,
        tuple(codes),
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row or row[0] is None:
            continue
        out[str(row[0])] = {
            "name": str(row[1] or ""),
            "sector_lv1": str(row[2] or ""),
            "pe_ratio": float(row[3]) if isinstance(row[3], (int, float)) else 0.0,
            "pb_ratio": float(row[4]) if isinstance(row[4], (int, float)) else 0.0,
            "roe": float(row[5]) if isinstance(row[5], (int, float)) else 0.0,
        }
    return out


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (str(table),),
    ).fetchone()
    return row is not None


def _load_growth_map(conn: sqlite3.Connection, *, trade_date: str, codes: list[str]) -> dict[str, dict[str, float]]:
    if not codes:
        return {}
    placeholders = ",".join(["?"] * len(codes))
    out: dict[str, dict[str, float]] = {}
    if _table_exists(conn, "financial_reports"):
        rows = conn.execute(
            f"""
            WITH latest AS (
              SELECT code, MAX(report_date) AS report_date
              FROM financial_reports
              WHERE code IN ({placeholders})
                AND report_date <= ?
              GROUP BY code
            )
            SELECT f.code, f.profit_growth_yoy, f.revenue_growth_yoy
            FROM financial_reports f
            JOIN latest l
              ON l.code = f.code
             AND l.report_date = f.report_date
            """,
            (*codes, str(trade_date)),
        ).fetchall()
        for row in rows:
            if not row or row[0] is None:
                continue
            out[str(row[0])] = {
                "profit_growth": float(row[1]) if isinstance(row[1], (int, float)) else 0.0,
                "revenue_growth": float(row[2]) if isinstance(row[2], (int, float)) else 0.0,
            }

    missing_codes = [code for code in codes if str(code) not in out]
    if missing_codes and _table_exists(conn, "stock_fundamentals"):
        placeholders_missing = ",".join(["?"] * len(missing_codes))
        rows = conn.execute(
            f"""
            SELECT code, net_profit_cagr, revenue_cagr
            FROM stock_fundamentals
            WHERE code IN ({placeholders_missing})
            """,
            tuple(missing_codes),
        ).fetchall()
        for row in rows:
            if not row or row[0] is None:
                continue
            out[str(row[0])] = {
                "profit_growth": float(row[1]) if isinstance(row[1], (int, float)) else 0.0,
                "revenue_growth": float(row[2]) if isinstance(row[2], (int, float)) else 0.0,
            }
    return out


def _load_snapshots(
    conn: sqlite3.Connection,
    *,
    trade_date: str,
    codes: list[str],
    thresholds_version: str,
    registry_version: str | None,
    weights_version: str | None,
) -> dict[str, dict[str, Any]]:
    if not codes:
        return {}
    placeholders = ",".join(["?"] * len(codes))
    rv = str(registry_version or "").strip()
    wv = str(weights_version or "").strip()
    rv_sql = " AND registry_version = ?" if rv else ""
    wv_sql = " AND weights_version = ?" if wv else ""
    params: list[Any] = [str(trade_date), str(thresholds_version), *codes]
    if rv:
        params.append(rv)
    if wv:
        params.append(wv)
    rows = conn.execute(
        f"""
        SELECT
          code,
          chaos_status,
          net_energy,
          self_history_reference_json,
          raw_factors_json,
          registry_version,
          weights_version
        FROM chaos_daily_snapshot
        WHERE trade_date = ?
          AND thresholds_version = ?
          AND code IN ({placeholders})
          {rv_sql}
          {wv_sql}
        """,
        params,
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row or row[0] is None:
            continue
        out[str(row[0])] = {
            "chaos_status": str(row[1] or ""),
            "net_energy": float(row[2] or 0.0),
            "self_history_reference_json": str(row[3] or "{}"),
            "raw_factors_json": str(row[4] or "{}"),
            "registry_version": str(row[5] or ""),
            "weights_version": str(row[6] or ""),
        }
    return out


def _round_float(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _state_score(*, snap: dict[str, Any], signal_mode: str, combo_lambda: float, combo_beta: float) -> float:
    ref = _parse_json_object(snap.get("self_history_reference_json"))
    net_energy = float(snap.get("net_energy") or 0.0)
    if signal_mode == "point":
        return float(net_energy)
    if signal_mode == "regime_speed":
        return float(ref.get("yang_speed_mean_in_window") or 0.0)
    if signal_mode == "regime_combo":
        speed = float(ref.get("yang_speed_mean_in_window") or 0.0)
        z = float(ref.get("net_energy_zscore_in_window") or 0.0)
        point_dir = 1.0 if net_energy > 0 else -1.0 if net_energy < 0 else 0.0
        return float(speed + combo_lambda * z + combo_beta * point_dir)
    raise SystemExit(f"unknown signal_mode: {signal_mode}")


def _state_summary(*, snap: dict[str, Any], state_score: float) -> str:
    ref = _parse_json_object(snap.get("self_history_reference_json"))
    net_energy = float(snap.get("net_energy") or 0.0)
    speed = float(ref.get("yang_speed_mean_in_window") or 0.0)
    zscore = float(ref.get("net_energy_zscore_in_window") or 0.0)
    parts: list[str] = []
    if state_score > 0:
        parts.append(f"组合信号为正({state_score:.3f})")
    else:
        parts.append(f"组合信号偏弱({state_score:.3f})")
    if net_energy > 0:
        parts.append(f"净能量为正({net_energy:.3f})")
    else:
        parts.append(f"净能量暂弱({net_energy:.3f})")
    if speed > 0:
        parts.append(f"阳速抬升({speed:.3f})")
    elif speed < 0:
        parts.append(f"阳速走弱({speed:.3f})")
    if zscore > 0.5:
        parts.append(f"相对历史偏强(z={zscore:.2f})")
    elif zscore < -0.5:
        parts.append(f"相对历史偏弱(z={zscore:.2f})")
    parts.append(f"状态分数{state_score:.3f}")
    return "，".join(parts[:4])


def _pulse_risk(raw_factors: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    hazard_high = float(raw_factors.get("hazard_score_5d_high") or 0.0)
    cooldown = float(raw_factors.get("sector_cooldown_detected") or 0.0)
    deteriorating = float(raw_factors.get("sector_trend_deteriorating") or 0.0)
    rollover = float(raw_factors.get("sector_leader_rollover") or 0.0)
    if hazard_high >= 1.0:
        score += 2.0
        reasons.append("短期 hazard 风险高")
    if cooldown >= 1.0:
        score += 1.0
        reasons.append("板块进入退潮")
    if deteriorating >= 1.0:
        score += 1.0
        reasons.append("板块趋势走弱")
    if rollover >= 1.0:
        score += 1.0
        reasons.append("龙头轮动衰减")
    return score, reasons


def _durability_gate(
    *,
    fundamentals: dict[str, Any],
    focus_snapshot: dict[str, Any],
    raw_factors: dict[str, Any],
) -> tuple[str, float, list[str], list[str], list[str], list[str]]:
    quality_reasons: list[str] = []
    configuration_reasons: list[str] = []
    attention_reasons: list[str] = []
    pulse_risk_reasons: list[str] = []

    fundamental_pass, fundamental_score, fundamental_reasons = score_fundamentals(
        fundamentals,
        max_pe=80.0,
        min_profit_growth=10.0,
        min_roe=8.0,
    )
    quality_reasons.extend(fundamental_reasons[:3])
    if not bool(fundamentals.get("table_exists")):
        pe_ttm = float(fundamentals.get("pe_ttm") or 0.0)
        roe = float(fundamentals.get("roe") or 0.0)
        if pe_ttm > 0:
            quality_reasons.append(f"PE{pe_ttm:.1f}仅作参考")
        if roe > 0:
            quality_reasons.append(f"ROE{roe:.1f}%仅作参考")

    config_score = int(focus_snapshot.get("config_score") or 0)
    attention_score = int(focus_snapshot.get("attention_score") or 0)
    focus_pass = bool(focus_snapshot.get("focus_pass"))
    if int(focus_snapshot.get("holder_etf_count") or 0) > 0:
        configuration_reasons.append("存在 ETF 承接")
    if int(focus_snapshot.get("holder_fund_count") or 0) >= 3:
        configuration_reasons.append("基金配置数量较多")
    if int(focus_snapshot.get("index_count") or 0) > 0:
        configuration_reasons.append("纳入指数配置")
    if int(focus_snapshot.get("research_inst") or 0) >= 1:
        attention_reasons.append("存在机构研究覆盖")
    if int(focus_snapshot.get("survey_orgs") or 0) >= 1:
        attention_reasons.append("存在机构调研")
    if int(focus_snapshot.get("consensus_orgs") or 0) >= 1:
        attention_reasons.append("存在一致预期跟踪")

    pulse_risk_score, pulse_risk_reasons = _pulse_risk(raw_factors)

    durability_quality = float(fundamental_score) + 8.0 * config_score + 5.0 * attention_score

    if pulse_risk_score >= 2.0:
        return (
            "durable_reject",
            durability_quality,
            quality_reasons,
            configuration_reasons,
            attention_reasons,
            pulse_risk_reasons,
        )
    if fundamental_pass and (focus_pass or config_score >= 2 or attention_score >= 2):
        return (
            "durable_pass",
            durability_quality,
            quality_reasons,
            configuration_reasons,
            attention_reasons,
            pulse_risk_reasons,
        )
    if not fundamental_pass and config_score == 0 and attention_score == 0:
        pulse_risk_reasons = list(pulse_risk_reasons)
        pulse_risk_reasons.append("缺乏中低频持有价值地板")
        return (
            "durable_reject",
            durability_quality,
            quality_reasons,
            configuration_reasons,
            attention_reasons,
            pulse_risk_reasons,
        )
    return (
        "durable_watch",
        durability_quality,
        quality_reasons,
        configuration_reasons,
        attention_reasons,
        pulse_risk_reasons,
    )


def _why_here(list_type: str) -> str:
    if list_type == "focus_list":
        return "状态主证据成立，且耐持有过滤通过，进入团队主线关注"
    if list_type == "watch_list":
        return "状态主证据成立，但耐持有证据仍偏弱，先进入观察名单"
    return "状态可能仍强，但耐持有过滤拒绝，需警惕短脉冲或退潮风险"


def _why_not_other_lists(list_type: str) -> str:
    if list_type == "focus_list":
        return "已通过耐持有过滤，不属于观察或短脉冲警示对象"
    if list_type == "watch_list":
        return "尚未通过耐持有过滤升级为核心专注，也未恶化到短脉冲警示"
    return "虽可能有状态强势，但不符合核心专注或观察名单的中低频持有要求"


def _cap_list(records: list[dict[str, Any]], *, cap: int) -> list[dict[str, Any]]:
    return records[: max(0, int(cap))]


def _missing_fundamentals_record(
    *,
    trade_date: str,
    code: str,
    name: str,
    snap: dict[str, Any],
    state_strength: float,
) -> dict[str, Any]:
    return {
        "trade_date": str(trade_date),
        "code": str(code),
        "name": str(name or ""),
        "state_summary": _state_summary(snap=snap, state_score=state_strength),
        "exclusion_reason": "缺少增长类基本面数据，当前不进入正式三桶名单",
        "required_fields": ["profit_growth", "revenue_growth"],
        "why_excluded": "Durability Gate 需要最小基本质量证据；在增长类字段缺失时，只进入数据质量排除列表",
    }


def _build_board(
    *,
    stock_conn: sqlite3.Connection,
    chaos_conn: sqlite3.Connection,
    trade_date: str,
    codes: list[str],
    thresholds_version: str,
    registry_version: str | None,
    weights_version: str | None,
    signal_mode: str,
    combo_lambda: float,
    combo_beta: float,
    top_n_per_list: int,
) -> dict[str, Any]:
    stock_map = _load_stock_rows(stock_conn, codes=codes)
    growth_map = _load_growth_map(stock_conn, trade_date=trade_date, codes=codes)
    snapshot_map = _load_snapshots(
        chaos_conn,
        trade_date=trade_date,
        codes=codes,
        thresholds_version=thresholds_version,
        registry_version=registry_version,
        weights_version=weights_version,
    )

    themes_snapshot_dir = PROJECT_ROOT / "var" / "ledgers" / "team_themes"
    stock_concepts_cache = load_stock_concepts_cache(
        themes_snapshot_dir=themes_snapshot_dir,
        stock_concepts_cache=None,
    )
    penetration_keywords = load_penetration_keywords(
        market_intelligence_config_dir=PROJECT_ROOT / "config" / "market_intelligence",
        penetration_keywords_cache=None,
    )
    market_focus_cache: dict[tuple[str, str], dict[str, Any]] = {}
    nonempty_table_cache: dict[str, bool] = {}

    focus_records: list[dict[str, Any]] = []
    watch_records: list[dict[str, Any]] = []
    warning_records: list[dict[str, Any]] = []
    missing_fundamentals_records: list[dict[str, Any]] = []
    skipped_not_ready = 0
    skipped_state_not_positive = 0

    for code in codes:
        snap = snapshot_map.get(str(code))
        base = stock_map.get(str(code), {})
        if not snap or str(snap.get("chaos_status") or "") != "ready":
            skipped_not_ready += 1
            continue
        predicted = _compute_predicted_direction(
            snap=snap,
            signal_mode=signal_mode,
            combo_lambda=combo_lambda,
            combo_beta=combo_beta,
            context_mode="stock_only",
        )
        if predicted <= 0:
            skipped_state_not_positive += 1
            continue

        state_strength = _state_score(
            snap=snap,
            signal_mode=signal_mode,
            combo_lambda=combo_lambda,
            combo_beta=combo_beta,
        )
        if str(code) not in growth_map:
            missing_fundamentals_records.append(
                _missing_fundamentals_record(
                    trade_date=str(trade_date),
                    code=str(code),
                    name=str(base.get("name") or ""),
                    snap=snap,
                    state_strength=state_strength,
                )
            )
            continue
        raw_factors = _parse_json_object(snap.get("raw_factors_json"))
        fundamentals = {
            "table_exists": True,
            "pe_ttm": float(base.get("pe_ratio") or 0.0),
            "profit_growth": float((growth_map.get(str(code)) or {}).get("profit_growth") or 0.0),
            "revenue_growth": float((growth_map.get(str(code)) or {}).get("revenue_growth") or 0.0),
            "roe": float(base.get("roe") or 0.0),
        }
        focus_snapshot = build_market_focus_snapshot(
            stock_conn.cursor(),
            code=str(code),
            stock_name=str(base.get("name") or ""),
            target_date=datetime.strptime(str(trade_date), "%Y-%m-%d").date(),
            market_focus_cache=market_focus_cache,
            nonempty_table_cache=nonempty_table_cache,
            stock_concepts_cache=stock_concepts_cache,
            penetration_keywords=penetration_keywords,
        )
        (
            durability_status,
            durability_quality,
            quality_reasons,
            configuration_reasons,
            attention_reasons,
            pulse_risk_reasons,
        ) = _durability_gate(
            fundamentals=fundamentals,
            focus_snapshot=focus_snapshot,
            raw_factors=raw_factors,
        )
        pulse_risk_score, pulse_risk_reasons_derived = _pulse_risk(raw_factors)
        pulse_risk_reasons = list(dict.fromkeys([*pulse_risk_reasons, *pulse_risk_reasons_derived]))

        if durability_status == "durable_pass":
            list_type = "focus_list"
        elif durability_status == "durable_watch":
            list_type = "watch_list"
        else:
            list_type = "short_pulse_warning"

        primary_reasons = list(
            dict.fromkeys(
                [*quality_reasons[:2], *configuration_reasons[:2], *attention_reasons[:1]]
            )
        )[:5]
        if not primary_reasons:
            primary_reasons = ["状态证据成立，但耐持有解释仍较弱"]
        main_risks = list(dict.fromkeys(pulse_risk_reasons))[:3]
        if not main_risks:
            main_risks = ["未见显著脉冲风险，但仍需跟踪后续退潮变化"]

        record = {
            "trade_date": str(trade_date),
            "code": str(code),
            "name": str(base.get("name") or ""),
            "list_type": list_type,
            "state_summary": _state_summary(snap=snap, state_score=state_strength),
            "durability_status": durability_status,
            "primary_reasons": primary_reasons,
            "main_risks": main_risks,
            "why_here": _why_here(list_type),
            "why_not_other_lists": _why_not_other_lists(list_type),
            "state_strength": _round_float(state_strength),
            "durability_quality": _round_float(durability_quality),
            "risk_penalty": _round_float(pulse_risk_score),
        }
        if list_type == "focus_list":
            focus_records.append(record)
        elif list_type == "watch_list":
            watch_records.append(record)
        else:
            warning_records.append(record)

    def _sort_key(item: dict[str, Any]) -> tuple[float, float, float, str]:
        return (
            -float(item.get("state_strength") or 0.0),
            -float(item.get("durability_quality") or 0.0),
            float(item.get("risk_penalty") or 0.0),
            str(item.get("code") or ""),
        )

    focus_records.sort(key=_sort_key)
    watch_records.sort(key=_sort_key)
    warning_records.sort(key=_sort_key)
    missing_fundamentals_records.sort(
        key=lambda item: (-float(item.get("state_strength") or 0.0), str(item.get("code") or ""))
    )

    return {
        "lists": {
            "focus_list": _cap_list(focus_records, cap=top_n_per_list),
            "watch_list": _cap_list(watch_records, cap=top_n_per_list),
            "short_pulse_warning": _cap_list(warning_records, cap=top_n_per_list),
        },
        "exclusions": {
            "missing_fundamentals": _cap_list(missing_fundamentals_records, cap=top_n_per_list),
        },
        "summary": {
            "candidate_count_before_cap": {
                "focus_list": len(focus_records),
                "watch_list": len(watch_records),
                "short_pulse_warning": len(warning_records),
            },
            "selected_count_after_cap": {
                "focus_list": len(_cap_list(focus_records, cap=top_n_per_list)),
                "watch_list": len(_cap_list(watch_records, cap=top_n_per_list)),
                "short_pulse_warning": len(_cap_list(warning_records, cap=top_n_per_list)),
            },
            "exclusion_count_before_cap": {
                "missing_fundamentals": len(missing_fundamentals_records),
            },
            "exclusion_count_after_cap": {
                "missing_fundamentals": len(_cap_list(missing_fundamentals_records, cap=top_n_per_list)),
            },
            "skipped": {
                "not_ready": int(skipped_not_ready),
                "state_not_positive": int(skipped_state_not_positive),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--universe", choices=["all_a_share", "top_by_amount"], default="all_a_share")
    parser.add_argument("--code-limit", type=int, default=200)
    parser.add_argument("--top-n-per-list", type=int, default=50)
    parser.add_argument("--thresholds-version", default="chaos_thresholds_v0")
    parser.add_argument("--registry-version", default="")
    parser.add_argument("--weights-version", default="")
    parser.add_argument("--signal-mode", choices=["point", "regime_speed", "regime_combo"], default="regime_combo")
    parser.add_argument("--combo-lambda", type=float, default=0.5)
    parser.add_argument("--combo-beta", type=float, default=-0.5)
    parser.add_argument("--stock-db", default=str(PROJECT_ROOT / "var" / "db" / "stock_data.db"))
    parser.add_argument("--chaos-db", default=str(PROJECT_ROOT / "var" / "db" / "chaos_factor_matrix_a_share.db"))
    parser.add_argument("--output-root", default="")
    parser.add_argument("--retention-days", type=int, default=14)
    parser.add_argument("--report-suffix", default="")
    args = parser.parse_args()

    stock_db = Path(str(args.stock_db)).expanduser().resolve()
    chaos_db = Path(str(args.chaos_db)).expanduser().resolve()
    if not stock_db.exists():
        raise SystemExit(f"stock db not found: {stock_db}")
    if not chaos_db.exists():
        raise SystemExit(f"chaos db not found: {chaos_db}")

    ledger_root, artifact_root, output_meta = _resolve_output_roots(
        project_root=PROJECT_ROOT,
        output_root=str(args.output_root),
    )
    generated_at = datetime.utcnow()
    retention_days = max(1, int(args.retention_days))
    expires_after = (generated_at + timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with sqlite3.connect(str(stock_db)) as stock_conn, sqlite3.connect(str(chaos_db)) as chaos_conn:
        if str(args.universe) == "all_a_share":
            codes = _load_codes_all_a_share(stock_conn)
        else:
            codes = _load_codes_top_by_amount(
                stock_conn,
                trade_date=str(args.trade_date),
                limit=max(1, int(args.code_limit)),
            )

        board = _build_board(
            stock_conn=stock_conn,
            chaos_conn=chaos_conn,
            trade_date=str(args.trade_date),
            codes=codes,
            thresholds_version=str(args.thresholds_version),
            registry_version=str(args.registry_version).strip() or None,
            weights_version=str(args.weights_version).strip() or None,
            signal_mode=str(args.signal_mode),
            combo_lambda=float(args.combo_lambda),
            combo_beta=float(args.combo_beta),
            top_n_per_list=max(1, int(args.top_n_per_list)),
        )

    payload = {
        "_meta": {
            "status": "ok",
            "generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "requested_by": "run_chaos_focus_board",
            "report_suffix": str(args.report_suffix).strip(),
            "output_mode": output_meta["output_mode"],
            "output_root": output_meta["output_root"],
            "canonical_output_mode": output_meta["canonical_output_mode"],
            "temporary_output": output_meta["temporary_output"],
            "retention_days": retention_days,
            "expires_after": expires_after,
        },
        "board_contract": {
            "list_objects": ["focus_list", "watch_list", "short_pulse_warning"],
            "mutual_exclusive": True,
            "consumer_mode": "team_meeting_first",
            "state_context_mode": "stock_only",
            "durability_gate_version": "v0_minimal",
        },
        "run_config": {
            "trade_date": str(args.trade_date),
            "universe": str(args.universe),
            "code_count": len(codes),
            "top_n_per_list": max(1, int(args.top_n_per_list)),
            "thresholds_version": str(args.thresholds_version),
            "registry_version": str(args.registry_version or "").strip(),
            "weights_version": str(args.weights_version or "").strip(),
            "signal_mode": str(args.signal_mode),
            "combo_lambda": float(args.combo_lambda),
            "combo_beta": float(args.combo_beta),
        },
        "lists": board["lists"],
        "exclusions": board["exclusions"],
        "summary": board["summary"],
    }
    _write_outputs(
        ledger_root=ledger_root,
        artifact_root=artifact_root,
        target_date=str(args.trade_date),
        payload=payload,
        suffix=str(args.report_suffix).strip(),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
