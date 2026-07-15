"""CLI entrypoint for NeoTrade3 governance runtime actions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .contracts import ValidationResult
from .runtime import (
    run_governance_candidate_validation_outcome,
    run_governance_final_validation_selection,
    run_governance_for_benchmark_run,
    run_governance_reject_execution,
    run_governance_status_transition,
)


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_validation_result_argument(value: str) -> ValidationResult:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            f"validation_result must be valid JSON: {exc}"
        ) from exc
    try:
        return ValidationResult.from_dict(payload)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            f"validation_result must match ValidationResult contract: {exc}"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run NeoTrade3 M5 governance runtime actions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    handoff_parser = subparsers.add_parser(
        "handoff",
        help="Materialize a governance handoff from a persisted benchmark run.",
    )
    handoff_parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (defaults to repository root).",
    )
    handoff_parser.add_argument(
        "--benchmark-run-id",
        required=True,
        help="Persisted benchmark run id used as the governance upstream input.",
    )
    handoff_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute without writing governance artifact/ledger outputs under var/.",
    )

    reject_parser = subparsers.add_parser(
        "reject",
        help="Materialize an independent governance reject execution from a persisted governance handoff.",
    )
    reject_parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (defaults to repository root).",
    )
    reject_parser.add_argument(
        "--source-run-id",
        required=True,
        help="Persisted governance handoff source run id.",
    )
    reject_parser.add_argument(
        "--validation-id",
        required=True,
        help="Validation result id to materialize as a reject execution.",
    )
    reject_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute without writing reject artifact/ledger outputs under var/.",
    )
    status_transition_parser = subparsers.add_parser(
        "status-transition",
        help="Materialize an independent governance status transition from persisted reject execution proof.",
    )
    status_transition_parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (defaults to repository root).",
    )
    status_transition_parser.add_argument(
        "--source-run-id",
        required=True,
        help="Persisted governance handoff source run id.",
    )
    status_transition_parser.add_argument(
        "--validation-id",
        required=True,
        help="Validation result id to materialize as a status transition.",
    )
    status_transition_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute without writing status transition artifact/ledger outputs under var/.",
    )
    candidate_validation_parser = subparsers.add_parser(
        "candidate-validation-outcome",
        help="Materialize an independent governance candidate validation outcome from an explicit validation_result payload.",
    )
    candidate_validation_parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (defaults to repository root).",
    )
    candidate_validation_parser.add_argument(
        "--source-run-id",
        required=True,
        help="Persisted governance handoff source run id.",
    )
    candidate_validation_parser.add_argument(
        "--validation-result",
        required=True,
        type=_parse_validation_result_argument,
        help="ValidationResult payload encoded as JSON.",
    )
    candidate_validation_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute without writing candidate validation artifact/ledger outputs under var/.",
    )
    final_selection_parser = subparsers.add_parser(
        "final-validation-selection",
        help="Materialize an independent governance final validation selection from persisted candidate validation truth.",
    )
    final_selection_parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (defaults to repository root).",
    )
    final_selection_parser.add_argument(
        "--source-run-id",
        required=True,
        help="Persisted governance handoff source run id.",
    )
    final_selection_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute without writing final validation artifact/ledger outputs under var/.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    project_root = (
        Path(args.project_root) if args.project_root else _default_project_root()
    )

    if args.command == "handoff":
        record = run_governance_for_benchmark_run(
            project_root=project_root,
            benchmark_run_id=str(args.benchmark_run_id),
            dry_run=bool(args.dry_run),
        )
        payload = {
            "source_run_id": record.source_run_id,
            "status": record.status,
            "source_layer": record.source_layer,
            "projected_assessment_count": record.projected_assessment_count,
            "projected_issue_count": record.projected_issue_count,
            "diagnostic_count": record.diagnostic_count,
            "change_request_count": record.change_request_count,
            "experiment_request_count": record.experiment_request_count,
            "validation_result_count": record.validation_result_count,
            "promotion_blocker_count": record.promotion_blocker_count,
            "attention_item_count": record.attention_item_count,
            "decision_record_count": record.decision_record_count,
            "artifact_path": record.artifact_path,
            "ledger_path": record.ledger_path,
            "dry_run": bool(args.dry_run),
        }
    elif args.command == "reject":
        record = run_governance_reject_execution(
            project_root=project_root,
            source_run_id=str(args.source_run_id),
            validation_id=str(args.validation_id),
            dry_run=bool(args.dry_run),
        )
        payload = {
            "validation_id": record.validation_id,
            "source_run_id": record.source_run_id,
            "status": record.status,
            "baseline_run_id": record.baseline_run_id,
            "candidate_run_id": record.candidate_run_id,
            "decision_id": record.decision_id,
            "decision": record.decision,
            "artifact_path": record.artifact_path,
            "ledger_path": record.ledger_path,
            "dry_run": bool(args.dry_run),
        }
    elif args.command == "candidate-validation-outcome":
        record = run_governance_candidate_validation_outcome(
            project_root=project_root,
            source_run_id=str(args.source_run_id),
            validation_result=args.validation_result,
            dry_run=bool(args.dry_run),
        )
        payload = {
            "validation_id": record.validation_id,
            "source_run_id": record.source_run_id,
            "status": record.status,
            "baseline_run_id": record.baseline_run_id,
            "candidate_run_id": record.candidate_run_id,
            "outcome": record.outcome,
            "artifact_path": record.artifact_path,
            "ledger_path": record.ledger_path,
            "dry_run": bool(args.dry_run),
        }
    elif args.command == "final-validation-selection":
        record = run_governance_final_validation_selection(
            project_root=project_root,
            source_run_id=str(args.source_run_id),
            dry_run=bool(args.dry_run),
        )
        payload = {
            "source_run_id": record.source_run_id,
            "status": record.status,
            "selected_validation_id": record.selected_validation_id,
            "baseline_run_id": record.baseline_run_id,
            "candidate_run_id": record.candidate_run_id,
            "outcome": record.outcome,
            "artifact_path": record.artifact_path,
            "ledger_path": record.ledger_path,
            "dry_run": bool(args.dry_run),
        }
    else:
        record = run_governance_status_transition(
            project_root=project_root,
            source_run_id=str(args.source_run_id),
            validation_id=str(args.validation_id),
            dry_run=bool(args.dry_run),
        )
        payload = {
            "validation_id": record.validation_id,
            "source_run_id": record.source_run_id,
            "status": record.status,
            "baseline_run_id": record.baseline_run_id,
            "candidate_run_id": record.candidate_run_id,
            "decision_id": record.decision_id,
            "effective_attention_id": record.effective_attention_id,
            "effective_attention_status": record.effective_attention_status,
            "effective_blocker_id": record.effective_blocker_id,
            "effective_blocker_active": record.effective_blocker_active,
            "artifact_path": record.artifact_path,
            "ledger_path": record.ledger_path,
            "dry_run": bool(args.dry_run),
        }

    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
