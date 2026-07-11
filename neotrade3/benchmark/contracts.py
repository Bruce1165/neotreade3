"""Formal contracts for NeoTrade3 M4 benchmark validation seed."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


BENCHMARK_SAMPLE_OBJECT_TYPE = "benchmark_sample"
BENCHMARK_SAMPLE_OBJECT_VERSION = 1

ASSESSMENT_SUMMARY_OBJECT_TYPE = "assessment_summary"
ASSESSMENT_SUMMARY_OBJECT_VERSION = 1

GAP_RECORD_OBJECT_TYPE = "gap_record"
GAP_RECORD_OBJECT_VERSION = 1

TRACE_BUNDLE_OBJECT_TYPE = "trace_bundle"
TRACE_BUNDLE_OBJECT_VERSION = 1

INTERACTION_GUARDRAIL_BREACH_OBJECT_TYPE = "interaction_guardrail_breach"
INTERACTION_GUARDRAIL_BREACH_OBJECT_VERSION = 1


def _require_text(value: object, *, field_name: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{field_name} must be a non-empty string")
    return raw


def _copy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    return {str(key): item for key, item in value.items()}


def _copy_str_list(value: Iterable[object] | None, *, field_name: str) -> list[str]:
    if value is None:
        return []
    items = [str(item).strip() for item in value if str(item).strip()]
    if any(not item for item in items):
        raise ValueError(f"{field_name} items must be non-empty strings")
    return items


def _copy_mapping_list(value: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if value is None:
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("mapping list items must be mapping objects")
        items.append({str(key): val for key, val in item.items()})
    return items


@dataclass(frozen=True)
class BenchmarkSample:
    stock_code: str
    trade_date: str
    sample_bucket: str
    target_state_type: str
    expected_target_state: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    scenario_tags: list[str] = field(default_factory=list)
    note: str = ""
    input_data_version: str = "m1_phase1.v1"
    rule_version: str = "m4_benchmark_seed.v1alpha1"
    object_type: str = BENCHMARK_SAMPLE_OBJECT_TYPE
    object_version: int = BENCHMARK_SAMPLE_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "sample_bucket": self.sample_bucket,
            "target_state_type": self.target_state_type,
            "expected_target_state": dict(self.expected_target_state),
            "evidence_refs": [dict(item) for item in self.evidence_refs],
            "scenario_tags": list(self.scenario_tags),
            "note": self.note,
            "input_data_version": self.input_data_version,
            "rule_version": self.rule_version,
            "object_type": self.object_type,
            "object_version": self.object_version,
        }


@dataclass(frozen=True)
class AssessmentSummary:
    benchmark_run_id: str
    symbol: str
    trade_date: str
    assessment_grade: str
    hard_violation_count: int
    warn_count: int
    sample_bucket_summary: dict[str, Any] = field(default_factory=dict)
    gap_group_distribution: dict[str, Any] = field(default_factory=dict)
    stability_risk_summary: dict[str, Any] = field(default_factory=dict)
    hold_quality_risk_summary: dict[str, Any] = field(default_factory=dict)
    interaction_risk_summary: dict[str, Any] = field(default_factory=dict)
    rule_version: str = "m4_benchmark_seed.v1alpha1"
    object_type: str = ASSESSMENT_SUMMARY_OBJECT_TYPE
    object_version: int = ASSESSMENT_SUMMARY_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "benchmark_run_id": self.benchmark_run_id,
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "assessment_grade": self.assessment_grade,
            "hard_violation_count": self.hard_violation_count,
            "warn_count": self.warn_count,
            "sample_bucket_summary": dict(self.sample_bucket_summary),
            "gap_group_distribution": dict(self.gap_group_distribution),
            "stability_risk_summary": dict(self.stability_risk_summary),
            "hold_quality_risk_summary": dict(self.hold_quality_risk_summary),
            "interaction_risk_summary": dict(self.interaction_risk_summary),
            "rule_version": self.rule_version,
            "object_type": self.object_type,
            "object_version": self.object_version,
        }


@dataclass(frozen=True)
class GapRecord:
    gap_id: str
    symbol: str
    trade_date: str
    date_range: str
    sample_bucket: str
    layer_scope: str
    gap_group: str
    gap_label: str
    severity: str
    target_state_type: str
    expected_target_state: dict[str, Any] = field(default_factory=dict)
    actual_state: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str = ""
    rule_version: str = "m4_benchmark_seed.v1alpha1"
    input_data_version: str = "m1_phase1.v1"
    benchmark_run_id: str = ""
    object_type: str = GAP_RECORD_OBJECT_TYPE
    object_version: int = GAP_RECORD_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "date_range": self.date_range,
            "sample_bucket": self.sample_bucket,
            "layer_scope": self.layer_scope,
            "gap_group": self.gap_group,
            "gap_label": self.gap_label,
            "severity": self.severity,
            "target_state_type": self.target_state_type,
            "expected_target_state": dict(self.expected_target_state),
            "actual_state": dict(self.actual_state),
            "evidence_refs": [dict(item) for item in self.evidence_refs],
            "trace_id": self.trace_id,
            "rule_version": self.rule_version,
            "input_data_version": self.input_data_version,
            "benchmark_run_id": self.benchmark_run_id,
            "object_type": self.object_type,
            "object_version": self.object_version,
        }


@dataclass(frozen=True)
class TraceBundle:
    trace_id: str
    symbol: str
    trade_date: str
    sample_bucket: str
    target_state_type: str
    m1_context: dict[str, Any] = field(default_factory=dict)
    m2_formal: dict[str, Any] = field(default_factory=dict)
    m2_shadow: dict[str, Any] = field(default_factory=dict)
    m3_context: dict[str, Any] = field(default_factory=dict)
    m4_assessment: dict[str, Any] = field(default_factory=dict)
    benchmark_run_id: str = ""
    rule_version: str = "m4_benchmark_seed.v1alpha1"
    object_type: str = TRACE_BUNDLE_OBJECT_TYPE
    object_version: int = TRACE_BUNDLE_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "sample_bucket": self.sample_bucket,
            "target_state_type": self.target_state_type,
            "m1_context": dict(self.m1_context),
            "m2_formal": dict(self.m2_formal),
            "m2_shadow": dict(self.m2_shadow),
            "m3_context": dict(self.m3_context),
            "m4_assessment": dict(self.m4_assessment),
            "benchmark_run_id": self.benchmark_run_id,
            "rule_version": self.rule_version,
            "object_type": self.object_type,
            "object_version": self.object_version,
        }


@dataclass(frozen=True)
class InteractionGuardrailBreach:
    breach_id: str
    symbol: str
    trade_date: str
    sample_bucket: str
    guardrail_code: str
    severity: str
    summary: str
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str = ""
    benchmark_run_id: str = ""
    rule_version: str = "m4_benchmark_seed.v1alpha1"
    object_type: str = INTERACTION_GUARDRAIL_BREACH_OBJECT_TYPE
    object_version: int = INTERACTION_GUARDRAIL_BREACH_OBJECT_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "breach_id": self.breach_id,
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "sample_bucket": self.sample_bucket,
            "guardrail_code": self.guardrail_code,
            "severity": self.severity,
            "summary": self.summary,
            "evidence_refs": [dict(item) for item in self.evidence_refs],
            "trace_id": self.trace_id,
            "benchmark_run_id": self.benchmark_run_id,
            "rule_version": self.rule_version,
            "object_type": self.object_type,
            "object_version": self.object_version,
        }


@dataclass(frozen=True)
class BenchmarkAssessmentResult:
    summary: AssessmentSummary
    gap_records: tuple[GapRecord, ...] = ()
    trace_bundle: TraceBundle | None = None
    interaction_guardrail_breaches: tuple[InteractionGuardrailBreach, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_payload(),
            "gap_records": [item.to_payload() for item in self.gap_records],
            "trace_bundle": (
                self.trace_bundle.to_payload() if self.trace_bundle is not None else None
            ),
            "interaction_guardrail_breaches": [
                item.to_payload() for item in self.interaction_guardrail_breaches
            ],
        }


def build_benchmark_sample(
    *,
    stock_code: str,
    trade_date: str,
    sample_bucket: str,
    target_state_type: str,
    expected_target_state: Mapping[str, Any] | None = None,
    evidence_refs: Iterable[Mapping[str, Any]] | None = None,
    scenario_tags: Iterable[object] | None = None,
    note: str = "",
    input_data_version: str = "m1_phase1.v1",
    rule_version: str = "m4_benchmark_seed.v1alpha1",
) -> BenchmarkSample:
    return BenchmarkSample(
        stock_code=_require_text(stock_code, field_name="stock_code"),
        trade_date=_require_text(trade_date, field_name="trade_date"),
        sample_bucket=_require_text(sample_bucket, field_name="sample_bucket"),
        target_state_type=_require_text(target_state_type, field_name="target_state_type"),
        expected_target_state=_copy_mapping(expected_target_state),
        evidence_refs=_copy_mapping_list(evidence_refs),
        scenario_tags=_copy_str_list(scenario_tags, field_name="scenario_tags"),
        note=str(note or "").strip(),
        input_data_version=_require_text(
            input_data_version,
            field_name="input_data_version",
        ),
        rule_version=_require_text(rule_version, field_name="rule_version"),
    )


def build_assessment_summary(
    *,
    benchmark_run_id: str,
    symbol: str,
    trade_date: str,
    assessment_grade: str,
    hard_violation_count: int,
    warn_count: int,
    sample_bucket_summary: Mapping[str, Any] | None = None,
    gap_group_distribution: Mapping[str, Any] | None = None,
    stability_risk_summary: Mapping[str, Any] | None = None,
    hold_quality_risk_summary: Mapping[str, Any] | None = None,
    interaction_risk_summary: Mapping[str, Any] | None = None,
    rule_version: str = "m4_benchmark_seed.v1alpha1",
) -> AssessmentSummary:
    if hard_violation_count < 0:
        raise ValueError("hard_violation_count must be >= 0")
    if warn_count < 0:
        raise ValueError("warn_count must be >= 0")
    return AssessmentSummary(
        benchmark_run_id=_require_text(
            benchmark_run_id,
            field_name="benchmark_run_id",
        ),
        symbol=_require_text(symbol, field_name="symbol"),
        trade_date=_require_text(trade_date, field_name="trade_date"),
        assessment_grade=_require_text(
            assessment_grade,
            field_name="assessment_grade",
        ),
        hard_violation_count=hard_violation_count,
        warn_count=warn_count,
        sample_bucket_summary=_copy_mapping(sample_bucket_summary),
        gap_group_distribution=_copy_mapping(gap_group_distribution),
        stability_risk_summary=_copy_mapping(stability_risk_summary),
        hold_quality_risk_summary=_copy_mapping(hold_quality_risk_summary),
        interaction_risk_summary=_copy_mapping(interaction_risk_summary),
        rule_version=_require_text(rule_version, field_name="rule_version"),
    )


def build_gap_record(
    *,
    gap_id: str,
    symbol: str,
    trade_date: str,
    date_range: str,
    sample_bucket: str,
    layer_scope: str,
    gap_group: str,
    gap_label: str,
    severity: str,
    target_state_type: str,
    expected_target_state: Mapping[str, Any] | None = None,
    actual_state: Mapping[str, Any] | None = None,
    evidence_refs: Iterable[Mapping[str, Any]] | None = None,
    trace_id: str,
    rule_version: str,
    input_data_version: str,
    benchmark_run_id: str,
) -> GapRecord:
    return GapRecord(
        gap_id=_require_text(gap_id, field_name="gap_id"),
        symbol=_require_text(symbol, field_name="symbol"),
        trade_date=_require_text(trade_date, field_name="trade_date"),
        date_range=_require_text(date_range, field_name="date_range"),
        sample_bucket=_require_text(sample_bucket, field_name="sample_bucket"),
        layer_scope=_require_text(layer_scope, field_name="layer_scope"),
        gap_group=_require_text(gap_group, field_name="gap_group"),
        gap_label=_require_text(gap_label, field_name="gap_label"),
        severity=_require_text(severity, field_name="severity"),
        target_state_type=_require_text(
            target_state_type,
            field_name="target_state_type",
        ),
        expected_target_state=_copy_mapping(expected_target_state),
        actual_state=_copy_mapping(actual_state),
        evidence_refs=_copy_mapping_list(evidence_refs),
        trace_id=_require_text(trace_id, field_name="trace_id"),
        rule_version=_require_text(rule_version, field_name="rule_version"),
        input_data_version=_require_text(
            input_data_version,
            field_name="input_data_version",
        ),
        benchmark_run_id=_require_text(
            benchmark_run_id,
            field_name="benchmark_run_id",
        ),
    )


def build_trace_bundle(
    *,
    trace_id: str,
    symbol: str,
    trade_date: str,
    sample_bucket: str,
    target_state_type: str,
    m1_context: Mapping[str, Any] | None = None,
    m2_formal: Mapping[str, Any] | None = None,
    m2_shadow: Mapping[str, Any] | None = None,
    m3_context: Mapping[str, Any] | None = None,
    m4_assessment: Mapping[str, Any] | None = None,
    benchmark_run_id: str,
    rule_version: str,
) -> TraceBundle:
    return TraceBundle(
        trace_id=_require_text(trace_id, field_name="trace_id"),
        symbol=_require_text(symbol, field_name="symbol"),
        trade_date=_require_text(trade_date, field_name="trade_date"),
        sample_bucket=_require_text(sample_bucket, field_name="sample_bucket"),
        target_state_type=_require_text(
            target_state_type,
            field_name="target_state_type",
        ),
        m1_context=_copy_mapping(m1_context),
        m2_formal=_copy_mapping(m2_formal),
        m2_shadow=_copy_mapping(m2_shadow),
        m3_context=_copy_mapping(m3_context),
        m4_assessment=_copy_mapping(m4_assessment),
        benchmark_run_id=_require_text(
            benchmark_run_id,
            field_name="benchmark_run_id",
        ),
        rule_version=_require_text(rule_version, field_name="rule_version"),
    )


def build_interaction_guardrail_breach(
    *,
    breach_id: str,
    symbol: str,
    trade_date: str,
    sample_bucket: str,
    guardrail_code: str,
    severity: str,
    summary: str,
    evidence_refs: Iterable[Mapping[str, Any]] | None = None,
    trace_id: str,
    benchmark_run_id: str,
    rule_version: str,
) -> InteractionGuardrailBreach:
    return InteractionGuardrailBreach(
        breach_id=_require_text(breach_id, field_name="breach_id"),
        symbol=_require_text(symbol, field_name="symbol"),
        trade_date=_require_text(trade_date, field_name="trade_date"),
        sample_bucket=_require_text(sample_bucket, field_name="sample_bucket"),
        guardrail_code=_require_text(guardrail_code, field_name="guardrail_code"),
        severity=_require_text(severity, field_name="severity"),
        summary=_require_text(summary, field_name="summary"),
        evidence_refs=_copy_mapping_list(evidence_refs),
        trace_id=_require_text(trace_id, field_name="trace_id"),
        benchmark_run_id=_require_text(
            benchmark_run_id,
            field_name="benchmark_run_id",
        ),
        rule_version=_require_text(rule_version, field_name="rule_version"),
    )
