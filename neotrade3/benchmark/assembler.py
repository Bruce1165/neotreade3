"""Minimal M4 benchmark assembly helpers for validating M2 shadow outputs."""

from __future__ import annotations

from typing import Any, Mapping

from neotrade3.cycle_intelligence import SmallCycle
from .contracts import (
    BenchmarkAssessmentResult,
    BenchmarkSample,
    build_assessment_summary,
    build_gap_record,
    build_interaction_guardrail_breach,
    build_trace_bundle,
)


DEFAULT_M4_BENCHMARK_RULE_VERSION = "m4_benchmark_seed.v1alpha1"

B1_TARGET_OPPORTUNITY_SAMPLE = "B1_target_opportunity"
B2_CONTROL_FAILURE_SAMPLE = "B2_control_failure"
B3_BOUNDARY_COMPLEX_SAMPLE = "B3_boundary_complex"
B4_INTERACTION_GUARDRAIL_SAMPLE = "B4_interaction_guardrail"

T1_PROHIBITION_TARGET = "T1_prohibition_target"
T2_RANGE_TARGET = "T2_range_target"
T3_STRONG_TARGET = "T3_strong_target"

ASSESSMENT_GRADE_PASS = "pass"
ASSESSMENT_GRADE_WARN = "warn"
ASSESSMENT_GRADE_FAIL = "fail"

SEVERITY_WARN = "warn"
SEVERITY_HIGH = "high"

GAP_GROUP_IDENTIFY = "G1 Identify Gap"
GAP_GROUP_INTERACTION = "G5 Interaction Gap"

GAP_LABEL_STATE_DRIFT = "L9 State-Drift"
GAP_LABEL_LOCAL_GLOBAL_MISREAD = "L8 Local-Global-Misread"

GUARDRAIL_CODE_LOCAL_GLOBAL_END = "C_GUARD_LOCAL_GLOBAL_END"

_RISK_LEVEL_ORDER = {"low": 0, "watch": 1, "high": 2}


def _payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_payload"):
        return value.to_payload()
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    raise ValueError("value must be a mapping or support to_payload()")


def _shadow_payload_bundle(shadow_bundle: Mapping[str, Any]) -> dict[str, Any]:
    mid_cycle_states_raw = shadow_bundle.get("mid_cycle_states") or {}
    if not isinstance(mid_cycle_states_raw, Mapping):
        raise ValueError("mid_cycle_states must be a mapping")
    mid_cycle_states = {
        str(scope): _payload(state)
        for scope, state in mid_cycle_states_raw.items()
    }
    return {
        "wave_hypothesis": _payload(shadow_bundle.get("wave_hypothesis")),
        "mid_cycle_states": mid_cycle_states,
        "cycle_linkage_state": _payload(shadow_bundle.get("cycle_linkage_state")),
        "growth_potential_profile": _payload(
            shadow_bundle.get("growth_potential_profile")
        ),
        "top_risk_profile": _payload(shadow_bundle.get("top_risk_profile")),
    }


def _risk_leq(actual_level: str, max_level: str) -> bool:
    return _RISK_LEVEL_ORDER.get(str(actual_level), 99) <= _RISK_LEVEL_ORDER.get(
        str(max_level),
        -1,
    )


def _make_benchmark_run_id(sample: BenchmarkSample) -> str:
    return (
        f"m4seed:{sample.sample_bucket}:{sample.stock_code}:{sample.trade_date}:"
        f"{sample.target_state_type}"
    )


def _make_trace_id(benchmark_run_id: str) -> str:
    return f"{benchmark_run_id}:trace"


