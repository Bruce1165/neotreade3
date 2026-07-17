from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from neotrade3.decision_engine.cli import main
from neotrade3.decision_engine.front_context_store import (
    build_decision_m3_front_context_record_id,
    read_decision_m3_front_context_artifact,
    read_decision_m3_front_context_ledger,
)


def _seed_formal_input_db(db_path: Path) -> date:
    target = date(2026, 7, 7)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE stocks (
                code TEXT PRIMARY KEY,
                name TEXT,
                asset_type TEXT,
                is_delisted INTEGER,
                sector_lv1 TEXT,
                sector_lv2 TEXT,
                last_trade_date TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE daily_prices (
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                turnover REAL,
                preclose REAL,
                pct_change REAL,
                updated_at TEXT
            )
            """
        )
        conn.execute("CREATE TABLE trading_calendar_cache (trade_date TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE trading_calendar_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            """
            INSERT INTO stocks(code, name, asset_type, is_delisted, sector_lv1, sector_lv2, last_trade_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("000001", "平安银行", "stock", 0, "金融", "银行", target.isoformat()),
        )
        conn.execute(
            "INSERT INTO trading_calendar_meta(key, value) VALUES (?, ?)",
            ("calendar_source", "trading_calendar_cache"),
        )
        conn.execute(
            "INSERT INTO trading_calendar_meta(key, value) VALUES (?, ?)",
            ("calendar_covered_until", target.isoformat()),
        )
        for i in range(20):
            trade_date = (target - timedelta(days=i)).isoformat()
            conn.execute(
                "INSERT INTO trading_calendar_cache(trade_date) VALUES (?)",
                (trade_date,),
            )
            conn.execute(
                """
                INSERT INTO daily_prices(
                    code, trade_date, open, high, low, close, volume, amount, turnover, preclose, pct_change, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "000001",
                    trade_date,
                    10.0 + i,
                    10.5 + i,
                    9.8 + i,
                    10.2 + i,
                    1000000.0 + i,
                    20000000.0 + i * 1000.0,
                    3.0 + i * 0.1,
                    10.0 + i,
                    0.5,
                    "2026-07-07T15:00:00Z",
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return target


def test_cli_materialize_front_contexts_writes_artifact_and_ledger(tmp_path: Path) -> None:
    (tmp_path / "var/db").mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "var/db/stock_data.db"
    target = _seed_formal_input_db(db_path)

    code = main(
        [
            "materialize-front-contexts",
            "--project-root",
            str(tmp_path),
            "--db-path",
            str(db_path),
            "--target-date",
            target.isoformat(),
            "--codes",
            "000001",
            "--run-id",
            target.isoformat(),
            "--source-run-id",
            target.isoformat(),
        ]
    )

    assert code == 0

    record_id = build_decision_m3_front_context_record_id(
        stock_code="000001",
        trade_date=target.isoformat(),
    )
    artifact = read_decision_m3_front_context_artifact(
        project_root=tmp_path,
        record_id=record_id,
    )
    ledger = read_decision_m3_front_context_ledger(
        project_root=tmp_path,
        record_id=record_id,
    )
    assert artifact is not None
    assert artifact["object_type"] == "m3_front_context"
    assert artifact["object_version"] == 2
    assert artifact["run_id"] == target.isoformat()
    assert artifact["source_run_id"] == target.isoformat()
    assert artifact["identify_state"]["run_id"] == target.isoformat()
    assert artifact["identify_state"]["object_version"] == 2
    assert ledger is not None
    assert ledger.record_id == record_id


def test_cli_materialize_front_contexts_fails_closed_on_missing_code(tmp_path: Path) -> None:
    (tmp_path / "var/db").mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "var/db/stock_data.db"
    target = _seed_formal_input_db(db_path)

    code = main(
        [
            "materialize-front-contexts",
            "--project-root",
            str(tmp_path),
            "--db-path",
            str(db_path),
            "--target-date",
            target.isoformat(),
            "--codes",
            "000001,000009",
            "--run-id",
            target.isoformat(),
            "--source-run-id",
            target.isoformat(),
        ]
    )

    assert code == 1

    record_id = build_decision_m3_front_context_record_id(
        stock_code="000001",
        trade_date=target.isoformat(),
    )
    assert (
        tmp_path
        / "var/artifacts/m3_front_contexts"
        / record_id
        / "front_context.json"
    ).exists() is False
    assert (
        tmp_path
        / "var/ledgers/m3_front_contexts"
        / record_id
        / "front_context.json"
    ).exists() is False
