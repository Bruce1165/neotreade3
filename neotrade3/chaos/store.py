from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def resolve_chaos_db_path(*, project_root: str | Path) -> Path:
    root = Path(project_root)
    p = root / "var" / "db" / "chaos_factor_matrix.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _utc_ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_chaos_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chaos_factor_registry(
          registry_version TEXT PRIMARY KEY,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chaos_factor_values(
          code TEXT NOT NULL,
          trade_date TEXT NOT NULL,
          factor_id TEXT NOT NULL,
          registry_version TEXT NOT NULL,
          factor_value REAL,
          created_at TEXT NOT NULL,
          PRIMARY KEY (code, trade_date, factor_id, registry_version)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chaos_daily_snapshot(
          code TEXT NOT NULL,
          trade_date TEXT NOT NULL,
          registry_version TEXT NOT NULL,
          weights_version TEXT NOT NULL,
          thresholds_version TEXT NOT NULL,
          chaos_status TEXT NOT NULL,
          yin_value REAL,
          yang_value REAL,
          net_energy REAL,
          yin_yang_ratio TEXT,
          reference_mode TEXT,
          self_history_reference_json TEXT NOT NULL,
          raw_factors_json TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY (code, trade_date, registry_version, weights_version, thresholds_version)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chaos_factor_values_date ON chaos_factor_values(trade_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chaos_factor_values_factor ON chaos_factor_values(factor_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chaos_daily_snapshot_date ON chaos_daily_snapshot(trade_date)"
    )
    conn.commit()


def upsert_registry(
    conn: sqlite3.Connection,
    *,
    registry_version: str,
    payload: dict[str, Any],
) -> None:
    ensure_chaos_schema(conn)
    conn.execute(
        """
        INSERT INTO chaos_factor_registry(registry_version, payload_json, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(registry_version) DO UPDATE SET
          payload_json=excluded.payload_json
        """,
        (
            str(registry_version),
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            _utc_ts(),
        ),
    )
    conn.commit()


def upsert_factor_values(
    conn: sqlite3.Connection,
    *,
    code: str,
    trade_date: str,
    registry_version: str,
    values: dict[str, float],
) -> None:
    ensure_chaos_schema(conn)
    ts = _utc_ts()
    rows = []
    for factor_id, v in (values or {}).items():
        fid = str(factor_id or "").strip()
        if not fid:
            continue
        rows.append((str(code), str(trade_date), fid, str(registry_version), float(v), ts))
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO chaos_factor_values(code, trade_date, factor_id, registry_version, factor_value, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(code, trade_date, factor_id, registry_version) DO UPDATE SET
          factor_value=excluded.factor_value
        """,
        rows,
    )
    conn.commit()


def upsert_daily_snapshot(
    conn: sqlite3.Connection,
    *,
    code: str,
    trade_date: str,
    registry_version: str,
    weights_version: str,
    thresholds_version: str,
    snapshot: dict[str, Any],
) -> None:
    ensure_chaos_schema(conn)
    self_ref = snapshot.get("self_history_reference") if isinstance(snapshot, dict) else {}
    raw_factors = snapshot.get("raw_factors") if isinstance(snapshot, dict) else {}
    evidence = snapshot.get("evidence") if isinstance(snapshot, dict) else []
    conn.execute(
        """
        INSERT INTO chaos_daily_snapshot(
          code, trade_date, registry_version, weights_version, thresholds_version,
          chaos_status, yin_value, yang_value, net_energy, yin_yang_ratio, reference_mode,
          self_history_reference_json, raw_factors_json, evidence_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code, trade_date, registry_version, weights_version, thresholds_version) DO UPDATE SET
          chaos_status=excluded.chaos_status,
          yin_value=excluded.yin_value,
          yang_value=excluded.yang_value,
          net_energy=excluded.net_energy,
          yin_yang_ratio=excluded.yin_yang_ratio,
          reference_mode=excluded.reference_mode,
          self_history_reference_json=excluded.self_history_reference_json,
          raw_factors_json=excluded.raw_factors_json,
          evidence_json=excluded.evidence_json
        """,
        (
            str(code),
            str(trade_date),
            str(registry_version),
            str(weights_version),
            str(thresholds_version),
            str(snapshot.get("chaos_status") or "pending"),
            float(snapshot.get("yin_value") or 0.0),
            float(snapshot.get("yang_value") or 0.0),
            float(snapshot.get("net_energy") or 0.0),
            str(snapshot.get("yin_yang_ratio") or ""),
            str(snapshot.get("reference_mode") or ""),
            json.dumps(self_ref if isinstance(self_ref, dict) else {}, ensure_ascii=False, separators=(",", ":")),
            json.dumps(raw_factors if isinstance(raw_factors, dict) else {}, ensure_ascii=False, separators=(",", ":")),
            json.dumps(list(evidence or []), ensure_ascii=False, separators=(",", ":")),
            _utc_ts(),
        ),
    )
    conn.commit()

