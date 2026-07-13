"""Shared runtime helpers for NeoTrade3 governance execution."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from neotrade3.benchmark.run_ledger import read_benchmark_batch_run_result

from .assembler import build_reject_decision_record_from_validation_result
from .contracts import AttentionItem, GovernanceDecisionRecord, PromotionBlocker, ValidationResult
from .handoff import build_governance_handoff_from_batch_run
from .run_ledger import (
    GovernanceCandidateValidationRecord,
    GovernanceRejectExecutionLedgerRecord,
    GovernanceRunLedgerRecord,
    GovernanceStatusTransitionRecord,
    materialize_governance_candidate_validation,
    materialize_governance_handoff,
    materialize_governance_reject_execution,
    materialize_governance_status_transition,
    read_governance_candidate_validation_result,
    read_governance_reject_execution_artifact,
    read_governance_reject_execution_ledger,
    read_governance_handoff_bundle,
)


DEFAULT_GOVERNANCE_BENCHMARK_RUN_ID = "validation_seed_v1_batch"


def resolve_governance_benchmark_run_id(
    *,
    benchmark_run_id: str,
) -> str:
    normalized = str(benchmark_run_id or "").strip()
    if not normalized:
        raise ValueError("benchmark_run_id must be non-empty")
    return normalized


def resolve_governance_validation_id(
    *,
    validation_id: str,
) -> str:
    normalized = str(validation_id or "").strip()
    if not normalized:
        raise ValueError("validation_id must be non-empty")
    return normalized


def _find_validation_result(
    *,
    validation_results: tuple[ValidationResult, ...],
    validation_id: str,
) -> ValidationResult:
    validation_result = next(
        (item for item in validation_results if item.validation_id == validation_id),
        None,
    )
    if validation_result is None:
        raise ValueError(f"validation_result not found for validation_id={validation_id}")
    return validation_result


def _require_final_validation_result(*, validation_result: ValidationResult) -> ValidationResult:
    if validation_result.outcome == "awaiting_candidate_validation":
        raise ValueError(
            "validation_result.outcome must not be awaiting_candidate_validation"
        )
    if not str(validation_result.candidate_run_id or "").strip():
        raise ValueError(
            "validation_result.candidate_run_id must be non-empty for final outcomes"
        )
    return validation_result


def _resolve_baseline_validation_result(
    *,
    bundle_validation_results: tuple[ValidationResult, ...],
    validation_id: str,
) -> ValidationResult:
    return _find_validation_result(
        validation_results=bundle_validation_results,
        validation_id=validation_id,
    )


def _resolve_candidate_validation_outcome(
    *,
    project_root: Path,
    validation_id: str,
) -> ValidationResult:
    validation_result = read_governance_candidate_validation_result(
        project_root=project_root,
        validation_id=validation_id,
    )
    if validation_result is None:
        raise ValueError(
            f"persisted candidate validation outcome not found for validation_id={validation_id}"
        )
    return validation_result


def _strip_expected_suffix(*, value: str, suffix: str, field_name: str) -> str:
    if not value.endswith(suffix):
        raise ValueError(f"{field_name} must end with {suffix!r}")
    return value[: -len(suffix)]


def _resolve_transition_object_ids(*, validation_result: ValidationResult) -> tuple[str, str]:
    experiment_id = str(validation_result.experiment_id or "").strip()
    if not experiment_id:
        raise ValueError(
            f"validation_result {validation_result.validation_id} missing experiment_id"
        )
    change_request_id = _strip_expected_suffix(
        value=experiment_id,
        suffix=":experiment",
        field_name="experiment_id",
    )
    diagnostic_id = _strip_expected_suffix(
        value=change_request_id,
        suffix=":cr",
        field_name="cr_id",
    )
    blocker_id = f"{diagnostic_id}:blocker"
    attention_id = f"{blocker_id}:attention"
    return blocker_id, attention_id


def _find_effective_blocker(
    *,
    promotion_blockers: tuple[PromotionBlocker, ...],
    blocker_id: str,
) -> PromotionBlocker:
    matches = [item for item in promotion_blockers if item.blocker_id == blocker_id]
    if not matches:
        raise ValueError(f"promotion_blocker not found for blocker_id={blocker_id}")
    if len(matches) != 1:
        raise ValueError(f"ambiguous promotion_blocker for blocker_id={blocker_id}")
    return replace(matches[0], active=True)


def _find_effective_attention_item(
    *,
    attention_items: tuple[AttentionItem, ...],
    attention_id: str,
) -> AttentionItem:
    matches = [item for item in attention_items if item.attention_id == attention_id]
    if not matches:
        raise ValueError(f"attention_item not found for attention_id={attention_id}")
    if len(matches) != 1:
        raise ValueError(f"ambiguous attention_item for attention_id={attention_id}")
    return replace(matches[0], status="resolved")


def _resolve_reject_transition_proof(
    *,
    project_root: Path,
    validation_id: str,
) -> tuple[GovernanceDecisionRecord, str]:
    reject_ledger = read_governance_reject_execution_ledger(
        project_root=project_root,
        validation_id=validation_id,
    )
    reject_artifact = read_governance_reject_execution_artifact(
        project_root=project_root,
        validation_id=validation_id,
    )
    if reject_artifact is not None:
        decision_payload = reject_artifact.get("decision_record")
        if not isinstance(decision_payload, dict):
            raise ValueError(
                f"persisted governance reject execution missing decision_record for validation_id={validation_id}"
            )
        return GovernanceDecisionRecord.from_dict(decision_payload), (
            f"var/artifacts/governance_rejections/{validation_id}/governance_reject_execution.json"
        )

    if reject_ledger is None:
        raise ValueError(
            f"persisted governance reject execution not found for validation_id={validation_id}"
        )
    return (
        GovernanceDecisionRecord(
            decision_id=reject_ledger.decision_id,
            subject_type="validation_result",
            subject_id=validation_id,
            decision=reject_ledger.decision,
            decision_scope="candidate_validation",
            rationale=(
                "Persisted reject execution ledger confirmed; transition runtime "
                "materializes the effective governance state projection."
            ),
            approver="system_governance",
            status="completed",
            evidence_refs=[],
        ),
        reject_ledger.artifact_path,
    )


def run_governance_for_benchmark_run(
    *,
    project_root: str | Path,
    benchmark_run_id: str,
    dry_run: bool = False,
) -> GovernanceRunLedgerRecord:
    project_root_path = Path(project_root)
    resolved_benchmark_run_id = resolve_governance_benchmark_run_id(
        benchmark_run_id=benchmark_run_id,
    )

    batch_result = read_benchmark_batch_run_result(
        project_root=project_root_path,
        run_id=resolved_benchmark_run_id,
    )
    if batch_result is None:
        raise FileNotFoundError(
            f"persisted benchmark artifact not found for run_id={resolved_benchmark_run_id}"
        )

    bundle = build_governance_handoff_from_batch_run(batch_result=batch_result)
    return materialize_governance_handoff(
        project_root=project_root_path,
        bundle=bundle,
        dry_run=dry_run,
    )


def run_governance_candidate_validation_outcome(
    *,
    project_root: str | Path,
    source_run_id: str,
    validation_result: ValidationResult,
    dry_run: bool = False,
) -> GovernanceCandidateValidationRecord:
    project_root_path = Path(project_root)
    resolved_source_run_id = resolve_governance_benchmark_run_id(
        benchmark_run_id=source_run_id,
    )
    resolved_validation_id = resolve_governance_validation_id(
        validation_id=validation_result.validation_id,
    )
    final_validation_result = _require_final_validation_result(
        validation_result=validation_result,
    )

    bundle = read_governance_handoff_bundle(
        project_root=project_root_path,
        source_run_id=resolved_source_run_id,
    )
    if bundle is None:
        raise ValueError(
            f"persisted governance handoff not found for source_run_id={resolved_source_run_id}"
        )

    baseline_validation_result = _resolve_baseline_validation_result(
        bundle_validation_results=bundle.validation_results,
        validation_id=resolved_validation_id,
    )
    if final_validation_result.experiment_id != baseline_validation_result.experiment_id:
        raise ValueError(
            "validation_result.experiment_id must match the persisted handoff baseline"
        )
    if final_validation_result.baseline_run_id != resolved_source_run_id:
        raise ValueError(
            "validation_result.baseline_run_id must match source_run_id"
        )

    return materialize_governance_candidate_validation(
        project_root=project_root_path,
        source_run_id=resolved_source_run_id,
        validation_result=final_validation_result,
        dry_run=dry_run,
    )


def run_governance_reject_execution(
    *,
    project_root: str | Path,
    source_run_id: str,
    validation_id: str,
    dry_run: bool = False,
) -> GovernanceRejectExecutionLedgerRecord:
    project_root_path = Path(project_root)
    resolved_source_run_id = resolve_governance_benchmark_run_id(
        benchmark_run_id=source_run_id,
    )
    resolved_validation_id = resolve_governance_validation_id(
        validation_id=validation_id,
    )

    bundle = read_governance_handoff_bundle(
        project_root=project_root_path,
        source_run_id=resolved_source_run_id,
    )
    if bundle is None:
        raise ValueError(
            f"persisted governance handoff not found for source_run_id={resolved_source_run_id}"
        )

    _resolve_baseline_validation_result(
        bundle_validation_results=bundle.validation_results,
        validation_id=resolved_validation_id,
    )
    validation_result = _resolve_candidate_validation_outcome(
        project_root=project_root_path,
        validation_id=resolved_validation_id,
    )
    if validation_result.baseline_run_id != resolved_source_run_id:
        raise ValueError(
            "persisted candidate validation baseline_run_id does not match source_run_id"
        )

    decision_record = build_reject_decision_record_from_validation_result(
        validation_result=validation_result
    )
    return materialize_governance_reject_execution(
        project_root=project_root_path,
        source_run_id=resolved_source_run_id,
        validation_result=validation_result,
        decision_record=decision_record,
        dry_run=dry_run,
    )


def run_governance_status_transition(
    *,
    project_root: str | Path,
    source_run_id: str,
    validation_id: str,
    dry_run: bool = False,
) -> GovernanceStatusTransitionRecord:
    project_root_path = Path(project_root)
    resolved_source_run_id = resolve_governance_benchmark_run_id(
        benchmark_run_id=source_run_id,
    )
    resolved_validation_id = resolve_governance_validation_id(
        validation_id=validation_id,
    )

    bundle = read_governance_handoff_bundle(
        project_root=project_root_path,
        source_run_id=resolved_source_run_id,
    )
    if bundle is None:
        raise ValueError(
            f"persisted governance handoff not found for source_run_id={resolved_source_run_id}"
        )

    _resolve_baseline_validation_result(
        bundle_validation_results=bundle.validation_results,
        validation_id=resolved_validation_id,
    )
    validation_result = _resolve_candidate_validation_outcome(
        project_root=project_root_path,
        validation_id=resolved_validation_id,
    )
    if validation_result.baseline_run_id != resolved_source_run_id:
        raise ValueError(
            "persisted candidate validation baseline_run_id does not match source_run_id"
        )
    blocker_id, attention_id = _resolve_transition_object_ids(
        validation_result=validation_result
    )
    effective_promotion_blocker = _find_effective_blocker(
        promotion_blockers=bundle.promotion_blockers,
        blocker_id=blocker_id,
    )
    effective_attention_item = _find_effective_attention_item(
        attention_items=bundle.attention_items,
        attention_id=attention_id,
    )
    decision_record, trigger_artifact_path = _resolve_reject_transition_proof(
        project_root=project_root_path,
        validation_id=resolved_validation_id,
    )
    return materialize_governance_status_transition(
        project_root=project_root_path,
        source_run_id=resolved_source_run_id,
        validation_result=validation_result,
        decision_record=decision_record,
        effective_attention_item=effective_attention_item,
        effective_promotion_blocker=effective_promotion_blocker,
        trigger_artifact_path=trigger_artifact_path,
        dry_run=dry_run,
    )
