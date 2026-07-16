from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from neotrade3.strategies.cli import main
from neotrade3.strategy_config import load_strategy_config


def test_cli_export_lowfreq_model_store_to_strategy_updates_lowfreq_v16_json(
    tmp_path: Path,
) -> None:
    (tmp_path / "var/db").mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "var/db/stock_data.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lowfreq_model_store (
                model_id TEXT PRIMARY KEY,
                params_json TEXT NOT NULL,
                source TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO lowfreq_model_store (
                model_id,
                params_json,
                source,
                requested_by,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "lowfreq_engine_v16_advanced",
                json.dumps(
                    {"BUY_THRESHOLD": 86.0, "MAX_POSITIONS": 2, "REBALANCE_DAYS": 18},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "test",
                "pytest",
                "2026-07-16T00:00:00Z",
                "2026-07-16T00:00:00Z",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    code = main(
        [
            "export-lowfreq-model-store-to-strategy",
            "--project-root",
            str(tmp_path),
        ]
    )

    assert code == 0

    exported = load_strategy_config(project_root=tmp_path, strategy_id="lowfreq_v16")
    assert exported.parameters["BUY_THRESHOLD"] == 86.0
    assert exported.parameters["MAX_POSITIONS"] == 2
    assert exported.parameters["REBALANCE_DAYS"] == 18
