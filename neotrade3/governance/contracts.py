"""Formal M5 governance contract objects for NeoTrade3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DIAGNOSTIC_CHAIN_OBJECT_TYPE = "diagnostic_chain"
CHANGE_REQUEST_OBJECT_TYPE = "change_request"
EXPERIMENT_REQUEST_OBJECT_TYPE = "experiment_request"
ATTENTION_ITEM_OBJECT_TYPE = "attention_item"
VALIDATION_RESULT_OBJECT_TYPE = "validation_result"
PROMOTION_BLOCKER_OBJECT_TYPE = "promotion_blocker"
GOVERNANCE_DECISION_RECORD_OBJECT_TYPE = "governance_decision_record"
M5_OBJECT_VERSION = 1

ROOT_LAYER_DATA = "A1_data_root"
ROOT_LAYER_RECOGNITION = "A2_recognition_root"
ROOT_LAYER_TRANSLATION = "A3_translation_root"
ROOT_LAYER_INTERACTION = "A4_interaction_root"
ROOT_LAYER_GOVERNANCE = "A5_governance_root"

PATH_DATA_REPAIR = "P1_data_repair"
PATH_RECOGNITION_REPAIR = "P2_recognition_repair"
PATH_TRANSLATION_REPAIR = "P3_translation_repair"
PATH_INTERACTION_SEMANTIC_REPAIR = "P4_interaction_semantic_repair"
PATH_EXPERIMENT_VALIDATION = "P5_experiment_validation"
PATH_HUMAN_ESCALATION = "P6_human_escalation"


def _require_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be a JSON object")
    return value


def _copy_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _copy_mapping_list(value: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    copied: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            copied.append(dict(item))
    return copied


def _copy_text_list(value: list[str] | None) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


@dataclass(frozen=True)
class DiagnosticChain:
    diagnostic_id: str
    symbol: str
    trade_date: str
    sample_bucket: str
    primary_root_layer: str
    secondary_layers: list[str]
    interaction_layers: list[str]
    problem_statement: str
    suspected_root_cause: str
    recommended_path: str
    source_gap_ids: list[str]
    source_breach_ids: list[str]
    evidence_refs: list[dict[str, Any]]
    trace_id: str = ""
    benchmark_run_id: str = ""
    object_type: str = DIAGNOSTIC_CHAIN_OBJECT_TYPE
    object_version: int = M5_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "diagnostic_id": self.diagnostic_id,
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "sample_bucket": self.sample_bucket,
            "primary_root_layer": self.primary_root_layer,
            "secondary_layers": _copy_text_list(self.secondary_layers),
            "interaction_layers": _copy_text_list(self.interaction_layers),
            "problem_statement": self.problem_statement,
            "suspected_root_cause": self.suspected_root_cause,
            "recommended_path": self.recommended_path,
            "source_gap_ids": _copy_text_list(self.source_gap_ids),
            "source_breach_ids": _copy_text_list(self.source_breach_ids),
            "evidence_refs": _copy_mapping_list(self.evidence_refs),
            "trace_id": self.trace_id,
            "benchmark_run_id": self.benchmark_run_id,
            "object_type": self.object_type,
            "object_version": self.object_version,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "DiagnosticChain":
        payload_mapping = _require_mapping(payload, field_name="diagnostic_chain")
        return cls(
            diagnostic_id=_require_text(
                payload_mapping.get("diagnostic_id"),
                field_name="diagnostic_id",
            ),
            symbol=_require_text(payload_mapping.get("symbol"), field_name="symbol"),
            trade_date=_require_text(
                payload_mapping.get("trade_date"),
                field_name="trade_date",
            ),
            sample_bucket=_require_text(
                payload_mapping.get("sample_bucket"),
                field_name="sample_bucket",
            ),
            primary_root_layer=_require_text(
                payload_mapping.get("primary_root_layer"),
                field_name="primary_root_layer",
            ),
            secondary_layers=_copy_text_list(payload_mapping.get("secondary_layers")),
            interaction_layers=_copy_text_list(payload_mapping.get("interaction_layers")),
            problem_statement=_require_text(
                payload_mapping.get("problem_statement"),
                field_name="problem_statement",
            ),
            suspected_root_cause=_require_text(
                payload_mapping.get("suspected_root_cause"),
                field_name="suspected_root_cause",
            ),
            recommended_path=_require_text(
                payload_mapping.get("recommended_path"),
                field_name="recommended_path",
            ),
            source_gap_ids=_copy_text_list(payload_mapping.get("source_gap_ids")),
            source_breach_ids=_copy_text_list(payload_mapping.get("source_breach_ids")),
            evidence_refs=_copy_mapping_list(payload_mapping.get("evidence_refs")),
            trace_id=str(payload_mapping.get("trace_id") or "").strip(),
            benchmark_run_id=str(payload_mapping.get("benchmark_run_id") or "").strip(),
            object_type=str(
                payload_mapping.get("object_type", DIAGNOSTIC_CHAIN_OBJECT_TYPE)
            ),
            object_version=int(payload_mapping.get("object_version", M5_OBJECT_VERSION)),
        )


@dataclass(frozen=True)
class ChangeRequest:
    cr_id: str
    diagnostic_id: str
    target_layer: str
    source_gap_ids: list[str]
    problem_statement: str
    suspected_root_cause: str
    expected_improvement: str
    risk_scope: str
    priority: str
    requires_human_approval: bool
    status: str
    evidence_refs: list[dict[str, Any]]
    object_type: str = CHANGE_REQUEST_OBJECT_TYPE
    object_version: int = M5_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "cr_id": self.cr_id,
            "diagnostic_id": self.diagnostic_id,
            "target_layer": self.target_layer,
            "source_gap_ids": _copy_text_list(self.source_gap_ids),
            "problem_statement": self.problem_statement,
            "suspected_root_cause": self.suspected_root_cause,
            "expected_improvement": self.expected_improvement,
            "risk_scope": self.risk_scope,
            "priority": self.priority,
            "requires_human_approval": self.requires_human_approval,
            "status": self.status,
            "evidence_refs": _copy_mapping_list(self.evidence_refs),
            "object_type": self.object_type,
            "object_version": self.object_version,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "ChangeRequest":
        payload_mapping = _require_mapping(payload, field_name="change_request")
        return cls(
            cr_id=_require_text(payload_mapping.get("cr_id"), field_name="cr_id"),
            diagnostic_id=_require_text(
                payload_mapping.get("diagnostic_id"),
                field_name="diagnostic_id",
            ),
            target_layer=_require_text(
                payload_mapping.get("target_layer"),
                field_name="target_layer",
            ),
            source_gap_ids=_copy_text_list(payload_mapping.get("source_gap_ids")),
            problem_statement=_require_text(
                payload_mapping.get("problem_statement"),
                field_name="problem_statement",
            ),
            suspected_root_cause=_require_text(
                payload_mapping.get("suspected_root_cause"),
                field_name="suspected_root_cause",
            ),
            expected_improvement=_require_text(
                payload_mapping.get("expected_improvement"),
                field_name="expected_improvement",
            ),
            risk_scope=_require_text(
                payload_mapping.get("risk_scope"),
                field_name="risk_scope",
            ),
            priority=_require_text(payload_mapping.get("priority"), field_name="priority"),
            requires_human_approval=bool(
                payload_mapping.get("requires_human_approval")
            ),
            status=_require_text(payload_mapping.get("status"), field_name="status"),
            evidence_refs=_copy_mapping_list(payload_mapping.get("evidence_refs")),
            object_type=str(
                payload_mapping.get("object_type", CHANGE_REQUEST_OBJECT_TYPE)
            ),
            object_version=int(payload_mapping.get("object_version", M5_OBJECT_VERSION)),
        )


@dataclass(frozen=True)
class ExperimentRequest:
    experiment_id: str
    cr_id: str
    target_layer: str
    hypothesis: str
    expected_improvement: str
    guardrail_codes: list[str]
    comparison_scope: dict[str, Any]
    status: str
    evidence_refs: list[dict[str, Any]]
    object_type: str = EXPERIMENT_REQUEST_OBJECT_TYPE
    object_version: int = M5_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "cr_id": self.cr_id,
            "target_layer": self.target_layer,
            "hypothesis": self.hypothesis,
            "expected_improvement": self.expected_improvement,
            "guardrail_codes": _copy_text_list(self.guardrail_codes),
            "comparison_scope": _copy_mapping(self.comparison_scope),
            "status": self.status,
            "evidence_refs": _copy_mapping_list(self.evidence_refs),
            "object_type": self.object_type,
            "object_version": self.object_version,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "ExperimentRequest":
        payload_mapping = _require_mapping(payload, field_name="experiment_request")
        return cls(
            experiment_id=_require_text(
                payload_mapping.get("experiment_id"),
                field_name="experiment_id",
            ),
            cr_id=_require_text(payload_mapping.get("cr_id"), field_name="cr_id"),
            target_layer=_require_text(
                payload_mapping.get("target_layer"),
                field_name="target_layer",
            ),
            hypothesis=_require_text(
                payload_mapping.get("hypothesis"),
                field_name="hypothesis",
            ),
            expected_improvement=_require_text(
                payload_mapping.get("expected_improvement"),
                field_name="expected_improvement",
            ),
            guardrail_codes=_copy_text_list(payload_mapping.get("guardrail_codes")),
            comparison_scope=_copy_mapping(payload_mapping.get("comparison_scope")),
            status=_require_text(payload_mapping.get("status"), field_name="status"),
            evidence_refs=_copy_mapping_list(payload_mapping.get("evidence_refs")),
            object_type=str(
                payload_mapping.get("object_type", EXPERIMENT_REQUEST_OBJECT_TYPE)
            ),
            object_version=int(payload_mapping.get("object_version", M5_OBJECT_VERSION)),
        )


@dataclass(frozen=True)
class AttentionItem:
    attention_id: str
    created_at: str
    source: str
    target_layer: str
    issue_type: str
    severity: str
    automation_class: str
    evidence_refs: list[dict[str, Any]]
    recommended_action: str
    human_action_required: bool
    status: str
    owner: str
    blocking_scope: str
    object_type: str = ATTENTION_ITEM_OBJECT_TYPE
    object_version: int = M5_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "attention_id": self.attention_id,
            "created_at": self.created_at,
            "source": self.source,
            "target_layer": self.target_layer,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "automation_class": self.automation_class,
            "evidence_refs": _copy_mapping_list(self.evidence_refs),
            "recommended_action": self.recommended_action,
            "human_action_required": bool(self.human_action_required),
            "status": self.status,
            "owner": self.owner,
            "blocking_scope": self.blocking_scope,
            "object_type": self.object_type,
            "object_version": self.object_version,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "AttentionItem":
        payload_mapping = _require_mapping(payload, field_name="attention_item")
        return cls(
            attention_id=_require_text(
                payload_mapping.get("attention_id"),
                field_name="attention_id",
            ),
            created_at=_require_text(
                payload_mapping.get("created_at"),
                field_name="created_at",
            ),
            source=_require_text(payload_mapping.get("source"), field_name="source"),
            target_layer=_require_text(
                payload_mapping.get("target_layer"),
                field_name="target_layer",
            ),
            issue_type=_require_text(
                payload_mapping.get("issue_type"),
                field_name="issue_type",
            ),
            severity=_require_text(
                payload_mapping.get("severity"),
                field_name="severity",
            ),
            automation_class=_require_text(
                payload_mapping.get("automation_class"),
                field_name="automation_class",
            ),
            evidence_refs=_copy_mapping_list(payload_mapping.get("evidence_refs")),
            recommended_action=_require_text(
                payload_mapping.get("recommended_action"),
                field_name="recommended_action",
            ),
            human_action_required=bool(payload_mapping.get("human_action_required")),
            status=_require_text(payload_mapping.get("status"), field_name="status"),
            owner=_require_text(payload_mapping.get("owner"), field_name="owner"),
            blocking_scope=_require_text(
                payload_mapping.get("blocking_scope"),
                field_name="blocking_scope",
            ),
            object_type=str(
                payload_mapping.get("object_type", ATTENTION_ITEM_OBJECT_TYPE)
            ),
            object_version=int(payload_mapping.get("object_version", M5_OBJECT_VERSION)),
        )


@dataclass(frozen=True)
class ValidationResult:
    validation_id: str
    experiment_id: str
    baseline_run_id: str
    candidate_run_id: str
    outcome: str
    cleared_guardrail_codes: list[str]
    remaining_guardrail_codes: list[str]
    introduced_risk_count: int
    evidence_refs: list[dict[str, Any]]
    object_type: str = VALIDATION_RESULT_OBJECT_TYPE
    object_version: int = M5_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "experiment_id": self.experiment_id,
            "baseline_run_id": self.baseline_run_id,
            "candidate_run_id": self.candidate_run_id,
            "outcome": self.outcome,
            "cleared_guardrail_codes": _copy_text_list(self.cleared_guardrail_codes),
            "remaining_guardrail_codes": _copy_text_list(
                self.remaining_guardrail_codes
            ),
            "introduced_risk_count": int(self.introduced_risk_count),
            "evidence_refs": _copy_mapping_list(self.evidence_refs),
            "object_type": self.object_type,
            "object_version": self.object_version,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "ValidationResult":
        payload_mapping = _require_mapping(payload, field_name="validation_result")
        return cls(
            validation_id=_require_text(
                payload_mapping.get("validation_id"),
                field_name="validation_id",
            ),
            experiment_id=_require_text(
                payload_mapping.get("experiment_id"),
                field_name="experiment_id",
            ),
            baseline_run_id=_require_text(
                payload_mapping.get("baseline_run_id"),
                field_name="baseline_run_id",
            ),
            candidate_run_id=str(payload_mapping.get("candidate_run_id") or "").strip(),
            outcome=_require_text(payload_mapping.get("outcome"), field_name="outcome"),
            cleared_guardrail_codes=_copy_text_list(
                payload_mapping.get("cleared_guardrail_codes")
            ),
            remaining_guardrail_codes=_copy_text_list(
                payload_mapping.get("remaining_guardrail_codes")
            ),
            introduced_risk_count=int(payload_mapping.get("introduced_risk_count", 0)),
            evidence_refs=_copy_mapping_list(payload_mapping.get("evidence_refs")),
            object_type=str(
                payload_mapping.get("object_type", VALIDATION_RESULT_OBJECT_TYPE)
            ),
            object_version=int(payload_mapping.get("object_version", M5_OBJECT_VERSION)),
        )


@dataclass(frozen=True)
class PromotionBlocker:
    blocker_id: str
    diagnostic_id: str
    blocker_code: str
    severity: str
    reason: str
    required_clearance: str
    active: bool
    evidence_refs: list[dict[str, Any]]
    object_type: str = PROMOTION_BLOCKER_OBJECT_TYPE
    object_version: int = M5_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "blocker_id": self.blocker_id,
            "diagnostic_id": self.diagnostic_id,
            "blocker_code": self.blocker_code,
            "severity": self.severity,
            "reason": self.reason,
            "required_clearance": self.required_clearance,
            "active": self.active,
            "evidence_refs": _copy_mapping_list(self.evidence_refs),
            "object_type": self.object_type,
            "object_version": self.object_version,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "PromotionBlocker":
        payload_mapping = _require_mapping(payload, field_name="promotion_blocker")
        return cls(
            blocker_id=_require_text(
                payload_mapping.get("blocker_id"),
                field_name="blocker_id",
            ),
            diagnostic_id=_require_text(
                payload_mapping.get("diagnostic_id"),
                field_name="diagnostic_id",
            ),
            blocker_code=_require_text(
                payload_mapping.get("blocker_code"),
                field_name="blocker_code",
            ),
            severity=_require_text(
                payload_mapping.get("severity"),
                field_name="severity",
            ),
            reason=_require_text(payload_mapping.get("reason"), field_name="reason"),
            required_clearance=_require_text(
                payload_mapping.get("required_clearance"),
                field_name="required_clearance",
            ),
            active=bool(payload_mapping.get("active")),
            evidence_refs=_copy_mapping_list(payload_mapping.get("evidence_refs")),
            object_type=str(
                payload_mapping.get("object_type", PROMOTION_BLOCKER_OBJECT_TYPE)
            ),
            object_version=int(payload_mapping.get("object_version", M5_OBJECT_VERSION)),
        )


@dataclass(frozen=True)
class GovernanceDecisionRecord:
    decision_id: str
    subject_type: str
    subject_id: str
    decision: str
    decision_scope: str
    rationale: str
    approver: str
    status: str
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    object_type: str = GOVERNANCE_DECISION_RECORD_OBJECT_TYPE
    object_version: int = M5_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "decision": self.decision,
            "decision_scope": self.decision_scope,
            "rationale": self.rationale,
            "approver": self.approver,
            "status": self.status,
            "evidence_refs": _copy_mapping_list(self.evidence_refs),
            "object_type": self.object_type,
            "object_version": self.object_version,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "GovernanceDecisionRecord":
        payload_mapping = _require_mapping(
            payload,
            field_name="governance_decision_record",
        )
        return cls(
            decision_id=_require_text(
                payload_mapping.get("decision_id"),
                field_name="decision_id",
            ),
            subject_type=_require_text(
                payload_mapping.get("subject_type"),
                field_name="subject_type",
            ),
            subject_id=_require_text(
                payload_mapping.get("subject_id"),
                field_name="subject_id",
            ),
            decision=_require_text(
                payload_mapping.get("decision"),
                field_name="decision",
            ),
            decision_scope=_require_text(
                payload_mapping.get("decision_scope"),
                field_name="decision_scope",
            ),
            rationale=_require_text(
                payload_mapping.get("rationale"),
                field_name="rationale",
            ),
            approver=_require_text(
                payload_mapping.get("approver"),
                field_name="approver",
            ),
            status=_require_text(payload_mapping.get("status"), field_name="status"),
            evidence_refs=_copy_mapping_list(payload_mapping.get("evidence_refs")),
            object_type=str(
                payload_mapping.get(
                    "object_type",
                    GOVERNANCE_DECISION_RECORD_OBJECT_TYPE,
                )
            ),
            object_version=int(payload_mapping.get("object_version", M5_OBJECT_VERSION)),
        )
