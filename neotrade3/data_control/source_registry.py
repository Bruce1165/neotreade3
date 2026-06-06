"""Source registry models and loaders for the NeoTrade3 data-control bootstrap."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from neotrade3.config_contracts import (
    raise_for_contract_issues,
    validate_source_registry,
)


@dataclass
class SourceRegistration:
    """Minimal source registration used by the bootstrap data-control chain."""

    source_id: str
    display_name: str
    source_type: str
    enabled: bool
    owner: str
    stage_support: list[str]
    official_write_allowed: bool
    notes: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceRegistration":
        stage_support_raw = payload.get("stage_support", [])
        stage_support = (
            [str(item) for item in stage_support_raw]
            if isinstance(stage_support_raw, list)
            else []
        )
        return cls(
            source_id=str(payload["source_id"]),
            display_name=str(payload["display_name"]),
            source_type=str(payload["source_type"]),
            enabled=bool(payload["enabled"]),
            owner=str(payload["owner"]),
            stage_support=stage_support,
            official_write_allowed=bool(payload.get("official_write_allowed", False)),
            notes=str(payload.get("notes", "")),
        )


@dataclass
class SourceRegistry:
    """Collection wrapper for registered data sources."""

    version: int
    description: str
    sources: list[SourceRegistration]

    @classmethod
    def from_file(cls, file_path: str | Path) -> "SourceRegistry":
        payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: Any) -> "SourceRegistry":
        if not isinstance(payload, dict):
            raise TypeError("source registry root must be a JSON object")
        payload_dict = cast(dict[str, Any], payload)
        sources_raw = payload_dict.get("sources", [])
        sources = (
            [
                SourceRegistration.from_dict(item)
                for item in sources_raw
                if isinstance(item, dict)
            ]
            if isinstance(sources_raw, list)
            else []
        )
        registry = cls(
            version=int(payload_dict["version"]),
            description=str(payload_dict.get("description", "")),
            sources=sources,
        )
        raise_for_contract_issues("source registry", validate_source_registry(registry))
        return registry

    def enabled_sources(self) -> list[SourceRegistration]:
        return [source for source in self.sources if source.enabled]

    def sources_for_stage(self, stage: str) -> list[SourceRegistration]:
        return [
            source for source in self.enabled_sources() if stage in source.stage_support
        ]
