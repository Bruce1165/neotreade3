"""Core models for the NeoTrade3 learning bootstrap."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class EvaluationDecision(str, Enum):
    """Bootstrap evaluation decisions for the learning loop."""

    REVIEW_REQUIRED = "review_required"
    STABLE = "stable"


@dataclass
class LearningInputSnapshot:
    """Collected daily inputs used by the learning bootstrap."""

    target_date: date
    task_result_count: int
    issue_event_count: int
    issue_case_count: int
    labs_seen: list[str] = field(default_factory=list)
    market_context: dict[str, object] = field(default_factory=dict)


@dataclass
class MetricSnapshot:
    """Minimal metric summary derived from bootstrap signals."""

    target_date: date
    total_tasks: int
    blocked_tasks: int
    skipped_tasks: int
    pending_tasks: int
    issue_events: int
    issue_cases: int


@dataclass
class AdjustmentCandidate:
    """Placeholder adjustment proposal requiring later review."""

    candidate_id: str
    target_date: date
    scope: str
    decision: EvaluationDecision
    reason: str
    recommended_action: str


@dataclass
class AuditRecord:
    """Bootstrap audit trail for learning-loop outputs."""

    audit_id: str
    target_date: date
    decision: EvaluationDecision
    summary: str


@dataclass
class LearningCycleSnapshot:
    """Combined bootstrap snapshot for the learning loop."""

    inputs: LearningInputSnapshot
    metrics: MetricSnapshot
    adjustment_candidates: list[AdjustmentCandidate] = field(default_factory=list)
    audit_records: list[AuditRecord] = field(default_factory=list)


@dataclass
class FactorSignal:
    source: str
    name: str
    value: float | None
    direction: str
    confidence_hint: float | None
    evidence: list[str] = field(default_factory=list)
    raw_refs: dict[str, str] = field(default_factory=dict)


@dataclass
class FactorMatrixStockCandidate:
    stock_code: str
    stock_name: str
    sector_lv1: str | None
    sector_lv2: str | None
    certainty: float
    subscores: dict[str, float]
    evidence: dict[str, list[str]]
    signals: list[FactorSignal] = field(default_factory=list)


@dataclass
class FactorMatrixDailyOutput:
    target_date: date
    universe: dict[str, object]
    market_context: dict[str, object]
    tiers: dict[str, list[FactorMatrixStockCandidate]]
    candidates_summary: dict[str, object]
    model_state: dict[str, object]
