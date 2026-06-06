"""Config loaders for the NeoTrade3 orchestration bootstrap."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from neotrade3.config_contracts import (
    raise_for_contract_issues,
    validate_orchestrator_config,
)

from .models import OrchestrationPhase, OrchestratorConfig, TaskRegistration


def load_orchestrator_config(file_path: str | Path) -> OrchestratorConfig:
    """Load orchestrator phases and tasks from JSON config."""

    payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
    return orchestrator_config_from_dict(payload)


def orchestrator_config_from_dict(payload: Any) -> OrchestratorConfig:
    if not isinstance(payload, dict):
        raise TypeError("orchestrator config root must be a JSON object")
    payload_dict = cast(dict[str, Any], payload)
    phases_raw = payload_dict.get("phases", [])
    phases = (
        [OrchestrationPhase(str(item)) for item in phases_raw]
        if isinstance(phases_raw, list)
        else []
    )
    tasks_raw = payload_dict.get("tasks", [])
    tasks = (
        [
            TaskRegistration.from_dict(item)
            for item in tasks_raw
            if isinstance(item, dict)
        ]
        if isinstance(tasks_raw, list)
        else []
    )
    config = OrchestratorConfig(
        version=int(payload_dict["version"]),
        description=str(payload_dict.get("description", "")),
        phases=phases,
        tasks=tasks,
    )
    raise_for_contract_issues(
        "orchestrator config", validate_orchestrator_config(config)
    )
    return config
