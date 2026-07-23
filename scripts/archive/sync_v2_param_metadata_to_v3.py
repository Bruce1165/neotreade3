import json
import argparse
from typing import Optional
from pathlib import Path


def _upper_snake(name: str) -> str:
    out = []
    for ch in str(name):
        if ch.isalnum():
            out.append(ch.upper())
        else:
            out.append("_")
    return "".join(out)


def _walk_schema_leaves(schema: object, prefix: str = "") -> list[tuple[str, dict]]:
    if not isinstance(schema, dict):
        return []
    props = schema.get("properties")
    if not isinstance(props, dict):
        return []
    leaves: list[tuple[str, dict]] = []
    for key, child in props.items():
        child_schema = child if isinstance(child, dict) else {}
        path = f"{prefix}.{key}" if prefix else str(key)
        if child_schema.get("type") == "object" or isinstance(child_schema.get("properties"), dict):
            leaves.extend(_walk_schema_leaves(child_schema, path))
            continue
        leaves.append((path, child_schema))
    return leaves


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    default_v3_dir = repo_root / "config" / "screeners"
    sibling_v2_dir = repo_root.parent / "NeoTrade2" / "config" / "screeners"
    default_v2_dir = sibling_v2_dir if sibling_v2_dir.exists() else Path("/Users/mac/NeoTrade2/config/screeners")
    default_report_path = repo_root / "var" / "artifacts" / "v2_param_metadata_sync_report.json"

    parser = argparse.ArgumentParser()
    parser.add_argument("--v2-dir", type=str, default=str(default_v2_dir))
    parser.add_argument("--v3-dir", type=str, default=str(default_v3_dir))
    parser.add_argument("--report-path", type=str, default=str(default_report_path))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _pick_report_v2_dir(v2_dir: Path) -> str:
    return str(v2_dir)


def _pick_report_v3_dir(v3_dir: Path) -> str:
    return str(v3_dir)


def _default_group_for(*, path: str, leaf_key: str) -> Optional[str]:
    if path.startswith("universe_filters."):
        return "股票池过滤"
    if leaf_key == "top_n":
        return "输出设置"
    if leaf_key == "lookback_days":
        return "基础设置"
    return None