def _build_state_drift_gap(
    *,
    sample: BenchmarkSample,
    benchmark_run_id: str,
    trace_id: str,
    expected_target_state: Mapping[str, Any],
    actual_state: Mapping[str, Any],
    evidence_refs: list[dict[str, Any]],
) -> Any:
    return build_gap_record(
        gap_id=f"{benchmark_run_id}:gap:{len(evidence_refs)}:{GAP_LABEL_STATE_DRIFT}",
        symbol=sample.stock_code,
        trade_date=sample.trade_date,
        date_range=sample.trade_date,
        sample_bucket=sample.sample_bucket,
        layer_scope="M2",
        gap_group=GAP_GROUP_IDENTIFY,
        gap_label=GAP_LABEL_STATE_DRIFT,
        severity=(
            SEVERITY_HIGH
            if sample.target_state_type in {T1_PROHIBITION_TARGET, T3_STRONG_TARGET}
            else SEVERITY_WARN
        ),
        target_state_type=sample.target_state_type,
        expected_target_state=expected_target_state,
        actual_state=actual_state,
        evidence_refs=evidence_refs,
        trace_id=trace_id,
        rule_version=sample.rule_version,
        input_data_version=sample.input_data_version,
        benchmark_run_id=benchmark_run_id,
    )


def _build_local_global_gap(
    *,
    sample: BenchmarkSample,
    benchmark_run_id: str,
    trace_id: str,
    expected_target_state: Mapping[str, Any],
    actual_state: Mapping[str, Any],
    evidence_refs: list[dict[str, Any]],
) -> Any:
    return build_gap_record(
        gap_id=f"{benchmark_run_id}:gap:interaction:{GAP_LABEL_LOCAL_GLOBAL_MISREAD}",
        symbol=sample.stock_code,
        trade_date=sample.trade_date,
        date_range=sample.trade_date,
        sample_bucket=sample.sample_bucket,
        layer_scope="M2-M3",
        gap_group=GAP_GROUP_INTERACTION,
        gap_label=GAP_LABEL_LOCAL_GLOBAL_MISREAD,
        severity=SEVERITY_HIGH,
        target_state_type=sample.target_state_type,
        expected_target_state=expected_target_state,
        actual_state=actual_state,
        evidence_refs=evidence_refs,
        trace_id=trace_id,
        rule_version=sample.rule_version,
        input_data_version=sample.input_data_version,
        benchmark_run_id=benchmark_run_id,
    )


