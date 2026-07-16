from __future__ import annotations

import json
import sqlite3
from http import HTTPStatus
from pathlib import Path

import pytest

from lowfreq_engine_v16_advanced import LowFreqTradingEngineV16

from apps.api.main import BootstrapApiService
from apps.api.shared import ApiError
from neotrade3.strategy_config import load_strategy_config
from neotrade3.strategy_exports import export_lowfreq_model_store_to_strategy_config
from neotrade3.strategies.lowfreq_v16 import apply_lowfreq_v16_strategy_config


def test_lowfreq_engine_v16_applies_strategy_config_file_when_present(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config/strategies/lowfreq_v16.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "strategy_id": "lowfreq_v16",
                "version": 1,
                "description": "test",
                "parameters": {"BUY_THRESHOLD": 92.0, "MAX_POSITIONS": 1},
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "var/db").mkdir(parents=True, exist_ok=True)
    service = BootstrapApiService(project_root=tmp_path)

    engine = service._lowfreq_engine_v16()

    assert float(getattr(engine, "BUY_THRESHOLD")) == 92.0
    assert int(getattr(engine, "MAX_POSITIONS")) == 1


def test_lowfreq_engine_v16_fails_closed_when_strategy_config_invalid(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config/strategies/lowfreq_v16.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "strategy_id": "lowfreq_v16",
                "version": 1,
                "description": "test",
                "parameters": {"MAX_POSITIONS": "2"},
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "var/db").mkdir(parents=True, exist_ok=True)
    service = BootstrapApiService(project_root=tmp_path)

    with pytest.raises(ApiError) as exc:
        service._lowfreq_engine_v16()

    assert exc.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert exc.value.code == "invalid_strategy_config"


def test_export_lowfreq_model_store_params_json_to_strategy_config_and_apply(
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
                    {"BUY_THRESHOLD": 87.0, "MAX_POSITIONS": 2, "REBALANCE_DAYS": 20},
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

    export_lowfreq_model_store_to_strategy_config(
        project_root=tmp_path,
        model_id="lowfreq_engine_v16_advanced",
        strategy_id="lowfreq_v16",
    )

    service = BootstrapApiService(project_root=tmp_path)
    engine = service._lowfreq_engine_v16()

    assert float(getattr(engine, "BUY_THRESHOLD")) == 87.0
    assert int(getattr(engine, "MAX_POSITIONS")) == 2
    assert int(getattr(engine, "REBALANCE_DAYS")) == 20


def test_repo_lowfreq_v16_json_is_consumable() -> None:
    project_root = Path(__file__).resolve().parents[2]
    (project_root / "var/db").mkdir(parents=True, exist_ok=True)
    strategy = load_strategy_config(project_root=project_root, strategy_id="lowfreq_v16")
    engine = LowFreqTradingEngineV16(db_path=project_root / "var/db/stock_data.db")

    apply_lowfreq_v16_strategy_config(engine=engine, strategy=strategy)

    assert float(getattr(engine, "BUY_THRESHOLD")) == float(
        strategy.parameters["BUY_THRESHOLD"]
    )
