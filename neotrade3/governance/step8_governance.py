from __future__ import annotations

from typing import Any, Optional


def build_adjustment_proposal_id(*, source_report_id: str) -> str:
    normalized_source_report_id = str(source_report_id or "").strip()
    if not normalized_source_report_id:
        raise ValueError("source_report_id must be non-empty")
    return f"{normalized_source_report_id}:proposal"


def build_governance_decision_log_id(*, source_proposal_id: str) -> str:
    normalized_source_proposal_id = str(source_proposal_id or "").strip()
    if not normalized_source_proposal_id:
        raise ValueError("source_proposal_id must be non-empty")
    return f"{normalized_source_proposal_id}:decision_log"


def build_adjustment_proposal_v0(
    *,
    asof_date: str,
    source_report_id: str,
    proposal_id: Optional[str] = None,
    status: str = "draft",
    rb_ids_touched: list[str] | None = None,
    proposed_changes: list[dict[str, str]] | None = None,
    risk_notes: str | None = None,
    evidence_paths: list[str] | None = None,
) -> dict[str, Any]:
    normalized_asof_date = str(asof_date or "").strip()
    normalized_source_report_id = str(source_report_id or "").strip()
    normalized_proposal_id = str(proposal_id or "").strip() or build_adjustment_proposal_id(
        source_report_id=normalized_source_report_id
    )
    normalized_status = str(status or "").strip() or "draft"
    normalized_rb_ids = [str(x).strip() for x in list(rb_ids_touched or []) if str(x).strip()]
    normalized_changes: list[dict[str, str]] = []
    for item in list(proposed_changes or []):
        if isinstance(item, dict):
            normalized_changes.append({str(k): str(v) for k, v in item.items()})
    normalized_evidence = [str(p).strip() for p in list(evidence_paths or []) if str(p).strip()]
    normalized_risk_notes = str(risk_notes or "").strip() or None
    return {
        "proposal_id": normalized_proposal_id,
        "asof_date": normalized_asof_date,
        "source_report_id": normalized_source_report_id,
        "status": normalized_status,
        "rb_ids_touched": normalized_rb_ids,
        "proposed_changes": normalized_changes,
        "risk_notes": normalized_risk_notes,
        "evidence_paths": normalized_evidence,
    }


def build_governance_decision_log_v0(
    *,
    asof_date: str,
    source_proposal_id: str,
    log_id: Optional[str] = None,
    decision: str = "defer",
    rationale: str = "v0 default defer",
    evidence_paths: list[str] | None = None,
    application_record_id: str | None = None,
) -> dict[str, Any]:
    normalized_asof_date = str(asof_date or "").strip()
    normalized_source_proposal_id = str(source_proposal_id or "").strip()
    normalized_log_id = str(log_id or "").strip() or build_governance_decision_log_id(
        source_proposal_id=normalized_source_proposal_id
    )
    normalized_decision = str(decision or "").strip() or "defer"
    normalized_rationale = str(rationale or "").strip() or "v0 default defer"
    normalized_evidence = [str(p).strip() for p in list(evidence_paths or []) if str(p).strip()]
    normalized_application_record_id = str(application_record_id or "").strip() or None
    return {
        "log_id": normalized_log_id,
        "asof_date": normalized_asof_date,
        "source_proposal_id": normalized_source_proposal_id,
        "decision": normalized_decision,
        "rationale": normalized_rationale,
        "evidence_paths": normalized_evidence,
        "application_record_id": normalized_application_record_id,
    }

