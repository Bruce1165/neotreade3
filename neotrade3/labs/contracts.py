from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .registry import LabRegistration, LabRegistry


def resolve_lab_runtime_task_id(lab: Any) -> str:
    jobs = getattr(lab, "daily_jobs", []) or []
    if jobs:
        task_id = str(getattr(jobs[0], "task_id", "") or "").strip()
        if task_id:
            return task_id
    lab_id = str(getattr(lab, "lab_id", "") or "").strip() or "unknown_lab"
    return f"{lab_id}.manual_run"


def build_lab_runtime_artifacts_payload(
    *,
    lab: Any,
    runtime_result: dict[str, Any],
    target_date: str,
    requested_by: str,
    requested_at: str,
    run_status: str,
) -> dict[str, Any]:
    if len(getattr(lab, "artifacts", []) or []) != 1:
        raise ValueError(
            f"lab '{str(getattr(lab, 'lab_id', '') or '')}' must declare exactly one artifact contract"
        )

    artifact_contract = lab.artifacts[0]
    lab_id = str(getattr(lab, "lab_id", ""))
    artifact_payload: dict[str, Any]

    if lab_id == "cup_handle_lab":
        raw_candidates = runtime_result.get("candidates", [])
        candidate_codes: list[str] = []
        if isinstance(raw_candidates, list):
            for item in raw_candidates:
                if isinstance(item, dict):
                    code = str(item.get("stock_code", "")).strip()
                else:
                    code = str(item).strip()
                if code:
                    candidate_codes.append(code)
        artifact_payload = {
            "version": 1,
            "lab_id": lab_id,
            "lab_name": str(getattr(lab, "display_name", "")),
            "target_date": target_date,
            "requested_by": requested_by,
            "requested_at": requested_at,
            "status": run_status,
            "message": str(runtime_result.get("message", "")),
            "candidates": candidate_codes,
            "candidate_details": raw_candidates if isinstance(raw_candidates, list) else [],
            "candidates_count": int(runtime_result.get("candidates_count", len(candidate_codes)) or 0),
            "raw_candidates_count": int(runtime_result.get("raw_candidates_count", len(candidate_codes)) or 0),
            "tier_distribution": (
                runtime_result.get("tier_distribution", {})
                if isinstance(runtime_result.get("tier_distribution", {}), dict)
                else {}
            ),
            "analysis_version": str(runtime_result.get("analysis_version", "")),
            "degraded": bool(runtime_result.get("degraded", False)),
            "degraded_steps": (
                runtime_result.get("degraded_steps", [])
                if isinstance(runtime_result.get("degraded_steps", []), list)
                else []
            ),
            "filter_applied": (
                runtime_result.get("filter_applied", {})
                if isinstance(runtime_result.get("filter_applied", {}), dict)
                else {}
            ),
            "notes": (
                runtime_result.get("notes", [])
                if isinstance(runtime_result.get("notes", []), list)
                else []
            ),
        }
    elif lab_id == "paper_simulation_lab":
        portfolio = runtime_result.get("portfolio", {})
        artifact_payload = {
            "version": 1,
            "lab_id": lab_id,
            "lab_name": str(getattr(lab, "display_name", "")),
            "target_date": target_date,
            "requested_by": requested_by,
            "requested_at": requested_at,
            "status": run_status,
            "message": str(runtime_result.get("message", "")),
            "strategy_id": str(runtime_result.get("strategy_id", "")),
            "candidates": (
                runtime_result.get("candidates", [])
                if isinstance(runtime_result.get("candidates", []), list)
                else []
            ),
            "cash_yuan": float(portfolio.get("cash", 0.0) or 0.0)
            if isinstance(portfolio, dict)
            else 0.0,
            "positions": (
                runtime_result.get("positions", [])
                if isinstance(runtime_result.get("positions", []), list)
                else []
            ),
            "portfolio": portfolio if isinstance(portfolio, dict) else {},
            "trades": (
                runtime_result.get("trades", {})
                if isinstance(runtime_result.get("trades", {}), dict)
                else {}
            ),
            "analytics": (
                runtime_result.get("analytics", {})
                if isinstance(runtime_result.get("analytics", {}), dict)
                else {}
            ),
            "analysis_version": str(runtime_result.get("analysis_version", "")),
            "notes": (
                runtime_result.get("notes", [])
                if isinstance(runtime_result.get("notes", []), list)
                else []
            ),
        }
    else:
        artifact_payload = {
            "version": 1,
            "lab_id": lab_id,
            "lab_name": str(getattr(lab, "display_name", "")),
            "target_date": target_date,
            "requested_by": requested_by,
            "requested_at": requested_at,
            "status": run_status,
            "message": str(runtime_result.get("message", "")),
            "market_context": (
                runtime_result.get("market_context", {})
                if isinstance(runtime_result.get("market_context", {}), dict)
                else {}
            ),
            "high_certainty_count": int(runtime_result.get("high_certainty_count", 0) or 0),
            "candidates": (
                runtime_result.get("candidates", [])
                if isinstance(runtime_result.get("candidates", []), list)
                else []
            ),
            "trading_signals": (
                runtime_result.get("trading_signals", [])
                if isinstance(runtime_result.get("trading_signals", []), list)
                else []
            ),
            "wave_signals": (
                runtime_result.get("wave_signals", [])
                if isinstance(runtime_result.get("wave_signals", []), list)
                else []
            ),
            "grade_distribution": (
                runtime_result.get("grade_distribution", {})
                if isinstance(runtime_result.get("grade_distribution", {}), dict)
                else {}
            ),
            "analysis_version": str(runtime_result.get("analysis_version", "")),
            "degraded": bool(runtime_result.get("degraded", False)),
            "degraded_steps": (
                runtime_result.get("degraded_steps", [])
                if isinstance(runtime_result.get("degraded_steps", []), list)
                else []
            ),
            "notes": (
                runtime_result.get("notes", [])
                if isinstance(runtime_result.get("notes", []), list)
                else []
            ),
        }
    return {str(artifact_contract.artifact_id): artifact_payload}


def write_lab_contract_artifacts(
    *,
    project_root: str | Path,
    lab: Any,
    artifacts_payload: dict[str, Any],
) -> list[str]:
    project_root_path = Path(project_root)
    contract_lookup = {
        str(artifact.artifact_id): artifact
        for artifact in (getattr(lab, "artifacts", []) or [])
    }
    artifact_refs: list[str] = []
    for artifact_id, payload in artifacts_payload.items():
        contract = contract_lookup.get(str(artifact_id))
        if contract is None:
            continue
        contract_path = project_root_path / str(contract.path)
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        artifact_refs.append(str(contract.path))
    return artifact_refs


def materialize_lab_runtime_artifacts(
    *,
    project_root: str | Path,
    labs_registry_path: str | Path,
    lab_id: str,
    runtime_result: dict[str, Any],
    target_date: str,
    requested_by: str,
    requested_at: str,
    run_status: str,
) -> tuple[LabRegistration, dict[str, Any], list[str]]:
    registry = LabRegistry.from_file(labs_registry_path)
    lab = registry.get_lab(str(lab_id))
    if lab is None:
        raise ValueError(f"unknown lab_id '{lab_id}'")
    artifacts_payload = build_lab_runtime_artifacts_payload(
        lab=lab,
        runtime_result=runtime_result,
        target_date=target_date,
        requested_by=requested_by,
        requested_at=requested_at,
        run_status=run_status,
    )
    artifact_refs = write_lab_contract_artifacts(
        project_root=project_root,
        lab=lab,
        artifacts_payload=artifacts_payload,
    )
    return lab, artifacts_payload, artifact_refs
