"""Core models for the NeoTrade3 issue center bootstrap."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class IssueSeverity(str, Enum):
    """Bootstrap severity vocabulary for centralized issue collection."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class IssueEvent:
    """Single issue signal derived from orchestrator planning placeholders."""

    event_id: str
    target_date: date
    source: str
    task_id: str
    phase: str
    severity: IssueSeverity
    status: str
    summary: str
    lab_id: str | None = None
    dependency_refs: list[str] = field(default_factory=list)


@dataclass
class IssueCase:
    """Grouped issue case keyed by one task in the bootstrap stage."""

    case_id: str
    target_date: date
    task_id: str
    phase: str
    severity: IssueSeverity
    status: str
    lab_id: str | None
    summary: str
    event_ids: list[str] = field(default_factory=list)


@dataclass
class RootCauseAnalysis:
    """Root cause analysis for an issue case."""

    primary_cause: str
    cause_category: str  # "dependency", "data", "config", "implementation", "environment"
    evidence: list[str] = field(default_factory=list)
    upstream_tasks: list[str] = field(default_factory=list)


@dataclass
class DegradationInfo:
    """Degradation detection result."""

    is_degradation: bool
    baseline_date: date | None = None
    baseline_value: float | None = None
    current_value: float | None = None
    change_pct: float | None = None
    metric_name: str | None = None


@dataclass
class Recommendation:
    """Actionable recommendation for an issue."""

    action: str
    priority: str  # "high", "medium", "low"
    rationale: str
    expected_outcome: str
    auto_fixable: bool = False


@dataclass
class IssueCenterSnapshot:
    """Daily aggregated issue-center view with deep analysis."""

    target_date: date
    events: list[IssueEvent] = field(default_factory=list)
    cases: list[IssueCase] = field(default_factory=list)
    root_causes: dict[str, RootCauseAnalysis] = field(default_factory=dict)
    degradations: dict[str, DegradationInfo] = field(default_factory=dict)
    recommendations: dict[str, list[Recommendation]] = field(default_factory=dict)
