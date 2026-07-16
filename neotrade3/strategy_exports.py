from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from neotrade3.strategy_config import StrategyConfig
from neotrade3.strategy_config import load_strategy_config
from neotrade3.strategy_config import save_strategy_config


def export_lowfreq_model_store_to_strategy_config(
    *,
    project_root: str | Path,
    model_id: str,
    strategy_id: str,
) -> Path:
    normalized_model_id = str(model_id or "").strip()
    if not normalized_model_id:
        raise ValueError("model_id must be a non-empty string")
    normalized_strategy_id = str(strategy_id or "").strip()
    if not normalized_strategy_id:
        raise ValueError("strategy_id must be a non-empty string")

    root = Path(project_root)
    db_path = root / "var/db/stock_data.db"
    if not db_path.exists():
        raise FileNotFoundError(str(db_path))

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT params_json FROM lowfreq_model_store WHERE model_id = ?",
            (normalized_model_id,),
        ).fetchone()
    except sqlite3.Error as exc:
        raise ValueError("lowfreq_model_store is not available") from exc
    finally:
        conn.close()

    if not row or not row[0]:
        raise ValueError(f"lowfreq_model_store model_id not found: {normalized_model_id}")
    try:
        params_payload: Any = json.loads(str(row[0]))
    except Exception as exc:
        raise ValueError("lowfreq_model_store params_json is not valid JSON") from exc
    if not isinstance(params_payload, dict):
        raise ValueError("lowfreq_model_store params_json must be a JSON object")

    existing: StrategyConfig | None
    try:
        existing = load_strategy_config(project_root=root, strategy_id=normalized_strategy_id)
    except FileNotFoundError:
        existing = None

    config = StrategyConfig(
        strategy_id=normalized_strategy_id,
        version=existing.version if existing is not None else 1,
        description=existing.description if existing is not None else "",
        parameters=params_payload,
    )
    return save_strategy_config(project_root=root, config=config)
