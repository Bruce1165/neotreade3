"""NeoTrade2 feature manual inventory loading and validation."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


class FeatureInventoryError(ValueError):
    """Raised when the feature inventory file is malformed."""


REQUIRED_STRING_FIELDS = (
    "feature_id",
    "feature_name",
    "domain",
    "status",
    "definition",
    "run_logic",
)
REQUIRED_LIST_FIELDS = ("data_sources", "owner_modules", "evidence")


def _require_non_empty_string(item: dict[str, Any], field: str) -> None:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FeatureInventoryError(
            f"feature inventory field '{field}' must be a non-empty string"
        )


def _require_non_empty_list(item: dict[str, Any], field: str) -> None:
    value = item.get(field)
    if not isinstance(value, list) or not value:
        raise FeatureInventoryError(
            f"feature inventory field '{field}' must be a non-empty list"
        )


def validate_feature_inventory(items: list[dict[str, Any]]) -> None:
    feature_ids: list[str] = []

    for item in items:
        if not isinstance(item, dict):
            raise FeatureInventoryError("feature inventory items must be JSON objects")
        for field in REQUIRED_STRING_FIELDS:
            _require_non_empty_string(item, field)
        for field in REQUIRED_LIST_FIELDS:
            _require_non_empty_list(item, field)
        feature_ids.append(str(item["feature_id"]))

    duplicates = sorted(
        {feature_id for feature_id in feature_ids if feature_ids.count(feature_id) > 1}
    )
    if duplicates:
        raise FeatureInventoryError(
            "feature inventory contains duplicate feature_id values: "
            + ", ".join(duplicates)
        )


def load_feature_inventory(file_path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise FeatureInventoryError("feature inventory root must be a JSON array")
    validate_feature_inventory(payload)
    return payload


def build_feature_inventory_payload(file_path: str | Path) -> dict[str, Any]:
    items = load_feature_inventory(file_path)
    domain_counts = Counter(item["domain"] for item in items)
    status_counts = Counter(item["status"] for item in items)
    return {
        "feature_count": len(items),
        "domains": dict(sorted(domain_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "features": items,
    }
