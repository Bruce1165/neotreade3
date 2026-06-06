"""Screener registry models for NeoTrade3 bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ScreenerRegistryError(ValueError):
    """Raised when a screener registry file is malformed."""


@dataclass
class ScreenerRegistration:
    screener_id: str
    display_name: str
    enabled: bool
    entrypoint: str
    tags: list[str]
    notes: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScreenerRegistration":
        tags_value = payload.get("tags", [])
        tags = (
            [str(item) for item in tags_value] if isinstance(tags_value, list) else []
        )
        return cls(
            screener_id=str(payload["screener_id"]),
            display_name=str(payload["display_name"]),
            enabled=bool(payload.get("enabled", True)),
            entrypoint=str(payload["entrypoint"]),
            tags=tags,
            notes=str(payload.get("notes", "")),
        )


@dataclass
class ScreenerRegistry:
    version: int
    description: str
    screeners: list[ScreenerRegistration]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScreenerRegistry":
        if not isinstance(payload, dict):
            raise ScreenerRegistryError("screener registry root must be a JSON object")

        version = payload.get("version")
        if not isinstance(version, int) or version < 1:
            raise ScreenerRegistryError(
                "screener registry version must be a positive integer"
            )

        screeners = [
            ScreenerRegistration.from_dict(item)
            for item in payload.get("screeners", [])
            if isinstance(item, dict)
        ]
        if not screeners:
            raise ScreenerRegistryError(
                "screener registry must contain at least one screener"
            )

        screener_ids = [screener.screener_id for screener in screeners]
        duplicates = sorted(
            {item for item in screener_ids if screener_ids.count(item) > 1}
        )
        if duplicates:
            raise ScreenerRegistryError(
                "screener registry contains duplicate screener_id values: "
                + ", ".join(duplicates)
            )

        for screener in screeners:
            if not screener.screener_id.strip():
                raise ScreenerRegistryError("screener_id must be a non-empty string")
            if not screener.display_name.strip():
                raise ScreenerRegistryError("display_name must be a non-empty string")
            if not screener.entrypoint.strip():
                raise ScreenerRegistryError("entrypoint must be a non-empty string")

        enabled_screeners = [screener for screener in screeners if screener.enabled]
        if len(enabled_screeners) != 7:
            raise ScreenerRegistryError(
                "enabled screeners must be exactly 7 for NeoTrade3 v1 scope"
            )

        non_internal = sorted(
            screener.screener_id
            for screener in enabled_screeners
            if "internal_formula" not in set(screener.tags)
        )
        if non_internal:
            raise ScreenerRegistryError(
                "enabled screeners must be internal_formula in NeoTrade3 v1 scope: "
                + ", ".join(non_internal)
            )

        return cls(
            version=version,
            description=str(payload.get("description", "")),
            screeners=screeners,
        )