def main() -> int:
    args = _parse_args()
    v2_dir = Path(args.v2_dir)
    v3_dir = Path(args.v3_dir)
    report_path = Path(args.report_path)

    file_mapping = {
        "cup_handle_v4": "coffee_cup_v4",
    }
    key_mapping = {
        "daily_hot_cold": {
            "min_amount_yi": "MIN_AMOUNT",
            "hot_pct_threshold": "HOT_PCT_THRESHOLD",
            "cold_pct_threshold": "COLD_PCT_THRESHOLD",
        }
    }

    changed = 0
    skipped = 0
    report_items: list[dict] = []
    for v3_path in sorted(v3_dir.glob("*.json")):
        if v3_path.name in {"screeners_registry.json"}:
            continue
        v3_payload = _load_json(v3_path)
        screener_id = str(v3_payload.get("screener_id") or v3_path.stem).strip()
        v2_name = file_mapping.get(screener_id, screener_id)
        v2_path = v2_dir / f"{v2_name}.json"
        if not v2_path.exists():
            report_items.append(
                {
                    "screener_id": screener_id,
                    "v3_file": str(v3_path),
                    "v2_file": str(v2_path),
                    "status": "skipped_v2_file_missing",
                }
            )
            skipped += 1
            continue
        v2_payload = _load_json(v2_path)
        v2_params = v2_payload.get("parameters")
        if not isinstance(v2_params, dict):
            report_items.append(
                {
                    "screener_id": screener_id,
                    "v3_file": str(v3_path),
                    "v2_file": str(v2_path),
                    "status": "skipped_v2_parameters_missing",
                }
            )
            skipped += 1
            continue

        schema = v3_payload.get("schema")
        if not isinstance(schema, dict):
            report_items.append(
                {
                    "screener_id": screener_id,
                    "v3_file": str(v3_path),
                    "v2_file": str(v2_path),
                    "status": "skipped_v3_schema_missing",
                }
            )
            skipped += 1
            continue

        leaf_pairs = _walk_schema_leaves(schema, "")
        local_key_map = key_mapping.get(screener_id, {})

        updated_any = False
        leaf_reports: list[dict] = []
        for path, leaf_schema in leaf_pairs:
            leaf_key = path.split(".")[-1]
            original_x_group = leaf_schema.get("x_group")
            default_group = _default_group_for(path=path, leaf_key=leaf_key)
            default_group_applied = False
            if default_group and not str(leaf_schema.get("x_group") or "").strip():
                leaf_schema["x_group"] = default_group
                updated_any = True
                default_group_applied = True

            v2_key = local_key_map.get(leaf_key) or _upper_snake(leaf_key)
            v2_entry = v2_params.get(v2_key)
            if not isinstance(v2_entry, dict):
                leaf_reports.append(
                    {
                        "path": path,
                        "leaf_key": leaf_key,
                        "v2_key": v2_key,
                        "status": "unmatched_v2_param_missing" if not default_group else "unmatched_v2_param_missing_with_default_group",
                        "default_group": default_group,
                        "default_group_applied": default_group_applied,
                        "x_group_before_default": original_x_group,
                        "x_group_after_default": leaf_schema.get("x_group"),
                    }
                )
                continue

            v2_display_name = str(v2_entry.get("display_name") or "").strip()
            v2_desc = str(v2_entry.get("description") or "").strip()
            v2_group = str(v2_entry.get("group") or "").strip()
            v2_min = v2_entry.get("min") if "min" in v2_entry else None
            v2_max = v2_entry.get("max") if "max" in v2_entry else None
            v2_step = v2_entry.get("step") if "step" in v2_entry else None

            before_x_display_name = leaf_schema.get("x_display_name")
            before_desc = leaf_schema.get("description")
            before_x_group = leaf_schema.get("x_group")
            before_x_min = leaf_schema.get("x_min")
            before_x_max = leaf_schema.get("x_max")
            before_x_step = leaf_schema.get("x_step")

            updated_fields: list[str] = []
            if not str(leaf_schema.get("x_display_name") or "").strip():
                if v2_display_name:
                    leaf_schema["x_display_name"] = v2_display_name
                    updated_any = True
                    updated_fields.append("x_display_name")

            if not str(leaf_schema.get("description") or "").strip():
                if v2_desc:
                    leaf_schema["description"] = v2_desc
                    updated_any = True
                    updated_fields.append("description")

            if v2_group and not str(leaf_schema.get("x_group") or "").strip():
                leaf_schema["x_group"] = v2_group
                updated_any = True
                updated_fields.append("x_group")

            if "min" in v2_entry and "x_min" not in leaf_schema:
                leaf_schema["x_min"] = v2_min
                updated_any = True
                updated_fields.append("x_min")

            if "max" in v2_entry and "x_max" not in leaf_schema:
                leaf_schema["x_max"] = v2_max
                updated_any = True
                updated_fields.append("x_max")

            if "step" in v2_entry and "x_step" not in leaf_schema:
                leaf_schema["x_step"] = v2_step
                updated_any = True
                updated_fields.append("x_step")

            leaf_reports.append(
                {
                    "path": path,
                    "leaf_key": leaf_key,
                    "v2_key": v2_key,
                    "status": "matched",
                    "updated_fields": updated_fields,
                    "default_group": default_group,
                    "default_group_applied": default_group_applied,
                    "x_group_before_default": original_x_group,
                    "v2": {
                        "display_name": v2_display_name,
                        "description": v2_desc,
                        "group": v2_group,
                        "min": v2_min,
                        "max": v2_max,
                        "step": v2_step,
                    },
                    "v3_before": {
                        "x_display_name": before_x_display_name,
                        "description": before_desc,
                        "x_group": before_x_group,
                        "x_min": before_x_min,
                        "x_max": before_x_max,
                        "x_step": before_x_step,
                    },
                    "v3_after": {
                        "x_display_name": leaf_schema.get("x_display_name"),
                        "description": leaf_schema.get("description"),
                        "x_group": leaf_schema.get("x_group"),
                        "x_min": leaf_schema.get("x_min"),
                        "x_max": leaf_schema.get("x_max"),
                        "x_step": leaf_schema.get("x_step"),
                    },
                }
            )

        if updated_any and not args.dry_run:
            _write_json(v3_path, v3_payload)
            changed += 1

        report_items.append(
            {
                "screener_id": screener_id,
                "v3_file": str(v3_path),
                "v2_file": str(v2_path),
                "status": "processed",
                "updated_any": updated_any,
                "leaves_total": len(leaf_pairs),
                "leaves": leaf_reports,
            }
        )

    report_payload = {
        "v2_dir": _pick_report_v2_dir(v2_dir),
        "v3_dir": _pick_report_v3_dir(v3_dir),
        "dry_run": bool(args.dry_run),
        "summary": {
            "changed_files": changed,
            "skipped_files": skipped,
            "processed_files": len(report_items),
        },
        "items": report_items,
    }
    if not args.dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "changed": changed,
                "skipped": skipped,
                "report_path": str(report_path),
                "dry_run": bool(args.dry_run),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
