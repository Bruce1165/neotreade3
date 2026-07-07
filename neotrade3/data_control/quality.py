"""Quality-status helpers for M1 phase-1 formal objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class M1QualityStatus:
    """Minimal quality-state payload for a formal M1 object family."""

    source_status: str
    freshness_status: str
    coverage_status: str
    replay_status: str
    details: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "source_status": self.source_status,
            "freshness_status": self.freshness_status,
            "coverage_status": self.coverage_status,
            "replay_status": self.replay_status,
            "details": dict(self.details or {}),
        }


@dataclass(frozen=True)
class M1FreshnessProof:
    """Minimal freshness-proof payload for a formal M1 object family."""

    object_family: str
    verdict: str
    reason: str
    target_date: Optional[str] = None
    observed_date: Optional[str] = None
    source_ref: Optional[str] = None
    required_window: Optional[str] = None
    available_window: Optional[str] = None
    details: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_family": self.object_family,
            "verdict": self.verdict,
            "reason": self.reason,
            "target_date": self.target_date,
            "observed_date": self.observed_date,
            "source_ref": self.source_ref,
            "required_window": self.required_window,
            "available_window": self.available_window,
            "details": dict(self.details or {}),
        }


@dataclass(frozen=True)
class M1AttentionItem:
    """Minimal structured attention item for M1 phase-1 issues."""

    issue_code: str
    severity: str
    message: str
    impacts: list[str]
    details: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "issue_code": self.issue_code,
            "severity": self.severity,
            "message": self.message,
            "impacts": list(self.impacts),
            "details": dict(self.details or {}),
        }


def build_quality_status(
    *,
    source_status: str,
    freshness_status: str,
    coverage_status: str,
    replay_status: str,
    details: Optional[dict[str, Any]] = None,
) -> M1QualityStatus:
    return M1QualityStatus(
        source_status=source_status,
        freshness_status=freshness_status,
        coverage_status=coverage_status,
        replay_status=replay_status,
        details=details or {},
    )


def build_attention_item(
    *,
    issue_code: str,
    severity: str,
    message: str,
    impacts: list[str],
    details: Optional[dict[str, Any]] = None,
) -> M1AttentionItem:
    return M1AttentionItem(
        issue_code=issue_code,
        severity=severity,
        message=message,
        impacts=list(impacts),
        details=details or {},
    )


def build_freshness_proof(
    *,
    object_family: str,
    verdict: str,
    reason: str,
    target_date: Optional[str] = None,
    observed_date: Optional[str] = None,
    source_ref: Optional[str] = None,
    required_window: Optional[str] = None,
    available_window: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> M1FreshnessProof:
    return M1FreshnessProof(
        object_family=object_family,
        verdict=verdict,
        reason=reason,
        target_date=target_date,
        observed_date=observed_date,
        source_ref=source_ref,
        required_window=required_window,
        available_window=available_window,
        details=details or {},
    )
