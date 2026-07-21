from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ChaosOperationalGateReport:
    start_date: str
    end_date: str
    code_count: int
    trade_date_count: int
    expected_rows: int
    snapshot_rows: int
    ready_rows: int
    pending_rows: int
    missing_snapshot_rows: int
    missing_ready_factor_rows: int


def _count_expected_rows(*, codes: list[str], trade_dates: list[str]) -> int:
    return int(len(codes)) * int(len(trade_dates))


def _as_str_list(items: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for x in items:
        s = str(x or "").strip()
        if s:
            out.append(s)
    return out


def verify_chaos_operational_gates(
    conn: sqlite3.Connection,
    *,
    start_date: str,
    end_date: str,
    codes: list[str],
    trade_dates: list[str],
    thresholds_version: str,
    registry_version: str | None = None,
    weights_version: str | None = None,
    allow_missing_ratio: float = 0.0,
    min_ready_ratio: float = 0.0,
) -> ChaosOperationalGateReport:
    normalized_codes = _as_str_list(codes)
    normalized_dates = _as_str_list(trade_dates)
    expected_rows = _count_expected_rows(codes=normalized_codes, trade_dates=normalized_dates)
    if expected_rows <= 0:
        raise RuntimeError("expected_rows <= 0")

    placeholders_codes = ",".join(["?"] * len(normalized_codes))
    placeholders_dates = ",".join(["?"] * len(normalized_dates))
    rv = str(registry_version or "").strip()
    wv = str(weights_version or "").strip()
    rv_sql = " AND registry_version = ?" if rv else ""
    wv_sql = " AND weights_version = ?" if wv else ""
    base_params = list(normalized_codes) + list(normalized_dates) + [str(thresholds_version)]
    if rv:
        base_params.append(rv)
    if wv:
        base_params.append(wv)

    snapshot_rows = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM chaos_daily_snapshot
        WHERE code IN ({placeholders_codes})
          AND trade_date IN ({placeholders_dates})
          AND thresholds_version = ?
          {rv_sql}
          {wv_sql}
        """,
        base_params,
    ).fetchone()[0]
    snapshot_rows_i = int(snapshot_rows or 0)

    missing_snapshot_rows = int(expected_rows - snapshot_rows_i)
    allow_missing = int(round(float(expected_rows) * float(max(0.0, allow_missing_ratio))))
    if missing_snapshot_rows > allow_missing:
        raise RuntimeError(
            f"chaos_snapshot_rows_missing: missing={missing_snapshot_rows} expected={expected_rows} got={snapshot_rows_i}"
        )

    status_rows = conn.execute(
        f"""
        SELECT chaos_status, COUNT(*)
        FROM chaos_daily_snapshot
        WHERE code IN ({placeholders_codes})
          AND trade_date IN ({placeholders_dates})
          AND thresholds_version = ?
          {rv_sql}
          {wv_sql}
        GROUP BY chaos_status
        """,
        base_params,
    ).fetchall()
    by_status = {str(r[0] or "").strip(): int(r[1] or 0) for r in status_rows if r}
    ready_rows = int(by_status.get("ready", 0))
    pending_rows = int(by_status.get("pending", 0))

    min_ready = int(round(float(expected_rows) * float(max(0.0, min_ready_ratio))))
    if ready_rows < min_ready:
        raise RuntimeError(
            f"chaos_ready_ratio_too_low: ready={ready_rows} expected_min={min_ready} expected_total={expected_rows}"
        )

    ref_rows = conn.execute(
        f"""
        SELECT code, trade_date, self_history_reference_json
        FROM chaos_daily_snapshot
        WHERE code IN ({placeholders_codes})
          AND trade_date IN ({placeholders_dates})
          AND thresholds_version = ?
          {rv_sql}
          {wv_sql}
        LIMIT 5000
        """,
        base_params,
    ).fetchall()
    for code, trade_date, ref_json in ref_rows:
        ref = json.loads(str(ref_json or "{}"))
        if not isinstance(ref, dict):
            raise RuntimeError(f"self_history_reference_not_dict: {code} {trade_date}")
        if "regime_anchor_date" not in ref:
            raise RuntimeError(f"self_history_reference_missing_regime_anchor_date: {code} {trade_date}")
        flip_rate = ref.get("flip_rate_in_window")
        if flip_rate is None:
            raise RuntimeError(f"self_history_reference_missing_flip_rate: {code} {trade_date}")
        if float(flip_rate) < 0.0 or float(flip_rate) > 1.0:
            raise RuntimeError(f"flip_rate_out_of_range: {code} {trade_date} {flip_rate}")
        if ref.get("yang_speed_mean_in_window") is None:
            raise RuntimeError(f"self_history_reference_missing_yang_speed_mean: {code} {trade_date}")

    pending_rows_sample = conn.execute(
        f"""
        SELECT code, trade_date, yin_value, yang_value
        FROM chaos_daily_snapshot
        WHERE code IN ({placeholders_codes})
          AND trade_date IN ({placeholders_dates})
          AND thresholds_version = ?
          {rv_sql}
          {wv_sql}
          AND chaos_status = 'pending'
        LIMIT 2000
        """,
        base_params,
    ).fetchall()
    for code, trade_date, yin, yang in pending_rows_sample:
        if float(yin or 0.0) != 0.0 or float(yang or 0.0) != 0.0:
            raise RuntimeError(f"pending_not_fail_closed: {code} {trade_date} yin={yin} yang={yang}")

    missing_ready_factor_rows = conn.execute(
        f"""
        WITH ready_snaps AS (
          SELECT DISTINCT code, trade_date, registry_version
          FROM chaos_daily_snapshot
          WHERE code IN ({placeholders_codes})
            AND trade_date IN ({placeholders_dates})
            AND thresholds_version = ?
            {rv_sql}
            {wv_sql}
            AND chaos_status = 'ready'
        ),
        ready_factors AS (
          SELECT DISTINCT code, trade_date, registry_version
          FROM chaos_factor_values
          WHERE code IN ({placeholders_codes})
            AND trade_date IN ({placeholders_dates})
        )
        SELECT COUNT(*)
        FROM ready_snaps s
        LEFT JOIN ready_factors f
          ON f.code = s.code AND f.trade_date = s.trade_date AND f.registry_version = s.registry_version
        WHERE f.code IS NULL
        """,
        list(normalized_codes)
        + list(normalized_dates)
        + [str(thresholds_version)]
        + ([rv] if rv else [])
        + ([wv] if wv else [])
        + list(normalized_codes)
        + list(normalized_dates),
    ).fetchone()[0]
    missing_ready_factor_rows_i = int(missing_ready_factor_rows or 0)
    if missing_ready_factor_rows_i > 0:
        raise RuntimeError(f"missing_ready_factor_rows: {missing_ready_factor_rows_i}")

    return ChaosOperationalGateReport(
        start_date=str(start_date),
        end_date=str(end_date),
        code_count=int(len(normalized_codes)),
        trade_date_count=int(len(normalized_dates)),
        expected_rows=int(expected_rows),
        snapshot_rows=int(snapshot_rows_i),
        ready_rows=int(ready_rows),
        pending_rows=int(pending_rows),
        missing_snapshot_rows=int(missing_snapshot_rows),
        missing_ready_factor_rows=int(missing_ready_factor_rows_i),
    )
