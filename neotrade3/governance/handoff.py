"""Pure M4 -> M5 governance handoff projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from neotrade3.benchmark.assembler import GUARDRAIL_CODE_LOCAL_GLOBAL_END
from neotrade3.benchmark.batch_runner import BenchmarkBatchRunResult
from neotrade3.benchmark.contracts import BenchmarkAssessmentResult

from .assembler import (
    build_attention_item,
    build_block_decision_record_from_promotion_blocker,
    build_b4_local_global_guardrail_diagnostic,
    build_change_request_from_diagnostic,
    build_experiment_request_from_change_request,
    build_pending_validation_result_from_experiment_request,
    build_promotion_blocker_from_diagnostic,
)
from .contracts import (
    AttentionItem,
    ChangeRequest,
    DiagnosticChain,
    ExperimentRequest,
    GovernanceDecisionRecord,
    PromotionBlocker,
    ValidationResult,
)

GOVERNANCE_HANDOFF_BUNDLE_OBJECT_TYPE = "governance_handoff_bundle"
GOVERNANCE_HANDOFF_BUNDLE_OBJECT_VERSION = 1
M4_SOURCE_LAYER = "M4"


def _copy_payload_list(objects: Sequence[Any]) -> list[dict[str, Any]]:
    return [item.to_payload() for item in objects]


@dataclass(frozen=True)
class GovernanceHandoffBundle:
    source_run_id: str
    source_layer: str
    diagnostics: tuple[DiagnosticChain, ...] = ()
    change_requests: tuple[ChangeRequest, ...] = ()
    experiment_requests: tuple[ExperimentRequest, ...] = ()
    validation_results: tuple[ValidationResult, ...] = ()
    promotion_blockers: tuple[PromotionBlocker, ...] = ()
    attention_items: tuple[AttentionItem, ...] = ()
    decision_records: tuple[GovernanceDecisionRecord, ...] = ()
    projected_assessment_count: int = 0
    projected_issue_count: int = 0
    object_type: str = GOVERNANCE_HANDOFF_BUNDLE_OBJECT_TYPE
    object_version: int = GOVERNANCE_HANDOFF_BUNDLE_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "source_run_id": self.source_run_id,
            "source_layer": self.source_layer,
            "diagnostics": _copy_payload_list(self.diagnostics),
            "change_requests": _copy_payload_list(self.change_requests),
            "experiment_requests": _copy_payload_list(self.experiment_requests),
            "validation_results": _copy_payload_list(self.validation_results),
            "promotion_blockers": _copy_payload_list(self.promotion_blockers),
            "attention_items": _copy_payload_list(self.attention_items),
            "decision_records": _copy_payload_list(self.decision_records),
            "projected_assessment_count": int(self.projected_assessment_count),
            "projected_issue_count": int(self.projected_issue_count),
            "object_type": self.object_type,
            "object_version": self.object_version,
        }


def _empty_handoff_bundle(
    *,
    source_run_id: str,
    projected_assessment_count: int,
) -> GovernanceHandoffBundle:
    return GovernanceHandoffBundle(
        source_run_id=str(source_run_id or "").strip(),
        source_layer=M4_SOURCE_LAYER,
        projected_assessment_count=projected_assessment_count,
        projected_issue_count=0,
    )


def _build_attention_item_from_blocker(
    *,
    diagnostic: DiagnosticChain,
    blocker: PromotionBlocker,
) -> AttentionItem:
    return build_attention_item(
        attention_id=f"{blocker.blocker_id}:attention",
        created_at=diagnostic.trade_date,
        source="governance",
        target_layer="M5",
        issue_type="promotion_blocker",
        severity=blocker.severity,
        automation_class="human_review_required",
        evidence_refs=blocker.evidence_refs,
        recommended_action=blocker.required_clearance,
        human_action_required=True,
        status="open",
        owner="system_governance",
        blocking_scope="promotion",
    )


def build_governance_handoff_from_assessment(
    *,
    assessment: BenchmarkAssessmentResult,
) -> GovernanceHandoffBundle:
    source_run_id = str(assessment.summary.benchmark_run_id or "").strip()
    if assessment.trace_bundle is None:
        return _empty_handoff_bundle(
            source_run_id=source_run_id,
            projected_assessment_count=1,
        )

    matching_breaches = tuple(
        breach
        for breach in assessment.interaction_guardrail_breaches
        if breach.guardrail_code == GUARDRAIL_CODE_LOCAL_GLOBAL_END
    )
    if not matching_breaches:
        return _empty_handoff_bundle(
            source_run_id=source_run_id,
            projected_assessment_count=1,
        )

    diagnostic = build_b4_local_global_guardrail_diagnostic(
        gap_records=assessment.gap_records,
        trace_bundle=assessment.trace_bundle,
        interaction_guardrail_breaches=matching_breaches,
    )
    change_request = build_change_request_from_diagnostic(diagnostic=diagnostic)
    experiment_request = build_experiment_request_from_change_request(
        change_request=change_request
    )
    validation_result = build_pending_validation_result_from_experiment_request(
        experiment_request=experiment_request,
        baseline_run_id=source_run_id,
    )
    promotion_blocker = build_promotion_blocker_from_diagnostic(
        diagnostic=diagnostic
    )
    attention_item = _build_attention_item_from_blocker(
        diagnostic=diagnostic,
        blocker=promotion_blocker,
    )
    decision_record = build_block_decision_record_from_promotion_blocker(
        blocker=promotion_blocker
    )
    return GovernanceHandoffBundle(
        source_run_id=source_run_id,
        source_layer=M4_SOURCE_LAYER,
        diagnostics=(diagnostic,),
        change_requests=(change_request,),
        experiment_requests=(experiment_request,),
        validation_results=(validation_result,),
        promotion_blockers=(promotion_blocker,),
        attention_items=(attention_item,),
        decision_records=(decision_record,),
        projected_assessment_count=1,
        projected_issue_count=1,
    )


def build_governance_handoff_from_batch_run(
    *,
    batch_result: BenchmarkBatchRunResult,
) -> GovernanceHandoffBundle:
    diagnostics: list[DiagnosticChain] = []
    change_requests: list[ChangeRequest] = []
    experiment_requests: list[ExperimentRequest] = []
    validation_results: list[ValidationResult] = []
    promotion_blockers: list[PromotionBlocker] = []
    attention_items: list[AttentionItem] = []
    decision_records: list[GovernanceDecisionRecord] = []

    for assessment in batch_result.results:
        bundle = build_governance_handoff_from_assessment(assessment=assessment)
        diagnostics.extend(bundle.diagnostics)
        change_requests.extend(bundle.change_requests)
        experiment_requests.extend(bundle.experiment_requests)
        validation_results.extend(bundle.validation_results)
        promotion_blockers.extend(bundle.promotion_blockers)
        attention_items.extend(bundle.attention_items)
        decision_records.extend(bundle.decision_records)

    return GovernanceHandoffBundle(
        source_run_id=str(batch_result.run_id or "").strip(),
        source_layer=M4_SOURCE_LAYER,
        diagnostics=tuple(diagnostics),
        change_requests=tuple(change_requests),
        experiment_requests=tuple(experiment_requests),
        validation_results=tuple(validation_results),
        promotion_blockers=tuple(promotion_blockers),
        attention_items=tuple(attention_items),
        decision_records=tuple(decision_records),
        projected_assessment_count=len(batch_result.results),
        projected_issue_count=len(diagnostics),
    )
