"""NeoTrade3 migration mapping utilities.

This module keeps migration decision data separate from the NeoTrade2 feature inventory:

- feature inventory: what exists in NeoTrade2 (facts + evidence)
- feature mapping: where the feature should land in NeoTrade3 (decision + status)
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from neotrade3.migration.feature_manual import load_feature_inventory


class FeatureMappingError(ValueError):
    """Raised when the feature mapping file is malformed."""


ALLOWED_MIGRATION_STATUSES = {
    "planned",
    "scaffolded",
    "implemented",
    "deferred",
    "retired",
}
ALLOWED_MIGRATION_STRATEGIES = {
    "migrate",
    "replace",
    "merge",
    "drop",
}


def _require_non_empty_string(item: dict[str, Any], field: str) -> None:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FeatureMappingError(
            f"feature mapping field '{field}' must be a non-empty string"
        )


def _require_list(item: dict[str, Any], field: str) -> list[Any]:
    value = item.get(field)
    if not isinstance(value, list):
        raise FeatureMappingError(f"feature mapping field '{field}' must be a list")
    return value


def _require_dict(item: dict[str, Any], field: str) -> dict[str, Any]:
    value = item.get(field)
    if not isinstance(value, dict):
        raise FeatureMappingError(f"feature mapping field '{field}' must be an object")
    return value


def validate_feature_mapping(
    payload: dict[str, Any],
    *,
    inventory_feature_ids: set[str],
    expected_scope_domain: str | None = None,
) -> None:
    if not isinstance(payload, dict):
        raise FeatureMappingError("feature mapping root must be a JSON object")

    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        raise FeatureMappingError("feature mapping version must be a positive integer")

    scope = payload.get("scope")
    if not isinstance(scope, dict):
        raise FeatureMappingError("feature mapping scope must be a JSON object")
    _require_non_empty_string(scope, "domain")
    if (
        expected_scope_domain is not None
        and scope.get("domain") != expected_scope_domain
    ):
        raise FeatureMappingError(
            f"feature mapping scope.domain mismatch: expected '{expected_scope_domain}', got '{scope.get('domain')}'"
        )

    mappings = payload.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        raise FeatureMappingError(
            "feature mapping mappings must be a non-empty JSON array"
        )

    feature_ids: list[str] = []
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise FeatureMappingError(
                "feature mapping mappings items must be JSON objects"
            )

        _require_non_empty_string(mapping, "feature_id")
        _require_non_empty_string(mapping, "migration_strategy")
        _require_non_empty_string(mapping, "migration_status")
        target = _require_dict(mapping, "target")

        strategy = str(mapping["migration_strategy"])
        if strategy not in ALLOWED_MIGRATION_STRATEGIES:
            raise FeatureMappingError(
                "feature mapping migration_strategy must be one of: "
                + ", ".join(sorted(ALLOWED_MIGRATION_STRATEGIES))
            )

        status = str(mapping["migration_status"])
        if status not in ALLOWED_MIGRATION_STATUSES:
            raise FeatureMappingError(
                "feature mapping migration_status must be one of: "
                + ", ".join(sorted(ALLOWED_MIGRATION_STATUSES))
            )

        neotrade3_domains = _require_list(target, "neotrade3_domains")
        if not neotrade3_domains:
            raise FeatureMappingError(
                "feature mapping target.neotrade3_domains must be a non-empty list"
            )
        if not all(
            isinstance(value, str) and value.strip() for value in neotrade3_domains
        ):
            raise FeatureMappingError(
                "feature mapping target.neotrade3_domains must contain non-empty strings"
            )

        modules = _require_list(target, "modules")
        if not modules:
            raise FeatureMappingError(
                "feature mapping target.modules must be a non-empty list"
            )
        if not all(isinstance(value, str) and value.strip() for value in modules):
            raise FeatureMappingError(
                "feature mapping target.modules must contain non-empty strings"
            )

        lab_id = target.get("lab_id")
        if lab_id is not None and (not isinstance(lab_id, str) or not lab_id.strip()):
            raise FeatureMappingError(
                "feature mapping target.lab_id must be a non-empty string when provided"
            )

        orchestrator_task_ids = target.get("orchestrator_task_ids")
        if orchestrator_task_ids is not None:
            if not isinstance(orchestrator_task_ids, list):
                raise FeatureMappingError(
                    "feature mapping target.orchestrator_task_ids must be a list when provided"
                )
            if not all(
                isinstance(value, str) and value.strip()
                for value in orchestrator_task_ids
            ):
                raise FeatureMappingError(
                    "feature mapping target.orchestrator_task_ids must contain non-empty strings"
                )

        decision_evidence = mapping.get("decision_evidence")
        if decision_evidence is not None:
            if not isinstance(decision_evidence, list):
                raise FeatureMappingError(
                    "feature mapping decision_evidence must be a list when provided"
                )
            if not all(
                isinstance(value, str) and value.strip() for value in decision_evidence
            ):
                raise FeatureMappingError(
                    "feature mapping decision_evidence must contain non-empty strings"
                )

        status_history = mapping.get("status_history")
        if status_history is not None:
            if not isinstance(status_history, list) or not status_history:
                raise FeatureMappingError(
                    "feature mapping status_history must be a non-empty list when provided"
                )
            for entry in status_history:
                if not isinstance(entry, dict):
                    raise FeatureMappingError(
                        "feature mapping status_history items must be JSON objects"
                    )
                _require_non_empty_string(entry, "at")
                _require_non_empty_string(entry, "status")
                status_value = str(entry.get("status"))
                if status_value not in ALLOWED_MIGRATION_STATUSES:
                    raise FeatureMappingError(
                        "feature mapping status_history.status must be one of: "
                        + ", ".join(sorted(ALLOWED_MIGRATION_STATUSES))
                    )
                note = entry.get("note")
                if note is not None and (not isinstance(note, str) or not note.strip()):
                    raise FeatureMappingError(
                        "feature mapping status_history.note must be a non-empty string when provided"
                    )

        feature_id = str(mapping["feature_id"])
        if feature_id not in inventory_feature_ids:
            raise FeatureMappingError(
                f"feature mapping references unknown feature_id '{feature_id}' (not found in inventory)"
            )
        feature_ids.append(feature_id)

    duplicates = sorted(
        {feature_id for feature_id in feature_ids if feature_ids.count(feature_id) > 1}
    )
    if duplicates:
        raise FeatureMappingError(
            "feature mapping contains duplicate feature_id values: "
            + ", ".join(duplicates)
        )


def load_feature_mapping(file_path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FeatureMappingError("feature mapping root must be a JSON object")
    return payload


def build_feature_mapping_payload(
    *,
    mapping_file_path: str | Path,
    inventory_file_path: str | Path,
    expected_scope_domain: str | None = None,
    filter_status: str | None = None,
    filter_strategy: str | None = None,
) -> dict[str, Any]:
    inventory_items = load_feature_inventory(inventory_file_path)
    inventory_index = {str(item["feature_id"]): item for item in inventory_items}
    inventory_feature_ids = set(inventory_index.keys())

    mapping_payload = load_feature_mapping(mapping_file_path)
    validate_feature_mapping(
        mapping_payload,
        inventory_feature_ids=inventory_feature_ids,
        expected_scope_domain=expected_scope_domain,
    )

    mappings: list[dict[str, Any]] = []
    for item in mapping_payload["mappings"]:
        feature_id = str(item["feature_id"])
        inventory_item = inventory_index[feature_id]
        mappings.append(
            {
                **item,
                "feature_name": str(inventory_item.get("feature_name", "")),
                "source_domain": str(inventory_item.get("domain", "")),
                "granularity": str(inventory_item.get("granularity", "")),
                "parent_feature_id": inventory_item.get("parent_feature_id"),
            }
        )

    status_counts_total = Counter(str(item["migration_status"]) for item in mappings)
    strategy_counts_total = Counter(
        str(item["migration_strategy"]) for item in mappings
    )
    neotrade3_domain_counts_total = Counter(
        domain
        for item in mappings
        for domain in item.get("target", {}).get("neotrade3_domains", [])
        if isinstance(domain, str)
    )

    filtered_mappings = mappings
    if filter_status is not None:
        if filter_status not in ALLOWED_MIGRATION_STATUSES:
            raise FeatureMappingError(
                "feature mapping filter_status must be one of: "
                + ", ".join(sorted(ALLOWED_MIGRATION_STATUSES))
            )
        filtered_mappings = [
            item
            for item in filtered_mappings
            if item.get("migration_status") == filter_status
        ]
    if filter_strategy is not None:
        if filter_strategy not in ALLOWED_MIGRATION_STRATEGIES:
            raise FeatureMappingError(
                "feature mapping filter_strategy must be one of: "
                + ", ".join(sorted(ALLOWED_MIGRATION_STRATEGIES))
            )
        filtered_mappings = [
            item
            for item in filtered_mappings
            if item.get("migration_strategy") == filter_strategy
        ]

    status_counts = Counter(str(item["migration_status"]) for item in filtered_mappings)
    strategy_counts = Counter(
        str(item["migration_strategy"]) for item in filtered_mappings
    )
    neotrade3_domain_counts = Counter(
        domain
        for item in filtered_mappings
        for domain in item.get("target", {}).get("neotrade3_domains", [])
        if isinstance(domain, str)
    )

    return {
        "version": int(mapping_payload["version"]),
        "scope": mapping_payload["scope"],
        "inventory_source": str(mapping_payload.get("inventory_source", "")),
        "mapping_count_total": len(mappings),
        "mapping_count": len(filtered_mappings),
        "filters": {"status": filter_status, "strategy": filter_strategy},
        "status_counts_total": dict(sorted(status_counts_total.items())),
        "strategy_counts_total": dict(sorted(strategy_counts_total.items())),
        "neotrade3_domain_counts_total": dict(
            sorted(neotrade3_domain_counts_total.items())
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "neotrade3_domain_counts": dict(sorted(neotrade3_domain_counts.items())),
        "mappings": filtered_mappings,
    }


def build_feature_mapping_coverage_payload(
    *,
    mapping_file_path: str | Path,
    inventory_file_path: str | Path,
    expected_scope_domain: str | None = None,
) -> dict[str, Any]:
    inventory_items = load_feature_inventory(inventory_file_path)
    inventory_ids_for_domain = sorted(
        str(item["feature_id"])
        for item in inventory_items
        if expected_scope_domain is None
        or str(item.get("domain")) == expected_scope_domain
    )
    inventory_id_set = set(inventory_ids_for_domain)

    mapping_payload = load_feature_mapping(mapping_file_path)
    validate_feature_mapping(
        mapping_payload,
        inventory_feature_ids=set(str(item["feature_id"]) for item in inventory_items),
        expected_scope_domain=expected_scope_domain,
    )
    mapped_ids = sorted(
        str(item["feature_id"]) for item in mapping_payload.get("mappings", [])
    )
    mapped_id_set = set(mapped_ids)

    missing_feature_ids = sorted(inventory_id_set - mapped_id_set)
    extra_feature_ids = sorted(mapped_id_set - inventory_id_set)

    return {
        "scope": mapping_payload.get("scope", {}),
        "inventory_source": str(mapping_payload.get("inventory_source", "")),
        "inventory_count": len(inventory_ids_for_domain),
        "mapped_count": len(mapped_ids),
        "missing_count": len(missing_feature_ids),
        "extra_count": len(extra_feature_ids),
        "missing_feature_ids": missing_feature_ids,
        "extra_feature_ids": extra_feature_ids,
        "status": (
            "ok" if not missing_feature_ids and not extra_feature_ids else "incomplete"
        ),
    }
