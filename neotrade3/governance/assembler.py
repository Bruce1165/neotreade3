"""Pure builders for M5 governance contract objects."""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from neotrade3.benchmark.assembler import (
    B4_INTERACTION_GUARDRAIL_SAMPLE,
    GAP_LABEL_LOCAL_GLOBAL_MISREAD,
    GUARDRAIL_CODE_LOCAL_GLOBAL_END,
)
from neotrade3.benchmark.contracts import (
    GapRecord,
    InteractionGuardrailBreach,
    TraceBundle,
)

from .contracts import (
    AttentionItem,
    PATH_EXPERIMENT_VALIDATION,
    PATH_HUMAN_ESCALATION,
    PATH_INTERACTION_SEMANTIC_REPAIR,
    ROOT_LAYER_INTERACTION,
    ROOT_LAYER_RECOGNITION,
    ROOT_LAYER_TRANSLATION,
    ChangeRequest,
    DiagnosticChain,
    ExperimentRequest,
    GovernanceDecisionRecord,
    PromotionBlocker,
    ValidationResult,
)


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


def _optional_text(value: str) -> str:
    return str(value or "").strip()


def _normalize_text_list(values: Iterable[str] | None) -> list[str]:
    if values is None:
        return []
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_evidence_refs(
    evidence_refs: Sequence[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if evidence_refs is None:
        return []
    normalized: list[dict[str, Any]] = []
    for item in evidence_refs:
        if isinstance(item, dict):
            normalized.append(dict(item))
    return normalized


def build_diagnostic_chain(
    *,
    diagnostic_id: str,
    symbol: str,
    trade_date: str,
    sample_bucket: str,
    primary_root_layer: str,
    problem_statement: str,
    suspected_root_cause: str,
    recommended_path: str,
    secondary_layers: Sequence[str] | None = None,
    interaction_layers: Sequence[str] | None = None,
    source_gap_ids: Sequence[str] | None = None,
    source_breach_ids: Sequence[str] | None = None,
    evidence_refs: Sequence[dict[str, Any]] | None = None,
    trace_id: str = "",
    benchmark_run_id: str = "",
) -> DiagnosticChain:
    return DiagnosticChain(
        diagnostic_id=_require_text(diagnostic_id, "diagnostic_id"),
        symbol=_require_text(symbol, "symbol"),
        trade_date=_require_text(trade_date, "trade_date"),
        sample_bucket=_require_text(sample_bucket, "sample_bucket"),
        primary_root_layer=_require_text(primary_root_layer, "primary_root_layer"),
        secondary_layers=_normalize_text_list(secondary_layers),
        interaction_layers=_normalize_text_list(interaction_layers),
        problem_statement=_require_text(problem_statement, "problem_statement"),
        suspected_root_cause=_require_text(
            suspected_root_cause, "suspected_root_cause"
        ),
        recommended_path=_require_text(recommended_path, "recommended_path"),
        source_gap_ids=_normalize_text_list(source_gap_ids),
        source_breach_ids=_normalize_text_list(source_breach_ids),
        evidence_refs=_normalize_evidence_refs(evidence_refs),
        trace_id=str(trace_id or "").strip(),
        benchmark_run_id=str(benchmark_run_id or "").strip(),
    )


def build_change_request(
    *,
    cr_id: str,
    diagnostic_id: str,
    target_layer: str,
    problem_statement: str,
    suspected_root_cause: str,
    expected_improvement: str,
    risk_scope: str,
    priority: str,
    requires_human_approval: bool,
    status: str,
    source_gap_ids: Sequence[str] | None = None,
    evidence_refs: Sequence[dict[str, Any]] | None = None,
) -> ChangeRequest:
    return ChangeRequest(
        cr_id=_require_text(cr_id, "cr_id"),
        diagnostic_id=_require_text(diagnostic_id, "diagnostic_id"),
        target_layer=_require_text(target_layer, "target_layer"),
        source_gap_ids=_normalize_text_list(source_gap_ids),
        problem_statement=_require_text(problem_statement, "problem_statement"),
        suspected_root_cause=_require_text(
            suspected_root_cause, "suspected_root_cause"
        ),
        expected_improvement=_require_text(
            expected_improvement, "expected_improvement"
        ),
        risk_scope=_require_text(risk_scope, "risk_scope"),
        priority=_require_text(priority, "priority"),
        requires_human_approval=bool(requires_human_approval),
        status=_require_text(status, "status"),
        evidence_refs=_normalize_evidence_refs(evidence_refs),
    )


def build_experiment_request(
    *,
    experiment_id: str,
    cr_id: str,
    target_layer: str,
    hypothesis: str,
    expected_improvement: str,
    comparison_scope: dict[str, Any] | None,
    status: str,
    guardrail_codes: Sequence[str] | None = None,
    evidence_refs: Sequence[dict[str, Any]] | None = None,
) -> ExperimentRequest:
    return ExperimentRequest(
        experiment_id=_require_text(experiment_id, "experiment_id"),
        cr_id=_require_text(cr_id, "cr_id"),
        target_layer=_require_text(target_layer, "target_layer"),
        hypothesis=_require_text(hypothesis, "hypothesis"),
        expected_improvement=_require_text(
            expected_improvement, "expected_improvement"
        ),
        guardrail_codes=_normalize_text_list(guardrail_codes),
        comparison_scope=dict(comparison_scope or {}),
        status=_require_text(status, "status"),
        evidence_refs=_normalize_evidence_refs(evidence_refs),
    )


def build_attention_item(
    *,
    attention_id: str,
    created_at: str,
    source: str,
    target_layer: str,
    issue_type: str,
    severity: str,
    automation_class: str,
    evidence_refs: Sequence[dict[str, Any]] | None = None,
    recommended_action: str,
    human_action_required: bool,
    status: str,
    owner: str,
    blocking_scope: str,
) -> AttentionItem:
    return AttentionItem(
        attention_id=_require_text(attention_id, "attention_id"),
        created_at=_require_text(created_at, "created_at"),
        source=_require_text(source, "source"),
        target_layer=_require_text(target_layer, "target_layer"),
        issue_type=_require_text(issue_type, "issue_type"),
        severity=_require_text(severity, "severity"),
        automation_class=_require_text(automation_class, "automation_class"),
        evidence_refs=_normalize_evidence_refs(evidence_refs),
        recommended_action=_require_text(recommended_action, "recommended_action"),
        human_action_required=bool(human_action_required),
        status=_require_text(status, "status"),
        owner=_require_text(owner, "owner"),
        blocking_scope=_require_text(blocking_scope, "blocking_scope"),
    )


def build_validation_result(
    *,
    validation_id: str,
    experiment_id: str,
    baseline_run_id: str,
    candidate_run_id: str,
    outcome: str,
    introduced_risk_count: int,
    cleared_guardrail_codes: Sequence[str] | None = None,
    remaining_guardrail_codes: Sequence[str] | None = None,
    evidence_refs: Sequence[dict[str, Any]] | None = None,
) -> ValidationResult:
    normalized_outcome = _require_text(outcome, "outcome")
    normalized_candidate_run_id = _optional_text(candidate_run_id)
    if (
        not normalized_candidate_run_id
        and normalized_outcome != "awaiting_candidate_validation"
    ):
        raise ValueError("candidate_run_id must not be empty")
    return ValidationResult(
        validation_id=_require_text(validation_id, "validation_id"),
        experiment_id=_require_text(experiment_id, "experiment_id"),
        baseline_run_id=_require_text(baseline_run_id, "baseline_run_id"),
        candidate_run_id=normalized_candidate_run_id,
        outcome=normalized_outcome,
        cleared_guardrail_codes=_normalize_text_list(cleared_guardrail_codes),
        remaining_guardrail_codes=_normalize_text_list(remaining_guardrail_codes),
        introduced_risk_count=int(introduced_risk_count),
        evidence_refs=_normalize_evidence_refs(evidence_refs),
    )


def build_promotion_blocker(
    *,
    blocker_id: str,
    diagnostic_id: str,
    blocker_code: str,
    severity: str,
    reason: str,
    required_clearance: str,
    active: bool,
    evidence_refs: Sequence[dict[str, Any]] | None = None,
) -> PromotionBlocker:
    return PromotionBlocker(
        blocker_id=_require_text(blocker_id, "blocker_id"),
        diagnostic_id=_require_text(diagnostic_id, "diagnostic_id"),
        blocker_code=_require_text(blocker_code, "blocker_code"),
        severity=_require_text(severity, "severity"),
        reason=_require_text(reason, "reason"),
        required_clearance=_require_text(required_clearance, "required_clearance"),
        active=bool(active),
        evidence_refs=_normalize_evidence_refs(evidence_refs),
    )


def build_governance_decision_record(
    *,
    decision_id: str,
    subject_type: str,
    subject_id: str,
    decision: str,
    decision_scope: str,
    rationale: str,
    approver: str,
    status: str,
    evidence_refs: Sequence[dict[str, Any]] | None = None,
) -> GovernanceDecisionRecord:
    return GovernanceDecisionRecord(
        decision_id=_require_text(decision_id, "decision_id"),
        subject_type=_require_text(subject_type, "subject_type"),
        subject_id=_require_text(subject_id, "subject_id"),
        decision=_require_text(decision, "decision"),
        decision_scope=_require_text(decision_scope, "decision_scope"),
        rationale=_require_text(rationale, "rationale"),
        approver=_require_text(approver, "approver"),
        status=_require_text(status, "status"),
        evidence_refs=_normalize_evidence_refs(evidence_refs),
    )


def build_pending_validation_result_from_experiment_request(
    *,
    experiment_request: ExperimentRequest,
    baseline_run_id: str,
) -> ValidationResult:
    return build_validation_result(
        validation_id=f"{experiment_request.experiment_id}:validation",
        experiment_id=experiment_request.experiment_id,
        baseline_run_id=baseline_run_id,
        candidate_run_id="",
        outcome="awaiting_candidate_validation",
        introduced_risk_count=0,
        cleared_guardrail_codes=[],
        remaining_guardrail_codes=experiment_request.guardrail_codes,
        evidence_refs=experiment_request.evidence_refs,
    )


def build_block_decision_record_from_promotion_blocker(
    *,
    blocker: PromotionBlocker,
) -> GovernanceDecisionRecord:
    return build_governance_decision_record(
        decision_id=f"{blocker.blocker_id}:decision",
        subject_type="promotion_blocker",
        subject_id=blocker.blocker_id,
        decision="block",
        decision_scope="promotion",
        rationale=blocker.reason,
        approver="system_governance",
        status="recorded",
        evidence_refs=blocker.evidence_refs,
    )


def build_reject_decision_record_from_validation_result(
    *,
    validation_result: ValidationResult,
) -> GovernanceDecisionRecord:
    if validation_result.outcome != "rejected":
        raise ValueError("validation_result.outcome must be rejected")
    return build_governance_decision_record(
        decision_id=f"{validation_result.validation_id}:decision",
        subject_type="validation_result",
        subject_id=validation_result.validation_id,
        decision="reject",
        decision_scope="promotion",
        rationale="validation outcome rejected",
        approver="system_governance",
        status="recorded",
        evidence_refs=validation_result.evidence_refs,
    )


def build_b4_local_global_guardrail_diagnostic(
    *,
    gap_records: Sequence[GapRecord],
    trace_bundle: TraceBundle,
    interaction_guardrail_breaches: Sequence[InteractionGuardrailBreach],
) -> DiagnosticChain:
    if trace_bundle.sample_bucket != B4_INTERACTION_GUARDRAIL_SAMPLE:
        raise ValueError("trace_bundle.sample_bucket must be B4_interaction_guardrail")

    matching_breaches = [
        breach
        for breach in interaction_guardrail_breaches
        if breach.guardrail_code == GUARDRAIL_CODE_LOCAL_GLOBAL_END
    ]
    if not matching_breaches:
        raise ValueError("B4 local-global guardrail breach is required")

    matching_gap_ids = [
        gap.gap_id
        for gap in gap_records
        if gap.gap_label == GAP_LABEL_LOCAL_GLOBAL_MISREAD
    ]
    evidence_refs: list[dict[str, Any]] = []
    for breach in matching_breaches:
        evidence_refs.extend(_normalize_evidence_refs(breach.evidence_refs))
    for gap in gap_records:
        if gap.gap_id in matching_gap_ids:
            evidence_refs.extend(_normalize_evidence_refs(gap.evidence_refs))

    return build_diagnostic_chain(
        diagnostic_id=(
            f"{trace_bundle.trace_id}:{GUARDRAIL_CODE_LOCAL_GLOBAL_END}:diagnostic"
        ),
        symbol=trace_bundle.symbol,
        trade_date=trace_bundle.trade_date,
        sample_bucket=trace_bundle.sample_bucket,
        primary_root_layer=ROOT_LAYER_INTERACTION,
        secondary_layers=[ROOT_LAYER_RECOGNITION, ROOT_LAYER_TRANSLATION],
        interaction_layers=["M2", "M3", "M4"],
        problem_statement=(
            "Local-end-only semantics drifted into a global-end interpretation "
            "and triggered the formal B4 interaction guardrail."
        ),
        suspected_root_cause=(
            "Local/global termination semantics were not preserved consistently "
            "across recognition, translation, and benchmark validation layers."
        ),
        recommended_path=PATH_INTERACTION_SEMANTIC_REPAIR,
        source_gap_ids=matching_gap_ids,
        source_breach_ids=[breach.breach_id for breach in matching_breaches],
        evidence_refs=evidence_refs,
        trace_id=trace_bundle.trace_id,
        benchmark_run_id=trace_bundle.benchmark_run_id,
    )


def build_change_request_from_diagnostic(
    *,
    diagnostic: DiagnosticChain,
    target_layer: str = "M2-M3",
) -> ChangeRequest:
    return build_change_request(
        cr_id=f"{diagnostic.diagnostic_id}:cr",
        diagnostic_id=diagnostic.diagnostic_id,
        target_layer=target_layer,
        source_gap_ids=diagnostic.source_gap_ids,
        problem_statement=diagnostic.problem_statement,
        suspected_root_cause=diagnostic.suspected_root_cause,
        expected_improvement=(
            "Clear the local/global termination semantics drift without "
            "introducing new high-severity interaction gaps."
        ),
        risk_scope="benchmark_guardrail",
        priority="high",
        requires_human_approval=True,
        status="proposed",
        evidence_refs=diagnostic.evidence_refs,
    )


def build_experiment_request_from_change_request(
    *,
    change_request: ChangeRequest,
    sample_bucket: str = B4_INTERACTION_GUARDRAIL_SAMPLE,
) -> ExperimentRequest:
    return build_experiment_request(
        experiment_id=f"{change_request.cr_id}:experiment",
        cr_id=change_request.cr_id,
        target_layer=change_request.target_layer,
        hypothesis=(
            "If the local/global termination semantics are aligned across the "
            "target layers, the B4 interaction guardrail should clear."
        ),
        expected_improvement=change_request.expected_improvement,
        guardrail_codes=[GUARDRAIL_CODE_LOCAL_GLOBAL_END],
        comparison_scope={
            "sample_bucket": sample_bucket,
            "validation_path": PATH_EXPERIMENT_VALIDATION,
            "compare_mode": "baseline_vs_candidate",
        },
        status="proposed",
        evidence_refs=change_request.evidence_refs,
    )


def build_promotion_blocker_from_diagnostic(
    *,
    diagnostic: DiagnosticChain,
    blocker_code: str = GUARDRAIL_CODE_LOCAL_GLOBAL_END,
) -> PromotionBlocker:
    return build_promotion_blocker(
        blocker_id=f"{diagnostic.diagnostic_id}:blocker",
        diagnostic_id=diagnostic.diagnostic_id,
        blocker_code=blocker_code,
        severity="high",
        reason=diagnostic.problem_statement,
        required_clearance=(
            "clear_guardrail_and_no_new_high_severity_gap_via_"
            f"{PATH_HUMAN_ESCALATION}"
        ),
        active=True,
        evidence_refs=diagnostic.evidence_refs,
    )
