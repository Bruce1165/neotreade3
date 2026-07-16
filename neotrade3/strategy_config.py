from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from neotrade3.config_contracts import raise_for_contract_issues


@dataclass(frozen=True)
class StrategyConfig:
    strategy_id: str
    version: int
    description: str
    parameters: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: Any) -> "StrategyConfig":
        if not isinstance(payload, dict):
            raise TypeError("strategy config root must be a JSON object")
        payload_dict = cast(dict[str, Any], payload)
        parameters_raw = payload_dict.get("parameters", {})
        parameters = parameters_raw if isinstance(parameters_raw, dict) else {}
        config = cls(
            strategy_id=str(payload_dict.get("strategy_id") or "").strip(),
            version=int(payload_dict.get("version") or 0),
            description=str(payload_dict.get("description") or "").strip(),
            parameters=parameters,
        )
        raise_for_contract_issues("strategy config", validate_strategy_config(config))
        return config

    def to_payload(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "version": self.version,
            "description": self.description,
            "parameters": self.parameters,
        }


def validate_strategy_config(config: StrategyConfig) -> list[str]:
    issues: list[str] = []
    if not config.strategy_id:
        issues.append("strategy_id must be a non-empty string")
    if config.version <= 0:
        issues.append("version must be a positive integer")
    if not isinstance(config.parameters, dict):
        issues.append("parameters must be a JSON object")
    return issues


def _normalize_strategy_id(raw_strategy_id: str) -> str:
    normalized = str(raw_strategy_id or "").strip()
    if not normalized:
        raise ValueError("strategy_id must be a non-empty string")
    path = Path(normalized)
    if path.is_absolute() or len(path.parts) != 1 or path.name != normalized:
        raise ValueError(f"invalid strategy_id: {raw_strategy_id}")
    if ".." in path.parts:
        raise ValueError(f"invalid strategy_id: {raw_strategy_id}")
    return normalized


def strategy_config_path(*, project_root: str | Path, strategy_id: str) -> Path:
    normalized = _normalize_strategy_id(strategy_id)
    return Path(project_root) / "config/strategies" / f"{normalized}.json"


def load_strategy_config(*, project_root: str | Path, strategy_id: str) -> StrategyConfig:
    file_path = strategy_config_path(project_root=project_root, strategy_id=strategy_id)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    config = StrategyConfig.from_dict(payload)
    if config.strategy_id != Path(file_path).stem:
        raise ValueError(
            "strategy_id in payload must match config filename stem: "
            f"{config.strategy_id} != {Path(file_path).stem}"
        )
    return config


def save_strategy_config(*, project_root: str | Path, config: StrategyConfig) -> Path:
    file_path = strategy_config_path(project_root=project_root, strategy_id=config.strategy_id)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = config.to_payload()
    file_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return file_path