def build_benchmark_assessment_from_m2_shadow(
    *,
    sample: BenchmarkSample,
    cycle: SmallCycle,
    shadow_bundle: Mapping[str, Any],
    m1_context: Mapping[str, Any] | None = None,
    m3_context: Mapping[str, Any] | None = None,
) -> BenchmarkAssessmentResult:
    cycle_payload = cycle.to_payload()
    shadow_payloads = _shadow_payload_bundle(shadow_bundle)
    expected = sample.expected_target_state

    benchmark_run_id = _make_benchmark_run_id(sample)
    trace_id = _make_trace_id(benchmark_run_id)

    gaps = []
    breaches = []

    def add_state_drift(
        *,
        expected_target_state: Mapping[str, Any],
        actual_state: Mapping[str, Any],
        evidence_refs: list[dict[str, Any]],
    ) -> None:
        gaps.append(
            _build_state_drift_gap(
                sample=sample,
                benchmark_run_id=benchmark_run_id,
                trace_id=trace_id,
                expected_target_state=expected_target_state,
                actual_state=actual_state,
                evidence_refs=evidence_refs,
            )
        )

    small_cycle_expected = expected.get("small_cycle_state") or {}
    allowed_small_cycle = small_cycle_expected.get("allowed") or []
    if allowed_small_cycle and cycle_payload.get("cycle_state") not in allowed_small_cycle:
        add_state_drift(
            expected_target_state={"small_cycle_state": dict(small_cycle_expected)},
            actual_state={"small_cycle_state": cycle_payload.get("cycle_state")},
            evidence_refs=[
                {
                    "object_type": cycle_payload.get("object_type"),
                    "field": "cycle_state",
                }
            ],
        )

    wave_expected = expected.get("wave_hypothesis") or {}
    wave_payload = shadow_payloads["wave_hypothesis"]
    replay_status = wave_expected.get("replay_consistency_status")
    if replay_status and wave_payload.get("replay_consistency_status") != replay_status:
        add_state_drift(
            expected_target_state={"wave_hypothesis": dict(wave_expected)},
            actual_state={
                "wave_hypothesis": {
                    "replay_consistency_status": wave_payload.get(
                        "replay_consistency_status"
                    ),
                    "wave_label_candidate": wave_payload.get("wave_label_candidate"),
                }
            },
            evidence_refs=[
                {
                    "object_type": wave_payload.get("object_type"),
                    "field": "replay_consistency_status",
                }
            ],
        )

    mid_cycle_payloads = shadow_payloads["mid_cycle_states"]
    for scope_key in ("fund_cycle", "industry_cycle"):
        scope_expected = expected.get(scope_key) or {}
        allowed_states = scope_expected.get("allowed") or []
        scope_payload = mid_cycle_payloads.get(scope_key) or {}
        if allowed_states and scope_payload.get("state") not in allowed_states:
            add_state_drift(
                expected_target_state={scope_key: dict(scope_expected)},
                actual_state={scope_key: {"state": scope_payload.get("state")}},
                evidence_refs=[
                    {
                        "object_type": scope_payload.get("object_type"),
                        "scope": scope_key,
                        "field": "state",
                    }
                ],
            )

    growth_expected = expected.get("growth_potential_profile") or {}
    growth_payload = shadow_payloads["growth_potential_profile"]
    allowed_growth_status = growth_expected.get("allowed_status") or []
    if allowed_growth_status and growth_payload.get("status") not in allowed_growth_status:
        add_state_drift(
            expected_target_state={"growth_potential_profile": dict(growth_expected)},
            actual_state={
                "growth_potential_profile": {"status": growth_payload.get("status")}
            },
            evidence_refs=[
                {
                    "object_type": growth_payload.get("object_type"),
                    "field": "status",
                }
            ],
        )

    top_risk_expected = expected.get("top_risk_profile") or {}
    top_risk_payload = shadow_payloads["top_risk_profile"]
    max_risk_level = top_risk_expected.get("max_risk_level")
    if max_risk_level and not _risk_leq(
        str(top_risk_payload.get("risk_level")),
        str(max_risk_level),
    ):
        add_state_drift(
            expected_target_state={"top_risk_profile": dict(top_risk_expected)},
            actual_state={
                "top_risk_profile": {
                    "risk_level": top_risk_payload.get("risk_level"),
                    "risk_type": top_risk_payload.get("risk_type"),
                }
            },
            evidence_refs=[
                {
                    "object_type": top_risk_payload.get("object_type"),
                    "field": "risk_level",
                }
            ],
        )

    linkage_expected = expected.get("cycle_linkage_state") or {}
    linkage_payload = shadow_payloads["cycle_linkage_state"]
    expected_support = linkage_expected.get("supports_continuation")
    expected_local_global = linkage_expected.get("local_end_vs_global_end") or []
    local_global_misread = False
    if isinstance(expected_support, bool):
        if bool(linkage_payload.get("supports_continuation")) != expected_support:
            local_global_misread = True
    if expected_local_global:
        if linkage_payload.get("local_end_vs_global_end") not in expected_local_global:
            local_global_misread = True
    if local_global_misread:
        evidence_refs = [
            {
                "object_type": linkage_payload.get("object_type"),
                "field": "supports_continuation",
            },
            {
                "object_type": linkage_payload.get("object_type"),
                "field": "local_end_vs_global_end",
            },
        ]
        gaps.append(
            _build_local_global_gap(
                sample=sample,
                benchmark_run_id=benchmark_run_id,
                trace_id=trace_id,
                expected_target_state={"cycle_linkage_state": dict(linkage_expected)},
                actual_state={
                    "cycle_linkage_state": {
                        "supports_continuation": linkage_payload.get(
                            "supports_continuation"
                        ),
                        "local_end_vs_global_end": linkage_payload.get(
                            "local_end_vs_global_end"
                        ),
                        "linkage_phase": linkage_payload.get("linkage_phase"),
                    }
                },
                evidence_refs=evidence_refs,
            )
        )
        if sample.sample_bucket == B4_INTERACTION_GUARDRAIL_SAMPLE:
            breaches.append(
                build_interaction_guardrail_breach(
                    breach_id=f"{benchmark_run_id}:breach:{GUARDRAIL_CODE_LOCAL_GLOBAL_END}",
                    symbol=sample.stock_code,
                    trade_date=sample.trade_date,
                    sample_bucket=sample.sample_bucket,
                    guardrail_code=GUARDRAIL_CODE_LOCAL_GLOBAL_END,
                    severity=SEVERITY_HIGH,
                    summary="局部结束与全局结束语义发生误读，违反 continuation guardrail。",
                    evidence_refs=evidence_refs,
                    trace_id=trace_id,
                    benchmark_run_id=benchmark_run_id,
                    rule_version=sample.rule_version,
                )
            )

    hard_violation_count = sum(1 for gap in gaps if gap.severity == SEVERITY_HIGH) + len(
        breaches
    )
    warn_count = sum(1 for gap in gaps if gap.severity == SEVERITY_WARN)
    if hard_violation_count > 0:
        assessment_grade = ASSESSMENT_GRADE_FAIL
    elif warn_count > 0:
        assessment_grade = ASSESSMENT_GRADE_WARN
    else:
        assessment_grade = ASSESSMENT_GRADE_PASS

    gap_group_distribution: dict[str, int] = {}
    for gap in gaps:
        gap_group_distribution[gap.gap_group] = gap_group_distribution.get(
            gap.gap_group,
            0,
        ) + 1

    summary = build_assessment_summary(
        benchmark_run_id=benchmark_run_id,
        symbol=sample.stock_code,
        trade_date=sample.trade_date,
        assessment_grade=assessment_grade,
        hard_violation_count=hard_violation_count,
        warn_count=warn_count,
        sample_bucket_summary={sample.sample_bucket: 1},
        gap_group_distribution=gap_group_distribution,
        stability_risk_summary={
            "small_cycle_state": cycle_payload.get("cycle_state"),
            "state_stability_level": cycle_payload.get("state_stability_level"),
            "wave_replay_consistency_status": wave_payload.get(
                "replay_consistency_status"
            ),
        },
        hold_quality_risk_summary={"status": "not_in_scope"},
        interaction_risk_summary={
            "guardrail_breach_count": len(breaches),
            "continuation_supported": linkage_payload.get("supports_continuation"),
        },
        rule_version=sample.rule_version,
    )

    trace_bundle = build_trace_bundle(
        trace_id=trace_id,
        symbol=sample.stock_code,
        trade_date=sample.trade_date,
        sample_bucket=sample.sample_bucket,
        target_state_type=sample.target_state_type,
        m1_context=dict(m1_context or {}),
        m2_formal={"small_cycle_state": cycle_payload},
        m2_shadow=shadow_payloads,
        m3_context=dict(m3_context or {}),
        m4_assessment={
            "assessment_summary": summary.to_payload(),
            "gap_ids": [gap.gap_id for gap in gaps],
            "interaction_guardrail_breach_ids": [
                breach.breach_id for breach in breaches
            ],
        },
        benchmark_run_id=benchmark_run_id,
        rule_version=sample.rule_version,
    )

    return BenchmarkAssessmentResult(
        summary=summary,
        gap_records=tuple(gaps),
        trace_bundle=trace_bundle,
        interaction_guardrail_breaches=tuple(breaches),
    )
