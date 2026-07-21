from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .step8_quality_report import (
    build_evaluation_outputs_v0,
    build_evaluation_trigger_inputs_v0,
    build_step8_report_id,
    build_tracking_pool_quality_report_v0,
)


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass(frozen=True)
class Step8QualityReportArtifactRecord:
    report_id: str
    written_at: str
    artifact_path: str
    asof_date: str
    source_run_id: str
    backtest_report_id: str | None
    quality_verdict: str
    quality_fail_reason_codes: tuple[str, ...]
    outputs_ready: str


def write_step8_quality_report_artifact(
    *,
    project_root: str | Path,
    asof_date: str,
    source_run_id: str,
    backtest_result: dict[str, Any] | None,
    upstream_evidence_paths: list[str] | None = None,
    backtest_report_id: str | None = None,
    dry_run: bool = False,
) -> Step8QualityReportArtifactRecord:
    project_root_path = Path(project_root)
    normalized_asof_date = str(asof_date or "").strip()
    normalized_source_run_id = str(source_run_id or "").strip()
    report_id = build_step8_report_id(
        source_run_id=normalized_source_run_id,
        asof_date=normalized_asof_date,
    )
    artifacts_dir = project_root_path / "var/artifacts/step8_quality_reports" / report_id
    artifact_file = artifacts_dir / "tracking_pool_quality_report.json"
    artifact_path = str(artifact_file.relative_to(project_root_path))

    report = build_tracking_pool_quality_report_v0(
        asof_date=normalized_asof_date,
        source_run_id=normalized_source_run_id,
        backtest_result=backtest_result,
        report_id=report_id,
    )

    outputs_ready = str(report.get("outputs_ready") or "pending").strip() or "pending"
    pending_reason = str(report.get("pending_reason") or "").strip() or None
    normalized_upstream_evidence_paths = [
        str(p).strip() for p in list(upstream_evidence_paths or []) if str(p).strip()
    ]
    report_evidence_paths = [artifact_path, *normalized_upstream_evidence_paths]
    report["evidence_paths"] = list(report_evidence_paths)

    trigger_inputs = build_evaluation_trigger_inputs_v0(
        asof_date=normalized_asof_date,
        source_run_id=normalized_source_run_id,
        inputs_ready=str(report.get("inputs_ready") or "pending"),
        pending_reason=pending_reason,
        evidence_paths=list(report_evidence_paths),
    )
    eval_outputs = build_evaluation_outputs_v0(
        report_id=report_id,
        asof_date=normalized_asof_date,
        source_run_id=normalized_source_run_id,
        outputs_ready=outputs_ready,
        pending_reason=pending_reason,
        report_paths=[artifact_path],
    )

    written_at = _now_iso()
    payload = {
        "tracking_pool_quality_report": dict(report),
        "evaluation_trigger_inputs": dict(trigger_inputs),
        "evaluation_outputs": dict(eval_outputs),
        "backtest_report_id": (str(backtest_report_id).strip() if backtest_report_id is not None else None),
        "written_at": written_at,
    }

    if not dry_run:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return Step8QualityReportArtifactRecord(
        report_id=report_id,
        written_at=written_at,
        artifact_path=artifact_path,
        asof_date=normalized_asof_date,
        source_run_id=normalized_source_run_id,
        backtest_report_id=(str(backtest_report_id).strip() if backtest_report_id is not None else None),
        quality_verdict=str(report.get("quality_verdict") or "").strip(),
        quality_fail_reason_codes=tuple(
            str(x).strip()
            for x in list(report.get("quality_fail_reason_codes") or [])
            if str(x).strip()
        ),
        outputs_ready=outputs_ready,
    )
