from __future__ import annotations

import json
from pathlib import Path

import pytest

from neotrade3.config_contracts import ConfigContractError
from neotrade3.strategy_config import load_strategy_config
from neotrade3.strategy_config import strategy_config_path


def test_load_strategy_config_reads_and_validates_payload(tmp_path: Path) -> None:
    config_path = strategy_config_path(project_root=tmp_path, strategy_id="lowfreq_v16")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "strategy_id": "lowfreq_v16",
                "version": 1,
                "description": "test",
                "parameters": {"k": "v"},
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    config = load_strategy_config(project_root=tmp_path, strategy_id="lowfreq_v16")

    assert config.strategy_id == "lowfreq_v16"
    assert config.version == 1
    assert config.parameters["k"] == "v"


def test_load_strategy_config_raises_when_strategy_id_mismatches_filename(tmp_path: Path) -> None:
    config_path = strategy_config_path(project_root=tmp_path, strategy_id="lowfreq_v16")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "strategy_id": "other",
                "version": 1,
                "description": "test",
                "parameters": {},
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_strategy_config(project_root=tmp_path, strategy_id="lowfreq_v16")


def test_load_strategy_config_raises_contract_error_for_invalid_payload(tmp_path: Path) -> None:
    config_path = strategy_config_path(project_root=tmp_path, strategy_id="lowfreq_v16")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "strategy_id": "lowfreq_v16",
                "version": 0,
                "description": "test",
                "parameters": {},
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigContractError):
        load_strategy_config(project_root=tmp_path, strategy_id="lowfreq_v16")


def test_strategy_config_path_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        strategy_config_path(project_root=tmp_path, strategy_id="../evil")
